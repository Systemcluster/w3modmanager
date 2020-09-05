from w3modmanager.core.model import Model
from w3modmanager.util.util import getRuntimePath

from functools import lru_cache
from typing import Optional, Dict, Any
import asyncio

from PySide2.QtCore import Qt, QAbstractTableModel, QModelIndex
from PySide2.QtGui import QFontDatabase, QColor, QIcon
from PySide2.QtWidgets import QWidget


class ModListModel(QAbstractTableModel):
    def __init__(self, parent: Optional[QWidget], model: Model) -> None:
        super().__init__(parent)

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
            ('Size', 'size'),
            ('Date Installed', 'installdate'),
            ('Version', 'version'),
            ('Source', 'source')
        ]

        self._icons: Dict[str, QIcon] = {}
        self._icons['mod'] = QIcon(str(getRuntimePath('resources/icons/dia.ico')))
        self._icons['dlc'] = QIcon(str(getRuntimePath('resources/icons/puzzle.ico')))
        self._icons['bin'] = QIcon(str(getRuntimePath('resources/icons/folder.ico')))
        self._icons['pat'] = QIcon(str(getRuntimePath('resources/icons/patch.ico')))
        self._icons['udf'] = QIcon(str(getRuntimePath('resources/icons/question.ico')))

        self._datatypes: Dict[str, str] = {}
        self._datatypes['mod'] = 'Mod'
        self._datatypes['dlc'] = 'DLC'
        self._datatypes['bin'] = 'Binary Files'
        self._datatypes['pat'] = 'Patch'
        self._datatypes['udf'] = 'Undefined / Mod?'

        self._lastUpdate = model.lastUpdate
        self._lastInitialization = model.lastInitialization
        self.modmodel = model
        model.updateCallbacks.append(self.update)
        self.update(self.modmodel)

    def clearCache(self) -> None:
        self.rowCount.cache_clear()
        self.columnCount.cache_clear()
        self.data.cache_clear()
        self.flags.cache_clear()
        self.headerData.cache_clear()

    def update(self, model: Model) -> None:
        self.layoutAboutToBeChanged.emit()
        self.clearCache()
        self._lastUpdate = model.lastUpdate
        self._lastInitialization = model.lastInitialization
        self.layoutChanged.emit()
        self.dataChanged.emit(self.index(0, 0), self.index(self.rowCount() - 1, self.columnCount() - 1))

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
            await self.modmodel.setPriority(mod, max(-1, min(9999, int(value))))
            self.data.cache_clear()
            self.dataChanged.emit(
                self.index(row, 0),
                self.index(row, self.columnCount() - 1))

    def setData(self, index: QModelIndex, value: Any, _role: int = 0) -> bool:
        if not index.isValid():
            return False
        col = self.getColumnKey(index.column())
        row = index.row()
        asyncio.create_task(self.setDataInternal(col, row, str(value)))
        return True

    @lru_cache(maxsize=None)
    def rowCount(self, _index: QModelIndex = None) -> int:
        return len(self.modmodel)

    @lru_cache(maxsize=None)
    def columnCount(self, _index: QModelIndex = None) -> int:
        return len(self._header)

    @lru_cache(maxsize=None)
    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.EditRole) -> Any:
        if role != Qt.DisplayRole:
            return None
        if orientation != Qt.Horizontal:
            return None
        return self._header[section][0] if len(self._header) > section else '?'

    @lru_cache(maxsize=None)
    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.NoItemFlags
        col = self.getColumnKey(index.column())
        if col in ('package', 'filename', 'category', 'priority',):
            mod = self.modmodel[index.row()]
            if col in ('priority',) and mod.datatype not in ('mod', 'udf',):
                return Qt.ItemIsEnabled | Qt.ItemIsSelectable
            return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    @lru_cache(maxsize=None)
    def data(self, index: QModelIndex, role: Qt.ItemDataRole = Qt.DisplayRole) -> Any:
        if not index.isValid():
            return None
        col = self.getColumnKey(index.column())
        if not col:
            return None

        if role == Qt.FontRole:
            if col in ('datatype', 'size',):
                return QFontDatabase.systemFont(QFontDatabase.FixedFont)
            return None

        if role == Qt.CheckStateRole:
            if col in ('enabled',):
                mod = self.modmodel[index.row()]
                val = mod[col]
                return Qt.Checked if val else Qt.Unchecked
            return None

        if role == Qt.BackgroundRole:
            mod = self.modmodel[index.row()]
            if not mod.enabled:
                return QColor(240, 240, 240)
            if col in ('priority',) and mod.datatype not in ('mod', 'udf',):
                return QColor(240, 240, 240)
            if mod.installdate > self._lastUpdate:
                return QColor(242, 255, 242)
            if mod.installdate > self._lastInitialization:
                return QColor(242, 246, 255)
            if not mod.installed:
                return QColor(250, 240, 240)
            return None

        if role == Qt.ForegroundRole:
            mod = self.modmodel[index.row()]
            if not mod.enabled:
                return QColor(60, 60, 60)
            return None

        if role == Qt.DecorationRole:
            if col in ('datatype',):
                mod = self.modmodel[index.row()]
                val = mod[col]
                return self._icons[val] if val in self._icons else self._icons['udf']
            return None

        if role == Qt.ToolTipRole:
            mod = self.modmodel[index.row()]
            if col in ('datatype',):
                val = mod[col]
                return self._datatypes[val] if val in self._datatypes else self._datatypes['udf']
            if col in ('enabled',):
                val = mod[col]
                return 'Enabled' if val else 'Disabled'
            return str(mod[col])

        if role == Qt.TextAlignmentRole:
            if col in ('size',):
                # Right|VCenter
                return 0x0082
            if col in ('priority', 'installdate', 'binFiles', 'menuFiles', 'settings',
                       'inputs', 'contentFiles', 'scriptFiles',):
                # HCenter|VCenter
                return 0x0084
            # Left|VCenter
            return 0x0081

        if role == Qt.EditRole:
            if col in ('package', 'filename', 'category', 'priority',):
                mod = self.modmodel[index.row()]
                return str(mod[col])
            return None

        # role used for sorting
        if role == Qt.UserRole:
            mod = self.modmodel[index.row()]
            if col in ('priority',):
                return f'{int(mod[col]): >20} {mod["filename"]}'
            if col in ('size',):
                return int(mod[col])
            if col in ('binFiles', 'menuFiles', 'contentFiles', \
                       'scriptFiles', 'settings', 'inputs',):
                return len(mod[col])
            return str(mod[col])

        if role == Qt.DisplayRole:
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
                return '%.1f %s' % (val, frm)
            if col in ('inputs', 'settings',):
                val = 0
                for s in mod[col]:
                    for n in s.config.sections():
                        val += len(s.config.items(n))
                return val if val else None

            if col in ('binFiles', 'menuFiles', 'contentFiles', 'scriptFiles',):
                val = len(mod[col])
                if val < 1:
                    return ''
                return val
            return str(mod[col])

        return None
