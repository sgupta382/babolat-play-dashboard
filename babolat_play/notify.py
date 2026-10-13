"""Desktop notification on macOS; silently does nothing elsewhere."""
import json
import subprocess
import sys


def notify(title: str, message: str) -> None:
    if sys.platform != "darwin":
        return
    # json.dumps quotes and escapes " and \\; ensure_ascii=False because AppleScript
    # rejects \\uXXXX escapes (which would silently drop every emoji notification).
    q = lambda s: json.dumps(s, ensure_ascii=False)
    script = f"display notification {q(message)} with title {q(title)}"
    try:
        subprocess.run(["osascript", "-e", script], check=False, timeout=10,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        pass
