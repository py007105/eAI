#!/usr/bin/env bash
# One-command demo launcher (POSIX shell). WRITTEN, NOT YET RUN: rehearse it before relying on it.
#   CONFIRM_RESET=1 bash tools/demo.sh
# Steps: refuse if a benchmark is running -> export results (and checksum) -> reset the scorecard -> start the stack -> preflight -> open the dashboard.
# The reset deletes the evaluator's volume (${PROJECT}_truth). It runs only with CONFIRM_RESET=1 AND only after the export produced SHA256SUMS.
set -euo pipefail
cd "$(dirname "$0")/.."
PROJECT="${PROJECT:-eai}"; EXPORT_DIR="${EXPORT_DIR:-results/benchmark-v1}"

if pgrep -f "run_benchmark|run_all_arms" >/dev/null 2>&1; then
  echo "a benchmark process is running; refusing to touch the stack" >&2; exit 1
fi

# 1. export (never reset first)
mkdir -p "$EXPORT_DIR/truth"
ev="$(docker ps -q --filter label=com.docker.compose.service=evaluator | head -n1)"
if [ -n "$ev" ]; then docker cp "$ev:/truth/." "$EXPORT_DIR/truth"; else echo "evaluator not running: skipping truth export"; fi
[ -f docs/results/benchmark_raw.jsonl ] && cp docs/results/benchmark_raw.jsonl "$EXPORT_DIR/"
( cd "$EXPORT_DIR" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS )
n="$(wc -l < "$EXPORT_DIR/SHA256SUMS")"
echo "exported $n file(s) with checksums to $EXPORT_DIR"

# 2. reset the scorecard
[ "${CONFIRM_RESET:-0}" = "1" ] || { echo "export done; re-run with CONFIRM_RESET=1 to delete ${PROJECT}_truth" >&2; exit 1; }
[ "$n" -gt 0 ] || { echo "nothing was exported; refusing to reset" >&2; exit 1; }
docker compose -p "$PROJECT" down
docker volume rm "${PROJECT}_truth"

# 3. start
docker compose -p "$PROJECT" up -d
echo "waiting 60 s for services"; sleep 60

# 4. preflight (non-zero exit stops the launcher)
python tools/preflight.py --require-llm-key || { echo "preflight failed; do not demo" >&2; exit 1; }

# 5. open
(xdg-open http://localhost:8050 || open http://localhost:8050) >/dev/null 2>&1 || echo "open http://localhost:8050"
