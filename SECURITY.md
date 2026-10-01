# Security policy

## Reporting a vulnerability

Email **security@my-ai-academy.example** with what you found and how to reproduce it. Please
do not open a public issue for a security problem, and please give us a chance to fix it
before publishing.

We will acknowledge your report within 7 days and tell you what we intend to do about it. We
have no bug bounty and cannot pay for reports. What we will do is credit you when the fix
ships, if you want to be credited.

If you report in good faith — you did not access anyone else's data beyond what was needed to
demonstrate the problem, you did not degrade the service for anyone else, and you gave us a
reasonable chance to respond — we will not pursue legal action against you and will say so to
anyone who asks.

## What is in scope

- The local service (`myai-core`), especially anything that lets a process or device reach it
  that should not: the loopback binding, the per-install token, the opt-in network listener
  and its pinned certificate, and the per-client credentials.
- The desktop application, especially the boundary between the web view and the Rust shell.
- Device pairing: the pairing code, the certificate fingerprint, and revocation.
- The portable `.myai` package, especially its encryption and the import path.
- The account server and this website: authentication, session handling, the OAuth flows.

## Known limits, which are not vulnerabilities

These are design decisions, documented on the
[disclosures page](https://my-ai-academy-website.vercel.app/disclosures). A report that
restates one of them is not a finding, though an argument that one of them is worse than we
think it is, is welcome.

- **The coding benchmark runs code your local model wrote.** It runs in a separate
  interpreter with an import allow-list, a scratch directory, a timeout and resource limits.
  That contains accidents. It is explicitly not a security boundary against a model that is
  actively hostile, and a model you imported is software you chose to run.
- **Builds are not signed by a certificate authority.** Operating systems will warn about
  them. Every published file has a SHA-256 on the download page, and
  [docs/signing.md](docs/signing.md) explains what signing would and would not change.
- **An imported model is arbitrary third-party data** fed to `llama.cpp`. We verify a hash
  when the publisher provides one and label the model unverified when they do not.
- **Anyone with your user account on your computer can read your AI's data.** The files are
  protected by operating-system permissions, not by a second password, and the application
  says so rather than implying a vault.

## Supported versions

This project is pre-1.0 and only the most recent release is supported. There are no backports.
