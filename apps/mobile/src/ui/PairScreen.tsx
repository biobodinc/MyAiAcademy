/**
 * Pairing: scan the QR code your computer is showing, or paste it (spec §52, §55).
 *
 * Two things on this screen are load-bearing and must not be softened into decoration:
 *
 * 1. **The fingerprint.** It is shown in the same groups of four the desktop shows, so the
 *    user can compare the two by eye. That comparison is the entire trust decision — there
 *    is no certificate authority behind it — so it is given a screen of its own before
 *    anything is sent, not a line of small print under a button.
 * 2. **What this build can do.** If the app cannot pin a certificate it says so here, in
 *    plain words, and the Connect button does not work. It is not offered and then failed.
 */

import { useState } from "react";
import { ScrollView, Text, TextInput, View, useWindowDimensions } from "react-native";

import { InvalidInvite, fingerprintGroups, parseInvite, type PairingInvite } from "../pairing";
import { transportStatus } from "../transport";
import { Button, Card, Problem } from "./parts";
import { styles, type Palette } from "./theme";
import { QrScanner } from "./QrScanner";

interface Props {
  palette: Palette;
  deviceName: string;
  onCancel: () => void;
  onPair: (invite: PairingInvite, deviceName: string) => Promise<void>;
}

export function PairScreen({ palette, deviceName, onCancel, onPair }: Props): React.JSX.Element {
  const [invite, setInvite] = useState<PairingInvite | null>(null);
  const [pasted, setPasted] = useState("");
  const [name, setName] = useState(deviceName);
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { width } = useWindowDimensions();
  const transport = transportStatus();

  function accept(raw: string): void {
    try {
      setInvite(parseInvite(raw));
      setProblem(null);
    } catch (error) {
      setInvite(null);
      setProblem(
        error instanceof InvalidInvite ? error.message : "That pairing code could not be read.",
      );
    }
  }

  async function connect(): Promise<void> {
    if (!invite) return;
    setBusy(true);
    setProblem(null);
    try {
      await onPair(invite, name.trim() || "Phone");
    } catch (error) {
      setProblem(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
      <Text style={[styles.title, { color: palette.text }]}>Pair with your computer</Text>

      {!transport.canConnect ? (
        <Card palette={palette} label="THIS BUILD CANNOT PAIR" tone="warning" dashed>
          <Text style={[styles.body, { color: palette.text }]}>{transport.summary}</Text>
          <Text style={[styles.body, { color: palette.muted }]}>
            You can still read a pairing code here to check it is valid — nothing is sent.
          </Text>
        </Card>
      ) : null}

      {invite === null ? (
        <>
          <QrScanner palette={palette} onScanned={accept} width={width - 72} />
          <Card palette={palette} label="OR PASTE THE CODE">
            <Text style={[styles.body, { color: palette.muted }]}>
              On your computer: Security → Network access → Show pairing code, then Copy.
            </Text>
            <TextInput
              value={pasted}
              onChangeText={setPasted}
              placeholder="Paste the pairing code here"
              placeholderTextColor={palette.muted}
              multiline
              autoCapitalize="none"
              autoCorrect={false}
              style={[
                styles.input,
                {
                  color: palette.text,
                  borderColor: palette.border,
                  backgroundColor: "transparent",
                },
              ]}
            />
            <View style={{ marginTop: 12 }}>
              <Button
                palette={palette}
                label="Read this code"
                onPress={() => accept(pasted.trim())}
                disabled={pasted.trim() === ""}
              />
            </View>
          </Card>
        </>
      ) : (
        <>
          <Card palette={palette} label="CHECK THIS MATCHES YOUR COMPUTER">
            <Text style={[styles.cardValue, { color: palette.text }]}>{invite.hostName}</Text>
            <Text style={[styles.body, { color: palette.muted }]}>
              Your computer is showing this fingerprint. If the two do not match character for
              character, something else is answering — stop, and do not continue.
            </Text>
            <Text style={[styles.mono, { color: palette.text }]}>
              {fingerprintGroups(invite.certificateFingerprint)}
            </Text>
          </Card>

          <Card palette={palette} label="NAME THIS DEVICE">
            <Text style={[styles.body, { color: palette.muted }]}>
              This is the name you will revoke it by, on your computer.
            </Text>
            <TextInput
              value={name}
              onChangeText={setName}
              autoCapitalize="words"
              style={[styles.input, { color: palette.text, borderColor: palette.border }]}
            />
          </Card>

          <Button
            palette={palette}
            label={transport.canConnect ? "The fingerprints match — connect" : "Cannot connect"}
            onPress={() => void connect()}
            disabled={!transport.canConnect}
            busy={busy}
          />
          <Button
            palette={palette}
            variant="quiet"
            label="They do not match"
            onPress={() => {
              setInvite(null);
              setPasted("");
            }}
          />
        </>
      )}

      {problem ? <Problem palette={palette}>{problem}</Problem> : null}

      <Button palette={palette} variant="quiet" label="Back" onPress={onCancel} />
    </ScrollView>
  );
}
