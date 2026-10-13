# Contributing

Thanks for helping keep Babolat Play rackets useful. Two kinds of contribution help most.

## 1. Labelled sessions (no coding needed)

Stroke type, spin and speed are still **inferred** (see [docs/FILE_FORMAT.md](docs/FILE_FORMAT.md)). A session where you know exactly what you hit is the best way to confirm them or correct them.

1. Follow the [calibration protocol](docs/FILE_FORMAT.md#help-confirm-the-format-calibration-protocol).
2. Open an issue titled **"Labelled session: <racket model>"**.
3. Attach the new `LOG*.BIN` (from the racket, or from `~/.babolat-play/raw/`) and your notes on what you hit and in what order.

Logs contain only swing data and the racket clock, no personal details. Still, only share what you're comfortable making public.

## 2. Code

```bash
git clone https://github.com/sgupta382/babolat-play-dashboard.git
cd babolat-play-dashboard
python3 -m unittest discover -s tests -v
python3 -m babolat_play demo && open site-demo/index.html
```

Ground rules:

- **Standard library only.** It has to run on a stock macOS `python3` (3.9) with nothing to install.
- **Never write to the racket.** The importer opens files read-only, and a test guards this.
- **Format changes go in `parser.py`** (`STROKES`, `SPINS`, `_speed_kmh`), each with a test using a real fixture. Update `docs/FILE_FORMAT.md` with the evidence.
- **Dashboard:** plain HTML, CSS and JS, with no build step and no CDN. Keep charts accessible: every chart has a table view, colors are never the only cue, and light and dark mode both work. Re-run `tools/screenshots.sh` and look at the result at phone width.
- Write the test first, keep pull requests focused, and describe what you checked.

## Ideas welcome

- Overhead detection, and decoding the "zone" byte (impact location?)
- Linux and Windows auto-import (udev rule, Task Scheduler)
- Export to CSV
