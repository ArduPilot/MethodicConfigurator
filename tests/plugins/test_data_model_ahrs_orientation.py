#!/usr/bin/env python3

"""
Tests for AHRS orientation data model.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from math import cos, radians, sin, sqrt
from unittest.mock import MagicMock

import pytest

from ardupilot_methodic_configurator.plugins.data_model_ahrs_orientation import AhrsOrientationDataModel

# pylint: disable=protected-access


@pytest.mark.parametrize("orientation", [0.0, 101.0])
def test_orientation_monitor_waits_for_usable_telemetry(connected_flight_controller: MagicMock, orientation: float) -> None:
    """
    Wait for fresh telemetry and a supported active board orientation.

    GIVEN: An initial telemetry gap and either a preset or custom active rotation
    WHEN: The orientation monitor polls twice
    THEN: It supplies only samples whose active rotation can be undone
    """
    # Given: Controller samples arrive after a gap.
    controller = connected_flight_controller
    controller.fc_parameters = {"AHRS_ORIENTATION": orientation}
    controller.request_scaled_imu_messages.return_value = (True, "")
    controller.poll_scaled_imu.side_effect = [None, (0.0, 0.0, -1000.0)]
    model = AhrsOrientationDataModel(controller)
    # When / Then: Do not invent a sample or interpret unsupported rotations.
    assert model.poll_imu_raw() is None
    assert model.poll_imu_raw() == ((0.0, 0.0, -1000.0) if orientation == 0.0 else None)


def test_unknown_capture_step_does_not_change_the_orientation_sequence(connected_flight_controller: MagicMock) -> None:
    """
    Reject an unsupported capture step without discarding valid poses.

    GIVEN: A valid LEVEL pose has been recorded
    WHEN: An unknown pose is requested
    THEN: It is rejected and the existing sequence is retained
    """
    # Given: A partially captured sequence.
    model = AhrsOrientationDataModel(connected_flight_controller)
    assert model.record_sample("LEVEL", (0.0, 0.0, -1000.0))[0]
    # When: Attempt a step that is not part of detection.
    success, message = model.record_sample("BACK", (0.0, 0.0, 1000.0))
    # Then: Only the original capture remains.
    assert not success
    assert message == "Unknown capture step: BACK"
    assert model._samples == {"LEVEL": (0.0, 0.0, -1000.0)}


def test_left_side_capture_cannot_masquerade_as_the_required_right_pose(connected_flight_controller: MagicMock) -> None:
    """
    Reject a physically inconsistent set of three poses.

    GIVEN: LEVEL and NOSE DOWN followed by LEFT instead of RIGHT
    WHEN: The captured orientation is estimated
    THEN: The model asks for accurate poses rather than recommending a reflected rotation
    """
    # Given: Still samples that individually pass capture validation.
    model = AhrsOrientationDataModel(connected_flight_controller)
    for step, sample in zip(
        model.get_required_steps(), ((0.0, 0.0, -1000.0), (-1000.0, 0.0, 0.0), (0.0, 1000.0, 0.0)), strict=True
    ):
        assert model.record_sample(step, sample)[0]
    # When: Estimate from the full sequence.
    success, estimate, message = model.estimate_orientation()
    # Then: Do not offer an incorrect preset or custom rotation.
    assert not success
    assert estimate is None
    assert message == (
        "The captured poses are inconsistent with LEVEL, NOSE DOWN, and RIGHT. "
        "Place the vehicle accurately and capture the sequence again."
    )
    assert model.compute_detected_position(0.0, 1000.0, 0.0) == "LEFT"


@pytest.mark.parametrize(
    ("angle", "expected"),
    [(540.0, 180.0), (-540.0, -180.0), (725.0, 5.0), (180.0, 180.0), (-180.0, -180.0), (180.5, -179.5), (-180.5, 179.5)],
)
def test_custom_rotation_angles_are_normalized_to_the_ardupilot_range(angle: float, expected: float) -> None:
    """
    Keep equivalent custom rotations in the supported angle range.

    GIVEN: An angle spanning multiple revolutions
    WHEN: The rotation angle is normalized
    THEN: The equivalent angle lies between minus and plus 180 degrees
    """
    # When / Then: Pure angle normalization preserves an equivalent rotation.
    assert AhrsOrientationDataModel._wrap_deg(angle) == expected


def test_zero_acceleration_has_no_direction_for_orientation_estimation() -> None:
    """
    Avoid assigning a direction to a zero vector.

    GIVEN: No acceleration vector
    WHEN: Direction normalization is requested
    THEN: No direction is returned instead of dividing by zero
    """
    # When / Then: The numerical helper rejects an undefined direction.
    assert AhrsOrientationDataModel._normalize((0.0, 0.0, 0.0)) is None


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
        assert message == (
            "AHRS_ORIENTATION could not be read or is a custom/unsupported rotation. "
            "Set it to 0, upload it, reboot the flight controller, and reconnect before starting auto-detection."
        )

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
        assert msg == "No IMU sample is available yet. Keep the vehicle still and try again."

    def test_model_refuses_estimation_when_required_samples_are_missing(self, connected_flight_controller) -> None:
        model = AhrsOrientationDataModel(connected_flight_controller)

        ok, estimate, msg = model.estimate_orientation()

        assert ok is False
        assert estimate is None
        assert msg == "Missing required samples. Capture LEVEL, NOSE DOWN, and RIGHT first."

    @pytest.mark.parametrize(
        ("expected_code", "samples"),
        [
            (0, ((0.0, 0.0, -1000.0), (-1000.0, 0.0, 0.0), (0.0, -1000.0, 0.0))),
            (2, ((0.0, 0.0, -1000.0), (0.0, 1000.0, 0.0), (-1000.0, 0.0, 0.0))),
            (
                7,
                (
                    (0.0, 0.0, -1034.8491567170374),
                    (-723.5732414799375, -723.5732414799378, 0.0),
                    (682.2252637648505, -682.2252637648502, 0.0),
                ),
            ),
            (16, ((0.0, -1000.0, 0.0), (-1000.0, 0.0, 0.0), (0.0, 0.0, 1000.0))),
            # ArduPilot documents Pitch90 as the board nose/arrow pointing straight up.
            (24, ((1000.0, 0.0, 0.0), (0.0, 0.0, -1000.0), (0.0, -1000.0, 0.0))),
            (
                38,
                (
                    (932.323801, -361.624570, 0.0),
                    (-143.038972, -368.776487, 918.446381),
                    (332.132778, 856.289421, 395.545503),
                ),
            ),
        ],
    )
    def test_model_identifies_ardupilot_preset_from_independent_samples(
        self,
        connected_flight_controller,
        expected_code: int,
        samples: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]],
    ) -> None:
        """
        The estimator should recover ArduPilot presets from independently calculated samples.

        GIVEN: Three exact gravity samples based on ArduPilot's published rotation matrices
        WHEN: The full capture sequence is recorded and estimated
        THEN: The corresponding preset is selected with a high match score
        """
        model = AhrsOrientationDataModel(connected_flight_controller)

        level, nose_down, right = samples
        assert model.record_sample("LEVEL", level)[0] is True
        assert model.record_sample("NOSE DOWN", nose_down)[0] is True
        assert model.record_sample("RIGHT", right)[0] is True

        ok, estimate, _ = model.estimate_orientation()

        assert ok is True
        assert estimate is not None
        assert estimate.best_code == expected_code
        assert estimate.is_preset_match is True
        assert 0.0 <= estimate.match_score_percent <= 100.0
        assert estimate.match_score_percent == pytest.approx(100.0, abs=1e-5)

    @pytest.mark.parametrize("sample", [(0.0, 0.0, -700.0), (0.0, 0.0, -1400.0)])
    def test_model_rejects_samples_outside_still_gravity_range(self, connected_flight_controller, sample) -> None:
        model = AhrsOrientationDataModel(connected_flight_controller)

        ok, message = model.record_sample("LEVEL", sample)

        assert ok is False
        expected_magnitude = "6.86" if sample[2] == -700.0 else "13.73"
        assert message == (
            f"IMU magnitude {expected_magnitude} m/s^2 is outside the expected still range. "
            "Keep the vehicle still and try again."
        )

    def test_model_rejects_pose_that_duplicates_another_step(self, connected_flight_controller) -> None:
        model = AhrsOrientationDataModel(connected_flight_controller)
        assert model.record_sample("LEVEL", (0.0, 0.0, -1000.0))[0] is True

        ok, message = model.record_sample("RIGHT", (0.0, 0.0, -1000.0))

        assert ok is False
        assert message == "RIGHT pose too similar to LEVEL. Reposition the vehicle further and try again."

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
        # Independent 3-2-1 direction cosines for roll=20, pitch=30, yaw=40.
        # Add a tenth of the X axis to the right pose to exercise rejection of cross-axis error.
        samples = [
            (-663.413948169, 473.021458440, -579.769465589),
            (-623.011794043, -782.467319745, -97.985703107),
            (500.0, -296.198132726, -813.797681349),
        ]

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
        assert message == (
            "The captured poses are inconsistent with LEVEL, NOSE DOWN, and RIGHT. "
            "Place the vehicle accurately and capture the sequence again."
        )


@pytest.mark.parametrize("acceleration", [7.0, 7.5, 13.0])
def test_capture_accepts_the_documented_still_acceleration_range(connected_flight_controller, acceleration: float) -> None:
    """
    Pose is retained with clear confirmation.

    GIVEN: A still acceleration at or between the accepted limits
    WHEN: The operator captures the level pose
    THEN: The pose is retained with clear confirmation
    """
    model = AhrsOrientationDataModel(connected_flight_controller)
    sample = (0.0, 0.0, -acceleration * 1000.0 / 9.80665)
    assert model.record_sample("LEVEL", sample) == (True, "Captured LEVEL sample")


def test_replacing_a_pose_still_checks_it_against_later_captures(connected_flight_controller) -> None:
    """
    Duplicate is rejected and the original level pose remains.

    GIVEN: Distinct level and nose-down captures
    WHEN: Level is replaced with the nose-down reading
    THEN: The duplicate is rejected and the original level pose remains
    """
    model = AhrsOrientationDataModel(connected_flight_controller)
    assert model.record_sample("LEVEL", (0.0, 0.0, -1000.0))[0]
    assert model.record_sample("NOSE DOWN", (-1000.0, 0.0, 0.0))[0]
    assert model.record_sample("LEVEL", (-1000.0, 0.0, 0.0)) == (
        False,
        "LEVEL pose too similar to NOSE DOWN. Reposition the vehicle further and try again.",
    )


def test_orientation_monitor_reuses_then_renews_the_imu_stream(connected_flight_controller) -> None:
    """
    Physical board axes are recovered and the stream is requested once per activation.

    GIVEN: A board with a 45-degree yaw preset and distinct acceleration on every axis
    WHEN: Monitoring polls, pauses and resumes
    THEN: The physical board axes are recovered and the stream is requested once per activation
    """
    controller = connected_flight_controller
    controller.fc_parameters = {"AHRS_ORIENTATION": 1.0}
    controller.request_scaled_imu_messages.return_value = (True, "")
    controller.poll_scaled_imu.return_value = (100.0, 200.0, 300.0)
    model = AhrsOrientationDataModel(controller)
    for _ in range(2):
        assert model.poll_imu_raw() == pytest.approx((150.0 * sqrt(2), 50.0 * sqrt(2), 300.0))
    controller.request_scaled_imu_messages.assert_called_once()
    model.stop_imu_monitoring()
    assert model.poll_imu_raw() == pytest.approx((150.0 * sqrt(2), 50.0 * sqrt(2), 300.0))
    assert controller.request_scaled_imu_messages.call_count == 2


@pytest.mark.parametrize(("yaw", "score"), [(22.5, 85.0), (20.0, 87.2256555832839)])
def test_halfway_between_yaw_presets_reports_custom_orientation_with_reduced_confidence(
    connected_flight_controller, yaw: float, score: float
) -> None:
    """
    Avoid recommending either of two equally plausible orientation presets.

    GIVEN: A board mounted near halfway between the None and Yaw45 presets
    WHEN: Three independent gravity poses are captured
    THEN: The custom yaw is recovered and confidence reflects the margin between presets
    """
    model = AhrsOrientationDataModel(connected_flight_controller)
    sine, cosine = sin(radians(yaw)), cos(radians(yaw))
    for step, sample in (
        ("LEVEL", (0.0, 0.0, -1000.0)),
        ("NOSE DOWN", (-1000 * cosine, 1000 * sine, 0.0)),
        ("RIGHT", (-1000 * sine, -1000 * cosine, 0.0)),
    ):
        assert model.record_sample(step, sample)[0]
    success, estimate, message = model.estimate_orientation()
    assert success is True
    assert message == "Estimation complete"
    assert estimate is not None
    assert estimate.is_preset_match is False
    assert estimate.match_score_percent == pytest.approx(score)
    assert estimate.custom_yaw_deg == pytest.approx(yaw)


def test_historical_board_rotation_recovers_all_three_physical_acceleration_axes(connected_flight_controller) -> None:
    """
    Undo the historical noninteger ArduPilot rotation on every IMU axis.

    GIVEN: Preset 38 is active and the controller reports distinct acceleration on all axes
    WHEN: The orientation monitor reads the sample
    THEN: Published ArduPilot direction cosines recover the physical board-frame acceleration
    """
    controller = connected_flight_controller
    controller.fc_parameters = {"AHRS_ORIENTATION": 38.0}
    controller.request_scaled_imu_messages.return_value = (True, "")
    controller.poll_scaled_imu.return_value = (100.0, 200.0, 300.0)
    model = AhrsOrientationDataModel(controller)
    assert model.poll_imu_raw() == pytest.approx((-331.819798693, -25.892864618, -170.953738647))


def test_capture_accepts_a_pose_at_the_duplicate_alignment_boundary(connected_flight_controller) -> None:
    """
    Keep the documented strict boundary for rejecting similar pose captures.

    GIVEN: A level capture and another still pose whose alignment is exactly 0.9
    WHEN: The second pose is captured
    THEN: It is accepted rather than rejected as a duplicate.
    """
    model = AhrsOrientationDataModel(connected_flight_controller)
    assert model.record_sample("LEVEL", (0.0, 0.0, -1000.0))[0]
    assert model.record_sample("NOSE DOWN", (sqrt(190000.0), 0.0, -900.0)) == (True, "Captured NOSE DOWN sample")


def test_estimation_accepts_the_minimum_consistent_pose_alignment(connected_flight_controller) -> None:
    """
    Accept the exact minimum alignment allowed for the three-pose experiment.

    GIVEN: Level and nose-down are accurate while the right pose has alignment 0.9397
    WHEN: The orientation is estimated
    THEN: The captures meet the consistency limit and identify the unrotated board.
    """
    model = AhrsOrientationDataModel(connected_flight_controller)
    for step, sample in (
        ("LEVEL", (0.0, 0.0, -1000.0)),
        ("NOSE DOWN", (-1000.0, 0.0, 0.0)),
        ("RIGHT", (-389.11675958218467, -1069.161285551235, 0.0)),
    ):
        assert model.record_sample(step, sample)[0]
    success, estimate, message = model.estimate_orientation()
    assert success is True
    assert message == "Estimation complete"
    assert estimate is not None
    assert estimate.best_code == 0


def test_nearby_preset_keeps_its_measured_match_score_instead_of_rounding_up_to_perfect(connected_flight_controller) -> None:
    """
    Distinguish a close preset recommendation from a perfect orientation match.

    GIVEN: A board mounted ten degrees from the unrotated preset
    WHEN: Three accurate independent gravity poses are captured
    THEN: That preset is recommended with its measured 98.987-percent confidence.
    """
    model = AhrsOrientationDataModel(connected_flight_controller)
    sine, cosine = sin(radians(10)), cos(radians(10))
    for step, sample in (
        ("LEVEL", (0.0, 0.0, -1000.0)),
        ("NOSE DOWN", (-1000 * cosine, 1000 * sine, 0.0)),
        ("RIGHT", (-1000 * sine, -1000 * cosine, 0.0)),
    ):
        assert model.record_sample(step, sample)[0]
    success, estimate, _message = model.estimate_orientation()
    assert success is True
    assert estimate is not None
    assert estimate.best_code == 0
    assert estimate.is_preset_match is True
    assert estimate.match_score_percent == pytest.approx(98.9871835341472)


def test_small_level_pose_error_does_not_flip_the_estimated_vehicle_axes(connected_flight_controller) -> None:
    """
    Tolerate ordinary placement error without reflecting the fitted board orientation.

    GIVEN: Nose-down and right are accurate while level is tilted by five degrees
    WHEN: The three-pose experiment is estimated
    THEN: The unrotated preset remains a consistent recommendation.
    """
    model = AhrsOrientationDataModel(connected_flight_controller)
    for step, sample in (
        ("LEVEL", (0.0, 1000 * sin(radians(5)), -1000 * cos(radians(5)))),
        ("NOSE DOWN", (-1000.0, 0.0, 0.0)),
        ("RIGHT", (0.0, -1000.0, 0.0)),
    ):
        assert model.record_sample(step, sample)[0]
    success, estimate, message = model.estimate_orientation()
    assert success is True
    assert message == "Estimation complete"
    assert estimate is not None
    assert estimate.best_code == 0


def test_preset_recommendation_includes_the_exact_ninety_percent_match_boundary(connected_flight_controller) -> None:
    """
    Include a consistent orientation that meets the preset confidence threshold exactly.

    GIVEN: Three independent captures for roll, pitch and yaw of 19.605966401 degrees
    WHEN: The best preset scores exactly ninety percent with a clear margin over the runner-up
    THEN: The preset is recommended rather than requiring a custom rotation.
    """
    model = AhrsOrientationDataModel(connected_flight_controller)
    samples = (
        (335.5496675230296, -316.0953420384153, -887.4064206251843),
        (-887.4064206251843, 210.02965511184672, -410.3625087733981),
        (-316.0953420384153, -925.1871587496315, 210.02965511184672),
    )
    for step, sample in zip(model.get_required_steps(), samples, strict=True):
        assert model.record_sample(step, sample)[0]
    success, estimate, _message = model.estimate_orientation()
    assert success is True
    assert estimate is not None
    assert estimate.best_code == 0
    assert estimate.match_score_percent == 90.0
    assert estimate.is_preset_match is True
