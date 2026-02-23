"""Scrollable checkbox list for selecting CAN signals."""

import logging

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .constants import MAX_LINES_PER_PLOT, SIGNAL_SELECTOR_MIN_WIDTH

logger = logging.getLogger(__name__)


class SignalSelector(QWidget):
    """Scrollable, filterable list of checkboxes for signal selection.

    Emits selectionChanged with the list of currently checked signal names
    whenever a checkbox is toggled.  Enforces a maximum of ``max_selected``
    simultaneous selections (defaults to MAX_LINES_PER_PLOT).
    """

    selectionChanged = pyqtSignal(list)

    def __init__(self, max_selected: int = MAX_LINES_PER_PLOT, parent=None):
        super().__init__(parent)
        self._checkboxes: dict[str, QCheckBox] = {}
        self._suppress_signals = False
        self._max_selected = max_selected

        self.setMinimumWidth(SIGNAL_SELECTOR_MIN_WIDTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Search/filter box
        self._filter_edit = QLineEdit()
        self._filter_edit.setPlaceholderText("Filter signals...")
        self._filter_edit.textChanged.connect(self._apply_filter)
        layout.addWidget(self._filter_edit)

        # Scrollable checkbox area
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_widget = QWidget()
        self._checkbox_layout = QVBoxLayout(self._scroll_widget)
        self._checkbox_layout.setContentsMargins(4, 4, 4, 4)
        self._checkbox_layout.addStretch()
        self._scroll_area.setWidget(self._scroll_widget)
        layout.addWidget(self._scroll_area)

    def set_signals(self, signal_names: list[str]) -> None:
        """Replace all checkboxes with a new sorted set of signal names."""
        self._suppress_signals = True

        # Clear existing checkboxes
        for cb in self._checkboxes.values():
            self._checkbox_layout.removeWidget(cb)
            cb.deleteLater()
        self._checkboxes.clear()

        # Add new checkboxes (sorted alphabetically)
        for name in sorted(signal_names):
            cb = QCheckBox(name)
            cb.stateChanged.connect(self._on_checkbox_changed)
            # Insert before the stretch at the end
            self._checkbox_layout.insertWidget(
                self._checkbox_layout.count() - 1, cb
            )
            self._checkboxes[name] = cb

        self._filter_edit.clear()
        self._suppress_signals = False

    def add_signals(self, new_names: list[str]) -> None:
        """Merge new signal names into the existing list.

        Preserves the checked state of all existing checkboxes.  Only adds
        checkboxes for names that are not already present.  New checkboxes
        are inserted in alphabetical order among existing ones.
        """
        names_to_add = [n for n in new_names if n not in self._checkboxes]
        if not names_to_add:
            return

        self._suppress_signals = True

        for name in sorted(names_to_add):
            cb = QCheckBox(name)
            cb.stateChanged.connect(self._on_checkbox_changed)

            # Find correct alphabetical insertion position
            insert_idx = 0
            for existing_name in sorted(self._checkboxes.keys()):
                if name < existing_name:
                    break
                insert_idx += 1

            self._checkbox_layout.insertWidget(insert_idx, cb)
            self._checkboxes[name] = cb

            # Apply current filter visibility
            filter_text = self._filter_edit.text().lower()
            if filter_text:
                cb.setVisible(filter_text in name.lower())

        self._suppress_signals = False

    def get_selected(self) -> list[str]:
        """Return list of currently checked signal names."""
        return [
            name
            for name, cb in self._checkboxes.items()
            if cb.isChecked()
        ]

    def set_selected(self, signal_names: list[str]) -> None:
        """Programmatically check the specified signals, uncheck all others."""
        self._suppress_signals = True
        names_set = set(signal_names)
        for name, cb in self._checkboxes.items():
            cb.setChecked(name in names_set)
        self._suppress_signals = False
        self.selectionChanged.emit(self.get_selected())

    def _on_checkbox_changed(self) -> None:
        """Emit selectionChanged when any checkbox is toggled.

        If the user exceeds the maximum selection count, the most recently
        checked box is automatically unchecked and the selection is unchanged.
        """
        if self._suppress_signals:
            return

        selected = self.get_selected()
        if len(selected) > self._max_selected:
            logger.info(
                "Max signals per plot reached (%d), unchecking excess",
                self._max_selected,
            )
            # Find the checkbox that was just checked (sender) and uncheck it
            sender = self.sender()
            if isinstance(sender, QCheckBox):
                self._suppress_signals = True
                sender.setChecked(False)
                self._suppress_signals = False
                selected = self.get_selected()

        self.selectionChanged.emit(selected)

    def _apply_filter(self, text: str) -> None:
        """Show/hide checkboxes based on filter text."""
        text_lower = text.lower()
        for name, cb in self._checkboxes.items():
            cb.setVisible(text_lower in name.lower())
