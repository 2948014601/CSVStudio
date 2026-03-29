from __future__ import annotations

import codecs
import csv
import io
import mmap
import os
import tempfile
from collections import OrderedDict
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable

import pandas as pd


DEFAULT_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030", "gbk", "utf-16")
DELIMITER_CANDIDATES = [",", "\t", ";", "|"]
ProgressCallback = Callable[[int, str], None]


@dataclass(slots=True)
class ColumnProfile:
    name: str
    dtype_hint: str
    null_ratio: float
    unique_count_sample: int


@dataclass(slots=True)
class CsvIndex:
    row_count: int
    chunk_size: int
    chunk_offsets: list[int]


@dataclass(slots=True)
class CsvMetadata:
    file_path: Path
    encoding: str
    delimiter: str
    column_count: int
    headers: list[str]
    preview_rows: list[dict[str, object]]
    column_profiles: list[ColumnProfile]
    null_cells_sample: int
    duplicate_rows_sample: int
    index: CsvIndex


@dataclass(slots=True)
class _ScanConfig:
    unit_size: int
    bom_length: int
    quote_unit: bytes
    lf_unit: bytes
    cr_unit: bytes


def detect_encoding(file_path: Path) -> str:
    for encoding in DEFAULT_ENCODINGS:
        try:
            with file_path.open("r", encoding=encoding) as handle:
                handle.read(4096)
            return encoding
        except UnicodeDecodeError:
            continue
    return "utf-8"


def detect_delimiter(file_path: Path, encoding: str) -> str:
    with file_path.open("r", encoding=encoding, newline="") as handle:
        sample = handle.read(8192)
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=DELIMITER_CANDIDATES)
        return dialect.delimiter
    except csv.Error:
        return ","


def _scan_config(file_path: Path, encoding: str) -> _ScanConfig:
    with file_path.open("rb") as handle:
        prefix = handle.read(4)

    normalized = encoding.lower().replace("_", "-")
    if normalized.startswith("utf-16"):
        if prefix.startswith(codecs.BOM_UTF16_BE):
            return _ScanConfig(
                unit_size=2,
                bom_length=len(codecs.BOM_UTF16_BE),
                quote_unit=b"\x00\x22",
                lf_unit=b"\x00\x0A",
                cr_unit=b"\x00\x0D",
            )
        return _ScanConfig(
            unit_size=2,
            bom_length=len(codecs.BOM_UTF16_LE) if prefix.startswith(codecs.BOM_UTF16_LE) else 0,
            quote_unit=b"\x22\x00",
            lf_unit=b"\x0A\x00",
            cr_unit=b"\x0D\x00",
        )

    return _ScanConfig(
        unit_size=1,
        bom_length=len(codecs.BOM_UTF8) if prefix.startswith(codecs.BOM_UTF8) else 0,
        quote_unit=b'"',
        lf_unit=b"\n",
        cr_unit=b"\r",
    )


def _scan_first_data_offset(file_path: Path, encoding: str) -> int:
    file_size = file_path.stat().st_size
    if file_size == 0:
        return 0

    config = _scan_config(file_path, encoding)
    with file_path.open("rb") as handle, mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as mapped:
        position = config.bom_length
        in_quotes = False
        record_has_content = False

        while position + config.unit_size <= file_size:
            unit = mapped[position : position + config.unit_size]

            if unit == config.quote_unit:
                record_has_content = True
                next_position = position + config.unit_size
                if in_quotes and next_position + config.unit_size <= file_size:
                    next_unit = mapped[next_position : next_position + config.unit_size]
                    if next_unit == config.quote_unit:
                        position = next_position + config.unit_size
                        continue
                in_quotes = not in_quotes
                position = next_position
                continue

            if not in_quotes and unit == config.cr_unit:
                next_position = position + config.unit_size
                if next_position + config.unit_size <= file_size:
                    next_unit = mapped[next_position : next_position + config.unit_size]
                    if next_unit == config.lf_unit:
                        next_position += config.unit_size
                if record_has_content:
                    return next_position
                position = next_position
                continue

            if not in_quotes and unit == config.lf_unit:
                next_position = position + config.unit_size
                if record_has_content:
                    return next_position
                position = next_position
                continue

            if unit not in {config.cr_unit, config.lf_unit}:
                record_has_content = True
            position += config.unit_size

    return file_size


