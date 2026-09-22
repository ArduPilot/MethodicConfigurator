"""
Data model for assigning multicopter motor functions to servo outputs.

This file is part of ArduPilot Methodic Configurator.
https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Mapping
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_filesystem_json_with_schema import FilesystemJSONWithSchema
from ardupilot_methodic_configurator.data_model_parameter_editor import (
    InvalidParameterNameError,
    OperationNotPossibleError,
    ParameterValueUpdateStatus,
)

if TYPE_CHECKING:
    from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
    from ardupilot_methodic_configurator.data_model_parameter_editor import ParameterEditor


_OUTPUT_NUMBERS_BY_FIRST_CONNECTION_TYPE = {
    "Main Out": tuple(range(1, 15)),
    "AIO": (*range(9, 15), *range(1, 9)),
}

_NO_CHANGES_MESSAGE = _("All motor output functions are already assigned; no changes are needed.")


class ServoOutRecommendationStatus(str, Enum):
    """Semantic outcome of a servo-output recommendation or apply operation."""

    RECOMMENDATIONS_AVAILABLE = "recommendations_available"
    NO_CHANGES = "no_changes"
    UNASSIGNED_MOTORS = "unassigned_motors"
    ERROR = "error"
    APPLIED = "applied"


class ServoOutDataModel:
    """Propose motor-output assignments from vehicle component and frame data."""

    def __init__(self, local_filesystem: "LocalFilesystem", parameter_editor: "ParameterEditor") -> None:
        self._local_filesystem = local_filesystem
        self._parameter_editor = parameter_editor
        self._motor_data_loader = FilesystemJSONWithSchema(
            json_filename="AP_Motors_test.json",
            schema_filename=str(Path("plugins", "AP_Motors_test_schema.json")),
        )

    def get_recommendations(self) -> tuple[dict[str, int], str, ServoOutRecommendationStatus]:
        """Return motor assignments, a user message, and its semantic status."""
        output_numbers = _OUTPUT_NUMBERS_BY_FIRST_CONNECTION_TYPE.get(self._get_connection_type())
        if output_numbers is None:
            return (
                {},
                _("Select either Main Out or AIO as the FC-to-ESC connection type before assigning outputs."),
                ServoOutRecommendationStatus.ERROR,
            )

        frame_class = self._get_frame_class()
        motor_data = self._motor_data_loader.load_json_data(str(Path(__file__).parent))
        motor_numbers = self._motor_numbers_for_frame_class(frame_class, motor_data or {})
        if motor_numbers is None:
            return (
                {},
                _("FRAME_CLASS %(frame_class)s does not have a supported motor-output mapping.")
                % {"frame_class": frame_class},
                ServoOutRecommendationStatus.ERROR,
            )
        if len(motor_numbers) > len(output_numbers):
            return (
                {},
                _("FRAME_CLASS %(frame_class)s requires more outputs than this plugin can assign.")
                % {"frame_class": frame_class},
                ServoOutRecommendationStatus.ERROR,
            )

        existing = self._existing_function_values()
        recommendation_outputs = self._recommendation_outputs(frame_class, output_numbers)
        recommendations = self._recommend_assignments(recommendation_outputs, motor_numbers, existing)
        assigned_functions = {self._function_number(value) for value in existing.values()} | set(recommendations.values())

        unassigned_motor_numbers = [
            motor_number for motor_number in motor_numbers if self._motor_function(motor_number) not in assigned_functions
        ]
        unassigned_message = self._unassigned_motors_message(unassigned_motor_numbers) if unassigned_motor_numbers else ""
        if recommendations:
            message = self._recommended_message(
                len(recommendations), tricopter_yaw_servo=frame_class == 7 and 39 in recommendations.values()
            )
            if unassigned_message:
                message += f" {unassigned_message}"
            status = ServoOutRecommendationStatus.RECOMMENDATIONS_AVAILABLE
        elif unassigned_motor_numbers:
            message = unassigned_message
            status = ServoOutRecommendationStatus.UNASSIGNED_MOTORS
        else:
            message = _NO_CHANGES_MESSAGE
            status = ServoOutRecommendationStatus.NO_CHANGES
        return recommendations, message, status

    def _recommend_assignments(
        self, output_numbers: tuple[int, ...], motor_numbers: tuple[int, ...], existing: Mapping[str, object]
    ) -> dict[str, int]:
        """Pair missing motor functions with free outputs in connection order."""
        assigned_functions = {self._function_number(value) for value in existing.values()}
        free_output_numbers = [
            output_number for output_number in output_numbers if self._is_unset(existing.get(f"SERVO{output_number}_FUNCTION"))
        ]
        recommendations: dict[str, int] = {}
        for motor_number in motor_numbers:
            motor_function = self._motor_function(motor_number)
            if motor_function in assigned_functions:
                continue
            if not free_output_numbers:
                break
            output_number = free_output_numbers.pop(0)
            recommendations[f"SERVO{output_number}_FUNCTION"] = motor_function
            assigned_functions.add(motor_function)
        return recommendations

    def apply_recommendations(self) -> tuple[list[str], str, ServoOutRecommendationStatus]:
        """Add and set every currently-unset recommended assignment in the open step."""
        recommendations, recommendation_message, recommendation_status = self.get_recommendations()
        if not recommendations:
            return [], recommendation_message, recommendation_status

        recommendation_prefix = self._recommended_message(
            len(recommendations), tricopter_yaw_servo=self._get_frame_class() == 7 and 39 in recommendations.values()
        )
        unassigned_message = recommendation_message.removeprefix(recommendation_prefix).strip()

        applied: list[str] = []
        failed: list[str] = []
        for parameter_name, value in recommendations.items():
            if parameter_name not in self._parameter_editor.current_step_parameters:
                try:
                    if not self._parameter_editor.add_parameter_to_current_file(parameter_name):
                        failed.append(parameter_name)
                        continue
                except (InvalidParameterNameError, OperationNotPossibleError):
                    failed.append(parameter_name)
                    continue
            result = self._parameter_editor.update_parameter_value(parameter_name, str(value))
            if result.status in (ParameterValueUpdateStatus.UPDATED, ParameterValueUpdateStatus.UNCHANGED):
                applied.append(parameter_name)
            else:
                failed.append(parameter_name)

        if not applied:
            message = _("No servo output assignments could be applied.")
        else:
            message = _("Applied %(count)d motor output assignment(s).") % {"count": len(applied)}
        if failed:
            message += " " + _("Could not apply: %(parameters)s.") % {"parameters": ", ".join(failed)}
        if unassigned_message:
            message += " " + unassigned_message
        return applied, message, ServoOutRecommendationStatus.APPLIED if applied else ServoOutRecommendationStatus.ERROR

    def _get_connection_type(self) -> str:
        data = self._local_filesystem.vehicle_components_fs.data or {}
        components = data.get("Components", {}) if isinstance(data, dict) else {}
        esc = components.get("ESC", {}) if isinstance(components, dict) else {}
        connection = esc.get("FC->ESC Connection", {}) if isinstance(esc, dict) else {}
        return str(connection.get("Type", "")) if isinstance(connection, dict) else ""

    def _get_frame_class(self) -> int:
        raw_value: object = self._parameter_editor.fc_parameters.get("FRAME_CLASS")
        if raw_value is None:
            raw_value = self._parameter_editor.fc_parameters.get("Q_FRAME_CLASS", 0)
        staged_parameter = self._parameter_editor.current_step_parameters.get("FRAME_CLASS")
        if staged_parameter is not None and self._function_number(staged_parameter.get_new_value()):
            raw_value = staged_parameter.get_new_value()
        if not isinstance(raw_value, (int, float, str)):
            return 0
        try:
            return int(raw_value)
        except (ValueError, OverflowError):
            return 0

    def _existing_function_values(self) -> Mapping[str, object]:
        existing = {
            name: value
            for name, value in self._parameter_editor.fc_parameters.items()
            if name.startswith("SERVO") and name.endswith("_FUNCTION")
        }
        existing.update(
            {
                name: parameter.get_new_value()
                for name, parameter in self._parameter_editor.current_step_parameters.items()
                if name.startswith("SERVO") and name.endswith("_FUNCTION")
            }
        )
        return existing

    @staticmethod
    def _motor_numbers_for_frame_class(frame_class: int, motor_data: Mapping[str, object]) -> tuple[int, ...] | None:
        """
        Return motor numbers from the first valid layout for ``frame_class``.

        Layouts sharing a frame class vary by frame type and geometry, but use the
        same motor-number set. This plugin only needs those numbers to derive
        ``SERVOx_FUNCTION`` values, so the first valid layout is sufficient.
        """
        layouts = motor_data.get("layouts", [])
        if not isinstance(layouts, list):
            return None
        for layout in layouts:
            if not isinstance(layout, Mapping) or layout.get("Class") != frame_class:
                continue
            motors = layout.get("motors")
            if not isinstance(motors, list):
                continue
            if not motors:
                continue
            motor_numbers: list[int] = []
            for motor in motors:
                if not isinstance(motor, Mapping):
                    break
                number = motor.get("Number")
                if not isinstance(number, int):
                    break
                motor_numbers.append(number)
            else:
                return tuple(motor_numbers)
        return None

    @staticmethod
    def _recommendation_outputs(frame_class: int, output_numbers: tuple[int, ...]) -> tuple[int, ...]:
        """Return output order, keeping a tricopter's yaw servo outside the ESC bank."""
        if frame_class != 7 or 7 not in output_numbers:
            return output_numbers
        return (*output_numbers[:3], 7)

    @staticmethod
    def _motor_function(motor_number: int) -> int:
        """Translate an ArduPilot motor number to its SERVOx_FUNCTION value."""
        if motor_number <= 8:
            return 32 + motor_number
        if motor_number <= 12:
            return 73 + motor_number
        return 147 + motor_number

    @staticmethod
    def _unassigned_motors_message(motor_numbers: list[int]) -> str:
        """Build a localized message for motors that are not routed to an output."""
        if len(motor_numbers) == 1:
            return _("Motor%(number)d is not assigned to any output.") % {"number": motor_numbers[0]}
        names = ", ".join(f"Motor{number}" for number in motor_numbers)
        return _("%(motors)s are not assigned to any output.") % {"motors": names}

    @staticmethod
    def _recommended_message(count: int, tricopter_yaw_servo: bool = False) -> str:
        """Build the localized message prefix used for proposed assignments."""
        message = _("Recommended %(count)d motor output assignment(s).") % {"count": count}
        if tricopter_yaw_servo:
            message += " " + _("SERVO7 is the tricopter yaw servo; connect it to a servo, not an ESC.")
        return message

    @staticmethod
    def _function_number(value: object) -> int | None:
        """Convert a configured function value to an integer when possible."""
        if not isinstance(value, (int, float, str)):
            return None
        try:
            numeric_value = float(value)
        except (ValueError, OverflowError):
            return None
        return int(numeric_value) if numeric_value.is_integer() else None

    @staticmethod
    def _is_unset(value: object) -> bool:
        if value is None or value == "":
            return True
        if not isinstance(value, (int, float, str)):
            return False
        try:
            return float(value) == 0
        except (ValueError, OverflowError):
            return False
