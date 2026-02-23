"""Custom pyqtgraph ViewBox and AxisItem for the live plot widgets.

Ported from pyCANlogViewer/plot_example.py.
"""

import pyqtgraph as pg
from PyQt6.QtCore import pyqtSignal
from pyqtgraph.Qt import QtCore


class OffsetTimeAxis(pg.AxisItem):
    """AxisItem that adds a configurable offset to tick labels.

    Used for position-offset scrolling: the ViewBox x-range stays fixed
    at ``(0, window_sec)`` while curves slide via ``setPos()``.  This
    axis adds the current time offset so labels show real elapsed time
    instead of the local 0-based coordinates.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._offset = 0.0

    def set_offset(self, offset: float) -> None:
        if offset != self._offset:
            self._offset = offset
            # Invalidate pyqtgraph's cached QPicture for axis ticks.
            # AxisItem.paint() skips regeneration when self.picture is
            # not None, so we must clear it to force new tick labels.
            self.picture = None
            self.update()

    def tickStrings(self, values, scale, spacing):
        shifted = [v + self._offset for v in values]
        return super().tickStrings(shifted, scale, spacing)


class CustomViewBox(pg.ViewBox):
    """ViewBox with custom mouse behavior:
    - Left-drag: pan
    - Middle-click: re-enable auto-range (fit all data, follow new data)
    - Right-drag: rect zoom (default RectMode)
    - Wheel: zoom in/out

    Emits ``userPanned`` when the user manually pans, zooms, or rect-zooms
    (any gesture that should disable auto-scroll).
    Emits ``fitRequested`` when the user middle-clicks to re-enable auto-scroll.
    """

    userPanned = pyqtSignal()
    fitRequested = pyqtSignal()

    def __init__(self, *args, **kwds):
        super().__init__(*args, **kwds)
        self.setMouseMode(self.RectMode)

    def mouseClickEvent(self, ev):
        if ev.button() == QtCore.Qt.MouseButton.MiddleButton:
            # Axis auto-range policy is fully managed by MainWindow via
            # the fitRequested signal.  Do NOT enable auto-range here --
            # _apply_x_axis_policy decides whether to use pyqtgraph
            # auto-range or position-offset scrolling with manual Y.
            self.fitRequested.emit()
            ev.accept()
        else:
            super().mouseClickEvent(ev)

    def mouseDragEvent(self, ev, axis=None):
        if ev.button() == QtCore.Qt.MouseButton.LeftButton:
            self.setMouseMode(self.PanMode)
            super().mouseDragEvent(ev, axis=axis)
            self.setMouseMode(self.RectMode)
        else:
            super().mouseDragEvent(ev, axis=axis)
        self.userPanned.emit()

    def wheelEvent(self, ev, axis=None):
        super().wheelEvent(ev, axis=axis)
        self.userPanned.emit()
