"""Download the SMD (Server Machine Dataset) files of the OmniAnomaly repository at ONE pinned commit.

    python data/download_smd.py --commit 7fb0e0acf89ea49908896bcc9f9e80fcfff6baf4 [--dest data/raw/smd]

- Refuses to run without a full 40-character commit hash (a branch name such as "master" is not accepted).
- Reads the file list and sizes for that commit from the GitHub API and prints the total size before downloading.
- Resumable: a file already on disk whose git blob hash matches the commit's file list is kept, not downloaded again.
- Every downloaded file is checked against its git blob hash, then --dest/MANIFEST.json records URL, commit, size and
  SHA256 per file.
SMD data lives under data/raw/ (git-ignored) and must never be committed. The pinned commit is in docs/SMD_EVAL.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = "https://github.com/NetManAIOps/OmniAnomaly"
TREE = "https://api.github.com/repos/NetManAIOps/OmniAnomaly/git/trees/{commit}?recursive=1"
RAW = "https://raw.githubusercontent.com/NetManAIOps/OmniAnomaly/{commit}/{path}"
PREFIX = "ServerMachineDataset/"
FOLDERS = ("train", "test", "test_label", "interpretation_label")
MACHINES = ([f"machine-1-{i}" for i in range(1, 9)] + [f"machine-2-{i}" for i in range(1, 10)]
            + [f"machine-3-{i}" for i in range(1, 12)])
FILES = [f"{PREFIX}{d}/{m}.txt" for d in FOLDERS for m in MACHINES] + [f"{PREFIX}LICENSE"]
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def git_blob_sha1(path: Path) -> str:
    """The hash git gives a file: sha1(b"blob <size>\\0" + content)."""
    h = hashlib.sha1(f"blob {path.stat().st_size}\0".encode())
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def list_files(commit: str) -> dict:
    req = urllib.request.Request(TREE.format(commit=commit), headers={"User-Agent": "eternalai-download-smd"})
    with urllib.request.urlopen(req, timeout=60) as r:
        tree = json.load(r)
    if tree.get("truncated"):
        raise RuntimeError("GitHub returned a truncated file list")
    return {t["path"]: t for t in tree["tree"] if t["type"] == "blob"}


def fetch(url: str, out: Path) -> None:
    tmp = out.with_suffix(out.suffix + ".part")
    with urllib.request.urlopen(url, timeout=120) as r, open(tmp, "wb") as f:
        while chunk := r.read(1 << 16):
            f.write(chunk)
    tmp.replace(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--commit", default=None, help="full 40-character OmniAnomaly commit hash (required)")
    ap.add_argument("--dest", default="data/raw/smd")
    a = ap.parse_args(argv)
    if not a.commit or not COMMIT_RE.match(a.commit):
        print("refusing to run: pass --commit with a full 40-character OmniAnomaly commit hash (see docs/SMD_EVAL.md)",
              file=sys.stderr)
        return 2
    listed = list_files(a.commit)
    missing = [p for p in FILES if p not in listed]
    if missing:
        print(f"{len(missing)} expected files are not in commit {a.commit}:", file=sys.stderr)
        for p in missing:
            print(f"  {p}", file=sys.stderr)
        return 3
    total = sum(listed[p]["size"] for p in FILES)
    print(f"{len(FILES)} files, {total} bytes ({total / 1e6:.1f} MB) at commit {a.commit}")

    dest = Path(a.dest)
    entries, failed = [], []
    for k, rel in enumerate(FILES, 1):
        local = rel[len(PREFIX):]
        out = dest / local
        out.parent.mkdir(parents=True, exist_ok=True)
        url = RAW.format(commit=a.commit, path=rel)
        want = listed[rel]["sha"]
        kept = out.exists() and out.stat().st_size == listed[rel]["size"] and git_blob_sha1(out) == want
        if not kept:
            try:
                fetch(url, out)
            except Exception as e:  # report and continue; the evaluation refuses incomplete input
                failed.append((rel, str(e)))
                print(f"[{k}/{len(FILES)}] FAILED {local}: {e}", file=sys.stderr)
                continue
            if git_blob_sha1(out) != want:
                failed.append((rel, "git blob hash differs from the commit's file list"))
                print(f"[{k}/{len(FILES)}] FAILED {local}: hash differs", file=sys.stderr)
                out.unlink()
                continue
        entries.append({"path": local, "url": url, "bytes": out.stat().st_size, "git_blob_sha1": want,
                        "sha256": sha256(out)})
        print(f"[{k}/{len(FILES)}] {'kept' if kept else 'got '} {local}  {entries[-1]['bytes']} bytes")

    manifest = {"source": REPO, "folder": PREFIX.rstrip("/"), "commit": a.commit,
                "downloaded_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "note": "SMD data; never commit. Written by data/download_smd.py.",
                "expected_files": len(FILES), "failed": [{"path": p, "error": e} for p, e in failed],
                "files": entries}
    (dest / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {dest / 'MANIFEST.json'} ({len(entries)} files, {len(failed)} failed)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
