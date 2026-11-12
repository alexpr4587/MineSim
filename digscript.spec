# -*- mode: python ; coding: utf-8 -*-

"""PyInstaller spec for DigScript: windowed onedir build for Windows and Linux.

The entry point is ``src/digscript/__main__.py``; its ``main()`` calls
``multiprocessing.freeze_support()`` as the very first call so a frozen app
does not spawn itself in an endless loop.

``exclude_binaries=True`` selects onedir mode: the executable is written next
to the collected binaries, datas and shared libraries instead of being bundled
into a single onefile binary.
"""

a = Analysis(
    ["src/digscript/__main__.py"],
    pathex=["src"],
    binaries=[],
    datas=[
        ("src/digscript/content", "digscript/content"),
        ("assets", "assets"),
    ],
    hiddenimports=[
        "digscript.runner.main",
        "digscript.runner.minerlib",
        "digscript.scripting.host",
        "digscript.scripting.stubs",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="digscript",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # windowed build
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="digscript",
)
