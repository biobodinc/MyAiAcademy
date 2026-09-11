//! Supervises the `myai-core` local service.
//!
//! Startup protocol: the service prints one line `MYAI_CORE_READY {json}` to stdout once
//! it is listening. The JSON names its base URL and the *file* holding the API token; the
//! shell reads the token from that file (owner-only permissions) and never from stdout.
//! This keeps the platform data-directory convention in exactly one place (Python).
//!
//! In release builds the service is a bundled sidecar (`binaries/myai-core-<triple>`).
//! In debug builds, when no sidecar has been built, we fall back to `uv run myai-core`
//! from the repository so `pnpm tauri dev` works out of the box.

use std::{
    fs,
    path::PathBuf,
    sync::{Arc, Mutex},
    time::{Duration, Instant},
};

use serde::{Deserialize, Serialize};
use tauri::AppHandle;
use tauri_plugin_shell::{
    process::{CommandChild, CommandEvent},
    ShellExt,
};

const READY_PREFIX: &str = "MYAI_CORE_READY ";
const READY_TIMEOUT: Duration = Duration::from_secs(45);
const SIDECAR_NAME: &str = "myai-core";

#[derive(Debug, Clone, Serialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum ServiceState {
    Starting,
    Running { base_url: String, pid: Option<u32> },
    Failed { error: String },
}

#[derive(Debug, Clone, Serialize)]
pub struct ServiceCredentials {
    pub base_url: String,
    pub token: String,
}

#[derive(Debug, Deserialize)]
struct ReadyPayload {
    base_url: String,
    token_file: PathBuf,
    pid: Option<u32>,
}

#[derive(Debug, thiserror::Error)]
pub enum ServiceError {
    #[error("the local AI service is still starting")]
    NotReady,
    #[error("the local AI service failed to start: {0}")]
    Failed(String),
    #[error("could not read the local API token: {0}")]
    Token(String),
    #[error("could not launch the local AI service: {0}")]
    Spawn(String),
}

#[derive(Default)]
struct Inner {
    state: Option<ServiceState>,
    child: Option<CommandChild>,
    token_file: Option<PathBuf>,
}

pub struct ServiceManager {
    inner: Mutex<Inner>,
}

impl ServiceManager {
    pub fn new() -> Self {
        Self {
            inner: Mutex::new(Inner::default()),
        }
    }

    pub fn state(&self) -> ServiceState {
        self.inner
            .lock()
            .expect("service mutex poisoned")
            .state
            .clone()
            .unwrap_or(ServiceState::Starting)
    }

    pub fn credentials(&self) -> Result<ServiceCredentials, ServiceError> {
        let (state, token_file) = {
            let inner = self.inner.lock().expect("service mutex poisoned");
            (inner.state.clone(), inner.token_file.clone())
        };
        match state {
            Some(ServiceState::Running { base_url, .. }) => {
                let token_file = token_file.ok_or(ServiceError::NotReady)?;
                let token = fs::read_to_string(&token_file)
                    .map_err(|e| ServiceError::Token(e.to_string()))?
                    .trim()
                    .to_owned();
                if token.is_empty() {
                    return Err(ServiceError::Token("token file is empty".into()));
                }
                Ok(ServiceCredentials { base_url, token })
            }
            Some(ServiceState::Failed { error }) => Err(ServiceError::Failed(error)),
            _ => Err(ServiceError::NotReady),
        }
    }

