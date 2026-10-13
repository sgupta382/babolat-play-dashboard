# Babolat Play Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A local tool that imports Babolat Play racket sessions automatically when the racket is plugged in, stores the history, computes milestones, and serves a mobile-first PWA dashboard of trends on the LAN.

**Architecture:** A Python standard-library package `babolat_play` (parser → SQLite store → milestones → static site builder → `http.server`) plus launchd agents for import-on-mount and the server. The dashboard is plain HTML/CSS/JS reading a generated `data.js`, with no external dependencies.

**Tech Stack:** Python 3.9+ (stdlib only: sqlite3, http.server, unittest, plistlib), vanilla JS (ES2019), inline SVG charts, Canvas for share cards, Service Worker, macOS launchd.

**Spec:** `docs/design.md`

## Global Constraints
- Python ≥ 3.9 and stdlib only. No pip dependencies at runtime or for tests.
- The racket volume is never written to (open files `rb` only; no deletes, renames or mkdirs under the volume).
- The dashboard loads nothing from the network. No CDN, no web fonts.
- The app data dir is `~/.babolat-play/`, overridable with the env var `BABOLAT_PLAY_HOME`.
- The server listens on port 8765 by default.
- Speeds are stored in km/h. The UI defaults to mph and has a km/h toggle.
- Sessions with fewer than 10 swings are not imported.
- The repo is `sgupta382/babolat-play-dashboard`, public, MIT. The `data/` folder and personal DBs are git-ignored.
- Every UI that shows decoded values links to `docs/FILE_FORMAT.md` and says the meanings are inferred.

## Review Focus
1. **Racket plugged in twice with the same log:** the second import must report 0 new and 0 updated, produce no new milestones and send no notification (test in Task 3).
2. **The log grows between imports** (same session start, more swings): the session is replaced, not duplicated, and swing count increases (test in Task 3).
3. **A truncated or corrupt `.BIN`** (length not 50 + 13n, or an invalid date in the start record): that file is skipped with an error string, and the other files still import (tests in Tasks 1 and 3).
4. **A build failure mid-write:** the previous `site/` stays intact (test in Task 5).
5. **A session imported out of date order** (older than existing ones): the milestone chain is recomputed deterministically, and pre-existing milestone keys keep their original import ID, so they aren't re-celebrated (test in Task 4).

---

## File Structure

```
babolat_play/
  __init__.py       version
  __main__.py       -> cli.main()
  paths.py          home dir, db path, site dir, raw archive dir
  parser.py         bytes -> Session/Swing; format constants & mapping tables
  store.py          SQLite persistence
  importer.py       volume discovery, import orchestration, raw archive
  milestones.py     pure: sessions -> milestones
  site.py           data.js + copy app/ -> site/ (atomic swap)
  server.py         LAN static server
  agent.py          launchd plist install/uninstall
  notify.py         macOS notification (no-op elsewhere)
  demo.py           real 2022 fixture + synthetic sessions
  cli.py            argparse entry
  app/              index.html styles.css app.js charts.js share.js sw.js manifest.webmanifest icon.svg icon-192.png icon-512.png
  fixtures/LOG000_2022-08-29.BIN   (demo fixture, shipped in the package)
tests/
  fixtures/LOG000.BIN LOG001.BIN
  test_parser.py test_store.py test_importer.py test_milestones.py test_site.py
docs/ design.md ARCHITECTURE.md FILE_FORMAT.md img/*.png
README.md CONTRIBUTING.md LICENSE .gitignore
```
The prototype files (`babolat_play.py`, `dashboard_template.html`, `dashboard.html`) are deleted in Task 1. `data/` stays as a git-ignored local backup.

---

### Task 1: Repo scaffold and parser

**Files:** create `babolat_play/__init__.py`, `__main__.py`, `paths.py`, `parser.py`, `.gitignore`, `tests/fixtures/*`, `tests/test_parser.py`. Delete the prototype files.

