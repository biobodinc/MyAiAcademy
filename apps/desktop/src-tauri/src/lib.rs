//! MyAI Academy desktop shell.
//!
//! The shell is deliberately thin. Its jobs are:
//!
//! 1. Supervise the local Python service (`myai-core`) as a sidecar process.
//! 2. Hand the webview the per-installation API token read from disk (the token is never
//!    embedded in frontend code).
//! 3. Provide native affordances the webview may not have: folder picker, opening https
//!    links in the system browser.
//!
//! Everything else lives in the service or the React UI.

mod service;

use std::sync::Arc;

use tauri::{Manager, RunEvent};

use crate::service::{ServiceCredentials, ServiceManager, ServiceState};

#[tauri::command]
fn service_state(manager: tauri::State<'_, Arc<ServiceManager>>) -> ServiceState {
    manager.state()
}

#[tauri::command]
fn local_api_credentials(
    manager: tauri::State<'_, Arc<ServiceManager>>,
) -> Result<ServiceCredentials, String> {
    manager.credentials().map_err(|e| e.to_string())
}

#[tauri::command]
fn restart_service(
    app: tauri::AppHandle,
    manager: tauri::State<'_, Arc<ServiceManager>>,
) -> Result<(), String> {
    manager.restart(&app).map_err(|e| e.to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(
            tauri_plugin_log::Builder::new()
                .level(if cfg!(debug_assertions) {
                    log::LevelFilter::Debug
                } else {
                    log::LevelFilter::Info
                })
                .build(),
        )
        .setup(|app| {
            let manager = Arc::new(ServiceManager::new());
            app.manage(manager.clone());
            manager.start(app.handle());
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            service_state,
            local_api_credentials,
            restart_service
        ])
        .build(tauri::generate_context!())
        .expect("error while building MyAI Academy")
        .run(|app, event| {
            if let RunEvent::Exit = event {
                if let Some(manager) = app.try_state::<Arc<ServiceManager>>() {
                    manager.stop();
                }
            }
        });
}
