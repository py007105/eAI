import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("ml_", Path(__file__).resolve().parents[1] / "tools" / "migrate_layout.py")
ml = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ml)


def test_imports_and_module_paths():
    src = "from eternalai.engine import Engine\nimport eternalai.llm as llm\nmock.patch('eternalai.collector.x')\n"
    out = ml.rewrite("tests/test_x.py", src)
    assert out == "from engine.engine import Engine\nimport engine.llm as llm\nmock.patch('engine.collector.x')\n"


def test_database_file_name_is_kept():
    assert ml.rewrite("engine/store.py", 'DB = "eternalai.db"') == 'DB = "eternalai.db"'


def test_paths_and_joins():
    src = 'ROOT / "scripts" / "kind_e2e.py"\nROOT / "models" / "artifacts"\nMAIN / "scripts" / "memguard.py"\n'
    out = ml.rewrite("tools/x.py", src)
    assert 'ROOT / "tools" / "kind_e2e.py"' in out
    assert 'ROOT / "ml" / "models" / "artifacts"' in out
    assert 'MAIN / "scripts" / "memguard.py"' in out  # another checkout keeps the old layout
    assert ml.rewrite("tools/x.py", 'repo / "models"') == 'repo / "models"'
    assert ml.rewrite("x.yml", "context: ./app/web\n") == "context: ./services/shop/web\n"
    assert ml.rewrite("x.ps1", r"python scripts\kind_e2e.py") == r"python tools\kind_e2e.py"


def test_markdown_only_real_paths_and_ml_depth():
    md = "Run `python scripts/kind_e2e.py`; the web app/API stays; see eternalai/drivers/k8s.py."
    assert ml.rewrite("docs/x.md", md) == "Run `python tools/kind_e2e.py`; the web app/API stays; see engine/drivers/k8s.py."
    assert "parents[2]" in ml.rewrite("ml/models/x.py", "R = Path(__file__).resolve().parents[1]")
    assert "parents[1]" in ml.rewrite("tools/x.py", "R = Path(__file__).resolve().parents[1]")
