"""SQLite persistence for sessions, swings, milestones and import runs."""
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Sequence, Union

from .parser import Session, Swing

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY, started_at TEXT NOT NULL, source TEXT,
  swing_count INTEGER NOT NULL, imported_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS swings (
  session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  idx INTEGER NOT NULL, t INTEGER, stroke TEXT, spin TEXT, zone INTEGER,
  speed_kmh REAL, glitch INTEGER, raw TEXT, PRIMARY KEY (session_id, idx));
CREATE TABLE IF NOT EXISTS milestones (
  key TEXT PRIMARY KEY, title TEXT, detail TEXT, value REAL, stroke TEXT,
  session_id TEXT, achieved_at TEXT, import_id INTEGER);
CREATE TABLE IF NOT EXISTS imports (
  id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL,
  new_sessions INTEGER DEFAULT 0, updated_sessions INTEGER DEFAULT 0);
"""
MILESTONE_FIELDS = ("key", "title", "detail", "value", "stroke", "session_id", "achieved_at")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Store:
    def __init__(self, path: Union[str, Path]):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path))
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript(SCHEMA)

    # --- sessions -------------------------------------------------------
    def upsert_session(self, s: Session) -> str:
        """Insert a new session, replace one whose log has grown, else skip."""
        row = self.db.execute("SELECT swing_count FROM sessions WHERE id = ?", (s.id,)).fetchone()
        if row and row[0] >= len(s.swings):
            return "skipped"
        with self.db:
            if row:
                self.db.execute("DELETE FROM swings WHERE session_id = ?", (s.id,))
                self.db.execute("UPDATE sessions SET swing_count = ?, imported_at = ? WHERE id = ?",
                                (len(s.swings), _now(), s.id))
            else:
                self.db.execute("INSERT INTO sessions VALUES (?, ?, ?, ?, ?)",
                                (s.id, s.started_at.isoformat(), s.source, len(s.swings), _now()))
            self.db.executemany(
                "INSERT INTO swings VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [(s.id, w.idx, w.t, w.stroke, w.spin, w.zone, w.speed_kmh, int(w.glitch), w.raw)
                 for w in s.swings])
        return "updated" if row else "new"

    def sessions(self) -> List[Session]:
        out = []
        for sid, started, source in self.db.execute(
                "SELECT id, started_at, source FROM sessions ORDER BY started_at, id"):
            swings = [Swing(idx, t, stroke, spin, zone, speed, bool(glitch), raw)
                      for idx, t, stroke, spin, zone, speed, glitch, raw in self.db.execute(
                          "SELECT idx, t, stroke, spin, zone, speed_kmh, glitch, raw "
                          "FROM swings WHERE session_id = ? ORDER BY idx", (sid,))]
            out.append(Session(sid, datetime.fromisoformat(started), source, swings))
        return out

    # --- import runs ----------------------------------------------------
    def begin_import(self) -> int:
        with self.db:
            return self.db.execute("INSERT INTO imports (at) VALUES (?)", (_now(),)).lastrowid

    def finish_import(self, import_id: int, new: int, updated: int) -> None:
        with self.db:
            self.db.execute("UPDATE imports SET new_sessions = ?, updated_sessions = ? WHERE id = ?",
                            (new, updated, import_id))

    def discard_import(self, import_id: int) -> None:
        with self.db:
            self.db.execute("DELETE FROM imports WHERE id = ?", (import_id,))

    def latest_import_id(self) -> Optional[int]:
        return self.db.execute("SELECT MAX(id) FROM imports").fetchone()[0]

    def last_import_at(self) -> Optional[str]:
        row = self.db.execute("SELECT at FROM imports ORDER BY id DESC LIMIT 1").fetchone()
        return row[0] if row else None

    # --- milestones -----------------------------------------------------
    def sync_milestones(self, ms: Sequence, import_id: int) -> list:
        """Make the table match `ms`. Existing keys keep their original import id,
        so re-computing history never re-celebrates an old milestone.
        Returns the milestones that were newly added."""
        existing = {k for (k,) in self.db.execute("SELECT key FROM milestones")}
        keys = {m.key for m in ms}
        added = []
        with self.db:
            for k in existing - keys:
                self.db.execute("DELETE FROM milestones WHERE key = ?", (k,))
            for m in ms:
                vals = tuple(getattr(m, f) for f in MILESTONE_FIELDS)
                if m.key in existing:
                    self.db.execute(
                        "UPDATE milestones SET title=?, detail=?, value=?, stroke=?, session_id=?, achieved_at=? "
                        "WHERE key=?", vals[1:] + (m.key,))
                else:
                    self.db.execute("INSERT INTO milestones VALUES (?, ?, ?, ?, ?, ?, ?, ?)", vals + (import_id,))
                    added.append(m)
        return added

    def milestones(self) -> List[dict]:
        cols = MILESTONE_FIELDS + ("import_id",)
        return [dict(zip(cols, row)) for row in self.db.execute(
            f"SELECT {', '.join(cols)} FROM milestones ORDER BY achieved_at, key")]
