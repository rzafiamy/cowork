import sqlite3
import os
import time
from pathlib import Path
from typing import Any, Optional

from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import HTML

try:
    from rapidfuzz import process, fuzz
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False

# Fallback basic matcher if rapidfuzz isn't installed
def simple_fuzz_match(query, choices, limit=3):
    matches = []
    q_lower = query.lower()
    for choice in choices:
        c_lower = choice.lower()
        if q_lower in c_lower:
            # Score 100 for starts_with, 50 for contains
            score = 100 if c_lower.startswith(q_lower) else 50
            matches.append((choice, score))
    matches.sort(key=lambda x: x[1], reverse=True)
    return matches[:limit]

# Reuse the existing LocalEmbedder if possible
try:
    from .memoria import _LocalEmbedder
except ImportError:
    _LocalEmbedder = None


class HistoryDB:
    """Offline local database for shell history with FTS5 and context tracking."""
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        with self.conn:
            self.conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS history_fts USING fts5(
                    interaction_text,
                    context_cwd,
                    timestamp UNINDEXED
                )
            """)
            
            # Create a regular table to store embeddings (for vector search fallback)
            # If we were using sqlite-vec, we'd use 'CREATE VIRTUAL TABLE ... USING vec0'
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS history_meta (
                    id INTEGER PRIMARY KEY,
                    interaction_text TEXT UNIQUE,
                    context_cwd TEXT,
                    timestamp REAL,
                    usage_count INTEGER DEFAULT 1
                )
            """)

    def add_interaction(self, text: str, cwd: str):
        if not text.strip():
            return
        now = time.time()
        with self.conn:
            # Update meta
            cursor = self.conn.execute(
                "SELECT id, usage_count FROM history_meta WHERE interaction_text = ?", 
                (text,)
            )
            row = cursor.fetchone()
            if row:
                self.conn.execute(
                    "UPDATE history_meta SET usage_count = ?, timestamp = ?, context_cwd = ? WHERE id = ?",
                    (row["usage_count"] + 1, now, cwd, row["id"])
                )
            else:
                self.conn.execute(
                    "INSERT INTO history_meta (interaction_text, context_cwd, timestamp) VALUES (?, ?, ?)",
                    (text, cwd, now)
                )
                self.conn.execute(
                    "INSERT INTO history_fts (interaction_text, context_cwd, timestamp) VALUES (?, ?, ?)",
                    (text, cwd, now)
                )

    def get_recent_history(self, limit=100) -> list[str]:
        cursor = self.conn.execute(
            "SELECT interaction_text FROM history_meta ORDER BY timestamp DESC LIMIT ?", 
            (limit,)
        )
        return [row["interaction_text"] for row in cursor.fetchall()]

    def search_fts(self, query: str, limit=10) -> list[str]:
        # Very basic FTS5 prefix search
        # E.g. query "dock" -> search '"dock*"'
        if not query.strip():
            return []
        
        # Clean query for fts
        clean_query = query.replace('"', '').replace("'", "")
        fts_query = f'"{clean_query}*"'
        try:
            cursor = self.conn.execute(
                "SELECT interaction_text FROM history_fts WHERE history_fts MATCH ? ORDER BY rank LIMIT ?", 
                (fts_query, limit)
            )
            return [row["interaction_text"] for row in cursor.fetchall()]
        except sqlite3.OperationalError:
            return []


