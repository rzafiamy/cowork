# 8. Storage and Caching

Cowork uses the local disk to store artifacts, maintain workspaces, and cache external requests. This ensures data privacy and reduces redundant network traffic for external APIs.

## Storage Folders (`~/.cowork/storage/`)

The workspace storage directory acts as the central destination for files generated or managed by the agent:

* **Location:** `~/.cowork/storage/`
* **Purpose:** Any time the agent uses the `storage_write` tool (e.g., executing connectors), the file is persisted here in the persistent storage.
* **Usage:** Provides a safe boundary for agent I/O operations and acts as a localized "workspace" where user notes, markdown artifacts, or raw fetched data can be reliably retrieved across sessions without impacting the source code tree.

## API Cache (`~/.cowork/api_cache/`)

To optimize the use of external integrations and reduce redundant calls, Cowork implements a **Disk-Based TTL Cache** for HTTP requests (like web scraping, news fetching, and weather updates).

* **Location:** `~/.cowork/api_cache/`
* **Mechanism:**
  * Request URLs and payloads are hashed (SHA-256) to create a unique cache key (`<hash>.json`).
  * Responses are stored alongside a timestamp (`ts`) and the raw value.
* **TTL (Time To Live):** Different tools utilize specific TTLs to balance freshness and efficiency. For example:
  * Default Web Calls: `3600` seconds (1 hour).
  * News / Web Search: `1800` to `3600` seconds.
  * Weather Data: `600` seconds (10 mins).
  * Metadata/Wiki: `86400` to `604800` seconds (1 day to 1 week).
* **Benefits:** Saves tokens, minimizes rate limit errors with third-party APIs, and significantly speeds up agent execution times when requesting previously fetched data.
