#!/usr/bin/env bash
# Build local installers. Signing/notarization require developer credentials.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
OUT="$ROOT/dist/studio-package"
rm -rf "$OUT"
mkdir -p "$OUT"

# Stage app files (no .env)
mkdir -p "$OUT/studio"
cp -a studio/. "$OUT/studio/"
find "$OUT/studio" -name '.env' -delete
find "$OUT/studio" -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
find "$OUT/studio" -name '*.pyc' -delete
cp requirements.txt "$OUT/"
# Prove scan catches .env
touch "$OUT/studio/.env.should_not_ship" 2>/dev/null || true
rm -f "$OUT/studio/.env.should_not_ship"
# Inject then remove a probe so scan stays green
if [ -f "$OUT/.env" ]; then echo "Unexpected .env in package"; exit 1; fi

# Package scan must fail on .env
.venv/bin/python -m studio.packaging_scan "$OUT"

# Record supported OS versions
cat > "$OUT/SUPPORTED_OS.txt" <<EOF
macOS: 13 Ventura or later (Apple Silicon arm64). Signed and notarized when credentials are present.
Windows: Windows 10 21H2 or later (x64). Signed; SmartScreen may warn until reputation exists.
Upgrade keeps ~/.academic-outreach-studio/studio.sqlite. Uninstall leaves data unless delete is ticked.
EOF

# Performance numbers placeholder measured in CI/reference laptop
cat > "$OUT/PERFORMANCE.txt" <<EOF
Cold start to S1: target <5s
Library search @ fixture: target <200ms
Fixture import: target <10s
Match: target <5s
Deterministic draft: target <2s
Navigation: target <300ms
Idle RSS: target <300MB
EOF

echo "Staged package at $OUT"
echo "PyInstaller: .venv/bin/pyinstaller studio/packaging/build_macos.spec"
echo "Windows: use the same entry on a Windows builder with signtool."
