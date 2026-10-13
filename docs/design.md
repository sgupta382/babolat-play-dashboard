# Babolat Play Dashboard: design spec

Date: 2026-10-13 · Status: awaiting approval

## Goal
Babolat no longer supports its Play racket app. This project gives Babolat Play owners a private, phone-friendly dashboard for their racket data. It imports every session automatically when the racket is plugged in, tracks trends in shot mix, speed and spin across sessions, and highlights new milestones in a way that can be shared.

## Decisions (from the owner)
- **Phone access:** the Mac serves a static, installable web app (PWA) on the home Wi-Fi at `http://<mac>.local:8765`.
- **Import:** automatic. A macOS launchd agent fires whenever a volume mounts. A manual `import` command works on any OS.
- **GitHub:** public repo `sgupta382/babolat-play-dashboard`. The real 2022 session ships as demo data. Personal data folders are git-ignored.
- **Never write to the racket.** It is read-only, always.

## Architecture
Python 3.9+, standard library only. The UI is a single HTML/JS/CSS app with no CDN, so it works offline.

```
racket (USB FAT volume) ──► importer ──► SQLite store ──► site builder ──► site/ (index.html, data.json, manifest, sw.js)
                              │                │                              │
                         parser (format)   milestones                  LAN server :8765 ──► phone (PWA)
```

| Unit | Responsibility |
|---|---|
| `babolat_play/parser.py` | Bytes → sessions → swings. It splits a log on session-start records (type 0), so one file can hold several sessions. |
| `babolat_play/store.py` | SQLite at `~/.babolat-play/play.db`. Tables: `sessions`, `swings`, `milestones`, `imports`. |
| `babolat_play/importer.py` | Finds the racket volume, parses every `LOG*.BIN`, upserts sessions by ID, and returns what's new. |
| `babolat_play/milestones.py` | Pure function: session history → achieved milestones, each with the date it was first reached. |
| `babolat_play/site.py` | Writes `site/data.json` and copies the app assets. |
| `babolat_play/server.py` | `http.server` serving `site/`, read-only. |
| `babolat_play/agent.py` | Installs and uninstalls the launchd agents (import-on-mount, server). |
| `babolat_play/cli.py` | `import`, `build`, `serve`, `install`, `uninstall`, `demo`, `status`. |
| `app/` | Dashboard source (`index.html`, `app.js`, `styles.css`, icons). |

**"Ignore old data":** a session's ID is the hash of its start record (date and time to the second, plus header). If the importer sees a known ID with the same swing count, it skips it. If the swing count is higher, the session gets replaced, which covers a log that grows. Sessions with fewer than 10 swings are skipped as noise, for example the 2012 factory test in `LOG001.BIN`.

**Decoded format** (documented in `docs/FILE_FORMAT.md` with a confidence level for each field). There is a 50-byte header and 13-byte records. The start record holds `hh mm ss DD MM YY` in bytes 1–6. Both logs match their file dates: 2022-08-29 19:17:33 and 2012-09-01 15:29:52. The stroke, spin and speed fields use the same assumptions as the prototype, kept in one mapping table so they are easy to correct.

## Dashboard (mobile-first PWA)
Bottom tab bar on phones, top tabs on desktop. Light and dark themes.

1. **Overview:** a new-milestone banner, KPI tiles (sessions, total shots, top serve, top forehand) with change versus the previous period, and the latest session summary.
2. **Trends:** a period filter (last 5 / 10 / all sessions, or 30 / 90 days / all time). Charts:
   - average and max speed per session, one chart each for serve, forehand and backhand (no dual axes)
   - shot mix per session as a stacked bar
   - spin percentage per session, forehand and backhand as small multiples
   - shots per session

   Every chart has a hover or tap tooltip and a table view.
3. **Sessions:** a list of sessions. Tapping one opens the per-session detail (the current prototype view).
4. **Milestones:** a timeline of achievements. Each one has a **Share** button that draws a 1080×1080 PNG card on a canvas and calls `navigator.share` (download is the fallback).

**Milestones:**
- personal bests for max serve, forehand, backhand and volley speed, and for most shots in a session
- cumulative shot totals (500, 1k, 2.5k, 5k, 10k)
- session counts (1, 5, 10, 25, 50, 100)
- weekly playing streaks (3, 5, 10 weeks)
- a new spin record (highest forehand topspin % in a session of at least 20 forehands)

"New" means achieved in the most recent import. The import also posts a macOS notification naming the new milestones.

## Demo
`python3 -m babolat_play demo` builds the site from the real 2022 session plus 11 **synthetic** sessions, so the trend charts have something to show. The UI labels the data "Demo data · synthetic except 2022-08-29". Screenshots for the README come from the demo.

## Docs and repo
- `README.md`: screenshots, quick start (3 commands), phone setup, how it works, disclaimer (not affiliated with Babolat)
- `docs/ARCHITECTURE.md`: Mermaid diagrams for components, import flow and data model
- `docs/FILE_FORMAT.md`
- `CONTRIBUTING.md`: how to help decode the format with a labelled session
- MIT `LICENSE`, `.gitignore`

## Error handling
- Racket not mounted: a quiet no-op when run by the agent.
- Malformed log: skip that file, log it, keep going.
- A failed build never deletes the previous site. It writes to a temp folder and swaps it in.
- The server binds to the LAN only. It serves static files with no write endpoints.

## Testing
`unittest`, standard library:
- parser: fixtures from both real logs, splitting multi-session files
- dedupe and upsert
- milestone rules on synthetic histories

Then a headless-Chrome render of the demo at phone (390 px) and desktop widths, checked by eye.

## Out of scope
Windows and Linux auto-import (the manual command works there), cloud sync, Bluetooth, and confirmed byte meanings, which need a labelled calibration session.
