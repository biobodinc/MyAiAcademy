"use client";

import QRCode from "qrcode";
import { useEffect, useState } from "react";

import { ACCOUNT_API } from "@/lib/account";
import { groupCode, pairingPayload } from "@/lib/pairing";

/**
 * A pairing code, offered two ways: scan it, or type it.
 *
 * The QR is the quick path and the digits are the fallback for anyone whose camera will not
 * cooperate, so both are on screen at once rather than behind a toggle. The countdown is
 * there because a code that has quietly lapsed looks exactly like one that has not.
 *
 * It counts down against the server's absolute `expiresAt` rather than a duration it decrements
 * locally: a tab that was backgrounded, or a clock that drifted, would otherwise keep showing
 * time on a code the server has already stopped honouring.
 */
export function PairingInvite({ code, expiresAt }: { code: string; expiresAt: string }) {
  const [qr, setQr] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    let cancelled = false;
    QRCode.toDataURL(pairingPayload(ACCOUNT_API, code), { margin: 1, width: 220 })
      .then((url) => {
        if (!cancelled) setQr(url);
      })
      .catch(() => {
        // No QR is survivable — the digits below are the whole code.
        if (!cancelled) setQr(null);
      });
    return () => {
      cancelled = true;
    };
  }, [code]);

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  const left = Math.max(0, Math.ceil((new Date(expiresAt).getTime() - now) / 1000));
  const minutes = Math.floor(left / 60);
  const seconds = String(left % 60).padStart(2, "0");

  return (
    <div className="mt-5 border-l-2 border-accent py-1 pl-5">
      <p className="datum text-accent uppercase">Pairing code</p>
      <div className="mt-4 flex flex-col gap-6 sm:flex-row sm:items-start">
        {qr ? (
          // eslint-disable-next-line @next/next/no-img-element -- a data: URI, not a file to optimise
          <img
            src={qr}
            alt={`QR code containing pairing code ${groupCode(code)}`}
            width={160}
            height={160}
            className="rounded-sharp border border-border bg-white p-2"
          />
        ) : null}
        <div>
          <p className="datum text-fg-muted uppercase">Or type this code</p>
          <p className="datum mt-1 text-3xl tracking-[0.2em] text-fg">{groupCode(code)}</p>
          <p className="datum mt-2 text-fg-muted">
            {left > 0 ? `expires in ${minutes}:${seconds}` : "expired — generate another"}
          </p>
        </div>
      </div>
      <p className="mt-4 max-w-md text-sm text-fg-muted">
        Scan this on the device you are adding, or type the digits. It works once. Anyone who has it
        could add a device to your account, so do not share it or leave it on screen.
      </p>
    </div>
  );
}
