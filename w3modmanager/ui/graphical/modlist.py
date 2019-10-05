from pathlib import Path
from urllib.parse import urlparse
from typing import Union, List, Tuple

from loguru import logger

from qtpy.QtCore import Qt, QSettings, QUrl, QPoint, QItemSelectionModel
from qtpy.QtWidgets import QApplication, QStyledItemDelegate, \
    QStyleOptionViewItem, \
    QStyle, QAbstractItemView, QWidget, QTableView
from qtpy.QtGui import QPen, QColor, QKeySequence, QKeyEvent, QMouseEvent

from w3modmanager.core.model import Model, ModExistsError, ModNotFoundError
from w3modmanager.util.util import *
from w3modmanager.domain.mod.fetcher import *
from w3modmanager.domain.mod.mod import Mod
from w3modmanager.ui.graphical.modlistmodel import ModListModel


class ModListItemDelegate(QStyledItemDelegate):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.linepen = QPen(QColor(200, 200, 200), 0, parent.gridStyle())

    def paint(self, painter, option, index):
        itemOption = QStyleOptionViewItem(option)

        # disable focus outline
        if itemOption.state & QStyle.State_HasFocus:
            itemOption.state ^= QStyle.State_HasFocus
        if index.row() == option.styleObject.hoverIndexRow:
            itemOption.state |= QStyle.State_MouseOver
        if index.column() in (5, 11):
            oldpen = painter.pen()
            painter.setPen(self.linepen)
            painter.drawLine(
                option.rect.topRight() + QPoint(2, 0),
                option.rect.bottomRight() + QPoint(2, 0)
            )
            painter.setPen(oldpen)

        super().paint(painter, itemOption, index)


class ModListSelectionModel(QItemSelectionModel):
    def setCurrentIndex(self, index, command):
        if not index.isValid():
            return
        # always focus column 2
        index = self.model().index(index.row(), 2)
        super().setCurrentIndex(index, command)


