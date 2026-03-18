"""Ensure the backend can be executed as a script without import errors."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


def test_main_module_runs_as_script_without_import_error():
    main_path = Path(__file__).resolve().parents[1] / "app" / "main.py"
    backend_root = main_path.parent.parent
    app_dir = main_path.parent

    original_sys_path = sys.path.copy()
    try:
        sys.path = [str(app_dir)] + [
            path
            for path in original_sys_path
            if Path(path).resolve() not in {backend_root, app_dir}
        ]
        runpy.run_path(str(main_path), run_name="__main__")
    finally:
        sys.path = original_sys_path
