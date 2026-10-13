"""macOS launchd agents: import whenever a volume mounts, and keep the server up."""
import os
import plistlib
import subprocess
from pathlib import Path
from typing import Tuple

IMPORT_LABEL = "com.babolatplay.import"
SERVE_LABEL = "com.babolatplay.serve"
AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"


def build_plists(repo_root: Path, home: Path, python: str, port: int) -> Tuple[dict, dict]:
    env = {"PYTHONPATH": str(repo_root), "BABOLAT_PLAY_HOME": str(home)}
    log = str(home / "agent.log")
    common = {"EnvironmentVariables": env, "StandardOutPath": log, "StandardErrorPath": log,
              "WorkingDirectory": str(repo_root)}
    importer = dict(common, Label=IMPORT_LABEL, StartOnMount=True, RunAtLoad=False,
                    ProgramArguments=[python, "-m", "babolat_play", "import", "--auto"])
    server = dict(common, Label=SERVE_LABEL, RunAtLoad=True, KeepAlive=True,
                  ProgramArguments=[python, "-m", "babolat_play", "serve", "--port", str(port)])
    return importer, server


def _plist_path(label: str) -> Path:
    return AGENTS_DIR / f"{label}.plist"


def _launchctl(*args: str) -> bool:
    return subprocess.run(["launchctl", *args], stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL).returncode == 0


def _load(path: Path) -> None:
    if not _launchctl("bootstrap", f"gui/{os.getuid()}", str(path)):
        _launchctl("load", "-w", str(path))


def _unload(label: str, path: Path) -> None:
    if not _launchctl("bootout", f"gui/{os.getuid()}/{label}"):
        _launchctl("unload", "-w", str(path))


def install(repo_root: Path, home: Path, python: str, port: int, serve: bool = True) -> list:
    AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    home.mkdir(parents=True, exist_ok=True)
    importer, server = build_plists(repo_root, home, python, port)
    installed = []
    for plist in ([importer, server] if serve else [importer]):
        path = _plist_path(plist["Label"])
        if path.exists():
            _unload(plist["Label"], path)
        path.write_bytes(plistlib.dumps(plist))
        _load(path)
        installed.append(path)
    return installed


def uninstall() -> list:
    removed = []
    for label in (IMPORT_LABEL, SERVE_LABEL):
        path = _plist_path(label)
        if path.exists():
            _unload(label, path)
            path.unlink()
            removed.append(path)
    return removed


def installed() -> dict:
    return {label: _plist_path(label).exists() for label in (IMPORT_LABEL, SERVE_LABEL)}
