# 7. Background Jobs and Tracing

Cowork isn't just a synchronous chat application. It manages asynchronous, background tasks and provides rich observability into the agent process.

## Background Jobs (The Sentinel)
The `JobManager` handles concurrent agent executions.
* When a command is dispatched (especially for scheduled triggers), it is registered as an `AgentJob`.
* The system enforces a global concurrency limit (default: 10).
* Job state (`pending`, `running`, `completed`, `failed`) is persisted in `~/.cowork/jobs.json`.
* If the CLI quits forcefully, running jobs are safely marked as "Ghost Jobs" upon restart.

## Cron Tasks
Users can schedule tasks via the `cron.py` system or via agent tool calls (`CronScheduleTool`).
* Jobs can be scheduled to run `once`, `daily`, `weekly`, or via custom expression.
* The main polling loop evaluates the `cron_jobs.json` list and triggers standard background `AgentJob` paths whenever a trigger time is reached.

## Tracing
Because the agent uses a complex REACT loop, Meta-Router, and various Context boundaries, debugging what the LLM *thought* vs what it *did* is crucial.
* `WorkflowTraceLogger` captures highly structured, timestamped JSONL traces for **every single job**.
* Traces are grouped by their Session ID inside `~/.cowork/traces/` or `workspace/<slug>/traces/`.
* Traces include payload data for prompts, router categorizations, tool executions, and step budget usages.
* These traces can be parsed by `trace.py:render_trace_timeline` to render a human-readable, colorized terminal overview of the workflow.
