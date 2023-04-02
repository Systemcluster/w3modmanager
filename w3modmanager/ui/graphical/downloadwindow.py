from typing import cast
from w3modmanager.util.util import getTitleString, debounce
from w3modmanager.ui.graphical.modlist import ModListItemDelegate
from w3modmanager.domain.web.nexus import RequestError, ResponseError, getModId, getModFileUrls, getModFiles
from w3modmanager.core.model import *

import html

import dateparser

from PySide6.QtCore import QModelIndex, Qt, QSize, Signal, QObject
from PySide6.QtWidgets import QLabel, QGroupBox, QVBoxLayout, QHBoxLayout, QSizePolicy, QPushButton, \
    QLineEdit, QDialog, QWidget, QTableWidget, QTableWidgetItem, QAbstractItemView
from PySide6.QtGui import QMouseEvent, QWheelEvent


class DownloadWindowEvents(QObject):
    download = Signal(list)


class DownloadWindow(QDialog):
    def __init__(self, parent: Optional[QWidget] = None, url: str = '') -> None:
        super().__init__(parent, )

        if parent:
            self.setWindowTitle('Download Mod')
        else:
            self.setWindowTitle(getTitleString('Download Mod'))
            self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        mainLayout = QVBoxLayout(self)
        mainLayout.setContentsMargins(5, 5, 5, 5)

        self.signals = DownloadWindowEvents(self)

        # URL input

        gbUrl = QGroupBox('Mod URL')
        gbUrlLayout = QVBoxLayout()
        gbUrl.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)

        self.url = QLineEdit()
        self.url.setPlaceholderText('https://www.nexusmods.com/witcher3/mods/...')
        self.url.setText(url)
        self.url.textChanged.connect(lambda: self.validateUrl(self.url.text()))
        gbUrlLayout.addWidget(self.url)

        self.urlInfo = QLabel('🌐')
        self.urlInfo.setContentsMargins(4, 4, 4, 4)
        self.urlInfo.setMinimumHeight(36)
        self.urlInfo.setWordWrap(True)
        gbUrlLayout.addWidget(self.urlInfo)

        gbUrl.setLayout(gbUrlLayout)
        mainLayout.addWidget(gbUrl)

        # File selection

        gbFiles = QGroupBox('Mod Files')
        gbFilesLayout = QVBoxLayout()
        gbFiles.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding)

        self.files = QTableWidget(0, 4)
        self.files.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.files.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.files.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.files.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.files.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.files.setWordWrap(False)
        self.files.setSortingEnabled(True)
        self.files.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.files.verticalHeader().hide()
        self.files.setSortingEnabled(True)
        self.files.sortByColumn(2, Qt.SortOrder.DescendingOrder)
        self.files.verticalHeader().setVisible(False)
        self.files.verticalHeader().setDefaultSectionSize(25)
        self.files.horizontalHeader().setHighlightSections(False)
        self.files.horizontalHeader().setStretchLastSection(True)
        self.files.setHorizontalHeaderLabels(['File Name', 'Version', 'Upload Date', 'Description'])
        self.files.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.files.verticalScrollBar().valueChanged.connect(lambda: self.files.clearFocus())
        self.files.itemSelectionChanged.connect(lambda: self.validateFiles())
        self.files.setDisabled(True)
        gbFilesLayout.addWidget(self.files)

        _mouseMoveEvent = self.files.mouseMoveEvent
        _wheelEvent = self.files.wheelEvent
        self.files.hoverIndexRow = -1  # type: ignore

        def mouseMoveEvent(event: QMouseEvent) -> None:
            _mouseMoveEvent(event)
            self.files.hoverIndexRow = self.files.indexAt(event.pos()).row()  # type: ignore

        def wheelEvent(event: QWheelEvent) -> None:
            _wheelEvent(event)
            # repaint previously hovered row on scroll avoid repaint artifacts
            index = self.files.model().index(self.files.hoverIndexRow, 0)  # type: ignore
            self.files.hoverIndexRow = self.files.indexAt(event.position().toPoint()).row()  # type: ignore
            rect = self.files.visualRect(index)
            rect.setLeft(0)
            rect.setRight(self.files.viewport().width())
            self.files.viewport().repaint(rect)

        self.files.mouseMoveEvent = mouseMoveEvent  # type: ignore
        self.files.wheelEvent = wheelEvent  # type: ignore
        self.files.setItemDelegate(ModListItemDelegate(self.files))
        self.files.setMouseTracking(True)

        gbFiles.setLayout(gbFilesLayout)
        mainLayout.addWidget(gbFiles)

        # Actions

        actionsLayout = QHBoxLayout()
        actionsLayout.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.download = QPushButton('Download', self)
        self.download.clicked.connect(lambda: self.downloadEvent())
        self.download.setAutoDefault(True)
        self.download.setDefault(True)
        self.download.setDisabled(True)
        actionsLayout.addWidget(self.download)
        cancel = QPushButton('Cancel', self)
        cancel.clicked.connect(self.cancelEvent)
        actionsLayout.addWidget(cancel)
        mainLayout.addLayout(actionsLayout)

        # Setup

        self.setMinimumSize(QSize(440, 440))
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding)
        self.resize(QSize(720, 440))

        self.finished.connect(lambda: self.validateUrl.cancel())  # type: ignore
        self.finished.connect(lambda: self.downloadEvent.cancel())  # type: ignore

        self.modId = 0
        self.validateUrl(self.url.text())

    def cancelEvent(self) -> None:
        self.close()

    @debounce(200, cancel_running=True)
    async def validateUrl(self, url: str) -> bool:
        self.download.setDisabled(True)
        self.files.setDisabled(True)
        self.files.clearSelection()
        self.files.clearFocus()
        self.files.clearContents()
        self.files.setRowCount(0)
        self.files.setSortingEnabled(False)
        self.url.setStyleSheet('')
        self.modId = 0
        if not url:
            self.urlInfo.setText('''
                <font color="#888">Please enter a valid mod url.</font>
                ''')
            return False
        modId = getModId(url)
        if not modId:
            self.files.setDisabled(True)
            self.url.setStyleSheet('''
                *{
                    border: 1px solid #B22222;
                    padding: 1px 0px;
                }
                ''')
            self.urlInfo.setText('''
                <font color="#888">Please enter a valid mod url.</font>
                ''')
            return False
        self.urlInfo.setText('🌐')
        try:
            filesResponse = await getModFiles(modId)
        except (RequestError, ResponseError, Exception) as e:
            self.url.setStyleSheet('''
                *{
                    border: 1px solid #B22222;
                    padding: 1px 0px;
                }
                ''')
            self.urlInfo.setText(f'''
                <font color="#888">Could not get mod files: {e}.</font>
                ''')
            return False
        try:
            files = filesResponse['files']
            if not len(files):
                self.urlInfo.setText(f'''
                    <font color="#888">Mod "{modId}" has no files!</font>
                    ''')
                return False

            self.files.setRowCount(len(files))
            for i in range(len(files)):
                file = files[i]
                fileid = int(file['file_id'])
                name = str(file['name'])
                version = str(file['version'])
                _uploadtime = dateparser.parse(file['uploaded_time'])
                uploadtime = _uploadtime.astimezone(tz=None).strftime('%Y-%m-%d %H:%M:%S') if _uploadtime else '?'
                description = html.unescape(str(file['description']))
                nameItem = QTableWidgetItem(name)
                nameItem.setToolTip(name)
                nameItem.setData(Qt.ItemDataRole.UserRole, fileid)
                self.files.setItem(i, 0, nameItem)
                versionItem = QTableWidgetItem(version)
                versionItem.setToolTip(version)
                self.files.setItem(i, 1, versionItem)
                uploadtimeItem = QTableWidgetItem(uploadtime)
                uploadtimeItem.setToolTip(uploadtime)
                self.files.setItem(i, 2, uploadtimeItem)
                descriptionItem = QTableWidgetItem(description)
                descriptionItem.setToolTip(description)
                self.files.setItem(i, 3, descriptionItem)
        except KeyError as e:
            logger.exception(
                f'Could not find key "{str(e)}" in mod files response')
            self.urlInfo.setText(f'''
                <font color="#888">Could not find key "{str(e)}" in mod files response.</font>
                ''')
            return False

        self.urlInfo.setText(f'''
            <font color="#888">Found {len(files)} available files.</font>
            ''')
        self.files.resizeColumnsToContents()
        self.files.setDisabled(False)
        self.files.setSortingEnabled(True)
        self.modId = modId
        return True

    def validateFiles(self) -> bool:
        selection = self.files.selectionModel().selectedRows()
        if len(selection) > 0:
            self.download.setText(f'Download {len(selection)} mods')
            self.download.setDisabled(False)
            return True
        return False

    @debounce(25, cancel_running=True)
    async def downloadEvent(self) -> None:
        self.download.setDisabled(True)
        self.url.setDisabled(True)
        selection = self.files.selectionModel().selectedRows()
        files = [self.files.item(cast(QModelIndex, index).row(), 0).data(Qt.ItemDataRole.UserRole)
                 for index in selection]
        self.files.setDisabled(True)
        try:
            urls = await asyncio.gather(
                *[getModFileUrls(self.modId, file) for file in files],
            )
        except (RequestError, ResponseError, Exception) as e:
            self.url.setStyleSheet('''
                *{
                    border: 1px solid #B22222;
                    padding: 1px 0px;
                }
                ''')
            self.urlInfo.setText(f'''
                <font color="#888">Could not download mod files: {e}.</font>
                ''')
            return
        try:
            self.signals.download.emit([url[0]['URI'] for url in urls])
        except KeyError as e:
            logger.exception(
                f'Could not find key "{str(e)}" in file download response')
            self.urlInfo.setText(f'''
                <font color="#888">Could not find key "{str(e)}" in file download response.</font>
                ''')
            return
        self.close()