    /// Spawn the service and watch its output until the ready line arrives.
    pub fn start(self: &Arc<Self>, app: &AppHandle) {
        {
            let mut inner = self.inner.lock().expect("service mutex poisoned");
            inner.state = Some(ServiceState::Starting);
        }
        let spawned = spawn_service(app);
        let (mut rx, child) = match spawned {
            Ok(pair) => pair,
            Err(err) => {
                log::error!("{err}");
                self.fail(err.to_string());
                return;
            }
        };
        let pid = child.pid();
        {
            let mut inner = self.inner.lock().expect("service mutex poisoned");
            inner.child = Some(child);
        }

        let manager = Arc::clone(self);
        tauri::async_runtime::spawn(async move {
            let started = Instant::now();
            let mut stderr_tail: Vec<String> = Vec::new();
            loop {
                let remaining = READY_TIMEOUT.saturating_sub(started.elapsed());
                if remaining.is_zero() && !manager.is_running() {
                    manager.fail(format!(
                        "timed out after {}s waiting for the service to report ready.\n{}",
                        READY_TIMEOUT.as_secs(),
                        stderr_tail.join("\n")
                    ));
                    break;
                }
                let event =
                    tokio::time::timeout(remaining.max(Duration::from_millis(50)), rx.recv()).await;
                match event {
                    Ok(Some(CommandEvent::Stdout(bytes))) => {
                        let line = String::from_utf8_lossy(&bytes);
                        if let Some(json) = line.trim().strip_prefix(READY_PREFIX) {
                            match serde_json::from_str::<ReadyPayload>(json) {
                                Ok(ready) => manager.ready(ready, pid),
                                Err(e) => manager.fail(format!("malformed ready line: {e}")),
                            }
                        } else {
                            log::debug!("myai-core: {}", line.trim_end());
                        }
                    }
                    Ok(Some(CommandEvent::Stderr(bytes))) => {
                        let line = String::from_utf8_lossy(&bytes).trim_end().to_owned();
                        log::debug!("myai-core: {line}");
                        stderr_tail.push(line);
                        if stderr_tail.len() > 40 {
                            stderr_tail.remove(0);
                        }
                    }
                    Ok(Some(CommandEvent::Error(err))) => {
                        manager.fail(format!("process error: {err}"));
                        break;
                    }
                    Ok(Some(CommandEvent::Terminated(status))) => {
                        if !manager.is_running() || status.code != Some(0) {
                            manager.fail(format!(
                                "the service exited (code {:?}).\n{}",
                                status.code,
                                stderr_tail.join("\n")
                            ));
                        }
                        break;
                    }
                    Ok(Some(_)) => {}
                    Ok(None) => break,
                    Err(_) => {
                        // Timeout tick; loop re-evaluates the deadline.
                    }
                }
            }
        });
    }

    pub fn restart(self: &Arc<Self>, app: &AppHandle) -> Result<(), ServiceError> {
        self.stop();
        self.start(app);
        Ok(())
    }

    pub fn stop(&self) {
        let child = self
            .inner
            .lock()
            .expect("service mutex poisoned")
            .child
            .take();
        if let Some(child) = child {
            if let Err(e) = child.kill() {
                log::warn!("failed to stop myai-core: {e}");
            }
        }
    }

    fn is_running(&self) -> bool {
        matches!(
            self.inner.lock().expect("service mutex poisoned").state,
            Some(ServiceState::Running { .. })
        )
    }

    fn ready(&self, payload: ReadyPayload, pid: u32) {
        log::info!("myai-core ready at {}", payload.base_url);
        let mut inner = self.inner.lock().expect("service mutex poisoned");
        inner.token_file = Some(payload.token_file);
        inner.state = Some(ServiceState::Running {
            base_url: payload.base_url,
            pid: payload.pid.or(Some(pid)),
        });
    }

    fn fail(&self, error: String) {
        log::error!("myai-core failed: {error}");
        let mut inner = self.inner.lock().expect("service mutex poisoned");
        inner.state = Some(ServiceState::Failed { error });
    }
}

type Spawned = (tauri::async_runtime::Receiver<CommandEvent>, CommandChild);

fn spawn_service(app: &AppHandle) -> Result<Spawned, ServiceError> {
    match app.shell().sidecar(SIDECAR_NAME) {
        Ok(cmd) => cmd.spawn().map_err(|e| ServiceError::Spawn(e.to_string())),
        Err(sidecar_err) => {
            if cfg!(debug_assertions) {
                log::warn!(
                    "no bundled sidecar ({sidecar_err}); falling back to `uv run myai-core`"
                );
                spawn_dev_service(app)
            } else {
                Err(ServiceError::Spawn(sidecar_err.to_string()))
            }
        }
    }
}

/// Debug-only: run the service from the monorepo with uv.
fn spawn_dev_service(app: &AppHandle) -> Result<Spawned, ServiceError> {
    let repo_root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../..")
        .canonicalize()
        .map_err(|e| ServiceError::Spawn(format!("cannot resolve repository root: {e}")))?;
    app.shell()
        .command("uv")
        .args([
            "run",
            "--project",
            &repo_root.to_string_lossy(),
            "myai-core",
        ])
        .current_dir(repo_root)
        .spawn()
        .map_err(|e| ServiceError::Spawn(format!("{e} (is `uv` installed and on PATH?)")))
}
