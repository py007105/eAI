"""UI pass before R5b: no 'proof' wording; plain-language status line; approval countdown, highlight and page title; evidence collapsed by default."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dashboard"))
import views  # noqa: E402
from labels import LABELS, t  # noqa: E402


def flat(node):
    out = []

    def walk(n):
        if isinstance(n, (list, tuple)):
            for x in n:
                walk(x)
        elif isinstance(n, (str, int, float)):
            out.append(str(n))
        elif n is not None:
            walk(getattr(n, "children", None))
    walk(node)
    return " ".join(out)


def test_no_proof_wording_in_any_visible_label():
    for lang, d in LABELS.items():
        for k, v in d.items():
            assert not re.search(r"\bproo?f|\bprov(e|ed|es|ing)\b", v, re.I), (lang, k, v)
            assert "प्रमाण" not in v and "सिद्ध" not in v, (lang, k)
