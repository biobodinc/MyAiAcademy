# ADR-0008 llama.cpp for local inference; lexical retrieval first

## Context

Phase 2 needs chat that runs on ordinary consumer hardware, including CPU-only laptops,
and knowledge retrieval that works offline. The spec names PyTorch/Transformers for the
AI stack, which Phase 4 training will use.

## Decision

- **Inference:** GGUF models through llama.cpp (`llama-cpp-python`), behind the
  `ModelProvider` protocol. It runs quantised 1–7B models on CPU at usable speed and uses
  CUDA/Metal/ROCm when present. PyTorch remains the training runtime (Phase 4); adapters
  it produces are converted to GGUF for inference.
- **Supply:** a small curated catalog of permissively or clearly licensed GGUF files. The
  licence is shown and explicitly accepted before any network request. Downloads resume
  and are verified against the host-declared SHA-256 (or a pinned hash).
- **Retrieval:** BM25 over SQLite FTS5 with porter stemming. It is lexical, fast, private
  and dependency-free. The UI and API label it as lexical; embedding-based retrieval is a
  planned addition, not an assumption.
- **Memory:** explicit only. Nothing is remembered without the user adding it.

## Consequences

- The optional `local-inference` extra compiles llama.cpp from source where no wheel is
  available; CI tests the service without it so the "runtime unavailable" path stays
  honest. Release builds include it.
- Retrieval quality depends on shared vocabulary between question and passage; the chat
  shows which passages were used so users can judge.
