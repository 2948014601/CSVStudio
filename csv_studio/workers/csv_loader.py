from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from csv_studio.services.csv_service import build_index, inspect_csv_preview


class CsvLoadWorker(QObject):
    preview_ready = Signal(object)
    completed = Signal(object)
    failed = Signal(str)
    status = Signal(str)
    progress = Signal(int, str)

    def __init__(self, file_path: str | Path, chunk_size: int = 2000, sample_rows: int = 1000) -> None:
        super().__init__()
        self.file_path = str(file_path)
        self.chunk_size = chunk_size
        self.sample_rows = sample_rows

    @Slot()
    def run(self) -> None:
        try:
            self.status.emit("正在读取 CSV 预览与字段信息…")
            self.progress.emit(4, "正在读取 CSV 预览与字段信息…")
            preview_metadata = inspect_csv_preview(
                self.file_path,
                chunk_size=self.chunk_size,
                sample_rows=self.sample_rows,
            )
            self.preview_ready.emit(preview_metadata)
            self.progress.emit(10, "预览已准备完成，正在后台建立完整索引…")

            full_index = build_index(
                preview_metadata.file_path,
                self.chunk_size,
                progress_callback=lambda percent, message: self.progress.emit(percent, message),
            )
            full_metadata = replace(preview_metadata, index=full_index)
            self.progress.emit(100, "索引建立完成")
            self.completed.emit(full_metadata)
        except Exception as exc:
            self.failed.emit(str(exc))
