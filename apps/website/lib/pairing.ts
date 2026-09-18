/**
 * What a pairing QR code carries, for adding a device to an *account*.
 *
 * Not to be confused with the host pairing in `apps/mobile/src/pairing.ts`. That one joins a
 * phone to one computer and carries a certificate fingerprint to pin, because the phone must
 * accept that machine and no other. This one joins a device to an account on the central
 * server, which is reached over ordinary HTTPS with a public certificate — so there is
 * nothing to pin, and the payload is only where to ask and what to say.
 *
 * Versioned from the start: a device built against `v: 1` should refuse a payload it does
 * not understand rather than guess at it.
 */
export const PAIRING_PAYLOAD_VERSION = 1;

export interface PairingPayload {
  v: number;
  /** Origin of the account server the device should call. */
  api: string;
  /** The single-use code, also shown on screen so it can be typed instead. */
  code: string;
}

export function pairingPayload(api: string, code: string): string {
  const payload: PairingPayload = { v: PAIRING_PAYLOAD_VERSION, api, code };
  return JSON.stringify(payload);
}

/** `26001182` → `2600 1182`. Grouped digits are markedly easier to copy by eye. */
export function groupCode(code: string): string {
  return code.replace(/(\d{4})(?=\d)/g, "$1 ");
}
