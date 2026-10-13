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
| 7–8 | Session length in seconds, uint16 LE | `48 10` = 4168 s |
| 9–10 | Number of records that follow (swings and markers), uint16 LE | `97 00` = 151 |
| 11 | ❓ | `40` |
| 12 | ❓ (zero so far) | `00` |

**Evidence:** every log decodes to a date that matches its file modification date, and the times are plausible. Bytes 7–8 and 9–10 hold in all 9 logs seen so far: the length is always a few seconds past the last swing, and the count matches the records exactly.

### Record type 10: marker ✅

`0a 01 03 00 61 00 00 00 00 00 00 tt tt` turns up right after a session start, mid-session after a pause, and on its own in empty sessions. It's a device event (perhaps wake-up, or battery at 97%), not a swing, and the parser skips it.

### Swing record

| Byte(s) | Meaning | Status | Notes |
|---|---|---|---|
| 0 | Stroke code | ✅ `3`/`4`, 🟡 others | `3` forehand side, `4` backhand side (volleys included), `2` serve, `8`/`9` volley. See *Volleys* below. |
| 1 | "Zone" code, values 2–9 | ❓ | Mostly `6`. Possibly impact location or swing family. |
| 2 | Spin class | 🟡 | `0` flat, `1` topspin, `2` slice |
| 3 | Spin amount? | 🟡 | Ranges 0–99. Flat shots mostly under 35, topspin and slice mostly 40–90. |
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
- **Clock glitch.** The final record of every log has a nonsense timestamp (for example 65289 s). Gaps over 30 minutes are flagged `glitch` and kept off timelines.

### Volleys (calibrated 2026-10-13)

Five labelled sessions, recorded after a clock reset:

| Log | What was played | Codes 3 / 4 / 8+9 | Byte 4 median |
|---|---|---|---|
| LOG003 | Forehand drill, baseline | 19 / 1 / 0 | 36 |
| LOG005 | Backhand drill, baseline | 3 / 21 / 0 | 41 |
| LOG002 | Warm-up rally at the service line | 34 / 20 / 3 | 12–19 |
| LOG007 | "Mostly volleys" | 44 / 25 / 25 | 9–14 after a pause marker at 5:47, 35–38 before |
| LOG008 | Volleys at the net | 16 / 20 / 19 | 9–12 |

- **Codes 3 and 4 are the side of the body, not the shot type.** The two drills confirm 3 = forehand and 4 = backhand. In the volley sessions, about two in three volleys still carry 3 or 4.
- **The parser therefore calls a 3 or 4 a volley when byte 4 is under 20 mph and the spin isn't topspin** (`VOLLEY_MAX_MPH`). On the labelled data this catches 70 of 72 net volleys, flags no shot from the baseline drills, and flags 19 of 54 shots from the service-line warm-up (slow, flat or slice pushes, which look like volleys to the sensor).
- **LOG007 opens with 33 shots at groundstroke speed, mostly topspin,** before the pause marker. They decode as groundstrokes. The player remembered the session as all volleys, so this part is unconfirmed.
- **Codes 8 and 9 are still read as volleys.** In these sessions they were all slow and flat or slice. Byte 7 for them is about +50, close to serves (+63), while forehands and backhands are 0 or below. That hints at a racket-head-up swing, such as a high volley or an overhead. A session with overheads would settle it.
- **No serves were recorded,** so the serve findings are unchanged.

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
