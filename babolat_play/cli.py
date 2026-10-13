"""Command line: python3 -m babolat_play <command>"""
import argparse
import sys
from pathlib import Path
from typing import List, Optional

from . import agent, demo, paths, server, site
from .importer import ImportResult, find_racket_volumes, import_path
from .milestones import compute_milestones
from .notify import notify
from .store import Store

REPO_ROOT = Path(__file__).resolve().parent.parent
KMH_PER_MPH = 1.609344


def _sync_and_build(store: Store, import_id: int, out: Path, label: Optional[str] = None) -> list:
    added = store.sync_milestones(compute_milestones(store.sessions()), import_id)
    site.build_site(store, out, label)
    return added


def _milestone_text(m) -> str:
    if m.key.startswith("pb_") and m.stroke and m.key != f"pb_topspin@{m.session_id}":
        return f"{m.title} · {round(m.value / KMH_PER_MPH)} mph"
    return m.title


def cmd_import(args) -> int:
    volumes = [Path(args.path)] if args.path else find_racket_volumes()
    if not volumes:
        if not args.auto:
            print("No racket found. Plug it in (it mounts as BABOLAT) or pass --path.")
        return 0 if args.auto else 1
    store = Store(paths.db_path())
    import_id = store.begin_import()
    total = ImportResult(import_id)
    for vol in volumes:
        try:
            r = import_path(vol, store, archive=paths.raw_dir(), min_swings=args.min_swings,
                            import_id=import_id)
        except PermissionError:
            notify("Babolat Play", "Can't read the racket. Allow Python access to removable volumes (see README).")
            print(f"Permission denied reading {vol}. See README > Troubleshooting.", file=sys.stderr)
            return 1
        total.new += r.new
        total.updated += r.updated
        total.skipped += r.skipped
        total.errors += r.errors
    store.finish_import(import_id, len(total.new), len(total.updated))
    added = _sync_and_build(store, import_id, paths.site_dir())

    print(f"{len(total.new)} new, {len(total.updated)} updated, {total.skipped} already imported or skipped")
    for e in total.errors:
        print(f"  skipped file: {e}", file=sys.stderr)
    for m in added:
        print(f"  milestone: {_milestone_text(m)}")
    if args.auto and (total.new or total.updated):
        n = len(total.new) + len(total.updated)
        msg = f"{n} new session{'s' if n != 1 else ''} imported"
        if added:
            msg += " · 🏆 " + ", ".join(_milestone_text(m) for m in added[:3])
        notify("Babolat Play", msg)
    return 0


def cmd_build(args) -> int:
    out = site.build_site(Store(paths.db_path()), paths.site_dir())
    print(f"Built {out}")
    return 0


def cmd_serve(args) -> int:
    if not (paths.site_dir() / "index.html").exists():
        site.build_site(Store(paths.db_path()), paths.site_dir())
    print("Dashboard on your network:")
    for url in server.lan_urls(args.port):
        print(f"  {url}")
    sys.stdout.flush()
    server.serve(paths.site_dir(), args.host, args.port)
    return 0


def cmd_install(args) -> int:
    if sys.platform != "darwin":
        print("Auto-import agents are macOS only. Use `import` manually and `serve` to view.")
        return 1
    for p in agent.install(REPO_ROOT, paths.home(), sys.executable, args.port, serve=not args.no_serve):
        print(f"Installed {p}")
    print("Running a first import now...")
    cmd_import(argparse.Namespace(path=None, auto=False, min_swings=10))
    if not args.no_serve:
        print("Open on your phone (same Wi-Fi), then Share > Add to Home Screen:")
        for url in server.lan_urls(args.port):
            print(f"  {url}")
    return 0


def cmd_uninstall(args) -> int:
    for p in agent.uninstall():
        print(f"Removed {p}")
    print(f"Your data is kept in {paths.home()}")
    return 0


def cmd_demo(args) -> int:
    store = Store(":memory:")
    first = store.begin_import()
    import_path(demo.FIXTURE_DIR, store, import_id=first)
    synthetic = demo.synthetic_sessions(seed=7)
    for s in synthetic[:-3]:
        store.upsert_session(s)
    _sync_and_build(store, first, Path(args.out), demo.LABEL)
    latest = store.begin_import()
    for s in synthetic[-3:]:
        store.upsert_session(s)
    _sync_and_build(store, latest, Path(args.out), demo.LABEL)
    print(f"Demo dashboard built in {args.out}. Open {Path(args.out).resolve() / 'index.html'}")
    return 0


def cmd_status(args) -> int:
    store = Store(paths.db_path())
    sessions = store.sessions()
    print(f"Data folder:   {paths.home()}")
    print(f"Sessions:      {len(sessions)} ({sum(len(s.swings) for s in sessions)} shots)")
    print(f"Last import:   {store.last_import_at() or 'never'}")
    print(f"Racket found:  {', '.join(map(str, find_racket_volumes())) or 'no'}")
    for label, ok in agent.installed().items():
        print(f"Agent {label}: {'installed' if ok else 'not installed'}")
    print("URLs:          " + "  ".join(server.lan_urls(8765)))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="babolat_play", description="Your Babolat Play racket data, back in your hands.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("import", help="import new sessions from the racket and rebuild the dashboard")
    p.add_argument("--path", help="folder holding LOG*.BIN (default: auto-detect the racket)")
    p.add_argument("--auto", action="store_true", help="quiet mode for the launchd agent; notifies on news")
    p.add_argument("--min-swings", type=int, default=10, help="ignore sessions shorter than this")
    p.set_defaults(fn=cmd_import)
    sub.add_parser("build", help="rebuild the dashboard from stored data").set_defaults(fn=cmd_build)
    p = sub.add_parser("serve", help="serve the dashboard on your local network")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--host", default="0.0.0.0")
    p.set_defaults(fn=cmd_serve)
    p = sub.add_parser("install", help="macOS: auto-import on plug-in and keep the server running")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--no-serve", action="store_true", help="only install the import agent")
    p.set_defaults(fn=cmd_install)
    sub.add_parser("uninstall", help="remove the launchd agents (keeps your data)").set_defaults(fn=cmd_uninstall)
    p = sub.add_parser("demo", help="build a demo dashboard (real 2022 session + synthetic data)")
    p.add_argument("--out", default="site-demo")
    p.set_defaults(fn=cmd_demo)
    sub.add_parser("status", help="show what's imported and what's installed").set_defaults(fn=cmd_status)
    args = ap.parse_args(argv)
    return args.fn(args)
