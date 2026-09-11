import Constants from "expo-constants";
import { StatusBar } from "expo-status-bar";
import { useReducer } from "react";
import { StyleSheet, Text, View, useColorScheme } from "react-native";
import { SafeAreaProvider, SafeAreaView } from "react-native-safe-area-context";

import { describeConnection, reduceConnection, type ConnectionState } from "./src/connection";

const INITIAL: ConnectionState = { kind: "unpaired" };

export default function App() {
  const scheme = useColorScheme();
  const [connection] = useReducer(reduceConnection, INITIAL);
  const status = describeConnection(connection);
  const dark = scheme === "dark";
  const version = Constants.expoConfig?.version ?? "0.0.0";

  return (
    <SafeAreaProvider>
      <SafeAreaView style={[styles.screen, dark ? styles.screenDark : styles.screenLight]}>
        <StatusBar style={dark ? "light" : "dark"} />
        <View style={styles.header}>
          <Text style={[styles.brand, dark && styles.textDark]}>MyAI Academy</Text>
          <Text style={[styles.subtitle, dark && styles.mutedDark]}>
            Your AI, on every device you authorise.
          </Text>
        </View>

        <View style={[styles.card, dark ? styles.cardDark : styles.cardLight]}>
          <Text style={[styles.cardLabel, dark && styles.mutedDark]}>CONNECTION</Text>
          <Text style={[styles.cardValue, dark && styles.textDark]}>
            {status.emoji} {status.label}
          </Text>
        </View>

        <View style={[styles.card, dark ? styles.cardDark : styles.cardLight]}>
          <Text style={[styles.cardLabel, dark && styles.mutedDark]}>WHAT THIS APP IS</Text>
          <Text style={[styles.body, dark && styles.textDark]}>
            This phone app is a controller for the AI running on your own computer. It is not a
            separate AI, and it does not upload your conversations, memories or files anywhere.
          </Text>
        </View>

        <View style={[styles.card, styles.notice, dark ? styles.cardDark : styles.cardLight]}>
          <Text style={[styles.cardLabel, dark && styles.mutedDark]}>PLANNED · PHASE 6</Text>
          <Text style={[styles.body, dark && styles.textDark]}>
            Sign-in, QR pairing with your desktop, chat, skill and training status, and per-device
            permissions arrive in Phase 6, after accounts and device identity exist. Until then this
            app shows its connection state truthfully: not paired.
          </Text>
        </View>

        <Text style={[styles.footer, dark && styles.mutedDark]}>
          v{version} · Private by default
        </Text>
      </SafeAreaView>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, padding: 20, gap: 14 },
  screenLight: { backgroundColor: "#f6f7fb" },
  screenDark: { backgroundColor: "#0e1016" },
  header: { marginBottom: 6 },
  brand: { fontSize: 28, fontWeight: "700", letterSpacing: -0.5 },
  subtitle: { marginTop: 4, fontSize: 14, color: "#5c6275" },
  card: { borderRadius: 16, padding: 16, borderWidth: 1 },
  cardLight: { backgroundColor: "#ffffff", borderColor: "#e2e5ee" },
  cardDark: { backgroundColor: "#161925", borderColor: "#262b3c" },
  notice: { borderStyle: "dashed" },
  cardLabel: { fontSize: 11, fontWeight: "700", letterSpacing: 1, color: "#5c6275" },
  cardValue: { marginTop: 6, fontSize: 18, fontWeight: "600" },
  body: { marginTop: 6, fontSize: 14, lineHeight: 20 },
  footer: { marginTop: "auto", textAlign: "center", fontSize: 12, color: "#5c6275" },
  textDark: { color: "#eef0f6" },
  mutedDark: { color: "#9aa1b8" },
});
