# Installer & update signing (₹0-first)

Application-level update authenticity is implemented in-repo via
`python -m studio.dataset sign-update` (Ed25519 issuer key → `update_manifest.json` +
`update_manifest.sig`). That is **not** a substitute for OS trust.

| Platform | Trusted OS path | Cost | Status in this repo |
| --- | --- | --- | --- |
| Windows Store MSIX | Store signing | Usually $0 for individual if accepted | Spec only — needs Store listing |
| Windows direct EXE | Authenticode (signtool) | Certificate purchase | Spec + PyInstaller; unsigned until cert |
| macOS | Developer ID + notarization | Apple Developer Program | Spec + PyInstaller; unsigned until membership |
| Linux AppImage | Optional GPG + update manifest | $0 | Manifest signing available |

## Operator steps (when credentials exist)

```bash
# 1) Build payload (on the target OS)
.venv/bin/pyinstaller studio/packaging/build_windows.spec
# or build_macos.spec

# 2) Sign OS artifact with vendor tools (signtool / codesign + notarize)

# 3) Sign update channel manifest (works today with issuer vault / env key)
.venv/bin/python -m studio.dataset sign-update \
  --payload dist/AcademicStudio.zip \
  --url 'https://example.invalid/AcademicStudio.zip' \
  --version 1.0.0 \
  --out dist/updates/1.0.0
```

## Honesty

Until Store approval or paid certificates exist, customers may see SmartScreen /
Gatekeeper warnings. Document that in listing copy and prefer marketplace-native
delivery when available.
