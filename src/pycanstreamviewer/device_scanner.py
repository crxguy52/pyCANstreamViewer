"""CAN device enumeration across all installed python-can interfaces."""

import logging

import can

from .constants import DEBUG_CHANNEL, DEBUG_INTERFACE

logger = logging.getLogger(__name__)


def scan_can_devices() -> list[dict[str, str]]:
    """Scan for all available CAN devices across installed interfaces.

    Uses ``can.detect_available_configs()`` which probes every installed
    python-can interface (PCAN, Kvaser, IXXAT, Vector, socketcan, etc.)
    for connected hardware.

    Returns:
        List of ``{"interface": str, "channel": str}`` dicts.
        Always includes a virtual/debug entry at the end.
    """
    devices: list[dict[str, str]] = []
    try:
        configs = can.detect_available_configs()
        for cfg in configs:
            devices.append(
                {
                    "interface": cfg.get("interface", "unknown"),
                    "channel": str(cfg.get("channel", "")),
                }
            )
        logger.info("Device scan found %d hardware device(s)", len(devices))
    except Exception:
        logger.exception("Error scanning CAN devices")

    # Always include virtual bus for debug / hardware-free testing
    devices.append({"interface": DEBUG_INTERFACE, "channel": DEBUG_CHANNEL})
    return devices


def format_device_label(device: dict[str, str]) -> str:
    """Format a device dict for display in a dropdown.

    Example: ``"pcan: PCAN_USBBUS1"``
    """
    return f"{device['interface']}: {device['channel']}"


def parse_device_label(label: str) -> tuple[str, str]:
    """Inverse of ``format_device_label``.

    Returns:
        ``(interface, channel)`` tuple.
    """
    interface, channel = label.split(": ", 1)
    return interface, channel
