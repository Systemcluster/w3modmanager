from pathlib import Path
from urllib.parse import urlparse
from typing import Union, List, Tuple

from loguru import logger

from qtpy.QtCore import Qt, QSettings, QUrl, QPoint, QItemSelectionModel
from qtpy.QtWidgets import QApplication, QStyledItemDelegate, \
    QStyleOptionViewItem, QStyle, QAbstractItemView, QWidget, \
    QTableView, QMessageBox, QPushButton
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
                    self._model.remove(mod)
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
                    path = Path(QUrl(path).toLocalFile())
                    logger.bind(dots=True, path=path).info(f'Installing mods from')
                    i, e = self.installFromFile(path)
                    installed += i
                    errors += e
        except Exception as e:
            # we should never land here, but don't lock up the UI if it happens
            logger.exception(e)
            errors += 1

        if installed > 0 or errors > 0:
            log = logger.bind(modlist=bool(installed))
            if installed > 0 and errors > 0:
                log = log.warning
            elif installed > 0:
                log = log.success
            else:
                log = log.error
            log('Installed {0} mods{1}'.format(installed, f' ({errors} errors)' if errors else ''))
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
        archive = path.is_file()
        source = None
        md5hash = ''
        try:
            if archive:
                logger.bind(path=str(path), dots=True).debug('Unpacking archive')
                md5hash = getMD5Hash(path)
                source = path
                path = extractMod(path)
            valid, exhausted = containsValidMod(path, searchlimit=8)
            if not valid:
                if not exhausted and self.showContinueSearchDialog(searchlimit=8):
                    if not containsValidMod(path):
                        raise InvalidPathError(path, 'Invalid mod')
                elif not exhausted:
                    raise InvalidPathError(path, 'Stopped searching for mod')
                else:
                    raise InvalidPathError(path, 'Invalid mod')
            mods = Mod.fromDirectory(path, searchCommonRoot=not archive)
            for mod in mods:
                mod.md5hash = md5hash
                if source:
                    mod.source = source
                try:
                    # TODO: incomplete: check if mod is installed, ask if replace
                    self._model.add(mod)
                    installed += 1
                except ModExistsError:
                    logger.bind(path=path, name=mod.filename).error(f'Mod exists')
                    errors += 1
            self.model().update(self._model)
            self.model().sort()
        except InvalidPathError as e:
            # TODO: enhancement: better install error message
            logger.bind(path=e.path).error(e.message)
            errors += 1
        finally:
            if archive:
                shutil.rmtree(path, onerror=lambda f, path, e: logger.bind(path=path).warning(
                    'Could not remove temporary directory'
                ))
        return installed, errors

    def showContinueSearchDialog(self, searchlimit: int):
        messagebox = QMessageBox(self)
        messagebox.setWindowTitle('Unusual search depth')
        messagebox.setText(f'''
            <p>No mod detected after searching through {searchlimit} directories.</p>
            <p>Are you sure this is a valid mod?</p>
            ''')
        messagebox.setTextFormat(Qt.RichText)
        messagebox.setStandardButtons(QMessageBox.Cancel)
        yes: QPushButton = QPushButton(' Yes, continue searching ', messagebox)
        yes.setAutoDefault(True)
        yes.setDefault(True)
        messagebox.addButton(yes, QMessageBox.YesRole)
        messagebox.exec_()
        return messagebox.clickedButton() == yes

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
            try:
                parse = urlparse(url.toString())
                if parse.scheme not in ['file']:
                    self.setDisabled(False)
                    event.ignore()
                    return
                filepath = Path(url.toLocalFile())
                if isArchive(filepath) or containsValidMod(filepath, searchlimit=8)[0]:
                    self.setDisabled(False)
                    event.accept()
                    return
            except Exception as e:
                logger.debug(str(e))
        self.setDisabled(False)
        event.ignore()

    def dragMoveEvent(self, event):
        event.accept()

    def dragLeaveEvent(self, event):
        event.accept()
