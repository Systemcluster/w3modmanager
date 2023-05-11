"""
w3modmanager - Mod Manager for The Witcher 3 - main module
"""


import w3modmanager

import asyncio
import os
import sys
import traceback

from argparse import ArgumentParser
from concurrent.futures.thread import ThreadPoolExecutor
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, NoReturn

import appdirs

from loguru import logger


# check running python version

if sys.version_info < w3modmanager.MIN_PYTHON_VERSION:
    sys.exit('error: python >= {}.{} is required for this program.'.format(
        *w3modmanager.MIN_PYTHON_VERSION))


# setup Qt environment

if 'QT_DEVICE_PIXEL_RATIO' in os.environ:
    del os.environ['QT_DEVICE_PIXEL_RATIO']
os.environ['QT_API'] = 'pyside6'


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


# setup print override

def debug_print(arg: Any) -> None:
    import builtins

    from inspect import currentframe, getframeinfo
    frame = currentframe()
    if frame and frame.f_back:
        frameinfo = getframeinfo(frame.f_back)
        builtins.print(frameinfo.filename + ':' + str(frameinfo.lineno), arg)
    else:
        builtins.print(arg)


print = debug_print  # noqa: A001


# setup exception hook

sys._excepthook = sys.excepthook  # type: ignore


def exception_hook(exctype, value, tb) -> None:  # type: ignore # noqa
    time = datetime.now(tz=None).strftime('%Y-%m-%d-%H%M%S%z')  # noqa: DTZ005
    with open(f'crash-{time}.txt', 'w', encoding='utf8') as file:
        file.write(f'{w3modmanager.NAME} crashed.\n\n')
        file.write(f'App version: {w3modmanager.VERSION} ({w3modmanager.VERSION_HASH})\n')
        file.write(f'Date: {time}\n')
        file.write(f'Exception Type: {exctype}\n')
        file.write(f'Exception Value: {value}\n\n')
        file.write(f'Traceback:\n')
        file.writelines(traceback.format_tb(tb))
    sys._excepthook(exctype, value, traceback)  # type: ignore
    sys.exit(value if value else 1)


sys.excepthook = exception_hook


# start main program

class StartupMode(Enum):
    Main = 0
    Settings = 1
    About = 2


