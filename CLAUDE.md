# pyCANstreamViewer

Live CAN bus viewer with PyQt6 and pyqtgraph. Streams, decodes, and plots CAN signals in real time.

## Architecture

### Top-level orchestration
- `main.py` creates QApplication and shows `MainWindow`
- `MainWindow` delegates to `CanManager`, `LiveDataStore`, and `FigureBlock`

### Data flow
```
CAN Bus -> python-can Notifier (daemon thread)
  -> DecoderListener.on_message_received()
    -> LiveDataStore.append() [thread-safe, O(1)]
  -> can.Logger (optional recording)

GUI Thread:
  QTimer @ configurable Hz -> FigureBlock.refresh_plots()
    -> LiveDataStore.get_arrays() [lock + numpy copy]
```

### Key design decisions
- **No data loss**: Every CAN frame is captured into circular buffers. Refresh rate only controls screen redraw frequency.
- **Thread safety**: `LiveDataStore` uses `threading.Lock`. Write path (append) is O(1). Read path (get_arrays) copies numpy arrays so GUI can render without holding the lock.
- **Device scanning**: Uses `can.detect_available_configs()` for multi-interface hardware enumeration (PCAN, Kvaser, IXXAT, Vector, socketcan, etc.).
- **Debug mode**: Selecting "virtual: debug" device uses a virtual CAN bus with synthetic sine-wave data. No hardware required.

## File structure
```
src/pycanstreamviewer/
  main.py              - QApplication setup
  main_window.py       - GUI layout + orchestration
  figure_block.py      - SignalSelector + pyqtgraph plot widget
  signal_selector.py   - Filterable checkbox list
  live_data_store.py   - Thread-safe circular buffers
  can_manager.py       - CAN bus lifecycle (connect/disconnect/record)
  device_scanner.py    - CAN device enumeration
  decode.py            - Real-time DecoderListener
  debug_replay.py      - Synthetic data for hardware-free testing
  custom_viewbox.py    - Mouse gesture overrides for pyqtgraph
  utils.py             - Engineering notation formatter
  constants.py         - All named constants
  logging_config.py    - Dual console + file logging
```

## Running
```
pdm install
pdm run start
```

## Dependencies
- PyQt6, pyqtgraph, python-can, cantools, PyYAML, numpy

## Known issues / history
- 2026-02-19: Staff engineer code review. Fixes implemented:
  - **BUG**: `MainWindow.closeEvent` was missing -- CAN bus, Notifier thread, and file logger were left running on window close. Added `closeEvent` to cleanly shut down all resources.
  - **BUG**: `debug_replay.py` frequency calculation `0.05 * hash(sig.name) % 7` could produce negative frequencies due to negative `hash()` values. Fixed with `abs(hash(...))`.
  - **BUG**: `_on_start` could crash with `ValueError` if user clicked Start with "No devices found" selected (label lacks `: ` separator needed by `parse_device_label`). Added guard for invalid device text format.
  - **BUG**: `can_manager.start()` exception path leaked the partially-opened CAN bus. Refactored `stop()` into `_cleanup()` (no signals) + `stop()` (with `disconnected` signal). Exception handler now calls `_cleanup()`.
  - **BUG**: `can_manager.stop()` emitted `disconnected` even when never connected (e.g., called from `closeEvent` on fresh launch). Now only emits when a bus was actually open.
  - Added double-start guard in `can_manager.start()` -- calls `stop()` first if already connected.
  - Added `DecoderListener.on_error()` to surface CAN bus errors (e.g., hardware unplugged mid-stream) to the UI via `CanManager.error` signal.
  - Moved `MAX_REPLAY_MESSAGES` and magic numbers (50.0 defaults, 1.0 min amplitude) from `debug_replay.py` to `constants.py` as named constants.
- 2026-02-19: Staff engineer review of lazy device scan, middle-click auto-range, and mouse key label. Fixes implemented:
  - **BUG**: `CustomViewBox.mouseClickEvent` did not call `ev.accept()` on middle-click, allowing the event to propagate through pyqtgraph's scene graph. Added `ev.accept()`.
  - **UX**: `_on_scan_devices` blocked the GUI thread for several seconds with no visual feedback. Added `QApplication.setOverrideCursor(WaitCursor)` and `processEvents()` so the "Scanning..." status label is painted and the cursor changes before the blocking `scan_can_devices()` call. Wrapped in try/finally to guarantee cursor restoration.
  - **CODE QUALITY**: Magic string `"Click to scan..."` was duplicated in two locations (combo init and `_on_start` guard). Extracted to `DEVICE_SCAN_LABEL_INITIAL` in `constants.py`.