**Produces:**
```python
# parser.py
HEADER_LEN = 50; REC_LEN = 13; MAX_GAP_S = 1800
STROKES = {2: "serve", 3: "forehand", 4: "backhand", 8: "volley", 9: "volley"}
SPINS = {0: "flat", 1: "topspin", 2: "slice"}
class FormatError(ValueError): ...
@dataclass(frozen=True)
class Swing: idx: int; t: int; stroke: str; spin: str; zone: int; speed_kmh: Optional[float]; glitch: bool; raw: str
@dataclass
class Session: id: str; started_at: datetime; source: str; swings: List[Swing]
def parse_log(data: bytes, source: str = "") -> List[Session]
# paths.py
def home() -> Path; def db_path() -> Path; def site_dir() -> Path; def raw_dir() -> Path
```
Rules:
- A file must be `len >= 50` with `(len-50) % 13 == 0`, else `FormatError`.
- A record with `r[0] == 0` starts a session. `started_at = datetime(2000+r[6], r[5], r[4], r[1], r[2], r[3])`, and a `ValueError` becomes `FormatError`.
- `id = sha1(header + start_record).hexdigest()[:16]`. Records before the first start record are dropped.
- `t = uint16 LE at r[11:13]`, and `glitch = t - prev_t > MAX_GAP_S`.
- `speed_kmh`: for serves `r[5]` (or `None` if 0). Otherwise `round(r[4] * 1.609344, 1)` (or `None` if 0).
- `raw = r.hex()`.

- [ ] **Step 1: Copy fixtures and write failing tests**
```bash
mkdir -p tests/fixtures babolat_play/fixtures && cp data/LOG000.BIN data/LOG001.BIN tests/fixtures/ && cp data/LOG000.BIN babolat_play/fixtures/LOG000_2022-08-29.BIN
```
```python
# tests/test_parser.py
import unittest
from datetime import datetime
from pathlib import Path
from babolat_play.parser import parse_log, FormatError, HEADER_LEN, REC_LEN
FIX = Path(__file__).parent / "fixtures"

class ParserTest(unittest.TestCase):
    def test_real_session(self):
        [s] = parse_log((FIX / "LOG000.BIN").read_bytes(), "LOG000.BIN")
        self.assertEqual(s.started_at, datetime(2022, 8, 29, 19, 17, 33))
        self.assertEqual(len(s.swings), 151)
        counts = {k: sum(w.stroke == k for w in s.swings) for k in ("forehand", "backhand", "serve", "volley")}
        self.assertEqual(counts, {"forehand": 52, "backhand": 39, "serve": 43, "volley": 17})
        self.assertEqual(sum(w.glitch for w in s.swings), 1)
        self.assertEqual(max(w.speed_kmh for w in s.swings if w.stroke == "serve"), 133)

    def test_factory_log(self):
        [s] = parse_log((FIX / "LOG001.BIN").read_bytes())
        self.assertEqual(s.started_at, datetime(2012, 9, 1, 15, 29, 52))
        self.assertEqual(len(s.swings), 3)

    def test_multi_session_file_splits(self):
        a = (FIX / "LOG000.BIN").read_bytes(); b = (FIX / "LOG001.BIN").read_bytes()
        sessions = parse_log(a + b[HEADER_LEN:])
        self.assertEqual([len(s.swings) for s in sessions], [151, 3])
        self.assertNotEqual(sessions[0].id, sessions[1].id)

    def test_id_stable_when_log_grows(self):
        a = (FIX / "LOG000.BIN").read_bytes()
        self.assertEqual(parse_log(a[:-REC_LEN])[0].id, parse_log(a)[0].id)

    def test_truncated_file_rejected(self):
        with self.assertRaises(FormatError):
            parse_log((FIX / "LOG000.BIN").read_bytes()[:-3])

    def test_bad_date_rejected(self):
        a = bytearray((FIX / "LOG000.BIN").read_bytes()); a[HEADER_LEN + 5] = 13  # month 13
        with self.assertRaises(FormatError):
            parse_log(bytes(a))
```
- [ ] **Step 2:** `python3 -m unittest tests.test_parser -v`. Expect an ImportError failure.
- [ ] **Step 3:** Implement `parser.py` and `paths.py` to the rules above, write `.gitignore` (`data/`, `*.db`, `site/`, `site-demo/`, `__pycache__/`, `.DS_Store`), and delete the prototype files.
- [ ] **Step 4:** Run the tests. Expect PASS.
- [ ] **Step 5:** `git init && git add -A && git commit -m "feat: log parser with session splitting"`

### Task 2: SQLite store

**Files:** `babolat_play/store.py`, `tests/test_store.py`

