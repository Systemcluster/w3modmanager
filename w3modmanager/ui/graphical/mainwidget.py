from w3modmanager.core.model import Model
from w3modmanager.ui.graphical.modlist import ModList
from w3modmanager.util.util import getRuntimePath

import html

from loguru import logger
from qtpy.QtCore import QSettings, Qt
from qtpy.QtWidgets import QVBoxLayout, QSplitter, QWidget, QTextEdit, \
    QLabel, QStackedWidget, QLineEdit
from qtpy.QtGui import QFont, QPixmap


class MainWidget(QWidget):
    def __init__(self, parent: QWidget, model: Model):
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
        self.modlistlayout.setMargin(0)
        self.modlistwidget.setLayout(self.modlistlayout)
        self.stack.addWidget(self.modlistwidget)

        # search bar

        # TODO: incomplete: make search bar functional
        searchbar = QLineEdit()
        searchbar.setPlaceholderText('Search...')
        self.modlistlayout.addWidget(searchbar)

        # mod list

        modlist = ModList(self, model)
        self.modlistlayout.addWidget(modlist)

        # welcome message

        welcomelayout = QVBoxLayout()
        welcomelayout.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        welcomewidget = QWidget()
        welcomewidget.setLayout(welcomelayout)
        welcomewidget.dragEnterEvent = lambda e: [
            modlist.dragEnterEvent(e)
        ]
        welcomewidget.dragMoveEvent = lambda e: [
            modlist.dragMoveEvent(e)
        ]
        welcomewidget.dragLeaveEvent = lambda e: [
            modlist.dragLeaveEvent(e)
        ]
        welcomewidget.dropEvent = lambda e: [
            modlist.dropEvent(e)
        ]
        welcomewidget.setAcceptDrops(True)

        iconpixmap = QPixmap(str(getRuntimePath('resources/icons/open-folder.ico')))
        iconpixmap = iconpixmap.scaledToHeight(32)
        icon = QLabel()
        icon.setPixmap(iconpixmap)
        icon.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        icon.setMargin(4)
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
        self.outputfont = QFont('monospace')
        self.outputfont.setStyleHint(QFont.Monospace)
        self.output.setFont(self.outputfont)
        self.output.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.output.setReadOnly(True)
        self.output.setTextCursor
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


    def modelUpdateEvent(self, model: Model):
        if len(model) > 0:
            self.stack.setCurrentIndex(0)
        else:
            self.stack.setCurrentIndex(1)

    def unhideOutput(self):
        if self.splitter.sizes()[1] < 10:
            self.splitter.setSizes([self.splitter.size().height(), 50])

    def unhideModList(self):
        if self.splitter.sizes()[0] < 10:
            self.splitter.setSizes([50, self.splitter.size().height()])

    def log(self, message):
        # format log messages to user readable output
        settings = QSettings()

        record = message.record
        message = record['message']
        extra = record['extra']
        level = record['level'].lower()

        name = str(extra['name']) if 'name' in extra else ''
        path = str(extra['path']) if 'path' in extra else ''
        dots = bool(extra['dots']) if 'dots' in extra else False
        newline = bool(extra['newline']) if 'newline' in extra else False
        output = bool(extra['output']) if 'output' in extra else bool(len(message))
        modlist = bool(extra['modlist']) if 'modlist' in extra else False

        if level in ['debug'] and settings.value('debugOutput') != 'True':
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
        if settings.value('unhideOutput') == 'True' and output:
            self.unhideOutput()
