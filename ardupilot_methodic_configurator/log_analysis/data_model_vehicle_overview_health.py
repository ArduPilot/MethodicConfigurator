"""
Health extraction helpers for vehicle overview.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-FileCopyrightText: 2026 Omkar Sarkar <omkarsarkar24@gmail.com>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from ardupilot_methodic_configurator.log_analysis.data_model_log_data import LogData


def instance_health_from_message_field(
    log_data: LogData,
    message_name: str,
    instance: int,
    health_field: str,
) -> bool | None:
    """Return health for one message instance, where 0 means unhealthy and non-zero means healthy."""
    columns = log_data.get_message_columns(message_name)
    names = columns.dtype.names if columns is not None else None
    if columns is None or columns.size == 0 or names is None:
        return None
    if "I" not in names or health_field not in names:
        return None

    instance_numbers = log_data.get_field(message_name, "I")
    mask = instance_numbers == (instance - 1)
    if not mask.any():
        return None

    health_values = log_data.get_field(message_name, health_field)[mask]
    return bool((health_values == 0).sum() == 0)
