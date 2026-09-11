# myai-cli

Terminal client for the MyAI Academy local service.

```
myai serve                 # start the local service (same as `myai-core`)
myai status                # AI / internet / training availability
myai hardware              # detected hardware and capability tier
myai storage show          # storage root and per-category usage
myai storage set-root D:\MyAI
myai profile show
myai profile create --name Nova --owner Alex --personality "Helpful, curious, concise"
myai skills
myai run "/train video 4h" # run a slash command
myai audit                 # local security activity
```

The CLI finds the running service via `<app-data-dir>/local-api.json` and authenticates
with the per-installation token in `<app-data-dir>/local-api.token`. It never contacts
anything other than `127.0.0.1`.

Phase 2 additions:

```
myai models list | show <id> | download <id> | use <id> | remove <id>
myai chat "What do you remember?"     # one turn (streams)
myai chat                             # interactive; /memory etc. work inline
myai memory list | add "..." | forget <id> | clear
myai knowledge add notes.md paper.pdf | list | search "query" | remove <id>
```