**Produces:**
```python
class Store:
    def __init__(self, path: Union[str, Path]): ...          # ":memory:" allowed; creates schema
    def upsert_session(self, s: Session) -> str                # "new" | "updated" | "skipped"
    def sessions(self) -> List[Session]                        # ordered by started_at, swings loaded
    def begin_import(self) -> int                              # inserts imports row, returns id
    def finish_import(self, import_id: int, new: int, updated: int) -> None
    def latest_import_id(self) -> Optional[int]
    def sync_milestones(self, ms: List["Milestone"], import_id: int) -> List["Milestone"]  # returns newly added
    def milestones(self) -> List[dict]                         # keys: key,title,detail,value,stroke,session_id,achieved_at,import_id
```
Schema: `sessions(id PK, started_at, source, swing_count, imported_at)`, `swings(session_id, idx, t, stroke, spin, zone, speed_kmh, glitch, raw, PK(session_id, idx))`, `milestones(key PK, title, detail, value, stroke, session_id, achieved_at, import_id)`, `imports(id PK AUTOINCREMENT, at, new_sessions, updated_sessions)`.

Upsert: an unknown id inserts and returns "new". A known id with a greater swing count deletes its swings, reinserts and returns "updated". Otherwise "skipped".

`sync_milestones`: keys absent from `ms` are deleted. Existing keys get their fields updated but keep `import_id`. New keys are inserted with `import_id` and returned.

- [ ] **Step 1: Failing tests**
```python
import unittest
from pathlib import Path
from babolat_play.parser import parse_log, REC_LEN
from babolat_play.store import Store
FIX = Path(__file__).parent / "fixtures"

class StoreTest(unittest.TestCase):
    def setUp(self):
        self.db = Store(":memory:"); self.raw = (FIX / "LOG000.BIN").read_bytes()
    def test_new_then_skip(self):
        s = parse_log(self.raw)[0]
        self.assertEqual(self.db.upsert_session(s), "new")
        self.assertEqual(self.db.upsert_session(s), "skipped")
        self.assertEqual(len(self.db.sessions()), 1)
    def test_grown_session_updates(self):
        self.db.upsert_session(parse_log(self.raw[:-2 * REC_LEN])[0])
        self.assertEqual(self.db.upsert_session(parse_log(self.raw)[0]), "updated")
        [s] = self.db.sessions(); self.assertEqual(len(s.swings), 151)
    def test_roundtrip_fields(self):
        orig = parse_log(self.raw)[0]; self.db.upsert_session(orig)
        back = self.db.sessions()[0]
        self.assertEqual(back.started_at, orig.started_at); self.assertEqual(back.swings, orig.swings)
```
- [ ] **Step 2:** Run. Expect FAIL.
- [ ] **Step 3:** Implement `store.py`.
- [ ] **Step 4:** Run. Expect PASS.
- [ ] **Step 5:** Commit: `feat: sqlite store with idempotent upsert`

### Task 3: Importer, raw archive and notify

**Files:** `babolat_play/importer.py`, `notify.py`, `tests/test_importer.py`

**Produces:**
```python
@dataclass
class ImportResult: new: List[str]; updated: List[str]; skipped: int; errors: List[str]; import_id: int
def find_racket_volumes(roots: Sequence[Path] = (Path("/Volumes"),)) -> List[Path]   # dirs named BABOLAT (case-insens.) or containing PLAY.URL + LOG*.BIN
def import_path(src: Path, store: Store, archive: Optional[Path] = None, min_swings: int = 10) -> ImportResult
# notify.py
def notify(title: str, message: str) -> None   # osascript on darwin, else no-op; never raises
```
`import_path` handles each `LOG*.BIN` (sorted) by reading bytes and copying them to `archive/<sha1>.BIN` if absent. It then parses (a `FormatError` appends `"<name>: <err>"` and continues), drops sessions under `min_swings`, and upserts. The result counts and import ID are recorded with `begin_import`/`finish_import`. It never writes under `src`.

