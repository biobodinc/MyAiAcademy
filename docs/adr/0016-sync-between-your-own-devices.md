# ADR-0016 Sync between your own devices

- Status: accepted
- Date: 2026-09-13
- Builds on ADR-0014 (per-client credentials) and ADR-0015 (reaching the host from a phone).

## Context

Phase 7 is the promise that your AI is the same AI on your laptop as on your desktop (§16,
§72), and that you can reach it from outside your home network through a relay (§18).

Sync is the feature where bugs do not announce themselves. A note that never arrives, a
conversation you deleted that comes back next week, a paragraph replaced by an older draft
from a machine that had been asleep — none of these produce an error. The user finds out
later, if at all, and cannot tell whether they misremembered. So the decisions below are
mostly about making those specific failures impossible rather than about throughput.

## Decision

### A counter, not a clock

Each installation keeps a counter and stamps every change with it. Syncing is "give me
everything you have done since number N".

Ordering by `updated_at` would have been less code, and would have been wrong: two machines'
clocks disagree, sometimes by hours, and a laptop that has been asleep disagrees with itself.
A counter is only ever compared against a cursor from the same installation, which makes
"everything you have not seen from me" an exact question rather than a guess.

### The stamp is applied by the session, not by the services

A `before_flush` listener on SQLAlchemy's `Session` stamps anything about to be written,
wherever it came from — a route, a background job, the CLI. The alternative, asking each
service to record what it changed, fails in one specific way and fails **silently**: someone
adds a feature, forgets the call, no test goes red, and that edit simply never leaves the
machine. Forgetting is not made available.

The listener is on the `Session` class rather than on one factory, because sessions are also
opened directly — `DeviceService` opens its own to count a failed pairing attempt outside the
transaction that is about to roll back — and a factory-level listener would miss those.

### Deletions travel

A deletion leaves a tombstone carrying the same counter value. Without them, sync sees "the
other device has a row I lack" and helpfully restores it. A delete that will not stay deleted
is worse than no sync at all.

A tombstone is also written for a deletion of something this machine never had, so a third
device cannot reintroduce it later.

### Conflicts are resolved deterministically, and the loser is kept

The rule is symmetric so that both machines reach the same answer: higher `version`, then
later `updated_at`, then higher install id purely as a tiebreak. If the two sides disagreed
about the outcome, each would hand the other "news" on every sync and they would swap
forever.

What matters more than the rule is what happens to the version that loses. It is written
whole into `sync_conflicts` — its fields, its version, where it came from — and shown in the
app. Discarding a person's writing because two clocks disagreed is not a trade-off this
program makes, and "last write wins" is usually a euphemism for doing exactly that.

### An explicit list of what does not travel

`sync/registry.py` names every table and which side of the line it falls on, and a test
fails if a new table is added without a decision. Three kinds stay put: credentials and
audit records (a device's credential is its own; copying it would make revocation
meaningless), facts about one machine (storage roots, installed models, benchmarks), and
work in progress (a job cannot be continued elsewhere).

Knowledge documents are excluded for a different reason: the file bytes have nowhere to go
yet, and a document in the list that cannot be opened or searched is worse than not showing
it.

### Rows are re-bound to the receiving machine's AI

`ai_profile.ai_id` is generated per installation, so a memory's `ai_id` names nothing on
another machine — the foreign key fails outright, which is how this was found. The row is
not _about_ that key, though; it is about the user's AI, and each installation has its own
row for it. So the key is replaced on arrival.

This is also the line past which "one AI on two machines" stops being automatic. The two
installations agree about what the AI knows and has learned. Making them agree about who it
_is_ — one name, one set of goals — is the account question, and is not answered here.

### End-to-end encryption, built before the relay it is for

Two devices on the same network already have a private channel: the pinned TLS connection
from ADR-0015. The envelope (HKDF-SHA256 from the pairing credential, AES-256-GCM) adds
nothing there, and does not pretend to.

It exists for the relay in §18. A relay terminates TLS, so whoever runs it can read
everything passing through unless the traffic is already unreadable when it arrives.
Building and testing this now — with a test that puts a relay in the middle and shows it
gets nothing — means the relay can be added later without anyone re-litigating whether it
can be trusted. It cannot, and it does not need to be.

## What is built, and what is not

Built and tested, including two complete installations with two databases syncing over the
real HTTPS listener: the counter, the tombstones, the batch, conflict detection and
resolution, the preserved losers, the registry and its exclusions, the re-binding, and the
envelope.

**Not built: the relay.** It needs a server on the internet, and therefore the same decision
that blocks accounts — who runs it, and who pays for it. The encryption it would need is
done and proven; nothing about it is waiting on code.

**Not built: automatic syncing.** Nothing runs on a timer yet. A sync happens when it is
asked for. Deciding when a device should sync on its own is a question about battery,
metered connections and surprise, and it should be answered deliberately rather than by
defaulting to "every thirty seconds".

**Not built: a second device in anyone's hands.** The phone still cannot connect (ADR-0015),
so in practice today's peers are two desktop installations.

## Consequences

- Every synced table needs `sync_seq` and `sync_origin`, and every new table forces a
  decision. That is the intended cost.
- `sync_conflicts` holds whole copies of user rows, so it is user data: the Privacy Center's
  erase covers it, and its own completeness test is what caught that.
- The counter makes a restored backup safe in one direction only. A database restored from a
  backup has a lower counter than its peers remember, so its own changes since the backup
  would be skipped. Handling that properly — a new install id on restore — is not done, and
  is the first thing to build when backup and restore arrive in Phase 8.
