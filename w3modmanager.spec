# -*- mode: python -*-

from os import path
from pathlib import Path
from shutil import rmtree

from PyInstaller.building.build_main import COLLECT, EXE, PYZ, Analysis


runtime_hooks = ['./runtime.py'] if path.isfile('./runtime.py') else []

a = Analysis(
    ['./w3modmanager/__main__.py'],
    pathex=['./w3modmanager'],
    binaries=[],
    datas=[('resources', 'resources')],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=runtime_hooks,
    excludes=[
        # ignore unused Qt libraries
        'PySide6.QtBluetooth',
        'PySide6.QtCharts',
        'PySide6.QtDataVisualization',
        'PySide6.QtDesigner',
        'PySide6.QtLocation',
        'PySide6.QtMultimedia',
        'PySide6.QtNetwork',
        'PySide6.QtOpenGL',
        'PySide6.QtOpenGLWidgets',
        'PySide6.QtPdf',
        'PySide6.QtPdfWidgets',
        'PySide6.QtPrintSupport',
        'PySide6.QtQml',
        'PySide6.QtQuick',
        'PySide6.QtQuick3D',
        'PySide6.QtQuickControls2',
        'PySide6.QtQuickWidgets',
        'PySide6.QtSql',
        'PySide6.QtTest',
        'PySide6.QtTextToSpeech',
        'PySide6.QtUiTools',
        'PySide6.QtWebChannel',
        'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineWidgets',
        'PySide6.QtWebSockets',
        # ignore lib2to3
        'lib2to3'
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False
)
pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=None
)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='w3modmanager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=False,
    console=False,
    icon='./resources/icons/w3b.ico'
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='w3modmanager'
)

# remove unused files from the distribution
remove = [
    'Qt6Network.dll',
    'Qt6OpenGL.dll',
    'Qt6Pdf.dll',
    'Qt6Qml.dll',
    'Qt6QmlModels.dll',
    'Qt6Quick.dll',
    'Qt6VirtualKeyboard.dll',
    'translations'
]
dist = Path(coll.name)
for filename in remove:
    target = dist.joinpath('PySide6').joinpath(filename)
    if target.is_file():
        target.unlink()
    if target.is_dir():
        rmtree(target)