- [ ] **Step 1: Failing tests** (use a temp dir as the fake volume)
```python
import tempfile, shutil, unittest, os
from pathlib import Path
from babolat_play.importer import import_path, find_racket_volumes
from babolat_play.store import Store
FIX = Path(__file__).parent / "fixtures"

class ImporterTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()); self.vol = self.tmp / "BABOLAT"; self.vol.mkdir()
        for f in ("LOG000.BIN", "LOG001.BIN"): shutil.copy(FIX / f, self.vol / f)
        (self.vol / "PLAY.URL").write_text("x"); self.db = Store(":memory:")
    def tearDown(self): shutil.rmtree(self.tmp)
    def test_first_import_skips_factory_log(self):
        r = import_path(self.vol, self.db, archive=self.tmp / "raw")
        self.assertEqual((len(r.new), len(r.updated), r.errors), (1, 0, []))
        self.assertEqual(len(list((self.tmp / "raw").glob("*.BIN"))), 2)
    def test_reimport_is_noop(self):
        import_path(self.vol, self.db); r = import_path(self.vol, self.db)
        self.assertEqual((len(r.new), len(r.updated)), (0, 0))
    def test_corrupt_file_does_not_block_others(self):
        (self.vol / "LOG002.BIN").write_bytes(b"\x00" * 51)
        r = import_path(self.vol, self.db)
        self.assertEqual(len(r.new), 1); self.assertTrue(any("LOG002.BIN" in e for e in r.errors))
    def test_volume_untouched(self):
        before = {p.name: (p.stat().st_mtime, p.stat().st_size) for p in self.vol.iterdir()}
        import_path(self.vol, self.db)
        self.assertEqual(before, {p.name: (p.stat().st_mtime, p.stat().st_size) for p in self.vol.iterdir()})
    def test_find_volume(self):
        self.assertEqual(find_racket_volumes([self.tmp]), [self.vol])
```
- [ ] **Steps 2–4:** fail → implement → pass.
- [ ] **Step 5:** Commit: `feat: importer with dedupe, raw archive and notifications`

### Task 4: Milestones

**Files:** `babolat_play/milestones.py`, `tests/test_milestones.py`

**Produces:**
```python
@dataclass(frozen=True)
class Milestone: key: str; title: str; detail: str; value: float; stroke: Optional[str]; session_id: str; achieved_at: str  # ISO datetime
SHOT_TOTALS = (500, 1000, 2500, 5000, 10000); SESSION_COUNTS = (1, 5, 10, 25, 50, 100); STREAK_WEEKS = (3, 5, 10)
def compute_milestones(sessions: List[Session]) -> List[Milestone]   # chronological
```
Rules (walk sessions sorted by `started_at`):
- `first_session`: always emitted for session 1. Session counts give `sessions_{n}`.
- Cumulative shots crossing a threshold give `shots_{n}`.
- Speed PBs for each stroke in (serve, forehand, backhand, volley): a session max greater than the running best, from the 2nd session that has that stroke onward, gives `pb_{stroke}@{session_id}`. Its value is in km/h and the title reads like "New serve speed record".
- Most shots in a session (2nd session onward, strictly greater) gives `pb_shots@{sid}`.
- Forehand topspin % with ≥ 20 forehands, beating the running best from the 2nd qualifying session, gives `pb_topspin@{sid}`.
- Weekly streak: consecutive ISO weeks with ≥ 1 session. Reaching N for the first time gives `streak_{n}`.

- [ ] **Step 1: Failing tests** use a helper `mk(day, serve_kmh, n_fh, topspin_frac)` that builds `Session` objects in memory.
```python
import unittest
from datetime import datetime, timedelta
from babolat_play.parser import Session, Swing
from babolat_play.milestones import compute_milestones
from babolat_play.store import Store

def mk(day, serve=100, n_fh=20, top=0.5, sid=None):
    sw = [Swing(i, i * 10, "forehand", "topspin" if i < n_fh * top else "flat", 6, 40.0, False, "") for i in range(n_fh)]
    sw.append(Swing(n_fh, n_fh * 10, "serve", "flat", 6, float(serve), False, ""))
    return Session(sid or f"s{day}", datetime(2024, 1, 1) + timedelta(days=day), "t", sw)

class MilestoneTest(unittest.TestCase):
    keys = staticmethod(lambda ms: [m.key for m in ms])
    def test_first_session_no_pb(self):
        ks = self.keys(compute_milestones([mk(0)]))
        self.assertIn("first_session", ks); self.assertIn("sessions_1", ks)
        self.assertFalse(any(k.startswith("pb_") for k in ks))
    def test_serve_pb(self):
        ks = self.keys(compute_milestones([mk(0, 100), mk(7, 120), mk(14, 110)]))
        self.assertIn("pb_serve@s7", ks); self.assertNotIn("pb_serve@s14", ks)
    def test_weekly_streak(self):
        ks = self.keys(compute_milestones([mk(0), mk(7), mk(14)]))
        self.assertIn("streak_3", ks)
    def test_shot_total(self):
        ks = self.keys(compute_milestones([mk(d * 2, n_fh=100) for d in range(5)]))
        self.assertIn("shots_500", ks)
    def test_out_of_order_import_keeps_old_import_ids(self):
        db = Store(":memory:"); a, b = mk(7, 120), mk(14, 130)
        for s in (a, b): db.upsert_session(s)
        i1 = db.begin_import(); db.sync_milestones(compute_milestones(db.sessions()), i1)
        db.upsert_session(mk(0, 90))   # older session arrives later
        i2 = db.begin_import(); added = db.sync_milestones(compute_milestones(db.sessions()), i2)
        old = {m["key"]: m["import_id"] for m in db.milestones()}
        self.assertEqual(old["pb_serve@s14"], i1)
        self.assertNotIn("first_session", [m.key for m in added])
```
- [ ] **Steps 2–4:** fail → implement → pass (`python3 -m unittest discover -s tests -v`).
- [ ] **Step 5:** Commit: `feat: milestone engine`

