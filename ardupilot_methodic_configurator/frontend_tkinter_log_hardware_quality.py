"""
Hardware overview tab for the ArduPilot Methodic Configurator log quality report window.

Displays IMU, compass, barometer, and airspeed sensor identity and health
extracted from a parsed ArduPilot .bin log file.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from tkinter import ttk

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.frontend_tkinter_scroll_frame import ScrollFrame
from ardupilot_methodic_configurator.log_analysis.data_model_vehicle_overview import (
    AirspeedInfo,
    BaroInfo,
    CompassInfo,
    HardwareReport,
    ImuInfo,
)


def _clean_devtype(name: str | None) -> str:
    """Strip DEVTYPE_ prefix and category prefix from device type names."""
    if not name or name == "Unknown":
        return "-"
    for prefix in ("DEVTYPE_INS_", "DEVTYPE_BARO_", "DEVTYPE_AIRSPEED_", "DEVTYPE_"):
        if name.startswith(prefix):
            return name[len(prefix) :]
    return name


def _fmt_val(val: object) -> str:
    """Format values — replace None or unknown strings with a dash."""
    if val is None:
        return "-"
    s = str(val)
    return "-" if s in ("Unknown", "None", "") else s


def _add_kv(parent: ttk.Frame, key: str, value: str) -> None:
    """Pack a key-value pair inside a hardware card."""
    row = ttk.Frame(parent)
    row.pack(fill=tk.X, padx=10, pady=3)
    ttk.Label(row, text=key, foreground="gray", font=("TkDefaultFont", 11), width=18).pack(side=tk.LEFT)
    ttk.Label(row, text=value, font=("TkDefaultFont", 11, "bold")).pack(side=tk.LEFT, fill=tk.X, expand=True)


def _build_imu_cards(parent: ttk.Frame, imus: list[ImuInfo]) -> None:
    ttk.Label(parent, text=_("IMUs"), font=("TkDefaultFont", 13, "bold")).pack(anchor=tk.W, padx=14, pady=(16, 6))
    for imu in imus:
        card = ttk.LabelFrame(parent, text=f"IMU {imu.instance}")
        card.pack(side=tk.TOP, fill=tk.X, padx=14, pady=6)
        col1 = ttk.Frame(card)
        col1.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4, pady=4)
        col2 = ttk.Frame(card)
        col2.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4, pady=4)
        _add_kv(col1, _("Accel:"), _clean_devtype(imu.accel_name))
        _add_kv(col1, _("Gyro:"), _clean_devtype(imu.gyro_name))
        _add_kv(col1, _("Bus type:"), _fmt_val(imu.accel_bus_type))
        _add_kv(col1, _("Accel ok:"), _fmt_val(imu.accel_healthy))
        _add_kv(col2, _("Accel cal:"), _fmt_val(imu.accel_calibrated))
        _add_kv(col2, _("Gyro cal:"), _fmt_val(imu.gyro_calibrated))
        _add_kv(col2, _("Temp cal:"), _fmt_val(imu.accel_temp_calibrated))
        _add_kv(col2, _("Gyro ok:"), _fmt_val(imu.gyro_healthy))


def _build_compass_cards(parent: ttk.Frame, compasses: list[CompassInfo]) -> None:
    ttk.Label(parent, text=_("Compasses"), font=("TkDefaultFont", 13, "bold")).pack(anchor=tk.W, padx=14, pady=(18, 6))
    for compass in compasses:
        card = ttk.LabelFrame(parent, text=f"Compass {compass.instance}")
        card.pack(side=tk.TOP, fill=tk.X, padx=14, pady=6)
        col1 = ttk.Frame(card)
        col1.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4, pady=4)
        col2 = ttk.Frame(card)
        col2.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4, pady=4)
        _add_kv(col1, _("Chip:"), _clean_devtype(compass.name))
        _add_kv(col1, _("Bus type:"), _fmt_val(compass.bus_type))
        _add_kv(col1, _("External:"), _fmt_val(compass.external))
        _add_kv(col2, _("Calibrated:"), _fmt_val(compass.calibrated))
        _add_kv(col2, _("Motor cal:"), _fmt_val(compass.motor_calibrated))
        _add_kv(col2, _("Healthy:"), _fmt_val(compass.healthy))


def _build_baro_cards(parent: ttk.Frame, baros: list[BaroInfo]) -> None:
    ttk.Label(parent, text=_("Barometers"), font=("TkDefaultFont", 13, "bold")).pack(anchor=tk.W, padx=14, pady=(18, 6))
    for baro in baros:
        card = ttk.LabelFrame(parent, text=f"Baro {baro.instance}")
        card.pack(side=tk.TOP, fill=tk.X, padx=14, pady=6)
        col1 = ttk.Frame(card)
        col1.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4, pady=4)
        col2 = ttk.Frame(card)
        col2.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4, pady=4)
        _add_kv(col1, _("Chip:"), _clean_devtype(baro.name))
        _add_kv(col1, _("Bus type:"), _fmt_val(baro.bus_type))
        _add_kv(col2, _("Wind comp:"), _fmt_val(baro.wind_compensation))
        _add_kv(col2, _("Healthy:"), _fmt_val(baro.healthy))


def _build_airspeed_cards(parent: ttk.Frame, airspeeds: list[AirspeedInfo]) -> None:
    ttk.Label(parent, text=_("Airspeed sensors"), font=("TkDefaultFont", 13, "bold")).pack(anchor=tk.W, padx=14, pady=(18, 6))
    for arspd in airspeeds:
        card = ttk.LabelFrame(parent, text=f"Airspeed {arspd.instance}")
        card.pack(side=tk.TOP, fill=tk.X, padx=14, pady=6)
        col1 = ttk.Frame(card)
        col1.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4, pady=4)
        _add_kv(col1, _("Type:"), _fmt_val(arspd.sensor_type))
        _add_kv(col1, _("In use:"), _fmt_val(arspd.use))
        _add_kv(col1, _("Healthy:"), _fmt_val(arspd.healthy))


def build_hardware_tab(parent: ttk.Frame, hw: HardwareReport | None) -> None:
    """Build the hardware overview tab content into the given parent frame."""
    if hw is None:
        ttk.Label(parent, text=_("No hardware data available"), foreground="gray").pack(padx=24, pady=24)
        return

    scroll_container = ScrollFrame(parent)
    scroll_container.pack(fill=tk.BOTH, expand=True)
    inner = scroll_container.view_port

    if hw.imus:
        _build_imu_cards(inner, hw.imus)
    if hw.compasses:
        _build_compass_cards(inner, hw.compasses)
    if hw.baros:
        _build_baro_cards(inner, hw.baros)
    if hw.airspeed_sensors:
        _build_airspeed_cards(inner, hw.airspeed_sensors)
