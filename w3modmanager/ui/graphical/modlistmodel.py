from w3modmanager.core.model import Model
from w3modmanager.util.util import getRuntimePath

from functools import lru_cache
from typing import Optional, Dict, Any

from qtpy.QtCore import Qt, QAbstractTableModel, QModelIndex
from qtpy.QtGui import QFontDatabase, QColor, QIcon
from qtpy.QtWidgets import QWidget


class ModListModel(QAbstractTableModel):
    def __init__(self, parent: Optional[QWidget], model: Model):
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
            ('Date Installed', 'date'),
            ('Version', 'version'),
            ('Source', 'source')
        ]

        self._icons: Dict[str, QIcon] = {}
        self._icons['mod'] = QIcon(str(getRuntimePath('resources/icons/dia.ico')))
        self._icons['dlc'] = QIcon(str(getRuntimePath('resources/icons/puzzle.ico')))
        self._icons['bin'] = QIcon(str(getRuntimePath('resources/icons/folder.ico')))
        self._icons['pat'] = QIcon(str(getRuntimePath('resources/icons/patch.ico')))
        self._icons['???'] = QIcon(str(getRuntimePath('resources/icons/question.ico')))

        self.modmodel = model
        model.updateCallbacks.append(self.update)
        self.update(self.modmodel)

    def update(self, model: Model) -> None:
        self.layoutAboutToBeChanged.emit()
        self.data.cache_clear()
        self._lastUpdate = model.lastUpdate
        self.layoutChanged.emit()
        self.dataChanged.emit(self.index(0, 0), self.index(self.rowCount() - 1, self.columnCount() - 1))

    def getColumnKey(self, column) -> str:
        return self._header[column][1]

    def rowCount(self, _index=QModelIndex()) -> int:
        return len(self.modmodel)

    def columnCount(self, _index=QModelIndex()) -> int:
        return len(self._header)

    def headerData(self, section, orientation, role=Qt.EditRole):
        if role != Qt.DisplayRole:
            return None
        if orientation != Qt.Horizontal:
            return None
        return self._header[section][0] if len(self._header) > section else "?"

    def setData(self, index, value, _role) -> bool:
        if not index.isValid():
            return False
        mod = self.modmodel[index.row()]
        col = self.getColumnKey(index.column())
        if col in ('enabled',):
            if col == 'enabled':
                mod.enabled = True if value == Qt.Checked else False
            self.data.cache_clear()
            self.dataChanged.emit(
                self.index(index.row(), 0),
                self.index(index.row(), self.columnCount() - 1))
            return True
        return False

    def flags(self, index) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable

    @lru_cache(maxsize=None)
    def data(self, index, role=Qt.DisplayRole) -> Any:
        if not index.isValid():
            return None
        col = self.getColumnKey(index.column())
        if not col:
            return None

        if role == Qt.FontRole:
            if col in ('datatype', 'size'):
                return QFontDatabase.systemFont(QFontDatabase.FixedFont)
            return None

        if role == Qt.CheckStateRole:
            if col in ('enabled',):
                mod = self.modmodel[index.row()]
                item = mod[col]
                return Qt.Checked if item else Qt.Unchecked
            return None

        if role == Qt.BackgroundRole:
            mod = self.modmodel[index.row()]
            if not mod.enabled:
                return QColor(240, 240, 240)
            if col in ('priority',) and mod.datatype not in ('mod', 'udf'):
                return QColor(240, 240, 240)
            if mod.date > self._lastUpdate:
                return QColor(238, 242, 255)
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
                return self._icons[val] if val in self._icons else self._icons['???']
            return None

        if role == Qt.ToolTipRole:
            mod = self.modmodel[index.row()]
            return str(mod[col])

        if role == Qt.TextAlignmentRole:
            if col in ('size',):
                # Right|VCenter
                return 0x0082
            if col in ('priority', 'date', 'binFiles', 'menuFiles', 'settings',
                       'inputs', 'contentFiles', 'scriptFiles',):
                # HCenter|VCenter
                return 0x0084
            # Left|VCenter
            return 0x0081

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
            if col in ('date',):
                return mod[col].strftime('%Y-%m-%d %H:%M:%S')
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
