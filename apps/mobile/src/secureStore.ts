/**
 * Where the device credential actually lives on a phone (spec §55).
 *
 * iOS puts it in the Keychain and Android in the Keystore-backed shared preferences, both of
 * which survive a reinstall-free restart and neither of which is readable by another app.
 *
 * On the web preview there is no such place. Rather than quietly dropping the credential
 * into `localStorage` — where any script on the origin could read it — the web build keeps
 * it in memory for the session only. That build cannot pin a certificate and so cannot pair
 * in the first place, which makes an honest in-memory store the whole of what it needs.
 */

import { Platform } from "react-native";
import * as SecureStore from "expo-secure-store";

import {
  memoryStore,
  parseCredential,
  serialiseCredential,
  type CredentialStore,
  type DeviceCredential,
} from "./credential";

const KEY = "myai.device-credential.v1";

function keychainStore(): CredentialStore {
  return {
    async read(): Promise<DeviceCredential | null> {
      try {
        return parseCredential(await SecureStore.getItemAsync(KEY));
      } catch {
        // An unreadable keychain entry reads as unpaired, which the user can recover from
        // by pairing again. Guessing at a partial credential is not recoverable.
        return null;
      }
    },
    async write(credential: DeviceCredential): Promise<void> {
      await SecureStore.setItemAsync(KEY, serialiseCredential(credential), {
        keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
      });
    },
    async clear(): Promise<void> {
      await SecureStore.deleteItemAsync(KEY);
    },
  };
}

export function credentialStore(): CredentialStore {
  return Platform.OS === "web" ? memoryStore() : keychainStore();
}
