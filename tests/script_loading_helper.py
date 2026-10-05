#!/usr/bin/env python3

"""
Load standalone repository scripts for tests without sharing mutable module state.

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import importlib.util
from pathlib import Path
from types import ModuleType


def load_script_module(script_path: Path) -> ModuleType:
    """Execute a standalone Python script in a fresh module on every call."""
    spec = importlib.util.spec_from_file_location(script_path.stem, script_path)
    if spec is None or spec.loader is None:
        message = f"Cannot load a Python script from {script_path}"
        raise ImportError(message)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
