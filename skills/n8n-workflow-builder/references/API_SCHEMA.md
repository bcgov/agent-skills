# n8n workflow JSON — the POST schema

Write workflows so they can be POSTed to the n8n public API
(`https://docs.n8n.io/api/api-reference/`, `POST /api/v1/workflows`). This skill only
**produces** the JSON; `tools/n8n/push.sh` posts it (it sends exactly the writable fields).

## Top-level (what the API accepts on create/update)

```json
{
  "name": "<name>",
  "nodes": [ /* node objects */ ],
  "connections": { /* wiring, by node name */ },
  "settings": { "executionOrder": "v1" }
}
```

`push.sh` builds the request body as `{name, nodes, connections, settings, staticData?}` — so
those are the only fields you need to emit. The API assigns the workflow `id`, and ignores
`active` on create (push.sh activates separately). Do not include `id`, `active`, `tags`, or
read-only metadata.

## Nodes

`nodes` is an array of node objects (see `N8N_NODES.md` for each type):

```json
{
  "parameters": { },
  "id": "unique-within-workflow",
  "name": "Unique Node Name",
  "type": "n8n-nodes-base.webhook",
  "typeVersion": 2,
  "position": [x, y]
}
```

- `name` must be unique (connections reference it).
- `id` must be unique within the workflow.
- `position` is `[x, y]` for editor layout; lay the chain left-to-right.
- `parameters.command` is a plain string, or — for a long multi-line command (the merge/report
  nodes, > 200 chars) — a JSON **array of lines** that `push.sh` joins with `\n` and `pull.sh`
  splits back, so it diffs cleanly in git. Short/single-line commands stay strings. See `N8N_NODES.md`.

## Connections

`connections` maps a **source node name** to its outputs. Each output is a list of lists of
targets (`main[outputIndex][...] -> { node, type, index }`):

```json
"connections": {
  "Webhook": { "main": [[{ "node": "Cluster status", "type": "main", "index": 0 }]] },
  "Cluster status": { "main": [[{ "node": "Merge snippets", "type": "main", "index": 0 }]] },
  "Merge snippets": { "main": [[{ "node": "Report", "type": "main", "index": 0 }]] },
  "Report": { "main": [[{ "node": "Respond to Webhook (HTML)", "type": "main", "index": 0 }]] }
}
```

The Sticky Note is not wired (it has no connections).

## Posting (not this skill's job)

```bash
# from tools/n8n/, with the port-forward up and N8N_API_KEY set
./push.sh --dry-run workflows/<name>.json   # validate
./push.sh workflows/<name>.json             # create/update + activate
```

`push.sh` matches by `name` (a same-named workflow is overwritten, otherwise created); ids are
never tracked or written back. Keep the JSON pretty-printed (one workflow per file) so it diffs
cleanly under version control, matching what `pull.sh` writes.