- 2026-02-19: Added x-axis time window dropdown, performance optimization, and distribution.py:
  - **FEATURE**: Time window dropdown (`win_10s`, `win_30s`, `win_60s`, `win_120s`, `win_300s`, `win_all`) controls visible x-axis span during auto-scroll. Default: 30s.
  - **PERFORMANCE**: Enabled `clipToView=True` on all PlotDataItems so pyqtgraph only renders points within the visible x-range, reducing GPU/CPU load when buffer is full.
  - **FEATURE**: Auto-scroll logic -- when streaming, x-axis follows the latest data within the selected time window. Pan/zoom/scroll disables auto-scroll; middle-click re-enables it.
  - **FEATURE**: `CustomViewBox` now emits `userPanned` and `fitRequested` signals for auto-scroll state management.
  - **FEATURE**: `LiveDataStore.get_latest_timestamp()` tracks the most recent relative timestamp with O(1) cost.
  - **BUILD**: `distribution.py` uses `beta.common.pyinstaller.build` for PyInstaller packaging. Run via `pdm run dist`.
- 2026-02-19: Staff engineer review of auto-scroll, time window, and distribution changes. Fixes implemented:
  - **BUG**: `CustomViewBox.mouseClickEvent` middle-click called `enableAutoRange(XYAxes)` unconditionally, causing a one-frame flicker in fixed-window mode (view jumped to show ALL data, then snapped back on next timer tick). Changed to only enable Y-axis auto-range; X-axis policy is now managed by `MainWindow._apply_x_axis_policy()`.
  - **BUG**: `_on_refresh_tick` in "All" mode called `enableAutoRange(XAxis)` on every single tick (up to 60Hz). This was redundant and wasteful -- auto-range stays enabled once set. Moved to one-time setup in `_apply_x_axis_policy()`.
  - **BUG**: `_on_user_panned` set `_auto_scroll = False` but did not disable x auto-range on the ViewBox. In "All" mode, pyqtgraph's auto-range would fight the user's pan, snapping the view back on every repaint. Now explicitly calls `disableAutoRange(XAxis)`.
  - **BUG**: `_on_time_window_changed` did not disable x auto-range when switching from "All" to fixed-window mode, causing a one-frame glitch. Now delegates to `_apply_x_axis_policy()` which handles both directions.
  - **REFACTOR**: Extracted `_apply_x_axis_policy()` in `MainWindow` to centralize x-axis auto-range management. Called from `_on_connected`, `_on_fit_requested`, `_on_time_window_changed`, and `_on_user_panned`. Eliminates scattered/inconsistent auto-range toggling.
  - **MAINTENANCE**: `__init__.py` version was hardcoded as `"0.1.0"`, duplicating the version in `pyproject.toml`. Replaced with `importlib.metadata.version()` so the version is always read from the installed package metadata (single source of truth).
- 2026-02-19: Fixed debug mode data flow:
  - **BUG**: python-can's virtual bus does NOT deliver messages to the same `can.Bus` instance that sent them. The debug replay and the Notifier were sharing one bus instance, so zero messages were ever received. Fixed by creating a second virtual bus instance (`_debug_send_bus`) on the same channel for the debug replay to send on. The Notifier's bus instance receives the messages via the shared virtual channel.
- 2026-02-19: Removed x-axis linking between plots (performance), removed 60Hz refresh rate. Staff engineer review fixes:
  - **BUG**: `_on_n_plots_changed` did not apply x-axis policy or y auto-range to newly created figure blocks when called during active streaming. New blocks would have default ViewBox auto-range state, causing a visual glitch (one-frame jump or incorrect axis behavior). Added `_apply_x_axis_policy()` and y auto-range enable after rebuild when `_refresh_timer.isActive()`.
  - **BUG**: `_on_load_preset` had the same issue -- rebuilding blocks during streaming left new ViewBoxes without the current axis policies. Applied same fix.
- 2026-02-20: Performance optimization: OpenGL rendering, antialias off, skipFiniteCheck. Staff engineer review fixes:
  - **ROBUSTNESS**: `main.py` had no fallback if OpenGL context creation fails (e.g., VM without GPU, broken driver). `MainWindow()` construction would crash ungracefully. Added try/except that catches OpenGL failures and falls back to software rendering with a warning log.
