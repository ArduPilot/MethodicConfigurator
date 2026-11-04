"""
Dispatch Windows frozen executables to their project script entry points.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

# ruff: noqa: INP001

import importlib
import json
import os
import sys
from pathlib import Path

import argcomplete

from ardupilot_methodic_configurator.backend_bin_log_validation import validate_bin_log


def main() -> None:
    """Run the selected command and provide completion before starting its UI."""
    if len(sys.argv) == 3 and sys.argv[1] == "--validate-bin-log":
        validate_bin_log(sys.argv[2])
        return

    bundle_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    scripts = json.loads((bundle_dir / "project_scripts.json").read_text(encoding="utf-8"))
    command = "ardupilot_methodic_configurator"
    if sys.argv[1:2] == ["--_project-script"]:
        if len(sys.argv) < 3:
            message = "Missing project script name"
            raise SystemExit(message)
        command = sys.argv[2]
        del sys.argv[1:3]
        sys.argv[0] = command

    entry = scripts.get(command)
    if entry is None:
        message = f"Unknown project script: {command}"
        raise SystemExit(message)
    module_name, function_name = entry.split(":", 1)
    module = importlib.import_module(module_name)
    if os.environ.get("_ARGCOMPLETE") and command != "ardupilot_methodic_configurator":
        argcomplete.autocomplete(module.create_argument_parser())
    getattr(module, function_name)()


if __name__ == "__main__":
    main()
