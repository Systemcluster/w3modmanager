from w3modmanager.core.model import Model
from w3modmanager.ui.graphical.modlist import ModList
from w3modmanager.ui.graphical.flowlayout import FlowLayout
from w3modmanager.util.util import getRuntimePath, isValidNexusModsUrl, isValidModDownloadUrl, isValidFileUrl

import html
from typing import Any
import asyncio

from loguru import logger
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSplitter, \
    QStackedWidget, QTextEdit, QVBoxLayout, QWidget
from PySide6.QtGui import QIcon, QKeyEvent, QKeySequence


class MainWidget(QWidget):
    def __init__(self, parent: QWidget, model: Model) -> None:
        super().__init__(parent)

        logger.add(self.log)

        settings = QSettings()
        self.mainlayout = QVBoxLayout()
        self.mainlayout.setContentsMargins(5, 5, 5, 5)
        self.setLayout(self.mainlayout)

        # summary

        summarylayout = FlowLayout()
        summarylayout.setContentsMargins(0, 0, 0, 0)
        self.summary = QWidget()
        self.summary.setLayout(summarylayout)
        self.mainlayout.addWidget(self.summary)
        self.summary.setVisible(settings.value('showSummary', 'True') == 'True')

        detailslayout = QHBoxLayout()
        detailslayout.setContentsMargins(1, 0, 0, 0)
        detailslayout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        detailslayout.setSpacing(15)
        details = QWidget()
        details.setLayout(detailslayout)
        summarylayout.addWidget(details)

        self.modstotal = QLabel()
        detailslayout.addWidget(self.modstotal)
        self.modsenabled = QLabel()
        detailslayout.addWidget(self.modsenabled)

        buttonslayout = QHBoxLayout()
        buttonslayout.setContentsMargins(0, 0, 0, 0)
        buttonslayout.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        buttons = QWidget()
        buttons.setLayout(buttonslayout)
        summarylayout.addWidget(buttons)

        self.startscriptmerger = QPushButton('Start Script Merger')
        self.startscriptmerger.setContentsMargins(0, 0, 0, 0)
        self.startscriptmerger.setMinimumWidth(140)
        self.startscriptmerger.setIcon(QIcon(str(getRuntimePath('resources/icons/script.ico'))))
        buttonslayout.addWidget(self.startscriptmerger)

        self.startgame = QPushButton('Start Game')
        self.startgame.setContentsMargins(0, 0, 0, 0)
        self.startgame.setMinimumWidth(100)
        self.startgame.setIcon(QIcon(str(getRuntimePath('resources/icons/w3b.ico'))))
        buttonslayout.addWidget(self.startgame)

        # splitter

        self.splitter = QSplitter(Qt.Vertical)

        self.stack = QStackedWidget()
        self.splitter.addWidget(self.stack)

        # mod list widget

        self.modlistwidget = QWidget()
        self.modlistlayout = QVBoxLayout()
        self.modlistlayout.setContentsMargins(0, 0, 0, 0)
        self.modlistwidget.setLayout(self.modlistlayout)
        self.stack.addWidget(self.modlistwidget)

        # search bar

        self.searchbar = QLineEdit()
        self.searchbar.setPlaceholderText('Search...')
        self.modlistlayout.addWidget(self.searchbar)

        # mod list

        self.modlist = ModList(self, model)
        self.modlistlayout.addWidget(self.modlist)

        self.searchbar.textChanged.connect(lambda e: self.modlist.setFilter(e))

        # welcome message

        welcomelayout = QVBoxLayout()
        welcomelayout.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        welcomewidget = QWidget()
        welcomewidget.setLayout(welcomelayout)
        welcomewidget.dragEnterEvent = self.modlist.dragEnterEvent  # type: ignore
        welcomewidget.dragMoveEvent = self.modlist.dragMoveEvent  # type: ignore
        welcomewidget.dragLeaveEvent = self.modlist.dragLeaveEvent  # type: ignore
        welcomewidget.dropEvent = self.modlist.dropEvent  # type: ignore
        welcomewidget.setAcceptDrops(True)

        icon = QIcon(str(getRuntimePath('resources/icons/open-folder.ico')))
        iconpixmap = icon.pixmap(32, 32)
        icon = QLabel()
        icon.setPixmap(iconpixmap)
        icon.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        icon.setContentsMargins(4, 4, 4, 4)
        welcomelayout.addWidget(icon)

        welcome = QLabel('''<p><font>
            No mod installed yet.
            Drag a mod into this area to get started!
            </font></p>''')
        welcome.setAttribute(Qt.WA_TransparentForMouseEvents)
        welcome.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        welcomelayout.addWidget(welcome)

        self.stack.addWidget(welcomewidget)

        # output log

        self.output = QTextEdit(self)
        self.output.setTextInteractionFlags(Qt.NoTextInteraction)
        self.output.setReadOnly(True)
        self.output.setContextMenuPolicy(Qt.NoContextMenu)
        self.output.setPlaceholderText('Program output...')
        self.splitter.addWidget(self.output)

        # TODO: enhancement: show indicator if scripts have to be merged

        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.mainlayout.addWidget(self.splitter)

        # TODO: incomplete: make start game / start script merger buttons functional

        if len(model):
            self.stack.setCurrentIndex(0)
            self.splitter.setSizes([self.splitter.size().height(), 50])
        else:
            self.stack.setCurrentIndex(1)
            self.splitter.setSizes([self.splitter.size().height(), 0])
        model.updateCallbacks.append(self.modelUpdateEvent)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key_Escape:
            self.modlist.setFocus()
            self.searchbar.setText('')
        elif event.matches(QKeySequence.Find):
            self.searchbar.setFocus()
        elif event.matches(QKeySequence.Paste):
            self.pasteEvent()
        # TODO: enhancement: add start game / start script merger shortcuts
        else:
            super().keyPressEvent(event)

    def pasteEvent(self) -> None:
        clipboard = QApplication.clipboard().text().splitlines()
        if len(clipboard) == 1 and isValidNexusModsUrl(clipboard[0]):
            self.parentWidget().showDownloadModDialog()
        else:
            urls = [url for url in QApplication.clipboard().text().splitlines() if len(str(url.strip()))]
            if all(isValidModDownloadUrl(url) or isValidFileUrl(url) for url in urls):
                asyncio.create_task(self.modlist.checkInstallFromURLs(urls))

    def modelUpdateEvent(self, model: Model) -> None:
        total = len(model)
        enabled = len([mod for mod in model if model[mod].enabled])
        self.modstotal.setText(
            f'<font color="#73b500" size="4">{total}</font> \
                <font color="#888" text-align="center">Installed Mod{"" if total == 1 else "s"}</font>'
        )
        self.modsenabled.setText(
            f'<font color="#73b500" size="4">{enabled}</font> \
                <font color="#888">Enabled Mod{"" if enabled == 1 else "s"}</font>'
        )

        if len(model) > 0:
            if self.stack.currentIndex() != 0:
                self.stack.setCurrentIndex(0)
                self.repaint()
        else:
            if self.stack.currentIndex() != 1:
                self.stack.setCurrentIndex(1)
                self.repaint()

    def unhideOutput(self) -> None:
        if self.splitter.sizes()[1] < 10:
            self.splitter.setSizes([self.splitter.size().height(), 50])

    def unhideModList(self) -> None:
        if self.splitter.sizes()[0] < 10:
            self.splitter.setSizes([50, self.splitter.size().height()])

    def log(self, message: Any) -> None:
        # format log messages to user readable output
        settings = QSettings()

        record = message.record
        message = record['message']
        extra = record['extra']
        level = record['level'].name.lower()

        name = str(extra['name']) if 'name' in extra and extra['name'] is not None else ''
        path = str(extra['path']) if 'path' in extra and extra['path'] is not None else ''
        dots = bool(extra['dots']) if 'dots' in extra and extra['dots'] is not None else False
        newline = bool(extra['newline']) if 'newline' in extra and extra['newline'] is not None else False
        output = bool(extra['output']) if 'output' in extra and extra['output'] is not None else bool(message)
        modlist = bool(extra['modlist']) if 'modlist' in extra and extra['modlist'] is not None else False

        if level in ['debug'] and settings.value('debugOutput', 'False') != 'True':
            if newline:
                self.output.append(f'')
            return

        n = '<br>' if newline else ''
        d = '...' if dots else ''
        if len(name) and len(path):
            path = f' ({path})'

        if output:
            message = html.escape(message, quote=True)

            if level in ['success', 'error', 'warning']:
                message = f'<strong>{message}</strong>'
            if level in ['success']:
                message = f'<font color="#04c45e">{message}</font>'
            if level in ['error', 'critical']:
                message = f'<font color="#ee3b3b">{message}</font>'
            if level in ['warning']:
                message = f'<font color="#ff6500">{message}</font>'
            if level in ['debug', 'trace']:
                message = f'<font color="#aaa">{message}</font>'
                path = f'<font color="#aaa">{path}</font>' if path else ''
                d = f'<font color="#aaa">{d}</font>' if d else ''

            time = record['time'].astimezone(tz=None).strftime('%Y-%m-%d %H:%M:%S')
            message = f'<font color="#aaa">{time}</font> {message}'
            self.output.append(f'{n}{message.strip()}{" " if name or path else ""}{name}{path}{d}')
        else:
            self.output.append(f'')

        self.output.verticalScrollBar().setValue(self.output.verticalScrollBar().maximum())
        self.output.repaint()

        if modlist:
            self.unhideModList()
        if settings.value('unhideOutput', 'True') == 'True' and output:
            self.unhideOutput()
