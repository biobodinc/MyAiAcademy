// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Biobodinc. Part of MyAI Academy.
import { useEffect } from "react";
import { Navigate, Route, Routes } from "react-router";

import { Layout } from "./components/Layout";
import { ServiceGate } from "./components/ServiceGate";
import { Alert, Button, Spinner } from "./components/ui";
import { AuditPage } from "./features/audit/AuditPage";
import { ChatPage } from "./features/chat/ChatPage";
import { ConsolePage } from "./features/console/ConsolePage";
import { DashboardPage } from "./features/dashboard/DashboardPage";
import { HardwarePage } from "./features/hardware/HardwarePage";
import { KnowledgePage } from "./features/knowledge/KnowledgePage";
import { MemoryPage } from "./features/memory/MemoryPage";
import { ModelsPage } from "./features/models/ModelsPage";
import { OnboardingWizard } from "./features/onboarding/OnboardingWizard";
import { ProjectsPage } from "./features/projects/ProjectsPage";
import { PrivacyPage } from "./features/privacy/PrivacyPage";
import { SecurityPage } from "./features/security/SecurityPage";
import { PortablePage } from "./features/portable/PortablePage";
import { SyncPage } from "./features/sync/SyncPage";
import { ProfilePage } from "./features/profile/ProfilePage";
import { SettingsPage } from "./features/settings/SettingsPage";
import { SkillsPage } from "./features/skills/SkillsPage";
import { StoragePage } from "./features/storage/StoragePage";
import { describeError, usePreferences } from "./lib/api";
import { applyTheme } from "./lib/theme";

export function App() {
  return (
    <ServiceGate>
      <ThemedRoutes />
    </ServiceGate>
  );
}

function ThemedRoutes() {
  const prefs = usePreferences();
  useEffect(() => {
    applyTheme(prefs.data?.theme);
  }, [prefs.data?.theme]);

  if (prefs.isPending) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner label="Loading your preferences…" />
      </div>
    );
  }

  /**
   * A failed read is not the same fact as "not onboarded yet", and conflating the two emptied
   * the window. `onboarded` used to fall back to false whenever preferences were missing for
   * any reason, so one failed GET /api/preferences redirected to /onboarding, where the wizard
   * had no preferences either and rendered a bare spinner. The result was a white window
   * reading "Loading" — no sidebar, no message, no way back, and permanent, because nothing
   * refetches preferences on its own. Nothing threw, so the error boundary never saw it: the
   * app was not crashing, it was confidently showing a loading state for data that was never
   * going to arrive. A burst of requests from switching pages quickly, or a second copy of
   * myai-core holding the SQLite file, is enough to produce that one failure.
   */
  if (!prefs.data) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <Alert tone="danger" title="Could not read your preferences">
          <p>{prefs.isError ? describeError(prefs.error) : "The service returned no settings."}</p>
          <p className="mt-2 text-fg-muted">
            Your AI and its data are untouched. This is the app failing to read its own settings,
            which it needs before it can decide which screen to show you.
          </p>
          <div className="mt-3">
            <Button onClick={() => void prefs.refetch()}>Try again</Button>
          </div>
        </Alert>
      </div>
    );
  }

  const onboarded = prefs.data.onboarding_completed;

  return (
    <Routes>
      <Route path="/onboarding" element={<OnboardingWizard />} />
      {onboarded ? (
        <Route element={<Layout />}>
          <Route index element={<DashboardPage />} />
          <Route path="chat" element={<ChatPage />} />
          <Route path="console" element={<ConsolePage />} />
          <Route path="models" element={<ModelsPage />} />
          <Route path="memory" element={<MemoryPage />} />
          <Route path="knowledge" element={<KnowledgePage />} />
          <Route path="skills" element={<SkillsPage />} />
          <Route path="profile" element={<ProfilePage />} />
          <Route path="hardware" element={<HardwarePage />} />
          <Route path="storage" element={<StoragePage />} />
          <Route path="projects" element={<ProjectsPage />} />
          <Route path="privacy" element={<PrivacyPage />} />
          <Route path="security" element={<SecurityPage />} />
          <Route path="sync" element={<SyncPage />} />
          <Route path="portable" element={<PortablePage />} />
          <Route path="activity" element={<AuditPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      ) : (
        <Route path="*" element={<Navigate to="/onboarding" replace />} />
      )}
    </Routes>
  );
}
