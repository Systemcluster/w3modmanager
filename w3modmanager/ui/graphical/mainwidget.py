from w3modmanager.core.model import Model
from w3modmanager.ui.graphical.modlist import ModList
from w3modmanager.util.util import getRuntimePath

import html
from typing import Any

from loguru import logger
from qtpy.QtCore import QSettings, Qt
from qtpy.QtWidgets import QVBoxLayout, QSplitter, QWidget, QTextEdit, \
    QLabel, QStackedWidget, QLineEdit
from qtpy.QtGui import QKeyEvent, QKeySequence, QIcon


class MainWidget(QWidget):
    def __init__(self, parent: QWidget, model: Model) -> None:
        super().__init__(parent)

        logger.add(self.log)

        self.mainlayout = QVBoxLayout()
        self.setLayout(self.mainlayout)

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
        welcomewidget.dragEnterEvent = self.modlist.dragEnterEvent
        welcomewidget.dragMoveEvent = self.modlist.dragMoveEvent
        welcomewidget.dragLeaveEvent = self.modlist.dragLeaveEvent
        welcomewidget.dropEvent = self.modlist.dropEvent
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
        self.output.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.output.setReadOnly(True)
        self.output.setContextMenuPolicy(Qt.NoContextMenu)
        self.output.setPlaceholderText('Program output...')
        self.splitter.addWidget(self.output)

        # TODO: enhancement: add a launch game icon
        # TODO: enhancement: show indicator if scripts have to be merged

        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.mainlayout.addWidget(self.splitter)

        if len(model):
            self.stack.setCurrentIndex(0)
            self.splitter.setSizes([self.splitter.size().height(), 50])
        else:
            self.stack.setCurrentIndex(1)
            self.splitter.setSizes([self.splitter.size().height(), 0])
        model.updateCallbacks.append(self.modelUpdateEvent)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.matches(QKeySequence.Find):
            self.searchbar.setFocus()
        if event.key() == Qt.Key_Escape:
            self.modlist.setFocus()
            self.searchbar.setText('')
        super().keyPressEvent(event)

    def modelUpdateEvent(self, model: Model) -> None:
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

        name = str(extra['name']) if 'name' in extra else ''
        path = str(extra['path']) if 'path' in extra else ''
        dots = bool(extra['dots']) if 'dots' in extra else False
        newline = bool(extra['newline']) if 'newline' in extra else False
        output = bool(extra['output']) if 'output' in extra else bool(len(message))
        modlist = bool(extra['modlist']) if 'modlist' in extra else False

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

            message = f'<font color="#aaa">{record["time"].strftime("%Y-%m-%d %H:%M:%S")}</font> {message}'
            self.output.append(f'{n}{message.strip()} {name}{path}{d}')
        else:
            self.output.append(f'')

        self.output.verticalScrollBar().setValue(self.output.verticalScrollBar().maximum())
        self.output.repaint()

        if modlist:
            self.unhideModList()
        if settings.value('unhideOutput', 'True') == 'True' and output:
            self.unhideOutput()
