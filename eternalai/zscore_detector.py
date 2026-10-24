"""Per-signal z-score detector (plan §6.3, §9.1), as a standalone, reusable module.

Rule, for one signal (one key) at a time:

    z = (value - mean_normal) / max(std_normal, floor)
    hot       = z beyond the limit (3.0) in the configured direction AND the absolute gap beyond min_gap
    anomalous = hot for STREAK_NEEDED (3) checks in a row

- The first WARMUP_POINTS (15) values only fill the baseline; they are never anomalous.
- The baseline is the last BASELINE_WINDOW (120) values that were NOT hot, so a problem never becomes the new normal.
- None / NaN / inf values change no state at all.
- Deterministic: the same inputs give the same outputs.

With direction "upper" and the per-metric floor/min_gap of eternalai.baselines.ZSCORE_METRICS, the results equal the
benchmark port eternalai.baselines.ZScoreDetector (tests/test_zscore_detector.py checks this).

Only the standard library and numpy are imported. Not wired into the live engine (see docs/handback/rajat.md).
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from typing import Any, Hashable, Mapping

import numpy as np

Z_LIMIT = 3.0
STREAK_NEEDED = 3
WARMUP_POINTS = 15
BASELINE_WINDOW = 120
DIRECTIONS = ("upper", "lower", "two_sided")


@dataclass(frozen=True)
class SignalConfig:
    """floor: minimum standard deviation; min_gap: minimum absolute gap from the mean; direction: which side alarms."""
    floor: float
    min_gap: float
    direction: str = "upper"

    def __post_init__(self):
        if self.direction not in DIRECTIONS:
            raise ValueError(f"direction must be one of {DIRECTIONS}, got {self.direction!r}")
        if not (self.floor > 0 and math.isfinite(self.floor)):
            raise ValueError(f"floor must be a positive finite number, got {self.floor!r}")
        if not (self.min_gap >= 0 and math.isfinite(self.min_gap)):
            raise ValueError(f"min_gap must be a non-negative finite number, got {self.min_gap!r}")


@dataclass(frozen=True)
class ZResult:
    z: float                 # 0.0 during warm-up or for a missing value (as in the port)
    hot: bool                # beyond the limit and the gap on this check
    anomalous: bool          # hot for streak_needed checks in a row
    mean: float | None       # baseline mean; None during warm-up or for a missing value
    std: float | None        # baseline std after the floor; None during warm-up or for a missing value
    n_baseline: int          # values in the baseline after this update


def _missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        return not math.isfinite(float(value))
    except (TypeError, ValueError):
        return True


class ZScoreDetector:
    """State per key. `configs` maps a key, or a metric name (the last element of a tuple key), to a SignalConfig."""

    def __init__(self, configs: Mapping[Hashable, SignalConfig] | None = None, default: SignalConfig | None = None,
                 *, z_limit: float = Z_LIMIT, streak_needed: int = STREAK_NEEDED, warmup: int = WARMUP_POINTS,
                 window: int = BASELINE_WINDOW):
        if warmup < 2 or window < warmup or streak_needed < 1 or z_limit <= 0:
            raise ValueError("need warmup >= 2, window >= warmup, streak_needed >= 1, z_limit > 0")
        self.configs = dict(configs or {})
        self.default = default
        self.z_limit, self.streak_needed, self.warmup, self.window = float(z_limit), int(streak_needed), int(warmup), int(window)
        self._base: dict[Hashable, deque] = {}
        self._streak: dict[Hashable, int] = {}
        self._last: dict[Hashable, dict] = {}

    def config_for(self, key: Hashable) -> SignalConfig:
        if key in self.configs:
            return self.configs[key]
        if isinstance(key, tuple) and key and key[-1] in self.configs:
            return self.configs[key[-1]]
        if self.default is not None:
            return self.default
        raise KeyError(f"no SignalConfig for key {key!r}")

    def update(self, key: Hashable, value: float | None, t: Any = None) -> ZResult:
        cfg = self.config_for(key)
        base = self._base.get(key)
        n = len(base) if base is not None else 0
        if _missing(value):                                # no state change at all
            return ZResult(0.0, False, False, None, None, n)
        value = float(value)
        if base is None:
            base = self._base[key] = deque(maxlen=self.window)
        if len(base) < self.warmup:
            base.append(value)
            self._last[key] = {"t": t, "value": value, "z": 0.0, "mean": None, "std": None, "hot": False,
                               "anomalous": False}
            return ZResult(0.0, False, False, None, None, len(base))
        arr = np.array(base)
        mean = float(arr.mean())
        std = max(float(arr.std()), cfg.floor)
        z = (value - mean) / std
        gap = value - mean
        if cfg.direction == "upper":
            hot = z > self.z_limit and gap > cfg.min_gap
        elif cfg.direction == "lower":
            hot = z < -self.z_limit and -gap > cfg.min_gap
        else:
            hot = abs(z) > self.z_limit and abs(gap) > cfg.min_gap
        hot = bool(hot)
        streak = self._streak.get(key, 0) + 1 if hot else 0
        self._streak[key] = streak
        if not hot:                                        # learn "normal" only from values that looked normal
            base.append(value)
        anomalous = streak >= self.streak_needed
        self._last[key] = {"t": t, "value": value, "z": z, "mean": mean, "std": std, "hot": hot, "anomalous": anomalous}
        return ZResult(z, hot, anomalous, mean, std, len(base))

    def explain(self, key: Hashable) -> dict | None:
        """Data for a later plain-words layer (no user text, no raw anomaly score). None if the key has no value yet."""
        last = self._last.get(key)
        if last is None:
            return None
        cfg = self.config_for(key)
        side = None
        if last["mean"] is not None:
            side = "above" if last["value"] > last["mean"] else "below" if last["value"] < last["mean"] else "at"
        return {"key": key, "t": last["t"], "value": last["value"], "z": last["z"], "mean": last["mean"],
                "std": last["std"], "direction": cfg.direction, "side": side, "hot": last["hot"],
                "anomalous": last["anomalous"], "warming_up": last["mean"] is None,
                "n_baseline": len(self._base.get(key, ()))}

    def reset(self, key: Hashable | None = None) -> None:
        """Forget one key (or every key)."""
        if key is None:
            self._base.clear(); self._streak.clear(); self._last.clear()
        else:
            self._base.pop(key, None); self._streak.pop(key, None); self._last.pop(key, None)