class ModList(QTableView):
    def __init__(self, parent: QWidget, model: Model):
        super().__init__(parent)

        self.hoverIndexRow = -1
        self._model = model

        self.setMouseTracking(True)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setWordWrap(False)
        self.setSortingEnabled(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAcceptDrops(True)

        self.setStyleSheet('''
            QTableView {
                gridline-color: rgba(255,255,255,1);
            }
            QTableView::item {
                padding: 5px;
                margin: 1px 0;
            }
            QTableView::item:!selected:hover {
                background-color: rgb(217, 235, 249);
                padding: 0;
            }
            ''')

        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setContextMenuPolicy(Qt.CustomContextMenu)

        self.setVerticalHeader(None)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(25)
        self.setCornerButtonEnabled(False)
        self.horizontalHeader().setHighlightSections(False)
        self.horizontalHeader().setStretchLastSection(True)
        # self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

        self.setItemDelegate(ModListItemDelegate(self))
        self.setModel(ModListModel(self, model))
        self.setSelectionModel(ModListSelectionModel(self.model()))

        self.resizeColumnsToContents()
        self.sortByColumn(2, Qt.AscendingOrder)
        self.sortByColumn(1, Qt.AscendingOrder)
        self.sortByColumn(3, Qt.AscendingOrder)
        self.horizontalHeader().sortIndicatorChanged.connect(self.sortByColumn)

        self.setFocus()

        QApplication.clipboard().dataChanged.connect(self.copyBufferChanged)

        # TODO: enhancement: notify of inconsistencies like enabled-but-unconfigured-mods

    def modelUpdateEvent(self, model: Model):
        self.sortByColumn()

    def mouseMoveEvent(self, event: QMouseEvent):
        self.hoverIndexRow = self.indexAt(event.pos()).row()
        return super().mouseMoveEvent(event)

    def selectionChanged(self, selected, deselected):
        return super().selectionChanged(selected, deselected)

    def eventFilter(self, obj, event):
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event: QKeyEvent):
        if event.matches(QKeySequence.Paste):
            self.pasteEvent()
        elif event.matches(QKeySequence.Delete):
            for index in self.selectionModel().selectedRows():
                mod: Mod = self.model().getMod(index.row())
                try:
                    self._model.remove(mod.filename)
                except ModNotFoundError:
                    logger.bind(name=mod.filename).warning('Mod not found')
            self.model().update(self._model)
            self.model().sort()
            self.repaint()
        return super().keyPressEvent(event)

    def copyBufferChanged(self):
        if QSettings().value('nexusCheckClipboard', 'False') == 'True':
            self.checkInstallFromURLs(QApplication.clipboard().text().splitlines(), local=False)

    def pasteEvent(self):
        self.checkInstallFromURLs(QApplication.clipboard().text().splitlines())

    def checkInstallFromURLs(self, paths: List[Union[str, QUrl]], local=True, web=True):
        installed = 0
        errors = 0
        installedBefore = len(self._model)
        logger.bind(newline=True, output=False).debug('Starting install from URLs')
        try:
            for path in paths:
                if isinstance(path, QUrl):
                    path = path.toString()
                if web and isValidNexusModsUrl(path):
                    self.setDisabled(True)
                    logger.bind(dots=True, path=path).info(f'Installing mods from')
                    i, e = self.installFromNexusmods(path)
                    installed += i
                    errors += e
                elif local and isValidFileUrl(path):
                    self.setDisabled(True)
                    localpath = Path(QUrl(path).toLocalFile())
                    logger.bind(dots=True, path=localpath).info(f'Installing mods from')
                    i, e = self.installFromFile(localpath)
                    installed += i
                    errors += e
        except Exception as e:
            # we should never land here, but don't lock up the UI if it happens
            logger.critical(str(e))

        if installed > 0 or errors > 0:
            log = logger.bind()
            if installed > 0 and errors > 0:
                log = log.warning
            elif installed > 0:
                log = log.success
            else:
                log = log.error
            log('Installed {0} mods {1}'.format(installed, f'({errors} errors)' if errors else ''))
        if not installedBefore:
            # if list was empty before, auto resize columns
            self.resizeColumnsToContents()
        self.setDisabled(False)

    def installFromNexusmods(self, url: str) -> Tuple[int, int]:
        # TODO: incomplete: ask if install and which files
        return 0, 0

    def installFromFile(self, path: Path) -> Tuple[int, int]:
        installed = 0
        errors = 0
        try:
            mods = Mod.fromPath(path)
            # TODO: incomplete: fix mod name, package, etc
            for mod in mods:
                # TODO: incomplete: check if mod is installed, ask if replace
                try:
                    self._model.add(mod)
                    installed += 1
                except ModExistsError:
                    logger.bind(path=path, name=mod.modname).error(f'Mod exists')
                    errors += 1
            self.model().update(self._model)
            self.model().sort()
        except InvalidPathError as e:
            # TODO: enhancement: better install error message
            logger.bind(path=e.path).error(e.message)
            errors += 1
        return installed, errors

    def dropEvent(self, event):
        event.accept()
        self.setDisabled(True)
        self.repaint()
        self.checkInstallFromURLs(event.mimeData().urls())
        self.setDisabled(False)

    def dragEnterEvent(self, event):
        self.setDisabled(True)
        self.repaint()
        urls = event.mimeData().urls()
        if not urls:
            self.setDisabled(False)
            event.ignore()
            return
        for url in urls:
            parse = urlparse(url.toString())
            if parse.scheme not in ['file']:
                self.setDisabled(False)
                event.ignore()
                return
            filepath = Path(url.toLocalFile())
            if not isArchive(filepath) and not containsValidMod(filepath):
                self.setDisabled(False)
                event.ignore()
                return
        self.setDisabled(False)
        event.accept()

    def dragMoveEvent(self, event):
        event.accept()

    def dragLeaveEvent(self, event):
        event.accept()
