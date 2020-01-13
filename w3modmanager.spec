# -*- mode: python -*-

from os import path
from PyInstaller.building.build_main import Analysis, PYZ, EXE


runtime_hooks = ['.\\runtime.py'] if path.isfile('.\\runtime.py') else []

a = Analysis(
    ['.\\w3modmanager\\__main__.py'],
    pathex=['.\\w3modmanager'],
    binaries=[],
    datas=[('resources', 'resources'), ('tools', 'tools')],
    hiddenimports=['distutils'],
    hookspath=[],
    runtime_hooks=runtime_hooks,
    excludes=['PyQt5'],  # ignore QtPy's PyQt5 since we use PySide2
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)
pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=None,
)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='w3modmanager',
    debug=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    uac_admin=False,
    bootloader_ignore_signals=True,
    icon='.\\resources\\icons\\w3b.ico',
)
