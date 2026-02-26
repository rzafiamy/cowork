"""
⏰ Cron Service & Task Scheduler
Handles persistence and execution of scheduled agent tasks.
"""

import json
import uuid
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from .config import CONFIG_DIR

CRON_FILE = CONFIG_DIR / "cron_jobs.json"


def _now() -> datetime:
    """Return the current local time as a *naive* datetime (no tzinfo).
    This keeps everything consistent – we never mix aware & naive objects.
    Using the system clock guarantees the user's PC time is authoritative.
    """
    return datetime.now()


def _now_iso() -> str:
    return _now().isoformat()


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
        schedule_type: str = "once",   # once, daily, weekly
        schedule_value: str = "",       # ISO timestamp, "05:00", or natural time
        session_id: Optional[str] = None,
    ) -> None:
        self.job_id = job_id or str(uuid.uuid4())[:8]
        self.prompt = prompt
        self.schedule_type = schedule_type
        self.schedule_value = schedule_value
        self.session_id = session_id
        self.status = CronStatus.ENABLED
        self.created_at = _now_iso()
        self.last_run: Optional[str] = None
        self.next_run: Optional[str] = None
        self.run_count: int = 0
        self.last_result: Optional[str] = None

        if not self.next_run:
            self.calculate_next_run()

    # ── next-run calculation ──────────────────────────────────────────────────

    def calculate_next_run(self) -> None:
        """Robust next-run calculation.  All times are naive local datetimes."""
        now = _now()

        def _parse_time(val: str) -> Optional[datetime]:
            """Extract HH:MM or HH:MM:SS from an arbitrary string."""
            m = re.search(r'(\d{1,2}):(\d{2})(?::(\d{2}))?', val)
            if m:
                try:
                    h, mn, s = m.groups()
                    return now.replace(hour=int(h), minute=int(mn),
                                       second=int(s or 0), microsecond=0)
                except ValueError:
                    pass
            return None

        if self.schedule_type == "once":
            # 1. Try full ISO
            try:
                self.next_run = datetime.fromisoformat(self.schedule_value).isoformat()
                return
            except Exception:
                pass
            # 2. Try HH:MM
            t = _parse_time(self.schedule_value)
            if t:
                if t <= now:
                    t += timedelta(days=1)
                self.next_run = t.isoformat()
                return
            # 3. Fallback: now + 1 h
            self.next_run = (now + timedelta(hours=1)).isoformat()

        elif self.schedule_type == "daily":
            t = _parse_time(self.schedule_value)
            if t:
                if t <= now:
                    t += timedelta(days=1)
                self.next_run = t.isoformat()
            else:
                self.next_run = (now + timedelta(days=1)).replace(
                    hour=9, minute=0, second=0, microsecond=0
                ).isoformat()

        elif self.schedule_type == "weekly":
            t = _parse_time(self.schedule_value)
            if t:
                if t <= now:
                    t += timedelta(days=7)
                self.next_run = t.isoformat()
            else:
                self.next_run = (now + timedelta(weeks=1)).replace(
                    hour=9, minute=0, second=0, microsecond=0
                ).isoformat()

    def is_due(self) -> bool:
        """Return True if this job should run right now."""
        if self.status != CronStatus.ENABLED or not self.next_run:
            return False
        try:
            return datetime.fromisoformat(self.next_run) <= _now()
        except Exception:
            return False

    # ── serialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, data: dict) -> "CronJob":
        j = cls.__new__(cls)
        j.__dict__.update(data)
        return j


# ─── Manager ─────────────────────────────────────────────────────────────────

class CronManager:
    """Manages persistent cron jobs."""

    def __init__(self) -> None:
        self._jobs: dict[str, CronJob] = {}
        self._load()

    # ── persistence ───────────────────────────────────────────────────────────

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
        CRON_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CRON_FILE, "w") as f:
            json.dump({k: v.to_dict() for k, v in self._jobs.items()}, f, indent=2)

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def add_job(
        self,
        prompt: str,
        schedule_type: str,
        schedule_value: str,
        session_id: Optional[str] = None,
    ) -> CronJob:
        job = CronJob(
            prompt=prompt,
            schedule_type=schedule_type,
            schedule_value=schedule_value,
            session_id=session_id,
        )
        self._jobs[job.job_id] = job
        self._save()
        return job

    def remove_job(self, job_id: str) -> bool:
        # Support partial prefix match
        resolved = self._resolve_id(job_id)
        if resolved and resolved in self._jobs:
            del self._jobs[resolved]
            self._save()
            return True
        return False

    def get_job(self, job_id: str) -> Optional[CronJob]:
        resolved = self._resolve_id(job_id)
        return self._jobs.get(resolved) if resolved else None

    def list_all(self) -> list[CronJob]:
        return sorted(self._jobs.values(), key=lambda x: x.next_run or "")

    def get_pending_jobs(self) -> list[CronJob]:
        """Return jobs that are enabled and whose next_run has passed."""
        return [j for j in self._jobs.values() if j.is_due()]

    def search_jobs(self, query: str) -> list[CronJob]:
        """Case-insensitive search across prompt, job_id, and schedule values."""
        q = query.lower()
        return [
            j for j in self._jobs.values()
            if q in j.prompt.lower()
            or q in j.job_id.lower()
            or q in j.schedule_type.lower()
            or q in (j.schedule_value or "").lower()
            or q in (j.status or "").lower()
        ]

    def mark_run(self, job_id: str, result: Optional[str] = None) -> None:
        resolved = self._resolve_id(job_id)
        if resolved and resolved in self._jobs:
            job = self._jobs[resolved]
            job.last_run = _now_iso()
            job.run_count += 1
            job.last_result = result

            if job.schedule_type == "once":
                job.status = CronStatus.DISABLED
                job.next_run = None
            else:
                job.calculate_next_run()

            self._save()

    # ── helpers ───────────────────────────────────────────────────────────────

    def _resolve_id(self, job_id: str) -> Optional[str]:
        """Match exact or prefix job_id."""
        if job_id in self._jobs:
            return job_id
        matches = [k for k in self._jobs if k.startswith(job_id)]
        return matches[0] if len(matches) == 1 else None

    def all_job_ids(self) -> list[str]:
        return list(self._jobs.keys())
