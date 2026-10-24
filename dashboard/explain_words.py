"""Turn a service's numbers into short, plain-language sentences (never raw anomaly scores).

The constants below are DISPLAY thresholds only: they decide what is worth mentioning in a
sentence. They do not feed back into anomaly detection, which lives elsewhere in the system.
"""
import math

from charts_labels import ct

SLOW_LAT_RATIO = 1.5       # mention latency at or above 1.5 times normal
ERROR_SHARE = 0.01         # mention errors at or above 1% of requests
HIGH_MEM_SHARE = 0.60      # mention memory at or above 60% of the limit
RISING_MEM_SLOPE = 0.01    # also say "rising" when growth is at least 1% of the limit per minute
HIGH_TRAFFIC_RATIO = 2.0   # mention traffic at or above 2 times normal


def _num(features: dict, key: str):
    v = features.get(key)
    if v is None:
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(v) or math.isinf(v):
        return None
    return v


def explain_service(name: str, features: dict | None, lang: str = "en") -> list[str]:
    features = features or {}
    sentences: list[str] = []

    up_frac = _num(features, "up_frac")
    if up_frac is not None and up_frac == 0:
        sentences.append(ct("not_answering", lang).format(s=name))

    lat_ratio = _num(features, "lat_ratio")
    if lat_ratio is not None and lat_ratio >= SLOW_LAT_RATIO:
        sentences.append(ct("slow", lang).format(s=name, x=lat_ratio))

    error_ratio = _num(features, "error_ratio")
    if error_ratio is not None and error_ratio >= ERROR_SHARE:
        sentences.append(ct("errors", lang).format(s=name, p=error_ratio * 100))

    mem_share = _num(features, "mem_share")
    if mem_share is not None and mem_share >= HIGH_MEM_SHARE:
        sentence = ct("mem", lang).format(s=name, p=mem_share * 100)
        slope = _num(features, "mem_slope_share_per_min")
        if slope is not None and slope >= RISING_MEM_SLOPE:
            sentence += ct("mem_rising_suffix", lang).format(q=slope * 100)
        sentences.append(sentence)

    rps_ratio = _num(features, "rps_ratio")
    if rps_ratio is not None and rps_ratio >= HIGH_TRAFFIC_RATIO:
        sentences.append(ct("traffic", lang).format(s=name, x=rps_ratio))

    restarts = _num(features, "restarts_in_window")
    if restarts is not None and restarts > 0:
        sentences.append(ct("restarted", lang).format(s=name))

    deploys = _num(features, "deploys_3m")
    if deploys is not None and deploys > 0:
        sentences.append(ct("deployed", lang).format(s=name))

    return sentences
