"""Ensure the backend can be executed as a script without import errors."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


def test_main_script_execution():
    script_path = Path(__file__).resolve().parents[1] / "app" / "main.py"
    backend_root = script_path.parent.parent.resolve()
    app_dir = script_path.parent.resolve()

    original_sys_path = sys.path.copy()
    try:
        sys.path = [
            str(app_dir),
            *[path for path in original_sys_path if Path(path).resolve() != backend_root],
        ]
        runpy.run_path(str(script_path), run_name="__main__")
    finally:
        sys.path = original_sys_path