### Task 5: Site builder and server

**Files:** `babolat_play/site.py`, `server.py`, `tests/test_site.py`

**Produces:**
```python
def build_payload(store: Store, demo_label: Optional[str] = None) -> dict
def build_site(store: Store, out_dir: Path, demo_label: Optional[str] = None) -> Path
def serve(site_dir: Path, host: str = "0.0.0.0", port: int = 8765) -> None
```
**Data contract (`data.js` → `window.PLAY_DATA`):**
```json
{"version":1,"generated_at":"ISO","demo":null|"label","latest_import_id":3,
 "sessions":[{"id":"…","started_at":"ISO","source":"LOG000.BIN","duration_s":3568,
   "swings":[[t,"forehand","topspin",45.1,0], …]}],
 "milestones":[{"key":"…","title":"…","detail":"…","value":133,"stroke":"serve","session_id":"…","achieved_at":"ISO","is_new":true}]}
```
`duration_s` is the max `t` of non-glitch swings. `is_new` is `import_id == latest_import_id`.

`build_site` copies `babolat_play/app/*` and writes `data.js` into `out_dir.with_name(out_dir.name + ".tmp")`. It then renames any existing `out_dir` to `.old`, renames `.tmp` to `out_dir` and removes `.old`. On any exception it removes `.tmp` and re-raises, leaving `out_dir` untouched.

`serve` uses `ThreadingHTTPServer` with `SimpleHTTPRequestHandler(directory=str(site_dir))`, adds `Cache-Control: no-cache` and suppresses access logs.

- [ ] **Step 1: Failing tests**
```python
import json, tempfile, shutil, unittest
from pathlib import Path
from unittest import mock
from babolat_play import site
from babolat_play.store import Store
from babolat_play.parser import parse_log
FIX = Path(__file__).parent / "fixtures"

class SiteTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()); self.db = Store(":memory:")
        self.db.upsert_session(parse_log((FIX / "LOG000.BIN").read_bytes())[0])
    def tearDown(self): shutil.rmtree(self.tmp)
    def test_payload(self):
        p = site.build_payload(self.db)
        self.assertEqual(len(p["sessions"][0]["swings"]), 151)
        self.assertEqual(p["sessions"][0]["duration_s"], 3568)
    def test_build_writes_app_and_data(self):
        out = site.build_site(self.db, self.tmp / "site")
        self.assertTrue((out / "index.html").exists())
        js = (out / "data.js").read_text()
        self.assertTrue(js.startswith("window.PLAY_DATA="))
        json.loads(js[len("window.PLAY_DATA="):].rstrip(";\n"))
    def test_failed_build_keeps_previous_site(self):
        out = site.build_site(self.db, self.tmp / "site")
        with mock.patch.object(site, "_write_data", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError): site.build_site(self.db, out)
        self.assertTrue((out / "data.js").exists()); self.assertFalse((self.tmp / "site.tmp").exists())
```
- [ ] **Steps 2–4:** fail → implement (the `app/` dir only needs a stub `index.html` at this point) → pass.
- [ ] **Step 5:** Commit: `feat: atomic static site builder and LAN server`

