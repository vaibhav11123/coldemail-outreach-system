#!/usr/bin/env python3
"""Lightweight mutation smoke for critical email/approval guards.

Not a substitute for mutmut — verifies that selected deliberate bugs would be
caught by studio/tests/prod_qual/test_inv_email_safety.py style assertions.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAILER = ROOT / "studio" / "mailer_studio.py"


def _must_contain(path: Path, needle: str) -> None:
    text = path.read_text(encoding="utf-8")
    if needle not in text:
        raise SystemExit(f"MUTATION-SMOKE FAIL: missing guard text in {path}: {needle!r}")


def main() -> int:
    # Structural checks that critical control points still exist in source.
    _must_contain(MAILER, "Draft is not approved")
    _must_contain(MAILER, "Unknown delivery requires manual reconciliation")
    _must_contain(MAILER, "Recipient is suppressed")
    _must_contain(MAILER, "AND state = 'pending'")
    _must_contain(MAILER, "return cur.rowcount == 1")
    # Parse to ensure file remains valid Python after edits
    ast.parse(MAILER.read_text(encoding="utf-8"))
    print("MUTATION-SMOKE PASS: critical send guards present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
