"""Build a standalone executable with PyInstaller."""

import argparse
import shutil
import sys
from pathlib import Path

from pycanstreamviewer import __version__

# This file lives at src/pycanstreamviewer/distribution.py
# Project root is two levels up
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent.parent


def _build_collect_submodules_args() -> list[str]:
    """Return --collect-submodules flags for dynamically-loaded packages.

    python-can loads interface backends and I/O plugins dynamically via
    importlib and entry_points.  Individual ``--hidden-import`` entries
    miss nested submodules (e.g. ``can.interfaces.ixxat.canlib``,
    ``can.interfaces.pcan.pcan``) and break at runtime on machines with
    that hardware.  ``--collect-submodules`` recursively bundles every
    submodule in the package, which is both more robust and shorter.

    cantools similarly auto-detects database format loaders at import time.
    """
    packages = ["can", "cantools"]
    args: list[str] = []
    for pkg in packages:
        args.extend(["--collect-submodules", pkg])
    return args


def _build_hidden_imports() -> list[str]:
    """Return --hidden-import flags for packages without PyInstaller hooks."""
    modules = [
        "yaml",
        "wrapt",
        "packaging",
        "typing_extensions",
    ]
    args: list[str] = []
    for mod in modules:
        args.extend(["--hidden-import", mod])
    return args


def _build_data_file_args() -> list[str]:
    """Return --add-data flags for config and dbc directories.

    Data files are initially placed inside ``_internal/`` by PyInstaller.
    ``_relocate_data_dirs`` moves them next to the executable after the
    build completes.
    """
    sep = ";" if sys.platform == "win32" else ":"

    config_src = str(_PROJECT_ROOT / "config" / "*.yaml")
    dbc_src = str(_PROJECT_ROOT / "dbc" / "*.dbc")

    return [
        "--add-data", f"{config_src}{sep}config",
        "--add-data", f"{dbc_src}{sep}dbc",
    ]


def _build_metadata_args() -> list[str]:
    """Return --copy-metadata flags for packages that use entry_points."""
    packages = ["python-can", "cantools"]
    args: list[str] = []
    for pkg in packages:
        args.extend(["--copy-metadata", pkg])
    return args


def _relocate_data_dirs(app_dir: Path) -> None:
    """Move config/ and dbc/ from _internal/ to next to the executable.

    PyInstaller does not allow --add-data destinations outside _internal/.
    This post-build step moves user-facing directories to the top level
    so they are easy to find and edit.
    """
    internal = app_dir / "_internal"
    for dirname in ("config", "dbc"):
        src = internal / dirname
        dest = app_dir / dirname
        if src.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.move(str(src), str(dest))
            print(f"Relocated {dirname}/ from _internal/ to app root")


def build(*, console: bool = False) -> None:
    """Assemble PyInstaller arguments and run the build.

    Parameters
    ----------
    console :
        If True, build with ``--console`` instead of ``--windowed`` so
        tracebacks are visible in a terminal.  Useful for debugging the
        frozen app.
    """
    import PyInstaller.__main__

    entry_script = str(_SCRIPT_DIR / "__main__.py")
    dist_dir = str(_PROJECT_ROOT / "dist")
    build_dir = str(_PROJECT_ROOT / "build")
    icon_path = _PROJECT_ROOT / "icon.ico"
    app_dir = _PROJECT_ROOT / "dist" / "pycanstreamviewer"

    version = __version__ or "0.0.0+dev"

    args = [
        entry_script,
        "--name", "pycanstreamviewer",
        "--noconfirm",
        "--onedir",
        "--distpath", dist_dir,
        "--workpath", build_dir,
        "--console" if console else "--windowed",
    ]

    if icon_path.is_file():
        args.extend(["--icon", str(icon_path)])

    args.extend(_build_data_file_args())
    args.extend(_build_metadata_args())
    args.extend(_build_collect_submodules_args())
    args.extend(_build_hidden_imports())

    print(f"Building pycanstreamviewer v{version}")
    print(f"Entry script: {entry_script}")
    print(f"Output: {app_dir}")

    PyInstaller.__main__.run(args)
    _relocate_data_dirs(app_dir)

    print("Build complete.")


def _parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the distribution build."""
    parser = argparse.ArgumentParser(
        description="Build a standalone pyCANstreamViewer executable.",
    )
    parser.add_argument(
        "--console",
        action="store_true",
        help="Build with a visible console window (for debugging the frozen app).",
    )
    return parser.parse_args()


def main() -> None:
    """Top-level entry point for the distribution build."""
    args = _parse_args()
    build(console=args.console)


if __name__ == "__main__":
    main()
