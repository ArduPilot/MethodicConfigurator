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

from ardupilot_methodic_configurator.plugins.data_model_servo_out import ServoOutDataModel


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
        recommendations, _message = model.get_recommendations()

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
        recommendations, _message = model.get_recommendations()

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
        recommendations, _message = model.get_recommendations()

        # Assert (Then)
        assert recommendations["SERVO8_FUNCTION"] == 40
        assert recommendations["SERVO9_FUNCTION"] == 41
        assert recommendations["SERVO12_FUNCTION"] == 44

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
        recommendations, _message = model.get_recommendations()

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
                "SERVO1_FUNCTION": SimpleNamespace(new_value="70"),
                "SERVO2_FUNCTION": SimpleNamespace(new_value="0"),
            },
        )

        # Act (When)
        recommendations, _message = model.get_recommendations()

        # Assert (Then)
        assert "SERVO1_FUNCTION" not in recommendations
        assert recommendations["SERVO2_FUNCTION"] == 34

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
        recommendations, message = model.get_recommendations()

        # Assert (Then)
        assert recommendations == {}
        assert "Main Out or AIO" in message


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
        editor.update_parameter_value.return_value = SimpleNamespace(status=SimpleNamespace(name="UPDATED"))
        filesystem = SimpleNamespace(
            vehicle_components_fs=SimpleNamespace(data={"Components": {"ESC": {"FC->ESC Connection": {"Type": "Main Out"}}}})
        )
        model = ServoOutDataModel(filesystem, editor)

        # Act (When)
        applied, _message = model.apply_recommendations()

        # Assert (Then)
        assert applied == ["SERVO1_FUNCTION", "SERVO2_FUNCTION", "SERVO3_FUNCTION", "SERVO4_FUNCTION"]
        assert editor.add_parameter_to_current_file.call_count == 4
        assert editor.update_parameter_value.call_args_list[0].args == ("SERVO1_FUNCTION", "33")
