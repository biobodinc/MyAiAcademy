import { useEffect } from "react";
import { Navigate, Route, Routes } from "react-router";

import { Layout } from "./components/Layout";
import { ServiceGate } from "./components/ServiceGate";
import { Spinner } from "./components/ui";
import { AuditPage } from "./features/audit/AuditPage";
import { ConsolePage } from "./features/console/ConsolePage";
import { DashboardPage } from "./features/dashboard/DashboardPage";
import { HardwarePage } from "./features/hardware/HardwarePage";
import { OnboardingWizard } from "./features/onboarding/OnboardingWizard";
import { PrivacyPage } from "./features/privacy/PrivacyPage";
import { ProfilePage } from "./features/profile/ProfilePage";
import { SettingsPage } from "./features/settings/SettingsPage";
import { SkillsPage } from "./features/skills/SkillsPage";
import { StoragePage } from "./features/storage/StoragePage";
import { usePreferences } from "./lib/api";
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
        <Spinner />
      </div>
    );
  }
  const onboarded = prefs.data?.onboarding_completed ?? false;

  return (
    <Routes>
      <Route path="/onboarding" element={<OnboardingWizard />} />
      {onboarded ? (
        <Route element={<Layout />}>
          <Route index element={<DashboardPage />} />
          <Route path="console" element={<ConsolePage />} />
          <Route path="skills" element={<SkillsPage />} />
          <Route path="profile" element={<ProfilePage />} />
          <Route path="hardware" element={<HardwarePage />} />
          <Route path="storage" element={<StoragePage />} />
          <Route path="privacy" element={<PrivacyPage />} />
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
