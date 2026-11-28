#!/usr/bin/env bash
# Live endpoint smoke — external APIs + local Studio HTTP.
# Usage: bash studio/prod_qual/live_endpoint_smoke.sh [base_url]
set -euo pipefail
BASE="${1:-http://127.0.0.1:8765}"
HOST_HEADER="127.0.0.1"
LOG="${LIVE_SMOKE_LOG:-/opt/cursor/artifacts/live_endpoint_smoke.log}"
mkdir -p "$(dirname "$LOG")"
exec > >(tee "$LOG") 2>&1

echo "=== Live endpoint smoke $(date -u +%Y-%m-%dT%H:%M:%SZ) base=$BASE ==="

check_http() {
  local name="$1" url="$2"
  local code
  code=$(curl -s -o /tmp/live_body.txt -w "%{http_code}" -m 30 -H "Host: $HOST_HEADER" "$url" || echo "000")
  echo "$name  HTTP $code  $url"
  if [[ "$code" != "200" && "$code" != "302" && "$code" != "303" ]]; then
    echo "  FAIL body: $(head -c 200 /tmp/live_body.txt)"
    return 1
  fi
  return 0
}

FAIL=0

echo "--- External research APIs ---"
if curl -sf -m 30 "https://api.openalex.org/works?filter=authorships.author.id:A5023888391&per-page=1" >/tmp/oa.json; then
  echo "OpenAlex  OK  $(python3 -c "import json;d=json.load(open('/tmp/oa.json'));print(d['results'][0]['display_name'][:80] if d.get('results') else 'empty')")"
else
  echo "OpenAlex  FAIL"; FAIL=1
fi

if curl -sf -m 30 -H "User-Agent: AcademicOutreachStudio/1.0 (mailto:support@academic-outreach.studio)" \
  "https://api.crossref.org/works/10.1038/nature14539" >/tmp/cr.json; then
  echo "Crossref  OK  $(python3 -c "import json;d=json.load(open('/tmp/cr.json'));print((d['message'].get('title') or [''])[0][:80])")"
else
  echo "Crossref  FAIL"; FAIL=1
fi

# Follow OpenCitations redirect to api.opencitations.net
if curl -sfL -m 30 "https://opencitations.net/index/api/v1/citations/10.1038/nature14539" >/tmp/oc.json; then
  echo "OpenCitations  OK  bytes=$(wc -c </tmp/oc.json)"
else
  echo "OpenCitations  FAIL"; FAIL=1
fi

echo "--- Faculty school pages ---"
for url in \
  "https://www.eecs.mit.edu/role/faculty/" \
  "https://www.cs.stanford.edu/people/faculty" \
  "https://www2.eecs.berkeley.edu/Faculty/Lists/faculty.html"
do
  code=$(curl -sI -m 30 -o /dev/null -w "%{http_code}" -L "$url" || echo "000")
  echo "Faculty  HTTP $code  $url"
  if [[ "$code" != "200" ]]; then FAIL=1; fi
done

echo "--- Studio localhost ---"
for path in /offer /profile /directory "/directory?q=kernel" /start /shortlist /ai /connections /mail /reader \
  /api/licensing/editions /api/licensing/issuer-public /api/licensing/device
do
  check_http "Studio$path" "$BASE$path" || FAIL=1
done

echo "--- Summary fail=$FAIL ---"
exit "$FAIL"
