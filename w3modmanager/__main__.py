"""
w3modmanager - Mod Manager for The Witcher 3 - main module
"""


import sys
import os
import asyncio
from pathlib import Path
from typing import Optional, NoReturn
from argparse import ArgumentParser
from enum import Enum

import appdirs
from loguru import logger

import w3modmanager


# check running python version
if sys.version_info < w3modmanager.MIN_PYTHON_VERSION:
    sys.exit('error: python >= %s.%s is required for this program.'
             % w3modmanager.MIN_PYTHON_VERSION)

# setup Qt environment
if 'QT_DEVICE_PIXEL_RATIO' in os.environ:
    del os.environ['QT_DEVICE_PIXEL_RATIO']
os.environ['QT_API'] = 'pyside2'

# setup logger if tty is attached
logger.remove(0)
if sys.stdout.isatty():
    logger.add(
        sys.stderr,
        level='TRACE',
        backtrace=True,
        colorize=True,
        filter='w3modmanager',
        format='\
<g>{time:YYYY-MM-DD HH:mm:ss.SSS}</> | \
<level>{level:8}</> | \
<m>{name}</>:<m>{function}</>:<m>{line}</> - \
<level>{message}</> - \
<e>{extra}</>'
    )


class StartupMode(Enum):
    Main = 0
    Settings = 1
    About = 2


def main(gamePath: Optional[str] = None,
         configPath: Optional[str] = None,
         startupMode: StartupMode = StartupMode.Main) -> NoReturn:

    from w3modmanager.util.util import getRuntimePath
    from w3modmanager.core.model import Model
    from w3modmanager.core.errors import OtherInstanceError, InvalidGamePath, InvalidConfigPath
    from w3modmanager.ui.graphical.mainwindow import MainWindow
    from w3modmanager.domain.system.permissions import \
        getWritePermissions, setWritePermissions

    from qtpy.QtCore import Qt, QSettings
    from qtpy.QtWidgets import QApplication
    from qtpy.QtGui import QIcon, QPalette

    from asyncqt import QEventLoop  # noqa


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

    eventloop = QEventLoop(app)
    asyncio.set_event_loop(eventloop)

    palette = QPalette(app.palette())
    palette.setColor(QPalette.Link, Qt.red)
    palette.setColor(QPalette.LinkVisited, Qt.red)
    app.setPalette(palette)

    icon = QIcon()
    icon.addFile(str(getRuntimePath('resources/icons/w3b.ico')))
    app.setWindowIcon(icon)

    # configure startup overrides
    settings = QSettings()
    if gamePath:
        settings.setValue('gamePath', gamePath)
    if configPath:
        settings.setValue('configPath', configPath)
    if startupMode == StartupMode.About:
        MainWindow.showAboutDialog(None)
        sys.exit()
    if startupMode == StartupMode.Settings:
        MainWindow.showSettingsDialog(None)
        sys.exit()

    def createModel(ignorelock=False):
        nonlocal settings
        return Model(
            Path(str(settings.value('gamePath'))),
            Path(str(settings.value('configPath'))),
            Path(appdirs.user_data_dir(w3modmanager.NAME, w3modmanager.ORG_NAME)),
            ignorelock)
    try:
        # try to initialize the mod management model
        try:
            model = createModel()
        # if another instance is already open, inform and ask to open anyway
        except OtherInstanceError as e:
            if MainWindow.showOtherInstanceDialog(None):
                model = createModel(True)
            else:
                raise e
        # if game path or config path is invalid or not set,
        # show a special settings dialog and retry
        except (InvalidGamePath, InvalidConfigPath):
            MainWindow.showSettingsDialog(None, True)
            model = createModel()

        # check for write access to the game and config directories
        for path in (model.gamepath, model.configpath, model.cachepath,):
            if not getWritePermissions(path):
                if not MainWindow.showInvalidPermissionsDialog(None, path) \
                or not setWritePermissions(path):
                    raise PermissionError(f'Not enough permissions for {path}')

        window = MainWindow(model)
        app.setActiveWindow(window)

        with eventloop:
            sys.exit(eventloop.run_forever())

    except OtherInstanceError as e:
        sys.exit(f'error: {str(e)}')

    except (InvalidGamePath, InvalidConfigPath) as e:
        MainWindow.showInvalidConfigErrorDialog(None)
        sys.exit(f'error: {str(e)}')

    except PermissionError as e:
        MainWindow.showInvalidPermissionsErrorDialog(None)
        sys.exit(f'error: {str(e)}')

    except Exception as e:
        MainWindow.showCritcalErrorDialog(None, str(e))
        sys.exit(f'error: {str(e)}')

    sys.exit()


if __name__ == '__main__':
    argp = ArgumentParser(
        prog=w3modmanager.NAME,
        description=w3modmanager.SUBTITLE,
        epilog=f'See {w3modmanager.URL_WEB} for the latest updates.')
    argp.add_argument(
        '-v', '--version', default=False, action='version',
        help='show the version number and exit', version=f'%(prog)s {w3modmanager.VERSION}')
    mode = argp.add_argument_group(
        title='start overrides'
    ).add_mutually_exclusive_group()
    mode.add_argument(
        '--settings', default=False, action='store_true',
        help='open the settings dialog and exit')
    mode.add_argument(
        '--about', default=False, action='store_true',
        help='open the about dialog and exit')
    dirs = argp.add_argument_group(
        title='path overrides')
    dirs.add_argument(
        '-g', '--game-path', type=str, default='',
        help='start with a different game installation path')
    dirs.add_argument(
        '-s', '--config-path', type=str, default='',
        help='start with a different game config path')
    args = argp.parse_args()
    startupMode: StartupMode = StartupMode.Main
    if args.settings:
        startupMode = StartupMode.Settings
    if args.about:
        startupMode = StartupMode.About
    main(args.game_path, args.config_path, startupMode)
