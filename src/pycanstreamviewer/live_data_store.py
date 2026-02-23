"""Thread-safe circular-buffer data store for live CAN signal data."""

import threading

import numpy as np

from .constants import BUFFER_INITIAL_CAPACITY


class CircularBuffer:
    """Fixed-capacity circular buffer backed by pre-allocated numpy arrays.

    When full, oldest data is overwritten (FIFO eviction).
    All public methods assume the caller holds the parent store's lock.
    """

    def __init__(self, capacity: int = BUFFER_INITIAL_CAPACITY):
        self._t = np.empty(capacity, dtype=np.float64)
        self._val = np.empty(capacity, dtype=np.float64)
        self._capacity = capacity
        self._head = 0  # next write position
        self._count = 0  # number of valid elements

    def append(self, t: float, val: float) -> None:
        """Append a single data point. O(1)."""
        self._t[self._head] = t
        self._val[self._head] = val
        self._head = (self._head + 1) % self._capacity
        if self._count < self._capacity:
            self._count += 1

    def get_arrays(self) -> tuple[np.ndarray, np.ndarray]:
        """Return contiguous, time-ordered copies of the buffered data.

        The returned arrays are safe to use from the GUI thread without
        holding the lock -- they are independent copies.
        """
        if self._count == 0:
            return np.array([], dtype=np.float64), np.array([], dtype=np.float64)

        if self._count < self._capacity:
            # Buffer not yet full -- data is contiguous from index 0..count
            return (
                self._t[: self._count].copy(),
                self._val[: self._count].copy(),
            )

        # Buffer is full and has wrapped. Oldest sample is at self._head.
        tail_len = self._capacity - self._head
        t_out = np.empty(self._capacity, dtype=np.float64)
        val_out = np.empty(self._capacity, dtype=np.float64)
        t_out[:tail_len] = self._t[self._head :]
        t_out[tail_len:] = self._t[: self._head]
        val_out[:tail_len] = self._val[self._head :]
        val_out[tail_len:] = self._val[: self._head]
        return t_out, val_out


class LiveDataStore:
    """Thread-safe container for live CAN signal data.

    The CAN reader thread (Notifier) calls ``append()`` from its thread.
    The GUI thread calls ``get_arrays()`` and ``get_signal_names()`` from
    the main thread.  A ``threading.Lock`` protects all shared state.
    """

    def __init__(self, buffer_capacity: int = BUFFER_INITIAL_CAPACITY):
        self._buffers: dict[str, CircularBuffer] = {}
        self._lock = threading.Lock()
        self._buffer_capacity = buffer_capacity
        self._t0: float | None = None
        self._latest_t: float | None = None

    def append(self, signal_name: str, timestamp: float, value: float) -> None:
        """Add a data point.  Called from the CAN reader thread."""
        with self._lock:
            if self._t0 is None:
                self._t0 = timestamp
            t_rel = timestamp - self._t0

            if self._latest_t is None or t_rel > self._latest_t:
                self._latest_t = t_rel

            if signal_name not in self._buffers:
                self._buffers[signal_name] = CircularBuffer(self._buffer_capacity)
            self._buffers[signal_name].append(t_rel, value)

    def get_arrays(
        self, signal_name: str
    ) -> tuple[np.ndarray | None, np.ndarray | None]:
        """Get time-ordered arrays for a signal.  Called from GUI thread."""
        with self._lock:
            buf = self._buffers.get(signal_name)
            if buf is None:
                return None, None
            return buf.get_arrays()

    def get_signal_names(self) -> list[str]:
        """Return sorted list of all known signal names."""
        with self._lock:
            return sorted(self._buffers.keys())

    def get_latest_timestamp(self) -> float | None:
        """Return the most recent relative timestamp, or None if no data."""
        with self._lock:
            return self._latest_t

    def clear(self) -> None:
        """Clear all data (e.g., on stop / restart)."""
        with self._lock:
            self._buffers.clear()
            self._t0 = None
            self._latest_t = None
