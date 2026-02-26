---
name: nextcloud-tools
description: Operate on Nextcloud files and folders, including uploading images/files directly from the web.
triggers:
  - nextcloud
  - upload
  - download
  - folder
  - search
  - save to nextcloud
  - sauvegarder sur nextcloud
  - enregistrer sur nextcloud
trust_tier: 4
tool_categories:
  - NEXTCLOUD_TOOLS
  - SEARCH_TOOLS
permissions:
  categories:
    - NEXTCLOUD_TOOLS
    - SEARCH_TOOLS
  tools:
    - nextcloud_create_folder
    - nextcloud_delete
    - nextcloud_download
    - nextcloud_list
    - nextcloud_search
    - nextcloud_upload
    - nextcloud_upload_from_url
    - google_cse_search
    - google_search
    - brave_search
---
# Nextcloud Tools Skill

Purpose: Operate on Nextcloud files and folders, including fetching real images/files
from the web and uploading them directly to Nextcloud — all in a single pipeline.

## Key Capability: Search → Save to Nextcloud

When a user asks to **find real images on the web and save them to Nextcloud**,
you CAN do this end-to-end without any limitations. Use this workflow:

1. **Search** for images using `google_cse_search` with `search_type="image"` (or
   `brave_search` / `google_search`). Extract the direct image URLs from the results.
2. **Create a folder** on Nextcloud using `nextcloud_create_folder` if needed.
3. **Upload each image** directly from its URL using `nextcloud_upload_from_url`.
   This tool downloads from the web and uploads to Nextcloud in ONE step — no local
   file or intermediate download is required.

**NEVER tell the user you cannot download images from URLs — you can, via `nextcloud_upload_from_url`.**

## Tool Reference

| Tool | When to use |
|------|-------------|
| `nextcloud_upload_from_url` | Download from a public URL and upload to Nextcloud directly (images, PDFs, etc.) |
| `nextcloud_upload` | Upload a file that already exists on the local filesystem |
| `nextcloud_create_folder` | Create a new folder in Nextcloud |
| `nextcloud_list` | List contents of a Nextcloud directory |
| `nextcloud_download` | Download a Nextcloud file to local disk |
| `nextcloud_delete` | Delete a file or folder from Nextcloud |
| `nextcloud_search` | Search for files inside Nextcloud |
| `google_cse_search` | Find images/content on the web (use `search_type="image"` for images) |

## Workflow (General)

1. Prefer the smallest tool call that can complete the next step.
2. Validate required arguments before execution.
3. If a tool returns an error, repair arguments or switch to a safer fallback.
4. Synthesize concise results and stop tool usage once the user goal is met.

## Guardrails

- Never fabricate tool output; report failures honestly.
- For `nextcloud_upload_from_url`, only direct public image/file URLs work.
  If a URL redirects to an HTML page (not the raw file), skip it and try the next result.
- Report each upload result clearly (success + remote path, or failure + reason).
