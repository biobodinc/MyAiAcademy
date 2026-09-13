/**
 * The camera half of pairing.
 *
 * The camera is the only permission this app declares, it is requested at the moment it is
 * used rather than at launch, and it is released as soon as a code is read. Where there is
 * no camera — the web preview, a simulator, a device where permission was refused — the
 * screen says so and the pasted-code path is the way through, rather than a dead viewfinder.
 */

import { useState } from "react";
import { Platform, Text, View } from "react-native";
import { CameraView, useCameraPermissions } from "expo-camera";

import { Button, Card } from "./parts";
import { styles, type Palette } from "./theme";

export function QrScanner({
  palette,
  onScanned,
  width,
}: {
  palette: Palette;
  onScanned: (raw: string) => void;
  width: number;
}): React.JSX.Element {
  const [permission, requestPermission] = useCameraPermissions();
  const [done, setDone] = useState(false);

  if (Platform.OS === "web") {
    return (
      <Card palette={palette} label="SCAN THE CODE" dashed>
        <Text style={[styles.body, { color: palette.muted }]}>
          The web preview has no camera. Paste the pairing code below instead.
        </Text>
      </Card>
    );
  }

  if (!permission) {
    return (
      <Card palette={palette} label="SCAN THE CODE">
        <Text style={[styles.body, { color: palette.muted }]}>Checking the camera…</Text>
      </Card>
    );
  }

  if (!permission.granted) {
    return (
      <Card palette={palette} label="SCAN THE CODE">
        <Text style={[styles.body, { color: palette.text }]}>
          {permission.canAskAgain
            ? "The camera is used only to read the pairing code your computer is showing. " +
              "Nothing is recorded, and no image leaves this phone."
            : "Camera access is turned off for this app in your phone's settings. You can " +
              "paste the pairing code below instead."}
        </Text>
        {permission.canAskAgain ? (
          <View style={{ marginTop: 12 }}>
            <Button
              palette={palette}
              label="Allow the camera"
              onPress={() => void requestPermission()}
            />
          </View>
        ) : null}
      </Card>
    );
  }

  const size = Math.max(180, Math.min(width, 320));
  return (
    <Card palette={palette} label="SCAN THE CODE">
      <View
        style={{
          marginTop: 10,
          height: size,
          borderRadius: 12,
          overflow: "hidden",
          backgroundColor: "#000",
        }}
      >
        <CameraView
          style={{ flex: 1 }}
          facing="back"
          barcodeScannerSettings={{ barcodeTypes: ["qr"] }}
          // Stop listening after the first read: a second scan of the same single-use code
          // would only race the first.
          onBarcodeScanned={
            done
              ? undefined
              : ({ data }) => {
                  setDone(true);
                  onScanned(data);
                }
          }
        />
      </View>
      <Text style={[styles.body, { color: palette.muted }]}>
        Point this at the QR code on your computer's Security page.
      </Text>
    </Card>
  );
}
