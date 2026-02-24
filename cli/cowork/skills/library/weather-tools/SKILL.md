---
name: weather-tools
description: Get current conditions and weather forecasts.
triggers:
  - weather
  - forecast
  - meteo
  - météo
  - prévision
  - temperature
  - rain
  - climate
trust_tier: 2
tool_categories:
  - WEATHER_TOOLS
permissions:
  categories:
    - WEATHER_TOOLS
  tools:
    - openweather_current
    - openweather_forecast
---
# Weather Tools Skill

Purpose: Get current conditions and weather forecasts.

Workflow:
1. Prefer the smallest tool call that can complete the next step.
2. Validate required arguments before execution.
3. If a tool returns an error, repair arguments or switch to a safer fallback.
4. Synthesize concise results and stop tool usage once the user goal is met.

Guardrails:
- Never call tools outside this skill's declared permissions.
- Never fabricate tool output; report failures honestly.
