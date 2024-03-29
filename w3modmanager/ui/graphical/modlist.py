from w3modmanager.core.errors import ModelError, ModExistsError
from w3modmanager.core.model import Model
from w3modmanager.domain.mod.fetcher import *
from w3modmanager.domain.mod.mod import Mod
from w3modmanager.domain.web.nexus import RequestError, ResponseError, downloadFile, getCategoryName, getModInformation
from w3modmanager.ui.graphical.detailswindow import DetailsWindow
from w3modmanager.ui.graphical.modlistmodel import ModListModel
from w3modmanager.util.util import *

import asyncio
import re

from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import cast
from urllib.parse import unquote, urlparse

import dateparser

from loguru import logger
from PySide6.QtCore import (
    QAbstractItemModel,
    QAbstractTableModel,
    QEvent,
    QItemSelection,
    QItemSelectionModel,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    QPoint,
    QRect,
    QRegularExpression,
    QSettings,
    QSortFilterProxyModel,
    Qt,
    QTimer,
    QUrl,
)
from PySide6.QtGui import (
    QColor,
    QCursor,
    QDesktopServices,
    QDragEnterEvent,
    QDragLeaveEvent,
    QDragMoveEvent,
    QDropEvent,
    QIcon,
    QKeyEvent,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QResizeEvent,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHeaderView,
    QMenu,
    QMessageBox,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QWidget,
)


class ModListItemDelegate(QStyledItemDelegate):
    def __init__(self, parent: QTableView) -> None:
        super().__init__(parent)
        self.linepen = QPen(QColor(200, 200, 200), 0, parent.gridStyle())

    def paint(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex
    ) -> None:
        itemOption = QStyleOptionViewItem(option)

        # disable focus outline
        if itemOption.state & QStyle.StateFlag.State_HasFocus:  # type: ignore
            itemOption.state ^= QStyle.StateFlag.State_HasFocus  # type: ignore
        # hover whole row
        if index.row() == itemOption.styleObject.hoverIndexRow:  # type: ignore
            itemOption.state |= QStyle.StateFlag.State_MouseOver  # type: ignore

        super().paint(painter, itemOption, index)

        # draw lines around numeric columns
        if index.column() in (5, 12):
            oldpen = painter.pen()
            painter.setPen(self.linepen)
            painter.drawLine(
                itemOption.rect.topRight() + QPoint(0, 0),  # type: ignore
                itemOption.rect.bottomRight() + QPoint(0, 0)  # type: ignore
            )
            painter.setPen(oldpen)

    def updateEditorGeometry(
        self, editor: QWidget, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex
    ) -> None:
        itemOption = QStyleOptionViewItem(option)
        # set size of editor to size of cell
        geom: QRect = QApplication.style().subElementRect(QStyle.SubElement.SE_ItemViewItemText, itemOption, editor)
        geom.setTop(geom.top())
        editor.setGeometry(geom)


class ModListSelectionModel(QItemSelectionModel):
    def __init__(self, parent: QWidget, model: QAbstractItemModel) -> None:
        super().__init__(model, parent)

    def setCurrentIndex(
        self, index: QModelIndex | QPersistentModelIndex, command: QItemSelectionModel.SelectionFlag
    ) -> None:
        if not index.isValid():
            return
        # always focus column 3
        index = self.model().index(index.row(), 3)
        super().setCurrentIndex(index, command)


class ModListFilterModel(QSortFilterProxyModel):
    def __init__(self, parent: QWidget, source: QAbstractTableModel) -> None:
        super().__init__(parent)
        self.setSourceModel(source)
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setSortRole(Qt.ItemDataRole.UserRole)

    def filterAcceptsRow(self, row: int, parent: QModelIndex | QPersistentModelIndex) -> bool:
        filterRegExp = self.filterRegularExpression()
        if not filterRegExp.pattern() or not filterRegExp.isValid():
            return True
        sourceModel = self.sourceModel()
        return filterRegExp.match(
            sourceModel.data(sourceModel.index(row, 3, parent))
        ).hasMatch() or filterRegExp.match(
            sourceModel.data(sourceModel.index(row, 2, parent))
        ).hasMatch()