### Task 6: CLI, demo data and launchd agents

**Files:** `babolat_play/cli.py`, `demo.py`, `agent.py`

**Commands** (`python3 -m babolat_play <cmd>`):
- **`import [--path P] [--auto] [--min-swings 10]`:** finds volumes (or uses `--path`), imports from each, then `begin_import` → `sync_milestones` → `finish_import` → `build_site(site_dir())`. It prints a summary. With `--auto` it prints nothing when no racket is present, and on success it calls `notify("Babolat Play", "2 new sessions · 🏆 New serve speed record")`, naming milestones only when some were added. A `PermissionError` on the volume calls `notify` with "Grant Python access to removable volumes; see README" and exits 1.
- **`build`:** rebuilds the site from the DB.
- **`serve [--port 8765] [--host 0.0.0.0]`:** prints `http://<hostname>.local:<port>` and the LAN IP.
- **`install [--no-serve]`:** writes plists to `~/Library/LaunchAgents/`.
  - `com.babolatplay.import`: `ProgramArguments=[sys.executable,"-m","babolat_play","import","--auto"]`, `StartOnMount=true`, `RunAtLoad=false`.
  - `com.babolatplay.serve`: `serve`, `RunAtLoad=true`, `KeepAlive=true`.

  Both get `EnvironmentVariables={"PYTHONPATH": <repo root>}` and log to `~/.babolat-play/agent.log`. Loads them with `launchctl bootstrap gui/<uid> <plist>`, falling back to `launchctl load -w`, then runs one import immediately.
- **`uninstall`:** `launchctl bootout` and removes both plists.
- **`demo [--out site-demo]`:** uses `Store(":memory:")`, loads `fixtures/LOG000_2022-08-29.BIN` (import 1), then `demo.synthetic_sessions(seed=7)` (11 sessions starting 2022-09-03, about weekly, with drifting improvement; the last 3 come as import 2 so the "new" banner shows). Builds with `demo_label="Demo data · synthetic except 2022-08-29"`.
- **`status`:** session count, last import time, site dir, URL, agent installed yes or no.

`demo.synthetic_sessions(seed) -> List[Session]` uses `random.Random(seed)`, 90–200 swings per session, stroke mix about 35/27/27/11, speeds Gaussian around the real session's means with a +1.5%/session trend, spin probabilities from the real session, `source="synthetic"` and an id of `syn-{n}`.

- [ ] **Step 1:** Implement, then smoke-test:
```bash
python3 -m babolat_play demo --out /tmp/x && ls /tmp/x
BABOLAT_PLAY_HOME=$(mktemp -d) python3 -m babolat_play import --path tests/fixtures   # expect "1 new session"
BABOLAT_PLAY_HOME=<same> python3 -m babolat_play import --path tests/fixtures          # expect "0 new"
```
- [ ] **Step 2:** `python3 -m unittest discover -s tests` passes. Commit: `feat: cli, demo data, launchd agents`

### Task 7: Dashboard PWA

**Files:** `babolat_play/app/{index.html, styles.css, app.js, charts.js, share.js, sw.js, manifest.webmanifest, icon.svg, icon-192.png, icon-512.png}`

**Spec for the implementer** (follow the dataviz skill; palette already validated):
- **Tokens:** light and dark on `:root`, plus `[data-theme]` overrides. Series colors: forehand `#2a78d6` / `#3987e5`, backhand `#eb6834` / `#d95926`, serve `#1baf7a` / `#199e70`, volley `#eda100` / `#c98500`. Chrome uses the `references/palette.md` ink, grid and surface values. Font is `system-ui`.
- **Layout:** mobile-first, single column under 720 px, with a fixed bottom tab bar (Overview, Trends, Sessions, Milestones) that respects `env(safe-area-inset-bottom)`. At 720 px and up, tabs move to the top and grids use 2–4 columns. Max width 1100 px with a 16 px gutter.
- **Header:** title, a demo badge if `demo` is set, an mph/km/h segmented toggle and a theme toggle. Both toggles are saved in `localStorage` inside try/catch.
- **Overview:**
  - a new-milestones banner (if any `is_new`, dismissible per import ID) with share buttons
  - 4 KPI tiles: sessions, total shots, top serve, top forehand. Each shows its delta vs the previous period, meaning the last 5 sessions vs the 5 before.
  - a latest-session card with a mini stroke mix
  - an "inferred data" footnote linking to the FILE_FORMAT doc on GitHub
