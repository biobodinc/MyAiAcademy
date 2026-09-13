import Constants from "expo-constants";
import { StatusBar } from "expo-status-bar";
import { useState } from "react";
import { ActivityIndicator, Platform, Text, View, useColorScheme } from "react-native";
import { SafeAreaProvider, SafeAreaView } from "react-native-safe-area-context";

import { HomeScreen } from "./src/ui/HomeScreen";
import { PairScreen } from "./src/ui/PairScreen";
import { DARK, LIGHT, styles } from "./src/ui/theme";
import { useHost } from "./src/useHost";

/** A first guess at this device's name, which the user can change before pairing. */
function suggestedDeviceName(): string {
  const platform = Platform.OS === "ios" ? "iPhone" : Platform.OS === "android" ? "Android" : "Web";
  const model = Constants.deviceName;
  return typeof model === "string" && model ? model : `My ${platform}`;
}

export default function App(): React.JSX.Element {
  const palette = useColorScheme() === "dark" ? DARK : LIGHT;
  const host = useHost();
  const [pairing, setPairing] = useState(false);
  const version = Constants.expoConfig?.version ?? "0.0.0";

  return (
    <SafeAreaProvider>
      <SafeAreaView style={[styles.screen, { backgroundColor: palette.background }]}>
        <StatusBar style={palette === DARK ? "light" : "dark"} />
        <View>
          <Text style={[styles.brand, { color: palette.text }]}>MyAI Academy</Text>
          <Text style={[styles.subtitle, { color: palette.muted }]}>
            Your AI, on every device you authorise.
          </Text>
        </View>

        {host.loading ? (
          <View style={{ flex: 1, justifyContent: "center" }}>
            <ActivityIndicator color={palette.muted} />
          </View>
        ) : pairing ? (
          <PairScreen
            palette={palette}
            deviceName={suggestedDeviceName()}
            onCancel={() => setPairing(false)}
            onPair={async (invite, name) => {
              await host.pair(invite, name);
              setPairing(false);
            }}
          />
        ) : (
          <HomeScreen
            palette={palette}
            connection={host.connection}
            credential={host.credential}
            status={host.status}
            problem={host.problem}
            busy={host.loading}
            onPair={() => setPairing(true)}
            onRefresh={() => void host.refresh()}
            onForget={() => void host.forget()}
          />
        )}

        <Text style={[styles.footer, { color: palette.muted }]}>
          v{version} · Private by default
        </Text>
      </SafeAreaView>
    </SafeAreaProvider>
  );
}
