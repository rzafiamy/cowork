"""
⏰ Cron Tools
Tools for scheduling and managing recurring agent tasks.
"""

from typing import Any, Dict
from ..base import BaseTool
from ...cron import CronManager

class CronScheduleTool(BaseTool):
    @property
    def name(self) -> str:
        return "cron_schedule"

    @property
    def description(self) -> str:
        return (
            "Schedule a recurring or one-time task for the agent. "
            "Note: These tasks run ONLY while the CLI session is active and are NOT system cron jobs. "
            "The agent will be triggered at the specified time with the given prompt."
        )

    @property
    def category(self) -> str:
        return "CRON_TOOLS"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "The prompt the agent should execute at the scheduled time"},
                "schedule_type": {
                    "type": "string", 
                    "description": "How often to run",
                    "enum": ["once", "daily", "weekly"]
                },
                "schedule_value": {
                    "type": "string", 
                    "description": "Time to run. For 'daily' or 'weekly', use 'HH:MM' (24h format). For 'once', use ISO format or 'HH:MM' (defaults to tomorrow)."
                },
            },
            "required": ["prompt", "schedule_type", "schedule_value"],
        }

    def execute(self, prompt: str, schedule_type: str, schedule_value: str) -> str:
        self._emit("⏰ Scheduling cron task...")
        mgr = CronManager()
        job = mgr.add_job(
            prompt=prompt,
            schedule_type=schedule_type,
            schedule_value=schedule_value
        )
        return f"✅ Task scheduled: {schedule_type} @ {schedule_value} (Job ID: {job.job_id})"

class CronListTool(BaseTool):
    @property
    def name(self) -> str:
        return "cron_list"

    @property
    def description(self) -> str:
        return "List all active scheduled cron tasks."

    @property
    def category(self) -> str:
        return "CRON_TOOLS"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {"type": "object", "properties": {}, "required": []}

    def execute(self) -> str:
        self._emit("📋 Listing cron tasks...")
        mgr = CronManager()
        jobs = mgr.list_all()
        if not jobs:
            return "No active cron tasks."
        lines = ["Active Cron Tasks:\n"]
        for j in jobs:
            lines.append(f"• ID: {j.job_id} | {j.schedule_type} @ {j.schedule_value} | Prompt: {j.prompt[:50]}...")
        return "\n".join(lines)

class CronDeleteTool(BaseTool):
    @property
    def name(self) -> str:
        return "cron_delete"

    @property
    def description(self) -> str:
        return "Delete a scheduled cron task by its ID."

    @property
    def category(self) -> str:
        return "CRON_TOOLS"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "job_id": {"type": "string", "description": "The ID of the cron job to delete"}
            },
            "required": ["job_id"],
        }

    def execute(self, job_id: str) -> str:
        self._emit(f"🗑️ Deleting cron task: {job_id}...")
        mgr = CronManager()
        if mgr.remove_job(job_id):
            return f"✅ Cron task '{job_id}' deleted."
        return f"❌ Error: Cron task '{job_id}' not found."
