from pathlib import Path
from urllib.parse import urlparse
from typing import Union, List, Tuple
from datetime import datetime

from loguru import logger

from qtpy.QtCore import Qt, QSettings, QUrl, QPoint, \
    QItemSelectionModel, QSortFilterProxyModel, QAbstractItemModel, \
    QAbstractTableModel, QRect, QModelIndex, QItemSelection, \
    QObject, QEvent, QTimer, QSize
from qtpy.QtWidgets import QApplication, QStyledItemDelegate, \
    QStyleOptionViewItem, QStyle, QAbstractItemView, QWidget, \
    QTableView, QMessageBox, QPushButton
from qtpy.QtGui import QPen, QColor, QKeySequence, QKeyEvent, QMouseEvent, QPainter, QPixmap

from w3modmanager.core.model import Model, ModExistsError, ModNotFoundError
from w3modmanager.util.util import *
from w3modmanager.domain.mod.fetcher import *
from w3modmanager.domain.mod.mod import Mod
from w3modmanager.ui.graphical.modlistmodel import ModListModel


class ModListItemDelegate(QStyledItemDelegate):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.linepen = QPen(QColor(200, 200, 200), 0, parent.gridStyle())

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        itemOption = QStyleOptionViewItem(option)

        # disable focus outline
        if itemOption.state & QStyle.State_HasFocus:
            itemOption.state ^= QStyle.State_HasFocus
        # hover whole row
        if index.row() == option.styleObject.hoverIndexRow:
            itemOption.state |= QStyle.State_MouseOver
        # draw lines around numeric columns
        if index.column() in (5, 11):
            oldpen = painter.pen()
            painter.setPen(self.linepen)
            painter.drawLine(
                itemOption.rect.topRight() + QPoint(2, 0),
                itemOption.rect.bottomRight() + QPoint(2, 0)
            )
            painter.setPen(oldpen)

        super().paint(painter, itemOption, index)

    def updateEditorGeometry(self, editor: QWidget, option: QStyleOptionViewItem, index: QModelIndex):
        itemOption = QStyleOptionViewItem(option)
        # set size of editor to size of cell
        geom: QRect = QApplication.style().subElementRect(QStyle.SE_ItemViewItemText, itemOption, editor)
        geom.setTop(geom.top())
        editor.setGeometry(geom)


class ModListSelectionModel(QItemSelectionModel):
    def __init__(self, parent: QWidget, model: QAbstractItemModel):
        super().__init__(model, parent)

    def setCurrentIndex(self, index, command):
        if not index.isValid():
            return
        # always focus column 3
        index = self.model().index(index.row(), 3)
        super().setCurrentIndex(index, command)


class ModListFilterModel(QSortFilterProxyModel):
    def __init__(self, parent: QWidget, source: QAbstractTableModel):
        super().__init__(parent)
        self.setSourceModel(source)
        self.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.setSortCaseSensitivity(Qt.CaseInsensitive)
        self.setFilterKeyColumn(3)
        self.setSortRole(Qt.UserRole)
        # TODO: enhancement: filter for multiple columns


