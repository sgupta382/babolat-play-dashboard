"""Derive milestones from session history. Pure: same history, same milestones.

Keys are stable identifiers; the store uses them to tell genuinely new
achievements from ones already celebrated.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional

from .parser import Session

SHOT_TOTALS = (500, 1000, 2500, 5000, 10000)
SESSION_COUNTS = (1, 5, 10, 25, 50, 100)
STREAK_WEEKS = (3, 5, 10)
SPEED_STROKES = ("serve", "forehand", "backhand", "volley")
MIN_FOREHANDS_FOR_SPIN = 20


@dataclass(frozen=True)
class Milestone:
    key: str
    title: str
    detail: str
    value: float
    stroke: Optional[str]
    session_id: str
    achieved_at: str  # ISO datetime of the session that achieved it


def _week_index(s: Session) -> int:
    d = s.started_at.date()
    return (d.toordinal() - d.weekday()) // 7  # Monday-based weeks, continuous across years


def compute_milestones(sessions: List[Session]) -> List[Milestone]:
    out: List[Milestone] = []
    best_speed: Dict[str, float] = {}
    best_shots: Optional[int] = None
    best_topspin: Optional[float] = None
    total_shots = 0
    weeks_seen = set()
    best_streak = 0

    for n, s in enumerate(sorted(sessions, key=lambda x: (x.started_at, x.id)), 1):
        at = s.started_at.isoformat()

        def add(key, title, detail, value, stroke=None):
            out.append(Milestone(key, title, detail, float(value), stroke, s.id, at))

        if n == 1:
            add("first_session", "First session recorded", "Your tracking journey starts here", 1)
        if n in SESSION_COUNTS:
            add(f"sessions_{n}", f"{n} sessions", f"{n} sessions tracked", n)

        before = total_shots
        total_shots += len(s.swings)
        for t in SHOT_TOTALS:
            if before < t <= total_shots:
                add(f"shots_{t}", f"{t:,} shots", f"{t:,} shots hit across all sessions", t)

        for stroke in SPEED_STROKES:
            speeds = [w.speed_kmh for w in s.swings if w.stroke == stroke and w.speed_kmh]
            if not speeds:
                continue
            top = max(speeds)
            if stroke in best_speed and top > best_speed[stroke]:
                add(f"pb_{stroke}@{s.id}", f"New {stroke} speed record",
                    f"Fastest {stroke} yet", top, stroke)
            best_speed[stroke] = max(top, best_speed.get(stroke, top))

        shots = len(s.swings)
        if best_shots is not None and shots > best_shots:
            add(f"pb_shots@{s.id}", "Most shots in a session", f"{shots} shots in one session", shots)
        best_shots = max(shots, best_shots or 0)

        fh = [w for w in s.swings if w.stroke == "forehand"]
        if len(fh) >= MIN_FOREHANDS_FOR_SPIN:
            pct = round(100 * sum(w.spin == "topspin" for w in fh) / len(fh))
            if best_topspin is not None and pct > best_topspin:
                add(f"pb_topspin@{s.id}", "Topspin record", f"{pct}% of forehands hit with topspin",
                    pct, "forehand")
            best_topspin = max(pct, best_topspin if best_topspin is not None else pct)

        w = _week_index(s)
        if w not in weeks_seen:
            weeks_seen.add(w)
            streak = 1
            while w - streak in weeks_seen:
                streak += 1
            for target in STREAK_WEEKS:
                if best_streak < target <= streak:
                    add(f"streak_{target}", f"{target}-week streak",
                        f"Played {target} weeks in a row", target)
            best_streak = max(best_streak, streak)
    return out