- 2026-02-20: Staff engineer review of position-offset scrolling PR. Fixes implemented:
  - **PERFORMANCE**: `_on_refresh_tick` called `refresh_plots()` (which calls `setData()` and triggers `clipToView` path rebuild) BEFORE `shift_curves()` (which calls `setPos()` and triggers a second path rebuild via `viewRangeChanged`). Swapped the order so `shift_curves()` runs first -- positions are correct when `setData()` rebuilds the path, avoiding one redundant path rebuild per visible line per tick.
  - **PERFORMANCE**: `refresh_plots()` Y-range computation used an O(n) boolean mask (`(t >= lo) & (t <= hi)`) over the full circular buffer. Replaced with `np.searchsorted()` which is O(log n) since time arrays are guaranteed sorted. Eliminates a 50K-element boolean array allocation and two 50K-element comparisons per signal per tick.
- 2026-02-20: Staff engineer review of x-axis linking PR (`LINK_X_AXES`, `setXLink` in `_rebuild_figure_blocks`, restructured `_on_user_panned`). Fixes implemented:
  - **BUG**: `CustomViewBox.wheelEvent` emitted `userPanned` BEFORE `super().wheelEvent()`, opposite of `mouseDragEvent` which emits AFTER. While both orderings produce correct results for the current `_on_user_panned` logic, the inconsistency is a maintenance hazard -- future changes to `_on_user_panned` that depend on post-interaction ViewBox state would break only for wheel events. Moved `userPanned.emit()` after `super().wheelEvent()` to match `mouseDragEvent` ordering.
  - **DOCS**: Added note in `_apply_x_axis_policy` docstring explaining that with `LINK_X_AXES` the `setRange`/`enableAutoRange` calls on blocks 1+ are redundant (block 0 propagates via x-link) but kept for robustness.
  - **VERIFIED SAFE**: Offset-to-absolute conversion in `_on_user_panned` is correct with x-link. When user drags on block N, x-link propagates the range to block 0 before the handler reads it. The saved offset + propagated range produces correct absolute coordinates.
  - **VERIFIED SAFE**: No circular signal cascades. pyqtgraph uses `blockLink(True)` to prevent ping-pong during `linkedViewChanged`, and `userPanned`/`fitRequested` only fire from direct mouse input handlers (not from x-link propagation).
  - **VERIFIED SAFE**: No dangling references on plot rebuild. pyqtgraph uses `weakref` for linked views; dead references return `None` and `linkedViewChanged` exits early.
- 2026-02-23: Replaced `distribution.py` with standalone PyInstaller build (removed `beta.common` dependency):
  - **REFACTOR**: Moved `distribution.py` from project root to `src/pycanstreamviewer/distribution.py`. Now invoked via `pdm run dist` (`python -m pycanstreamviewer.distribution`).
  - **REFACTOR**: Replaced `beta.common.pyinstaller.build` wrapper with direct `PyInstaller.__main__.run()` calls. All hidden imports for python-can interfaces/IO and metadata copying are explicit in the script.
  - **FEATURE**: `get_app_root()` added to `utils.py` -- frozen-aware path resolver. Returns `os.path.dirname(sys.executable)` when running as PyInstaller bundle, project root when running from source.
  - **BUG**: `main_window.py`, `can_manager.py`, and `main.py` used inline `__file__`-based path resolution that breaks in PyInstaller bundles. Replaced with `get_app_root()`.
  - **LAYOUT**: PyInstaller output places `config/` and `dbc/` next to the `.exe` (outside `_internal/`). Logs and recordings are also created next to the `.exe` at runtime.
  - Removed `py-beta-common` from optional dependencies, bumped PyInstaller requirement to `>=6.0`.
- 2026-02-23: Staff engineer review of standalone PyInstaller build and frozen-app path resolution. Fixes implemented:
  - **BUG**: `distribution.py` listed individual `--hidden-import` entries for each `can.interfaces.*` and `can.io.*` module. This misses nested submodules (e.g. `can.interfaces.ixxat.canlib`, `can.interfaces.pcan.pcan`) that are loaded at runtime -- frozen app would crash with `ModuleNotFoundError` when scanning for IXXAT/PCAN hardware. Replaced with `--collect-submodules can` and `--collect-submodules cantools` which recursively bundle all submodules.
  - **ROBUSTNESS**: `distribution.py` used `--windowed` unconditionally, which suppresses all console output including crash tracebacks. If the frozen app fails before logging is initialized (e.g., DLL import error), the user sees nothing. Added `--console` CLI flag (`pdm run dist -- --console`) for debug builds.
  - **CODE QUALITY**: Magic string `"pycanstreamviewer_debug"` was duplicated in two `can.Bus()` calls in `can_manager.py`. Extracted to `DEBUG_VIRTUAL_CHANNEL` in `constants.py`.
