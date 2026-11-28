# -*- mode: python ; coding: utf-8 -*-
# Windows x64 PyInstaller spec. Sign with signtool after build.
# SmartScreen may warn until reputation exists.

block_cipher = None

a = Analysis(
    ['../__main__.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('../templates', 'studio/templates'),
        ('../static', 'studio/static'),
        ('../data', 'studio/data'),
        ('../benchmarks', 'studio/benchmarks'),
    ],
    hiddenimports=['uvicorn.logging', 'uvicorn.loops', 'uvicorn.loops.auto', 'uvicorn.protocols', 'uvicorn.protocols.http', 'uvicorn.protocols.http.auto', 'uvicorn.protocols.websockets', 'uvicorn.protocols.websockets.auto', 'uvicorn.lifespan', 'uvicorn.lifespan.on'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='AcademicOutreachStudio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
)
