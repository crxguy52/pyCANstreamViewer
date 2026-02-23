"""Named constants for pyCANstreamViewer."""

# Window geometry
WINDOW_MIN_WIDTH = 1200
WINDOW_MIN_HEIGHT = 800
WINDOW_DEFAULT_WIDTH = 1600
WINDOW_DEFAULT_HEIGHT = 1000

# Plot configuration
MAX_PLOT_COUNT = 4
DEFAULT_PLOT_COUNT = 3
MAX_LINES_PER_PLOT = 10

# Signal selector
SIGNAL_SELECTOR_MIN_WIDTH = 250

# Logging
LOG_FORMAT = "%(asctime)s - %(name)-40s - %(levelname)-8s - %(message)s"
LOG_DATE_FORMAT = "%d-%b-%Y %H:%M:%S"

# pyqtgraph rendering
ANTIALIAS_ENABLED = False
USE_OPENGL = False
DOWNSAMPLE_MODE = "peak"
Y_RANGE_PADDING = 50e-3  # fractional padding for manual Y-range management
LINK_X_AXES = True

# File dialog filters and default directories (relative to project root)
DBC_FILTER = "DBC Files (*.dbc);;All Files (*)"
DEFAULT_DBC_DIR = "dbc"

# UI spacing
TOOLBAR_SPACING = 20

# Log directory (relative to CWD at startup)
LOG_DIR_NAME = "logs"

# ---------------------------------------------------------------------------
# Live CAN streaming constants
# ---------------------------------------------------------------------------

# CAN baud rates (dict keys start with string prefix per coding standard)
CAN_BITRATES = {
    "rate_125k": 125_000,
    "rate_250k": 250_000,
    "rate_500k": 500_000,
    "rate_1M": 1_000_000,
}
DEFAULT_CAN_BITRATE_KEY = "rate_500k"

# Circular buffer sizing
BUFFER_INITIAL_CAPACITY = 50_000

# Plot refresh rates
REFRESH_RATES_HZ = {
    "hz_5": 5,
    "hz_10": 10,
    "hz_20": 20,
    "hz_30": 30,
}
DEFAULT_REFRESH_RATE_KEY = "hz_30"

# Recording file formats
RECORDING_FORMATS = {
    "fmt_log": ".log",
    "fmt_blf": ".blf",
}
DEFAULT_RECORDING_DIR = "recordings"

# Debug replay
DEBUG_REPLAY_INTERVAL_MS = 10
DEBUG_MAX_REPLAY_MESSAGES = 5
DEBUG_SIGNAL_DEFAULT_MIDPOINT = 50.0
DEBUG_SIGNAL_DEFAULT_AMPLITUDE = 50.0
DEBUG_SIGNAL_MIN_AMPLITUDE = 1.0

# Time window options for x-axis (seconds, None = show all)
TIME_WINDOWS = {
    "win_10s": 10,
    "win_30s": 30,
    "win_60s": 60,
    "win_120s": 120,
    "win_300s": 300,
    "win_all": None,
}
DEFAULT_TIME_WINDOW_KEY = "win_30s"

# Device scanner labels
DEVICE_SCAN_LABEL_NONE = "No devices found"
DEVICE_SCAN_LABEL_ERROR = "Scan error"
DEVICE_SCAN_LABEL_INITIAL = "Click to scan..."

# Debug virtual bus identifier
DEBUG_INTERFACE = "virtual"
DEBUG_CHANNEL = "debug"
DEBUG_VIRTUAL_CHANNEL = "pycanstreamviewer_debug"
