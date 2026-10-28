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
from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.data_model_par_dict import Par, ParDict
from ardupilot_methodic_configurator.data_model_parameter_editor import (
    InvalidParameterNameError,
    OperationNotPossibleError,
    ParameterValueUpdateStatus,
)
from ardupilot_methodic_configurator.data_model_vehicle_components_validation import PWM_OUT_PORTS
from ardupilot_methodic_configurator.plugins.data_model_servo_out import PWM_OUT_PORTS as SERVO_OUT_PWM_PORTS
from ardupilot_methodic_configurator.plugins.data_model_servo_out import ServoOutDataModel, ServoOutRecommendationStatus

if TYPE_CHECKING:
    from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
    from ardupilot_methodic_configurator.data_model_parameter_editor import ParameterEditor

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


class TestServoOutputRecommendations:  # pylint: disable=too-many-public-methods
    """Test the user's safe default motor-output assignments."""

    def test_output_connection_types_use_the_canonical_pwm_output_choices(self) -> None:
        """The servo model uses the same output labels as vehicle-component validation."""
        assert SERVO_OUT_PWM_PORTS is PWM_OUT_PORTS

    def test_main_out_quad_starts_motor_functions_at_first_servo_output(self, servo_model_factory, caplog) -> None:
        """
        Main Out wiring assigns a quad's motors to the first output bank.

        GIVEN: A quad uses the Main Out FC-to-ESC connection
        WHEN: The user opens the servo-output step
        THEN: Motor functions 1 through 4 are proposed for SERVO1 through SERVO4
        """
        # Arrange (Given)
        model = servo_model_factory("Main Out", 1)

        # Act (When)
        recommendations, message, status = model.get_recommendations()
        assert caplog.messages == []
        assert message == "Recommended 4 motor output assignment(s)."
        assert status is ServoOutRecommendationStatus.RECOMMENDATIONS_AVAILABLE

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

    def test_main_out_tricopter_keeps_the_yaw_servo_outside_the_esc_outputs(self, servo_model_factory) -> None:
        """A tricopter's yaw servo must not be recommended in the ESC output block."""
        model = servo_model_factory("Main Out", 7)

        recommendations, message, _status = model.get_recommendations()

        assert recommendations == {
            "SERVO1_FUNCTION": 33,
            "SERVO2_FUNCTION": 34,
            "SERVO3_FUNCTION": 36,
            "SERVO7_FUNCTION": 39,
        }
        assert message == (
            "Recommended 4 motor output assignment(s). SERVO7 is the tricopter yaw servo; connect it to a servo, not an ESC."
        )

    def test_tricopter_keeps_yaw_output_reserved_when_an_esc_output_is_occupied(self, servo_model_factory) -> None:
        """An occupied early output must not move an ESC onto the reserved yaw-servo output."""
        model = servo_model_factory(
            "Main Out",
            7,
            {"SERVO1_FUNCTION": SimpleNamespace(get_new_value=lambda: "51")},
        )

        recommendations, message, _status = model.get_recommendations()

        assert recommendations == {
            "SERVO2_FUNCTION": 33,
            "SERVO3_FUNCTION": 34,
            "SERVO4_FUNCTION": 36,
            "SERVO7_FUNCTION": 39,
        }
        assert message == (
            "Recommended 4 motor output assignment(s). SERVO7 is the tricopter yaw servo; connect it to a servo, not an ESC."
        )

    def test_aio_tricopter_keeps_the_yaw_servo_on_servo7(self, servo_model_factory) -> None:
        """AIO connection ordering must not move the tricopter yaw servo into the ESC bank."""
        model = servo_model_factory("AIO", 7)

        recommendations, _message, _status = model.get_recommendations()

        assert recommendations == {
            "SERVO9_FUNCTION": 33,
            "SERVO10_FUNCTION": 34,
            "SERVO11_FUNCTION": 36,
            "SERVO7_FUNCTION": 39,
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

    def test_octa_does_not_describe_motor7_as_a_tricopter_servo(self, servo_model_factory) -> None:
        """Motor function 39 on an octa is still an ESC output, not a tricopter warning."""
        model = servo_model_factory("Main Out", 3)

        _recommendations, message, _status = model.get_recommendations()

        assert "tricopter" not in message.lower()

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

    def test_offline_recommendations_respect_motor_functions_saved_in_other_steps(self, servo_model_factory) -> None:
        """GIVEN offline assignments in earlier files, WHEN recommending, THEN preserve outputs and avoid duplicate motors."""
        model = servo_model_factory("Main Out", 1)
        model._parameter_editor.fc_parameters.clear()
        model._local_filesystem.file_parameters = {
            "05_board_orientation.param": ParDict({"SERVO1_FUNCTION": Par(70)}),
            "16_accelerometer_calibration.param": ParDict({"SERVO2_FUNCTION": Par(33), "SERVO7_FUNCTION": Par(34)}),
        }
        model._local_filesystem.vehicle_type = "ArduCopter"
        model._local_filesystem.vehicle_components_fs.data["Components"]["Frame"] = {"Specifications": {"Frame class": "Quad"}}

        recommendations, _message, status = model.get_recommendations()

        assert status is ServoOutRecommendationStatus.RECOMMENDATIONS_AVAILABLE
        assert recommendations == {"SERVO3_FUNCTION": 35, "SERVO4_FUNCTION": 36}

    def test_offline_recommendations_use_last_saved_assignment_for_an_output(self, servo_model_factory) -> None:
        """GIVEN a later step disables an output, WHEN offline, THEN it can receive a motor again."""
        model = servo_model_factory("Main Out", 1)
        model._local_filesystem.file_parameters = {
            "05_board_orientation.param": ParDict({"SERVO1_FUNCTION": Par(70)}),
            "16_accelerometer_calibration.param": ParDict({"SERVO1_FUNCTION": Par(0)}),
        }

        recommendations, _message, status = model.get_recommendations()

        assert status is ServoOutRecommendationStatus.RECOMMENDATIONS_AVAILABLE
        assert recommendations["SERVO1_FUNCTION"] == 33

    def test_recommendations_skip_outputs_overwritten_by_a_later_step(self, servo_model_factory) -> None:
        """An active-step recommendation must not be silently erased by a later saved value."""
        model = servo_model_factory("Main Out", 1)
        model._parameter_editor.current_file = "10_servo_out.param"
        model._local_filesystem.file_parameters = {
            "05_board_orientation.param": ParDict({"SERVO1_FUNCTION": Par(70)}),
            "10_servo_out.param": ParDict(),
            "14_later_setup.param": ParDict({"SERVO1_FUNCTION": Par(0)}),
        }

        recommendations, message, _status = model.get_recommendations()

        assert "SERVO1_FUNCTION" not in recommendations
        assert recommendations["SERVO2_FUNCTION"] == 33
        assert "SERVO1_FUNCTION (14_later_setup.param)" in message

    def test_tricopter_yaw_skips_pinned_output_overwritten_by_a_later_step(self, servo_model_factory) -> None:
        """A later saved SERVO7 value must block the pinned tricopter yaw assignment too."""
        model = servo_model_factory("Main Out", 7)
        model._parameter_editor.current_file = "10_servo_out.param"
        model._local_filesystem.file_parameters = {
            "10_servo_out.param": ParDict(),
            "14_later_setup.param": ParDict({"SERVO7_FUNCTION": Par(0)}),
        }

        recommendations, message, _status = model.get_recommendations()

        assert "SERVO7_FUNCTION" not in recommendations
        assert "SERVO7_FUNCTION (14_later_setup.param)" in message

    def test_malformed_frame_component_data_returns_a_recommendation_error(self, servo_model_factory) -> None:
        """Malformed nested vehicle data falls back to a clear unsupported-frame result."""
        model = servo_model_factory("Main Out", 1)
        model._parameter_editor.fc_parameters.clear()
        model._local_filesystem.vehicle_type = "ArduCopter"
        model._local_filesystem.vehicle_components_fs.data = {
            "Components": {
                "ESC": {"FC->ESC Connection": {"Type": "Main Out"}},
                "Frame": [],
            }
        }

        recommendations, message, status = model.get_recommendations()

        assert recommendations == {}
        assert status is ServoOutRecommendationStatus.ERROR
        assert message == "FRAME_CLASS 0 does not have a supported motor-output mapping."

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

    def test_offline_project_uses_saved_frame_class_for_motor_recommendations(self) -> None:
        """Without an FC, use the frame selected in vehicle components rather than class zero."""
        filesystem = SimpleNamespace(
            vehicle_components_fs=SimpleNamespace(
                data={
                    "Components": {
                        "ESC": {"FC->ESC Connection": {"Type": "Main Out"}},
                        "Frame": {"Specifications": {"Frame class": "Quad"}},
                    }
                }
            )
        )
        filesystem.vehicle_type = "ArduCopter"
        editor = SimpleNamespace(fc_parameters={}, current_step_parameters={})
        model = ServoOutDataModel(cast("LocalFilesystem", filesystem), cast("ParameterEditor", editor))

        recommendations, _message, status = model.get_recommendations()

        assert status is ServoOutRecommendationStatus.RECOMMENDATIONS_AVAILABLE
        assert recommendations == {
            "SERVO1_FUNCTION": 33,
            "SERVO2_FUNCTION": 34,
            "SERVO3_FUNCTION": 35,
            "SERVO4_FUNCTION": 36,
        }

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
        assert message == "Select either Main Out or AIO as the FC-to-ESC connection type before assigning outputs."
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
        assert message == "Applied 3 motor output assignment(s). Could not apply: SERVO2_FUNCTION."

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
        applied, message, status = model.apply_recommendations()

        # Assert (Then)
        assert not applied
        assert status is ServoOutRecommendationStatus.ERROR
        assert message == (
            "No servo output assignments could be applied. Could not apply: "
            "SERVO1_FUNCTION, SERVO2_FUNCTION, SERVO3_FUNCTION, SERVO4_FUNCTION."
        )

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
        assert message == ("Applied 1 motor output assignment(s). Motor2, Motor3, Motor4 are not assigned to any output.")


@pytest.mark.parametrize("frame_class", ["invalid", [], float("inf")])
def test_invalid_frame_configuration_cannot_propose_motor_outputs(
    servo_model_factory: Callable[[str, int, dict[str, object] | None], ServoOutDataModel], frame_class: object
) -> None:
    """
    Reject unsupported frame values without guessing output assignments.

    GIVEN: FRAME_CLASS contains malformed data
    WHEN: The user requests motor outputs
    THEN: No assignments are proposed and the unsupported mapping is explained
    """
    # Given: A valid connection but an unusable frame value.
    model = servo_model_factory("Main Out", 1, None)
    cast("dict[str, object]", model._parameter_editor.fc_parameters)["FRAME_CLASS"] = frame_class
    # When: Resolve recommendations through the public API.
    recommendations, message, status = model.get_recommendations()
    # Then: Do not guess a frame or overwrite outputs.
    assert recommendations == {}
    assert status is ServoOutRecommendationStatus.ERROR
    assert message == "FRAME_CLASS 0 does not have a supported motor-output mapping."


@pytest.mark.parametrize("invalid_function", [[], "invalid", 5.5])
def test_unrecognized_output_functions_are_preserved_instead_of_reassigned(
    servo_model_factory: Callable[[str, int, dict[str, object] | None], ServoOutDataModel], invalid_function: object
) -> None:
    """
    Preserve ambiguous output assignments for user review.

    GIVEN: An output has a value that is not a valid integer servo function
    WHEN: Motor assignments are recommended
    THEN: That output is left alone and motors are assigned to known free outputs
    """
    # Given: An occupied or ambiguous first output.
    model = servo_model_factory("Main Out", 1, None)
    cast("dict[str, object]", model._parameter_editor.fc_parameters)["SERVO1_FUNCTION"] = invalid_function
    # When: Recommend safe assignments.
    recommendations, _message, status = model.get_recommendations()
    # Then: Ambiguous values are not interpreted as disabled outputs.
    assert recommendations == {f"SERVO{index + 1}_FUNCTION": 32 + index for index in range(1, 5)}
    assert status is ServoOutRecommendationStatus.RECOMMENDATIONS_AVAILABLE


@pytest.mark.parametrize(
    "layouts", [None, [{"Class": 1}], [{"Class": 1, "motors": [None]}], [{"Class": 1, "motors": [{"Number": "1"}]}]]
)
def test_unusable_motor_metadata_produces_an_actionable_mapping_error(
    servo_model_factory: Callable[[str, int, dict[str, object] | None], ServoOutDataModel], layouts: object
) -> None:
    """
    Reject malformed motor-layout metadata.

    GIVEN: Motor-layout data is missing or contains invalid motor records
    WHEN: The user requests output recommendations
    THEN: A supported-mapping error is returned rather than a partial assignment
    """
    # Given: Only the external JSON-loader boundary is mocked.
    model = servo_model_factory("Main Out", 1, None)
    with patch.object(model._motor_data_loader, "load_json_data", return_value={"layouts": layouts}):
        # When: Read and interpret the layout.
        recommendations, message, status = model.get_recommendations()
    # Then: Invalid records do not silently become a usable layout.
    assert recommendations == {}
    assert status is ServoOutRecommendationStatus.ERROR
    assert message == "FRAME_CLASS 1 does not have a supported motor-output mapping."


@pytest.mark.parametrize("occupied", [True, False])
def test_applying_outputs_without_available_assignments_explains_the_result(
    servo_model_factory: Callable[[str, int, dict[str, object] | None], ServoOutDataModel], occupied: bool
) -> None:
    """
    Distinguish already assigned motors from motors that cannot be routed.

    GIVEN: All motor functions are assigned or all outputs are occupied by other functions
    WHEN: The user applies recommended outputs
    THEN: No changes occur and the message explains which situation applies
    """
    # Given: A complete mapping or no available free outputs.
    parameters: dict[str, object] = {
        f"SERVO{index}_FUNCTION": SimpleNamespace(get_new_value=lambda index=index: 4 if occupied else 32 + index)
        for index in range(1, 15 if occupied else 5)
    }
    model = servo_model_factory("Main Out", 1, parameters)
    # When: Apply recommendations.
    applied, message, status = model.apply_recommendations()
    # Then: A no-op carries the correct semantic result.
    assert applied == []
    if occupied:
        assert status is ServoOutRecommendationStatus.UNASSIGNED_MOTORS
        assert "Motor1, Motor2, Motor3, Motor4 are not assigned" in message
    else:
        assert status is ServoOutRecommendationStatus.NO_CHANGES
        assert "no changes are needed" in message


@pytest.mark.parametrize("exception_type", [InvalidParameterNameError, OperationNotPossibleError])
def test_unavailable_servo_parameter_does_not_prevent_other_motor_assignments(
    servo_model_factory: Callable[[str, int, dict[str, object] | None], ServoOutDataModel], exception_type: type[Exception]
) -> None:
    """
    Recover from a domain error when adding one output parameter.

    GIVEN: The first recommended output cannot be added to the current step
    WHEN: The user applies the recommendations
    THEN: Other outputs are staged and the unavailable output is named
    """
    # Given: Parameter-editor operations form the boundary under test.
    model = servo_model_factory("Main Out", 1, None)
    editor = cast("SimpleNamespace", model._parameter_editor)
    editor.add_parameter_to_current_file = MagicMock(side_effect=[exception_type("Unavailable"), True, True, True])
    editor.update_parameter_value = MagicMock(return_value=SimpleNamespace(status=ParameterValueUpdateStatus.UPDATED))
    # When: Apply the real model's recommendations.
    applied, message, status = model.apply_recommendations()
    # Then: One unavailable output does not prevent the others from being assigned.
    assert applied == ["SERVO2_FUNCTION", "SERVO3_FUNCTION", "SERVO4_FUNCTION"]
    assert status is ServoOutRecommendationStatus.APPLIED
    assert message == "Applied 3 motor output assignment(s). Could not apply: SERVO1_FUNCTION."


@pytest.mark.parametrize("motor_count", [14, 15])
def test_frame_layouts_respect_the_available_output_capacity(
    servo_model_factory: Callable[[str, int, dict[str, object] | None], ServoOutDataModel],
    motor_count: int,
) -> None:
    """
    Accept a full output bank and reject layouts exceeding its capacity.

    GIVEN: A scripting frame layout requires fourteen or fifteen outputs
    WHEN: The user requests assignments for fourteen available outputs
    THEN: All fourteen motors are assigned or the excess capacity is explained
    """
    # Given: A realistic external layout exceeding this plugin's routing capacity.
    model = servo_model_factory("Main Out", 15, None)
    metadata = {"layouts": [{"Class": 15, "motors": [{"Number": number} for number in range(1, motor_count + 1)]}]}
    with patch.object(model._motor_data_loader, "load_json_data", return_value=metadata):
        # When: Resolve the complete motor layout.
        recommendations, message, status = model.get_recommendations()
    # Then: Never silently omit the fifteenth motor.
    if motor_count == 15:
        assert recommendations == {}
        assert status is ServoOutRecommendationStatus.ERROR
        assert message == "FRAME_CLASS 15 requires more outputs than this plugin can assign."
    else:
        functions = (*range(33, 41), *range(82, 86), 160, 161)
        assert recommendations == {f"SERVO{index}_FUNCTION": value for index, value in enumerate(functions, 1)}
        assert status is ServoOutRecommendationStatus.RECOMMENDATIONS_AVAILABLE
        assert message == "Recommended 14 motor output assignment(s)."


def test_multiple_later_servo_changes_explain_conflicts_without_discarding_recommendation_summary(servo_model_factory) -> None:
    """
    Preserve the assignment summary and every conflicting later step.

    GIVEN: Two currently unassigned outputs have saved changes after this step
    WHEN: Motor outputs are recommended
    THEN: Those outputs are skipped and both conflicts follow the recommendation summary
    """
    model = servo_model_factory("Main Out", 1)
    model._parameter_editor.current_file = "10_servo_out.param"
    model._local_filesystem.file_parameters = {
        "10_servo_out.param": ParDict(),
        "14_later_setup.param": ParDict({"SERVO1_FUNCTION": Par(0), "SERVO2_FUNCTION": Par(0)}),
        "15_later_setup.param": ParDict({"SERVO1_FUNCTION": Par(0)}),
    }
    recommendations, message, status = model.get_recommendations()
    assert recommendations == {f"SERVO{number + 2}_FUNCTION": 32 + number for number in range(1, 5)}
    assert status is ServoOutRecommendationStatus.RECOMMENDATIONS_AVAILABLE
    assert message == (
        "Recommended 4 motor output assignment(s). "
        "Skipped outputs with later saved changes because those steps would overwrite assignments: "
        "SERVO1_FUNCTION (14_later_setup.param), SERVO2_FUNCTION (14_later_setup.param)."
    )


def test_occupied_tricopter_yaw_output_is_preserved_and_reports_the_unassigned_servo(servo_model_factory) -> None:
    """
    Preserve an occupied yaw-servo output and explain the missing assignment.

    GIVEN: A tricopter's SERVO7 is occupied by a non-motor function
    WHEN: Outputs are recommended
    THEN: Three ESC assignments are proposed and the unassigned yaw function is reported
    """
    model = servo_model_factory("Main Out", 7, {"SERVO7_FUNCTION": SimpleNamespace(get_new_value=lambda: 70)})
    recommendations, message, status = model.get_recommendations()
    assert recommendations == {"SERVO1_FUNCTION": 33, "SERVO2_FUNCTION": 34, "SERVO3_FUNCTION": 36}
    assert status is ServoOutRecommendationStatus.RECOMMENDATIONS_AVAILABLE
    assert message == "Recommended 3 motor output assignment(s). Motor7 is not assigned to any output."


@pytest.mark.parametrize(
    ("frame_class", "summary"),
    [(1, ""), (3, ""), (7, " SERVO7 is the tricopter yaw servo; connect it to a servo, not an ESC.")],
)
def test_applying_motor_outputs_retains_only_the_unresolved_assignment_guidance(
    servo_model_factory, frame_class: int, summary: str
) -> None:
    """
    Replace the recommendation summary with an accurate application result.

    GIVEN: A quad, octa or tricopter has free outputs and the editor accepts each assignment
    WHEN: The recommendations are applied
    THEN: The result reports the applied assignments without repeating the recommendation.
    """
    model = servo_model_factory("Main Out", frame_class)
    editor = cast("SimpleNamespace", model._parameter_editor)
    editor.add_parameter_to_current_file = MagicMock(return_value=True)
    editor.update_parameter_value = MagicMock(return_value=SimpleNamespace(status=ParameterValueUpdateStatus.UPDATED))
    applied, message, status = model.apply_recommendations()
    count = 8 if frame_class == 3 else 4
    assert len(applied) == count
    assert status is ServoOutRecommendationStatus.APPLIED
    assert message == f"Applied {count} motor output assignment(s)."
    recommendations, recommendation_message, _status = model.get_recommendations()
    assert len(recommendations) == count
    assert recommendation_message == f"Recommended {count} motor output assignment(s)." + summary


@pytest.mark.parametrize("source", ["saved", "controller", "staged"])
def test_motor_assignments_ignore_servo_settings_that_are_not_output_functions(servo_model_factory, source: str) -> None:
    """
    Interpret only SERVOx_FUNCTION values as existing motor assignments.

    GIVEN: The BLHeli output mask has the numeric value of Motor1's function
    WHEN: Recommendations combine saved, controller and staged parameters
    THEN: The mask does not make an unassigned Motor1 appear connected.
    """
    model = servo_model_factory("Main Out", 1)
    if source == "saved":
        model._local_filesystem.file_parameters = {"10_servo.param": ParDict({"SERVO_BLH_MASK": Par(33)})}
    elif source == "controller":
        model._parameter_editor.fc_parameters["SERVO_BLH_MASK"] = 33
    else:
        model._parameter_editor.current_step_parameters["SERVO_BLH_MASK"] = SimpleNamespace(get_new_value=lambda: 33)
    recommendations, _message, status = model.get_recommendations()
    assert status is ServoOutRecommendationStatus.RECOMMENDATIONS_AVAILABLE
    assert recommendations == {f"SERVO{number}_FUNCTION": 32 + number for number in range(1, 5)}


def test_later_changes_to_occupied_outputs_do_not_warn_about_overwriting_new_assignments(servo_model_factory) -> None:
    """
    Reserve future outputs only when they are currently available for assignment.

    GIVEN: A motor and a control output already have assignments that are changed by a later step
    WHEN: The remaining motors are routed to free outputs
    THEN: Occupied outputs are preserved and no overwrite warning refers to them.
    """
    parameters = {
        "SERVO1_FUNCTION": SimpleNamespace(get_new_value=lambda: 33),
        "SERVO2_FUNCTION": SimpleNamespace(get_new_value=lambda: 4),
    }
    model = servo_model_factory("Main Out", 1, parameters)
    model._parameter_editor.current_file = "10_servo.param"
    model._local_filesystem.file_parameters = {
        "10_servo.param": ParDict(),
        "12_controls.param": ParDict({"SERVO1_FUNCTION": Par(33), "SERVO2_FUNCTION": Par(4)}),
    }
    recommendations, message, status = model.get_recommendations()
    assert status is ServoOutRecommendationStatus.RECOMMENDATIONS_AVAILABLE
    assert recommendations == {f"SERVO{number + 1}_FUNCTION": 32 + number for number in range(2, 5)}
    assert message == "Recommended 3 motor output assignment(s)."


@pytest.mark.parametrize("bad_motors", [None, [], [None], [{"Number": "invalid"}]])
def test_motor_layout_selection_continues_after_an_unusable_matching_layout(bad_motors: object) -> None:
    """
    Recover from an unusable layout when another matching motor arrangement exists.

    GIVEN: Motor metadata contains a malformed matching layout before a usable one
    WHEN: The frame class's motor numbers are resolved
    THEN: The usable layout supplies all four motor numbers.
    """
    data = {
        "layouts": [
            {"Class": 1, "motors": bad_motors},
            {"Class": 1, "motors": [{"Number": number} for number in range(1, 5)]},
        ]
    }
    assert ServoOutDataModel._motor_numbers_for_frame_class(1, data) == (1, 2, 3, 4)


@pytest.mark.parametrize("unset", ["", "33.5"])
def test_empty_functions_remain_assignable_and_fractional_functions_are_not_motor_assignments(
    servo_model_factory, unset: str
) -> None:
    """
    Avoid interpreting incomplete function edits as a valid motor assignment.

    GIVEN: One output has an empty edit or an invalid fractional function value
    WHEN: A quad's motor outputs are recommended
    THEN: Motor1 is assigned to the first genuinely free output.
    """
    model = servo_model_factory("Main Out", 1, {"SERVO1_FUNCTION": SimpleNamespace(get_new_value=lambda: unset)})
    recommendations, _message, _status = model.get_recommendations()
    first_output = 1 if unset == "" else 2
    assert recommendations == {f"SERVO{number + first_output - 1}_FUNCTION": 32 + number for number in range(1, 5)}


@pytest.mark.parametrize(("vehicle", "label", "frame_class"), [("Rover", "Boat", 2), ("", "Quad", 1)])
def test_offline_frame_labels_use_the_selected_vehicle_dictionary_or_copter_fallback(
    servo_model_factory, vehicle: str, label: str, frame_class: int
) -> None:
    """
    Interpret saved frame labels using their vehicle's own numbering.

    GIVEN: No controller frame parameter is available and a saved frame label exists
    WHEN: The offline frame class is resolved
    THEN: Rover labels use Rover numbering and an unspecified vehicle uses Copter's fallback.
    """
    model = servo_model_factory("Main Out", 1)
    model._parameter_editor.fc_parameters.clear()
    model._local_filesystem.vehicle_type = vehicle
    model._local_filesystem.vehicle_components_fs.data["Components"]["Frame"] = {"Specifications": {"Frame class": label}}
    assert model._get_frame_class() == frame_class
