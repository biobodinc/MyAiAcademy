/** The handful of pieces every screen is built from. */

import type { ReactNode } from "react";
import { ActivityIndicator, Pressable, Text, View } from "react-native";

import { styles, type Palette } from "./theme";

export function Card({
  palette,
  label,
  children,
  dashed = false,
  tone,
}: {
  palette: Palette;
  label?: string;
  children: ReactNode;
  dashed?: boolean;
  tone?: "danger" | "warning";
}): React.JSX.Element {
  const borderColor =
    tone === "danger" ? palette.danger : tone === "warning" ? palette.warning : palette.border;
  return (
    <View
      style={[
        styles.card,
        dashed && styles.dashed,
        { backgroundColor: palette.surface, borderColor },
      ]}
    >
      {label ? <Text style={[styles.cardLabel, { color: palette.muted }]}>{label}</Text> : null}
      {children}
    </View>
  );
}

export function Button({
  palette,
  label,
  onPress,
  disabled = false,
  busy = false,
  variant = "primary",
}: {
  palette: Palette;
  label: string;
  onPress: () => void;
  disabled?: boolean;
  busy?: boolean;
  variant?: "primary" | "quiet";
}): React.JSX.Element {
  const primary = variant === "primary";
  const inactive = disabled || busy;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled: inactive, busy }}
      onPress={onPress}
      disabled={inactive}
      style={({ pressed }) => [
        styles.button,
        {
          backgroundColor: primary ? palette.accent : "transparent",
          borderWidth: primary ? 0 : 1,
          borderColor: palette.border,
          opacity: inactive ? 0.45 : pressed ? 0.8 : 1,
        },
      ]}
    >
      {busy ? (
        <ActivityIndicator color={primary ? palette.accentText : palette.text} />
      ) : (
        <Text style={[styles.buttonLabel, { color: primary ? palette.accentText : palette.text }]}>
          {label}
        </Text>
      )}
    </Pressable>
  );
}

/** A problem the person needs to read, never a toast that vanishes before it is understood. */
export function Problem({
  palette,
  children,
}: {
  palette: Palette;
  children: ReactNode;
}): React.JSX.Element {
  return (
    <Card palette={palette} label="WHAT WENT WRONG" tone="danger">
      <Text style={[styles.body, { color: palette.text }]}>{children}</Text>
    </Card>
  );
}
