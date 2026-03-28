from __future__ import annotations

import csv
import re
from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QObject, Qt, Signal
from PySide6.QtGui import QColor, QFont

from csv_studio.services.csv_service import ChunkedCsvSource, CsvMetadata, inspect_csv, save_csv_with_edits


NUMERIC_RE = re.compile(r"^[+-]?(\d+(\.\d+)?|\.\d+)$")
DATE_RE = re.compile(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}")
EDITED_CELL_BACKGROUND = QColor("#E8F3EC")
NULL_FOREGROUND = QColor("#94A3B8")
TEXT_FOREGROUND = QColor("#0F172A")
ERROR_FOREGROUND = QColor("#B91C1C")
ERROR_BACKGROUND = QColor("#FEE2E2")


class CsvTableModel(QAbstractTableModel):
    metadata_changed = Signal(object)
    cache_changed = Signal(int)
    dirty_state_changed = Signal(bool, int)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.metadata: CsvMetadata | None = None
        self.source: ChunkedCsvSource | None = None
        self._edited_cells: dict[tuple[int, int], str] = {}
        self._null_font = QFont()
        self._null_font.setItalic(True)

    def open_file(self, file_path: str, chunk_size: int = 2000) -> CsvMetadata:
        metadata = inspect_csv(file_path, chunk_size=chunk_size)
        self.set_metadata(metadata)
        return metadata

    def set_metadata(self, metadata: CsvMetadata) -> None:
        self.beginResetModel()
        self.metadata = metadata
        self.source = ChunkedCsvSource(metadata)
        self._edited_cells.clear()
        self.endResetModel()
        self.metadata_changed.emit(metadata)
        self.cache_changed.emit(self.cached_chunk_count())
        self.dirty_state_changed.emit(False, 0)

    def clear(self) -> None:
        self.beginResetModel()
        self.metadata = None
        self.source = None
        self._edited_cells.clear()
        self.endResetModel()
        self.cache_changed.emit(0)
        self.dirty_state_changed.emit(False, 0)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid() or not self.metadata:
            return 0
        return self.metadata.index.row_count

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid() or not self.metadata:
            return 0
        return self.metadata.column_count

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.ItemIsEnabled
        return Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> object:
        if not index.isValid() or not self.metadata or not self.source:
            return None

        value = self.raw_value(index.row(), index.column())
        is_null = value == ""
        is_edited = (index.row(), index.column()) in self._edited_cells
        is_error = value.upper() in {"ERROR", "INVALID", "#N/A"}

        if role in {Qt.DisplayRole, Qt.EditRole}:
            return "" if role == Qt.EditRole and is_null else ("NULL" if is_null else value)

        if role == Qt.ToolTipRole:
            return value if value else "空值"

        if role == Qt.ForegroundRole:
            if is_null:
                return NULL_FOREGROUND
            if is_error:
                return ERROR_FOREGROUND
            return TEXT_FOREGROUND

        if role == Qt.BackgroundRole:
            if is_error:
                return ERROR_BACKGROUND
            if is_edited:
                return EDITED_CELL_BACKGROUND

        if role == Qt.FontRole and is_null:
            return self._null_font

        if role == Qt.TextAlignmentRole:
            if NUMERIC_RE.match(value):
                return int(Qt.AlignRight | Qt.AlignVCenter)
            if DATE_RE.match(value):
                return int(Qt.AlignHCenter | Qt.AlignVCenter)
            return int(Qt.AlignLeft | Qt.AlignVCenter)

        return None

    def setData(self, index: QModelIndex, value: object, role: int = Qt.EditRole) -> bool:
        if role != Qt.EditRole or not index.isValid() or not self.metadata:
            return False

        text = "" if value is None else str(value)
        row = index.row()
        column = index.column()
        original = self.base_value(row, column)
        key = (row, column)

        if text == original:
            self._edited_cells.pop(key, None)
        else:
            self._edited_cells[key] = text

        self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole, Qt.ToolTipRole, Qt.BackgroundRole])
        self.dirty_state_changed.emit(self.has_unsaved_changes(), self.edited_cell_count())
        return True

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> object:
        if role != Qt.DisplayRole or not self.metadata:
            return None
        if orientation == Qt.Horizontal:
            if section >= len(self.metadata.headers):
                return None
            profile = self.metadata.column_profiles[section]
            excel_name = self._excel_column_name(section)
            return f"{excel_name}  {profile.name} · {profile.dtype_hint}"
        return str(section + 1)

    def base_value(self, row: int, column: int) -> str:
        if not self.metadata or not self.source:
            return ""
        chunk_size = self.metadata.index.chunk_size
        chunk_index = row // chunk_size
        row_in_chunk = row % chunk_size
        chunk = self.source.get_chunk(chunk_index)
        self.cache_changed.emit(self.cached_chunk_count())
        if row_in_chunk >= len(chunk) or column >= len(chunk[row_in_chunk]):
            return ""
        value = chunk[row_in_chunk][column]
        if value is None:
            return ""
        text = str(value)
        if text.lower() in {"nan", "none", "null"}:
            return ""
        return text

    def raw_value(self, row: int, column: int) -> str:
        edited = self._edited_cells.get((row, column))
        if edited is not None:
            return edited
        return self.base_value(row, column)

    def revert_cell(self, row: int, column: int) -> bool:
        key = (row, column)
        if key not in self._edited_cells:
            return False
        del self._edited_cells[key]
        index = self.index(row, column)
        self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole, Qt.ToolTipRole, Qt.BackgroundRole])
        self.dirty_state_changed.emit(self.has_unsaved_changes(), self.edited_cell_count())
        return True

    def has_unsaved_changes(self) -> bool:
        return bool(self._edited_cells)

    def edited_cell_count(self) -> int:
        return len(self._edited_cells)

    def write_edits(self, target_path: str | Path | None = None) -> tuple[Path, int]:
        if not self.metadata:
            raise RuntimeError("当前没有打开的 CSV 文件。")
        return save_csv_with_edits(self.metadata, self._edited_cells, target_path)

    def cached_chunk_count(self) -> int:
        return self.source.cached_chunk_count() if self.source else 0

    def column_values(self, column: int, limit: int = 400) -> list[str]:
        if not self.source:
            return []
        return self.source.sample_column_values(column, limit=limit)

    def column_profile(self, column: int):
        if not self.metadata or column >= len(self.metadata.column_profiles):
            return None
        return self.metadata.column_profiles[column]

    def preview_headers(self) -> list[str]:
        if not self.metadata:
            return []
        return list(self.metadata.headers)

    def preview_rows(self, limit: int = 2000) -> list[list[str]]:
        if not self.metadata:
            return []
        row_total = min(limit, self.rowCount())
        rows: list[list[str]] = []
        for row_index in range(row_total):
            rows.append([self.raw_value(row_index, column_index) for column_index in range(self.columnCount())])
        return rows

    def export_preview_csv(self, file_path: str, limit: int = 2000) -> int:
        headers = self.preview_headers()
        rows = self.preview_rows(limit=limit)
        with open(file_path, "w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(headers)
            writer.writerows(rows)
        return len(rows)

    @staticmethod
    def _excel_column_name(index: int) -> str:
        result = []
        value = index + 1
        while value:
            value, remainder = divmod(value - 1, 26)
            result.append(chr(65 + remainder))
        return "".join(reversed(result))
