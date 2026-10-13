# Babolat Play log format (reverse-engineered)

Babolat never published this format. Everything below was worked out from real logs, and each field is marked:

✅ verified · 🟡 inferred (consistent with the data, not confirmed against known shots) · ❓ unknown

All decoding lives in [`babolat_play/parser.py`](../babolat_play/parser.py). The mapping tables `STROKES` and `SPINS` are the single place to fix when an inference turns out wrong.

## The racket as a USB drive

When connected, the racket mounts as a small FAT volume (about 4 MB) named `BABOLAT`:

| File | Meaning |
|---|---|
| `LOG000.BIN`, `LOG001.BIN`, … | Swing logs ✅ |
| `USERPAR.INF` | 74 bytes of user/racket parameters. It starts with the same `55 02` magic as the logs and shares the bytes `92 79` with the log header. ❓ |
| `PLAY.URL` | Windows shortcut to the defunct `babolatplay.com/first` |
| `System Volume Information/` | Created by Windows, not the racket |

## Log layout ✅

```
[ 50-byte header ][ 13-byte record ][ 13-byte record ] …
```

Every log seen so far has a length of exactly `50 + 13·n` bytes.

### Header (50 bytes) ❓

The same in both known logs:

```
55 02 00 00 48 0d 00 20 5e 00 00 00 6f 00 00 00 70 7f 00 20 00 00 00 00
39 51 40 00 00 00 00 00 00 00 00 00 01 00 00 00 76 7f 00 20 06 00 00 92 79 00
```

Several 32-bit little-endian words (`0x20000d48`, `0x20007f70`, `0x20007f76`) look like ARM Cortex-M SRAM addresses, so the header may be a firmware struct dumped as-is. `92 79` also appears in `USERPAR.INF`, so it might be a device or user ID. The parser hashes the header into the session ID and otherwise ignores it.

### Record type 0: session start ✅

| Byte | Meaning | Example (LOG000) |
|---|---|---|
| 0 | `0x00` marks a session start | `00` |
| 1, 2, 3 | Hour, minute, second (racket clock, local time) | `13 11 21` = 19:17:33 |
| 4, 5, 6 | Day, month, year − 2000 | `1d 08 16` = 29 Aug 2022 |
| 7–12 | ❓ | `48 10 97 00 40 00` |

**Evidence:** both logs decode to dates that match their file modification dates (2022-08-29 and 2012-09-01), and the times are plausible.

### Swing record

| Byte(s) | Meaning | Status | Notes |
|---|---|---|---|
| 0 | Stroke code | 🟡 | `3` forehand, `4` backhand, `2` serve, `8`/`9` volley. In LOG000: 52 / 39 / 43 / 6+11. |
| 1 | "Zone" code, values 2–9 | ❓ | Mostly `6`. Possibly impact location or swing family. |
| 2 | Spin class | 🟡 | `0` flat, `1` topspin, `2` slice |
| 3 | ❓ | ❓ | Ranges 2–99 |
| 4 | Racket speed | 🟡 | Read as **mph**. Ordering: serve > forehand > backhand > volley. |
| 5 | Serve ball speed | 🟡 | Non-zero **only for serves**, 87–133, read as **km/h** |
| 6 | ❓ | ❓ | Zero in all records seen |
| 7–8 | ❓ | ❓ | Look like a signed pair, maybe impact x/y or a rotation |
| 9–10 | ❓ | ❓ | Zero in all records seen |
| 11–12 | Seconds since session start, uint16 LE | ✅ | Increases monotonically, ending at about 59 min |

**Evidence and reasoning:**

- **Stroke.** Code 2 is the only code carrying a byte-5 value, and that value sits in a typical club-level serve range. Codes 3 and 4 dominate the counts, as groundstrokes do. Codes 8 and 9 are rare and slow.
- **Spin.** With 0/1/2 read as flat/topspin/slice:
  - forehands are 54% topspin
  - backhands are 72% slice
  - serves are 74% flat
  - volleys are 65% slice and 0% topspin

  That pattern fits a typical player well.
- **Speed unit.** Reading byte 4 as m/s would give forehands of about 200 km/h, which is impossible. Read as mph, the serve racket speed (about 36) against the ball speed (about 66 mph) gives a plausible ratio.
- **Clock glitch.** The final record in LOG000 jumps about 3 hours. Gaps over 30 minutes are flagged `glitch` and kept off timelines.

Several sessions can follow each other in one file. Each type-0 record starts a new one.

## Help confirm the format: calibration protocol

This is the fastest way to turn 🟡 into ✅:

1. Charge the racket and import once, so the next session is the only new one.
2. Play a **labelled** session and write down the order:
   - 10 flat serves, then 10 kick or slice serves
   - 10 topspin forehands, then 10 slice forehands
   - 10 topspin backhands, then 10 slice backhands
   - 10 volleys, then 5 overheads
   - a few deliberately off-centre hits
3. If you can, measure serve speed with a radar app and note a few readings.
4. Copy the new `LOG*.BIN` and share it together with your notes; [CONTRIBUTING.md](../CONTRIBUTING.md) explains how.
