"""Knowledge base and outcome-ranked fix choice (plan §9.5, Package C). Data: ml/data/kb/ (built by tools/build_kb.py)."""
from .loader import KB, KBError, load_kb  # noqa: F401
from .ranking import Fix, ranked_fixes, ranked_runbooks  # noqa: F401
