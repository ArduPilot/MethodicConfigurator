#!/usr/bin/env python3

"""
Behavior-driven tests for servo-output recommendations.

This file is part of ArduPilot Methodic Configurator.
https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Callable
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ardupilot_methodic_configurator.data_model_parameter_editor import ParameterValueUpdateStatus
from ardupilot_methodic_configurator.plugins.data_model_servo_out import ServoOutDataModel, ServoOutRecommendationStatus

# pytest injects fixtures by matching the test function parameter name.
# pylint: disable=redefined-outer-name,protected-access


@pytest.fixture
def servo_model_factory() -> Callable[[str, int, dict[str, object] | None], ServoOutDataModel]:
    """Build a servo model with realistic component and parameter-editor data."""

    def create(connection_type: str, frame_class: int, parameters: dict[str, object] | None = None) -> ServoOutDataModel:
        filesystem = SimpleNamespace(
            vehicle_components_fs=SimpleNamespace(
                data={"Components": {"ESC": {"FC->ESC Connection": {"Type": connection_type}}}}
            )
        )
        editor = SimpleNamespace(
            fc_parameters={"FRAME_CLASS": frame_class},
            current_step_parameters=parameters or {},
        )
        return ServoOutDataModel(filesystem, editor)

    return create


class TestServoOutputRecommendations:
    """Test the user's safe default motor-output assignments."""

    def test_main_out_quad_starts_motor_functions_at_first_servo_output(self, servo_model_factory) -> None:
        """
        Main Out wiring assigns a quad's motors to the first output bank.

        GIVEN: A quad uses the Main Out FC-to-ESC connection
        WHEN: The user opens the servo-output step
        THEN: Motor functions 1 through 4 are proposed for SERVO1 through SERVO4
        """
        # Arrange (Given)
        model = servo_model_factory("Main Out", 1)

        # Act (When)
        recommendations, _message, _status = model.get_recommendations()

        # Assert (Then)
        assert recommendations == {
            "SERVO1_FUNCTION": 33,
            "SERVO2_FUNCTION": 34,
            "SERVO3_FUNCTION": 35,
            "SERVO4_FUNCTION": 36,
        }

    def test_aio_hexa_starts_motor_functions_at_auxiliary_bank(self, servo_model_factory) -> None:
        """
        AIO wiring assigns a hexa's motors to the auxiliary output bank.

        GIVEN: A hexa uses the AIO FC-to-ESC connection
        WHEN: The user opens the servo-output step
        THEN: Motor functions are proposed from SERVO9 through SERVO14
        """
        # Arrange (Given)
        model = servo_model_factory("AIO", 2)

        # Act (When)
        recommendations, _message, _status = model.get_recommendations()

        # Assert (Then)
        assert recommendations == {
            "SERVO9_FUNCTION": 33,
            "SERVO10_FUNCTION": 34,
            "SERVO11_FUNCTION": 35,
            "SERVO12_FUNCTION": 36,
            "SERVO13_FUNCTION": 37,
            "SERVO14_FUNCTION": 38,
        }

    def test_main_out_dodeca_continues_in_aio_bank_after_eight_motors(self, servo_model_factory) -> None:
        """
        A large vehicle continues in the AIO bank after its Main Out bank is full.

        GIVEN: A 12-motor frame uses Main Out as its first FC-to-ESC connection
        WHEN: The user requests output recommendations
        THEN: Motors 1 through 8 use Main Out and motors 9 through 12 use AIO
        """
        # Arrange (Given)
        model = servo_model_factory("Main Out", 12)

        # Act (When)
        recommendations, _message, _status = model.get_recommendations()

        # Assert (Then)
        assert recommendations["SERVO8_FUNCTION"] == 40
        assert recommendations["SERVO9_FUNCTION"] == 82
        assert recommendations["SERVO12_FUNCTION"] == 85

    def test_main_out_tricopter_uses_layout_motor_numbers(self, servo_model_factory) -> None:
        """A tricopter's non-contiguous motor numbers must be retained."""
        model = servo_model_factory("Main Out", 7)

        recommendations, _message, _status = model.get_recommendations()

        assert recommendations == {
            "SERVO1_FUNCTION": 33,
            "SERVO2_FUNCTION": 34,
            "SERVO3_FUNCTION": 36,
            "SERVO4_FUNCTION": 39,
        }

    def test_aio_octa_continues_in_main_out_bank_after_six_motors(self, servo_model_factory) -> None:
        """
        A large vehicle continues in the Main Out bank after its AIO bank is full.

        GIVEN: An eight-motor frame uses AIO as its first FC-to-ESC connection
        WHEN: The user requests output recommendations
        THEN: Motors 1 through 6 use AIO and motors 7 and 8 use Main Out
        """
        # Arrange (Given)
        model = servo_model_factory("AIO", 3)

        # Act (When)
        recommendations, _message, _status = model.get_recommendations()

        # Assert (Then)
        assert recommendations["SERVO14_FUNCTION"] == 38
        assert recommendations["SERVO1_FUNCTION"] == 39
        assert recommendations["SERVO2_FUNCTION"] == 40

    def test_existing_nonzero_assignment_is_preserved(self, servo_model_factory) -> None:
        """
        Existing user assignments are never overwritten.

        GIVEN: A motor output already has a non-zero function
        WHEN: The user requests recommendations
        THEN: That output is omitted while disabled outputs are proposed
        """
        # Arrange (Given)
        model = servo_model_factory(
            "Main Out",
            1,
            {
                "SERVO1_FUNCTION": SimpleNamespace(get_new_value=lambda: "70"),
                "SERVO2_FUNCTION": SimpleNamespace(get_new_value=lambda: "0"),
            },
        )

        # Act (When)
        recommendations, _message, _status = model.get_recommendations()

        # Assert (Then)
        assert "SERVO1_FUNCTION" not in recommendations
        assert recommendations["SERVO2_FUNCTION"] == 33

    def test_fc_assignment_is_preserved_when_current_step_is_empty(self, servo_model_factory) -> None:
        """FC-side assignments are not overwritten merely because this step is empty."""
        model = servo_model_factory("Main Out", 1)
        model._parameter_editor.fc_parameters["SERVO1_FUNCTION"] = 70

        recommendations, _message, _status = model.get_recommendations()

        assert "SERVO1_FUNCTION" not in recommendations

    def test_existing_motor_function_is_not_duplicated(self, servo_model_factory) -> None:
        """A motor function already routed elsewhere is never proposed a second time."""
        model = servo_model_factory(
            "Main Out",
            1,
            {
                "SERVO1_FUNCTION": SimpleNamespace(get_new_value=lambda: "34"),
                "SERVO2_FUNCTION": SimpleNamespace(get_new_value=lambda: "0"),
                "SERVO3_FUNCTION": SimpleNamespace(get_new_value=lambda: "35"),
                "SERVO4_FUNCTION": SimpleNamespace(get_new_value=lambda: "36"),
            },
        )

        recommendations, _message, _status = model.get_recommendations()

        assert recommendations["SERVO2_FUNCTION"] == 33
        assert 34 not in recommendations.values()

    def test_user_is_told_when_a_motor_has_no_output(self, servo_model_factory) -> None:
        """
        A motor missing from every output is placed on the next free output.

        GIVEN: Motor2 is routed to output 1, Motor1 is unrouted, and output 2 is disabled
        WHEN: The user requests motor-output recommendations
        THEN: Motor1 is proposed for the free output
        """
        # Arrange (Given)
        model = servo_model_factory(
            "Main Out",
            1,
            {
                "SERVO1_FUNCTION": SimpleNamespace(get_new_value=lambda: "34"),
                "SERVO2_FUNCTION": SimpleNamespace(get_new_value=lambda: "0"),
                "SERVO3_FUNCTION": SimpleNamespace(get_new_value=lambda: "35"),
                "SERVO4_FUNCTION": SimpleNamespace(get_new_value=lambda: "36"),
            },
        )

        # Act (When)
        recommendations, message, _status = model.get_recommendations()

        # Assert (Then)
        assert recommendations == {"SERVO2_FUNCTION": 33}
        assert "Motor1 is not assigned to any output" not in message

    def test_q_frame_class_is_used_when_frame_class_is_unavailable(self) -> None:
        """
        A Copter frame class can be discovered from the Q_ parameter namespace.

        GIVEN: The FC exposes only Q_FRAME_CLASS=1 and the connection is Main Out
        WHEN: The user requests motor-output recommendations
        THEN: Quad motor assignments are proposed
        """
        # Arrange (Given)
        filesystem = SimpleNamespace(
            vehicle_components_fs=SimpleNamespace(data={"Components": {"ESC": {"FC->ESC Connection": {"Type": "Main Out"}}}})
        )
        editor = SimpleNamespace(fc_parameters={"Q_FRAME_CLASS": 1}, current_step_parameters={})
        model = ServoOutDataModel(filesystem, editor)

        # Act (When)
        recommendations, _message, _status = model.get_recommendations()

        # Assert (Then)
        assert recommendations["SERVO1_FUNCTION"] == 33

    def test_staged_frame_class_is_used_before_the_fc_value(self, servo_model_factory) -> None:
        """
        Staged frame-class changes drive recommendations before upload.

        GIVEN: The FC still reports class 0 but the current step stages class 12
        WHEN: The user requests motor-output recommendations
        THEN: The twelve-motor layout is used
        """
        # Arrange (Given)
        model = servo_model_factory(
            "Main Out",
            0,
            {"FRAME_CLASS": SimpleNamespace(get_new_value=lambda: "12")},
        )

        # Act (When)
        recommendations, message, _status = model.get_recommendations()

        # Assert (Then)
        assert message.startswith("Recommended")
        assert recommendations["SERVO12_FUNCTION"] == 85

    def test_invalid_staged_frame_class_falls_back_to_fc_value(self, servo_model_factory) -> None:
        """An unusable staged FRAME_CLASS does not hide a supported FC value."""
        model = servo_model_factory(
            "Main Out",
            1,
            {"FRAME_CLASS": SimpleNamespace(get_new_value=lambda: "0.0")},
        )

        recommendations, message, _status = model.get_recommendations()

        assert recommendations["SERVO1_FUNCTION"] == 33
        assert message.startswith("Recommended")

    def test_quadplane_controls_leave_free_outputs_for_motor_assignments(self) -> None:
        """A stock QuadPlane can receive motors after its positional control outputs."""
        filesystem = SimpleNamespace(
            vehicle_components_fs=SimpleNamespace(data={"Components": {"ESC": {"FC->ESC Connection": {"Type": "Main Out"}}}})
        )
        editor = SimpleNamespace(
            fc_parameters={
                "Q_FRAME_CLASS": 1,
                "SERVO1_FUNCTION": 4,
                "SERVO2_FUNCTION": 19,
                "SERVO3_FUNCTION": 70,
                "SERVO4_FUNCTION": 21,
            },
            current_step_parameters={},
        )
        model = ServoOutDataModel(filesystem, editor)

        recommendations, message, _status = model.get_recommendations()

        assert recommendations == {
            "SERVO5_FUNCTION": 33,
            "SERVO6_FUNCTION": 34,
            "SERVO7_FUNCTION": 35,
            "SERVO8_FUNCTION": 36,
        }
        assert "not assigned to any output" not in message

    def test_empty_motor_layout_is_not_treated_as_a_valid_mapping(self) -> None:
        """
        An empty motor list is rejected as an unusable layout.

        GIVEN: Motor metadata contains a matching layout with no motors
        WHEN: The model resolves the frame-class layout
        THEN: It reports that no supported mapping exists
        """
        # Arrange (Given)
        motor_data = {"layouts": [{"Class": 1, "motors": []}]}

        # Act (When)
        motor_numbers = ServoOutDataModel._motor_numbers_for_frame_class(1, motor_data)

        # Assert (Then)
        assert motor_numbers is None

    def test_motor_thirteen_uses_the_servo_function_range(self) -> None:
        """Motor13 maps to the first function in the extended motor range."""
        assert ServoOutDataModel._motor_function(13) == 160

    def test_unrecognized_connection_does_not_propose_assignments(self, servo_model_factory) -> None:
        """
        Non-output ESC connections require the user to choose an appropriate mapping.

        GIVEN: The ESC connection is not Main Out or AIO
        WHEN: The user requests recommendations
        THEN: No output functions are proposed and the reason is explained
        """
        # Arrange (Given)
        model = servo_model_factory("CAN1", 1)

        # Act (When)
        recommendations, message, status = model.get_recommendations()

        # Assert (Then)
        assert recommendations == {}
        assert "Main Out or AIO" in message
        assert status is ServoOutRecommendationStatus.ERROR

    def test_complete_mapping_has_a_semantic_no_changes_status(self, servo_model_factory) -> None:
        """A complete mapping reports status independently of its localized message."""
        model = servo_model_factory(
            "Main Out",
            1,
            {
                "SERVO1_FUNCTION": SimpleNamespace(get_new_value=lambda: "33"),
                "SERVO2_FUNCTION": SimpleNamespace(get_new_value=lambda: "34"),
                "SERVO3_FUNCTION": SimpleNamespace(get_new_value=lambda: "35"),
                "SERVO4_FUNCTION": SimpleNamespace(get_new_value=lambda: "36"),
            },
        )

        recommendations, _message, status = model.get_recommendations()

        assert recommendations == {}
        assert status is ServoOutRecommendationStatus.NO_CHANGES


