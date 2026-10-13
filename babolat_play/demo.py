"""Demo data: the real 2022-08-29 session plus clearly-labelled synthetic ones,
so a fresh clone shows working trend charts."""
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

from .parser import Session, Swing

FIXTURE_DIR = Path(__file__).parent / "fixtures"
LABEL = "Demo data · synthetic except 2022-08-29"

# Shaped on the real session: stroke mix, mean speed (km/h), spread, spin odds.
PROFILE = {
    "forehand": (0.35, 45.0, 14.0, {"topspin": 0.54, "flat": 0.38, "slice": 0.08}),
    "backhand": (0.27, 40.0, 11.0, {"slice": 0.72, "flat": 0.18, "topspin": 0.10}),
    "serve":    (0.27, 106.0, 11.0, {"flat": 0.74, "topspin": 0.21, "slice": 0.05}),
    "volley":   (0.11, 31.0, 12.0, {"slice": 0.65, "flat": 0.35}),
}
GROWTH_PER_SESSION = 0.015


def _pick(rng: random.Random, odds: dict) -> str:
    return rng.choices(list(odds), weights=list(odds.values()))[0]


def synthetic_sessions(seed: int = 7, count: int = 11) -> List[Session]:
    rng = random.Random(seed)
    day = datetime(2022, 9, 3, 18, 30)
    out = []
    for n in range(1, count + 1):
        boost = 1 + GROWTH_PER_SESSION * n
        strokes = list(PROFILE)
        mix = [PROFILE[k][0] for k in strokes]
        swings, t = [], 0
        for i in range(rng.randint(90, 200)):
            t += rng.randint(8, 30)
            stroke = rng.choices(strokes, weights=mix)[0]
            _, mean, sd, spins = PROFILE[stroke]
            speed = round(max(10.0, rng.gauss(mean * boost, sd)), 1)
            swings.append(Swing(i, t, stroke, _pick(rng, spins), 6, speed, False, ""))
        out.append(Session(f"syn-{n}", day + timedelta(minutes=rng.randint(-60, 60)), "synthetic", swings))
        day += timedelta(days=rng.choice((4, 6, 7, 7, 8, 9)))
    return out
