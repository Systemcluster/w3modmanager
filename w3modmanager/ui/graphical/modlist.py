from pathlib import Path
from urllib.parse import urlparse, unquote
from typing import Union, List, Tuple, Optional
from datetime import datetime, timezone
import asyncio

from loguru import logger
import dateparser

from Qt.QtCore import Qt, QSettings, QUrl, QPoint, \
    QItemSelectionModel, QSortFilterProxyModel, QAbstractItemModel, \
    QAbstractTableModel, QRect, QModelIndex, QItemSelection, \
    QObject, QEvent, QTimer, QSize
from Qt.QtWidgets import QApplication, QStyledItemDelegate, \
    QStyleOptionViewItem, QStyle, QAbstractItemView, QWidget, \
    QTableView, QMessageBox, QPushButton
from Qt.QtGui import QPen, QColor, QKeySequence, QKeyEvent, QMouseEvent, QPainter, QPixmap, \
    QDropEvent, QDragEnterEvent, QDragMoveEvent, QDragLeaveEvent, QResizeEvent, QPaintEvent

from w3modmanager.core.model import Model
from w3modmanager.core.errors import ModExistsError, ModNotFoundError, ModelError
from w3modmanager.util.util import *
from w3modmanager.domain.mod.fetcher import *
from w3modmanager.domain.mod.mod import Mod
from w3modmanager.domain.web.nexus import RequestError, ResponseError, getCategoryName, getModInformation, downloadFile
from w3modmanager.ui.graphical.modlistmodel import ModListModel


