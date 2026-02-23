"""Real-time CAN message decoding via python-can Listener interface."""

import logging
from collections.abc import Callable

import can
import cantools

from .live_data_store import LiveDataStore

logger = logging.getLogger(__name__)


class DecoderListener(can.Listener):
    """Decodes CAN messages in real-time and stores decoded signals.

    This is a python-can ``Listener`` called by the ``Notifier``'s
    background thread for each received message.  It decodes the message
    using the DBC database and appends each signal value to the
    ``LiveDataStore``.
    """

    def __init__(
        self,
        db: cantools.database.Database,
        data_store: LiveDataStore,
        new_signals_callback: Callable[[list[str]], None] | None = None,
        error_callback: Callable[[Exception], None] | None = None,
    ):
        self._db = db
        self._data_store = data_store
        self._new_signals_callback = new_signals_callback
        self._error_callback = error_callback
        self._no_decode: set[int] = set()  # arb IDs not in DBC
        self._known_signals: set[str] = set()

    def on_message_received(self, msg: can.Message) -> None:
        """Called by Notifier for each received CAN message."""
        if msg.arbitration_id in self._no_decode:
            return

        try:
            db_message = self._db.get_message_by_frame_id(msg.arbitration_id)
            signals = db_message.decode(msg.data, decode_choices=False)

            newly_discovered: list[str] = []
            for signal_name, value in signals.items():
                self._data_store.append(signal_name, msg.timestamp, float(value))

                if signal_name not in self._known_signals:
                    self._known_signals.add(signal_name)
                    newly_discovered.append(signal_name)

            if newly_discovered and self._new_signals_callback:
                self._new_signals_callback(newly_discovered)

        except KeyError:
            logger.info(
                "Cannot decode ArbID %d (0x%03X), skipping",
                msg.arbitration_id,
                msg.arbitration_id,
            )
            self._no_decode.add(msg.arbitration_id)
        except Exception:
            logger.exception(
                "Error decoding message arb_id=0x%03X", msg.arbitration_id
            )

    def on_error(self, exc: Exception) -> None:
        """Called by Notifier when bus.recv() raises an exception.

        This typically happens when CAN hardware is unplugged mid-stream.
        """
        logger.error("CAN bus error in Notifier: %s", exc)
        if self._error_callback is not None:
            self._error_callback(exc)

    def stop(self) -> None:
        """Called by Notifier on shutdown."""
