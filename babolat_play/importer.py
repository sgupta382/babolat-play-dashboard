"""Find the racket, read its logs (never writing to it) and store new sessions."""
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence

from .parser import FormatError, parse_log
from .store import Store

VOLUME_NAME = "BABOLAT"


@dataclass
class ImportResult:
    import_id: int
    new: List[str] = field(default_factory=list)
    updated: List[str] = field(default_factory=list)
    skipped: int = 0
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


def import_path(src: Path, store: Store, archive: Optional[Path] = None,
                min_swings: int = 10, import_id: Optional[int] = None) -> ImportResult:
    own_run = import_id is None
    result = ImportResult(import_id if not own_run else store.begin_import())
    for f in sorted(Path(src).glob("LOG*.BIN"), key=lambda p: p.name.upper()):
        data = f.read_bytes()
        if archive is not None:
            _archive(data, archive)
        try:
            sessions = parse_log(data, f.name)
        except FormatError as e:
            result.errors.append(f"{f.name}: {e}")
            continue
        for s in sessions:
            if len(s.swings) < min_swings:
                result.skipped += 1
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
