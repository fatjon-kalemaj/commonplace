# Notion connector (working)

Reads pages shared with an internal integration. Read-only: the HTTP client
allows `GET` plus `POST /search` and `POST /databases/{id}/query`, and refuses
everything else before a request is sent.

## Setup

1. Go to https://www.notion.so/my-integrations and create an internal integration.
2. Under Capabilities, enable **Read content** only. Leave Update content,
   Insert content and user information access off.
3. In Notion, open each top-level page you want synced, choose
   **Connections**, and add the integration. Child pages inherit access.
4. Store the token:

   ```bash
   commonplace secrets set NOTION_TOKEN    # OS keychain
   # or: export NOTION_TOKEN=...
   ```

5. Enable it in your config:

   ```toml
   [connectors.notion]
   enabled = true
   ```

## What it reads

- Pages returned by `/v1/search`, newest edit first, stopping at the last sync cursor.
- Block children up to three levels deep, rendered to Markdown.
- A `select` property whose value is Meeting, Decision, Project, Task or Document
  becomes the record's kind hint. `people` properties become participants.

The demo uses recorded API responses in `demo/data/notion/` through the same code path.
