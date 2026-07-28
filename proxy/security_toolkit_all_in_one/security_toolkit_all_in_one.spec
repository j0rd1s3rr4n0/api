# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


block_cipher = None
ROOT = Path(SPECPATH).resolve()


a = Analysis(
    ["security_toolkit_all_in_one.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "security_toolkit.ico"), "."),
        (str(ROOT / "dorks_seed.txt"), "."),
    ],
    hiddenimports=[
        "socks",
        "sockshandler",
        "ultimater_multi",
        "requests",
        "urllib3.contrib.socks",
    ],
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
    name="security_toolkit_all_in_one",
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
    icon=str(ROOT / "security_toolkit.ico"),
)
