from typing import List, Optional, Tuple
from math import floor

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QLayout, QSizePolicy, QStyle, QLayoutItem, QWidget


class FlowLayout(QLayout):
    def __init__(self, parent: Optional[QWidget] = None, spacing: Optional[QSize] = None) -> None:
        super().__init__(parent)

        self._spacing = spacing if spacing else QSize(-1, -1)
        self._items: List[QLayoutItem] = []

    def __del__(self) -> None:
        del self._items[:]

    def addItem(self, item: QLayoutItem) -> None:
        self._items.append(item)

    def horizontalSpacing(self) -> int:
        if self._spacing.width() >= 0:
            return self._spacing.width()
        else:
            return self.smartSpacing(QStyle.PM_LayoutHorizontalSpacing)

    def verticalSpacing(self) -> int:
        if self._spacing.height() >= 0:
            return self._spacing.height()
        else:
            return self.smartSpacing(QStyle.PM_LayoutVerticalSpacing)

    def smartSpacing(self, metric: QStyle) -> int:
        parent = self.parent()
        if parent is None:
            return -1
        elif parent.isWidgetType():
            return parent.style().pixelMetric(metric, None, parent)
        else:
            return parent.spacing()

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem:
        if 0 <= index < len(self._items):
            return self._items[index]
        return None  # type: ignore

    def takeAt(self, index: int) -> QLayoutItem:
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None  # type: ignore

    def expandingDirections(self) -> Qt.Orientations:
        return Qt.Horizontal

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self.doLayout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self.doLayout(rect, False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        left, top, right, bottom = self.getContentsMargins()
        size += QSize(left + right, top + bottom)
        return size

    def doLayout(self, rect: QRect, testonly: bool) -> int:
        left, top, right, bottom = self.getContentsMargins()
        effective = rect.adjusted(+left, +top, -right, -bottom)
        x = effective.x()
        y = effective.y()

        lines: List[Tuple[int, List[Tuple[QLayoutItem, QPoint]]]] = []
        line = 0
        lineheight = 0
        for item in self._items:
            widget = item.widget()
            hspace = self.horizontalSpacing()
            if hspace == -1:
                hspace = widget.style().layoutSpacing(
                    QSizePolicy.Preferred,
                    QSizePolicy.Preferred,
                    Qt.Horizontal
                )
            vspace = self.verticalSpacing()
            if vspace == -1:
                vspace = widget.style().layoutSpacing(
                    QSizePolicy.Preferred,
                    QSizePolicy.Preferred,
                    Qt.Vertical
                )
            nextX = x + item.sizeHint().width() + hspace
            if nextX - hspace > effective.right() and lineheight > 0:
                x = effective.x()
                y = y + lineheight + vspace
                nextX = x + item.sizeHint().width() + hspace
                lineheight = 0
                line += 1

            lineheight = max(lineheight, item.sizeHint().height())
            if not testonly:
                if len(lines) <= line:
                    lines.append((lineheight, []))
                else:
                    lines[line] = (max(lines[line][0], lineheight), lines[line][1])
                lines[line][1].append((item, QPoint(x, y)))

            x = nextX

        if not testonly:
            for maxlineheight, current in lines:
                if len(current) > 1:
                    linewidth = sum(line[0].sizeHint().width() for line in current)
                    spacing = floor((effective.right() - linewidth) / (len(current) - 1)) - hspace
                else:
                    spacing = 0
                for i, (item, point) in enumerate(current):
                    item.setGeometry(QRect(
                        QPoint(
                            point.x() + (spacing if i > 0 else 0),
                            point.y() + floor((maxlineheight - item.sizeHint().height()) / 2)
                        ),
                        item.sizeHint() if len(current) > 1
                        else QSize(effective.width(), item.sizeHint().height()))
                    )

        return y + lineheight - rect.y() + bottom
