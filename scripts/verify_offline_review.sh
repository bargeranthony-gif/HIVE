#!/usr/bin/env bash
# Bounded local verification. No installs, network calls, external writes or spending.
set -euo pipefail
repo_root="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$repo_root"

if ! python3 -m pytest --version >/dev/null 2>&1; then
    printf 'BLOCKED: pytest is not installed; no automatic install attempted.\n' >&2
    exit 2
fi

scratch="$(mktemp -d)"
trap 'rm -rf -- "$scratch"' EXIT
export HIVE_HOME="$scratch/hive-home"
export PYTHONPATH="$repo_root"
export PYTHONDONTWRITEBYTECODE=1
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1

# Include other in-branch fictional review acceptance tests when present.
# The isolated candidate ZIP may omit them; never claim they were tested then.
# Run every in-branch regression and review suite, including both replay contracts.
python3 -m pytest -q tests --disable-warnings

python3 -m hive.temporal_graph \
    --fixture fixtures/cedar_arc_temporal.json \
    --output "$scratch/brief"

python3 -m hive.temporal_graph \
    --fixture fixtures/cedar_arc_temporal.json \
    --compare-from 2026-03-10T00:00:00Z \
    --output "$scratch/delta"

python3 - "$scratch/brief/temporal_graph.json" "$scratch/delta/temporal_delta.json" <<'PY'
import json
import sys
from pathlib import Path
result=json.loads(Path(sys.argv[1]).read_text())
receipt=result['receipt']
assert result['classification']=='SYNTHETIC_OFFLINE_TEMPORAL_GRAPH_REVIEW'
assert receipt['live_provider_calls']==0
assert receipt['api_credits_spent']==0
assert receipt['external_writes']==0
assert receipt['trades_executed']==0
assert receipt['hive_database_modified'] is False
assert receipt['commercial_derivative_permission']=='UNKNOWN_NOT_GRANTED'
assert len(result['paths'])==3
delta=json.loads(Path(sys.argv[2]).read_text())
assert delta['classification']=='SYNTHETIC_OFFLINE_HISTORICAL_CHANGE_REVIEW'
assert any(row['source_id']=='S-02' for row in delta['claims_removed_or_superseded'])
assert delta['receipt']['external_writes']==0
print('S2 synthetic snapshot and historical-delta receipts verified. Zero external actions; licensing blocked.')
PY
# S3 is deliberately non-joinable on the two unchanged synthetic fixtures.
# Fail closed and preserve only a sanitized reason code, not mixed-tenant data.
if [ -f fixtures/economic_replay_synthetic.json ]; then
    status=0
    python3 -m hive.evidence_bridge \
      --graph fixtures/cedar_arc_temporal.json \
      --replay fixtures/economic_replay_synthetic.json \
      > "$scratch/bridge-denial.json" || status=$?
    if [ "$status" -ne 3 ]; then
        printf 'BLOCKED: S3 cross-tenant bridge did not return rejection code 3.\n' >&2
        exit 4
    fi
    python3 - "$scratch/bridge-denial.json" <<'PYBRIDGE'
import json,sys
from pathlib import Path
v=json.loads(Path(sys.argv[1]).read_text())
assert v['state']=='BLOCKED'
assert v['reason']=='CROSS_TENANT_DENIED'
assert v['graph_or_replay_inspected'] is False
assert v['joined_claims']==[]
assert v['receipt']['commercial_authority']=='NOT_GRANTED'
print('S3 synthetic cross-tenant no-join receipt verified.')
PYBRIDGE
fi
printf 'DONE: offline test harness and S2/S3 receipts passed. No production merge or deployment.\n'
