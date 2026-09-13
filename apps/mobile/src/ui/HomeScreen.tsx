/**
 * What your AI is doing, as seen from the phone (spec §6, §52).
 *
 * The phone is a controller, not a second AI, so every line here is the host's own answer
 * repeated — including "I can't". When the phone is not paired, or cannot verify the host,
 * that is what the screen is about; it does not show a hopeful dashboard of nothing.
 */

import { RefreshControl, ScrollView, Text, View } from "react-native";

import { describeConnection, type ConnectionState } from "../connection";
import { describeAvailability, type HostStatus } from "../hostStatus";
import type { DeviceCredential } from "../credential";
import { fingerprintGroups } from "../pairing";
import { transportStatus } from "../transport";
import { Button, Card, Problem } from "./parts";
import { styles, type Palette } from "./theme";

interface Props {
  palette: Palette;
  connection: ConnectionState;
  credential: DeviceCredential | null;
  status: HostStatus | null;
  problem: string | null;
  busy: boolean;
  onPair: () => void;
  onRefresh: () => void;
  onForget: () => void;
}

export function HomeScreen({
  palette,
  connection,
  credential,
  status,
  problem,
  busy,
  onPair,
  onRefresh,
  onForget,
}: Props): React.JSX.Element {
  const link = describeConnection(connection);
  const transport = transportStatus();

  return (
    <ScrollView
      contentContainerStyle={styles.scroll}
      refreshControl={
        credential ? (
          <RefreshControl refreshing={busy} onRefresh={onRefresh} tintColor={palette.muted} />
        ) : undefined
      }
    >
      <Card palette={palette} label="CONNECTION">
        <Text style={[styles.cardValue, { color: palette.text }]}>
          {link.emoji} {link.label}
        </Text>
        {credential ? (
          <Text style={[styles.body, { color: palette.muted }]}>
            Paired as “{credential.deviceId}” · verified by this fingerprint:
          </Text>
        ) : null}
        {credential ? (
          <Text style={[styles.mono, { color: palette.muted }]}>
            {fingerprintGroups(credential.pin.certificateFingerprint)}
          </Text>
        ) : null}
      </Card>

      {problem ? <Problem palette={palette}>{problem}</Problem> : null}

      {credential === null ? (
        <>
          <Card palette={palette} label="WHAT THIS APP IS">
            <Text style={[styles.body, { color: palette.text }]}>
              This app is a controller for the AI running on your own computer. It is not a separate
              AI, and it does not upload your conversations, memories or files anywhere.
            </Text>
          </Card>
          {transport.canConnect ? null : (
            <Card palette={palette} label="THIS BUILD CANNOT PAIR" tone="warning" dashed>
              <Text style={[styles.body, { color: palette.text }]}>{transport.summary}</Text>
            </Card>
          )}
          <Button palette={palette} label="Pair with your computer" onPress={onPair} />
        </>
      ) : (
        <>
          {status ? (
            <>
              <Availability
                palette={palette}
                label="YOUR AI"
                value={status.ai}
                detail={status.aiDetail}
              />
              <Availability
                palette={palette}
                label="TRAINING"
                value={status.training}
                detail={status.trainingDetail}
              />
              <Card palette={palette} label="PRIVACY">
                <Text style={[styles.cardValue, { color: palette.text }]}>
                  {status.cloudUploads === 0
                    ? "Nothing has been uploaded"
                    : `${status.cloudUploads} uploads recorded`}
                </Text>
                <Text style={[styles.body, { color: palette.muted }]}>
                  Privacy mode: {status.privacyMode} · host version {status.serviceVersion}
                </Text>
              </Card>
            </>
          ) : (
            <Card palette={palette} label="YOUR AI" dashed>
              <Text style={[styles.body, { color: palette.muted }]}>
                Nothing to show until your computer answers.
              </Text>
            </Card>
          )}
          <View style={{ gap: 10 }}>
            <Button palette={palette} label="Refresh" onPress={onRefresh} busy={busy} />
            <Button
              palette={palette}
              variant="quiet"
              label="Forget this computer"
              onPress={onForget}
            />
          </View>
        </>
      )}
    </ScrollView>
  );
}

function Availability({
  palette,
  label,
  value,
  detail,
}: {
  palette: Palette;
  label: string;
  value: Parameters<typeof describeAvailability>[0];
  detail: string;
}): React.JSX.Element {
  const described = describeAvailability(value);
  return (
    <Card palette={palette} label={label}>
      <Text style={[styles.cardValue, { color: palette.text }]}>
        {described.emoji} {described.label}
      </Text>
      <Text style={[styles.body, { color: palette.muted }]}>{detail}</Text>
    </Card>
  );
}
