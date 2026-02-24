"""
🧠 Memoria: Hybrid Long-Term Memory System
Implements the Knowledge Graph + Session Summary memory framework.

Storage:  Local SQLite (no external DB)
Vectors:  sqlite-vec extension (local KNN search)
Embedder: sentence-transformers all-MiniLM-L6-v2 (22 MB, CPU-friendly)
Fallback: keyword overlap when deps are unavailable
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
import struct
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .config import CONFIG_DIR
from .prompts import (
    CONTEXT_FUSION_TEMPLATE,
    MEMORY_CONSOLIDATION_PROMPT,
    SESSION_SUMMARY_PROMPT,
    TRIPLET_EXTRACTION_PROMPT,
)
from .theme import OP_DEFAULTS

# ─── Paths ────────────────────────────────────────────────────────────────────

MEMORIA_DIR = CONFIG_DIR / "memoria"
MEMORIA_DIR.mkdir(exist_ok=True)
MEMORIA_DB = MEMORIA_DIR / "memoria.db"

# ─── Embedding dimension for all-MiniLM-L6-v2 ────────────────────────────────
EMBED_DIM = 384
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from",
    "how", "i", "in", "is", "it", "of", "on", "or", "that", "the", "this",
    "to", "we", "what", "when", "where", "who", "why", "with", "you", "your",
    # French
    "le", "la", "les", "un", "une", "des", "du", "de", "au", "aux",
    "mon", "ton", "son", "ma", "ta", "sa", "mes", "tes", "ses",
    "je", "tu", "il", "elle", "nous", "vous", "ils", "elles",
    "est", "sont", "et", "ou", "sur", "sous", "dans", "avec",
}

# Strong indicators that a message is a temporary task directive, not durable profile memory.
TRANSIENT_MEMORY_PATTERNS = [
    r"\bfor this (task|request|message|email|run|time)\b",
    r"\bright now\b",
    r"\btoday\b",
    r"\btomorrow\b",
    r"\bthis time\b",
    r"\bjust this once\b",
    r"\bcan you\b",
    r"\bplease\b",
    r"\bsend (it|this|that|the)\b",
    r"\bemail (it|this|that|the)\b",
]

# Durable profile/preference patterns worth storing in long-term memory.
DURABLE_MEMORY_PATTERNS = [
    # English
    r"\bi am\b", r"\bi'm\b", r"\bmy name is\b", r"\bcall me\b", r"\bi live in\b", r"\bi work as\b",
    r"\bmy email( address)? is\b", r"\bmy phone( number)? is\b", r"\bmy birthday is\b",
    r"\bi prefer\b", r"\bi like\b", r"\bi dislike\b", r"\bi hate\b", r"\balways\b", r"\bnever\b",
    r"\bmy goal is\b", r"\bi'm working on\b", r"\bwe are building\b", r"\bwhenever i ask\b",
    r"\bremember\b", r"\bsave this\b", r"\bfor future\b", r"\bimportant\b", r"\bnote this\b",
    # French
    r"\bje suis\b", r"\bmon nom est\b", r"\bj'habite\b", r"\bje travaille\b",
    r"\bmon email est\b", r"\bmon e-mail est\b", r"\bmon numero est\b", r"\bmon numéro est\b",
    r"\bje prefere\b", r"\bje préfère\b", r"\bj'aime\b", r"\bje n'aime pas\b",
    r"\bmon objectif\b", r"\bje travaille sur\b", r"\bnous construisons\b",
    r"\brappelle\b", r"\bsauvegarde\b", r"\benregistre\b", r"\bpour plus tard\b",
]

TRIVIAL_CHAT_WORDS = {
    "ok", "okay", "thanks", "thank", "merci", "bonjour", "salut", "hello", "hi", "hey"
}

EMAIL_RE = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.IGNORECASE)
TASKISH_SUBJECT_TERMS = {
    "slide", "slides", "story", "document", "docx", "pptx", "chart", "plotchart", "file",
}
TRANSIENT_PREDICATE_TERMS = {
    "wants", "want", "requests", "requested", "asks", "asked", "should", "contains",
    "topic", "create", "send", "sent", "emailed", "delay", "save", "format", "action",
}
DURABLE_PREDICATE_TERMS = {
    "is", "am", "are", "has", "have", "prefers", "prefer", "likes", "like", "dislikes",
    "communicates", "uses", "works", "lives", "speaks", "typically", "usually", "always", "never",
}
TRANSIENT_OBJECT_TERMS = {
    "today", "tomorrow", "tonight", "right now", "this task", "this request", "this image",
    "slide", "slides", "docx", "pptx", "plotchart", "19:00",
}

# ─── Prompts are centralized in prompts.py ───────────────────────────────────
# Import: TRIPLET_EXTRACTION_PROMPT, SESSION_SUMMARY_PROMPT, CONTEXT_FUSION_TEMPLATE


# ─── Local Embedder ───────────────────────────────────────────────────────────

class _LocalEmbedder:
    """
    Lazy-loaded sentence-transformers embedder.
    Uses all-MiniLM-L6-v2: 22 MB, 384-dim, CPU-friendly, ~5ms/sentence.
    Falls back to None if sentence-transformers is not installed.
    """

    _instance: Optional["_LocalEmbedder"] = None
    _model: Any = None
    _available: Optional[bool] = None

    @classmethod
    def get(cls) -> Optional["_LocalEmbedder"]:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance if cls._available else None

    def __init__(self) -> None:
        if _LocalEmbedder._available is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
            _LocalEmbedder._model = SentenceTransformer(
                "all-MiniLM-L6-v2",
                device="cpu",
            )
            _LocalEmbedder._available = True
        except ImportError:
            _LocalEmbedder._available = False
        except Exception:
            _LocalEmbedder._available = False

    def encode(self, text: str) -> Optional[bytes]:
        """Return float32 bytes (384 floats) or None on failure."""
        if not _LocalEmbedder._available or _LocalEmbedder._model is None:
            return None
        try:
            vec = _LocalEmbedder._model.encode(text, normalize_embeddings=True)
            return struct.pack(f"{EMBED_DIM}f", *vec.tolist())
        except Exception:
            return None

    @staticmethod
    def cosine_from_bytes(a: bytes, b: bytes) -> float:
        """Compute cosine similarity between two float32 byte blobs."""
        try:
            va = struct.unpack(f"{EMBED_DIM}f", a)
            vb = struct.unpack(f"{EMBED_DIM}f", b)
            dot = sum(x * y for x, y in zip(va, vb))
            na = math.sqrt(sum(x * x for x in va))
            nb = math.sqrt(sum(x * x for x in vb))
            if na == 0 or nb == 0:
                return 0.0
            return dot / (na * nb)
        except Exception:
            return 0.0


# ─── SQLite Store ─────────────────────────────────────────────────────────────

def _open_db() -> tuple[sqlite3.Connection, bool]:
    """
    Open (or create) the Memoria SQLite database.
    Tries to load sqlite-vec for KNN search; falls back to plain SQLite.
    """
    conn = sqlite3.connect(str(MEMORIA_DB))
    conn.row_factory = sqlite3.Row

    vec_available = False

    # Try loading sqlite-vec extension
    try:
        import sqlite_vec  # type: ignore
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        vec_available = True
        conn.enable_load_extension(False)
    except Exception:
        pass  # Will use manual cosine fallback

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS kg_triplets (
            id          TEXT PRIMARY KEY,
            session_id  TEXT,
            user_id     TEXT NOT NULL,
            subject     TEXT NOT NULL,
            predicate   TEXT NOT NULL,
            object      TEXT NOT NULL,
            embedding   BLOB,
            created_at  TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_kg_user ON kg_triplets(user_id);

        CREATE TABLE IF NOT EXISTS session_summaries (
            session_id  TEXT PRIMARY KEY,
            summary     TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        );
    """)

    # 🛠️ Migration: Add session_id column and index to existing databases
    try:
        cursor = conn.execute("PRAGMA table_info(kg_triplets)")
        columns = [row["name"] for row in cursor.fetchall()]
        if "session_id" not in columns:
            conn.execute("ALTER TABLE kg_triplets ADD COLUMN session_id TEXT")
            conn.commit()
        
        # Ensure index is created after column exists
        conn.execute("CREATE INDEX IF NOT EXISTS idx_kg_session ON kg_triplets(session_id)")
        conn.commit()
    except Exception:
        pass

    if vec_available:
        try:
            conn.execute(f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS kg_vec
                USING vec0(
                    id TEXT PRIMARY KEY,
                    embedding float[{EMBED_DIM}]
                );
            """)
        except Exception:
            vec_available = False

    conn.commit()
    return conn, vec_available


# ─── Memoria ──────────────────────────────────────────────────────────────────

class Memoria:
    """
    Hybrid memory system combining:
    - Knowledge Graph (triplets) in local SQLite
    - Local vector search via sqlite-vec (or manual cosine fallback)
    - Session summaries for rolling conversation context
    - EWA temporal decay for relevance weighting

    Zero external dependencies required at runtime:
      • With sentence-transformers + sqlite-vec → full semantic search
      • Without → keyword overlap fallback (same as before)
    """

    def __init__(
        self,
        user_id: str,
        session_id: str,
        api_client: Any,
        config: Any,
    ) -> None:
        self.user_id = user_id
        self.session_id = session_id
        self.api_client = api_client
        self.config = config
        self.decay_rate = config.get("decay_rate", OP_DEFAULTS["decay_rate"])
        self.top_k = config.get("top_k_memories", OP_DEFAULTS["top_k_memories"])
        self.min_memory_similarity = config.get("memory_min_similarity", OP_DEFAULTS["memory_min_similarity"])
        self.min_memory_weight = config.get("memory_min_weight", OP_DEFAULTS["memory_min_weight"])
        self.topic_overlap_min = config.get("memory_topic_overlap_min", OP_DEFAULTS["memory_topic_overlap_min"])
        self.high_similarity_bypass = config.get(
            "memory_high_similarity_bypass",
            OP_DEFAULTS["memory_high_similarity_bypass"],
        )
        self.kg_limit = config.get("memory_kg_limit_triplets", OP_DEFAULTS["memory_kg_limit_triplets"])

        self._db, self._vec_available = _open_db()
        self._embedder = _LocalEmbedder.get()
        self._summary: str = self._load_summary()

    # ── Storage helpers ───────────────────────────────────────────────────────

    def _load_summary(self) -> str:
        row = self._db.execute(
            "SELECT summary FROM session_summaries WHERE session_id = ?",
            (self.session_id,),
        ).fetchone()
        return row["summary"] if row else ""

    def _save_summary(self) -> None:
        self._db.execute(
            """INSERT INTO session_summaries(session_id, summary, updated_at)
               VALUES(?, ?, ?)
               ON CONFLICT(session_id) DO UPDATE SET
                 summary = excluded.summary,
                 updated_at = excluded.updated_at""",
            (self.session_id, self._summary, datetime.utcnow().isoformat()),
        )
        self._db.commit()

    # ── Read Path ─────────────────────────────────────────────────────────────

    def get_fused_context(self, query: str) -> str:
        """
        Retrieve relevant context for the current query.
        Combines session summary + weighted persona triplets.
        """
        summary = self._summary
        triplets = self._get_weighted_triplets(query)
        # For short/low-signal conversational turns, semantic relevance may be weak.
        # Add a small recency fallback so durable profile facts remain usable.
        if not triplets:
            triplets = self._get_recent_triplets(limit=max(2, self.top_k // 2))

        if not summary and not triplets:
            return ""

        triplet_lines = []
        for t in triplets[: self.top_k]:
            triplet_lines.append(
                f"  • {t['subject']} {t['predicate']} {t['object']}"
            )
        triplets_str = "\n".join(triplet_lines) if triplet_lines else "  (No relevant persona facts available)"
        summary_str = summary if summary else "(No session summary yet)"

        return CONTEXT_FUSION_TEMPLATE.format(
            summary=summary_str,
            triplets=triplets_str,
        )

    def _get_recent_triplets(self, limit: int = 3) -> list[dict]:
        rows = self._db.execute(
            "SELECT id, subject, predicate, object, created_at "
            "FROM kg_triplets WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (self.user_id, max(1, int(limit))),
        ).fetchall()
        out: list[dict] = []
        for row in rows:
            out.append(
                {
                    "id": row["id"],
                    "subject": row["subject"],
                    "predicate": row["predicate"],
                    "object": row["object"],
                    "weight": 0.5,
                    "similarity": 0.0,
                }
            )
        return out

    def _topic_terms(self, text: str) -> set[str]:
        terms = set(re.findall(r"[a-zA-Z0-9_]+", text.lower()))
        return {t for t in terms if len(t) >= 3 and t not in STOPWORDS}

    def _passes_relevance_gate(self, query: str, triplet_text: str, similarity: float, weight: float) -> bool:
        if similarity < self.min_memory_similarity and weight < self.min_memory_weight:
            return False

        q_terms = self._topic_terms(query)
        if not q_terms:
            return similarity >= self.min_memory_similarity

        t_terms = self._topic_terms(triplet_text)
        overlap = len(q_terms & t_terms)
        if overlap >= self.topic_overlap_min:
            return True
        return similarity >= self.high_similarity_bypass

    def _get_weighted_triplets(self, query: str) -> list[dict]:
        """
        Semantic search with EWA temporal decay.

        Strategy (in priority order):
          1. sqlite-vec KNN  — if extension loaded + embeddings stored
          2. Manual cosine   — if embeddings stored but no sqlite-vec
          3. Keyword overlap — always available as final fallback
        """
        now = datetime.utcnow()
        query_vec = self._embedder.encode(query) if self._embedder else None

        # 1. Attempt sqlite-vec search first (efficient for scale)
        if query_vec and self._vec_available:
            try:
                # Get more candidates than top_k because decay might re-rank later additions
                limit = self.top_k * 10
                res = self._db.execute(f"""
                    SELECT
                        t.id, t.subject, t.predicate, t.object, t.embedding, t.created_at,
                        v.distance
                    FROM kg_triplets t
                    JOIN kg_vec v ON t.id = v.id
                    WHERE t.user_id = ?
                      AND v.embedding MATCH ?
                    ORDER BY v.distance
                    LIMIT ?
                """, (self.user_id, query_vec, limit)).fetchall()

                if res:
                    weighted = []
                    for row in res:
                        # Convert distance to similarity (approximate)
                        # distance is square Euclidean for float vec in sqlite-vec by default
                        # or cosine distance if specified.
                        similarity = 1.0 / (1.0 + row["distance"])
                        
                        try:
                            created_at = datetime.fromisoformat(row["created_at"])
                        except Exception:
                            created_at = now
                        delta_min = (now - created_at).total_seconds() / 60.0
                        weight = similarity * math.exp(-self.decay_rate * delta_min)

                        triplet_text = f"{row['subject']} {row['predicate']} {row['object']}"
                        if self._passes_relevance_gate(query, triplet_text, similarity, weight):
                            weighted.append({
                                "id": row["id"],
                                "subject": row["subject"],
                                "predicate": row["predicate"],
                                "object": row["object"],
                                "weight": weight,
                                "similarity": similarity,
                            })
                    weighted.sort(key=lambda t: t["weight"], reverse=True)
                    return weighted
            except Exception:
                pass # Fallback to manual

        # 2. Manual Scan (if vector search failed or unavailable)
        rows = self._db.execute(
            "SELECT id, subject, predicate, object, embedding, created_at "
            "FROM kg_triplets WHERE user_id = ?",
            (self.user_id,),
        ).fetchall()

        if not rows:
            return []

        weighted: list[dict] = []
        for row in rows:
            triplet_text = f"{row['subject']} {row['predicate']} {row['object']}"

            # ── Similarity score ──────────────────────────────────────────────
            if query_vec and row["embedding"]:
                similarity = _LocalEmbedder.cosine_from_bytes(query_vec, row["embedding"])
            else:
                # Keyword fallback
                q_words = set(re.findall(r"\w+", query.lower()))
                t_words = set(re.findall(r"\w+", triplet_text.lower()))
                overlap = len(q_words & t_words)
                similarity = min(1.0, overlap / max(len(q_words), 1))

            # ── EWA temporal decay ────────────────────────────────────────────
            try:
                created_at = datetime.fromisoformat(row["created_at"])
            except Exception:
                created_at = now
            delta_min = (now - created_at).total_seconds() / 60.0
            weight = similarity * math.exp(-self.decay_rate * delta_min)

            if self._passes_relevance_gate(query, triplet_text, similarity, weight):
                weighted.append(
                    {
                        "id": row["id"],
                        "subject": row["subject"],
                        "predicate": row["predicate"],
                        "object": row["object"],
                        "weight": weight,
                        "similarity": similarity,
                    }
                )

        weighted.sort(key=lambda t: t["weight"], reverse=True)
        return weighted

    # ── Write Path ────────────────────────────────────────────────────────────

    def is_durable_message(self, user_message: str) -> bool:
        text = user_message.strip()
        if not text:
            return False
        if text.startswith("/"):
            return False

        lowered = text.lower()
        words = re.findall(r"[a-zA-Z0-9_]+", lowered)
        if words and all(w in TRIVIAL_CHAT_WORDS for w in words):
            return False

        has_durable_pattern = any(re.search(p, lowered) for p in DURABLE_MEMORY_PATTERNS)
        has_transient_pattern = any(re.search(p, lowered) for p in TRANSIENT_MEMORY_PATTERNS)

        # Structured contact details are durable only when the user states ownership.
        has_personal_email = bool(
            EMAIL_RE.search(text)
            and ("my email" in lowered or "email address is" in lowered or "mon email" in lowered or "mon e-mail" in lowered)
        )

        if has_durable_pattern or has_personal_email:
            return True

        # Reject action-like transient directives by default.
        if has_transient_pattern:
            return False

        # Conservative fallback: keep only self-profile statements, not generic long instructions.
        has_self_reference = any(token in {"i", "im", "i'm", "my", "me", "je", "mon", "ma", "mes"} for token in words)
        has_state_verb = any(
            token in {
                "am", "live", "work", "prefer", "like", "dislike", "hate", "use", "have",
                "suis", "habite", "travaille", "prefere", "préfère", "aime",
            }
            for token in words
        )
        return len(words) >= 5 and has_self_reference and has_state_verb

    def _is_durable_memory_candidate(self, user_message: str) -> bool:
        # Backward-compatible internal alias.
        return self.is_durable_message(user_message)

    def _is_triplet_durable(self, subject: str, predicate: str, object_: str, source_message: str) -> bool:
        """
        Filter out extracted triplets that look like temporary task directives.
        Keep only stable profile/workflow facts for long-term memory.
        """
        subj = (subject or "").strip().lower()
        pred = (predicate or "").strip().lower()
        obj = (object_ or "").strip().lower()
        triple_text = f"{subj} {pred} {obj}".strip()
        source = (source_message or "").strip().lower()
        pred_words = set(re.findall(r"[a-z0-9_]+", pred))
        subj_words = set(re.findall(r"[a-z0-9_]+", subj))
        obj_words = set(re.findall(r"[a-z0-9_:@.\-]+", obj))

        if not subj or not pred or not obj:
            return False

        if any(re.search(p, triple_text) for p in TRANSIENT_MEMORY_PATTERNS):
            return False
        if any(term in subj_words for term in TASKISH_SUBJECT_TERMS):
            return False
        if any(term in pred_words for term in TRANSIENT_PREDICATE_TERMS):
            # Exception: "prefers ... format" can still be durable style preference.
            if not (("prefer" in pred_words or "prefers" in pred_words) and "format" in pred_words):
                return False
        if any(term in obj for term in TRANSIENT_OBJECT_TERMS):
            return False
        if any(re.search(p, source) for p in TRANSIENT_MEMORY_PATTERNS):
            if not any(re.search(p, source) for p in DURABLE_MEMORY_PATTERNS):
                return False

        # Explicitly keep stable contact/profile facts.
        if EMAIL_RE.search(obj) and any(w in pred_words for w in {"email", "address", "has", "is"}):
            return True
        if "user" in subj_words and any(w in pred_words for w in {"communicates", "speaks", "uses", "prefers", "typically", "usually"}):
            return True
        if any(w in pred_words for w in DURABLE_PREDICATE_TERMS):
            return True
        return False

    def prune_transient_triplets(self) -> int:
        """
        Remove already-stored non-durable triplets from the user's KG.
        Returns number of removed triplets.
        """
        rows = self._db.execute(
            "SELECT id, subject, predicate, object FROM kg_triplets WHERE user_id = ?",
            (self.user_id,),
        ).fetchall()
        if not rows:
            return 0

        doomed_ids: list[str] = []
        for row in rows:
            if not self._is_triplet_durable(
                str(row["subject"]),
                str(row["predicate"]),
                str(row["object"]),
                "",
            ):
                doomed_ids.append(str(row["id"]))

        for tid in doomed_ids:
            self._db.execute(
                "DELETE FROM kg_triplets WHERE id = ? AND user_id = ?",
                (tid, self.user_id),
            )
            try:
                self._db.execute("DELETE FROM kg_vec WHERE id = ?", (tid,))
            except Exception:
                pass
        self._db.commit()
        return len(doomed_ids)

    async def update(self, user_message: str, assistant_response: str) -> None:
        """
        Non-blocking memory update (called in background).
        Extracts triplets and updates session summary in parallel.
        """
        if not user_message or not self._is_durable_memory_candidate(user_message):
            return
        try:
            import asyncio

            await asyncio.gather(
                self._process_triplets(user_message),
                self._update_session_summary(user_message, assistant_response),
            )
        except Exception:
            pass  # Memory failures are non-fatal

        # Automatic consolidation if limit reached
        try:
            current_count = self.get_triplet_count()
            if current_count > self.kg_limit:
                await self.consolidate()
        except Exception:
            pass

    async def consolidate(self) -> tuple[bool, str]:
        """
        Consolidate Knowledge Graph to remove redundancy and stay within limits.
        Uses LLM to merge triplets.
        """
        all_triplets = self.get_all_triplets()
        if not all_triplets:
            return False, "no_triplets"

        formatted = "\n".join(
            [f"{t['subject']} | {t['predicate']} | {t['object']}" for t in all_triplets]
        )

        prompt = MEMORY_CONSOLIDATION_PROMPT.format(triplets=formatted)
        
        try:
            result = await self.api_client.chat(
                messages=[{"role": "user", "content": prompt}],
                model=self.config.get("model_text"),
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            content = result.get("content", "{}")
            parsed = json.loads(content)
            new_triplets = parsed.get("triplets", []) if isinstance(parsed, dict) else []
            if not isinstance(new_triplets, list) or not new_triplets:
                return False, "empty_model_output"

            cleaned: list[tuple[str, str, str]] = []
            for t in new_triplets:
                if not (isinstance(t, dict) and all(k in t for k in ("subject", "predicate", "object"))):
                    continue
                subj = str(t["subject"])[:200].strip()
                pred = str(t["predicate"])[:200].strip()
                obj = str(t["object"])[:200].strip()
                if not (subj and pred and obj):
                    continue
                if not self._is_triplet_durable(subj, pred, obj, ""):
                    continue
                cleaned.append((subj, pred, obj))

            if not cleaned:
                return False, "no_valid_triplets"

            old_set = {
                (str(t["subject"]).strip(), str(t["predicate"]).strip(), str(t["object"]).strip())
                for t in all_triplets
            }
            new_set = set(cleaned)
            if old_set == new_set:
                return False, "no_changes"

            # 1. Clear existing
            self._db.execute("DELETE FROM kg_triplets WHERE user_id = ?", (self.user_id,))
            try:
                self._db.execute("DELETE FROM kg_vec WHERE id NOT IN (SELECT id FROM kg_triplets)")
            except Exception:
                pass

            # 2. Insert consolidated ones
            for subj, pred, obj in cleaned:
                triplet_id = str(uuid.uuid4())
                triplet_text = f"{subj} {pred} {obj}"

                embedding: Optional[bytes] = None
                if self._embedder:
                    embedding = self._embedder.encode(triplet_text)

                self._db.execute(
                    """INSERT INTO kg_triplets
                       (id, session_id, user_id, subject, predicate, object, embedding, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        triplet_id,
                        self.session_id,
                        self.user_id,
                        subj,
                        pred,
                        obj,
                        embedding,
                        datetime.utcnow().isoformat(),
                    ),
                )
                if embedding:
                    try:
                        self._db.execute(
                            "INSERT INTO kg_vec(id, embedding) VALUES (?, ?)",
                            (triplet_id, embedding),
                        )
                    except Exception:
                        pass

            self._db.commit()
            return True, "consolidated"
        except Exception:
            return False, "exception"

    async def _process_triplets(self, user_message: str) -> None:
        """Extract knowledge triplets from user message and save to KG."""
        try:
            prompt = TRIPLET_EXTRACTION_PROMPT.format(message=user_message)
            result = await self.api_client.chat(
                messages=[{"role": "user", "content": prompt}],
                model=self.config.get("model_text"),
                temperature=0.1,
                response_format={"type": "json_object"},
                max_tokens=500,
            )
            content = result.get("content", "{}")

            # Robust JSON parsing
            try:
                parsed = json.loads(content)
                if isinstance(parsed, dict):
                    triplets = parsed.get("triplets", [])
                elif isinstance(parsed, list):
                    triplets = parsed
                else:
                    triplets = []
            except json.JSONDecodeError:
                # Fallback: try to find anything that looks like an array
                match = re.search(r"\[.*\]", content, re.DOTALL)
                try:
                    triplets = json.loads(match.group()) if match else []
                except Exception:
                    triplets = []

            if not triplets:
                return

            # Insert new triplets with local embeddings
            for t in triplets:
                if isinstance(t, dict) and all(k in t for k in ("subject", "predicate", "object")):
                    subj = str(t["subject"])[:200]
                    pred = str(t["predicate"])[:200]
                    obj = str(t["object"])[:200]
                    if not self._is_triplet_durable(subj, pred, obj, user_message):
                        continue

                    triplet_id = str(uuid.uuid4())
                    triplet_text = f"{subj} {pred} {obj}"

                    # Generate local embedding (None if deps unavailable)
                    embedding: Optional[bytes] = None
                    if self._embedder:
                        embedding = self._embedder.encode(triplet_text)

                    self._db.execute(
                        """INSERT OR IGNORE INTO kg_triplets
                           (id, session_id, user_id, subject, predicate, object, embedding, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            triplet_id,
                            self.session_id,
                            self.user_id,
                            subj,
                            pred,
                            obj,
                            embedding,
                            datetime.utcnow().isoformat(),
                        ),
                    )

                    # Also insert into sqlite-vec virtual table if available
                    if embedding:
                        try:
                            self._db.execute(
                                "INSERT OR IGNORE INTO kg_vec(id, embedding) VALUES (?, ?)",
                                (triplet_id, embedding),
                            )
                        except Exception:
                            pass  # sqlite-vec not loaded or failed

            self._db.commit()
        except Exception as e:
            # We keep it non-fatal but we could log it to a file if we had a logger
            pass

    async def _update_session_summary(
        self, user_message: str, assistant_response: str
    ) -> None:
        """Update the rolling session summary via LLM."""
        if not assistant_response:
            return
        try:
            prompt = SESSION_SUMMARY_PROMPT.format(
                current_summary=self._summary or "(none yet)",
                user_message=user_message[:500],
                assistant_response=assistant_response[:1000],
            )
            result = await self.api_client.chat(
                messages=[{"role": "user", "content": prompt}],
                model=self.config.get("model_compress"),
                temperature=OP_DEFAULTS["temperature_compress"],
                max_tokens=300,
            )
            new_summary = result.get("content", "").strip()
            if new_summary:
                self._summary = new_summary
                self._save_summary()
        except Exception:
            pass

    def add_triplet(self, subject: str, predicate: str, object_: str) -> str:
        """Manually add a knowledge triplet to the graph."""
        triplet_id = str(uuid.uuid4())
        triplet_text = f"{subject} {predicate} {object_}"

        embedding: Optional[bytes] = None
        if self._embedder:
            embedding = self._embedder.encode(triplet_text)

        self._db.execute(
            """INSERT INTO kg_triplets
               (id, session_id, user_id, subject, predicate, object, embedding, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                triplet_id,
                self.session_id,
                self.user_id,
                str(subject)[:200],
                str(predicate)[:200],
                str(object_)[:200],
                embedding,
                datetime.utcnow().isoformat(),
            ),
        )

        if embedding:
            try:
                self._db.execute(
                    "INSERT INTO kg_vec(id, embedding) VALUES (?, ?)",
                    (triplet_id, embedding),
                )
            except Exception:
                pass

        self._db.commit()
        return triplet_id

    def search_triplets(self, query: str) -> list[dict]:
        """Perform a semantic search for relevant triplets."""
        return self._get_weighted_triplets(query)

    # ── Utility ───────────────────────────────────────────────────────────────

    def get_triplet_count(self) -> int:
        row = self._db.execute(
            "SELECT COUNT(*) AS n FROM kg_triplets WHERE user_id = ?",
            (self.user_id,),
        ).fetchone()
        return row["n"] if row else 0

    def get_all_triplets(self) -> list[dict]:
        """Return all triplets for the user."""
        rows = self._db.execute(
            "SELECT id, subject, predicate, object, created_at FROM kg_triplets WHERE user_id = ? ORDER BY created_at DESC",
            (self.user_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def delete_triplet(self, triplet_id: str) -> bool:
        """Delete a specific triplet."""
        cursor = self._db.execute(
            "DELETE FROM kg_triplets WHERE id = ? AND user_id = ?",
            (triplet_id, self.user_id),
        )
        try:
            self._db.execute("DELETE FROM kg_vec WHERE id = ?", (triplet_id,))
        except Exception:
            pass
        self._db.commit()
        return cursor.rowcount > 0

    def get_summary(self) -> str:
        return self._summary

    def is_semantic_search_available(self) -> bool:
        """True if BOTH local embeddings AND vector DB extension are active."""
        return self._embedder is not None and self._vec_available

    def clear_session(self) -> None:
        """Clear session summary (keep KG)."""
        self._summary = ""
        self._db.execute(
            "DELETE FROM session_summaries WHERE session_id = ?",
            (self.session_id,),
        )
        self._db.commit()

    def clear_all(self) -> None:
        """Clear all memory for this user."""
        self._db.execute(
            "DELETE FROM kg_triplets WHERE user_id = ?", (self.user_id,)
        )
        self._db.execute(
            "DELETE FROM session_summaries WHERE session_id = ?",
            (self.session_id,),
        )
        try:
            self._db.execute(
                "DELETE FROM kg_vec WHERE id NOT IN (SELECT id FROM kg_triplets)"
            )
        except Exception:
            pass
        self._db.commit()
        self._summary = ""
