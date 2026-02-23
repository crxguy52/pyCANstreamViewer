"""Shared utility functions."""

import math
import os
import sys


def get_app_root() -> str:
    """Return the application root directory.

    When running as a PyInstaller bundle, returns the directory containing the
    executable (where config/, dbc/, logs/, etc. live).  When running from
    source, returns the project root via triple-parent traversal from this file.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )


def eng_str(x, fmt="%s", si=False):
    """Format a number in engineering notation (exponent is a multiple of 3).

    Adapted from pyCANlogViewer/plot_example.py.

    Args:
        x: Numeric value to format.
        fmt: printf-style format string for the mantissa.
        si: If True, use SI suffixes (k, M, G, etc.) instead of e-notation.

    Returns:
        Formatted string in engineering notation.
    """
    if x is None:
        return "None"

    try:
        x = float(x)
    except (ValueError, TypeError):
        return str(x)

    if math.isnan(x):
        return "NaN"

    if math.isinf(x):
        return "-Inf" if x < 0 else "Inf"

    if x == 0:
        return fmt % 0

    sign = ""
    if x < 0:
        x = -x
        sign = "-"

    exp = int(math.floor(math.log10(x)))
    exp3 = exp - (exp % 3)
    x3 = x / (10**exp3)

    if si and exp3 >= -24 and exp3 <= 24 and exp3 != 0:
        exp3_text = "yzafpnum kMGTPEZY"[int((exp3 - (-24)) / 3)]
    elif exp3 == 0:
        exp3_text = ""
    else:
        exp3_text = "e%s" % exp3

    return ("%s" + fmt + "%s") % (sign, x3, exp3_text)
