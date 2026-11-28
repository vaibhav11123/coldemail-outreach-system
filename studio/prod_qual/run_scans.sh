#!/usr/bin/env bash
# Supply-chain and secret scans for production qualification.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="${1:-/opt/cursor/artifacts/prod_qual}"
mkdir -p "$OUT"
cd "$ROOT"

echo "== pip-audit =="
if .venv/bin/pip-audit -r requirements.txt -f json -o "$OUT/pip_audit.json" 2>"$OUT/pip_audit.err"; then
  echo PASS >"$OUT/pip_audit.status"
else
  echo FAIL >"$OUT/pip_audit.status"
  cat "$OUT/pip_audit.err" || true
fi

echo "== gitleaks =="
GITLEAKS_BIN="${GITLEAKS_BIN:-gitleaks}"
if ! command -v "$GITLEAKS_BIN" >/dev/null 2>&1; then
  GITLEAKS_BIN=/tmp/gitleaks
fi
if [[ -x "$GITLEAKS_BIN" ]]; then
  if "$GITLEAKS_BIN" detect --source "$ROOT" --no-git -r "$OUT/gitleaks.json" -f json; then
    echo PASS >"$OUT/gitleaks.status"
  else
    echo FAIL >"$OUT/gitleaks.status"
  fi
else
  echo NOT_RUN >"$OUT/gitleaks.status"
fi

echo "== done =="
ls -la "$OUT"
