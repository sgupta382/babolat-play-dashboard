"""Correct session times after the racket's clock resets.

A flat battery resets the racket clock to 2012-09-01, so every later session
carries a 2012 date. One offset (real time minus racket time), measured from a
session whose real end time you know, fixes every session recorded since that
reset. The saved calibration remembers which sessions it saw: an unknown
session dated before its anchor means the clock has reset again.
"""
import json
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from .parser import Session


class Clock:
    def __init__(self, offset_s: int, anchor: datetime, ids: List[str]):
        self.offset_s = offset_s
        self.anchor = anchor      # racket-clock end of the latest calibrated session
        self.ids = set(ids)       # sessions present when the clock was calibrated

    def correct(self, s: Session) -> Optional[Session]:
        """The session with its real start time, or None if it can't be dated."""
        if not s.clock_reset:
            return s
        if s.id not in self.ids and s.started_at <= self.anchor:
            return None  # recorded after another reset
        return replace(s, started_at=s.started_at + timedelta(seconds=self.offset_s))


def calibrate(sessions: List[Session], last_ended: datetime) -> Clock:
    """Calibrate from the real time the latest reset-clock session ended."""
    reset = [s for s in sessions if s.clock_reset]
    if not reset:
        raise ValueError("no sessions with a reset clock")
    anchor = max(s.started_at + timedelta(seconds=s.duration_s) for s in reset)
    return Clock(round((last_ended - anchor).total_seconds()), anchor, [s.id for s in reset])


def load(path: Path) -> Optional[Clock]:
    try:
        d = json.loads(Path(path).read_text())
    except FileNotFoundError:
        return None
    return Clock(d["offset_s"], datetime.fromisoformat(d["anchor"]), d["ids"])


def save(path: Path, clock: Clock) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps({
        "offset_s": clock.offset_s,
        "anchor": clock.anchor.isoformat(),
        "ids": sorted(clock.ids),
    }, indent=2))
