from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QThread, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableView,
    QTabWidget,
    QTextEdit,
    QToolBox,
    QVBoxLayout,
    QWidget,
)

from csv_studio.models.csv_table_model import CsvTableModel
from csv_studio.services.csv_service import CsvMetadata
from csv_studio.widgets.title_bar import TitleBar
from csv_studio.workers.csv_loader import CsvLoadWorker


RESIZE_LEFT = 1
RESIZE_RIGHT = 2
RESIZE_TOP = 4
RESIZE_BOTTOM = 8


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("CSV Studio")
        self.resize(1620, 960)
        self.setMinimumSize(1180, 720)
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.current_column_index: int | None = None
        self.load_thread: QThread | None = None
        self.load_worker: CsvLoadWorker | None = None
        self._load_stage = "idle"
        self._has_preview_loaded = False
        self._syncing_cell_editor = False
        self._resize_margin = 6
        self._resize_edges = 0
        self._resize_origin = QPoint()
        self._resize_start_geometry = QRect()

        self.model = CsvTableModel(self)
        self.model.metadata_changed.connect(self._on_metadata_loaded)
        self.model.cache_changed.connect(self._on_cache_changed)
        self.model.dirty_state_changed.connect(self._on_dirty_state_changed)
        self.model.dataChanged.connect(self._on_model_data_changed)

        self._build_ui()
        self._apply_button_variant(self.open_button, "accent")
        self._bind_events()
        self._refresh_workspace_files()
        self._set_empty_state()

    def _build_ui(self) -> None:
        outer = QWidget(objectName="OuterRoot")
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(6, 6, 6, 6)
        outer_layout.setSpacing(0)

        self.app_shell = QFrame()
        self.app_shell.setObjectName("AppShell")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(10)
        shadow.setOffset(0, 2)
        shadow.setColor(Qt.gray)
        self.app_shell.setGraphicsEffect(shadow)

        shell_layout = QVBoxLayout(self.app_shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        self.title_bar = TitleBar(self)
        self.toolbar_bar = self._create_toolbar_bar()

        self.left_panel = self._create_left_panel()
        self.center_panel = self._create_center_panel()
        self.right_panel = self._create_right_panel()
        self.left_panel.setMinimumWidth(220)
        self.right_panel.setMinimumWidth(340)

        self.content_splitter = QSplitter(Qt.Horizontal)
        self.content_splitter.setChildrenCollapsible(False)
        self.content_splitter.setHandleWidth(8)
        self.content_splitter.addWidget(self.left_panel)
        self.content_splitter.addWidget(self.center_panel)
        self.content_splitter.addWidget(self.right_panel)
        self.content_splitter.setStretchFactor(0, 0)
        self.content_splitter.setStretchFactor(1, 1)
        self.content_splitter.setStretchFactor(2, 0)
        self.content_splitter.setSizes([250, 1030, 380])

        self.status_strip = self._create_status_strip()

        shell_layout.addWidget(self.title_bar)
        shell_layout.addWidget(self.toolbar_bar)
        shell_layout.addWidget(self.content_splitter, 1)
        shell_layout.addWidget(self.status_strip)

        outer_layout.addWidget(self.app_shell)
        self.setCentralWidget(outer)

    def _create_toolbar_bar(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("ToolBar")
        frame.setFixedHeight(68)
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.new_button = QPushButton("新建")
        self.new_button.setEnabled(False)
        self.open_button = QPushButton("打开")
        self.close_file_button = QPushButton("关闭表")
        self.close_file_button.setEnabled(False)
        self.save_button = QPushButton("保存")
        self.save_button.setEnabled(False)
        self.save_as_button = QPushButton("另存为")
        self.save_as_button.setEnabled(False)
        self.import_button = QPushButton("导入")
        self.import_button.setEnabled(False)
        self.export_table_button = QPushButton("导出表格")
        self.export_table_button.setEnabled(False)
        self.sort_button = QPushButton("排序")
        self.sort_button.setEnabled(False)
        self.filter_button = QPushButton("筛选")
        self.filter_button.setEnabled(False)
        self.dedupe_button = QPushButton("去重")
        self.dedupe_button.setEnabled(False)
        self.clean_button = QPushButton("清洗")
        self.clean_button.setEnabled(False)

        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("输入或粘贴 CSV 路径后回车打开")
        self.path_edit.setMinimumWidth(320)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("全局搜索（界面占位）")
        self.search_edit.setMinimumWidth(220)

        for widget in [
            self.new_button,
            self.open_button,
            self.close_file_button,
            self.save_button,
            self.save_as_button,
            self.import_button,
            self.export_table_button,
            self.sort_button,
            self.filter_button,
            self.dedupe_button,
            self.clean_button,
            self.path_edit,
            self.search_edit,
        ]:
            layout.addWidget(widget)
        return frame

    def _create_left_panel(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("Panel")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        title = QLabel("资源")
        title.setStyleSheet("font-size:13px;font-weight:700;")
        self.toolbox = QToolBox()
        self.files_list = QListWidget()
        self.columns_list = QListWidget()
        self.filters_list = QListWidget()
        self.quality_text = QTextEdit()
        self.quality_text.setReadOnly(True)
        self.quality_text.setMinimumHeight(220)

        self.toolbox.addItem(self.files_list, "文件")
        self.toolbox.addItem(self.columns_list, "列结构")
        self.toolbox.addItem(self.filters_list, "已保存筛选")
        self.toolbox.addItem(self.quality_text, "数据质量")

        layout.addWidget(title)
        layout.addWidget(self.toolbox, 1)
        return frame

    def _create_center_panel(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        info_bar = QFrame()
        info_bar.setObjectName("Panel")
        info_layout = QHBoxLayout(info_bar)
        info_layout.setContentsMargins(12, 9, 12, 9)
        info_layout.setSpacing(8)
        self.info_file = self._make_tag("表格：未打开")
        self.info_rows = self._make_tag("行数：0")
        self.info_cols = self._make_tag("列数：0")
        self.info_encoding = self._make_tag("编码：-")
        self.info_delimiter = self._make_tag("分隔符：-")
        self.info_state = self._make_tag("状态：待命")
        for widget in [
            self.info_file,
            self.info_rows,
            self.info_cols,
            self.info_encoding,
            self.info_delimiter,
            self.info_state,
        ]:
            info_layout.addWidget(widget)
        info_layout.addStretch(1)

        self.loading_frame = QFrame()
        self.loading_frame.setObjectName("Panel")
        loading_layout = QHBoxLayout(self.loading_frame)
        loading_layout.setContentsMargins(12, 8, 12, 8)
        loading_layout.setSpacing(10)
        self.loading_title_label = QLabel("加载进度")
        self.loading_title_label.setStyleSheet("font-weight:700;")
        self.loading_message_label = QLabel("等待开始")
        self.loading_message_label.setProperty("role", "muted")
        self.loading_progress = QProgressBar()
        self.loading_progress.setRange(0, 100)
        self.loading_progress.setValue(0)
        self.loading_progress.setTextVisible(True)
        self.loading_progress.setFixedWidth(360)
        self.loading_progress.setFormat("%p%")
        loading_layout.addWidget(self.loading_title_label)
        loading_layout.addWidget(self.loading_message_label, 1)
        loading_layout.addWidget(self.loading_progress)
        self.loading_frame.setVisible(False)

        table_shell = QFrame()
        table_shell.setObjectName("Panel")
        table_layout = QVBoxLayout(table_shell)
        table_layout.setContentsMargins(10, 10, 10, 10)
        table_layout.setSpacing(8)
        self.table_view = QTableView()
        self.table_view.setModel(self.model)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSortingEnabled(False)
        self.table_view.setSelectionBehavior(QTableView.SelectItems)
        self.table_view.setSelectionMode(QTableView.ExtendedSelection)
        self.table_view.setShowGrid(True)
        self.table_view.setWordWrap(False)
        self.table_view.setHorizontalScrollMode(QTableView.ScrollPerPixel)
        self.table_view.setVerticalScrollMode(QTableView.ScrollPerPixel)
        self.table_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_view.verticalHeader().setDefaultSectionSize(29)
        self.table_view.horizontalHeader().setDefaultSectionSize(160)
        self.table_view.horizontalHeader().setStretchLastSection(False)
        table_layout.addWidget(self.table_view, 1)

        layout.addWidget(info_bar)
        layout.addWidget(self.loading_frame)
        layout.addWidget(table_shell, 1)
        return container

    def _create_right_panel(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("Panel")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_cell_tab(), "单元格")
        self.tabs.addTab(self._create_column_tab(), "列")
        self.tabs.addTab(self._create_file_tab(), "文件")
        layout.addWidget(self.tabs, 1)
        return frame

    def _create_cell_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(10)
        self.cell_position_label = QLabel("-")
        self.cell_column_label = QLabel("-")
        form.addRow("当前位置", self.cell_position_label)
        form.addRow("当前列", self.cell_column_label)

        value_title = QLabel("单元格全文")
        value_title.setStyleSheet("font-weight:700;")
        self.cell_value_editor = QTextEdit()
        self.cell_value_editor.setAcceptRichText(False)
        self.cell_value_editor.setPlaceholderText("选择单元格后，这里会显示完整内容，可直接修改。")
        self.cell_value_editor.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.cell_value_editor.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.cell_value_editor.setMinimumHeight(260)
        self.cell_value_editor.setReadOnly(True)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(8)
        self.apply_cell_button = QPushButton("写入当前单元格")
        self.apply_cell_button.setEnabled(False)
        self.revert_cell_button = QPushButton("撤销当前修改")
        self.revert_cell_button.setEnabled(False)
        button_row.addWidget(self.apply_cell_button)
        button_row.addWidget(self.revert_cell_button)
        button_row.addStretch(1)

        layout.addLayout(form)
        layout.addWidget(value_title)
        layout.addWidget(self.cell_value_editor, 1)
        layout.addLayout(button_row)
        return tab

    def _create_column_tab(self) -> QWidget:
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        self.column_name_label = QLabel("-")
        self.column_type_label = QLabel("-")
        self.column_null_label = QLabel("-")
        self.column_unique_label = QLabel("-")
        layout.addRow("列名", self.column_name_label)
        layout.addRow("类型", self.column_type_label)
        layout.addRow("空值率", self.column_null_label)
        layout.addRow("样本唯一值", self.column_unique_label)
        return tab

    def _create_file_tab(self) -> QWidget:
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        self.file_path_label = QLabel("-")
        self.file_path_label.setWordWrap(True)
        self.file_stage_label = QLabel("待命")
        self.file_rows_label = QLabel("0")
        self.file_cache_label = QLabel("0")
        self.file_encoding_label = QLabel("-")
        layout.addRow("文件路径", self.file_path_label)
        layout.addRow("加载阶段", self.file_stage_label)
        layout.addRow("当前行数", self.file_rows_label)
        layout.addRow("缓存块", self.file_cache_label)
        layout.addRow("编码", self.file_encoding_label)
        return tab

    def _create_status_strip(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("Panel")
        frame.setFixedHeight(34)
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)
        self.feedback_label = QLabel("准备就绪，可通过“打开”按钮或路径输入框加载大型 CSV。")
        self.feedback_label.setProperty("role", "muted")
        layout.addWidget(self.feedback_label, 1)

        self.status_labels: dict[str, QLabel] = {}
        for key, text in [
            ("encoding", "UTF-8"),
            ("delimiter", "逗号分隔"),
            ("linebreak", "LF 换行"),
            ("editable", "未打开"),
            ("position", "第 0 行 / 0"),
            ("column", "当前列：-"),
            ("selected", "已选 0 个单元格"),
            ("virtualized", "虚拟化"),
            ("cache", "缓存块：0"),
        ]:
            label = QLabel(text)
            self.status_labels[key] = label
            layout.addWidget(label)
        return frame

    def _bind_events(self) -> None:
        self.open_button.clicked.connect(self._open_file_dialog)
        self.close_file_button.clicked.connect(self._close_current_csv)
        self.save_button.clicked.connect(self._save_current_file)
        self.save_as_button.clicked.connect(self._save_as_current_file)
        self.path_edit.returnPressed.connect(self._open_path_from_input)
        self.files_list.itemDoubleClicked.connect(self._open_selected_file)
        self.export_table_button.clicked.connect(self._export_table_snapshot)
        self.apply_cell_button.clicked.connect(self._apply_cell_editor)
        self.revert_cell_button.clicked.connect(self._revert_current_cell_edit)
        self.cell_value_editor.textChanged.connect(self._on_cell_editor_text_changed)
        self.table_view.selectionModel().currentChanged.connect(self._on_current_cell_changed)
        self.table_view.selectionModel().selectionChanged.connect(self._on_selection_changed)

    def _make_tag(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setProperty("role", "tag")
        return label

    def _apply_button_variant(self, button: QWidget, variant: str) -> None:
        button.setProperty("variant", variant)
        button.style().unpolish(button)
        button.style().polish(button)

    def _refresh_workspace_files(self) -> None:
        self.files_list.clear()
        self.filters_list.clear()
        for file_path in sorted(Path.cwd().glob("*.csv")):
            item = QListWidgetItem(file_path.name)
            item.setData(Qt.UserRole, str(file_path))
            self.files_list.addItem(item)
        for example in ["金额 > 1000", "日期在本月", "缺失值检查", "高风险金额列"]:
            self.filters_list.addItem(example)

    def _set_empty_state(self) -> None:
        self.quality_text.setPlainText("尚未打开 CSV 文件。\n\n打开文件后，这里会显示缺失值、重复行和类型冲突的样本统计。")
        self.file_stage_label.setText("待命")
        self.file_rows_label.setText("0")
        self.file_cache_label.setText("0")
        self.file_encoding_label.setText("-")
        self.file_path_label.setText("-")
        self.path_edit.clear()
        self.cell_position_label.setText("-")
        self.cell_column_label.setText("-")
        self._syncing_cell_editor = True
        self.cell_value_editor.clear()
        self._syncing_cell_editor = False
        self.column_name_label.setText("-")
        self.column_type_label.setText("-")
        self.column_null_label.setText("-")
        self.column_unique_label.setText("-")
        self.columns_list.clear()
        self.table_view.clearSelection()
        self.title_bar.current_file_label.setText("未打开文件")
        self.title_bar.save_state_label.setText("未保存")
        self.info_file.setText("表格：未打开")
        self.info_rows.setText("行数：0")
        self.info_cols.setText("列数：0")
        self.info_encoding.setText("编码：-")
        self.info_delimiter.setText("分隔符：-")
        self.info_state.setText("状态：待命")
        self.status_labels["encoding"].setText("UTF-8")
        self.status_labels["delimiter"].setText("逗号分隔")
        self.status_labels["editable"].setText("未打开")
        self.status_labels["position"].setText("第 0 行 / 0")
        self.status_labels["column"].setText("当前列：-")
        self.status_labels["selected"].setText("已选 0 个单元格")
        self.status_labels["cache"].setText("缓存块：0")
        self.setWindowTitle("CSV Studio")
        self.current_column_index = None
        self._hide_loading()
        self._refresh_action_states()
        self._update_cell_editor_actions()

    def _editing_available(self) -> bool:
        if not self.model.metadata:
            return False
        if self.load_thread and self.load_thread.isRunning():
            return False
        return self._load_stage in {"final", "preview-failed"}

    def _refresh_action_states(self) -> None:
        has_file = self.model.metadata is not None
        is_loading = self.load_thread is not None and self.load_thread.isRunning()
        dirty = self.model.has_unsaved_changes()

        self.open_button.setEnabled(not is_loading)
        self.path_edit.setEnabled(not is_loading)
        self.files_list.setEnabled(not is_loading)
        self.close_file_button.setEnabled(has_file and not is_loading)
        self.export_table_button.setEnabled(has_file and not is_loading)
        self.save_as_button.setEnabled(has_file and not is_loading)
        self.save_button.setEnabled(has_file and dirty and not is_loading)
        self._set_editing_enabled(self._editing_available())

    def _set_editing_enabled(self, enabled: bool) -> None:
        if enabled:
            triggers = (
                QAbstractItemView.DoubleClicked
                | QAbstractItemView.SelectedClicked
                | QAbstractItemView.EditKeyPressed
            )
            self.table_view.setEditTriggers(triggers)
        else:
            self.table_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.cell_value_editor.setReadOnly(not enabled)
        self._update_cell_editor_actions()

    def _show_loading(self, percent: int, message: str) -> None:
        self.loading_frame.setVisible(True)
        self.loading_message_label.setText(message)
        self.loading_progress.setValue(max(0, min(percent, 100)))

    def _hide_loading(self) -> None:
        self.loading_frame.setVisible(False)
        self.loading_message_label.setText("等待开始")
        self.loading_progress.setValue(0)

    def _apply_initial_column_widths(self, metadata: CsvMetadata) -> None:
        self.table_view.horizontalHeader().setDefaultSectionSize(160)
        metrics = self.table_view.fontMetrics()
        for column in range(min(metadata.column_count, 24)):
            header = metadata.headers[column]
            candidates = [header]
            for row in metadata.preview_rows[:6]:
                candidates.append(str(row.get(header, "") or "NULL")[:24])
            width = 110
            for text in candidates:
                width = max(width, metrics.horizontalAdvance(text) + 42)
            self.table_view.setColumnWidth(column, min(width, 260))

    def _current_index(self):
        return self.table_view.currentIndex()

    def _open_file_dialog(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "打开 CSV 文件",
            str(Path.cwd()),
            "CSV 文件 (*.csv *.txt);;所有文件 (*.*)",
        )
        if file_path:
            self._load_file(file_path)

    def _open_path_from_input(self) -> None:
        file_path = self.path_edit.text().strip().strip('"')
        if file_path:
            self._load_file(file_path)

    def _open_selected_file(self, item: QListWidgetItem) -> None:
        file_path = item.data(Qt.UserRole)
        if file_path:
            self._load_file(file_path)

    def _load_file(self, file_path: str, skip_unsaved_check: bool = False) -> None:
        if self.load_thread and self.load_thread.isRunning():
            QMessageBox.information(self, "正在加载", "当前已有一个大型 CSV 正在加载，请稍候完成后再打开其他文件。")
            return

        if not skip_unsaved_check and not self._confirm_before_replacing_current("打开其他 CSV"):
            return

        path = Path(file_path)
        if not path.exists():
            QMessageBox.warning(self, "路径不存在", f"未找到文件：\n{path}")
            return

        self._load_stage = "loading"
        self._has_preview_loaded = False
        self.current_column_index = None
        self.path_edit.setText(str(path))
        self.file_path_label.setText(str(path))
        self.title_bar.current_file_label.setText(path.name)
        self.title_bar.save_state_label.setText("加载中")
        self.info_state.setText("状态：加载中")
        self.status_labels["editable"].setText("后台加载中")
        self._refresh_action_states()
        self._show_loading(2, "正在准备文件头与样本预览…")
        self._set_feedback(f"正在后台读取 {path.name}，先显示预览，再建立完整索引。")

        self.load_thread = QThread(self)
        self.load_worker = CsvLoadWorker(str(path))
        self.load_worker.moveToThread(self.load_thread)
        self.load_thread.started.connect(self.load_worker.run)
        self.load_worker.status.connect(self._on_loader_status)
        self.load_worker.progress.connect(self._on_loader_progress)
        self.load_worker.preview_ready.connect(self._on_preview_ready)
        self.load_worker.completed.connect(self._on_loader_completed)
        self.load_worker.failed.connect(self._on_loader_failed)
        self.load_worker.completed.connect(self.load_thread.quit)
        self.load_worker.failed.connect(self.load_thread.quit)
        self.load_thread.finished.connect(self._cleanup_loader)
        self.load_thread.finished.connect(self.load_worker.deleteLater)
        self.load_thread.finished.connect(self.load_thread.deleteLater)
        self.load_thread.start()

    def _on_loader_status(self, text: str) -> None:
        self._set_feedback(text)

    def _on_loader_progress(self, percent: int, text: str) -> None:
        self._show_loading(percent, text)
        self._set_feedback(text)

    def _on_preview_ready(self, metadata: CsvMetadata) -> None:
        self._has_preview_loaded = True
        self._load_stage = "preview"
        self.model.set_metadata(metadata)
        self._apply_initial_column_widths(metadata)
        self._show_loading(12, "预览已显示，正在继续统计完整行数…")
        self.info_state.setText("状态：后台索引中")
        self.status_labels["editable"].setText("后台索引中")
        self._refresh_action_states()
        if self.model.rowCount() > 0 and self.model.columnCount() > 0:
            self.table_view.setCurrentIndex(self.model.index(0, 0))

    def _on_loader_completed(self, metadata: CsvMetadata) -> None:
        self._load_stage = "final"
        self.model.set_metadata(metadata)
        self._apply_initial_column_widths(metadata)
        self._show_loading(100, f"索引已建立完成，共 {metadata.index.row_count:,} 行")
        self._hide_loading()
        self._set_feedback(f"已完成 {metadata.file_path.name} 的完整索引，共 {metadata.index.row_count:,} 行。")
        self.info_state.setText("状态：可编辑")
        self.status_labels["editable"].setText("可编辑")
        self._refresh_action_states()
        if self.model.rowCount() > 0 and self.model.columnCount() > 0:
            target_column = min(self.current_column_index or 0, self.model.columnCount() - 1)
            self.table_view.setCurrentIndex(self.model.index(0, target_column))

    def _on_loader_failed(self, message: str) -> None:
        self._hide_loading()
        if self._has_preview_loaded:
            self._load_stage = "preview-failed"
            self.title_bar.save_state_label.setText("仅预览")
            self.info_state.setText("状态：仅预览")
            self.status_labels["editable"].setText("可编辑")
            self.file_stage_label.setText("仅预览")
            self._set_feedback("完整索引构建失败，当前保留预览结果。")
            self._refresh_action_states()
            QMessageBox.warning(self, "后台索引失败", f"完整索引未建立成功，当前保留预览数据。\n\n{message}")
        else:
            self._load_stage = "failed"
            self.title_bar.save_state_label.setText("打开失败")
            self._set_feedback("CSV 加载失败。")
            self._refresh_action_states()
            QMessageBox.critical(self, "打开失败", f"CSV 读取失败：\n{message}")

    def _cleanup_loader(self) -> None:
        self.load_worker = None
        self.load_thread = None
        self._refresh_action_states()

    def _on_metadata_loaded(self, metadata: CsvMetadata) -> None:
        preview_stage = self._load_stage == "preview"
        self.title_bar.current_file_label.setText(metadata.file_path.name)
        self.setWindowTitle(f"CSV Studio - {metadata.file_path.name}")
        self.info_file.setText(f"表格：{metadata.file_path.name}")
        self.info_cols.setText(f"列数：{metadata.column_count}")
        self.info_encoding.setText(f"编码：{metadata.encoding}")
        self.info_delimiter.setText(f"分隔符：{self._delimiter_text(metadata.delimiter)}")
        self.file_encoding_label.setText(metadata.encoding)
        self.file_path_label.setText(str(metadata.file_path))

        if preview_stage:
            self.title_bar.save_state_label.setText("预览中")
            self.info_rows.setText(f"行数：预览前 {metadata.index.row_count:,} 行")
            self.info_state.setText("状态：后台索引中")
            self.file_stage_label.setText("预览中")
            self.status_labels["position"].setText(f"预览 0 / {metadata.index.row_count:,}")
            self.status_labels["editable"].setText("后台索引中")
        else:
            self.title_bar.save_state_label.setText("已保存")
            self.info_rows.setText(f"行数：{metadata.index.row_count:,}")
            self.info_state.setText("状态：可编辑")
            self.file_stage_label.setText("完成")
            self.status_labels["position"].setText(f"第 0 行 / {metadata.index.row_count:,}")
            self.status_labels["editable"].setText("可编辑")

        self.file_rows_label.setText(f"{metadata.index.row_count:,}")
        self.columns_list.clear()
        for profile in metadata.column_profiles:
            self.columns_list.addItem(f"{profile.name}  |  {profile.dtype_hint}  |  空值 {profile.null_ratio:.1%}  |  唯一值 {profile.unique_count_sample}")

        self.status_labels["encoding"].setText(metadata.encoding.upper())
        self.status_labels["delimiter"].setText(self._delimiter_text(metadata.delimiter))
        self.status_labels["column"].setText("当前列：-")
        self.status_labels["cache"].setText(f"缓存块：{self.model.cached_chunk_count()}")
        self._update_quality_panel(metadata)

    def _update_quality_panel(self, metadata: CsvMetadata) -> None:
        preview_count = len(metadata.preview_rows)
        null_ratio = metadata.null_cells_sample / (preview_count * metadata.column_count) if preview_count and metadata.column_count else 0.0
        stage_text = "当前已显示预览，后台仍在建立完整索引。" if self._load_stage == "preview" else "当前已建立完整索引，可稳定滚动浏览大文件。"
        self.quality_text.setPlainText("\n".join([
            f"文件：{metadata.file_path.name}",
            f"样本缺失单元格：{metadata.null_cells_sample}",
            f"样本重复行：{metadata.duplicate_rows_sample}",
            f"样本空值率：{null_ratio:.1%}",
            f"推断编码：{metadata.encoding}",
            f"推断分隔符：{repr(metadata.delimiter)}",
            "",
            stage_text,
        ]))

    def _on_current_cell_changed(self, current, previous) -> None:
        if not current.isValid() or not self.model.metadata:
            self.cell_position_label.setText("-")
            self.cell_column_label.setText("-")
            self._syncing_cell_editor = True
            self.cell_value_editor.clear()
            self._syncing_cell_editor = False
            self._update_cell_editor_actions()
            return

        row = current.row()
        column = current.column()
        raw_value = self.model.raw_value(row, column)
        profile = self.model.column_profile(column)
        self.current_column_index = column
        self.cell_position_label.setText(f"第 {row + 1} 行，第 {column + 1} 列")
        self.cell_column_label.setText(profile.name if profile else "-")
        self._syncing_cell_editor = True
        self.cell_value_editor.setPlainText(raw_value)
        self._syncing_cell_editor = False
        if self._load_stage == "preview":
            self.status_labels["position"].setText(f"预览 {row + 1} / {self.model.rowCount():,}")
        else:
            self.status_labels["position"].setText(f"第 {row + 1} 行 / {self.model.rowCount():,}")
        self.status_labels["column"].setText(f"当前列：第 {column + 1} 列 / {profile.name if profile else '-'}")
        if profile:
            self.column_name_label.setText(profile.name)
            self.column_type_label.setText(profile.dtype_hint)
            self.column_null_label.setText(f"{profile.null_ratio:.1%}")
            self.column_unique_label.setText(str(profile.unique_count_sample))
        self._update_cell_editor_actions()

    def _on_selection_changed(self, selected, deselected) -> None:
        selection_model = self.table_view.selectionModel()
        count = len(selection_model.selectedIndexes()) if selection_model else 0
        self.status_labels["selected"].setText(f"已选 {count} 个单元格")

    def _on_cache_changed(self, count: int) -> None:
        self.status_labels["cache"].setText(f"缓存块：{count}")
        self.file_cache_label.setText(str(count))

    def _on_dirty_state_changed(self, is_dirty: bool, edited_count: int) -> None:
        if not self.model.metadata:
            self.title_bar.save_state_label.setText("未保存")
        elif is_dirty:
            self.title_bar.save_state_label.setText(f"已修改 {edited_count} 格")
            self.info_state.setText("状态：已修改")
            self.status_labels["editable"].setText("可编辑")
        elif self._load_stage in {"final", "preview-failed"}:
            self.title_bar.save_state_label.setText("已保存")
            self.info_state.setText("状态：可编辑")
            self.status_labels["editable"].setText("可编辑")
        self._refresh_action_states()
        self._update_cell_editor_actions()

    def _on_model_data_changed(self, top_left, bottom_right, roles) -> None:
        current = self._current_index()
        if not current.isValid():
            return
        if top_left.row() <= current.row() <= bottom_right.row() and top_left.column() <= current.column() <= bottom_right.column():
            self._syncing_cell_editor = True
            self.cell_value_editor.setPlainText(self.model.raw_value(current.row(), current.column()))
            self._syncing_cell_editor = False
            self._update_cell_editor_actions()

    def _on_cell_editor_text_changed(self) -> None:
        if self._syncing_cell_editor:
            return
        self._update_cell_editor_actions()

    def _update_cell_editor_actions(self) -> None:
        current = self._current_index()
        can_edit = self._editing_available() and current.isValid() and self.model.metadata is not None
        if not can_edit:
            self.apply_cell_button.setEnabled(False)
            self.revert_cell_button.setEnabled(False)
            return
        editor_text = self.cell_value_editor.toPlainText()
        current_text = self.model.raw_value(current.row(), current.column())
        is_cell_edited = self.model.base_value(current.row(), current.column()) != current_text
        self.apply_cell_button.setEnabled(editor_text != current_text)
        self.revert_cell_button.setEnabled(is_cell_edited)

    def _apply_cell_editor(self) -> None:
        current = self._current_index()
        if not current.isValid() or not self._editing_available():
            return
        self.model.setData(current, self.cell_value_editor.toPlainText(), Qt.EditRole)
        self._set_feedback(f"已修改第 {current.row() + 1} 行第 {current.column() + 1} 列，记得保存到 CSV。")
        self._update_cell_editor_actions()

    def _revert_current_cell_edit(self) -> None:
        current = self._current_index()
        if not current.isValid():
            return
        if self.model.revert_cell(current.row(), current.column()):
            self._syncing_cell_editor = True
            self.cell_value_editor.setPlainText(self.model.raw_value(current.row(), current.column()))
            self._syncing_cell_editor = False
            self._set_feedback(f"已撤销第 {current.row() + 1} 行第 {current.column() + 1} 列的修改。")
        self._update_cell_editor_actions()

    def _confirm_before_replacing_current(self, action_text: str) -> bool:
        if not self.model.metadata or not self.model.has_unsaved_changes():
            return True

        reply = QMessageBox.question(
            self,
            "存在未保存修改",
            f"当前 CSV 有未保存修改，是否在{action_text}前先保存？",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save,
        )
        if reply == QMessageBox.Cancel:
            return False
        if reply == QMessageBox.Save:
            return self._save_current_file(reload_after_save=False)
        return True

    def _close_current_csv(self) -> None:
        if not self.model.metadata:
            return
        if self.load_thread and self.load_thread.isRunning():
            QMessageBox.information(self, "正在加载", "当前文件仍在后台建立索引，请等待完成后再关闭表格。")
            return
        if not self._confirm_before_replacing_current("关闭当前 CSV"):
            return
        self.model.clear()
        self._load_stage = "idle"
        self._has_preview_loaded = False
        self._set_empty_state()
        self._set_feedback("当前 CSV 已关闭。")

    def _save_current_file(self, reload_after_save: bool = True) -> bool:
        if not self.model.metadata:
            QMessageBox.information(self, "暂无表格", "请先打开 CSV 文件。")
            return False
        if self.load_thread and self.load_thread.isRunning():
            QMessageBox.information(self, "正在加载", "请等待后台索引完成后再保存。")
            return False
        if not self.model.has_unsaved_changes():
            self._set_feedback("当前没有未保存修改。")
            return True
        try:
            saved_path, row_count = self.model.write_edits()
        except Exception as exc:
            QMessageBox.critical(self, "保存失败", f"写入 CSV 失败：\n{exc}")
            return False

        self._set_feedback(f"已保存 {row_count:,} 行到 {saved_path}。")
        if reload_after_save:
            self._load_file(str(saved_path), skip_unsaved_check=True)
        return True

    def _save_as_current_file(self) -> bool:
        if not self.model.metadata:
            QMessageBox.information(self, "暂无表格", "请先打开 CSV 文件。")
            return False
        if self.load_thread and self.load_thread.isRunning():
            QMessageBox.information(self, "正在加载", "请等待后台索引完成后再另存为。")
            return False
        default_name = f"{self.model.metadata.file_path.stem}_副本.csv"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "另存为 CSV",
            str(self.model.metadata.file_path.with_name(default_name)),
            "CSV 文件 (*.csv)",
        )
        if not file_path:
            return False

        try:
            saved_path, row_count = self.model.write_edits(file_path)
        except Exception as exc:
            QMessageBox.critical(self, "另存为失败", f"写入 CSV 失败：\n{exc}")
            return False

        self._set_feedback(f"已另存为 {saved_path}，共 {row_count:,} 行。")
        self._load_file(str(saved_path), skip_unsaved_check=True)
        return True

    def _export_table_snapshot(self) -> None:
        if not self.model.metadata:
            QMessageBox.information(self, "暂无表格", "请先打开 CSV 文件。")
            return
        default_name = f"{self.model.metadata.file_path.stem}_preview.csv"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出表格快照",
            str(Path.cwd() / default_name),
            "CSV 文件 (*.csv)",
        )
        if not file_path:
            return
        row_count = self.model.export_preview_csv(file_path, limit=5000)
        self._set_feedback(f"表格快照已导出，共 {row_count} 行：{file_path}")

    def _set_feedback(self, text: str) -> None:
        self.feedback_label.setText(text)

    def closeEvent(self, event) -> None:
        if self.load_thread and self.load_thread.isRunning():
            QMessageBox.information(self, "正在加载", "当前文件仍在后台建立索引，请等待完成后再退出程序。")
            event.ignore()
            return
        if not self._confirm_before_replacing_current("退出程序"):
            event.ignore()
            return
        super().closeEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and not self.isMaximized():
            edges = self._resize_edges_for_pos(event.position().toPoint())
            if edges:
                self._resize_edges = edges
                self._resize_origin = event.globalPosition().toPoint()
                self._resize_start_geometry = self.geometry()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self.isMaximized():
            self.unsetCursor()
            super().mouseMoveEvent(event)
            return

        if self._resize_edges:
            self._perform_resize(event.globalPosition().toPoint())
            event.accept()
            return

        self.setCursor(self._cursor_for_edges(self._resize_edges_for_pos(event.position().toPoint())))
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._resize_edges = 0
        self.unsetCursor()
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event) -> None:
        if not self._resize_edges:
            self.unsetCursor()
        super().leaveEvent(event)

    def _resize_edges_for_pos(self, pos: QPoint) -> int:
        rect = self.rect()
        edges = 0
        if pos.x() <= self._resize_margin:
            edges |= RESIZE_LEFT
        elif pos.x() >= rect.width() - self._resize_margin:
            edges |= RESIZE_RIGHT
        if pos.y() <= self._resize_margin:
            edges |= RESIZE_TOP
        elif pos.y() >= rect.height() - self._resize_margin:
            edges |= RESIZE_BOTTOM
        return edges

    def _cursor_for_edges(self, edges: int):
        if edges in {RESIZE_LEFT, RESIZE_RIGHT}:
            return Qt.SizeHorCursor
        if edges in {RESIZE_TOP, RESIZE_BOTTOM}:
            return Qt.SizeVerCursor
        if edges in {RESIZE_LEFT | RESIZE_TOP, RESIZE_RIGHT | RESIZE_BOTTOM}:
            return Qt.SizeFDiagCursor
        if edges in {RESIZE_RIGHT | RESIZE_TOP, RESIZE_LEFT | RESIZE_BOTTOM}:
            return Qt.SizeBDiagCursor
        return Qt.ArrowCursor

    def _perform_resize(self, global_pos: QPoint) -> None:
        delta = global_pos - self._resize_origin
        geometry = QRect(self._resize_start_geometry)
        min_width = self.minimumWidth()
        min_height = self.minimumHeight()

        if self._resize_edges & RESIZE_LEFT:
            new_left = min(geometry.right() - min_width + 1, geometry.left() + delta.x())
            geometry.setLeft(new_left)
        if self._resize_edges & RESIZE_RIGHT:
            new_right = max(geometry.left() + min_width - 1, geometry.right() + delta.x())
            geometry.setRight(new_right)
        if self._resize_edges & RESIZE_TOP:
            new_top = min(geometry.bottom() - min_height + 1, geometry.top() + delta.y())
            geometry.setTop(new_top)
        if self._resize_edges & RESIZE_BOTTOM:
            new_bottom = max(geometry.top() + min_height - 1, geometry.bottom() + delta.y())
            geometry.setBottom(new_bottom)

        self.setGeometry(geometry)

    @staticmethod
    def _delimiter_text(delimiter: str) -> str:
        return {
            ",": "逗号分隔",
            "\t": "制表符分隔",
            ";": "分号分隔",
            "|": "管道符分隔",
        }.get(delimiter, repr(delimiter))