def build_index(
    file_path: Path,
    chunk_size: int,
    progress_callback: ProgressCallback | None = None,
    encoding: str | None = None,
) -> CsvIndex:
    file_size = file_path.stat().st_size
    if file_size == 0:
        if progress_callback:
            progress_callback(100, "空文件，索引完成")
        return CsvIndex(row_count=0, chunk_size=chunk_size, chunk_offsets=[0])

    resolved_encoding = encoding or detect_encoding(file_path)
    config = _scan_config(file_path, resolved_encoding)
    chunk_offsets: list[int] = []
    row_count = 0
    last_reported_percent = -1

    def report(progress_percent: int, message: str) -> None:
        nonlocal last_reported_percent
        progress_percent = max(10, min(progress_percent, 100))
        if progress_callback and progress_percent != last_reported_percent:
            last_reported_percent = progress_percent
            progress_callback(progress_percent, message)

    header_found = False
    in_quotes = False
    record_has_content = False

    def finalize_record(next_record_start: int) -> None:
        nonlocal header_found, row_count, record_has_content
        if not record_has_content:
            return
        if not header_found:
            header_found = True
            chunk_offsets.append(next_record_start)
            report(10, "已定位 CSV 记录边界，开始建立索引…")
        else:
            row_count += 1
            if row_count % chunk_size == 0:
                chunk_offsets.append(next_record_start)
            if row_count % 5000 == 0:
                percent = int(next_record_start / max(file_size, 1) * 88) + 10
                report(percent, f"正在扫描 CSV 记录边界，已处理约 {row_count:,} 行…")
        record_has_content = False

    with file_path.open("rb") as handle, mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as mapped:
        position = config.bom_length
        while position + config.unit_size <= file_size:
            unit = mapped[position : position + config.unit_size]

            if unit == config.quote_unit:
                record_has_content = True
                next_position = position + config.unit_size
                if in_quotes and next_position + config.unit_size <= file_size:
                    next_unit = mapped[next_position : next_position + config.unit_size]
                    if next_unit == config.quote_unit:
                        position = next_position + config.unit_size
                        continue
                in_quotes = not in_quotes
                position = next_position
                continue

            if not in_quotes and unit == config.cr_unit:
                next_position = position + config.unit_size
                if next_position + config.unit_size <= file_size:
                    next_unit = mapped[next_position : next_position + config.unit_size]
                    if next_unit == config.lf_unit:
                        next_position += config.unit_size
                finalize_record(next_position)
                position = next_position
                continue

            if not in_quotes and unit == config.lf_unit:
                next_position = position + config.unit_size
                finalize_record(next_position)
                position = next_position
                continue

            if unit not in {config.cr_unit, config.lf_unit}:
                record_has_content = True
            position += config.unit_size

        if record_has_content:
            finalize_record(file_size)

    if not header_found:
        chunk_offsets = [config.bom_length]

    report(100, f"索引建立完成，共 {row_count:,} 行")
    return CsvIndex(row_count=row_count, chunk_size=chunk_size, chunk_offsets=chunk_offsets or [config.bom_length])


def classify_dtype(sample_series: pd.Series) -> str:
    cleaned = sample_series.dropna().astype(str).str.strip()
    if cleaned.empty:
        return "空值"

    numeric = pd.to_numeric(cleaned, errors="coerce")
    if numeric.notna().mean() > 0.95:
        if cleaned.str.fullmatch(r"[-+]?\d+").mean() > 0.95:
            return "整数"
        return "小数"

    datetimes = pd.to_datetime(cleaned, errors="coerce", format="mixed")
    if datetimes.notna().mean() > 0.8:
        return "日期"

    return "文本"


def inspect_csv_preview(file_path: str | Path, chunk_size: int = 2000, sample_rows: int = 1000) -> CsvMetadata:
    path = Path(file_path)
    encoding = detect_encoding(path)
    delimiter = detect_delimiter(path, encoding)

    try:
        preview_df = pd.read_csv(
            path,
            encoding=encoding,
            sep=delimiter,
            nrows=sample_rows,
            dtype=str,
            keep_default_na=True,
        )
    except pd.errors.EmptyDataError:
        preview_df = pd.DataFrame()

    headers = [str(column) for column in preview_df.columns.tolist()]
    profiles: list[ColumnProfile] = []
    for header in headers:
        series = preview_df[header] if header in preview_df else pd.Series(dtype="object")
        null_ratio = float(series.isna().mean()) if len(series.index) else 0.0
        unique_count = int(series.dropna().nunique())
        profiles.append(
            ColumnProfile(
                name=header,
                dtype_hint=classify_dtype(series),
                null_ratio=null_ratio,
                unique_count_sample=unique_count,
            )
        )

    null_cells_sample = int(preview_df.isna().sum().sum()) if not preview_df.empty else 0
    duplicate_rows_sample = int(preview_df.duplicated().sum()) if not preview_df.empty else 0
    preview_rows = preview_df.head(6).fillna("").to_dict(orient="records")
    preview_index = CsvIndex(
        row_count=int(len(preview_df.index)),
        chunk_size=chunk_size,
        chunk_offsets=[_scan_first_data_offset(path, encoding)],
    )

    return CsvMetadata(
        file_path=path,
        encoding=encoding,
        delimiter=delimiter,
        column_count=len(headers),
        headers=headers,
        preview_rows=preview_rows,
        column_profiles=profiles,
        null_cells_sample=null_cells_sample,
        duplicate_rows_sample=duplicate_rows_sample,
        index=preview_index,
    )