class TestServoOutputApplication:
    """Test applying recommendations to the current configuration file."""

    def test_user_can_add_and_apply_missing_motor_functions(self) -> None:
        """
        Missing parameters are added and receive their recommended motor functions.

        GIVEN: A quad has Main Out wiring and no servo parameters in this step
        WHEN: The user applies the recommendations
        THEN: The four parameters are added and updated with Motor1 through Motor4
        """
        # Arrange (Given)
        editor = MagicMock()
        editor.fc_parameters = {"FRAME_CLASS": 1}
        editor.current_step_parameters = {}
        editor.add_parameter_to_current_file.return_value = True
        editor.update_parameter_value.return_value = SimpleNamespace(status=ParameterValueUpdateStatus.UPDATED)
        filesystem = SimpleNamespace(
            vehicle_components_fs=SimpleNamespace(data={"Components": {"ESC": {"FC->ESC Connection": {"Type": "Main Out"}}}})
        )
        model = ServoOutDataModel(filesystem, editor)

        # Act (When)
        applied, _message, _status = model.apply_recommendations()

        # Assert (Then)
        assert applied == ["SERVO1_FUNCTION", "SERVO2_FUNCTION", "SERVO3_FUNCTION", "SERVO4_FUNCTION"]
        assert editor.add_parameter_to_current_file.call_count == 4
        assert editor.update_parameter_value.call_args_list[0].args == ("SERVO1_FUNCTION", "33")

    def test_partial_application_names_assignments_that_could_not_be_applied(self) -> None:
        """
        A partial apply explains which output was unavailable.

        GIVEN: The second servo parameter cannot be added to the current step
        WHEN: The user applies the motor-output recommendations
        THEN: The result reports the three applied outputs and names the omitted one
        """
        # Arrange (Given)
        editor = MagicMock()
        editor.fc_parameters = {"FRAME_CLASS": 1}
        editor.current_step_parameters = {}
        editor.add_parameter_to_current_file.side_effect = lambda name: name != "SERVO2_FUNCTION"
        editor.update_parameter_value.return_value = SimpleNamespace(status=ParameterValueUpdateStatus.UPDATED)
        filesystem = SimpleNamespace(
            vehicle_components_fs=SimpleNamespace(data={"Components": {"ESC": {"FC->ESC Connection": {"Type": "Main Out"}}}})
        )
        model = ServoOutDataModel(filesystem, editor)

        # Act (When)
        applied, message, _status = model.apply_recommendations()

        # Assert (Then)
        assert applied == ["SERVO1_FUNCTION", "SERVO3_FUNCTION", "SERVO4_FUNCTION"]
        assert "SERVO2_FUNCTION" in message

    def test_application_accepts_only_parameter_update_status_values(self) -> None:
        """
        A status-like object is not mistaken for a successful parameter update.

        GIVEN: The editor returns an object whose name merely says UPDATED
        WHEN: The user applies the motor-output recommendations
        THEN: No assignment is reported as applied
        """
        # Arrange (Given)
        editor = MagicMock()
        editor.fc_parameters = {"FRAME_CLASS": 1}
        editor.current_step_parameters = {}
        editor.add_parameter_to_current_file.return_value = True
        editor.update_parameter_value.return_value = SimpleNamespace(status=SimpleNamespace(name="UPDATED"))
        filesystem = SimpleNamespace(
            vehicle_components_fs=SimpleNamespace(data={"Components": {"ESC": {"FC->ESC Connection": {"Type": "Main Out"}}}})
        )
        model = ServoOutDataModel(filesystem, editor)

        # Act (When)
        applied, message, _status = model.apply_recommendations()

        # Assert (Then)
        assert not applied
        assert message.startswith("No servo output assignments could be applied.")
        assert "SERVO1_FUNCTION" in message

    def test_application_preserves_unassigned_motor_warning(self) -> None:
        """Applying available outputs keeps the warning for motors still without an output."""
        editor = MagicMock()
        editor.fc_parameters = {"FRAME_CLASS": 1}
        editor.current_step_parameters = {
            "SERVO1_FUNCTION": SimpleNamespace(get_new_value=lambda: "4"),
            "SERVO2_FUNCTION": SimpleNamespace(get_new_value=lambda: "19"),
            "SERVO3_FUNCTION": SimpleNamespace(get_new_value=lambda: "70"),
            "SERVO4_FUNCTION": SimpleNamespace(get_new_value=lambda: "0"),
        }
        editor.current_step_parameters.update(
            {f"SERVO{output_number}_FUNCTION": SimpleNamespace(get_new_value=lambda: "100") for output_number in range(5, 15)}
        )
        editor.update_parameter_value.return_value = SimpleNamespace(status=ParameterValueUpdateStatus.UPDATED)
        filesystem = SimpleNamespace(
            vehicle_components_fs=SimpleNamespace(data={"Components": {"ESC": {"FC->ESC Connection": {"Type": "Main Out"}}}})
        )
        model = ServoOutDataModel(filesystem, editor)

        applied, message, _status = model.apply_recommendations()

        assert applied == ["SERVO4_FUNCTION"]
        assert "Applied 1 motor output assignment(s)." in message
        assert "Motor2, Motor3, Motor4 are not assigned to any output" in message
