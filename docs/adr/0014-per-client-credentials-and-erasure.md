# ADR-0014 Per-client credentials, and an erase that erases

- Status: accepted
- Date: 2026-09-12
- Extends ADR-0003 (loopback-only local API with a per-installation token).

## Context

Phase 5 of the spec is accounts, device identity and authorization, secure storage, the
Privacy Center and audit (§47, §51-§53, §60-§62).

Two of those cannot be built honestly yet, and one can be built better than it looks.

**Accounts cannot.** An account needs an account server: somewhere to hold identities,
issue tokens and be operated over time. This repository is published, holds no secrets, and
the product decision about who runs that service — and what, if anything, it costs — has not
been made. Building a local imitation of an account would teach the user something false
about where their identity lives, which is the one thing this project refuses to do.

**Device identity can, but not the way the word suggests.** The service binds to
127.0.0.1, so there are no remote devices to identify; a credential issued today is used by
programs on the same machine. That is still worth having, and the reason is concrete: today
every client reads the same installation token, so "let this tool try my AI" is
indistinguishable from "give this tool the master key", and there is no way to withdraw
access from one program without changing it for all of them.

**Erasure can, and the usual version of it is a lie.** "Delete my data" often means a flag
in a row. The user cannot check it, and it is trivially reversible by whoever holds the
database.

## Decision

**Every client holds its own credential, and only the installation itself can hand one out.**

- The installation token stays what it has always been: the owner's credential, readable
  only by the user's own account on this machine, read by the desktop shell at start-up.
- Any other program gets a credential of its own, either issued directly in the app or
  obtained by redeeming a **pairing code**: eight digits, single use, five minutes, burned
  after five wrong attempts, and every attempt written to the audit log.
- Authentication resolves a caller: the owner, or a named client. What a client does is
  recorded against it.
- **Only the owner may grant or revoke**, and only the owner may export or erase. A paired
  client can use the AI and read the security page; it cannot issue itself a spare key. A
  privilege boundary that only exists in the UI is not a boundary, so it is enforced in the
  route.
- **Revocation takes effect on the client's next request**, because the credential is
  checked against the database on every request rather than cached.
- Only SHA-256 hashes of credentials and codes are stored. A secret is shown once. A copy
  of the database therefore contains no working key, and a lost credential is replaced
  rather than recovered — stated wherever one is issued.
- SHA-256 rather than a slow KDF is deliberate: these are 256-bit random values, not
  guessable passwords, and pairing codes are bounded by expiry and an attempt counter. A
  slow hash would buy nothing and cost every request.
- **The failed-attempt counter is written in its own transaction.** A rejected attempt
  raises, the request is rolled back, and a counter that rolled back with it would count
  nothing while appearing to bound guessing.

**Secret storage is checked, not assumed.** At start-up the data directory and token file
are tightened if they are group- or world-readable, and the change is logged. The Security
page reports what was verified — and says plainly that on Windows, where access is governed
by ACLs a mode bit does not describe, nothing was verified, rather than showing a
reassuring tick.

**Export contains the data and none of the keys.** The database is copied through SQLite's
backup API so the copy is consistent while the service runs. Credentials are excluded on
purpose: they are access grants, not the user's data, and putting them in a file the user
might email themselves would be a quiet hole. Model weights are listed, not copied, because
an export the user cannot store is not an export. The archive carries a manifest saying
exactly what is and is not inside it.

**Erase deletes rows.** Not a flag: `DELETE` on every table that holds user data, leaving
the installation in its first-run state. It needs a typed phrase, and it says what it cannot
reach — copies made elsewhere, and data already on disk that a forensic tool could recover
because deleting a file does not overwrite it. A test asserts that every table in the schema
is either erased or explicitly listed as infrastructure, so a table added later cannot
silently survive an erase.

**Accounts are stated as absent.** `AccountState` reports `linked: false, available: false`
with a sentence saying there is no account server and no code path that would send anything
anywhere, and that an account is planned as the way to obtain installers and sign in on more
than one device. The app, the CLI and the website all read from that one place.

## Consequences

- Phase 6 (mobile pairing) has the mechanism it needs: codes, credentials, revocation and a
  caller identity. What it will add is reaching the service from another device, which today
  is deliberately impossible.
- The security page can be honest about a genuinely narrow threat model: this protects
  against other programs and other users on this machine, not against an attacker who has
  already taken over the user's account.
- Erase is dangerous by construction. It is owner-only, twice-confirmed, and previewed with
  counts before anything happens.
- Accounts remain a product decision, not an engineering one. When it is made, the honest
  local half of it is already here: a caller identity, revocable credentials and an audit
  trail to attach it to.
