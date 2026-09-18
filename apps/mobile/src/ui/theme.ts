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
  background: "#fbfaf7",
  surface: "#ffffff",
  border: "#e0ddd4",
  text: "#1a1a17",
  muted: "#6b6961",
  accent: "#a83e20",
  accentText: "#ffffff",
  danger: "#9f1239",
  warning: "#a16207",
};

export const DARK: Palette = {
  background: "#141412",
  surface: "#1d1c19",
  border: "#2e2c27",
  text: "#edeae2",
  muted: "#9a968b",
  accent: "#e2724c",
  accentText: "#141412",
  danger: "#f2708d",
  warning: "#e0a33c",
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
