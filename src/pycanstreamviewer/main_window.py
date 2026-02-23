"""MainWindow: top-level window with toolbars, figure blocks, and live CAN streaming."""

import logging
import os

import yaml
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QCloseEvent, QCursor
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class _ScanOnOpenComboBox(QComboBox):
    """QComboBox that emits ``aboutToPopup`` when the dropdown is opened.

    Used for lazy device scanning -- the scan only runs when the user
    clicks the dropdown, not at application startup.
    """

    aboutToPopup = pyqtSignal()

    def showPopup(self):
        self.aboutToPopup.emit()
        super().showPopup()

from .can_manager import CanManager
from .utils import get_app_root
from .constants import (
    CAN_BITRATES,
    DBC_FILTER,
    DEFAULT_CAN_BITRATE_KEY,
    DEFAULT_DBC_DIR,
    DEFAULT_PLOT_COUNT,
    DEFAULT_REFRESH_RATE_KEY,
    DEFAULT_TIME_WINDOW_KEY,
    DEVICE_SCAN_LABEL_ERROR,
    DEVICE_SCAN_LABEL_INITIAL,
    DEVICE_SCAN_LABEL_NONE,
    MAX_PLOT_COUNT,
    RECORDING_FORMATS,
    REFRESH_RATES_HZ,
    TIME_WINDOWS,
    TOOLBAR_SPACING,
    WINDOW_DEFAULT_HEIGHT,
    WINDOW_DEFAULT_WIDTH,
    WINDOW_MIN_HEIGHT,
    WINDOW_MIN_WIDTH,
    Y_RANGE_PADDING,
    LINK_X_AXES,
)
import pyqtgraph as pg

from .device_scanner import format_device_label, parse_device_label, scan_can_devices
from .figure_block import FigureBlock
from .live_data_store import LiveDataStore

# Mouse control key text (shown at bottom of window)
MOUSE_KEY_TEXT = (
    "Mouse: Left-drag = Pan  |  Middle-click = Fit all  |"
    "  Right-drag = Rect zoom  |  Scroll = Zoom"
)


