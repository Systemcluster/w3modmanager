"""
w3modmanager - Mod Manager for The Witcher 3 - main module
"""


import sys
import os
from pathlib import Path

import appdirs

import w3modmanager


# check running python version
if sys.version_info < w3modmanager.MIN_PYTHON_VERSION:
    sys.exit('error: python >= %s.%s is required for this program.' \
        % w3modmanager.MIN_PYTHON_VERSION)

# setup Qt environment
if 'QT_DEVICE_PIXEL_RATIO' in os.environ:
    del os.environ['QT_DEVICE_PIXEL_RATIO']
os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '1'
os.environ['QT_API'] = 'pyside2'


from w3modmanager.util.util import getRuntimePath
from w3modmanager.core.model import Model, OtherInstanceError, \
    InvalidGamePath, InvalidConfigPath, InvalidCachePath
from w3modmanager.ui.graphical.mainwindow import MainWindow

from qtpy.QtCore import Qt, QSettings
from qtpy.QtWidgets import QApplication
from qtpy.QtGui import QIcon, QPalette


QApplication.setOrganizationName(w3modmanager.ORG_NAME)
QApplication.setOrganizationDomain(w3modmanager.ORG_URL)
QApplication.setApplicationName(w3modmanager.TITLE)
QApplication.setApplicationVersion(w3modmanager.VERSION)
QApplication.setApplicationDisplayName(None)
QApplication.setAttribute(Qt.AA_NativeWindows)
QApplication.setAttribute(Qt.AA_DisableWindowContextHelpButton)

app = QApplication(sys.argv)
app.setStyleSheet('''
    Link { text-decoration: none; }
    ''')

palette = QPalette(app.palette())
palette.setColor(QPalette.Link, Qt.red)
palette.setColor(QPalette.LinkVisited, Qt.red)
palette.setColor(QPalette.LinkVisited, Qt.red)
app.setPalette(palette)

icon = QIcon()
icon.addFile(str(getRuntimePath('resources/icons/w3b.ico')))
app.setWindowIcon(icon)

try:
    settings = QSettings()

    # try to initialize the mod management model
    try:
        model = Model(
            Path(str(settings.value('gamePath'))),
            Path(str(settings.value('configPath'))),
            Path(appdirs.user_data_dir(w3modmanager.NAME, w3modmanager.ORG_NAME)))
    except (InvalidGamePath, InvalidConfigPath):
        # if game path or config path is invalid or not set, show a special settings dialog
        # and retry
        MainWindow.showSettingsDialog(None, True)
        try:
            model = Model(
                Path(str(settings.value('gamePath'))),
                Path(str(settings.value('configPath'))),
                Path(appdirs.user_data_dir(w3modmanager.NAME, w3modmanager.ORG_NAME)))
        except (InvalidGamePath, InvalidConfigPath) as e:
            MainWindow.showInvalidConfigDialog(None)
            sys.exit(f'error: {str(e)}')

    window = MainWindow(model)
    app.setActiveWindow(window)
    sys.exit(app.exec_())

except OtherInstanceError as e:
    # TODO: incomplete: ask to start anyway
    raise e

except InvalidCachePath as e:
    # TODO: enhancement: show informative message
    raise e

except Exception as e:
    MainWindow.showCritcalErrorDialog(None, str(e))
    sys.exit(f'error: {str(e)}')