class ModList(QTableView):
    def __init__(self, parent: QWidget, model: Model) -> None:
        super().__init__(parent)

        settings = QSettings()

        self.hoverIndexRow = -1
        self.modmodel = model
        self.installLock = asyncio.Lock()

        self.tasks: set[asyncio.Task[Any]] = set()

        self.setMouseTracking(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setWordWrap(False)
        self.setSortingEnabled(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAcceptDrops(True)
        self.setEditTriggers(QTableView.EditTrigger.EditKeyPressed | QTableView.EditTrigger.DoubleClicked)
        self.setShowGrid(False)
        self.setAutoScroll(False)
        self.setCornerButtonEnabled(False)

        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.showContextMenu)

        # setup viewport caching to counter slow resizing with many table elements
        self.resizeTimer = QTimer(self)
        self.resizeTimer.setSingleShot(True)
        self.resizeTimer.setInterval(225)
        self.resizeTimer.timeout.connect(lambda: [
            self.resizeTimer.stop(),
            self.viewport().repaint(),
        ])
        self.viewportCache = None

        self.listmodel = ModListModel(self, model)
        self.filtermodel = ModListFilterModel(self, self.listmodel)
        self.setModel(self.filtermodel)

        self.setItemDelegate(ModListItemDelegate(self))
        self.setSelectionModel(ModListSelectionModel(self, self.filtermodel))

        self.horizontalHeader().sectionMoved.connect(lambda: self.headerChangedEvent())
        self.horizontalHeader().sectionResized.connect(lambda: self.headerChangedEvent())

        self.horizontalHeader().setHighlightSections(False)
        self.horizontalHeader().setSectionsMovable(True)
        self.horizontalHeader().setResizeContentsPrecision(100)
        for section in range(self.horizontalHeader().count() - 1):
            self.horizontalHeader().setSectionResizeMode(section, QHeaderView.ResizeMode.Interactive)
        self.horizontalHeader().setStretchLastSection(True)

        self.verticalHeader().hide()
        self.verticalHeader().setVisible(False)
        self.setSectionSize(settings.value('compactMode', 'False') == 'True')
        self.verticalHeader().setResizeContentsPrecision(100)
        for section in range(self.verticalHeader().count()):
            self.verticalHeader().setSectionResizeMode(section, QHeaderView.ResizeMode.Fixed)
        self.verticalHeader().setStretchLastSection(False)

        if len(model):
            self.modCountLastUpdate = len(model)
            self.resizeColumnsToContents()
        elif settings.value('modlistLastUpdate') is not None:
            self.modCountLastUpdate = cast(int, settings.value('modlistLastUpdate', 0, int))
        else:
            self.modCountLastUpdate = 0

        if settings.value('modlistHorizontalHeaderState'):
            self.horizontalHeader().restoreState(settings.value('modlistHorizontalHeaderState'))  # type: ignore

        self.setFocus()

        self.sortByColumn(3, Qt.SortOrder.AscendingOrder, False)
        self.sortByColumn(2, Qt.SortOrder.AscendingOrder, False)
        self.sortByColumn(1, Qt.SortOrder.AscendingOrder, False)
        if settings.value('modlistSortColumn') is not None and \
           settings.value('modlistSortOrder') is not None:
            try:
                self.sortByColumn(
                    cast(int, settings.value('modlistSortColumn', 1, int)),
                    Qt.SortOrder.DescendingOrder if cast(int, settings.value('modlistSortOrder', 1, int)
                                                         ) else Qt.SortOrder.AscendingOrder,
                    False
                )
            except Exception as e:
                logger.exception(f'could not restore sort order: {e}')
        self.horizontalHeader().sortIndicatorChanged.connect(self.sortByColumn)

        self.doubleClicked.connect(self.doubleClickEvent)
        model.updateCallbacks.append(self.modelUpdateEvent)

        # TODO: enhancement: offer option to read readme and other additional text files

    def sizeHintForRow(self, row: int) -> int:
        if row < 0 or row >= self.model().rowCount():
            return -1
        return self.verticalHeader().defaultSectionSize()

    def setSectionSize(self, compact: bool) -> None:
        if compact:
            self.verticalHeader().setDefaultSectionSize(25)
        else:
            self.verticalHeader().setDefaultSectionSize(30)

    @debounce(200)
    async def headerChangedEvent(self) -> None:
        settings = QSettings()
        state = self.horizontalHeader().saveState()
        # call later to work around pyqt5 StopIteration exception
        asyncio.get_running_loop().call_later(
            25 / 1000.0,
            lambda: settings.setValue('modlistHorizontalHeaderState', state)
        )

    def modelUpdateEvent(self, model: Model) -> None:
        if not self.modCountLastUpdate and len(self.modmodel):
            # if list was empty before, auto resize columns
            self.resizeColumnsToContents()
        self.modCountLastUpdate = len(self.modmodel)
        settings = QSettings()
        settings.setValue('modlistLastUpdate', self.modCountLastUpdate)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        self.hoverIndexRow = self.indexAt(event.pos()).row()
        return super().mouseMoveEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.angleDelta().y() > 0:
                createAsyncTask(self.changeHoveredModPriority(1), self.tasks)
            elif event.angleDelta().y() < 0:
                createAsyncTask(self.changeHoveredModPriority(-1), self.tasks)
            return
        result = super().wheelEvent(event)
        # repaint previously hovered row on scroll avoid repaint artifacts
        index = self.model().index(self.hoverIndexRow, 0)
        self.hoverIndexRow = self.indexAt(event.position().toPoint()).row()
        rect = self.visualRect(index)
        rect.setLeft(0)
        rect.setRight(self.viewport().width())
        self.viewport().repaint(rect)
        return result

    def leaveEvent(self, event: QEvent) -> None:
        index = self.model().index(self.hoverIndexRow, 0)
        # unset row hover state and repaint previously hovered row
        self.hoverIndexRow = -1
        rect = self.visualRect(index)
        rect.setLeft(0)
        rect.setRight(self.viewport().width())
        self.viewport().repaint(rect)
        return super().leaveEvent(event)

    def doubleClickEvent(self, index: QModelIndex) -> None:
        if self.filtermodel.mapToSource(index).column() == 0:
            mod = self.modmodel[self.filtermodel.mapToSource(index).row()]
            if mod.enabled:
                createAsyncTask(self.modmodel.disable(mod), self.tasks)
            else:
                createAsyncTask(self.modmodel.enable(mod), self.tasks)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if self.width() > 1200:
            if not self.resizeTimer.isActive():
                self.resizeTimer.start()
                self.viewportCache = self.viewport().grab()
        else:
            self.resizeTimer.stop()

    def paintEvent(self, event: QPaintEvent) -> None:
        if self.resizeTimer.isActive() and self.viewportCache is not None:
            painter = QPainter(self.viewport())
            painter.drawPixmap(0, 0, self.viewportCache)
        else:
            if self.viewportCache is not None:
                self.viewportCache = None
            super().paintEvent(event)

    def selectionChanged(self, selected: QItemSelection, deselected: QItemSelection) -> None:
        super().selectionChanged(selected, deselected)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        return super().eventFilter(obj, event)

    def sortByColumn(self, col: int, order: Qt.SortOrder, save: bool = True) -> None:  # type: ignore
        if save and col is not None and order is not None:
            settings = QSettings()
            settings.setValue('modlistSortColumn', col)
            settings.setValue('modlistSortOrder', 0 if order == Qt.SortOrder.AscendingOrder else 1)
        super().sortByColumn(col, order)

    def showContextMenu(self, pos: QPoint) -> None:
        mods = self.getSelectedMods()
        if not mods:
            return
        packagemods = list({mod for mods in (
            (self.modmodel[mod] for mod in self.modmodel if self.modmodel[mod].package == package)
            for package in (mod.package for mod in mods)
        ) for mod in mods})
        menu = QMenu(self)
        menu.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Popup)
        menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        actionDetails = menu.addAction('&Show Details')
        actionDetails.triggered.connect(lambda: [
            self.showSelectedModsDetails()
        ])
        menu.addSeparator()
        actionOpen = menu.addAction('&Open Directory')
        actionOpen.setIcon(QIcon(str(getRuntimePath('resources/icons/open-folder.ico'))))
        actionOpen.triggered.connect(lambda: [
            util.openDirectory(self.modmodel.getModPath(mod))  # type: ignore
            for mod in mods
        ])
        menu.addSeparator()
        actionEnable = menu.addAction('&Enable')
        actionEnable.triggered.connect(lambda: [
            createAsyncTask(self.enableSelectedMods(True), self.tasks)
        ])
        actionEnable.setEnabled(not all(mod.enabled for mod in mods))
        actionDisable = menu.addAction('&Disable')
        actionDisable.triggered.connect(lambda: [
            createAsyncTask(self.enableSelectedMods(False), self.tasks)
        ])
        actionDisable.setEnabled(not all(not mod.enabled for mod in mods))
        menu.addSeparator()
        actionEnablePackage = menu.addAction('Enable Package')
        actionEnablePackage.triggered.connect(lambda: [
            createAsyncTask(self.enableSelectedMods(True, True), self.tasks)
        ])
        actionEnablePackage.setEnabled(len(packagemods) > len(mods) and not all(mod.enabled for mod in packagemods))
        actionDisablePackage = menu.addAction('Disable Package')
        actionDisablePackage.triggered.connect(lambda: [
            createAsyncTask(self.enableSelectedMods(False, True), self.tasks)
        ])
        actionDisablePackage.setEnabled(len(packagemods) > len(
            mods) and not all(not mod.enabled for mod in packagemods))
        menu.addSeparator()
        actionUninstall = menu.addAction('&Uninstall')
        actionUninstall.triggered.connect(lambda: [
            createAsyncTask(self.deleteSelectedMods(), self.tasks)
        ])
        actionUninstallPackage = menu.addAction('Uninstall Package')
        actionUninstallPackage.triggered.connect(lambda: [
            createAsyncTask(self.deleteSelectedMods(True), self.tasks)
        ])
        actionUninstallPackage.setEnabled(len(packagemods) > len(mods))
        menu.addSeparator()
        actionOpenNexus = menu.addAction('Open &Nexus Mods page')
        actionOpenNexus.setIcon(QIcon(str(getRuntimePath('resources/icons/browse.ico'))))
        actionOpenNexus.triggered.connect(lambda: [
            QDesktopServices.openUrl(QUrl(f'https://www.nexusmods.com/witcher3/mods/{modid}'))
            for modid in {mod.modid for mod in mods if mod.modid > 0}
        ])
        actionOpenNexus.setEnabled(not all(mod.modid <= 0 for mod in mods))

        menu.popup(self.viewport().mapToGlobal(pos))

    def selectRowChecked(self, row: int) -> None:
        nums: int = self.filtermodel.rowCount()
        if row < nums and row >= 0:
            self.selectRow(row)
        elif nums > 0:
            self.selectRow(nums - 1)

    def getSelectedMods(self) -> list[Mod]:
        return [
            self.modmodel[self.filtermodel.mapToSource(cast(QModelIndex, index)).row()]
            for index in self.selectionModel().selectedRows()
        ]

    def getHoveredMod(self) -> Mod | None:
        row = self.filtermodel.mapToSource(self.indexAt(self.viewport().mapFromGlobal(QCursor.pos()))).row()
        if row < 0 or row >= len(self.modmodel):
            return None
        return self.modmodel[row]

    async def enableSelectedMods(self, enable: bool = True, package: bool = False) -> None:
        if not self.selectionModel().hasSelection():
            return
        mods = self.getSelectedMods()
        if package:
            mods = list({mod for mods in (
                (self.modmodel[mod] for mod in self.modmodel if self.modmodel[mod].package == package)
                for package in (mod.package for mod in mods)
            ) for mod in mods})
        self.setDisabled(True)
        for mod in mods:
            try:
                if enable:
                    await self.modmodel.enable(mod)
                else:
                    await self.modmodel.disable(mod)
            except Exception as e:
                logger.bind(name=mod.filename).exception(f'Could not enable/disable mod: {e}')
        self.setDisabled(False)
        self.setFocus()

    async def deleteSelectedMods(self, package: bool = False) -> None:
        if not self.selectionModel().hasSelection():
            return
        self.setDisabled(True)
        mods = self.getSelectedMods()
        if package:
            mods = list({mod for mods in (
                (self.modmodel[mod] for mod in self.modmodel if self.modmodel[mod].package == package)
                for package in (mod.package for mod in mods)
            ) for mod in mods})
        # TODO: incomplete: ask if selected mods should really be removed
        inds = self.selectedIndexes()
        self.selectionModel().clear()
        for mod in mods:
            try:
                await self.modmodel.remove(mod)
            except Exception as e:
                logger.bind(name=mod.filename).exception(f'Could not delete mod: {e}')
        asyncio.get_running_loop().call_later(
            100 / 1000.0, partial(self.selectRowChecked, cast(QModelIndex, inds[0]).row()))
        self.setDisabled(False)
        self.setFocus()

    async def updateModDetails(self, mod: Mod) -> bool:
        logger.bind(name=mod.filename, dots=True).debug('Requesting details for mod')
        if not mod.md5hash:
            logger.bind(name=mod.filename).warning('Could not get details for mod not installed from archive')
            return False
        try:
            details = await getModInformation(mod.md5hash)
        except Exception as e:
            logger.bind(name=mod.filename).warning(f'{e}')
            return False
        try:
            details = [d for d in details if bool(d['mod']['available']) is True]
            details.sort(key=lambda d: d['mod']['updated_timestamp'], reverse=True)

            package = str(details[0]['mod']['name'])
            summary = str(details[0]['mod']['summary'])
            modid = int(details[0]['mod']['mod_id'])
            category = int(details[0]['mod']['category_id'])
            version = str(details[0]['file_details']['version'])
            fileid = int(details[0]['file_details']['file_id'])
            uploadname = str(details[0]['file_details']['name'])
            uploadtime = str(details[0]['file_details']['uploaded_time'])
            mod.package = package
            mod.summary = summary
            mod.modid = modid
            mod.category = getCategoryName(category)
            mod.version = version
            mod.fileid = fileid
            mod.uploadname = uploadname
            uploaddate = dateparser.parse(uploadtime)
            if uploaddate:
                mod.uploaddate = uploaddate.astimezone(tz=timezone.utc)
            else:
                logger.bind(name=mod.filename).debug(
                    f'Could not parse date {uploadtime} in mod information response')
        except KeyError as e:
            logger.bind(name=mod.filename).exception(
                f'Could not find key "{e!s}" in mod information response')
            return False
        try:
            await self.modmodel.update(mod)
        except Exception as e:
            logger.bind(name=mod.filename).exception(f'Could not update mod: {e}')
            return False
        return True

    async def updateSelectedModsDetails(self) -> None:
        if not self.selectionModel().hasSelection():
            return
        self.setDisabled(True)
        updatetime = datetime.now(tz=timezone.utc)
        mods = self.getSelectedMods()
        logger.bind(newline=True, output=False).debug(f'Requesting details for {len(mods)} mods')
        results = await asyncio.gather(
            *[self.updateModDetails(mod) for mod in mods], return_exceptions=True
        )
        successes = sum(results)
        errors = len(results) - successes
        message = 'Updated details for {} mods{}'.format(successes, f' ({errors} errors)' if errors else '')
        if errors:
            logger.warning(message)
        else:
            logger.success(message)
        self.modmodel.setLastUpdateTime(updatetime)
        self.setDisabled(False)
        self.setFocus()

    async def changeSelectedModsPriority(self, delta: int) -> None:
        mods = self.getSelectedMods()
        if len(mods) == 0:
            return
        await asyncio.gather(*[
            self.modmodel.setPriority(mod, max(-1, min(9999, int(mod.priority + delta))))
            for mod in mods if mod.datatype in ('mod', 'udf',)
        ])
        self.modmodel.setLastUpdateTime(datetime.now(tz=timezone.utc))

    async def changeHoveredModPriority(self, delta: int) -> None:
        mod = self.getHoveredMod()
        if mod is not None and mod.datatype in ('mod', 'udf',):
            await self.modmodel.setPriority(mod, max(-1, min(9999, int(mod.priority + delta))))
            self.modmodel.setLastUpdateTime(datetime.now(tz=timezone.utc))

    def showSelectedModsDetails(self) -> None:
        mods = self.getSelectedMods()
        for mod in mods:
            details = DetailsWindow(self, mod, self.modmodel)
            details.open()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.selectionModel().clear()
        elif event.matches(QKeySequence.StandardKey.Delete):
            createAsyncTask(self.deleteSelectedMods(), self.tasks)
        elif event.modifiers() & Qt.KeyboardModifier.ControlModifier == Qt.KeyboardModifier.ControlModifier \
                and event.key() == Qt.Key.Key_Return:
            mods = self.getSelectedMods()
            if len(mods) == 0:
                return
            mod = mods[0]
            if mod.enabled:
                createAsyncTask(self.enableSelectedMods(False), self.tasks)
            else:
                createAsyncTask(self.enableSelectedMods(True), self.tasks)
        elif event.modifiers() & Qt.KeyboardModifier.ControlModifier == Qt.KeyboardModifier.ControlModifier \
                and event.key() == Qt.Key.Key_Up:
            createAsyncTask(self.changeSelectedModsPriority(1), self.tasks)
        elif event.modifiers() & Qt.KeyboardModifier.ControlModifier == Qt.KeyboardModifier.ControlModifier \
                and event.key() == Qt.Key.Key_Down:
            createAsyncTask(self.changeSelectedModsPriority(-1), self.tasks)
        elif event.modifiers() & Qt.KeyboardModifier.ControlModifier == Qt.KeyboardModifier.ControlModifier \
                and event.key() == Qt.Key.Key_P:
            rows = self.selectionModel().selectedRows()
            if len(rows) == 0:
                return
            index = cast(QModelIndex, rows[0])
            index = index.sibling(index.row(), 5)
            if index.flags() & Qt.ItemFlag.ItemIsEditable:
                self.setCurrentIndex(index)
                self.edit(index)
        else:
            super().keyPressEvent(event)

    def setFilter(self, search: str) -> None:
        self.filtermodel.setFilterRegularExpression(
            QRegularExpression(search, QRegularExpression.PatternOption.CaseInsensitiveOption)
        )

    async def checkInstallFromURLs(
        self, paths: Sequence[str | QUrl], local: bool = True, web: bool = True
    ) -> None:
        await self.installLock.acquire()
        installed = 0
        errors = 0
        installtime = datetime.now(tz=timezone.utc)
        # remove duplicate paths
        paths = list(set(paths))
        logger.bind(newline=True, output=False).debug('Starting install from URLs')
        try:
            results = await asyncio.gather(
                *[self.installFromURL(path, local, web, installtime) for path in paths],
            )
            for result in results:
                installed += result[0]
                errors += result[1]
        except Exception as e:
            # we should never land here, but don't lock up the UI if it happens
            logger.exception(str(e))
            errors += 1

        if installed > 0 or errors > 0:
            log = logger.bind(modlist=bool(installed))
            message = 'Installed {} mods{}'.format(installed, f' ({errors} errors)' if errors else '')
            if installed > 0 and errors > 0:
                log.warning(message)
            elif installed > 0:
                log.success(message)
            else:
                log.error(message)
        self.setDisabled(False)
        self.setFocus()
        self.installLock.release()

    async def installFromURL(
        self, path: str | QUrl, local: bool = True, web: bool = True, installtime: datetime | None = None
    ) -> tuple[int, int]:
        installed = 0
        errors = 0
        if not installtime:
            installtime = datetime.now(tz=timezone.utc)
        if isinstance(path, QUrl):
            path = path.toString()
        if web and isValidModDownloadUrl(path):
            self.setDisabled(True)
            logger.bind(dots=True, path=path).info(f'Installing mods from')
            i, e = await self.installFromFileDownload(path, installtime)
            installed += i
            errors += e
        elif local and isValidFileUrl(path):
            self.setDisabled(True)
            path = QUrl(path)
            logger.bind(dots=True, path=Path(path.toLocalFile())).info(f'Installing mods from')
            i, e = await self.installFromFile(Path(path.toLocalFile()), installtime)
            installed += i
            errors += e
        else:
            logger.bind(path=path).error('Could not install mods from')
        return installed, errors

    async def installFromFileDownload(self, url: str, installtime: datetime | None = None) -> tuple[int, int]:
        installed = 0
        errors = 0
        if not installtime:
            installtime = datetime.now(tz=timezone.utc)
        try:
            target = Path(urlparse(url).path)
            filename = re.sub(r'[^\w\-_\. ]', r'_', unquote(target.name))
            target = Path(tempfile.gettempdir()).joinpath(
                'w3modmanager/download').joinpath(f'{filename}')
        except ValueError:
            logger.bind(name=url).exception('Wrong request URL')
            return 0, 1
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            logger.bind(name=url).info('Starting to download file')
            await downloadFile(url, target)
            installed, errors = await self.installFromFile(target, installtime)
        except (RequestError, ResponseError, Exception) as e:
            logger.bind(name=url).exception(f'Failed to download file: {e}')
            return 0, 1
        finally:
            if target.is_file():
                target.unlink()
        return installed, errors

    async def installFromFile(self, path: Path, installtime: datetime | None = None) -> tuple[int, int]:
        originalpath = path
        installed = 0
        errors = 0
        archive = path.is_file()
        source = None
        md5hash = ''
        details = None
        detailsrequest: asyncio.Task[Any] | None = None

        if not installtime:
            installtime = datetime.now(tz=timezone.utc)
        try:
            if archive:
                # unpack archive, set source and request details
                md5hash = getMD5Hash(path)
                source = path
                settings = QSettings()
                if settings.value('nexusGetInfo', 'False') == 'True':
                    logger.bind(path=str(path), dots=True).debug('Requesting details for archive')
                    detailsrequest = createAsyncTask(getModInformation(md5hash), self.tasks)
                logger.bind(path=str(path), dots=True).debug('Unpacking archive')
                path = await extractMod(source)

            # validate and read mod
            valid, exhausted = containsValidMod(path, searchlimit=8)
            if not valid:
                if not exhausted and self.showContinueSearchDialog(searchlimit=8):
                    if not containsValidMod(path):
                        raise InvalidPathError(path, 'Invalid mod')
                elif not exhausted:
                    raise InvalidPathError(path, 'Stopped searching for mod')
                else:
                    raise InvalidPathError(path, 'Invalid mod')
            mods = await Mod.fromDirectory(path, searchCommonRoot=not archive)

            installedMods = []
            # update mod details and add mods to the model
            for mod in mods:
                mod.md5hash = md5hash
                try:
                    # TODO: incomplete: check if mod is installed, ask if replace
                    await self.modmodel.add(mod)
                    installedMods.append(mod)
                    installed += 1
                except ModExistsError:
                    logger.bind(path=source if source else mod.source, name=mod.filename).error(f'Mod exists')
                    errors += 1
                    continue

            # wait for details response if requested
            if detailsrequest:
                try:
                    details = await detailsrequest
                except (RequestError, ResponseError, Exception) as e:
                    logger.warning(f'Could not get information for {source.name if source else path.name}: {e}')

            # update mod with additional information
            if source or details:
                for mod in installedMods:
                    if source:
                        # set source if it differs from the scan directory, e.g. an archive
                        mod.source = source
                    if details:
                        # set additional details if requested and available
                        try:
                            details = [d for d in details if bool(d['mod']['available']) is True]
                            details.sort(key=lambda d: d['mod']['updated_timestamp'], reverse=True)

                            package = str(details[0]['mod']['name'])
                            summary = str(details[0]['mod']['summary'])
                            modid = int(details[0]['mod']['mod_id'])
                            category = int(details[0]['mod']['category_id'])
                            version = str(details[0]['file_details']['version'])
                            fileid = int(details[0]['file_details']['file_id'])
                            uploadname = str(details[0]['file_details']['name'])
                            uploadtime = str(details[0]['file_details']['uploaded_time'])
                            mod.package = package
                            mod.summary = summary
                            mod.modid = modid
                            mod.category = getCategoryName(category)
                            mod.version = version
                            mod.fileid = fileid
                            mod.uploadname = uploadname
                            uploaddate = dateparser.parse(uploadtime)
                            if uploaddate:
                                mod.uploaddate = uploaddate.astimezone(tz=timezone.utc)
                            else:
                                logger.bind(name=mod.filename).debug(
                                    f'Could not parse date {uploadtime} in mod information response')
                        except KeyError as e:
                            logger.bind(name=mod.filename).exception(
                                f'Could not find key "{e!s}" in mod information response')
                    try:
                        await self.modmodel.update(mod)
                    except Exception:
                        logger.bind(name=mod.filename).warning('Could not update mod details')

        except ModelError as e:
            logger.bind(path=e.path).error(e.message)
            errors += 1
        except InvalidPathError as e:
            # TODO: enhancement: better install error message
            logger.bind(path=e.path).error(e.message)
            errors += 1
        except FileNotFoundError as e:
            logger.bind(path=e.filename).error(e.strerror if e.strerror else str(e))
            errors += 1
        except OSError as e:
            logger.bind(path=e.filename).error(e.strerror if e.strerror else str(e))
            errors += 1
        except Exception as e:
            logger.exception(str(e))
            errors += 1
        finally:
            if detailsrequest and not detailsrequest.done():
                detailsrequest.cancel()
            if archive and path != originalpath:
                try:
                    util.removeDirectory(path)
                except Exception:
                    logger.bind(path=path).warning('Could not remove temporary directory')
            self.modmodel.setLastUpdateTime(installtime)
            self.repaint()
        return installed, errors

    def showContinueSearchDialog(self, searchlimit: int) -> bool:
        messagebox = QMessageBox(self)
        messagebox.setWindowTitle('Unusual search depth')
        messagebox.setText(f'''
            <p>No mod detected after searching through {searchlimit} directories.</p>
            <p>Are you sure this is a valid mod?</p>
            ''')
        messagebox.setTextFormat(Qt.TextFormat.RichText)
        messagebox.setStandardButtons(QMessageBox.StandardButton.Cancel)
        yes: QPushButton = QPushButton(' Yes, continue searching ', messagebox)
        yes.setAutoDefault(True)
        yes.setDefault(True)
        messagebox.addButton(yes, QMessageBox.ButtonRole.YesRole)
        messagebox.exec_()
        return messagebox.clickedButton() == yes

    def dropEvent(self, event: QDropEvent) -> None:
        event.accept()
        self.setDisabled(True)
        self.repaint()
        createAsyncTask(self.checkInstallFromURLs(event.mimeData().urls()), self.tasks)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        self.setDisabled(True)
        self.repaint()
        urls = event.mimeData().urls()
        if not urls:
            self.setDisabled(False)
            self.setFocus()
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
        self.setFocus()
        event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        event.accept()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        event.accept()
