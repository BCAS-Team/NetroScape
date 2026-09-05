"""
title_bar.py

A hand-drawn title bar to replace the OS's native one, so we can get
the XP Luna blue gradient look. This means the main window runs
frameless (Qt.FramelessWindowHint) and we handle dragging and the
minimize/maximize/close buttons ourselves.
"""

from PySide6.QtCore import Qt, QPoint, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QSizePolicy

from xp_theme import TITLE_BAR_HEIGHT, TITLE_BUTTON_HEIGHT, TITLE_BUTTON_WIDTH, icon_path


class TitleBar(QWidget):
    minimize_clicked = Signal()
    maximize_clicked = Signal()
    close_clicked = Signal()

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("TitleBar")
        try:
            self.setFixedHeight(int(TITLE_BAR_HEIGHT))
        except (TypeError, ValueError):
            self.setFixedHeight(28)
        # Plain QWidget subclasses don't paint their QSS `background` by
        # default (only "complex" built-in widgets like QMenuBar/QToolBar
        # do that automatically). Without this attribute, #TitleBar's
        # gradient is silently ignored and the parent's default light
        # background shows through instead - which is why the bar looked
        # pale lavender instead of the navy gradient, and why white text/
        # glyphs on top of it kept disappearing.
        self.setAttribute(Qt.WA_StyledBackground, True)

        self._drag_pos: QPoint | None = None

        self.title_label = QLabel(title)
        self.title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        min_btn = QPushButton()
        max_btn = QPushButton()
        close_btn = QPushButton()
        min_btn.setIcon(self._title_icon("minimize"))
        max_btn.setIcon(self._title_icon("maximize"))
        close_btn.setIcon(self._title_icon("close"))
        min_btn.setToolTip("Minimize")
        max_btn.setToolTip("Maximize or restore")
        close_btn.setToolTip("Close")

        for btn in (min_btn, max_btn, close_btn):
            btn.setObjectName("TitleBarButton")
            btn.setFixedSize(int(TITLE_BUTTON_WIDTH), int(TITLE_BUTTON_HEIGHT))

        close_btn.setObjectName("CloseButton")

        min_btn.clicked.connect(self.minimize_clicked.emit)
        max_btn.clicked.connect(self.maximize_clicked.emit)
        close_btn.clicked.connect(self.close_clicked.emit)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(2)
        layout.addWidget(self.title_label)
        layout.addWidget(min_btn)
        layout.addWidget(max_btn)
        layout.addWidget(close_btn)

    @staticmethod
    def _title_icon(kind: str) -> QIcon:
        configured = icon_path(kind)
        if configured:
            return QIcon(configured)
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, False)
        if kind == "minimize":
            painter.setPen(QPen(QColor("#174A8C"), 2))
            painter.drawLine(3, 12, 13, 12)
            painter.setPen(QPen(QColor("#FFFFFF"), 2))
            painter.drawLine(3, 10, 13, 10)
        elif kind == "maximize":
            painter.setPen(QPen(QColor("#174A8C"), 2))
            painter.drawRect(3, 4, 10, 10)
            painter.setPen(QPen(QColor("#FFFFFF"), 2))
            painter.drawRect(3, 3, 10, 10)
        else:
            painter.setPen(QPen(QColor("#174A8C"), 3))
            painter.drawLine(3, 4, 12, 13)
            painter.drawLine(12, 4, 3, 13)
            painter.setPen(QPen(QColor("#FFFFFF"), 2))
            painter.drawLine(3, 3, 12, 12)
            painter.drawLine(12, 3, 3, 12)
        painter.end()
        return QIcon(pixmap)

    def set_title(self, text: str):
        self.title_label.setText(text)

    # --- window dragging ---
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            window = self.window()
            delta = event.globalPosition().toPoint() - self._drag_pos
            window.move(window.pos() + delta)
            self._drag_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.maximize_clicked.emit()