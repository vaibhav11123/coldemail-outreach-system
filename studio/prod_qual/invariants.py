"""Critical commercial invariants — each must have adversarial automated coverage.

INV-01  Never send an unapproved email.
INV-02  Never auto-resend unknown_delivery.
INV-03  Never create duplicate provider submissions for the same approved content.
INV-04  Never accept unsupported factual claims in an approved draft.
INV-05  Never represent unknown funding/eligibility as verified.
INV-06  Never expose one hosted customer's data to another (when multi-tenant is live).
INV-07  Never leak credentials via logs, installers, or support bundles.
INV-08  Never destroy the bundled research library when personal data is deleted.
INV-09  Never lose committed customer data across an ordinary process restart.
INV-10  Never incur unauthorized inference charges (no silent paid failover).
INV-11  Essential offline features must work with all external providers down.
INV-12  Never silently bypass provider authorization or institutional restrictions.
INV-13  Editing an approved draft clears approval before send.
INV-14  Suppressed recipients cannot be selected for send.
INV-15  Failed sends may be explicitly retried; unknown_delivery may not.
"""

INVARIANTS = [
    "INV-01",
    "INV-02",
    "INV-03",
    "INV-04",
    "INV-05",
    "INV-06",
    "INV-07",
    "INV-08",
    "INV-09",
    "INV-10",
    "INV-11",
    "INV-12",
    "INV-13",
    "INV-14",
    "INV-15",
]
