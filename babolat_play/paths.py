"""Where the tool keeps its data. Override the root with BABOLAT_PLAY_HOME."""
import os
from pathlib import Path


def home() -> Path:
    return Path(os.environ.get("BABOLAT_PLAY_HOME", Path.home() / ".babolat-play")).expanduser()


def db_path() -> Path:
    return home() / "play.db"


def site_dir() -> Path:
    return home() / "site"


def raw_dir() -> Path:
    return home() / "raw"
