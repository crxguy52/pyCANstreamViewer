"""Top-level entry point: create QApplication, configure pyqtgraph, show window."""

import logging
import os
import sys

import pyqtgraph as pg
from PyQt6.QtWidgets import QApplication

from .constants import ANTIALIAS_ENABLED, LOG_DIR_NAME, USE_OPENGL
from .logging_config import setup_logging
from .main_window import MainWindow
from .utils import get_app_root

logger = logging.getLogger(__name__)


def main():
    """Top-level orchestration function."""
    log_dir = os.path.join(get_app_root(), LOG_DIR_NAME)
    setup_logging(log_dir=log_dir)

    app = QApplication(sys.argv)
    pg.setConfigOptions(antialias=ANTIALIAS_ENABLED, useOpenGL=USE_OPENGL)

    try:
        window = MainWindow()
    except Exception:
        if USE_OPENGL:
            logger.warning(
                "Failed to create window with OpenGL enabled, "
                "falling back to software rendering",
                exc_info=True,
            )
            pg.setConfigOptions(useOpenGL=False)
            window = MainWindow()
        else:
            raise

    window.show()

    sys.exit(app.exec())