def main(gamePath: str | None = None,
         configPath: str | None = None,
         startupMode: StartupMode = StartupMode.Main) -> NoReturn:

    from w3modmanager.core.errors import InvalidConfigPath, InvalidGamePath, OtherInstanceError
    from w3modmanager.core.model import Model
    from w3modmanager.domain.system.permissions import getWritePermissions, setWritePermissions
    from w3modmanager.domain.web.nexus import closeSession
    from w3modmanager.ui.graphical.mainwindow import MainWindow
    from w3modmanager.util.util import getRuntimePath

    from PySide6.QtCore import QSettings, Qt
    from PySide6.QtGui import QFont, QIcon, QPalette
    from PySide6.QtWidgets import QApplication, QMessageBox
    from qasync import QEventLoop

    QApplication.setOrganizationName(w3modmanager.ORG_NAME)
    QApplication.setOrganizationDomain(w3modmanager.ORG_URL)
    QApplication.setApplicationName(w3modmanager.TITLE)
    QApplication.setApplicationVersion(w3modmanager.VERSION)
    QApplication.setApplicationDisplayName('')
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseDesktopOpenGL)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling)
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv)
    app.setStyleSheet('''
        Link {
            text-decoration: none;
        }
        QMainWindow,
        QDialog,
        QSplitter::handle {
            background: white;
        }
        QScrollBar:horizontal {
            border: 0;
            background: #eee;
            height: 10px;
        }
        QScrollBar:vertical {
            border: 0;
            background: #eee;
            width: 10px;
        }
        QScrollBar::handle:horizontal {
            background: lightblue;
            min-width: 20px;
        }
        QScrollBar::handle:vertical {
            background: lightblue;
            min-height: 20px;
        }
        QScrollBar::handle:vertical:hover,
        QScrollBar::handle:horizontal:hover {
            background: #82c8df;
        }
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical,
        QScrollBar::add-line:horizontal,
        QScrollBar::sub-line:horizontal {
            border: 0;
            background: transparent;
            width: 0px;
            height: 0px;
        }
        QTableView {
            gridline-color: white;
            padding: 0;
            border: 1px solid #cacaca;
        }
        QTableView::item {
            padding: 5px;
            margin: 1px 0;
        }
        QTableView::item:!selected:hover {
            background: rgb(217, 235, 249);
            padding: 0;
        }
        QTableView::item:selected {
            background: rgb(70, 145, 225);
            padding: 0;
        }
        QLineEdit {
            outline: none;
            border: 1px solid #cacaca;
            selection-background-color: rgb(70, 145, 225);
        }
        QTextEdit {
            outline: none;
            border: 1px solid #cacaca;
            selection-background-color: rgb(70, 145, 225);
        }
        QMenu {
            border: 1px solid #cacaca;
            background: white;
            padding: 3px 0;
            border-radius: 3px;
        }
        QMenu::item {
            background: transparent;
            padding: 4px 20px 4px 15px;
            margin: 0;
            color: black;
        }
        QMenu::item:disabled {
            color: gray;
        }
        QMenu::item:selected {
            background: rgb(217, 235, 249);
        }
        QMenu::icon {
            margin: 0;
            padding: 4px 6px;
        }
        QMenu::icon:checked {
            background: rgb(237, 245, 249);
        }
        QMenu::icon:checked:selected {
            background: rgb(217, 235, 249);
        }
        QMenu::indicator {
            margin: 0 -7px 0 0;
            padding: 4px 6px;
            width: 16px;
            height: 16px;
        }
        QMenu::indicator:non-exclusive:checked {
            image: url(resources/icons/check.ico);
            background: rgb(237, 245, 249);
        }
        QMenu::indicator:non-exclusive:checked:selected {
            background: rgb(217, 235, 249);
        }
        QMenu::separator {
            height: 1px;
            background: #cacaca;
            margin: 3px 0;
        }
    ''')

    eventloop = QEventLoop(app)
    asyncio.set_event_loop(eventloop)

    palette = QPalette(QApplication.palette())
    palette.setColor(QPalette.ColorRole.Link, Qt.GlobalColor.red)
    palette.setColor(QPalette.ColorRole.LinkVisited, Qt.GlobalColor.red)
    palette.setColor(QPalette.ColorRole.PlaceholderText, Qt.GlobalColor.gray)
    app.setPalette(palette)

    font = QFont('Segoe UI')
    font.setStyleHint(QFont.StyleHint.System)
    font.setWeight(QFont.Weight.Normal)
    font.setStyleStrategy(QFont.StyleStrategy.PreferDevice)
    font.setPointSize(9)
    app.setFont(font)

    icon = QIcon()
    icon.addFile(str(getRuntimePath('resources/icons/w3b.ico')))
    app.setWindowIcon(icon)

    import logging
    logging.basicConfig()
    logging.getLogger().setLevel(logging.WARNING)

    pool = ThreadPoolExecutor()
    asyncio.get_running_loop().set_default_executor(pool)

    # configure startup overrides
    settings = QSettings()
    if gamePath:
        settings.setValue('gamePath', gamePath)
    if configPath:
        settings.setValue('configPath', configPath)
    if startupMode == StartupMode.About:
        MainWindow.showAboutDialog(None).exec_()
        sys.exit()
    if startupMode == StartupMode.Settings:
        MainWindow.showSettingsDialog(None).exec_()
        sys.exit()

    exception_hook_set = False

    def createModel(ignorelock: bool = False) -> Model:
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
            if MainWindow.showOtherInstanceDialog(None).exec_() == QMessageBox.StandardButton.Yes:
                model = createModel(True)
            else:
                raise e
        # if game path or config path is invalid or not set,
        # show a special settings dialog and retry
        except (InvalidGamePath, InvalidConfigPath):
            MainWindow.showSettingsDialog(None, True).exec_()
            model = createModel()

        # check for write access to the game and config directories
        for path in (model.gamepath, model.configpath, model.cachepath,):
            if not getWritePermissions(path):
                if MainWindow.showInvalidPermissionsDialog(None, path).exec_() != QMessageBox.StandardButton.Yes \
                or not setWritePermissions(path):
                    raise PermissionError(f'Not enough permissions for {path}')

        window = MainWindow(model)
        app.setActiveWindow(window)

        def show_exception_hook(exctype, value, tb) -> None:  # type: ignore # noqa
            nonlocal window
            MainWindow.showCritcalErrorDialog(window, value, ''.join(
                traceback.format_exception(exctype, value, tb))).exec_()
            exception_hook(exctype, value, tb)
        sys.excepthook = show_exception_hook
        exception_hook_set = True

        with eventloop:
            status = eventloop.run_forever()
            eventloop.run_until_complete(closeSession())
            sys.exit(status)

    except OtherInstanceError as e:
        sys.exit(f'error: {e!s}')

    except (InvalidGamePath, InvalidConfigPath) as e:
        MainWindow.showInvalidConfigErrorDialog(None).exec_()
        sys.exit(f'error: {e!s}')

    except PermissionError as e:
        MainWindow.showInvalidPermissionsErrorDialog(None).exec_()
        sys.exit(f'error: {e!s}')

    except Exception as e:
        if not exception_hook_set:
            MainWindow.showCritcalErrorDialog(None, str(e)).exec_()
        raise e

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
