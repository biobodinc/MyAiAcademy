# ADR-0018 Creative skills, and the cloud shortcut

- Status: accepted
- Date: 2026-09-13
- Follows ADR-0012 (levels come from benchmarks) and ADR-0013 (training optimises instructions).

## Context

The skill tree lists four creative skills: Images, Video, Music and Games. All four have
sat at `planned` since Phase 1, which is honest but not useful — "planned for Phase 10"
tells someone nothing they can act on.

They are not one problem. Three of them need a model that produces pixels or audio. One of
them does not.

## Decision

### Games is a real skill, because game design is text

Designing a game is stating mechanics that hold together, a difficulty curve that goes
somewhere, and a hook that fits in a line. That is prose and arithmetic, and the benchmark
machinery from Phase 3 already measures exactly that kind of thing.

So `games` has instructions, a 12-task benchmark and a 12-task practice set, graded by the
same deterministic checks the text skills use — bullet counts, word limits, arithmetic,
JSON shape, forbidden words. Nothing is scored by asking a model whether it liked the
answer. Every task in both sets is proven solvable by a reference answer in the test suite,
and a test asserts a _wrong_ answer fails, because a benchmark that passes everything
measures nothing.

Games requires Writing and Coding first, which the tree already enforced.

### Images, video and music get an interface and an honest refusal

`skills/creative.py` defines what a provider would have to offer, reports that none is
installed, and gives every surface the same sentence. `/learn images` now says what it
would actually take — a local model of several gigabytes and in practice a graphics card —
rather than naming a phase.

**A conforming provider must run locally.** This is written into the protocol's docstring
and tested: the module is checked for any networking import or URL, because a file about
generating media is exactly where a quiet HTTP call would hide.

## Why not just call a cloud API

It would take an afternoon and it would work well. It is refused because it is the single
clearest break of what this program tells people it does: a prompt does not leave the
machine. "Except for pictures" is not a footnote that can be added later without the claim
having been false all along.

The honest positions are a local provider or none. This build has none, and says so.

## Consequences

- One creative skill is genuinely learnable and trainable today, with a level that means
  something.
- The other three say what they need. When a local provider exists it registers through
  `creative.register()` and they become available with nothing else to change.
- A future provider that reaches the network would pass its own tests and fail the one in
  `test_creative.py`, which is deliberate.

## What is not built

- **Any generation.** No pixels, no audio, no video are produced by this build.
- **A model catalog for creative models.** Sizes, licences and hardware requirements differ
  enough from text models that the existing catalog shape should not be assumed to fit.
- **Coding as a "creative provider".** Coding is already a learnable text skill with its own
  benchmark (Phase 3); it needs nothing from this file.
