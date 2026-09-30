# Signing the installers

## The short version

You cannot self-sign your way out of the warnings. Windows and macOS do not ask "is this
signed", they ask "is this signed by someone we already trust", and a certificate you made
yourself is not. Signing is still worth doing — it proves a build has not been altered since
it left the runner, and it gives the app one stable identity instead of a new one each
release — but it does not remove a single dialog.

| System | Unsigned | Self-signed | What clears it |
| ------ | -------- | ----------- | -------------- |
| Windows SmartScreen | "Windows protected your PC", Unknown publisher | Same warning; the signature also reports as untrusted, because the certificate chains to nothing Windows trusts | OV certificate plus download volume, or EV for day one |
| Windows Defender | May quarantine the bundled Python runtime on heuristics | No change — signing is not an antivirus input | Submit a false positive to Microsoft |
| macOS Gatekeeper | "Apple could not verify this app is free of malware" | No change; Gatekeeper accepts only Developer ID | Apple Developer ID plus notarisation |
| Linux, ChromeOS | Nothing blocks | Nothing blocks | Already fine |

## What each option costs

**Windows, EV code-signing certificate — roughly $400 to $700 a year.** The only option that
is clean on the first download. EV certificates carry SmartScreen reputation from the start.
Since June 2023 every code-signing certificate requires its private key on FIPS 140-2 Level 2
hardware, so this arrives as a USB token or a cloud HSM subscription, and CI has to reach it —
either a self-hosted runner with the token attached, or a cloud signing service.

**Windows, OV code-signing certificate — roughly $200 to $400 a year.** Cheaper, and the
warning fades as downloads accumulate against that certificate. Early users still see it. Same
hardware-key requirement.

**macOS, Apple Developer Program — $99 a year.** This is the good deal of the three. It gives
a Developer ID Application certificate and access to the notary service. Notarisation is what
actually matters: Apple scans the build, returns a ticket, the ticket is stapled into the
package, and Gatekeeper opens it without complaint.

**Linux — free.** Nothing to buy. If the packages ever go into an apt repository, sign the
repository metadata with a GPG key; the `.deb` files themselves do not need it.

## What is wired up already

The release workflow supports all of it and does none of it by default, so an unsigned build
is a working build rather than a broken one.

- **`WINDOWS_SIGNING=certificate`** with the `WINDOWS_CERTIFICATE` and
  `WINDOWS_CERTIFICATE_PASSWORD` secrets signs the Windows installers. Note that importing a
  certificate is not sufficient on its own: the bundler needs a thumbprint in its config, which
  the workflow now writes at build time. Before that fix, a configured certificate produced an
  unsigned installer and said nothing about it.
- **`MACOS_SIGNING=certificate`** with `APPLE_CERTIFICATE`, `APPLE_CERTIFICATE_PASSWORD`,
  `APPLE_SIGNING_IDENTITY`, `APPLE_ID`, `APPLE_PASSWORD` and `APPLE_TEAM_ID` signs and
  notarises. Anything else means ad-hoc signing, which builds and runs but does not satisfy
  Gatekeeper. Passing an empty or malformed `APPLE_CERTIFICATE` used to abort the macOS bundle
  entirely, so a missing certificate cost the build rather than the signature.
- **`scripts/make_windows_cert.ps1`** generates a self-signed certificate if you want the
  publisher name and the tamper check without buying anything. It will not remove the warning.

## What we do instead

Every published file is listed on the download page with its SHA-256, and a `SHA256SUMS` file
is published next to the installers so the check is one command:

```
sha256sum -c SHA256SUMS          # Linux, macOS
certutil -hash-file <file> SHA256   # Windows
```

An unsigned build with a published hash is a claim you can verify. An unsigned build with no
hash is not. That is the honest substitute, and the download page says which prompt each
system will show and what to do about it rather than pretending the prompts are not there.

## If Defender quarantines the sidecar

`myai-core` is a PyInstaller bundle, and packers of that shape are a common heuristic match.
Signing does not help. Submit the file at
<https://www.microsoft.com/en-us/wdsi/filesubmission> as a false positive; Microsoft usually
clears it within a few days, and the clearance applies to that exact build, so it has to be
repeated per release until the certificate earns reputation.
