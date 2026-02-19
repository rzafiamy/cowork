"""
⏰ Cron Service & Task Scheduler
Handles persistence and execution of scheduled agent tasks.
"""

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from .config import CONFIG_DIR

CRON_FILE = CONFIG_DIR / "cron_jobs.json"

class CronStatus:
    ENABLED  = "enabled"
    DISABLED = "disabled"
    RUNNING  = "running"
    FAILED   = "failed"

class CronJob:
    """Represents a scheduled agent task."""

    def __init__(
        self,
        job_id: Optional[str] = None,
        prompt: str = "",
        schedule_type: str = "once",  # once, daily, weekly, cron
        schedule_value: str = "",      # ISO timestamp, "05:00", or cron expr
        session_id: Optional[str] = None,
    ) -> None:
        self.job_id = job_id or str(uuid.uuid4())[:8]
        self.prompt = prompt
        self.schedule_type = schedule_type
        self.schedule_value = schedule_value
        self.session_id = session_id
        self.status = CronStatus.ENABLED
        self.created_at = datetime.now().isoformat()
        self.last_run: Optional[str] = None
        self.next_run: Optional[str] = None
        self.run_count: int = 0
        self.last_result: Optional[str] = None
        
        if not self.next_run:
            self.calculate_next_run()

    def calculate_next_run(self) -> None:
        """Robust next run calculation using Regex and dynamic fallbacks."""
        import re
        now = datetime.now()
        
        def find_time(val: str) -> Optional[datetime]:
            """Find HH:MM or HH:MM:SS in a string."""
            match = re.search(r'(\d{1,2}):(\d{2})(?::(\d{2}))?', val)
            if match:
                try:
                    h, m, s = match.groups()
                    return now.replace(hour=int(h), minute=int(m), second=int(s or 0), microsecond=0)
                except ValueError:
                    pass
            return None

        if self.schedule_type == "once":
            # 1. Try ISO
            try:
                self.next_run = datetime.fromisoformat(self.schedule_value).isoformat()
                return
            except Exception:
                pass
            
            # 2. Try Regex Time
            t = find_time(self.schedule_value)
            if t:
                if t <= now:
                    t += timedelta(days=1)
                self.next_run = t.isoformat()
                return

            # fallback: Now + 1 hour
            self.next_run = (now + timedelta(hours=1)).isoformat()
        
        elif self.schedule_type == "daily":
            t = find_time(self.schedule_value)
            if t:
                if t <= now:
                    t += timedelta(days=1)
                self.next_run = t.isoformat()
            else:
                self.next_run = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0).isoformat()
        
        elif self.schedule_type == "weekly":
            t = find_time(self.schedule_value)
            if t:
                if t <= now:
                    t += timedelta(days=7)
                self.next_run = t.isoformat()
            else:
                self.next_run = (now + timedelta(days=7)).replace(hour=9, minute=0, second=0).isoformat()

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, data: dict) -> "CronJob":
        j = cls.__new__(cls)
        j.__dict__.update(data)
        return j


class CronManager:
    """Manages persistent cron jobs."""

    def __init__(self) -> None:
        self._jobs: dict[str, CronJob] = {}
        self._load()

    def _load(self) -> None:
        if CRON_FILE.exists():
            try:
                with open(CRON_FILE) as f:
                    data = json.load(f)
                for jd in data.values():
                    self._jobs[jd["job_id"]] = CronJob.from_dict(jd)
            except Exception:
                self._jobs = {}

    def _save(self) -> None:
        with open(CRON_FILE, "w") as f:
            json.dump({k: v.to_dict() for k, v in self._jobs.items()}, f, indent=2)

    def add_job(self, prompt: str, schedule_type: str, schedule_value: str, session_id: Optional[str] = None) -> CronJob:
        job = CronJob(prompt=prompt, schedule_type=schedule_type, schedule_value=schedule_value, session_id=session_id)
        self._jobs[job.job_id] = job
        self._save()
        return job

    def remove_job(self, job_id: str) -> bool:
        if job_id in self._jobs:
            del self._jobs[job_id]
            self._save()
            return True
        return False

    def list_all(self) -> list[CronJob]:
        return sorted(self._jobs.values(), key=lambda x: x.next_run or "")

    def get_pending_jobs(self) -> list[CronJob]:
        now = datetime.now().isoformat()
        pending = []
        for job in self._jobs.values():
            if job.status == CronStatus.ENABLED and job.next_run and job.next_run <= now:
                pending.append(job)
        return pending

    def mark_run(self, job_id: str, result: Optional[str] = None) -> None:
        if job_id in self._jobs:
            job = self._jobs[job_id]
            job.last_run = datetime.now().isoformat()
            job.run_count += 1
            job.last_result = result
            
            if job.schedule_type == "once":
                job.status = CronStatus.DISABLED
                job.next_run = None
            else:
                job.calculate_next_run()
            
            self._save()
