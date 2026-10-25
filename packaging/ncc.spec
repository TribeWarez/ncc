# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the NCC Windows desktop release.

``scripts/build-release.ps1`` compiles ``ncc-daemon.exe`` with the ``nym``
feature, runs this spec, then copies the daemon beside ``ncc.exe`` in the
staged bundle. ``ncc.daemon.find_daemon`` looks there when frozen.
"""

from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent
CLIENT = ROOT / "client-py"

a = Analysis(
    [str(ROOT / "packaging" / "entry.py")],
    pathex=[str(CLIENT)],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "unittest", "pydoc", "doctest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ncc",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="ncc",
)
