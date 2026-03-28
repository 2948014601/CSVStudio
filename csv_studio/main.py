from __future__ import annotations

import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from csv_studio.main_window import MainWindow
from csv_studio.styles import APP_STYLESHEET, build_palette


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("CSV Studio")
    app.setStyle("Fusion")
    app.setPalette(build_palette())
    app.setStyleSheet(APP_STYLESHEET)
    app.setFont(QFont("Microsoft YaHei UI", 10))

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
