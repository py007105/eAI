"""Download the NAB realAWSCloudwatch series and labels/combined_windows.json at ONE pinned commit.

    python ml/data/download_nab.py --commit ea702d75cc2258d9d7dd35ca8e5e2539d71f3140 [--dest ml/data/raw/nab]

Refuses to run without a full 40-character commit hash (a branch name such as "master" is not accepted).
Writes the files under --dest (ml/data/raw/ is git-ignored) and --dest/MANIFEST.json with URL, commit, size and SHA256
per file. NAB data must never be committed. The pinned commit is recorded in docs/NAB_EVAL.md.
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

REPO = "https://github.com/numenta/NAB"
RAW = "https://raw.githubusercontent.com/numenta/NAB/{commit}/{path}"
SERIES = [
    "ec2_cpu_utilization_24ae8d", "ec2_cpu_utilization_53ea38", "ec2_cpu_utilization_5f5533",
    "ec2_cpu_utilization_77c1ca", "ec2_cpu_utilization_825cc2", "ec2_cpu_utilization_ac20cd",
    "ec2_cpu_utilization_c6585a", "ec2_cpu_utilization_fe7f93", "ec2_disk_write_bytes_1ef3de",
    "ec2_disk_write_bytes_c0d644", "ec2_network_in_257a54", "ec2_network_in_5abac7", "elb_request_count_8c0756",
    "grok_asg_anomaly", "iio_us-east-1_i-a2eb1cd9_NetworkIn", "rds_cpu_utilization_cc0c53",
    "rds_cpu_utilization_e47b3b",
]
FILES = [f"ml/data/realAWSCloudwatch/{s}.csv" for s in SERIES] + ["labels/combined_windows.json"]
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(url: str, out: Path) -> None:
    tmp = out.with_suffix(out.suffix + ".part")
    with urllib.request.urlopen(url, timeout=60) as r, open(tmp, "wb") as f:
        while chunk := r.read(1 << 16):
            f.write(chunk)
    if tmp.stat().st_size == 0:
        tmp.unlink()
        raise RuntimeError(f"empty download: {url}")
    tmp.replace(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--commit", default=None, help="full 40-character NAB commit hash (required)")
    ap.add_argument("--dest", default="ml/data/raw/nab")
    a = ap.parse_args(argv)
    if not a.commit or not COMMIT_RE.match(a.commit):
        print("refusing to run: pass --commit with a full 40-character NAB commit hash (see docs/NAB_EVAL.md)",
              file=sys.stderr)
        return 2
    dest = Path(a.dest)
    entries = []
    for rel in FILES:
        url = RAW.format(commit=a.commit, path=rel)
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        fetch(url, out)
        entries.append({"path": rel, "url": url, "bytes": out.stat().st_size, "sha256": sha256(out)})
        print(f"{rel}  {entries[-1]['bytes']} bytes  {entries[-1]['sha256'][:12]}")
    manifest = {"source": REPO, "commit": a.commit, "downloaded_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "note": "NAB data; never commit. Written by ml/data/download_nab.py.", "files": entries}
    (dest / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {dest / 'MANIFEST.json'} ({len(entries)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
