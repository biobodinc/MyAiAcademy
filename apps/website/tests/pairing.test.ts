import { describe, expect, it } from "vitest";

import { PAIRING_PAYLOAD_VERSION, groupCode, pairingPayload } from "@/lib/pairing";

describe("pairing payload", () => {
  it("carries the version, the server to call and the code", () => {
    const parsed = JSON.parse(pairingPayload("https://accounts.example.com", "26001182"));
    expect(parsed).toEqual({
      v: PAIRING_PAYLOAD_VERSION,
      api: "https://accounts.example.com",
      code: "26001182",
    });
  });

  it("is versioned, so a device can refuse a payload it does not understand", () => {
    expect(PAIRING_PAYLOAD_VERSION).toBe(1);
  });

  it("stays compact enough for a QR that scans easily", () => {
    // Well inside version 4 at medium correction (~62 bytes); a longer payload needs a
    // denser symbol, which is what makes a code hard to scan off a screen.
    expect(pairingPayload("https://accounts.myaiacademy.app", "26001182").length).toBeLessThan(80);
  });
});

describe("groupCode", () => {
  it("groups eight digits into two fours", () => {
    expect(groupCode("26001182")).toBe("2600 1182");
  });

  it("leaves a short code alone", () => {
    expect(groupCode("2600")).toBe("2600");
  });
});
