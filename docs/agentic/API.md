# 🌐 API & External Services

This document details all **API Endpoints** used by the MakiX Enterprise Agentic Workflow. These endpoints are categorized by their function: Inference, Data Ingestion, Image/Vision, and Tooling. All requests require a valid `Bearer Token` for authentication.

## 1. 🤖 Inference (LLM) Endpoints
These are the core endpoints that power the reasoning engine.

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| **POST** | `/chat/completions` | **Main Reasoning Loop**. Accepts `messages` array, `tools` schema, and returns `assistant` response or `tool_calls`. Used by `GeneralPurposeAgent.js`. |
| **GET** | `/models` | Fetches available models (e.g., `gpt-4`, `claude-3`) to populate the user settings dropdown. |
| **POST** | `/audio/transcriptions` | **Whisper Endpoint**. Converts uploaded user audio blobs into text prompts. |
| **POST** | `/audio/speech` | **TTS Endpoint**. Converts agent text responses into audio (Streaming). |

---

## 2. 🧠 Memory & RAG Endpoints
These endpoints manage the agent's long-term memory (Vector Store).

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| **POST** | `/ingest_data` | Uploads a file (PDF, TXT) to be parsed, chunked, and embedded into the vector database. |
| **POST** | `/query_data` | **Semantic Search**. Retrieves the top `k` most relevant chunks for a given `query` string. Used by `search_docs` tool. |
| **POST** | `/chunks` | Retrieves raw chunks based on metadata filters (e.g., specific page numbers). |
| **DELETE** | `/delete_collection` | Removes an ingested document and its vectors from the system. |
| **POST** | `/collection_exists` | Checks if a file has already been processed to prevent duplicate ingestion. |

---

## 3. 👁️ Vision & Image Endpoints
Capabilities for seeing and creating visual content.

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| **POST** | `/images/generations` | **DALL-E 3 / Stable Diffusion**. Generates images from text prompts. Returns a URL or Base64 string. |
| **POST** | `/recognize` | **GPT-4 Vision**. Analyzes an uploaded image blob and returns a text description based on the prompt. |

---

## 4. 🛠️ Tooling & Utility Endpoints (`/api/tools`)
These endpoints power specific agent tools. They act as proxies or specialized microservices.

### 🌍 Application Connectors
| Endpoint | Tool Name | Description |
| :--- | :--- | :--- |
| `/web/google_search` | `web_search` | Performs a Google SERP search. Returns titles, snippets, and links. |
| `/web/scrape_web` | `scrape_urls` | Fetches the raw HTML of a URL, cleans it, and returns the markdown text. |
| `/web/search_on_youtube` | `yt_search` | Searches YouTube for videos matching a query. |
| `/web/extract_yt_metadata` | `yt_meta` | Extracts views, likes, description, and tags from a YouTube URL. |
| `/web/youtube_transcript` | `yt_transcript` | Retrieves the closed captions/subtitles for a video. |
| `/web/wikipedia_info` | `wiki_get` | Fetches the summary and metadata of a Wikipedia page. |
| `/web/dweather` | `get_weather` | Real-time weather data for a location. |
| `/movies/get_latest_movies` | `tmdb_trending` | Fetches currently trending movies from TMDB. |
| `/movies/search_movies` | `tmdb_search` | Searches for movie details by title. |

---

## 5. 🛡️ Authentication & Headers
All requests must include the following headers:

```http
Authorization: Bearer <YOUR_API_TOKEN>
Content-Type: application/json
```

*   **Token**: Managed by `AuthService` and stored in local `chatbot_app.settings`.
*   **Endpoint Base**: Configurable in user settings (e.g., `https://api.openai.com/v1`, `http://localhost:11434/v1`).