class ModListItemDelegate(QStyledItemDelegate):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.linepen = QPen(QColor(200, 200, 200), 0, parent.gridStyle())

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
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

    def updateEditorGeometry(self, editor: QWidget, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        itemOption = QStyleOptionViewItem(option)
        # set size of editor to size of cell
        geom: QRect = QApplication.style().subElementRect(QStyle.SE_ItemViewItemText, itemOption, editor)
        geom.setTop(geom.top())
        editor.setGeometry(geom)


class ModListSelectionModel(QItemSelectionModel):
    def __init__(self, parent: QWidget, model: QAbstractItemModel) -> None:
        super().__init__(model, parent)

    def setCurrentIndex(self, index: QModelIndex, command: QItemSelectionModel) -> None:
        if not index.isValid():
            return
        # always focus column 3
        index = self.model().index(index.row(), 3)
        super().setCurrentIndex(index, command)


class ModListFilterModel(QSortFilterProxyModel):
    def __init__(self, parent: QWidget, source: QAbstractTableModel) -> None:
        super().__init__(parent)
        self.setSourceModel(source)
        self.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.setSortCaseSensitivity(Qt.CaseInsensitive)
        self.setFilterKeyColumn(3)
        self.setSortRole(Qt.UserRole)
        # TODO: enhancement: filter for multiple columns


class ModList(QTableView):
    def __init__(self, parent: QWidget, model: Model) -> None:
        super().__init__(parent)

        self.hoverIndexRow = -1
        self.modmodel = model
        self.modCountLastUpdate = len(self.modmodel)
        self.installLock = asyncio.Lock()

        self.setMouseTracking(True)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setWordWrap(False)
        self.setSortingEnabled(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAcceptDrops(True)
        self.setEditTriggers(QTableView.EditKeyPressed | QTableView.DoubleClicked)

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
                logger.exception(f'could not restore sort order: {e}')
        self.horizontalHeader().sortIndicatorChanged.connect(self.sortByColumn)

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
    async def headerChangedEvent(self) -> None:
        settings = QSettings()
        state = self.horizontalHeader().saveState()
        # call later to work around pyqt5 StopIteration exception
        asyncio.get_running_loop().call_later(
            25 / 1000.0,
            lambda: settings.setValue('modlistHorizontalHeaderState', state)
        )

    def modelUpdateEvent(self, model: Model) -> None:
        if not self.modCountLastUpdate:
            # if list was empty before, auto resize columns
            self.resizeColumnsToContents()
        self.modCountLastUpdate = len(self.modmodel)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        self.hoverIndexRow = self.indexAt(event.pos()).row()
        return super().mouseMoveEvent(event)

    def doubleClickEvent(self, index: QModelIndex) -> None:
        if self.filtermodel.mapToSource(index).column() == 0:
            mod = self.modmodel[self.filtermodel.mapToSource(index).row()]
            if mod.enabled:
                asyncio.create_task(self.modmodel.disable(mod))
            else:
                asyncio.create_task(self.modmodel.enable(mod))

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if not self.resizeTimer.isActive() and event.size() != self.viewportCacheSize:
            self.viewportCacheSize = event.size()
            self.viewportCache = self.viewport().grab()
            self.resizeTimer.start()

    def paintEvent(self, event: QPaintEvent) -> None:
        if self.resizeTimer.isActive():
            painter = QPainter(self.viewport())
            painter.drawPixmap(0, 0, self.viewportCache)
        else:
            super().paintEvent(event)

    def selectionChanged(self, selected: QItemSelection, deselected: QItemSelection) -> None:
        super().selectionChanged(selected, deselected)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        return super().eventFilter(obj, event)

    def sortByColumn(self, col: int, order: Qt.SortOrder, save: bool = True) -> None:
        if save and col is not None and order is not None:
            settings = QSettings()
            settings.setValue('modlistSortColumn', col)
            settings.setValue('modlistSortOrder', int(order))
        super().sortByColumn(col, order)

    def selectRowChecked(self, row: int) -> None:
        nums: int = self.filtermodel.rowCount()
        if row < nums and row >= 0:
            self.selectRow(row)
        elif nums > 0:
            self.selectRow(nums - 1)

    async def deleteMods(self) -> None:
        if not self.selectionModel().hasSelection():
            return
        self.setDisabled(True)
        mods: List[Mod] = [
            self.modmodel[self.filtermodel.mapToSource(index).row()]
            for index in self.selectionModel().selectedRows()
        ]
        inds = self.selectedIndexes()
        self.selectionModel().clear()
        for mod in mods:
            try:
                await self.modmodel.remove(mod)
            except ModNotFoundError:
                logger.bind(name=mod.filename).warning('Mod not found')
        asyncio.get_running_loop().call_later(100 / 1000.0, partial(self.selectRowChecked, inds[0].row()))
        self.setDisabled(False)
        self.setFocus()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.matches(QKeySequence.Delete):
            asyncio.create_task(self.deleteMods())
        super().keyPressEvent(event)

    def setFilter(self, search: str) -> None:
        self.filtermodel.setFilterFixedString(search)

    async def checkInstallFromURLs(self, paths: List[Union[str, QUrl]], local: bool = True, web: bool = True) -> None:
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
                loop=asyncio.get_running_loop()
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
            message = 'Installed {0} mods{1}'.format(installed, f' ({errors} errors)' if errors else '')
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
        self, path: Union[str, QUrl], local: bool = True, web: bool = True, installtime: Optional[datetime] = None
    ) -> Tuple[int, int]:
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
            path = Path(QUrl(path).toLocalFile())
            logger.bind(dots=True, path=path).info(f'Installing mods from')
            i, e = await self.installFromFile(path, installtime)
            installed += i
            errors += e
        else:
            logger.bind(path=path).error('Could not install mods from')
        return installed, errors

    async def installFromFileDownload(self, url: str, installtime: Optional[datetime] = None) -> Tuple[int, int]:
        installed = 0
        errors = 0
        if not installtime:
            installtime = datetime.now(tz=timezone.utc)
        try:
            target = Path(urlparse(url).path)
            target = Path(tempfile.gettempdir()).joinpath(
                'w3modmanager/download').joinpath(f'{unquote(target.name)}')
        except ValueError:
            logger.bind(name=url).exception('Wrong request URL')
            return 0, 1
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            logger.bind(name=url).info('Starting to download file')
            await downloadFile(url, target)
            installed, errors = await self.installFromFile(target, installtime)
        except (RequestError, ResponseError) as e:
            logger.bind(name=url).exception(f'Failed to download file: {e}')
            return 0, 1
        except Exception as e:
            logger.exception(str(e))
            return 0, 1
        finally:
            if target.is_file():
                target.unlink()
        return installed, errors

    async def installFromFile(self, path: Path, installtime: Optional[datetime] = None) -> Tuple[int, int]:
        originalpath = path
        installed = 0
        errors = 0
        archive = path.is_file()
        source = None
        md5hash = ''
        details = None
        detailsrequest = None

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
                    detailsrequest = asyncio.create_task(getModInformation(md5hash))
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
            mods = Mod.fromDirectory(path, searchCommonRoot=not archive)

            # wait for details response if requested
            if detailsrequest:
                try:
                    details = await detailsrequest
                except (RequestError, ResponseError) as e:
                    logger.warning(f'Could not get information for {source.name if source else path.name}: {e}')

            # update mod details and add mods to the model
            for mod in mods:
                mod.md5hash = md5hash
                if details:
                    # set additional details if requested and available
                    try:
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
                            f'Could not find key "{str(e)}" in mod information response')
                try:
                    # TODO: incomplete: check if mod is installed, ask if replace
                    await self.modmodel.add(mod)
                    installed += 1
                except ModExistsError:
                    logger.bind(path=source if source else mod.source, name=mod.filename).error(f'Mod exists')
                    errors += 1
                if source:
                    # set source if it differs from the scan directory, e.g. an archive
                    mod.source = source

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
            if archive and not path == originalpath:
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
        messagebox.setTextFormat(Qt.RichText)
        messagebox.setStandardButtons(QMessageBox.Cancel)
        yes: QPushButton = QPushButton(' Yes, continue searching ', messagebox)
        yes.setAutoDefault(True)
        yes.setDefault(True)
        messagebox.addButton(yes, QMessageBox.YesRole)
        messagebox.exec_()
        return messagebox.clickedButton() == yes

    def dropEvent(self, event: QDropEvent) -> None:
        event.accept()
        self.setDisabled(True)
        self.repaint()
        asyncio.create_task(self.checkInstallFromURLs(event.mimeData().urls()))

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
