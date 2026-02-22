# 6. Configuration and Profiles

All configuration and profile data for Cowork is managed via `config.py` and stored centrally in `~/.cowork/`.

## The Config Manager
The system relies on `config.json` for base settings (like token limits, system temperatures, and default models). However:
* **Environment Variables (`.env`) ALWAYS take precedence.**
* Keys like `OPENAI_API_KEY`, `COWORK_MODEL`, or `FIRECRAWL_API_KEY` are parsed from the environment and instantly override stored JSON configs.
* Any sensitive keys (e.g. API keys) are actively purged from the `config.json` file upon save to prevent credential leaking.

## AI Profiles
Cowork supports quickly swapping between different models and endpoint combinations via `ai_profiles.json`.
* An AI Profile is a combination of: `Name`, `Endpoint`, `Model`, `API Key`, and `Description`.
* Using the CLI (e.g. `/profile switch local-ollama` or `/profile switch gpt-4`), you can change the target model dynamically without restarting the application or wiping the current session context.

## Token Tracker
The `TokenTracker` listens to the responses of the currently active endpoint and model, accumulating usage token data. This is persisted to `~/.cowork/tokens.json` to allow the user to visualize their API expenditure across different models over time.

## Storage and Caching
For details regarding how `~/.cowork/storage/` and `~/.cowork/api_cache/` are used to persist workspace files and network cache, please refer to [08_Storage_and_Caching.md](./08_Storage_and_Caching.md).
