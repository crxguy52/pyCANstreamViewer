"""CAN bus connection lifecycle manager."""

import logging
import os
from datetime import datetime

import can
import cantools
from PyQt6.QtCore import QObject, pyqtSignal

from .constants import (
    DEBUG_CHANNEL,
    DEBUG_INTERFACE,
    DEBUG_VIRTUAL_CHANNEL,
    DEFAULT_CAN_BITRATE_KEY,
    DEFAULT_RECORDING_DIR,
    CAN_BITRATES,
    RECORDING_FORMATS,
)
from .decode import DecoderListener
from .live_data_store import LiveDataStore
from .utils import get_app_root

logger = logging.getLogger(__name__)


class CanManager(QObject):
    """Manages the CAN bus connection lifecycle.

    Responsibilities:
        - Open / close the CAN bus via python-can.
        - Set up a ``Notifier`` with a ``DecoderListener`` and optional
          file ``Logger``.
        - Emit Qt signals for connection state changes and errors.
        - Support debug mode via a virtual bus + ``DebugReplaySource``.
    """

    connected = pyqtSignal()
    disconnected = pyqtSignal()
    error = pyqtSignal(str)
    new_signals_discovered = pyqtSignal(list)

    def __init__(self, data_store: LiveDataStore, parent: QObject | None = None):
        super().__init__(parent)
        self._data_store = data_store
        self._bus: can.BusABC | None = None
        self._debug_send_bus: can.BusABC | None = None
        self._notifier: can.Notifier | None = None
        self._decoder: DecoderListener | None = None
        self._file_logger: can.io.generic.BaseIOHandler | None = None
        self._db: cantools.database.Database | None = None
        self._debug_source = None  # DebugReplaySource (lazy import)

    # --- Public API ---

    def load_dbc(self, dbc_path: str) -> None:
        """Load a DBC database for message decoding."""
        self._db = cantools.database.load_file(dbc_path)
        logger.info("DBC loaded: %s (%d messages)", dbc_path, len(self._db.messages))

    def start(
        self,
        interface: str,
        channel: str,
        bitrate: int = CAN_BITRATES[DEFAULT_CAN_BITRATE_KEY],
        record: bool = False,
        record_format_key: str = "",
    ) -> None:
        """Open the CAN bus and start receiving messages."""
        if self._bus is not None:
            logger.warning("start() called while already connected, stopping first")
            self.stop()

        if self._db is None:
            self.error.emit("No DBC loaded")
            return

        try:
            is_debug = (
                interface == DEBUG_INTERFACE and channel == DEBUG_CHANNEL
            )

            if is_debug:
                self._bus = can.Bus(
                    interface="virtual", channel=DEBUG_VIRTUAL_CHANNEL
                )
                # python-can's virtual bus does not deliver messages to the
                # same bus instance that sent them.  A second instance on the
                # same channel is needed for the debug replay to inject
                # messages that the Notifier can receive.
                self._debug_send_bus = can.Bus(
                    interface="virtual", channel=DEBUG_VIRTUAL_CHANNEL
                )
            else:
                self._bus = can.Bus(
                    interface=interface,
                    channel=channel,
                    bitrate=bitrate,
                )

            # Create decoder listener
            self._decoder = DecoderListener(
                db=self._db,
                data_store=self._data_store,
                new_signals_callback=self._on_new_signals,
                error_callback=self._on_bus_error,
            )

            listeners: list[can.Listener] = [self._decoder]

            # Optional file recording
            if record and record_format_key:
                suffix = RECORDING_FORMATS.get(record_format_key, ".blf")
                timestamp_str = datetime.now().strftime("%Y-%m-%d_%H%M%S")
                rec_dir = os.path.join(get_app_root(), DEFAULT_RECORDING_DIR)
                os.makedirs(rec_dir, exist_ok=True)
                filename = os.path.join(
                    rec_dir, f"can_recording_{timestamp_str}{suffix}"
                )
                self._file_logger = can.Logger(filename)
                listeners.append(self._file_logger)
                logger.info("Recording to %s", filename)

            # python-can Notifier runs its own daemon thread for bus.recv()
            self._notifier = can.Notifier(self._bus, listeners, timeout=1.0)

            # Start debug replay if virtual bus
            if is_debug:
                self._start_debug_replay()

            logger.info(
                "CAN bus started: interface=%s channel=%s bitrate=%d",
                interface,
                channel,
                bitrate,
            )
            self.connected.emit()

        except Exception as exc:
            logger.exception("Failed to start CAN bus")
            # Clean up any partially-initialized resources without emitting
            # disconnected (we never successfully connected)
            self._cleanup()
            self.error.emit(str(exc))

    def stop(self) -> None:
        """Stop receiving and close the bus.

        Safe to call even if not currently connected -- in that case
        this is a no-op (no ``disconnected`` signal is emitted).
        """
        was_connected = self._bus is not None
        self._cleanup()
        if was_connected:
            logger.info("CAN bus stopped")
            self.disconnected.emit()

    def _cleanup(self) -> None:
        """Release all CAN resources without emitting signals."""
        if self._debug_source is not None:
            self._debug_source.stop()
            self._debug_source = None

        if self._notifier is not None:
            self._notifier.stop()
            self._notifier = None

        if self._file_logger is not None:
            self._file_logger.stop()
            self._file_logger = None

        if self._debug_send_bus is not None:
            self._debug_send_bus.shutdown()
            self._debug_send_bus = None

        if self._bus is not None:
            self._bus.shutdown()
            self._bus = None

        self._decoder = None

    # --- Private helpers ---

    def _on_bus_error(self, exc: Exception) -> None:
        """Called by DecoderListener when the Notifier encounters a bus error.

        This is called from the Notifier's background thread.  Emitting the
        ``error`` Qt signal is safe via queued connection (see _on_new_signals).
        """
        self.error.emit(f"CAN bus error: {exc}")

    def _on_new_signals(self, new_names: list[str]) -> None:
        """Called by DecoderListener when previously-unseen signals arrive.

        This is called from the Notifier's background thread.  Emitting a
        Qt signal here is safe -- Qt delivers it via queued connection when
        the receiver lives in a different thread.
        """
        self.new_signals_discovered.emit(new_names)

    def _start_debug_replay(self) -> None:
        """Start injecting synthetic CAN messages into the virtual bus."""
        # Lazy import to avoid circular dependency and keep debug code
        # out of the critical path
        from .debug_replay import DebugReplaySource

        self._debug_source = DebugReplaySource(self._debug_send_bus, self._db)
        self._debug_source.start()
        logger.info("Debug replay source started")
