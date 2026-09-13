/** One palette and one set of shapes, so the screens look like one app. */

import { StyleSheet } from "react-native";

export interface Palette {
  background: string;
  surface: string;
  border: string;
  text: string;
  muted: string;
  accent: string;
  accentText: string;
  danger: string;
  warning: string;
}

export const LIGHT: Palette = {
  background: "#f6f7fb",
  surface: "#ffffff",
  border: "#e2e5ee",
  text: "#161925",
  muted: "#5c6275",
  accent: "#2f5bea",
  accentText: "#ffffff",
  danger: "#b3261e",
  warning: "#8a5a00",
};

export const DARK: Palette = {
  background: "#0e1016",
  surface: "#161925",
  border: "#262b3c",
  text: "#eef0f6",
  muted: "#9aa1b8",
  accent: "#7d9bff",
  accentText: "#0e1016",
  danger: "#ff8a80",
  warning: "#ffc66d",
};

export const styles = StyleSheet.create({
  screen: { flex: 1, padding: 20, gap: 14 },
  scroll: { paddingBottom: 32, gap: 14 },
  brand: { fontSize: 28, fontWeight: "700", letterSpacing: -0.5 },
  subtitle: { marginTop: 4, fontSize: 14 },
  title: { fontSize: 20, fontWeight: "700", letterSpacing: -0.3 },
  card: { borderRadius: 16, padding: 16, borderWidth: 1 },
  dashed: { borderStyle: "dashed" },
  cardLabel: { fontSize: 11, fontWeight: "700", letterSpacing: 1 },
  cardValue: { marginTop: 6, fontSize: 18, fontWeight: "600" },
  body: { marginTop: 6, fontSize: 14, lineHeight: 20 },
  mono: {
    marginTop: 10,
    fontSize: 13,
    lineHeight: 22,
    fontFamily: "Courier",
    letterSpacing: 0.5,
  },
  button: { borderRadius: 12, paddingVertical: 14, paddingHorizontal: 18, alignItems: "center" },
  buttonLabel: { fontSize: 15, fontWeight: "700" },
  input: {
    marginTop: 10,
    borderRadius: 12,
    borderWidth: 1,
    padding: 12,
    fontSize: 14,
    minHeight: 44,
  },
  row: { flexDirection: "row", alignItems: "center", gap: 10 },
  footer: { marginTop: "auto", textAlign: "center", fontSize: 12, paddingTop: 12 },
});
