# Zero fixed-cost commercial operating model (authoritative)

**Policy:** Target **₹0 upfront** and **₹0 mandatory monthly** infrastructure. Incur costs only as payment processing fees on successful sales (plus optional Apple Developer membership if we choose notarized macOS).

**Status key:** `[x]` decided/documented · `[~]` partially ready in-repo · `[ ]` external registration / approval pending · `BLOCKED` waiting on third party

This document does **not** claim merchant accounts, KYC, Store approval, or live payouts exist. Those remain operator actions.

---

## Locked principles

1. Prefer free alternatives → open source → student/startup benefits → platform-included → build ourselves → transaction fees → paid subscriptions last.
2. No Keygen subscription, no paid licensing SaaS, no paid AI APIs on our side, no paid marketing stack initially.
3. Customer research workspace stays local; we host only a thin commercial control plane when automation is justified.
4. **Initial sales volume (1–10/week):** manual purchase verification + local packaging CLI. No always-on licensing server required for offline device-bound licences.
5. Automate only when volume warrants (see thresholds below).
6. Never conceal faculty-contact or outreach capabilities during merchant review.

## Automation thresholds (operational guidance, not forecasts)

| Volume | Approach |
| --- | --- |
| 1–10 purchases/week | Manual verify → `python -m studio.dataset fulfil …` → private delivery |
| 10–50/week | Batch packaging; semi-automated delivery |
| 50–100/week | Payment webhooks + light Workers/D1 entitlement API |
| 100+/week | Dedicated commercial infra only if warranted |

## Cost posture

| Category | Selected approach | Fixed cost |
| --- | --- | --- |
| Seller identity | Individual (no company required to start) | ₹0 |
| International payments | PayPal Business Individual / MoR after approval | Fees on sale |
| Indian payments | UPI / approved individual links | ₹0 setup |
| Website | Cloudflare Pages (`pages.dev` until domain) | $0 |
| Entitlement DB (later) | Cloudflare D1 | $0 within limits |
| Light licensing API (later) | Cloudflare Workers + Web Crypto | $0 within limits |
| Object storage (later) | Cloudflare R2 | $0 within allowance |
| Licensing crypto | Existing Ed25519 / X25519 stack | $0 |
| Dataset packaging | Existing Python CLI (operator machine) | $0 |
| Windows signing/hosting | Microsoft Store MSIX path (if approved) | $0 registration |
| macOS trust | Local browser Studio now; Apple $99/yr if notarizing later | Deferred |
| AI | Customer BYOAI | $0 for us |
| Marketing | Organic / communities / affiliates | $0 upfront |
| Independent pen-test | Deferred paid; use free scanners meanwhile | Deferred |

## Payment & distribution shortlist (approval required)

| Rank | Provider / channel | Role | Status |
| --- | --- | --- | --- |
| 1 | FastSpring | International merchant of record | `[ ]` apply |
| 2 | Verifone/2Checkout | Alt MoR | `[ ]` apply |
| 3 | Paddle | Alt software checkout | `[ ]` product clearance |
| 4 | Cashfree | Indian gateway / intl | `[ ]` product clearance |
| 5 | Razorpay | Indian gateway / intl | `[ ]` product clearance |
| — | PayPal Business Payment Links | Immediate low-volume workaround | `[ ]` KYC |
| — | Microsoft Store | Windows distribution + eligible signing | `[ ]` Partner Center |
| — | Own Cloudflare Pages site | Discovery + checkout embed | `[~]` not built |
| Eliminate | Lemon Squeezy | Shutting down / no new sellers | `N/A` |
| High risk | Gumroad, Payhip | Lead-list / outreach policy risk | Avoid without written OK |

Template inquiry: `studio/prod_qual/MERCHANT_OUTREACH.md`.

## What we build vs outsource

| Build (us) | Outsource / skip initially |
| --- | --- |
| Complete Academic Studio + dataset | Card storage, tax engine, invoices |
| Fingerprinted packaging + licences | Custom payment gateway |
| Manual fulfilment CLI | Always-on PostgreSQL |
| Device activation / recovery UX | Full CRM / affiliate platform |
| Thin Workers entitlement API (later) | Keygen subscription |
| Product website + sample | Paid ads / SEO SaaS |

## Free registrations checklist (operator)

- [ ] GitHub Student Developer Pack (check commercial-use terms per offer)
- [ ] Cloudflare account (Pages / Workers / D1 / R2)
- [ ] Microsoft Partner Center (Store)
- [ ] PayPal Business Individual
- [ ] Stripe India invite request (optional)
- [ ] Razorpay / Cashfree applications (optional)
- [ ] Resend free tier (optional transactional mail)
- [ ] Google Search Console (after site exists)

## Engineering alignment

- Keep `LicenseStore` for **dev/test** and **manual fulfilment** on the operator machine.
- Optional later: Cloudflare Worker verifies payment webhooks + stores entitlements in D1; packaging remains Python on a trusted build host.
- See `KEYGEN_EVALUATION.md` (no Keygen spend) and `COMMERCIAL_DISTRIBUTION.md` (channels + launch checklist).
- Fulfilment command: `python -m studio.dataset fulfil --help`

## Honest limitations

- Merchant approval, KYC, Store certification, and payouts are **not done**.
- Free tiers have limits/overages; configure alerts.
- Student credits must not underpin perpetual customer entitlements.
- No legitimate free substitute for Apple Developer ID notarization.
- Automated scanners ≠ independent professional pen-test.
