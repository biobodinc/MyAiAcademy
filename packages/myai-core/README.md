# myai-core

The local AI service behind MyAI Academy. It runs on the user's own machine, binds to
`127.0.0.1` only, and owns all private state (profile, preferences, storage layout,
audit log, and, in later phases, memory, knowledge, skills and training jobs).

```
myai-core            # start the service (default: 127.0.0.1, port from config)
myai-core --help
```

See `docs/architecture.md` at the repository root for the full picture and
`docs/adr/` for the decisions behind it.
