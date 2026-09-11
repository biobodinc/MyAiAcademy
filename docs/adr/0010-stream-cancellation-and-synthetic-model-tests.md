# ADR-0010 Real stream cancellation and testing against the real runtime

## Context

Two things were found while finishing Phase 2:

1. When a client stopped reading a chat stream, Starlette cancelled the response task
   but never closed the synchronous generator driving llama.cpp. The generator stayed
   suspended at its last `yield`: the model kept its context, the runtime lock was never
   released (every later message would block forever), and the partial reply was never
   written to the conversation.
2. All chat tests used an injected fake backend. Hugging Face was unreachable from the
   development environment, so the real `llama-cpp-python` path had never run. A fake
   cannot reveal backend-specific facts (for example, llama.cpp's streamed chunks carry
   no usage block, so token counts were silently `null` with a real model).

## Decision

- **Cancellation is cooperative and always persists.** `ChatService.send` accepts a
  `threading.Event`; it checks the flag per chunk, closes the backend generator in a
  `finally`, and writes the assistant message with `finish_reason="cancelled"` (also when
  the consumer closes the generator outright). `api/streaming.py` runs the generator on
  its own thread and sets the flag the moment the SSE response ends for any reason.
  A live-server test aborts a stream and asserts the backend generator was closed, the
  partial reply was stored, and the next message streams within seconds.
- **The real runtime is tested with a synthetic model.** `conftest.build_tiny_gguf`
  writes a ~160 KB llama-architecture GGUF (byte-fallback vocabulary, two blocks, a chat
  template) with the `gguf` writer. `test_real_runtime.py` loads it through
  `LlamaCppProvider` and drives the API: load, chat SSE, benchmark inference, unload. The
  tests are skipped where the optional extra is absent and run in a dedicated CI job that
  builds llama.cpp. Output quality is not asserted; only that the real code path works.
- **User-supplied models are first-class but clearly labelled.** `POST /api/models/import`
  registers a GGUF the user already has, copies it under `Models/imported/` unless it is
  already inside the Models folder, records its SHA-256 and a `user-supplied` licence
  record. The user confirms their rights; the app does not claim to have verified them.

## Consequences

- `ModelEntry` is no longer catalog-only: it carries `id`, `name`, `source` and `license`
  at the top level and `catalog` becomes optional. UI and CLI key on `id`.
- The disclosure about chat being unconfirmed narrows to what is still true: a catalog
  model on consumer hardware has not been run by the authors.
- Token counts with llama.cpp are derived (chunks counted; prompt size read from the
  context) and are therefore approximate for multi-token chunks.