def inspect_csv(file_path: str | Path, chunk_size: int = 2000, sample_rows: int = 1000) -> CsvMetadata:
    preview_metadata = inspect_csv_preview(file_path, chunk_size=chunk_size, sample_rows=sample_rows)
    index = build_index(preview_metadata.file_path, chunk_size, encoding=preview_metadata.encoding)
    return replace(preview_metadata, index=index)


def save_csv_with_edits(
    metadata: CsvMetadata,
    edits: dict[tuple[int, int], str],
    target_path: str | Path | None = None,
) -> tuple[Path, int]:
    source_path = metadata.file_path
    final_path = Path(target_path) if target_path else source_path
    same_target = source_path.resolve() == final_path.resolve()

    row_edits: dict[int, dict[int, str]] = {}
    for (row_index, column_index), value in edits.items():
        row_edits.setdefault(row_index, {})[column_index] = value

    write_path = final_path
    temp_path: Path | None = None
    if same_target:
        fd, temp_name = tempfile.mkstemp(
            prefix=f"{final_path.stem}_",
            suffix=final_path.suffix,
            dir=str(final_path.parent),
        )
        os.close(fd)
        temp_path = Path(temp_name)
        write_path = temp_path

    row_count = 0
    try:
        with source_path.open("r", encoding=metadata.encoding, newline="") as source_handle, write_path.open(
            "w",
            encoding=metadata.encoding,
            newline="",
        ) as target_handle:
            reader = csv.reader(source_handle, delimiter=metadata.delimiter)
            writer = csv.writer(target_handle, delimiter=metadata.delimiter, lineterminator="\n")

            next(reader, None)
            writer.writerow(metadata.headers)

            for row_index, row in enumerate(reader):
                normalized = ["" if value is None else str(value) for value in row]
                if len(normalized) < metadata.column_count:
                    normalized.extend([""] * (metadata.column_count - len(normalized)))
                elif len(normalized) > metadata.column_count:
                    normalized = normalized[: metadata.column_count]

                for column_index, value in row_edits.get(row_index, {}).items():
                    if 0 <= column_index < metadata.column_count:
                        normalized[column_index] = value

                writer.writerow(normalized)
                row_count += 1

        if temp_path is not None:
            temp_path.replace(final_path)
    except Exception:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink(missing_ok=True)
        raise

    return final_path, row_count


class ChunkedCsvSource:
    def __init__(self, metadata: CsvMetadata, cache_size: int = 6) -> None:
        self.metadata = metadata
        self.cache_size = cache_size
        self._cache: OrderedDict[int, list[list[str]]] = OrderedDict()

    def get_chunk(self, chunk_index: int) -> list[list[str]]:
        if chunk_index in self._cache:
            self._cache.move_to_end(chunk_index)
            return self._cache[chunk_index]

        rows = self._read_chunk(chunk_index)
        self._cache[chunk_index] = rows
        while len(self._cache) > self.cache_size:
            self._cache.popitem(last=False)
        return rows

    def cached_chunk_count(self) -> int:
        return len(self._cache)

    def sample_column_values(self, column_index: int, limit: int = 400) -> list[str]:
        values: list[str] = []
        max_chunks = max(1, min(len(self.metadata.index.chunk_offsets), (limit // self.metadata.index.chunk_size) + 2))
        for chunk_index in range(max_chunks):
            for row in self.get_chunk(chunk_index):
                if column_index < len(row):
                    values.append(row[column_index])
                if len(values) >= limit:
                    return values
        return values

    def _read_chunk(self, chunk_index: int) -> list[list[str]]:
        if chunk_index >= len(self.metadata.index.chunk_offsets):
            return []

        rows: list[list[str]] = []
        byte_offset = self.metadata.index.chunk_offsets[chunk_index]
        row_limit = self.metadata.index.chunk_size
        with self.metadata.file_path.open("rb") as raw_handle:
            raw_handle.seek(byte_offset)
            text_handle = io.TextIOWrapper(raw_handle, encoding=self.metadata.encoding, newline="")
            reader = csv.reader(text_handle, delimiter=self.metadata.delimiter)
            while len(rows) < row_limit:
                try:
                    row = next(reader)
                except StopIteration:
                    break
                if row == []:
                    continue
                normalized = ["" if value is None else str(value) for value in row]
                if len(normalized) < self.metadata.column_count:
                    normalized.extend([""] * (self.metadata.column_count - len(normalized)))
                rows.append(normalized[: self.metadata.column_count])
        return rows
