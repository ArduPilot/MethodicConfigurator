#!/usr/bin/env python3

"""
Tests for AHRS orientation data model.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import pytest

from ardupilot_methodic_configurator.plugins.data_model_ahrs_orientation import AhrsOrientationDataModel

# pylint: disable=protected-access


class TestAhrsOrientationDataModelConnection:
    """Connection-state checks for the orientation helper model."""

    def test_model_reports_connected_when_master_link_exists(self, connected_flight_controller) -> None:
        model = AhrsOrientationDataModel(connected_flight_controller)
        assert model.is_connected() is True

    def test_model_reports_disconnected_when_master_link_absent(self, disconnected_flight_controller) -> None:
        model = AhrsOrientationDataModel(disconnected_flight_controller)
        assert model.is_connected() is False

    def test_detection_prerequisites_accept_zero_board_orientation(self, connected_flight_controller) -> None:
        connected_flight_controller.fc_parameters = {"AHRS_ORIENTATION": 0.0}
        model = AhrsOrientationDataModel(connected_flight_controller)

        assert model.validate_detection_prerequisites() == (True, "")

    def test_detection_prerequisites_accept_supported_nonzero_board_orientation(self, connected_flight_controller) -> None:
        connected_flight_controller.fc_parameters = {"AHRS_ORIENTATION": 24.0}
        model = AhrsOrientationDataModel(connected_flight_controller)

        assert model.validate_detection_prerequisites() == (True, "")

    def test_detection_prerequisites_reject_custom_board_orientation(self, connected_flight_controller) -> None:
        connected_flight_controller.fc_parameters = {"AHRS_ORIENTATION": 101.0}
        model = AhrsOrientationDataModel(connected_flight_controller)

        ok, message = model.validate_detection_prerequisites()

        assert ok is False
        assert "custom/unsupported" in message
        assert "upload" in message
        assert "reboot" in message

    def test_detection_prerequisites_reject_missing_board_orientation(self, connected_flight_controller) -> None:
        connected_flight_controller.fc_parameters = {}
        model = AhrsOrientationDataModel(connected_flight_controller)

        ok, message = model.validate_detection_prerequisites()

        assert ok is False
        assert "could not be read" in message

    def test_polling_undoes_current_pitch90_orientation(self, connected_flight_controller) -> None:
        """ArduPilot-corrected body-frame IMU data must be converted back to physical board axes."""
        connected_flight_controller.fc_parameters = {"AHRS_ORIENTATION": 24.0}
        connected_flight_controller.request_scaled_imu_messages.return_value = (True, "")
        connected_flight_controller.poll_scaled_imu.return_value = (0.0, 0.0, -1000.0)
        model = AhrsOrientationDataModel(connected_flight_controller)

        assert model.poll_imu_raw() == pytest.approx((1000.0, 0.0, 0.0), abs=1e-6)

    def test_detection_recovers_pitch90_when_fc_already_applies_pitch90(self, connected_flight_controller) -> None:
        """Compensating the active preset prevents it from corrupting the three-pose experiment."""
        connected_flight_controller.fc_parameters = {"AHRS_ORIENTATION": 24.0}
        connected_flight_controller.request_scaled_imu_messages.return_value = (True, "")
        connected_flight_controller.poll_scaled_imu.side_effect = [
            (0.0, 0.0, -1000.0),
            (-1000.0, 0.0, 0.0),
            (0.0, -1000.0, 0.0),
        ]
        model = AhrsOrientationDataModel(connected_flight_controller)

        for step in model.get_required_steps():
            assert model.record_sample(step, model.poll_imu_raw())[0] is True

        ok, estimate, _ = model.estimate_orientation()

        assert ok is True
        assert estimate is not None
        assert estimate.best_code == 24
        assert estimate.best_name == "Pitch90"


class TestAhrsOrientationDataModelCaptureAndEstimate:
    """Capture workflow and preset estimation behavior."""

    def test_model_rejects_missing_imu_sample_for_capture(self, connected_flight_controller) -> None:
        model = AhrsOrientationDataModel(connected_flight_controller)

        ok, msg = model.record_sample("LEVEL", None)

        assert ok is False
        assert "No IMU sample" in msg

    def test_model_refuses_estimation_when_required_samples_are_missing(self, connected_flight_controller) -> None:
        model = AhrsOrientationDataModel(connected_flight_controller)

        ok, estimate, msg = model.estimate_orientation()

        assert ok is False
        assert estimate is None
        assert "Missing required samples" in msg

    @pytest.mark.parametrize(
        ("expected_code", "level", "nose_down", "right"),
        [
            (0, (0.0, 0.0, -1000.0), (-1000.0, 0.0, 0.0), (0.0, -1000.0, 0.0)),
            (2, (0.0, 0.0, -1000.0), (0.0, 1000.0, 0.0), (-1000.0, 0.0, 0.0)),
            (16, (0.0, -1000.0, 0.0), (-1000.0, 0.0, 0.0), (0.0, 0.0, 1000.0)),
            # ArduPilot documents Pitch90 as the board nose/arrow pointing straight up.
            (24, (1000.0, 0.0, 0.0), (0.0, 0.0, -1000.0), (0.0, -1000.0, 0.0)),
            (
                38,
                (932.323801, -361.624570, 0.0),
                (-143.038972, -368.776487, 918.446381),
                (332.132778, 856.289421, 395.545503),
            ),
        ],
    )
    def test_model_identifies_ardupilot_preset_from_independent_samples(
        self,
        connected_flight_controller,
        expected_code: int,
        level: tuple[float, float, float],
        nose_down: tuple[float, float, float],
        right: tuple[float, float, float],
    ) -> None:
        """
        The estimator should recover ArduPilot presets from independently calculated samples.

        GIVEN: Three exact gravity samples based on ArduPilot's published rotation matrices
        WHEN: The full capture sequence is recorded and estimated
        THEN: The corresponding preset is selected with a high match score
        """
        model = AhrsOrientationDataModel(connected_flight_controller)

        assert model.record_sample("LEVEL", level)[0] is True
        assert model.record_sample("NOSE DOWN", nose_down)[0] is True
        assert model.record_sample("RIGHT", right)[0] is True

        ok, estimate, _ = model.estimate_orientation()

        assert ok is True
        assert estimate is not None
        assert estimate.best_code == expected_code
        assert estimate.is_preset_match is True
        assert estimate.match_score_percent >= 90.0

    @pytest.mark.parametrize("sample", [(0.0, 0.0, -700.0), (0.0, 0.0, -1400.0)])
    def test_model_rejects_samples_outside_still_gravity_range(self, connected_flight_controller, sample) -> None:
        model = AhrsOrientationDataModel(connected_flight_controller)

        ok, message = model.record_sample("LEVEL", sample)

        assert ok is False
        assert "outside the expected still range" in message

    def test_model_rejects_pose_that_duplicates_another_step(self, connected_flight_controller) -> None:
        model = AhrsOrientationDataModel(connected_flight_controller)
        assert model.record_sample("LEVEL", (0.0, 0.0, -1000.0))[0] is True

        ok, message = model.record_sample("RIGHT", (0.0, 0.0, -1000.0))

        assert ok is False
        assert "too similar to LEVEL" in message

    def test_model_allows_replacing_a_sample_for_the_same_step(self, connected_flight_controller) -> None:
        model = AhrsOrientationDataModel(connected_flight_controller)
        assert model.record_sample("LEVEL", (0.0, 0.0, -1000.0))[0] is True

        ok, _ = model.record_sample("LEVEL", (0.0, 0.0, -999.0))

        assert ok is True

    def test_custom_angles_are_the_board_to_body_correction_not_its_inverse(self, connected_flight_controller) -> None:
        """A board mounted at +30 degrees yaw requires a +30 degree ArduPilot custom correction."""
        model = AhrsOrientationDataModel(connected_flight_controller)
        assert model.record_sample("LEVEL", (0.0, 0.0, -1000.0))[0] is True
        assert model.record_sample("NOSE DOWN", (-866.025404, 500.0, 0.0))[0] is True
        assert model.record_sample("RIGHT", (-500.0, -866.025404, 0.0))[0] is True

        ok, estimate, _ = model.estimate_orientation()

        assert ok is True
        assert estimate is not None
        assert estimate.custom_roll_deg == pytest.approx(0.0, abs=1e-6)
        assert estimate.custom_pitch_deg == pytest.approx(0.0, abs=1e-6)
        assert estimate.custom_yaw_deg == pytest.approx(30.0, abs=1e-6)

    def test_custom_angles_use_ardupilot_321_euler_convention(self, connected_flight_controller) -> None:
        """A multi-axis custom result must round-trip through ArduPilot's Rz * Ry * Rx convention."""
        model = AhrsOrientationDataModel(connected_flight_controller)
        body_from_board = model._mat_mul(
            model._mat_mul(model._rot_z(40.0), model._rot_y(30.0)),
            model._rot_x(20.0),
        )
        board_from_body = [[body_from_board[col][row] for col in range(3)] for row in range(3)]
        samples = [tuple(-1000.0 * board_from_body[row][col] for row in range(3)) for col in range(3)]

        assert model.record_sample("LEVEL", samples[2])[0] is True
        assert model.record_sample("NOSE DOWN", samples[0])[0] is True
        assert model.record_sample("RIGHT", samples[1])[0] is True

        ok, estimate, _ = model.estimate_orientation()

        assert ok is True
        assert estimate is not None
        assert estimate.is_preset_match is False
        assert estimate.custom_roll_deg == pytest.approx(20.0, abs=1e-6)
        assert estimate.custom_pitch_deg == pytest.approx(30.0, abs=1e-6)
        assert estimate.custom_yaw_deg == pytest.approx(40.0, abs=1e-6)

    def test_estimation_rejects_inconsistent_capture_geometry(self, connected_flight_controller) -> None:
        """Orthogonalization must not turn a badly positioned pose into a perfect preset match."""
        model = AhrsOrientationDataModel(connected_flight_controller)
        assert model.record_sample("LEVEL", (0.0, 0.0, -1000.0))[0] is True
        assert model.record_sample("NOSE DOWN", (-1000.0, 0.0, 0.0))[0] is True
        assert model.record_sample("RIGHT", (-707.106781, -707.106781, 0.0))[0] is True

        ok, estimate, message = model.estimate_orientation()

        assert ok is False
        assert estimate is None
        assert "captured poses are inconsistent" in message
