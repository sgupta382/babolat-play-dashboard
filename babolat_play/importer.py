"""Find the racket, read its logs (never writing to it) and store new sessions."""
import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence

from .clock import Clock
from .parser import FormatError, Session, parse_log
from .store import Store

VOLUME_NAME = "BABOLAT"


@dataclass
class ImportResult:
    import_id: int
    new: List[str] = field(default_factory=list)
    updated: List[str] = field(default_factory=list)
    skipped: int = 0
    undated: int = 0            # reset racket clock and no calibration covers them
    errors: List[str] = field(default_factory=list)


def _is_racket(d: Path) -> bool:
    if d.name.upper() == VOLUME_NAME:
        return True
    return (d / "PLAY.URL").exists() and any(d.glob("LOG*.BIN"))


def find_racket_volumes(roots: Sequence[Path] = (Path("/Volumes"),)) -> List[Path]:
    found = []
    for root in roots:
        try:
            dirs = sorted(p for p in Path(root).iterdir() if p.is_dir())
        except OSError:
            continue
        found += [d for d in dirs if _is_racket(d)]
    return found


def _archive(data: bytes, archive: Path) -> None:
    """Keep every raw log we ever saw, so sessions can be re-decoded later."""
    archive.mkdir(parents=True, exist_ok=True)
    dest = archive / f"{hashlib.sha1(data).hexdigest()}.BIN"
    if not dest.exists():
        dest.write_bytes(data)


def log_files(src: Path) -> List[Path]:
    """LOG*.BIN files in src. Raises PermissionError/FileNotFoundError rather than
    returning nothing (pathlib's glob swallows a denied directory listing)."""
    names = [n for n in os.listdir(src) if n.upper().startswith("LOG") and n.upper().endswith(".BIN")]
    return [Path(src) / n for n in sorted(names, key=str.upper)]


def read_sessions(src: Path, archive: Optional[Path] = None,
                  errors: Optional[List[str]] = None) -> List[Session]:
    """Every session in the logs under src. Unreadable files go to `errors`."""
    out = []
    for f in log_files(src):
        data = f.read_bytes()
        if archive is not None:
            _archive(data, archive)
        try:
            out += parse_log(data, f.name)
        except FormatError as e:
            if errors is not None:
                errors.append(f"{f.name}: {e}")
    return out


def import_path(src: Path, store: Store, archive: Optional[Path] = None,
                min_swings: int = 10, import_id: Optional[int] = None,
                clock: Optional[Clock] = None) -> ImportResult:
    own_run = import_id is None
    result = ImportResult(import_id if not own_run else store.begin_import())
    for s in read_sessions(src, archive, result.errors):
        if len(s.swings) < min_swings:
            result.skipped += 1
            continue
        if s.clock_reset:
            s = clock.correct(s) if clock else None
            if s is None:
                result.undated += 1
                continue
        outcome = store.upsert_session(s)
        if outcome == "new":
            result.new.append(s.id)
        elif outcome == "updated":
            result.updated.append(s.id)
        else:
            result.skipped += 1
    if own_run:
        store.finish_import(result.import_id, len(result.new), len(result.updated))
    return result


def redecode(archive: Path, store: Store) -> int:
    """Re-decode stored sessions from the raw archive with the current parser,
    keeping their stored start times. Returns how many sessions were rewritten."""
    latest = {}
    for f in sorted(Path(archive).glob("*.BIN")):  # named by content hash, not LOG*.BIN
        try:
            sessions = parse_log(f.read_bytes(), f.name)
        except FormatError:
            continue
        for s in sessions:
            if s.id not in latest or len(s.swings) > len(latest[s.id].swings):
                latest[s.id] = s  # a log that grew is archived once per version
    return sum(store.replace_swings(s) for s in latest.values())
