from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QToolButton


class TitleBar(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("TitleBar")
        self._drag_offset: QPoint | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 10, 8)
        layout.setSpacing(10)

        self.icon_label = QLabel("▦")
        self.icon_label.setStyleSheet("color:#217346;font-size:18px;font-weight:700;")
        self.title_label = QLabel("CSV Studio")
        self.title_label.setStyleSheet("font-size:14px;font-weight:700;")
        self.current_file_label = QLabel("未打开文件")
        self.current_file_label.setProperty("role", "muted")
        self.save_state_label = QLabel("未保存")
        self.save_state_label.setProperty("role", "tag")
        self.avatar_label = QLabel("数据工作台")
        self.avatar_label.setProperty("role", "tag")

        self.min_button = QToolButton()
        self.min_button.setObjectName("TitleControl")
        self.min_button.setText("一")
        self.max_button = QToolButton()
        self.max_button.setObjectName("TitleControl")
        self.max_button.setText("□")
        self.close_button = QToolButton()
        self.close_button.setObjectName("TitleCloseButton")
        self.close_button.setText("×")

        self.min_button.clicked.connect(lambda: self.window().showMinimized())
        self.max_button.clicked.connect(self._toggle_max_restore)
        self.close_button.clicked.connect(lambda: self.window().close())

        layout.addWidget(self.icon_label)
        layout.addWidget(self.title_label)
        layout.addStretch(1)
        layout.addWidget(self.current_file_label)
        layout.addWidget(self.save_state_label)
        layout.addStretch(1)
        layout.addWidget(self.avatar_label)
        layout.addWidget(self.min_button)
        layout.addWidget(self.max_button)
        layout.addWidget(self.close_button)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.window().frameGeometry().topLeft()
            event.accept()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_offset and event.buttons() & Qt.LeftButton and not self.window().isMaximized():
            self.window().move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._toggle_max_restore()
            event.accept()
        super().mouseDoubleClickEvent(event)

    def _toggle_max_restore(self) -> None:
        window = self.window()
        if window.isMaximized():
            window.showNormal()
            self.max_button.setText("□")
        else:
            window.showMaximized()
            self.max_button.setText("❐")
