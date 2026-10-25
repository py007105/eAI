"""Saving and loading model artifacts together with the metadata that explains them.

Every artifact stores: what it was trained on, the feature list, the git commit and a UTC
timestamp. The live system loads these files; nothing is retrained or hardcoded at runtime.
"""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import joblib

ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "ml" / "models" / "artifacts"


def git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                              cwd=Path(__file__).parent, timeout=5).stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def save(name: str, obj, *, training_data: str, features: list[str], extra: dict | None = None) -> Path:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    path = ARTIFACT_DIR / f"{name}.joblib"
    joblib.dump(obj, path)
    meta = {"name": name, "training_data": training_data, "features": features, "git_commit": git_commit(),
            "trained_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **(extra or {})}
    path.with_suffix(".json").write_text(json.dumps(meta, indent=2))
    return path


# The frozen artifacts were pickled while the package was still called `eternalai` (renamed to `engine` on 25 Oct 2026).
# Their pickles name these old modules. Pointing the old names at the same module objects lets them load unchanged,
# so the frozen files and their recorded hashes stay exactly as trained. tests/test_artifacts_load.py loads every file.
_LEGACY_SUBMODULES = ("calibrate", "classify", "detect", "novelty", "rca", "safe_model")


def _alias_legacy_package() -> None:
    import importlib
    import sys
    pkg = __package__ or "engine"
    sys.modules.setdefault("eternalai", importlib.import_module(pkg))
    for sub in _LEGACY_SUBMODULES:
        sys.modules.setdefault(f"eternalai.{sub}", importlib.import_module(f"{pkg}.{sub}"))


def load(name: str):
    """Return (object, metadata) or (None, None) if the artifact has not been trained yet."""
    path = ARTIFACT_DIR / f"{name}.joblib"
    if not path.exists():
        return None, None
    _alias_legacy_package()
    return joblib.load(path), json.loads(path.with_suffix(".json").read_text())
