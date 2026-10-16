"""Download RCAEval RE1 metric zips from Zenodo (record 14590730) into data/raw/.

    python data/download_rcaeval.py --systems OB SS TT [--max-mb 2000] [--dest data/raw]

Checks the real size with a HEAD request first and refuses anything above
--max-mb. Zips are extracted into their own directory with path-traversal
protection; nothing from the archive is ever executed.
"""
import argparse
import urllib.request
import zipfile
from pathlib import Path

BASE = "https://zenodo.org/records/14590730/files/{name}.zip?download=1"


def size_mb(url: str) -> float:
    req = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(req, timeout=60) as r:
        return int(r.headers["Content-Length"]) / 1e6


def safe_extract(zf: zipfile.ZipFile, dest: Path):
    root = dest.resolve()
    for m in zf.namelist():
        if not (root / m).resolve().is_relative_to(root):
            raise RuntimeError(f"unsafe path in archive: {m}")
    zf.extractall(dest)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", default="RE1", choices=["RE1", "RE2", "RE3"])
    ap.add_argument("--systems", nargs="+", default=["OB"], choices=["OB", "SS", "TT"])
    ap.add_argument("--dest", default="data/raw")
    ap.add_argument("--max-mb", type=float, default=2000)
    a = ap.parse_args()
    dest = Path(a.dest)
    dest.mkdir(parents=True, exist_ok=True)
    for s in a.systems:
        name = f"{a.suite}-{s}"
        url = BASE.format(name=name)
        mb = size_mb(url)
        print(f"{name}: {mb:.1f} MB")
        if mb > a.max_mb:
            print(f"  skipped (over --max-mb {a.max_mb})")
            continue
        if (dest / name).exists():
            print("  already extracted")
            continue
        z = dest / f"{name}.zip"
        urllib.request.urlretrieve(url, z)
        with zipfile.ZipFile(z) as zf:
            safe_extract(zf, dest)
        z.unlink()
        print(f"  extracted to {dest / name}")


if __name__ == "__main__":
    main()
