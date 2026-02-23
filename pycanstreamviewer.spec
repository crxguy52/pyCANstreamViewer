# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.hooks import copy_metadata

datas = [('Z:\\My Drive\\fastboi\\pyCANstreamViewer\\config\\*.yaml', 'config'), ('Z:\\My Drive\\fastboi\\pyCANstreamViewer\\dbc\\*.dbc', 'dbc')]
hiddenimports = ['yaml', 'wrapt', 'packaging', 'typing_extensions']
datas += copy_metadata('python-can')
datas += copy_metadata('cantools')
hiddenimports += collect_submodules('can')
hiddenimports += collect_submodules('cantools')


a = Analysis(
    ['Z:\\My Drive\\fastboi\\pyCANstreamViewer\\src\\pycanstreamviewer\\__main__.py'],
    pathex=[],
    binaries=[],
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
    [],
    exclude_binaries=True,
    name='pycanstreamviewer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
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
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='pycanstreamviewer',
)
