"""
Feature-flag interpretation helpers for vehicle overview extraction.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""


def wind_compensation_enabled_from_name(wcf_name: str | None) -> bool:
    """Interpret BARO_WCF_ENABLE enum text to whether compensation is active."""
    return wcf_name is not None and wcf_name.lower() not in ("disabled", "none")


def airspeed_use_enabled_from_name(use_name: str | None) -> bool:
    """Interpret ARSPD_USE/ARSPD2_USE enum text to whether the sensor is used."""
    return use_name in ("Use", "UseWhenZeroThrottle")
