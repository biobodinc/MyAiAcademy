# Bundled skill packages

Each folder is a **skill package**: what `/learn <skill>` installs.

```
<skill>/
├── skill.json        manifest: id, version, name, licence, benchmark areas, resources note
├── instructions.md   the behavioural instructions added to the AI's system prompt once learned
└── benchmark.json    the standardised evaluation (spec §43) that sets the skill's level
```

Only skills with a _measurable_ benchmark ship a package. Creative skills (images, video,
music, games) have none yet and therefore cannot be learned; the UI says so.

A benchmark task is `{id, area, prompt, checks[], max_tokens?}`. Checks are deterministic
graders from `myai_core/skills/graders.py` (`exact`, `contains_all`, `contains_any`,
`contains_none`, `regex`, `numeric`, `word_count`, `line_count`, `bullets`,
`json_object`, `python_tests`, `code_contains`). `python_tests` executes the model's code
in an isolated interpreter with an import allow-list, a scratch directory and resource
limits (`myai_core/skills/sandbox.py`).

The level is `round(score × 100)` where score is the mean task score; see ADR-0011.
