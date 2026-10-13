"""macOS launchd agents: import whenever a volume mounts, and keep the server up."""
import os
import plistlib
import shutil
import subprocess
from pathlib import Path
from typing import Tuple

IMPORT_LABEL = "com.babolatplay.import"
SERVE_LABEL = "com.babolatplay.serve"
AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
PACKAGE_DIR = Path(__file__).resolve().parent


def stage_package(home: Path) -> Path:
    """Copy the package to <home>/lib so the agents never run code from the clone
    (launchd jobs can't read ~/Downloads, ~/Desktop or ~/Documents without consent).
    Returns the directory to put on PYTHONPATH."""
    lib = home / "lib"
    tmp = lib / "babolat_play.tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree(PACKAGE_DIR, tmp, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.rmtree(lib / "babolat_play", ignore_errors=True)
    tmp.rename(lib / "babolat_play")
    return lib


def build_plists(lib: Path, home: Path, python: str, port: int) -> Tuple[dict, dict]:
    env = {"PYTHONPATH": str(lib), "BABOLAT_PLAY_HOME": str(home)}
    log = str(home / "agent.log")
    common = {"EnvironmentVariables": env, "StandardOutPath": log, "StandardErrorPath": log,
              "WorkingDirectory": str(home)}
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


def install(home: Path, python: str, port: int, serve: bool = True) -> list:
    AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    home.mkdir(parents=True, exist_ok=True)
    importer, server = build_plists(stage_package(home), home, python, port)
    if not serve:  # honour --no-serve even if an earlier install started the server
        stale = _plist_path(SERVE_LABEL)
        if stale.exists():
            _unload(SERVE_LABEL, stale)
            stale.unlink()
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
