"""FigureBlock: a signal selector + pyqtgraph plot combined into one widget."""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QSplitter, QVBoxLayout, QWidget

from .constants import ANTIALIAS_ENABLED, DOWNSAMPLE_MODE, MAX_LINES_PER_PLOT
from .custom_viewbox import CustomViewBox, OffsetTimeAxis
from .live_data_store import LiveDataStore
from .signal_selector import SignalSelector


class FigureBlock(QWidget):
    """One plot block: SignalSelector on the left, pyqtgraph plot on the right.

    Pre-allocates MAX_LINES_PER_PLOT line items. When signals are
    checked/unchecked, lines are shown/hidden and their data updated.

    Supports **position-offset scrolling**: instead of changing the
    ViewBox x-range every tick (which triggers expensive auto-range
    recalculations), the ViewBox range stays fixed and curves are
    shifted with ``setPos()``.  The custom OffsetTimeAxis ensures
    axis labels show real elapsed time.
    """

    def __init__(
        self,
        data_store: LiveDataStore,
        parent=None,
    ):
        super().__init__(parent)
        self.data_store = data_store
        self._current_signals: list[str] = []
        self._x_offset = 0.0  # current position-offset value

        # Build the signal selector
        self.selector = SignalSelector()

        # Build the plot widget with custom viewbox and offset-aware time axis
        self._time_axis = OffsetTimeAxis(orientation="bottom")
        self.plot_widget = pg.PlotWidget(
            viewBox=CustomViewBox(),
            axisItems={"bottom": self._time_axis},
        )
        self.plot_item = self.plot_widget.getPlotItem()

        # Configure plot
        self.plot_item.showGrid(x=True, y=True)
        self.plot_item.setLabel("bottom", "Time", units="s")
        self.plot_item.setDownsampling(auto=True, mode=DOWNSAMPLE_MODE)
        self.plot_item.addLegend()

        # Pre-allocate line items with clipToView for performance
        self._lines: list[pg.PlotDataItem] = []
        for i in range(MAX_LINES_PER_PLOT):
            line = self.plot_item.plot(
                [], [],
                pen=(i, MAX_LINES_PER_PLOT),
                name="",
                clipToView=True,
                antialias=ANTIALIAS_ENABLED,
            )
            line.setVisible(False)
            self._lines.append(line)

        # Connect checkbox changes to plot updates
        self.selector.selectionChanged.connect(self._on_selection_changed)

        # Layout: horizontal splitter so user can resize selector vs. plot
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.selector)
        splitter.addWidget(self.plot_widget)
        # Give most space to the plot (roughly 1:4 ratio)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)

    def _on_selection_changed(self, selected_signals: list[str]) -> None:
        """Update visible lines based on which checkboxes are checked."""
        self._current_signals = selected_signals

        # Clear legend and rebuild
        legend = self.plot_item.legend
        if legend is not None:
            legend.clear()

        for i, line in enumerate(self._lines):
            if i < len(selected_signals):
                sig_name = selected_signals[i]
                t, val = self.data_store.get_arrays(sig_name)
                if t is not None:
                    line.setData(t, val, name=sig_name, skipFiniteCheck=True)
                    line.setPos(-self._x_offset, 0)
                    line.setVisible(True)
                    if legend is not None:
                        legend.addItem(line, sig_name)
                else:
                    line.setData([], [])
                    line.setVisible(False)
            else:
                line.setData([], [])
                line.setVisible(False)

    def refresh_plots(
        self, visible_t_range: tuple[float, float] | None = None
    ) -> tuple[float, float] | None:
        """Re-read data from the live data store and update visible lines.

        Called periodically by the QTimer in MainWindow.  Only updates
        lines that are already visible (i.e. their signal is checked).

        Parameters
        ----------
        visible_t_range :
            If provided, also computes the Y-axis bounds for data within
            this time range.  Used for manual Y-range management in
            position-offset scroll mode (where pyqtgraph's auto-range
            cannot correctly determine visible Y bounds).

        Returns
        -------
        tuple or None
            ``(y_min, y_max)`` if *visible_t_range* was given and visible
            data exists, else ``None``.
        """
        y_lo = float("inf")
        y_hi = float("-inf")
        has_data = False

        for i, line in enumerate(self._lines):
            if i < len(self._current_signals) and line.isVisible():
                sig_name = self._current_signals[i]
                t, val = self.data_store.get_arrays(sig_name)
                if t is not None:
                    line.setData(t, val, skipFiniteCheck=True)

                    if visible_t_range is not None and len(t) > 0:
                        # Time arrays are sorted, so use searchsorted
                        # for O(log n) index lookup instead of an O(n)
                        # boolean mask over the full buffer.
                        i_lo = np.searchsorted(t, visible_t_range[0], side="left")
                        i_hi = np.searchsorted(t, visible_t_range[1], side="right")
                        if i_hi > i_lo:
                            vis = val[i_lo:i_hi]
                            y_lo = min(y_lo, float(np.min(vis)))
                            y_hi = max(y_hi, float(np.max(vis)))
                            has_data = True

        if visible_t_range is not None and has_data:
            return (y_lo, y_hi)
        return None

    # --- Position-offset scrolling helpers ---

    def shift_curves(self, x_offset: float) -> None:
        """Slide all visible curves so data at *x_offset* aligns with x=0.

        This is the core of position-offset scrolling: the ViewBox
        x-range stays fixed at ``(0, window_sec)`` and curves are moved
        with ``setPos()``.  The OffsetTimeAxis adds *x_offset* to tick
        labels so the axis shows real elapsed time.
        """
        self._x_offset = x_offset
        for line in self._lines:
            if line.isVisible():
                line.setPos(-x_offset, 0)
        self._time_axis.set_offset(x_offset)

    def reset_curve_positions(self) -> None:
        """Reset all curve positions to origin and clear the axis offset.

        Called when switching to "All" mode, or when converting from
        position-offset back to absolute coordinates (e.g. user pan).
        """
        self._x_offset = 0.0
        for line in self._lines:
            line.setPos(0, 0)
        self._time_axis.set_offset(0.0)

    def get_x_offset(self) -> float:
        """Return the current position-offset value."""
        return self._x_offset

    def update_signal_list(self, signal_names: list[str]) -> None:
        """Called when new signals are discovered to update the checkbox list."""
        self.selector.add_signals(signal_names)

    def get_selected_signals(self) -> list[str]:
        """Return the currently selected signal names."""
        return self.selector.get_selected()

    def get_plot_item(self) -> pg.PlotItem:
        """Return the PlotItem."""
        return self.plot_item
