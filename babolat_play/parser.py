"""Decode Babolat Play LOG*.BIN files.

Layout (see docs/FILE_FORMAT.md for evidence and confidence per field):
a 50-byte header, then 13-byte records. A record whose first byte is 0
starts a session and carries its local start time; every other record is
one detected swing.
"""
import hashlib
import struct
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

HEADER_LEN = 50
REC_LEN = 13
# A jump this large between consecutive swings is a clock glitch, not a pause.
MAX_GAP_S = 1800
MPH_TO_KMH = 1.609344

# Inferred mappings - the only place to change when the format is better understood.
STROKES = {2: "serve", 3: "forehand", 4: "backhand", 8: "volley", 9: "volley"}
SPINS = {0: "flat", 1: "topspin", 2: "slice"}


class FormatError(ValueError):
    """The bytes do not match the known log layout."""


@dataclass(frozen=True)
class Swing:
    idx: int
    t: int                      # seconds since session start
    stroke: str
    spin: str
    zone: int                   # byte 1, meaning unknown (kept for future decoding)
    speed_kmh: Optional[float]
    glitch: bool                # timestamp implausible, keep out of timelines
    raw: str                    # record hex, so history can be re-decoded later


@dataclass
class Session:
    id: str
    started_at: datetime
    source: str
    swings: List[Swing]


def _speed_kmh(stroke: str, r: bytes) -> Optional[float]:
    if stroke == "serve":
        return float(r[5]) if r[5] else None
    return round(r[4] * MPH_TO_KMH, 1) if r[4] else None


def _start_time(r: bytes) -> datetime:
    try:
        return datetime(2000 + r[6], r[5], r[4], r[1], r[2], r[3])
    except ValueError as e:
        raise FormatError(f"invalid session start time: {e}") from None


def parse_log(data: bytes, source: str = "") -> List[Session]:
    if len(data) < HEADER_LEN or (len(data) - HEADER_LEN) % REC_LEN:
        raise FormatError(f"{len(data)} bytes is not a {HEADER_LEN}-byte header plus {REC_LEN}-byte records")
    header = data[:HEADER_LEN]
    sessions: List[Session] = []
    prev_t = 0
    for off in range(HEADER_LEN, len(data), REC_LEN):
        r = data[off:off + REC_LEN]
        if r[0] == 0:
            sid = hashlib.sha1(header + r).hexdigest()[:16]
            sessions.append(Session(sid, _start_time(r), source, []))
            prev_t = 0
            continue
        if not sessions:
            continue  # swings before any session start cannot be dated
        t = struct.unpack_from("<H", r, 11)[0]
        stroke = STROKES.get(r[0], "unknown")
        swings = sessions[-1].swings
        swings.append(Swing(
            idx=len(swings),
            t=t,
            stroke=stroke,
            spin=SPINS.get(r[2], "unknown"),
            zone=r[1],
            speed_kmh=_speed_kmh(stroke, r),
            glitch=t - prev_t > MAX_GAP_S,
            raw=r.hex(),
        ))
        prev_t = t
    return sessions
