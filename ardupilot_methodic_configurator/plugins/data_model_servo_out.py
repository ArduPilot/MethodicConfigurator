"""
Data model for assigning multicopter motor functions to servo outputs.

This file is part of ArduPilot Methodic Configurator.
https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_filesystem_json_with_schema import FilesystemJSONWithSchema
from ardupilot_methodic_configurator.data_model_parameter_editor import (
    InvalidParameterNameError,
    OperationNotPossibleError,
)
from ardupilot_methodic_configurator.plugins.data_model_esc_rpm_scale import EscRpmScaleDataModel

if TYPE_CHECKING:
    from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
    from ardupilot_methodic_configurator.data_model_parameter_editor import ParameterEditor


_SERVO_FUNCTION_MOTOR_1 = 33
_OUTPUT_NUMBERS_BY_FIRST_CONNECTION_TYPE = {
    "Main Out": (*range(1, 9), *range(9, 15)),
    "AIO": (*range(9, 15), *range(1, 9)),
}


class ServoOutDataModel:
    """Propose motor-output assignments from vehicle component and frame data."""

    def __init__(self, local_filesystem: "LocalFilesystem", parameter_editor: "ParameterEditor") -> None:
        self._local_filesystem = local_filesystem
        self._parameter_editor = parameter_editor
        self._motor_data_loader = FilesystemJSONWithSchema(
            json_filename="AP_Motors_test.json",
            schema_filename=str(Path("plugins", "AP_Motors_test_schema.json")),
        )

    def get_recommendations(self) -> tuple[dict[str, int], str]:
        """Return disabled/missing motor assignments and a message suitable for the UI."""
        connection_type = self._get_connection_type()
        output_numbers = _OUTPUT_NUMBERS_BY_FIRST_CONNECTION_TYPE.get(connection_type)
        if output_numbers is None:
            return {}, _("Select either Main Out or AIO as the FC-to-ESC connection type before assigning outputs.")

        frame_class = self._get_frame_class()
        motor_data = self._motor_data_loader.load_json_data(str(Path(__file__).parent))
        motor_count = EscRpmScaleDataModel.esc_count_for_frame_class(frame_class, motor_data or {})
        if motor_count is None:
            return {}, _("FRAME_CLASS %(frame_class)s does not have a supported motor-output mapping.") % {
                "frame_class": frame_class
            }
        if motor_count > len(output_numbers):
            return {}, _("FRAME_CLASS %(frame_class)s requires more outputs than this plugin can assign.") % {
                "frame_class": frame_class
            }

        existing = self._existing_function_values()
        recommendations: dict[str, int] = {}
        for motor_index, output_number in enumerate(output_numbers[:motor_count]):
            parameter_name = f"SERVO{output_number}_FUNCTION"
            if self._is_unset(existing.get(parameter_name)):
                recommendations[parameter_name] = _SERVO_FUNCTION_MOTOR_1 + motor_index

        if not recommendations:
            return {}, _("All motor output functions are already assigned; no changes are needed.")
        return recommendations, _("Recommended %(count)d motor output assignment(s).") % {"count": len(recommendations)}

    def apply_recommendations(self) -> tuple[list[str], str]:
        """Add and set every currently-unset recommended assignment in the open step."""
        recommendations, message = self.get_recommendations()
        if not recommendations:
            return [], message

        applied: list[str] = []
        for parameter_name, value in recommendations.items():
            if parameter_name not in self._parameter_editor.current_step_parameters:
                try:
                    if not self._parameter_editor.add_parameter_to_current_file(parameter_name):
                        continue
                except (InvalidParameterNameError, OperationNotPossibleError):
                    continue
            result = self._parameter_editor.update_parameter_value(parameter_name, str(value))
            if result.status.name in {"UPDATED", "UNCHANGED"}:
                applied.append(parameter_name)

        if not applied:
            return [], _("No servo output assignments could be applied.")
        return applied, _("Applied %(count)d motor output assignment(s).") % {"count": len(applied)}

    def _get_connection_type(self) -> str:
        data = self._local_filesystem.vehicle_components_fs.data or {}
        components = data.get("Components", {}) if isinstance(data, dict) else {}
        esc = components.get("ESC", {}) if isinstance(components, dict) else {}
        connection = esc.get("FC->ESC Connection", {}) if isinstance(esc, dict) else {}
        return str(connection.get("Type", "")) if isinstance(connection, dict) else ""

    def _get_frame_class(self) -> int:
        raw_value: object = self._parameter_editor.fc_parameters.get("FRAME_CLASS", 0)
        try:
            return int(raw_value)
        except (TypeError, ValueError):
            return 0

    def _existing_function_values(self) -> Mapping[str, object]:
        return {
            name: parameter.new_value
            for name, parameter in self._parameter_editor.current_step_parameters.items()
            if name.startswith("SERVO") and name.endswith("_FUNCTION")
        }

    @staticmethod
    def _is_unset(value: object) -> bool:
        if value is None or value == "":
            return True
        try:
            return float(value) == 0
        except (TypeError, ValueError):
            return False
