# ADR-0017 What a paired program may do

- Status: accepted
- Date: 2026-09-13
- Narrows ADR-0014 (per-client credentials).

## Context

ADR-0014 gave every program its own credential so one could be revoked without disturbing
the others. It did not narrow what a credential could _do_: a paired client could do anything
the owner could, minus a handful of owner-only actions.

That is fine for the user's own CLI and wrong for anything else. "Let this tool use my AI"
should not also mean "let it read every conversation I have ever had", and the difference
between a tool that summarises your notes and one that can rewrite them is exactly the
difference a person would want to be asked about.

## Decision

**Access is a set of named capabilities, granted by the owner, and default-deny.**

### The vocabulary is a list, and every entry is in prose

`security/capabilities.py` enumerates what can be granted, each with a title and a sentence
describing what it actually exposes. A consent screen listing `memory:write` asks people to
agree to nothing; one saying _"Change what your AI remembers — a tool with this can rewrite
what your AI believes about you"_ asks them something answerable.

Capabilities that touch what the user wrote are flagged `sensitive`, and a test checks that
every one of them is. The default grant contains none of them: it is enough to show a
dashboard and nothing else.

### Read and write are separate

`GET` and `HEAD` need the read capability; everything else needs the write one. Almost no
integration that reads your notes needs to rewrite them, and collapsing the two would make
the narrower, far more common grant unexpressible.

### The grant travels with the pairing code, not the redemption

The owner decides what a code will grant when they create it. A program that could name its
own permissions while redeeming would make the consent decorative. A client also cannot
change its own grant afterwards — that is owner-only, like issuing and revoking.

### One table, and unclassified means refused

`ROUTER_SCOPES` in `api/app.py` maps every router to its read and write capability, and a
router must appear there to be served at all. There is no "unclassified means allowed".

This is the same shape as the sync registry and the erase-coverage check, for the same
reason: the failure mode of "someone added an endpoint and nobody thought about scope" has
to be a red test rather than a quietly over-broad grant, because over-permission is
invisible until the day it matters.

### Owner-only stays owner-only

Issuing credentials, revoking them, changing a grant, exporting, erasing, restoring a
package and turning network access on are enforced inside their routes and are not reachable
through any capability. `FULL_GRANT` is everything a _client_ can hold, which is deliberately
less than what the owner can do.

## Migration

Clients paired before this existed were granted everything a client could do, because there
was no narrower option. Recording the full set for them states what is already true rather
than widening anything. Revoked clients are left empty: writing a full grant onto one would
make the audit trail read as though it had been re-authorised.

## Consequences

- Every new router forces a decision about scope, and a test fails until it is made.
- Narrowing a grant takes effect on the client's next request, like revocation.
- Permission changes are written to the audit log with what was added and what was taken
  away, so "when did this tool get access to my memories" is answerable.
- The mobile preset (`MOBILE_GRANT`) is what a phone controller needs: chat, memory reading
  and sync. Not knowledge files, and not rewriting what the AI remembers.

## What is not built

- **Per-route capabilities.** Scope is per router, split by method. A router mixing two very
  different concerns would be coarser than ideal; splitting the router is the fix, and none
  currently needs it.
- **Time-limited or one-shot grants.** A grant lasts until it is changed or the client is
  revoked.
- **Website authorization and a connected-apps directory** (§75). Both need the account
  decision — there is no account server, and an app directory implies one.