class SuperCompleter(Completer):
    """
    Super offline autocompleter combining:
    1. Static list / Slash commands
    2. Exact prefix match
    3. FTS5 Database match
    4. Fuzzy string matching
    """
    def __init__(self, slash_commands: list[tuple[str, str]], hashtag_pills: list[tuple[str, str]], memoria=None):
        self.slash_commands = slash_commands
        self.hashtag_pills = hashtag_pills
        history_path = Path.home() / ".cowork" / "super_history.db"
        self.db = HistoryDB(history_path)
        self.memoria = memoria
        
        # Cache for simple history completions so we don't query DB constantly for same prefix
        self._history_cache = []
        self._cache_time = 0
        
        # In-memory dictionary of words/compounds seen in this session
        self.session_words = set()
        # In-memory dictionary of bigrams (previous_word -> list of next_words)
        self.session_bigrams = {}

        # Load global dictionary for spelling correction/completion
        self.global_dictionary = set()
        self._load_dictionary()

    def _load_dictionary(self):
        """Load the OS word dictionary for android-like autocorrect."""
        dict_path = Path("/usr/share/dict/words")
        if dict_path.exists():
            try:
                with open(dict_path, "r", encoding="utf-8") as f:
                    for line in f:
                        w = line.strip().lower()
                        if len(w) >= 4 and w.isalpha():
                            self.global_dictionary.add(w)
            except Exception:
                pass

    @staticmethod
    def _esc(s: str) -> str:
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def add_session_text(self, text: str):
        """Extract compound words, file paths, variables from text to suggest later."""
        import re
        # Find words that might be paths, variables, snake_case, etc. Length >= 2
        words = re.findall(r'[a-zA-Z0-9_\-\./\\]{2,}', text)
        for i in range(len(words)):
            w = words[i]
            # Avoid picking up pure numbers or garbage
            if any(c.isalpha() for c in w):
                if len(w) >= 4:
                    self.session_words.add(w)
                # Add to bigrams
                if i < len(words) - 1:
                    next_w = words[i+1]
                    if any(c.isalpha() for c in next_w):
                        w_lower = w.lower()
                        if w_lower not in self.session_bigrams:
                            self.session_bigrams[w_lower] = []
                        if next_w not in self.session_bigrams[w_lower]:
                            self.session_bigrams[w_lower].append(next_w)
                
        # Keep set size reasonable (e.g., max 2000 words)
        if len(self.session_words) > 2000:
            self.session_words.clear()
        if len(self.session_bigrams) > 2000:
            self.session_bigrams.clear()

    def _refresh_cache(self):
        now = time.time()
        if now - self._cache_time > 5: # refresh cache every 5s max
            self._history_cache = self.db.get_recent_history(limit=500)
            self._cache_time = now

    def _fuzzy_match(self, query: str, limit=5) -> list[str]:
        self._refresh_cache()
        if HAS_RAPIDFUZZ:
            # We use partial_ratio for typo tolerance
            results = process.extract(query, self._history_cache, scorer=fuzz.partial_ratio, limit=limit)
            # return items that have a score > 60
            return [res[0] for res in results if res[1] > 60]
        else:
            results = simple_fuzz_match(query, self._history_cache, limit=limit)
            return [res[0] for res in results]

    def _dict_correction(self, word: str, limit=3) -> list[str]:
        """Find closest actual words from the global dictionary using fuzzy matching."""
        if not HAS_RAPIDFUZZ or not self.global_dictionary or len(word) < 3:
            return []
        # Score higher for prefix matches + similarity ratio
        results = process.extract(word.lower(), self.global_dictionary, scorer=fuzz.WRatio, limit=limit)
        # return items that have a score > 75
        return [res[0] for res in results if res[1] > 75]

    def get_completions(self, document: Document, complete_event: Any):
        text = document.text_before_cursor
        if not text:
            return

        # 1. Base Slash Commands (Exact/Prefix)
        if text.startswith("/"):
            typed = text.lower()
            for cmd, desc in self.slash_commands:
                if typed in cmd.lower():
                    display = HTML(f"<b>{self._esc(cmd)}</b>  <ansibrightblack>{self._esc(desc)}</ansibrightblack>")
                    yield Completion(cmd, start_position=-len(text), display=display, style='bg:ansigray fg:ansiwhite')
            # If the user is just typing the slash command (no arguments yet), don't show other completions
            if " " not in text.strip():
                return

        # 2. Hashtag Pill Completion
        words = text.split()
        if words and words[-1].startswith("#"):
            typed_tag = words[-1].lower()
            for tag, desc in self.hashtag_pills:
                if tag.lower().startswith(typed_tag):
                    yield Completion(
                        tag[len(words[-1]):],
                        start_position=0,
                        display=HTML(f"<ansiyellow><b>{self._esc(tag)}</b></ansiyellow>  <ansibrightblack>{self._esc(desc)}</ansibrightblack>")
                    )
            return
            
        # Extract the last word being typed
        last_word_match = __import__("re").search(r'[a-zA-Z0-9_\-\./\\]+$', text)
        last_word = last_word_match.group(0) if last_word_match else ""
        
        # Check if the user just typed a space, meaning we should predict the NEXT word
        is_space_end = text.endswith(" ")
        prev_word = ""
        if is_space_end and words:
            prev_word = words[-1].lower()

        # 3. Super History Completion (FTS / Fuzzy)
        # Avoid completing single letters too aggressively unless FTS match
        if len(text) >= 2 and not is_space_end:
            seen_completions = set()
            
            # 3a. FTS Prefix Match
            fts_matches = self.db.search_fts(text, limit=3)
            for match in fts_matches:
                if match not in seen_completions and match != text:
                    seen_completions.add(match)
                    yield Completion(
                        match,
                        start_position=-len(text),
                        display=HTML(f"<ansigreen>☄ {self._esc(match)}</ansigreen>"),
                        display_meta="History"
                    )
            
            # 3b. Fuzzy Typo Match
            fuzzy_matches = self._fuzzy_match(text, limit=3)
            for match in fuzzy_matches:
                if match not in seen_completions and match != text:
                    seen_completions.add(match)
                    yield Completion(
                        match,
                        start_position=-len(text),
                        display=HTML(f"<ansicyan>⚡ {self._esc(match)}</ansicyan>"),
                        display_meta="Fuzzy Session"
                    )
                    
            # 3c. Word completion from Session Text (LLM Outputs / User inputs) priority
            if len(last_word) >= 1:
                word_matches = [w for w in self.session_words if w.lower().startswith(last_word.lower()) and w != last_word]
                for w in word_matches[:5]:
                    if w.lower() not in [s.lower() for s in seen_completions]:
                        seen_completions.add(w)
                        yield Completion(
                            w,
                            start_position=-len(last_word),
                            display=HTML(f"<ansimagenta>🔹 {self._esc(w)}</ansimagenta>"),
                            display_meta="Session Word"
                        )
            
            # 3d. Android Keyboard-style Global Dictionary Typo Correction (Lowest Priority)
            if len(last_word) >= 3:
                dict_matches = self._dict_correction(last_word, limit=3)
                for w in dict_matches:
                    if w.lower() not in [s.lower() for s in seen_completions] and w.lower() != last_word.lower():
                        seen_completions.add(w)
                        yield Completion(
                            w,
                            start_position=-len(last_word),
                            display=HTML(f"<ansibrightblack>📖 {self._esc(w)}</ansibrightblack>"),
                            display_meta="Dictionary"
                        )
                        
        # 4. Next-Word Prediction (Bigrams)
        if is_space_end and prev_word in self.session_bigrams:
            next_words = self.session_bigrams[prev_word]
            for w in next_words[:5]:
                yield Completion(
                    w,
                    start_position=0,
                    display=HTML(f"<ansimagenta>🔮 {self._esc(w)}</ansimagenta>"),
                    display_meta="Next Word"
                )
