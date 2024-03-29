from w3modmanager.core.model import Model
from w3modmanager.util.util import createAsyncTask, getRuntimePath

import asyncio

from functools import cache
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, QSettings, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QWidget


class ModListModel(QAbstractTableModel):
    def __init__(self, parent: QWidget | None, model: Model) -> None:
        super().__init__(parent)

        self.tasks: set[asyncio.Task[Any]] = set()

        self._header = [
            ('', 'enabled'),
            ('Type', 'datatype'),
            ('Package', 'package'),
            ('Name', 'filename'),
            ('Category', 'category'),
            ('Priority', 'priority'),
            ('Content', 'contentFiles'),
            ('Scripts', 'scriptFiles'),
            ('Menus', 'menuFiles'),
            ('Bins', 'binFiles'),
            ('Settings', 'settings'),
            ('Inputs', 'inputs'),
            ('Bundled', 'bundledFiles'),
            ('Size', 'size'),
            ('Date Installed', 'installdate'),
            ('Version', 'version'),
            ('Source', 'source')
        ]

        self._datatypes: dict[str, str] = {}
        self._datatypes['mod'] = 'Mod'
        self._datatypes['dlc'] = 'DLC'
        self._datatypes['bin'] = 'Binary Files'
        self._datatypes['pat'] = 'Patch'
        self._datatypes['udf'] = 'Undefined / Mod?'

        self.setIcons()

        self._lastUpdate = model.lastUpdate
        self._lastInitialization = model.lastInitialization
        self.modmodel = model
        model.updateCallbacks.append(self.update)
        self.update(self.modmodel)

    def setIcons(self) -> None:
        settings = QSettings()
        colored = str(settings.value('iconColors', 'True')) == 'True'

        self._icons: dict[str, QIcon] = {}

        pixmap = QPixmap(str(getRuntimePath('resources/icons/dia.ico')))
        painter = QPainter(pixmap)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), QColor('#427aa1') if colored else QColor('#333333'))
        painter.end()
        self._icons['mod'] = QIcon(pixmap)

        pixmap = QPixmap(str(getRuntimePath('resources/icons/puzzle.ico')))
        painter = QPainter(pixmap)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), QColor('#aad576') if colored else QColor('#333333'))
        painter.end()
        self._icons['dlc'] = QIcon(pixmap)

        pixmap = QPixmap(str(getRuntimePath('resources/icons/folder.ico')))
        painter = QPainter(pixmap)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), QColor('#e94600') if colored else QColor('#333333'))
        painter.end()
        self._icons['bin'] = QIcon(pixmap)

        pixmap = QPixmap(str(getRuntimePath('resources/icons/patch.ico')))
        painter = QPainter(pixmap)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), QColor('#9a6700') if colored else QColor('#333333'))
        painter.end()
        self._icons['pat'] = QIcon(pixmap)

        pixmap = QPixmap(str(getRuntimePath('resources/icons/question.ico')))
        painter = QPainter(pixmap)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), QColor('#ffcf40') if colored else QColor('#333333'))
        painter.end()
        self._icons['udf'] = QIcon(pixmap)

        pixmap = QPixmap(str(getRuntimePath('resources/icons/sparkles.ico')))
        painter = QPainter(pixmap)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), QColor('#ffcf40') if colored else QColor('#333333'))
        painter.end()
        self._icons['spe'] = QIcon(pixmap)

    def clearCache(self) -> None:
        self.data.cache_clear()
        self.flags.cache_clear()
        self.headerData.cache_clear()

    def update(self, model: Model) -> None:
        settings = QSettings()

        self._colorNewest = QColor(242, 255, 242) \
            if settings.value('highlightNewest', 'True') == 'True' else None
        self._colorRecent = QColor(242, 246, 255) \
            if settings.value('highlightRecent', 'True') == 'True' else None
        self._colorUnmanaged = QColor(250, 240, 240) \
            if settings.value('highlightUnmanaged', 'True') == 'True' else None
        self._colorSpecial = QColor(255, 250, 220) \
            if settings.value('highlightSpecial', 'True') == 'True' else None
        self._colorDisabled = QColor(240, 240, 240) \
            if settings.value('highlightDisabled', 'True') == 'True' else None
        self._colorUnavailable = QColor(240, 240, 240)

        self.layoutAboutToBeChanged.emit()
        self.clearCache()
        self._lastUpdate = model.lastUpdate
        self._lastInitialization = model.lastInitialization
        self.layoutChanged.emit()
        self.dataChanged.emit(self.index(0, 0), self.index(
            self.rowCount() - 1, self.columnCount() - 1))

    def getColumnKey(self, column: int) -> str:
        return self._header[column][1]

    async def setDataInternal(self, col: str, row: int, value: str) -> None:
        if col in ('filename',):
            mod = self.modmodel[row]
            await self.modmodel.setFilename(mod, value)
            self.data.cache_clear()
            self.dataChanged.emit(
                self.index(row, 0),
                self.index(row, self.columnCount() - 1))
        if col in ('package',):
            mod = self.modmodel[row]
            await self.modmodel.setPackage(mod, value)
            self.data.cache_clear()
            self.dataChanged.emit(
                self.index(row, 0),
                self.index(row, self.columnCount() - 1))
        if col in ('category',):
            mod = self.modmodel[row]
            await self.modmodel.setCategory(mod, value)
            self.data.cache_clear()
            self.dataChanged.emit(
                self.index(row, 0),
                self.index(row, self.columnCount() - 1))
        if col in ('priority',):
            mod = self.modmodel[row]
            try:
                priority = max(-1, min(9999, int(value)))
            except ValueError:
                priority = -1
            await self.modmodel.setPriority(mod, priority)
            self.data.cache_clear()
            self.dataChanged.emit(
                self.index(row, 0),
                self.index(row, self.columnCount() - 1))

    def setData(self, index: QModelIndex | QPersistentModelIndex, value: Any, _role: int = 0) -> bool:
        if not index.isValid():
            return False
        col = self.getColumnKey(index.column())
        row = index.row()
        createAsyncTask(self.setDataInternal(col, row, str(value)), self.tasks)
        return True

    def rowCount(self, index: QModelIndex | QPersistentModelIndex | None = None) -> int:
        return len(self.modmodel)

    def columnCount(self, index: QModelIndex | QPersistentModelIndex | None = None) -> int:
        return len(self._header)

    @cache  # noqa: B019
    def headerData(
        self, section: int, orientation: Qt.Orientation, role: Qt.ItemDataRole = Qt.ItemDataRole.EditRole
    ) -> Any:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation != Qt.Orientation.Horizontal:
            return None
        return self._header[section][0] if len(self._header) > section else '?'

    @cache  # noqa: B019
    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        col = self.getColumnKey(index.column())
        if col in ('package', 'filename', 'category', 'priority',):
            mod = self.modmodel[index.row()]
            # TODO: disallow editing for special 0000 mods
            if col in ('priority',) and mod.datatype not in ('mod', 'udf',):
                return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    @cache  # noqa: B019
    def data(self, index: QModelIndex, role: Qt.ItemDataRole = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        col = self.getColumnKey(index.column())
        if not col:
            return None

        if role == Qt.ItemDataRole.FontRole:
            if col in ('datatype', 'size',):
                return QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
            elif col in ('scriptFiles',):
                mod = self.modmodel[index.row()]
                if mod.filename in self.modmodel.conflicts.scripts \
                and self.modmodel.conflicts.scripts[mod.filename]:
                    font = QFont()
                    font.setBold(True)
                    return font
            return None

        if role == Qt.ItemDataRole.CheckStateRole:
            if col in ('enabled',):
                mod = self.modmodel[index.row()]
                val = mod[col]
                return Qt.CheckState.Checked if val else Qt.CheckState.Unchecked
            return None

        if role == Qt.ItemDataRole.BackgroundRole:
            mod = self.modmodel[index.row()]
            if not mod.enabled:
                return self._colorDisabled
            if col in ('priority',) and mod.datatype not in ('mod', 'udf',):
                return self._colorUnavailable
            if mod.installdate > self._lastUpdate:
                return self._colorNewest
            if mod.installdate > self._lastInitialization:
                return self._colorRecent
            if mod.filename.startswith('mod0000'):
                return self._colorSpecial
            if not mod.installed:
                return self._colorUnmanaged
            return None

        if role == Qt.ItemDataRole.ForegroundRole:
            mod = self.modmodel[index.row()]
            if not mod.enabled:
                return QColor(60, 60, 60)
            elif col in ('scriptFiles',):
                if mod.filename in self.modmodel.conflicts.scripts \
                and self.modmodel.conflicts.scripts[mod.filename]:
                    return QColor('#e94600')
            elif col in ('bundledFiles',):
                if mod.filename in self.modmodel.conflicts.bundled \
                and self.modmodel.conflicts.bundled[mod.filename]:
                    return QColor('#9a6700')
            return None

        if role == Qt.ItemDataRole.DecorationRole:
            if col in ('datatype',):
                mod = self.modmodel[index.row()]
                if mod.filename.startswith('mod0000'):
                    return self._icons['spe']
                val = mod[col]
                return self._icons[val] if val in self._icons else self._icons['udf']
            return None

        if role == Qt.ItemDataRole.ToolTipRole:
            mod = self.modmodel[index.row()]
            if col in ('datatype',):
                val = mod[col]
                return self._datatypes[val] if val in self._datatypes else self._datatypes['udf']
            if col in ('enabled',):
                val = mod[col]
                return 'Enabled' if val else 'Disabled'
            tip = str(mod[col])
            if len(tip) > 2000:
                return tip[:2000] + ' ...'
            return tip

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col in ('size',):
                # Right|VCenter
                return 0x0082
            if col in ('priority', 'installdate', 'binFiles', 'menuFiles', 'settings',
                       'inputs', 'contentFiles', 'scriptFiles', 'bundledFiles',):
                # HCenter|VCenter
                return 0x0084
            # Left|VCenter
            return 0x0081

        if role == Qt.ItemDataRole.EditRole:
            if col in ('package', 'filename', 'category', 'priority',):
                mod = self.modmodel[index.row()]
                return str(mod[col])
            return None

        # role used for sorting
        if role == Qt.ItemDataRole.UserRole:
            mod = self.modmodel[index.row()]
            if col in ('priority',):
                return f'{"-" if int(mod[col]) < 0 else "+"}{abs(int(mod[col])): >20} {mod["filename"]}'
            if col in ('size',):
                return int(mod[col])
            if col in ('binFiles', 'menuFiles', 'contentFiles', \
                       'scriptFiles', 'settings', 'inputs', 'bundledFiles',):
                return len(mod[col])
            return str(mod[col])

        if role == Qt.ItemDataRole.DisplayRole:
            if col in ('enabled',):
                return None
            mod = self.modmodel[index.row()]
            if col in ('datatype',):
                return str(mod[col]).upper()
            if col in ('priority',):
                val = mod[col]
                if val < 0:
                    return 'none'
                return val
            if col in ('installdate',):
                return mod[col].astimezone(tz=None).strftime('%Y-%m-%d %H:%M:%S')
            if col in ('size',):
                val = mod[col]
                frm = 'b'
                val /= 1024
                frm = 'K'
                if val // 1024:
                    val /= 1024
                    frm = 'M'
                return f'{val:.1f} {frm}'
            if col in ('inputs', 'settings',):
                val = 0
                for s in mod[col]:
                    for n in s.config.sections():
                        val += len(s.config.items(n))
                return val if val else None

            if col in ('binFiles', 'menuFiles', 'contentFiles', 'scriptFiles', 'bundledFiles',):
                val = len(mod[col])
                if val < 1:
                    return ''
                return val
            return str(mod[col])

        return None
