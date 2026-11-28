# Payment lifecycle ops (verified purchase → entitlement)

**Constraint:** ₹0 fixed cost. Money moves through an approved marketplace; Studio records verified events locally.

## Happy path (Option A — manual)

1. Customer pays on marketplace.
2. Operator verifies the transaction in the provider dashboard (not a customer screenshot alone).
3. `python -m studio.dataset fulfil --verified-payment --provider … --payment-ref …`
4. Personalized dataset ZIP and/or Studio licence issuance.
5. Private delivery; customer activates via `/activate`.

## Automated webhook path (when provider supports it)

`POST /api/licensing/webhook/payment` with `X-Studio-Webhook-Secret`:

- Fail-closed if secret unset
- **Idempotent** on `external_payment_id` (same txn → same `license_id`)
- Appends `payment_events.jsonl` (`purchase_registered`, `idempotent_replay`)

## Refund / chargeback

1. Confirm refund in marketplace.
2. `POST /api/licensing/revoke/{license_id}` (same webhook secret) → store revoked + DEK cache cleared + `refund_recorded` event.
3. Disclose residual offline `.aslic` TTL window in refund policy (`PURCHASE_LIFECYCLE.md`).

## Issuer keys

| Mode | Mechanism |
| --- | --- |
| Dev | auto `dev_issuer.json` (forbidden in production) |
| CI/sealed | `STUDIO_ISSUER_PRIVATE_HEX` |
| Production operator | `python -m studio.dataset issuer-vault --init --passphrase …` + `STUDIO_ISSUER_MODE=production` + `STUDIO_ISSUER_VAULT_PASSPHRASE` |

Never ship issuer private material in customer packages.
