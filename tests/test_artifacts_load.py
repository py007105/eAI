"""Every frozen artifact must load in a fresh interpreter (the brain loads them at startup). The Python suite passed
while the brain could not start after the package rename, because nothing loaded the real files."""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "ml" / "models" / "artifacts"
NAMES = sorted(p.stem for p in ART.glob("*.joblib"))


def test_artifacts_exist():
    assert {"classifier", "detectors", "ranker", "baselines"} <= set(NAMES)


@pytest.mark.parametrize("name", NAMES)
def test_artifact_loads_in_fresh_interpreter_and_uses_engine_classes(name):
    code = (
        f"import sys; sys.path.insert(0, {str(ROOT)!r})\n"
        "import engine.artifacts as a\n"
        f"obj, meta = a.load({name!r})\n"
        "assert obj is not None and meta\n"
        "mods = {type(obj).__module__.split('.')[0]}\n"
        "if isinstance(obj, dict):\n"
        "    mods |= {type(v).__module__.split('.')[0] for v in obj.values()}\n"
        "assert 'eternalai' not in mods, mods\n"
        "import engine.classify, engine.detect\n"
        "assert sys.modules['eternalai.classify'] is engine.classify and sys.modules['eternalai.detect'] is engine.detect\n"
        "print('ok')\n"
    )
    r = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0 and "ok" in r.stdout, r.stderr[-600:]