class ModList(QTableView):
    def __init__(self, parent: QWidget, model: Model):
        super().__init__(parent)

        self.hoverIndexRow = -1
        self.modmodel = model

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
        self.horizontalHeader().setSectionsMovable(True)
        # self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

        self.listmodel = ModListModel(self, model)
        self.filtermodel = ModListFilterModel(self, self.listmodel)
        self.setModel(self.filtermodel)

        self.setItemDelegate(ModListItemDelegate(self))
        self.setSelectionModel(ModListSelectionModel(self, self.filtermodel))

        self.resizeColumnsToContents()

        settings = QSettings()
        if settings.value('modlistHorizontalHeaderState'):
            self.horizontalHeader().restoreState(settings.value('modlistHorizontalHeaderState'))

        self.horizontalHeader().sectionMoved.connect(lambda: self.headerChangedEvent())
        self.horizontalHeader().sectionResized.connect(lambda: self.headerChangedEvent())

        self.setFocus()

        self.sortByColumn(3, Qt.AscendingOrder, False)
        self.sortByColumn(2, Qt.AscendingOrder, False)
        self.sortByColumn(1, Qt.AscendingOrder, False)
        if settings.value('modlistSortColumn') is not None and \
           settings.value('modlistSortOrder') is not None:
            try:
                self.sortByColumn(
                    settings.value('modlistSortColumn', 1, int),
                    Qt.SortOrder(settings.value('modlistSortOrder', 1, int)),
                    False
                )
            except Exception as e:
                print(f'could not restore sort order: {e}')
        self.horizontalHeader().sortIndicatorChanged.connect(self.sortByColumn)

        QApplication.clipboard().dataChanged.connect(self.copyBufferChanged)
        self.doubleClicked.connect(self.doubleClickEvent)
        model.updateCallbacks.append(self.modelUpdateEvent)

        # setup viewport caching to counter slow resizing with many table elements
        self.resizeTimer = QTimer(self)
        self.resizeTimer.setSingleShot(True)
        self.resizeTimer.setInterval(250)
        self.resizeTimer.timeout.connect(lambda: [
            self.resizeTimer.stop(),
            self.viewport().repaint(),
        ])
        self.viewportCache = QPixmap()
        self.viewportCacheSize = QSize(0, 0)

        # TODO: enhancement: notify of inconsistencies like enabled-but-unconfigured-mods

        # TODO: enhancement: offer option to read readme and other additional text files

    @debounce(200)
    def headerChangedEvent(self):
        settings = QSettings()
        settings.setValue('modlistHorizontalHeaderState', self.horizontalHeader().saveState())

    def modelUpdateEvent(self, model: Model):
        pass

    def mouseMoveEvent(self, event: QMouseEvent):
        self.hoverIndexRow = self.indexAt(event.pos()).row()
        return super().mouseMoveEvent(event)

    def doubleClickEvent(self, index: QModelIndex):
        if self.filtermodel.mapToSource(index).column() == 0:
            mod = self.modmodel[self.filtermodel.mapToSource(index).row()]
            if mod.enabled:
                self.modmodel.disable(mod)
            else:
                self.modmodel.enable(mod)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self.resizeTimer.isActive() and event.size() != self.viewportCacheSize:
            self.viewportCacheSize = event.size()
            self.viewportCache = self.viewport().grab()
            self.resizeTimer.start()

    def paintEvent(self, event):
        if self.resizeTimer.isActive():
            painter = QPainter(self.viewport())
            painter.drawPixmap(0, 0, self.viewportCache)
        else:
            super().paintEvent(event)

    def selectionChanged(self, selected: QItemSelection, deselected: QItemSelection):
        return super().selectionChanged(selected, deselected)

    def eventFilter(self, obj: QObject, event: QEvent):
        return super().eventFilter(obj, event)

    def sortByColumn(self, col: int, order: Qt.SortOrder, save=True):
        if save and col is not None and order is not None:
            settings = QSettings()
            settings.setValue('modlistSortColumn', col)
            settings.setValue('modlistSortOrder', int(order))
        return super().sortByColumn(col, order)

    def keyPressEvent(self, event: QKeyEvent):
        if event.matches(QKeySequence.Paste):
            self.pasteEvent()
        elif event.matches(QKeySequence.Delete):
            self.setDisabled(True)
            mods: List[Mod] = [
                self.modmodel[self.filtermodel.mapToSource(index).row()]
                for index in self.selectionModel().selectedRows()
            ]
            for mod in mods:
                try:
                    self.modmodel.remove(mod)
                except ModNotFoundError:
                    logger.bind(name=mod.filename).warning('Mod not found')
            self.selectionModel().clear()
            self.setDisabled(False)
        return super().keyPressEvent(event)

    def copyBufferChanged(self):
        if QSettings().value('nexusCheckClipboard', 'False') == 'True':
            self.checkInstallFromURLs(QApplication.clipboard().text().splitlines(), local=False)

    def pasteEvent(self):
        self.checkInstallFromURLs(QApplication.clipboard().text().splitlines())

    def setFilter(self, filter: str):
        self.filtermodel.setFilterFixedString(filter)

    def checkInstallFromURLs(self, paths: List[Union[str, QUrl]], local=True, web=True):
        installed = 0
        errors = 0
        installedBefore = len(self.modmodel)
        installtime = datetime.utcnow()
        logger.bind(newline=True, output=False).debug('Starting install from URLs')
        try:
            for path in paths:
                if isinstance(path, QUrl):
                    path = path.toString()
                if web and isValidNexusModsUrl(path):
                    self.setDisabled(True)
                    logger.bind(dots=True, path=path).info(f'Installing mods from')
                    i, e = self.installFromNexusmods(path, installtime)
                    installed += i
                    errors += e
                elif local and isValidFileUrl(path):
                    self.setDisabled(True)
                    path = Path(QUrl(path).toLocalFile())
                    logger.bind(dots=True, path=path).info(f'Installing mods from')
                    i, e = self.installFromFile(path, installtime)
                    installed += i
                    errors += e
        except Exception as e:
            # we should never land here, but don't lock up the UI if it happens
            logger.exception(str(e))
            errors += 1

        if installed > 0 or errors > 0:
            log = logger.bind(modlist=bool(installed))
            message = 'Installed {0} mods{1}'.format(installed, f' ({errors} errors)' if errors else '')
            if installed > 0 and errors > 0:
                log.warning(message)
            elif installed > 0:
                log.success(message)
            else:
                log.error(message)
        if not installedBefore:
            # if list was empty before, auto resize columns
            self.resizeColumnsToContents()
        self.setDisabled(False)

    def installFromNexusmods(self, url: str, installtime=datetime.utcnow()) -> Tuple[int, int]:
        # TODO: incomplete: ask if install and which files
        return 0, 0

    def installFromFile(self, path: Path, installtime=datetime.utcnow()) -> Tuple[int, int]:
        originalpath = path
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
                    self.modmodel.add(mod)
                    installed += 1
                except ModExistsError:
                    logger.bind(path=mod.source, name=mod.filename).error(f'Mod exists')
                    errors += 1
        except InvalidPathError as e:
            # TODO: enhancement: better install error message
            logger.bind(path=e.path).error(e.message)
            errors += 1
        finally:
            if archive and not path == originalpath:
                try:
                    util.removeDirectory(path)
                except Exception:
                    logger.bind(path=path).warning('Could not remove temporary directory')
            self.modmodel.setLastUpdateTime(installtime)
            self.repaint()
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
