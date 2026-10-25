"""Update a branch written for the old folder layout to the new one (see docs/STRUCTURE.md).

After merging `main` into a branch that was started before the restructure, git already places new files in the new
folders (eternalai/ -> engine/, scripts/ -> tools/ ...), but their contents still use the old names. This rewrites only
the files that differ from the given base, so nothing else is touched.

    python tools/migrate_layout.py --base origin/main          # show what would change
    python tools/migrate_layout.py --base origin/main --write  # rewrite, then run the tests and commit

Never rewrite recorded evidence or pre-registered plans; they are skipped (docs/STRUCTURE.md lists them).
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

MOVES = [("eternalai", "engine"), ("app", "services/shop"), ("loadgen", "services/loadgen"), ("models", "ml/models"),
         ("data", "ml/data"), ("telemetry", "deploy/telemetry"), ("scripts", "tools")]
SKIP_PREFIX = ("results/", "docs/results/", "docs/postmortems/", "docs/session/", "console/", "ml/models/artifacts/")
TEXT_EXT = {".py", ".yml", ".yaml", ".ini", ".toml", ".ps1", ".sh", ".cfg", ".txt", ".md", ".json"}
SPECIAL = {"Dockerfile", ".dockerignore", ".gitignore", ".gitattributes"}
CHILD = {  # in Markdown, rewrite only real paths, so words such as "web app/" stay untouched
    "eternalai": r"[\w.\-]", "app": r"(?:Dockerfile|common|inventory|orders|payments|web|requirements)",
    "loadgen": r"[\w.\-]", "models": r"(?:artifacts|[\w\-]+\.py)",
    "data": r"(?:kb|raw|runs|processed|labels|[\w\-]+\.(?:py|txt|csv))", "telemetry": r"prometheus",
    "scripts": r"[\w\-]+\.(?:py|ps1|sh)",
}


def _segment(text: str, old: str, new: str, prose: bool) -> str:
    pat = re.compile(r"(?<![\w.\-/\\@:])(\./|\.\\)?" + re.escape(old) + r"([/\\])(?=" + (CHILD[old] if prose else ".") + ")")
    return pat.sub(lambda m: (m.group(1) or "") + (new.replace("/", "\\") if m.group(2) == "\\" else new) + m.group(2), text)


def rewrite(rel: str, text: str) -> str:
    path = Path(rel)
    t = text
    for old, new in MOVES:
        t = _segment(t, old, new, path.suffix == ".md")
    t = re.sub(r"\beternalai\.(?!db\b)(?=[a-z_])", "engine.", t)  # module paths; the file eternalai.db keeps its name
    t = re.sub(r"\bfrom eternalai\b", "from engine", t)
    t = re.sub(r"^(\s*)import eternalai\b", r"\1import engine", t, flags=re.M)
    if path.suffix == ".py":
        recv = r"((?<!\bMAIN )(?<!\bMAIN)(?<!\bck )(?<!\bck)(?<!\brepo )(?<!\brepo)/ ?)"  # MAIN/ck/repo: old-layout checkouts
        for old, parts in (("models", '"ml" / "models"'), ("data", '"ml" / "data"'), ("scripts", '"tools"'),
                           ("eternalai", '"engine"'), ("app", '"services" / "shop"'), ("loadgen", '"services" / "loadgen"')):
            t = re.sub(recv + f'"{old}"', r"\1" + parts, t)
        if rel.startswith(("ml/models/", "ml/data/")):  # one folder deeper than before
            t = t.replace("resolve().parents[1]", "resolve().parents[2]")
    return t


def changed_files(base: str) -> list[str]:
    out = subprocess.run(["git", "diff", "--name-only", "--diff-filter=AMR", f"{base}...HEAD"],
                         capture_output=True, text=True, check=True).stdout.split()
    return [f for f in out if not f.startswith(SKIP_PREFIX) and (Path(f).suffix in TEXT_EXT or Path(f).name in SPECIAL)]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", required=True, help="the branch you merged, e.g. origin/main")
    ap.add_argument("--write", action="store_true", help="rewrite the files (default: only list them)")
    a = ap.parse_args(argv)
    hits = 0
    for rel in changed_files(a.base):
        p = Path(rel)
        if not p.is_file():
            continue
        try:
            s = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        n = rewrite(rel, s)
        if n != s:
            hits += 1
            print(("rewrote " if a.write else "would rewrite ") + rel)
            if a.write:
                p.write_text(n, encoding="utf-8", newline="")
    print(f"{hits} file(s) {'rewritten' if a.write else 'to rewrite'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
