# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

winrt_datas, winrt_binaries, winrt_hiddenimports = collect_all('winrt')
storage_datas, storage_binaries, storage_hiddenimports = collect_all('winrt.windows.storage')
streams_datas, streams_binaries, streams_hiddenimports = collect_all('winrt.windows.storage.streams')
imaging_datas, imaging_binaries, imaging_hiddenimports = collect_all('winrt.windows.graphics.imaging')
ocr_datas, ocr_binaries, ocr_hiddenimports = collect_all('winrt.windows.media.ocr')

hiddenimports = []
hiddenimports += winrt_hiddenimports
hiddenimports += storage_hiddenimports
hiddenimports += streams_hiddenimports
hiddenimports += imaging_hiddenimports
hiddenimports += ocr_hiddenimports

datas = []
datas += winrt_datas
datas += storage_datas
datas += streams_datas
datas += imaging_datas
datas += ocr_datas

binaries = []
binaries += winrt_binaries
binaries += storage_binaries
binaries += streams_binaries
binaries += imaging_binaries
binaries += ocr_binaries


a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    name='textcut',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
