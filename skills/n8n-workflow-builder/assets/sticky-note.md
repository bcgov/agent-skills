<!-- Sticky-note content for a built workflow's "Production URL" node. The builder fills the
     placeholders and uses the result as the stickyNote `content` (newlines escaped as \n in
     the JSON). This comment is scaffolding — drop it; keep the body below as the note content.
       <TITLE>     workflow title, e.g. My triage
       <BASE_URL>  spec.n8n.base_url from tools/n8n/config.yaml (the production n8n host)
       <PATH>      the Webhook node's path (= the workflow name)
       <QUERY>     query params, e.g. id=123 (drop the "?<QUERY>" if none)
-->
## <TITLE> — production URL

Click to run this triage — read-only and idempotent, safe to fire any time:

**<BASE_URL>/webhook/<PATH>?<QUERY>**

Built from cleaned snippets by the workflow-builder skill.
