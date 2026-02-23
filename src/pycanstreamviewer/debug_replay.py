"""Synthetic CAN message generator for hardware-free testing."""

import logging
import math
import time

import can
import cantools
from PyQt6.QtCore import QTimer

from .constants import (
    DEBUG_MAX_REPLAY_MESSAGES,
    DEBUG_REPLAY_INTERVAL_MS,
    DEBUG_SIGNAL_DEFAULT_AMPLITUDE,
    DEBUG_SIGNAL_DEFAULT_MIDPOINT,
    DEBUG_SIGNAL_MIN_AMPLITUDE,
)

logger = logging.getLogger(__name__)


class DebugReplaySource:
    """Generates synthetic CAN messages for debug / testing.

    Uses a QTimer to periodically encode and send messages into a virtual
    bus.  The Notifier then processes them identically to real hardware.

    Signal values vary over time as sine waves so the plots show realistic
    waveforms.
    """

    def __init__(self, bus: can.BusABC, db: cantools.database.Database):
        self._bus = bus
        self._db = db
        self._timer: QTimer | None = None
        self._replay_messages = db.messages[:DEBUG_MAX_REPLAY_MESSAGES]
        logger.info(
            "DebugReplaySource: replaying %d/%d DBC messages",
            len(self._replay_messages),
            len(db.messages),
        )

    def start(self, interval_ms: int = DEBUG_REPLAY_INTERVAL_MS) -> None:
        """Begin generating synthetic messages at ``interval_ms``."""
        self._timer = QTimer()
        self._timer.timeout.connect(self._send_tick)
        self._timer.start(interval_ms)

    def stop(self) -> None:
        """Stop the generation timer."""
        if self._timer is not None:
            self._timer.stop()
            self._timer = None

    def _send_tick(self) -> None:
        """Encode and send one round of synthetic messages."""
        t = time.time()
        for idx, db_msg in enumerate(self._replay_messages):
            data: dict[str, float] = {}
            for sig in db_msg.signals:
                mid, amp = self._signal_range(sig)
                # Each signal gets a unique frequency so traces are distinct
                freq = 0.1 * (idx + 1) + 0.05 * (abs(hash(sig.name)) % 7)
                data[sig.name] = mid + amp * math.sin(t * 2.0 * math.pi * freq)

            try:
                encoded = db_msg.encode(data)
                msg = can.Message(
                    arbitration_id=db_msg.frame_id,
                    data=encoded,
                    timestamp=t,
                    is_extended_id=db_msg.is_extended_frame,
                )
                self._bus.send(msg)
            except Exception:
                # Encoding can fail if synthetic value is out of range;
                # log once and keep going
                logger.debug(
                    "Debug replay encode error for %s", db_msg.name, exc_info=True
                )

    @staticmethod
    def _signal_range(sig) -> tuple[float, float]:
        """Compute midpoint and amplitude for a DBC signal.

        Falls back to reasonable defaults when min/max are not defined.
        """
        if sig.minimum is not None and sig.maximum is not None:
            mid = (sig.minimum + sig.maximum) / 2.0
            amp = (sig.maximum - sig.minimum) / 2.0
            if amp == 0:
                amp = DEBUG_SIGNAL_MIN_AMPLITUDE
        else:
            mid = DEBUG_SIGNAL_DEFAULT_MIDPOINT
            amp = DEBUG_SIGNAL_DEFAULT_AMPLITUDE
        return mid, amp
