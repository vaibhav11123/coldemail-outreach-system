#!/usr/bin/env bash
# Optional bridge: verified webhook mint → manual fulfil (same payment ref).
# Requires STUDIO_LICENSING_WEBHOOK_SECRET and a running Studio on 127.0.0.1:8765
# OR skip webhook and fulfil alone after dashboard verification.
set -euo pipefail

SKU="${1:?usage: $0 <dataset|studio> <customer_id> <email> <provider> <payment_ref> <out_dir>}"
CUSTOMER="${2:?}"
EMAIL="${3:?}"
PROVIDER="${4:?}"
PAYMENT_REF="${5:?}"
OUT="${6:?}"
HOST="${STUDIO_HOST:-http://127.0.0.1:8765}"
SECRET="${STUDIO_LICENSING_WEBHOOK_SECRET:?set STUDIO_LICENSING_WEBHOOK_SECRET}"

API_SKU="standard_dataset"
[[ "$SKU" == "studio" || "$SKU" == "academic_studio" ]] && API_SKU="academic_studio"

curl -fsS -X POST "$HOST/api/licensing/webhook/payment" \
  -H "Host: 127.0.0.1:8765" \
  -H "Content-Type: application/json" \
  -H "X-Studio-Webhook-Secret: $SECRET" \
  -d "{\"customer_id\":\"$CUSTOMER\",\"customer_email\":\"$EMAIL\",\"sku\":\"$API_SKU\",\"payment_provider\":\"$PROVIDER\",\"external_payment_id\":\"$PAYMENT_REF\"}"

echo
.venv/bin/python -m studio.dataset fulfil \
  --verified-payment \
  --sku "$SKU" \
  --customer "$CUSTOMER" \
  --email "$EMAIL" \
  --provider "$PROVIDER" \
  --payment-ref "$PAYMENT_REF" \
  --out "$OUT"