- **Trends:**
  - a period filter row (Last 5 · Last 10 · All)
  - charts:
    - avg and max speed lines per session for serve, forehand and backhand: 3 small charts, each one stroke with an avg line plus a lighter dashed max line
    - shot mix stacked bars per session
    - forehand topspin % and backhand slice % lines as small multiples
    - shots per session bars

  Each chart has a crosshair or tap tooltip and a "Show table" toggle. Charts re-render on resize via `ResizeObserver`.
- **Sessions:** a reverse-chronological list (date, duration, shots, top speed, a mini stacked bar). Tapping one opens a detail sheet with per-stroke cards (count, avg and max speed, spin split), a 5-minute timeline and a swing table.
- **Milestones:** a timeline grouped by month. Each item has an icon (🏆 PB, 🎯 totals, 🔥 streak, 🎾 sessions), title, detail, date and a Share button.
- **share.js:** draws a 1080×1080 canvas card (gradient in the stroke color, big value with unit, title, date, a "Babolat Play Dashboard" footer) and builds a File. If `navigator.canShare({files})` it calls `navigator.share`, otherwise it downloads the PNG.
- **charts.js exports:** `lineChart(el, {series:[{label,color,dashed,points:[{x:Date,y:number}]}], unit})`, `stackedBars(el, {categories:[label], series:[{key,label,color,values:[]}]})`, `bars(el, {...})`. They draw SVG with recessive grid, 2 px lines, ≥ 8 px markers, 4 px rounded bar tops, 2 px surface gaps, a legend for 2 or more series, and direct end labels.
- **sw.js:** cache-first for app shell files, network-first for `data.js`. The manifest declares `display: standalone`, theme colors and the icons. `index.html` includes an `apple-touch-icon` and `<meta name="apple-mobile-web-app-capable">`.
- **Icons:** `icon.svg` (a tennis ball with a sensor arc). Render PNGs at 192 and 512 with headless Chrome screenshots.

- [ ] **Step 1:** Implement.
- [ ] **Step 2:** `python3 -m babolat_play demo --out site-demo`, then take headless-Chrome screenshots at 390×844 (each tab, light and dark) and 1280×900. Inspect for overflow, label collisions and wrong numbers. The real session must show 52 / 39 / 43 / 17.
- [ ] **Step 3:** `node --check` each JS file. Commit: `feat: mobile-first PWA dashboard`

### Task 8: Docs, diagrams and screenshots

**Files:** `README.md`, `docs/ARCHITECTURE.md`, `docs/FILE_FORMAT.md`, `CONTRIBUTING.md`, `LICENSE` (MIT, 2026, Saurabh Gupta), `docs/img/*.png`
- **README:**
  - hero screenshot (phone and desktop) and a "why"
  - features
  - quick start: `git clone …` → `python3 -m babolat_play install` → open `http://<mac>.local:8765` on the phone and Add to Home Screen
  - manual use on other OSes
  - demo command
  - "How it works" Mermaid flowchart
  - privacy (all local, LAN-only, read-only racket)
  - troubleshooting (macOS removable-volume permission for python3, port in use, `.local` name resolution)
  - accuracy disclaimer and a trademark disclaimer (not affiliated with Babolat)
- **ARCHITECTURE.md:** Mermaid component diagram, import sequence diagram (mount → launchd → importer → store → milestones → site → notification), ER diagram of the SQLite tables, and the dedupe rules.
- **FILE_FORMAT.md:** byte tables for the header, start record and swing record, each field marked ✅ verified / 🟡 inferred / ❓ unknown, the evidence for each, and the calibration protocol.
- **CONTRIBUTING.md:** how to contribute a labelled session, run the tests and the code style.
- [ ] Commit: `docs: readme, architecture, file format`

### Task 9: Install locally, verify end-to-end, publish
- [ ] Run `python3 -m unittest discover -s tests -v` and expect everything to pass.
- [ ] `python3 -m babolat_play install`, then confirm the agents with `launchctl list | grep babolatplay`, run `import --auto` against the mounted racket, `curl -s localhost:8765/ | head`, and confirm `status`.
- [ ] `gh repo create sgupta382/babolat-play-dashboard --public --source . --description "…" --push`. Verify with `gh repo view --web` (print the URL only).
