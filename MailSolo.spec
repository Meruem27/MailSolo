# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build definition for MailSolo.

All paths are resolved relative to this spec file, so the project can be
built from any location without absolute or global references.
"""

from pathlib import Path

PROJECT_ROOT = Path(SPECPATH).resolve()
LOGO_DIR = PROJECT_ROOT / "logo"

a = Analysis(
    [str(PROJECT_ROOT / "main.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[(str(LOGO_DIR / "MailSolo.png"), "logo")],
    hiddenimports=[],
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
    a.binaries,
    a.datas,
    [],
    name='MailSolo',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(LOGO_DIR / 'MailSolo.ico'),
    version=str(PROJECT_ROOT / 'version_info.txt'),
)
