"""Serve the built dashboard read-only on the local network."""
import socket
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import List


class _Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def list_directory(self, path):  # no directory listings
        self.send_error(404)
        return None

    def log_message(self, *args):
        pass


def lan_urls(port: int) -> List[str]:
    urls = [f"http://{socket.gethostname().split('.')[0]}.local:{port}"]
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))  # TEST-NET address: no packet is sent for UDP connect
            urls.append(f"http://{s.getsockname()[0]}:{port}")
    except OSError:
        pass
    return urls


def serve(site_dir: Path, host: str = "0.0.0.0", port: int = 8765) -> None:
    Path(site_dir).mkdir(parents=True, exist_ok=True)
    handler = partial(_Handler, directory=str(site_dir))
    with ThreadingHTTPServer((host, port), handler) as httpd:
        httpd.serve_forever()
