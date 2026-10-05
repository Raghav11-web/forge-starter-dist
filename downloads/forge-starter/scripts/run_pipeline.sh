#!/usr/bin/env bash
# One-shot Forge pipeline (dry-run outreach). Usage: ./scripts/run_pipeline.sh [limit]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY="${ROOT}/.venv/bin/python"
if [[ ! -x "$PY" ]]; then PY=python3; fi
LIMIT="${1:-10}"
echo "== find =="
"$PY" scripts/find_leads.py --limit "$LIMIT"
echo "== match =="
"$PY" scripts/match_leads.py --profile profiles/demo-freelancer.yaml
echo "== draft =="
"$PY" scripts/draft_proposals.py --top 5
echo "== queue =="
"$PY" scripts/queue_outreach.py --from-index data/proposals/latest-index.json
"$PY" scripts/queue_outreach.py --approve all --list
echo "== dry-run send =="
"$PY" scripts/send_outreach.py
echo "== digest =="
"$PY" scripts/daily_digest.py
