from w3modmanager.core.model import Model
from w3modmanager.domain.mod.mod import Mod
from w3modmanager.util.util import getRuntimePath

from functools import lru_cache, cmp_to_key
from typing import List, Optional, Dict, Any

from qtpy.QtCore import Qt, QAbstractTableModel, QModelIndex
from qtpy.QtGui import QFontDatabase, QColor, QIcon
from qtpy.QtWidgets import QWidget, QAbstractItemView


class ModListModel(QAbstractTableModel):
    def __init__(self, parent: Optional[QWidget] = None, model: Optional[Model] = None):
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

        self._sortColumn = None
        self._sortOrder = None

        self._values: List[Mod] = []
        self.update(model)

    def update(self, model: Optional[Model] = None) -> None:
        self.data.cache_clear()
        if model:
            self.layoutAboutToBeChanged.emit()
            self._values = model.all()
            self._lastUpdate = model.lastUpdate
            self.layoutChanged.emit()
        self.dataChanged.emit(self.index(0, 0), self.index(self.rowCount() - 1, self.columnCount() - 1))

    def getMod(self, row: int) -> Mod:
        return self._values[row]

    def getColumnKey(self, column) -> str:
        return self._header[column][1]

    def rowCount(self, _index=QModelIndex()) -> int:
        return len(self._values) if self._values else 0

    def columnCount(self, _index=QModelIndex()) -> int:
        return len(self._header)

    def headerData(self, section, orientation, role=Qt.EditRole):
        if role != Qt.DisplayRole:
            return None
        if orientation != Qt.Horizontal:
            return None
        return self._header[section][0] if len(self._header) > section else "?"

    def sort(self, column=None, order=None) -> None:
        # cache last used sort configuration
        if column is not None:
            self._sortColumn = column
        else:
            column = self._sortColumn
        if order is not None:
            self._sortOrder = order
        else:
            order = self._sortOrder
        if column is None or order is None:
            return

        # remember selected rows
        selection = [self._values[row.row()].filename for row in self.parent().selectionModel().selectedRows()]

        col = self.getColumnKey(column)

        def compare(lhs, rhs, col=col):
            item1 = lhs[col]
            item2 = rhs[col]
            bothinstance = lambda t: isinstance(item1, t) and isinstance(item2, t) # noqa
            if bothinstance(bool):
                diff = int(item1) - int(item2)
            elif bothinstance(int) or bothinstance(str) and item1.isdecimal():
                diff = int(item1) - int(item2)
            elif bothinstance(str):
                diff = 1 if item1.lower() > item2.lower() else -1 if item1.lower() < item2.lower() else 0
            elif bothinstance((list, )):
                diff = len(item1) - len(item2)
            else:
                diff = 0
            if not diff and col == 'priority':
                return compare(lhs, rhs, 'filename')
            return diff

        self._values = sorted(
            self._values,
            key=cmp_to_key(compare),
            reverse=order == Qt.DescendingOrder)

        # restore selected rows
        self.parent().selectionModel().clear()
        self.parent().setSelectionMode(QAbstractItemView.MultiSelection)
        for row, mod in enumerate(self._values):
            if mod.filename in selection:
                self.parent().selectRow(row)
        self.parent().setSelectionMode(QAbstractItemView.ExtendedSelection)

        self.update()

    def setData(self, index, value, _role) -> bool:
        if not index.isValid():
            return False
        mod = self._values[index.row()]
        col = self.getColumnKey(index.column())
        if col in ('enabled',):
            if col == 'enabled':
                mod.enabled = True if value == Qt.Checked else False
            self.data.cache_clear()
            self.dataChanged.emit(
                self.index(index.row(), 0),
                self.index(index.row(), self.columnCount() - 1))
            self.sort()
            return True
        return False

    def flags(self, index) -> Qt.ItemFlag:
        if not index.isValid():
            return None
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
                item = self._values[index.row()][col]
                return Qt.Checked if item else Qt.Unchecked
            return None

        if role == Qt.BackgroundRole:
            if not self._values[index.row()].enabled:
                return QColor(240, 240, 240)
            if col in ('priority',) and self._values[index.row()].datatype not in ('mod', 'udf'):
                return QColor(240, 240, 240)
            if self._values[index.row()].date > self._lastUpdate:
                return QColor(238, 242, 255)
            return None

        if role == Qt.ForegroundRole:
            if not self._values[index.row()].enabled:
                return QColor(60, 60, 60)
            return None

        if role == Qt.DecorationRole:
            if col in ('datatype',):
                val = self._values[index.row()][col]
                return self._icons[val] if val in self._icons else self._icons['???']
            return None

        if role == Qt.ToolTipRole:
            return str(self._values[index.row()][col])

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

        if role == Qt.DisplayRole:
            if col in ('enabled',):
                return None
            if col in ('datatype',):
                return str(self._values[index.row()][col]).upper()
            if col in ('priority',):
                val = self._values[index.row()][col]
                if val < 0:
                    return 'none'
                return val
            if col in ('date',):
                return self._values[index.row()][col].strftime('%Y-%m-%d %H:%M:%S')
            if col in ('size',):
                val = self._values[index.row()][col]
                frm = 'b'
                val /= 1024
                frm = 'K'
                if val // 1024:
                    val /= 1024
                    frm = 'M'
                return '%.1f %s' % (val, frm)
            if col in ('inputs', 'settings',):
                val = 0
                for s in self._values[index.row()][col]:
                    for n in s.config.sections():
                        val += len(s.config.items(n))
                return val if val else None

            if col in ('binFiles', 'menuFiles', 'contentFiles', 'scriptFiles',):
                val = len(self._values[index.row()][col])
                if val < 1:
                    return ''
                return val
            return str(self._values[index.row()][col])

        return None
