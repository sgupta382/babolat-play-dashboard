"""Build the static dashboard: the app shell plus a generated data.js."""
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from . import __version__
from .store import Store

APP_DIR = Path(__file__).parent / "app"


def build_payload(store: Store, demo_label: Optional[str] = None) -> dict:
    latest = store.latest_import_id()
    sessions = []
    for s in store.sessions():
        timed = [w.t for w in s.swings if not w.glitch]
        sessions.append({
            "id": s.id,
            "started_at": s.started_at.isoformat(),
            "source": s.source,
            "duration_s": max(timed) if timed else 0,
            # compact rows: [t, stroke, spin, speed_kmh, glitch]
            "swings": [[w.t, w.stroke, w.spin, w.speed_kmh, int(w.glitch)] for w in s.swings],
        })
    milestones = [dict(m, is_new=latest is not None and m.pop("import_id") == latest)
                  for m in store.milestones()]
    return {
        "version": 1,
        "app_version": __version__,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "demo": demo_label,
        "latest_import_id": latest,
        "sessions": sessions,
        "milestones": milestones,
    }


def _write_data(out: Path, payload: dict) -> None:
    (out / "data.js").write_text("window.PLAY_DATA=" + json.dumps(payload, separators=(",", ":")) + ";\n")


def build_site(store: Store, out_dir: Path, demo_label: Optional[str] = None) -> Path:
    """Build into a sibling temp dir, then swap it in, so a failed build
    never leaves the served site half-written."""
    out_dir = Path(out_dir)
    tmp = out_dir.with_name(out_dir.name + ".tmp")
    old = out_dir.with_name(out_dir.name + ".old")
    for d in (tmp, old):
        shutil.rmtree(d, ignore_errors=True)
    try:
        shutil.copytree(APP_DIR, tmp)
        _write_data(tmp, build_payload(store, demo_label))
        if out_dir.exists():
            out_dir.rename(old)
        tmp.rename(out_dir)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        if old.exists() and not out_dir.exists():
            old.rename(out_dir)
        raise
    shutil.rmtree(old, ignore_errors=True)
    return out_dir
