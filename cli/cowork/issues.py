"""
🚨 Issue Manager: Knowledge Base for failed task/tool executions.
Stores (issue, reason, solution) triplets to provide real-time hints to the LLM.
"""

from __future__ import annotations

import sqlite3
import struct
import uuid
import math
import re
from datetime import datetime, timezone
from typing import Any, Optional, List, Dict

from .config import CONFIG_DIR
from .memoria import _LocalEmbedder, EMBED_DIM

# ─── Paths ────────────────────────────────────────────────────────────────────

ISSUES_DIR = CONFIG_DIR / "issues"
ISSUES_DIR.mkdir(exist_ok=True)
ISSUES_DB = ISSUES_DIR / "issues.db"


def _open_db() -> tuple[sqlite3.Connection, bool]:
    conn = sqlite3.connect(str(ISSUES_DB))
    conn.row_factory = sqlite3.Row

    vec_available = False
    try:
        import sqlite_vec  # type: ignore
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        vec_available = True
        conn.enable_load_extension(False)
    except Exception:
        pass

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS issue_triplets (
            id          TEXT PRIMARY KEY,
            user_id     TEXT NOT NULL,
            issue       TEXT NOT NULL,
            reason      TEXT NOT NULL,
            solution    TEXT NOT NULL,
            embedding   BLOB,
            created_at  TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_issue_user ON issue_triplets(user_id);
    """)

    if vec_available:
        try:
            conn.execute(f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS issue_vec
                USING vec0(
                    id TEXT PRIMARY KEY,
                    embedding float[{EMBED_DIM}]
                );
            """)
        except Exception:
            vec_available = False

    conn.commit()
    return conn, vec_available


class IssueManager:
    """
    Retrieves and records (issue, reason, solution) triplets.
    Provides hints to the agent when it hits API or tool errors.
    """
    def __init__(self, user_id: str, config: Any) -> None:
        self.user_id = user_id
        self.config = config
        self._db, self._vec_available = _open_db()
        self._embedder = _LocalEmbedder.get()
        self.top_k = 3
        self.min_similarity = 0.5

    def add_issue(self, issue: str, reason: str, solution: str) -> str:
        """Record a new issue-solution triplet."""
        triplet_id = str(uuid.uuid4())
        
        # We index the problem statement mostly, so we combine issue and reason.
        search_text = f"{issue} {reason}"
        
        embedding: Optional[bytes] = None
        if self._embedder:
            embedding = self._embedder.encode(search_text)
            
        self._db.execute(
            """INSERT INTO issue_triplets
               (id, user_id, issue, reason, solution, embedding, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                triplet_id,
                self.user_id,
                str(issue)[:500],
                str(reason)[:500],
                str(solution)[:1000],
                embedding,
                datetime.now(timezone.utc).isoformat(),
            ),
        )

        if embedding:
            try:
                self._db.execute(
                    "INSERT INTO issue_vec(id, embedding) VALUES (?, ?)",
                    (triplet_id, embedding),
                )
            except Exception:
                pass

        self._db.commit()
        return triplet_id
        
    def search_issues(self, query: str) -> List[Dict[str, Any]]:
        """Search for similar errors/issues and return their solutions."""
        query_vec = self._embedder.encode(query) if self._embedder else None
        
        if query_vec and self._vec_available:
            try:
                limit = self.top_k * 3
                res = self._db.execute(f"""
                    SELECT
                        t.id, t.issue, t.reason, t.solution, v.distance
                    FROM issue_triplets t
                    JOIN issue_vec v ON t.id = v.id
                    WHERE t.user_id = ?
                      AND v.embedding MATCH ?
                    ORDER BY v.distance
                    LIMIT ?
                """, (self.user_id, query_vec, limit)).fetchall()
                
                if res:
                    matches = []
                    for row in res:
                        similarity = 1.0 / (1.0 + row["distance"])
                        if similarity >= self.min_similarity:
                            matches.append({
                                "id": row["id"],
                                "issue": row["issue"],
                                "reason": row["reason"],
                                "solution": row["solution"],
                                "similarity": similarity
                            })
                    matches.sort(key=lambda t: t["similarity"], reverse=True)
                    return matches[:self.top_k]
            except Exception:
                pass # fallback to manual
                
        # Manual scan fallback
        rows = self._db.execute(
            "SELECT id, issue, reason, solution, embedding "
            "FROM issue_triplets WHERE user_id = ?",
            (self.user_id,)
        ).fetchall()
        
        if not rows:
            return []
            
        matches = []
        for row in rows:
            triplet_text = f"{row['issue']} {row['reason']}"
            if query_vec and row["embedding"]:
                similarity = _LocalEmbedder.cosine_from_bytes(query_vec, row["embedding"])
            else:
                # keyword overlap
                q_words = set(re.findall(r"\w+", query.lower()))
                t_words = set(re.findall(r"\w+", triplet_text.lower()))
                overlap = len(q_words & t_words)
                similarity = min(1.0, overlap / max(len(q_words), 1))
                
            if similarity >= self.min_similarity:
                matches.append({
                    "id": row["id"],
                    "issue": row["issue"],
                    "reason": row["reason"],
                    "solution": row["solution"],
                    "similarity": similarity
                })
        
        matches.sort(key=lambda t: t["similarity"], reverse=True)
        return matches[:self.top_k]

    def list_all(self) -> List[Dict[str, Any]]:
        """List all issue triplets for the user."""
        rows = self._db.execute(
            "SELECT id, issue, reason, solution, created_at "
            "FROM issue_triplets WHERE user_id = ? ORDER BY created_at DESC",
            (self.user_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_triplet_count(self) -> int:
        res = self._db.execute("SELECT COUNT(*) as c FROM issue_triplets WHERE user_id=?", (self.user_id,)).fetchone()
        return res["c"] if res else 0

    def delete_issue(self, triplet_id: str) -> bool:
        res = self._db.execute("DELETE FROM issue_triplets WHERE id=? AND user_id=?", (triplet_id, self.user_id))
        if res.rowcount > 0:
            if self._vec_available:
                try:
                    self._db.execute("DELETE FROM issue_vec WHERE id=?", (triplet_id,))
                except Exception:
                    pass
            self._db.commit()
            return True
        return False

    def clear_all(self) -> None:
        self._db.execute("DELETE FROM issue_triplets WHERE user_id=?", (self.user_id,))
        if self._vec_available:
            try:
                # Can't easily filter virtual table by user_id without join, so we clear what matches
                self._db.execute("DELETE FROM issue_vec WHERE id IN (SELECT id FROM issue_triplets WHERE user_id=?)", (self.user_id,))
            except Exception:
                pass
        self._db.commit()

    def migrate_user_data(self, from_user_id: str) -> int:
        """Migrate all issue triplets from one user_id to another."""
        cursor = self._db.execute(
            "UPDATE issue_triplets SET user_id = ? WHERE user_id = ?",
            (self.user_id, from_user_id)
        )
        count = cursor.rowcount
        self._db.commit()
        return count
