# Sales and distribution strategy (authoritative)

**Linked:** `ZERO_COST_COMMERCIAL.md` · `MERCHANT_OUTREACH.md` · fulfilment CLI  
**Status key:** `[x]` decided/documented · `[~]` partial in-repo · `[ ]` external · `AVOID` without written approval

This roadmap does **not** claim merchant, Store, or marketplace acceptance. Product-category approval is the primary commercial blocker.

---

## Architecture (locked)

| Component | Direction |
| --- | --- |
| Primary sales channel | Own product website (Cloudflare Pages) |
| Preferred checkout | FastSpring (MoR), subject to approval |
| Alt MoR | Verifone / 2Checkout |
| Indian gateways | Cashfree / Razorpay — product clearance required |
| Immediate low-volume | PayPal Business Payment Links + manual fulfilment |
| Windows | Direct download + Microsoft Store (if certified) |
| macOS | Local browser Studio now; notarized download after Apple $99 if chosen |
| Dataset delivery | Personalized packages via existing Python issuer |
| Licensing | Existing Ed25519 / X25519 stack (manual offline first) |
| Acquisition | Academic communities, affiliates, organic search |

## Platforms eliminated or high-risk

| Platform | Decision | Reason |
| --- | --- | --- |
| Lemon Squeezy | Eliminate | New sellers closed; shutdown scheduled |
| Payhip | `AVOID` | Lead-list / scraped-data policy risk |
| Gumroad | `AVOID` | Email-list / bulk-outreach restrictions |
| OpenDataBay | Poor fit | Individual seller + contact-DB policy |
| Datarade | Not primary | Business registration / enterprise focus |

## Low-volume operating model (1–10 sales/week)

1. Customer pays via approved marketplace or PayPal payment link.
2. Operator verifies the transaction offline.
3. Run fulfilment: `python -m studio.dataset fulfil …`
4. Deliver private download (or marketplace file delivery).
5. Record stays in local `delivery_ledger.sqlite` + fulfilment receipt.

No always-on licensing server required for offline device-bound licences. Remote revocation and device replacement stay manual until volume justifies Workers/D1.

## Build vs skip (now)

| Build | Skip until volume / approval |
| --- | --- |
| Complete Studio + dataset | Custom payment gateway |
| Fingerprinted packaging | Always-on PostgreSQL |
| Manual `fulfil` CLI | Full CRM / affiliate SaaS |
| Product website | Paid ads / SEO subscriptions |
| Purchase→entitlement adapter (later) | Keygen subscription |

## Discovery channels (priority assessment)

University communities · campus reps · research newsletters · study-abroad creators · organic search · LinkedIn · Reddit (r/gradadmissions, r/PhD, r/REU, r/MSCS, r/InternationalStudents) · Microsoft Store · YouTube · Product Hunt · GitHub sample · ACM/IEEE student chapters.

Community posts must follow each community’s rules. These are prospective channels, not partnerships.

## Website (proposed IA)

Home · Dataset · Academic Studio · Sample · Pricing · Docs · Downloads · Licence recovery · Help · Changelog · Privacy · Terms · Research resource landing pages (only where dataset coverage supports claims).

Provisional prices: Dataset **$14.99** · Studio **$39.99**.

## Affiliate (proposal only)

Free join · 25% commission after refund window · unique link/code · transparent disclosure · prefer provider-native attribution when MoR selected.

## Launch checklist (operator + engineering)

### Commercial infrastructure

- [ ] FastSpring eligibility inquiry
- [ ] 2Checkout eligibility inquiry
- [ ] Paddle product clearance
- [ ] Cashfree product clearance
- [ ] Razorpay product clearance
- [ ] PayPal Business Individual KYC
- [ ] Confirm Indian seller / payout requirements
- [ ] Obtain pricing quotations
- [ ] Select primary + fallback after written product acceptance

### Website and checkout

- [ ] Cloudflare Pages site (or `pages.dev`)
- [ ] Dataset + Studio product pages + sample
- [ ] Hosted checkout embed after approval
- [ ] Webhooks → licence issuer (when automating)
- [ ] Test purchase, delivery, refund, recovery

### Software distribution

- [ ] Windows production installer / MSIX
- [ ] Microsoft Partner Center + Store submission
- [ ] Apple Developer enrollment (if notarizing)
- [ ] Secure release hosting (R2 within free tier)
- [ ] Linux packaging evaluation

### Distribution assets

- [ ] Walkthrough video · docs · internship guides · SEO resources
- [ ] Affiliate programme design
- [ ] Product Hunt / LinkedIn / YouTube prep

### Launch qualification

- [ ] Complete advertised product functionality
- [ ] Dataset distribution rights / privacy review
- [ ] Merchant acceptance for **both** products
- [ ] International purchase + payout verified
- [ ] Licensing security review
- [ ] Support + recovery workflows
- [ ] Final release report

## Engineering commands

```bash
# Manual fulfilment after verifying payment
.venv/bin/python -m studio.dataset fulfil \
  --sku dataset \
  --out /tmp/deliveries/cust_demo \
  --customer cust_demo \
  --email student@example.edu \
  --provider paypal \
  --payment-ref TXN123

.venv/bin/python -m studio.dataset fulfil \
  --sku studio \
  --out /tmp/deliveries/cust_demo_studio \
  --customer cust_demo \
  --email student@example.edu \
  --provider paypal \
  --payment-ref TXN456
```

Merchant inquiry text: `MERCHANT_OUTREACH.md`.
