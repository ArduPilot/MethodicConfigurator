"""
Validate DataFlash logs in an isolated process without loading the GUI.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""


def validate_bin_log(logfile: str) -> None:
    """Validate a log and report invalid input without a traceback."""
    from pymavlink import mavutil  # noqa: PLC0415  # pylint: disable=import-outside-toplevel

    try:
        mlog = mavutil.mavlink_connection(logfile)
        close_method = getattr(mlog, "close", None)
        if callable(close_method):
            close_method()
    except (OSError, ValueError, SystemExit) as error:
        raise SystemExit(str(error)) from None