class MainWindow(QMainWindow):
    """Top-level application window for live CAN streaming."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("pyCANstreamViewer")
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.resize(WINDOW_DEFAULT_WIDTH, WINDOW_DEFAULT_HEIGHT)

        self._dbc_path: str | None = None
        self._figure_blocks: list[FigureBlock] = []

        # Resolve default directories relative to the app root
        app_root = get_app_root()
        self._default_dbc_dir = os.path.join(app_root, DEFAULT_DBC_DIR)
        self._preset_path = os.path.join(app_root, "config", "preset_views.yaml")
        self._presets: dict[str, list[list[str]]] = {}

        # Core streaming objects
        self._data_store = LiveDataStore()
        self._can_manager = CanManager(self._data_store)
        self._refresh_timer = QTimer()
        self._auto_scroll = True

        # === Build UI ===
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # --- Row 1: CAN connection controls ---
        row1 = QHBoxLayout()

        row1.addWidget(QLabel("Device:"))
        self._cmb_device = _ScanOnOpenComboBox()
        self._cmb_device.setMinimumWidth(200)
        self._cmb_device.addItem(DEVICE_SCAN_LABEL_INITIAL)
        row1.addWidget(self._cmb_device)
        row1.addSpacing(TOOLBAR_SPACING)

        row1.addWidget(QLabel("Baud:"))
        self._cmb_bitrate = QComboBox()
        for key in CAN_BITRATES:
            self._cmb_bitrate.addItem(key)
        self._cmb_bitrate.setCurrentText(DEFAULT_CAN_BITRATE_KEY)
        row1.addWidget(self._cmb_bitrate)
        row1.addSpacing(TOOLBAR_SPACING)

        self._btn_select_dbc = QPushButton("Select DBC...")
        self._lbl_dbc_path = QLabel("No DBC selected")
        row1.addWidget(self._btn_select_dbc)
        row1.addWidget(self._lbl_dbc_path, 1)
        row1.addSpacing(TOOLBAR_SPACING)

        self._chk_record = QCheckBox("Record")
        row1.addWidget(self._chk_record)

        self._cmb_record_format = QComboBox()
        for key in RECORDING_FORMATS:
            self._cmb_record_format.addItem(key)
        row1.addWidget(self._cmb_record_format)
        row1.addSpacing(TOOLBAR_SPACING)

        self._btn_start = QPushButton("Start")
        self._btn_stop = QPushButton("Stop")
        self._btn_stop.setEnabled(False)
        row1.addWidget(self._btn_start)
        row1.addWidget(self._btn_stop)

        main_layout.addLayout(row1)

        # --- Row 2: Plot controls ---
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("N Plots:"))
        self._cmb_n_plots = QComboBox()
        for i in range(1, MAX_PLOT_COUNT + 1):
            self._cmb_n_plots.addItem(str(i))
        self._cmb_n_plots.setCurrentText(str(DEFAULT_PLOT_COUNT))

        row2.addWidget(self._cmb_n_plots)
        row2.addSpacing(TOOLBAR_SPACING)

        row2.addWidget(QLabel("Preset Views:"))
        self._cmb_presets = QComboBox()
        self._cmb_presets.addItem("(none)")
        row2.addWidget(self._cmb_presets)
        self._btn_save_preset = QPushButton("Save Preset")
        row2.addWidget(self._btn_save_preset)
        row2.addSpacing(TOOLBAR_SPACING)

        row2.addWidget(QLabel("Refresh:"))
        self._cmb_refresh_rate = QComboBox()
        for key in REFRESH_RATES_HZ:
            self._cmb_refresh_rate.addItem(key)
        self._cmb_refresh_rate.setCurrentText(DEFAULT_REFRESH_RATE_KEY)
        row2.addWidget(self._cmb_refresh_rate)
        row2.addSpacing(TOOLBAR_SPACING)

        row2.addWidget(QLabel("Time Window:"))
        self._cmb_time_window = QComboBox()
        for key in TIME_WINDOWS:
            self._cmb_time_window.addItem(key)
        self._cmb_time_window.setCurrentText(DEFAULT_TIME_WINDOW_KEY)
        row2.addWidget(self._cmb_time_window)

        row2.addStretch()

        self._lbl_status = QLabel("Ready")
        row2.addWidget(self._lbl_status)
        main_layout.addLayout(row2)

        # --- Main area: figure blocks ---
        self._plots_container = QVBoxLayout()
        main_layout.addLayout(self._plots_container, 1)  # stretch factor 1

        # --- Mouse key ---
        lbl_mouse_key = QLabel(MOUSE_KEY_TEXT)
        lbl_mouse_key.setStyleSheet("color: gray; font-size: 11px;")
        main_layout.addWidget(lbl_mouse_key)

        # Build initial figure blocks
        self._rebuild_figure_blocks(DEFAULT_PLOT_COUNT)

        # === Connect signals ===
        self._cmb_device.aboutToPopup.connect(self._on_scan_devices)
        self._btn_select_dbc.clicked.connect(self._on_select_dbc)
        self._btn_start.clicked.connect(self._on_start)
        self._btn_stop.clicked.connect(self._on_stop)
        self._cmb_n_plots.currentTextChanged.connect(self._on_n_plots_changed)
        self._btn_save_preset.clicked.connect(self._on_save_preset)
        self._cmb_presets.currentTextChanged.connect(self._on_load_preset)
        self._cmb_refresh_rate.currentTextChanged.connect(
            self._on_refresh_rate_changed
        )
        self._cmb_time_window.currentTextChanged.connect(
            self._on_time_window_changed
        )

        self._can_manager.connected.connect(self._on_connected)
        self._can_manager.disconnected.connect(self._on_disconnected)
        self._can_manager.error.connect(self._on_error)
        self._can_manager.new_signals_discovered.connect(self._on_new_signals)
        self._refresh_timer.timeout.connect(self._on_refresh_tick)

        # Load existing presets from YAML
        self._load_presets_from_file()

    # --- Device scanning ---

    def _on_scan_devices(self) -> None:
        """Scan for available CAN devices and populate the dropdown.

        Called lazily when the user opens the device dropdown.  Re-scans
        every time so newly plugged-in devices are detected.

        The scan probes hardware and can take a few seconds.  A wait
        cursor and processEvents() call ensure the "Scanning..." status
        is painted before the blocking call.
        """
        self._lbl_status.setText("Scanning for CAN devices...")
        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        QApplication.processEvents()

        try:
            devices = scan_can_devices()
        finally:
            QApplication.restoreOverrideCursor()

        # Block signals while repopulating so currentTextChanged doesn't fire
        self._cmb_device.blockSignals(True)
        self._cmb_device.clear()

        if len(devices) <= 1:
            # Only the virtual/debug entry exists -- no real hardware found
            self._cmb_device.addItem(DEVICE_SCAN_LABEL_NONE)

        for dev in devices:
            self._cmb_device.addItem(format_device_label(dev))

        self._cmb_device.blockSignals(False)

        hw_count = len(devices) - 1  # subtract the virtual/debug entry
        self._lbl_status.setText(
            f"Scan complete: {hw_count} hardware device(s) found"
        )
        logger.info("Device scan populated %d entries", self._cmb_device.count())

    # --- DBC file selection ---

    def _on_select_dbc(self) -> None:
        start_dir = (
            self._default_dbc_dir if os.path.isdir(self._default_dbc_dir) else ""
        )
        path, _ = QFileDialog.getOpenFileName(
            self, "Select DBC File", start_dir, DBC_FILTER
        )
        if path:
            self._dbc_path = path
            self._lbl_dbc_path.setText(os.path.basename(path))
            logger.info("DBC file selected: %s", path)

    # --- Start / Stop streaming ---

    def _on_start(self) -> None:
        """Start live CAN acquisition."""
        device_text = self._cmb_device.currentText()
        if device_text in (
            DEVICE_SCAN_LABEL_NONE, DEVICE_SCAN_LABEL_ERROR,
            "", DEVICE_SCAN_LABEL_INITIAL,
        ):
            self._lbl_status.setText("Select a valid CAN device first")
            return

        if ": " not in device_text:
            self._lbl_status.setText("Invalid device selection")
            return

        if not self._dbc_path:
            self._lbl_status.setText("Select a DBC file first")
            return

        # Parse selected device
        interface, channel = parse_device_label(device_text)

        # Get bitrate
        bitrate_key = self._cmb_bitrate.currentText()
        bitrate = CAN_BITRATES.get(bitrate_key, CAN_BITRATES[DEFAULT_CAN_BITRATE_KEY])

        # Clear previous data
        self._data_store.clear()

        # Load DBC and start
        self._can_manager.load_dbc(self._dbc_path)
        self._can_manager.start(
            interface=interface,
            channel=channel,
            bitrate=bitrate,
            record=self._chk_record.isChecked(),
            record_format_key=self._cmb_record_format.currentText(),
        )

    def _on_stop(self) -> None:
        """Stop live CAN acquisition."""
        self._refresh_timer.stop()
        self._can_manager.stop()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Ensure CAN bus and timers are cleanly shut down on window close."""
        self._refresh_timer.stop()
        self._can_manager.stop()
        logger.info("Window closed, resources cleaned up")
        super().closeEvent(event)

    def _on_connected(self) -> None:
        """Slot: CAN bus connected successfully."""
        self._btn_start.setEnabled(False)
        self._btn_stop.setEnabled(True)
        self._lbl_status.setText("Connected - streaming...")
        self._auto_scroll = True

        # Configure axis policies (handles both X and Y auto-range)
        self._apply_x_axis_policy()

        # Start refresh timer at selected rate
        rate_key = self._cmb_refresh_rate.currentText()
        hz = REFRESH_RATES_HZ.get(rate_key, REFRESH_RATES_HZ[DEFAULT_REFRESH_RATE_KEY])
        interval_ms = int(1.0e3 / hz)
        self._refresh_timer.start(interval_ms)

    def _on_disconnected(self) -> None:
        """Slot: CAN bus disconnected."""
        self._btn_start.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self._lbl_status.setText("Stopped")

    def _on_error(self, error_msg: str) -> None:
        """Slot: CAN bus error."""
        self._lbl_status.setText(f"Error: {error_msg}")
        self._btn_start.setEnabled(True)
        self._btn_stop.setEnabled(False)
        logger.error("CAN error: %s", error_msg)

    # --- Live data ---

    def _on_new_signals(self, new_names: list[str]) -> None:
        """Slot: new signal names discovered from incoming CAN data."""
        all_names = self._data_store.get_signal_names()
        for block in self._figure_blocks:
            block.update_signal_list(all_names)

        self._lbl_status.setText(
            f"Streaming... {len(all_names)} signals discovered"
        )

    def _on_refresh_tick(self) -> None:
        """Slot: QTimer fires to update all plots with latest data.

        In fixed-window mode with auto-scroll, uses **position-offset
        scrolling**: curves are shifted with ``setPos()`` instead of
        calling ``setXRange()``.  This avoids the expensive ViewBox
        range-change cascade (Y auto-range recalculation, path-cache
        invalidation, etc.) that makes auto-scroll slower than static
        panning.  Y-range is computed manually from numpy arrays.
        """
        window_key = self._cmb_time_window.currentText()
        window_sec = TIME_WINDOWS.get(window_key)
        use_offset = self._auto_scroll and window_sec is not None

        t_min = None
        if use_offset:
            t_max = self._data_store.get_latest_timestamp()
            if t_max is not None:
                t_min = max(0.0, t_max - window_sec)

        for block in self._figure_blocks:
            if use_offset and t_min is not None:
                # Position-offset mode: shift curves FIRST so the
                # positions are correct when setData() triggers
                # clipToView path rebuild (avoids a redundant second
                # rebuild that would happen if shift_curves ran after).
                block.shift_curves(t_min)
                y_range = block.refresh_plots(
                    visible_t_range=(t_min, t_min + window_sec)
                )
                if y_range is not None:
                    vb = block.get_plot_item().getViewBox()
                    vb.setYRange(
                        y_range[0], y_range[1], padding=Y_RANGE_PADDING
                    )
            else:
                # "All" mode or auto-scroll off: pyqtgraph auto-range
                # handles axes; just push new data.
                block.refresh_plots()

    def _on_refresh_rate_changed(self, rate_key: str) -> None:
        """Slot: user changed the refresh rate dropdown."""
        hz = REFRESH_RATES_HZ.get(rate_key)
        if hz is None:
            return
        interval_ms = int(1.0e3 / hz)
        if self._refresh_timer.isActive():
            self._refresh_timer.setInterval(interval_ms)
        logger.info("Refresh rate changed to %d Hz", hz)

    def _on_time_window_changed(self, window_key: str) -> None:
        """Slot: user changed the time window dropdown."""
        self._auto_scroll = True
        self._apply_x_axis_policy()

        window_sec = TIME_WINDOWS.get(window_key)
        logger.info(
            "Time window changed to %s",
            f"{window_sec}s" if window_sec is not None else "All",
        )

    def _apply_x_axis_policy(self) -> None:
        """Configure axis auto-range and position-offset state.

        **"All" mode**: both X and Y auto-range are enabled; pyqtgraph
        handles everything.  Curve positions are reset to (0, 0).

        **Fixed-window mode** (position-offset scrolling): X and Y
        auto-range are disabled.  The ViewBox x-range is locked at
        ``(0, window_sec)``; curves slide via ``setPos()`` and Y-range
        is managed manually in ``_on_refresh_tick``.

        Must be called whenever auto-scroll is re-enabled, the time
        window selection changes, or new figure blocks are created
        during streaming.

        Note: with ``LINK_X_AXES`` the ``setRange``/``enableAutoRange``
        calls on blocks 1+ are redundant (block 0's change propagates
        via x-link), but harmless and keeps the logic robust if x-link
        is ever disabled.
        """
        if not self._figure_blocks:
            return

        window_key = self._cmb_time_window.currentText()
        window_sec = TIME_WINDOWS.get(window_key)

        for block in self._figure_blocks:
            vb = block.get_plot_item().getViewBox()
            if window_sec is None:
                # "All" mode: reset positions, let pyqtgraph auto-range.
                block.reset_curve_positions()
                vb.enableAutoRange(axis=pg.ViewBox.XAxis)
                vb.enableAutoRange(axis=pg.ViewBox.YAxis)
            else:
                # Fixed-window / position-offset: lock x-range, disable
                # auto-range (Y is managed manually in refresh tick).
                block.reset_curve_positions()
                vb.disableAutoRange(axis=pg.ViewBox.XAxis)
                vb.disableAutoRange(axis=pg.ViewBox.YAxis)
                vb.setRange(xRange=(0, window_sec), padding=0)

                # Position curves to current time if data is available,
                # preventing a one-frame flash of t=0..window_sec.
                t_max = self._data_store.get_latest_timestamp()
                if t_max is not None:
                    t_min = max(0.0, t_max - window_sec)
                    block.shift_curves(t_min)

    def _on_user_panned(self) -> None:
        """Slot: user panned or zoomed manually -- disable auto-scroll.

        This fires on the *first* mouse-move of a drag (subsequent moves
        are no-ops thanks to the early return).

        If position-offset scrolling was active, converts the view back
        to absolute coordinates so that pyqtgraph's built-in Y auto-range
        works correctly during manual exploration.

        With x-link enabled, the drag on one plot has already propagated
        the range to all others before this handler runs.  We save the
        offset first, reset all curves, then set the absolute range on
        the first block only (x-link propagates it).
        """
        if not self._auto_scroll:
            return
        self._auto_scroll = False

        # All blocks share the same offset during position-offset mode.
        # Save it before reset_curve_positions zeroes it out.
        offset = (
            self._figure_blocks[0].get_x_offset()
            if self._figure_blocks
            else 0.0
        )

        for block in self._figure_blocks:
            block.reset_curve_positions()
            vb = block.get_plot_item().getViewBox()
            vb.disableAutoRange(axis=pg.ViewBox.XAxis)
            vb.enableAutoRange(axis=pg.ViewBox.YAxis)

        # Convert from offset coords to absolute on the first block.
        # x-link propagates the new range to all other blocks.
        if offset != 0.0 and self._figure_blocks:
            vb = self._figure_blocks[0].get_plot_item().getViewBox()
            [[x_lo, x_hi], _] = vb.viewRange()
            vb.setRange(
                xRange=(x_lo + offset, x_hi + offset),
                padding=0,
                disableAutoRange=True,
            )

    def _on_fit_requested(self) -> None:
        """Slot: user middle-clicked to re-enable auto-scroll.

        Calls ``_apply_x_axis_policy`` which transitions back into
        position-offset mode (or "All" auto-range) as appropriate.
        """
        self._auto_scroll = True
        self._apply_x_axis_policy()

    # --- Dynamic plot count ---

    def _on_n_plots_changed(self, new_text: str) -> None:
        new_count = int(new_text)
        if new_count == len(self._figure_blocks):
            return

        # Save current selections
        saved_selections: list[list[str]] = []
        for block in self._figure_blocks:
            saved_selections.append(block.get_selected_signals())

        # Tear down existing blocks
        for block in self._figure_blocks:
            self._plots_container.removeWidget(block)
            block.setParent(None)
            block.deleteLater()
        self._figure_blocks.clear()

        # Rebuild
        self._rebuild_figure_blocks(new_count)

        # Restore selections for blocks that still exist
        for i, block in enumerate(self._figure_blocks):
            if i < len(saved_selections):
                block.selector.set_selected(saved_selections[i])

        # If streaming is active, new blocks need axis policies applied.
        if self._refresh_timer.isActive():
            self._apply_x_axis_policy()

        logger.info("Plot count changed to %d", new_count)

    def _rebuild_figure_blocks(self, count: int) -> None:
        """Create ``count`` FigureBlock widgets and add them to the layout."""
        signal_names = self._data_store.get_signal_names()

        for i in range(count):
            block = FigureBlock(data_store=self._data_store)

            # Connect viewbox signals for auto-scroll control
            vb = block.get_plot_item().getViewBox()
            vb.userPanned.connect(self._on_user_panned)
            vb.fitRequested.connect(self._on_fit_requested)

            if signal_names:
                block.update_signal_list(signal_names)
            self._figure_blocks.append(block)
            self._plots_container.addWidget(block, 1)  # equal stretch for all

        # Link x-axes so panning/zooming one plot moves all others.
        # During position-offset auto-scroll the ViewBox range never
        # changes, so the link is a no-op (no cascade overhead).
        if LINK_X_AXES and len(self._figure_blocks) > 1:
            first_plot = self._figure_blocks[0].get_plot_item()
            for block in self._figure_blocks[1:]:
                block.get_plot_item().setXLink(first_plot)

    # --- Presets ---

    def _load_presets_from_file(self) -> None:
        """Load presets from the YAML config file and populate the dropdown."""
        self._presets.clear()
        if os.path.isfile(self._preset_path):
            try:
                with open(self._preset_path, "r") as f:
                    data = yaml.safe_load(f)
                if isinstance(data, dict):
                    self._presets = data
            except Exception:
                logger.exception("Failed to load presets from %s", self._preset_path)

        # Refresh the dropdown without triggering _on_load_preset
        self._cmb_presets.blockSignals(True)
        self._cmb_presets.clear()
        self._cmb_presets.addItem("(none)")
        for name in self._presets:
            self._cmb_presets.addItem(name)
        self._cmb_presets.blockSignals(False)

    def _on_save_preset(self) -> None:
        """Capture current view state and save as a named preset."""
        name, ok = QInputDialog.getText(self, "Save Preset", "Preset name:")
        if not ok or not name.strip():
            return
        name = name.strip()

        # Capture: list of signal lists, one per plot block
        signals_per_plot = []
        for block in self._figure_blocks:
            signals_per_plot.append(block.get_selected_signals())

        self._presets[name] = signals_per_plot

        # Write all presets to YAML
        os.makedirs(os.path.dirname(self._preset_path), exist_ok=True)
        with open(self._preset_path, "w") as f:
            yaml.dump(self._presets, f, default_flow_style=False)

        # Refresh dropdown and select the new preset
        self._cmb_presets.blockSignals(True)
        self._cmb_presets.clear()
        self._cmb_presets.addItem("(none)")
        for preset_name in self._presets:
            self._cmb_presets.addItem(preset_name)
        self._cmb_presets.setCurrentText(name)
        self._cmb_presets.blockSignals(False)

        self._lbl_status.setText(f"Preset '{name}' saved")
        logger.info("Preset '%s' saved with %d plots", name, len(signals_per_plot))

    def _on_load_preset(self, preset_name: str) -> None:
        """Restore a saved preset view."""
        if preset_name == "(none)" or preset_name not in self._presets:
            return

        signals_per_plot = self._presets[preset_name]
        n_plots = len(signals_per_plot)

        # Clamp to valid range
        if n_plots < 1:
            return
        if n_plots > MAX_PLOT_COUNT:
            n_plots = MAX_PLOT_COUNT
            signals_per_plot = signals_per_plot[:MAX_PLOT_COUNT]

        # Update n_plots dropdown (this triggers _on_n_plots_changed which
        # rebuilds blocks, but we need to apply selections after)
        self._cmb_n_plots.blockSignals(True)
        self._cmb_n_plots.setCurrentText(str(n_plots))
        self._cmb_n_plots.blockSignals(False)

        # Manually rebuild if count differs
        if n_plots != len(self._figure_blocks):
            for block in self._figure_blocks:
                self._plots_container.removeWidget(block)
                block.setParent(None)
                block.deleteLater()
            self._figure_blocks.clear()
            self._rebuild_figure_blocks(n_plots)

        # Apply signal selections
        for i, block in enumerate(self._figure_blocks):
            if i < len(signals_per_plot):
                block.selector.set_selected(signals_per_plot[i])
            else:
                block.selector.set_selected([])

        # If streaming is active, apply axis policies to any newly created
        # blocks (same rationale as _on_n_plots_changed).
        if self._refresh_timer.isActive():
            self._apply_x_axis_policy()

        self._lbl_status.setText(f"Preset '{preset_name}' loaded")
        logger.info("Preset '%s' loaded", preset_name)
