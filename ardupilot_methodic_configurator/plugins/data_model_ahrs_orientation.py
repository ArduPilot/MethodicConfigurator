"""
Data model for AHRS orientation helper plugin.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

from dataclasses import dataclass
from math import asin, atan2, cos, degrees, radians, sin, sqrt
from re import findall
from typing import TYPE_CHECKING

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.plugins.imu_helpers import (
    compute_detected_position as _compute_detected_position,
)
from ardupilot_methodic_configurator.plugins.imu_helpers import (
    compute_movement_magnitude_ms2 as _compute_movement_magnitude_ms2,
)
from ardupilot_methodic_configurator.plugins.imu_helpers import (
    poll_scaled_imu as _poll_scaled_imu,
)

if TYPE_CHECKING:
    from ardupilot_methodic_configurator.backend_flightcontroller import FlightController

_REQUIRED_STEPS: tuple[str, str, str] = ("LEVEL", "NOSE DOWN", "RIGHT")
_MIN_CAPTURE_ALIGNMENT = 0.9397  # cos(20 degrees)

# ArduPilot AHRS_ORIENTATION preset names from parameter metadata.
_AHRS_ORIENTATION_NAMES: dict[int, str] = {
    0: "None",
    1: "Yaw45",
    2: "Yaw90",
    3: "Yaw135",
    4: "Yaw180",
    5: "Yaw225",
    6: "Yaw270",
    7: "Yaw315",
    8: "Roll180",
    9: "Yaw45Roll180",
    10: "Yaw90Roll180",
    11: "Yaw135Roll180",
    12: "Pitch180",
    13: "Yaw225Roll180",
    14: "Yaw270Roll180",
    15: "Yaw315Roll180",
    16: "Roll90",
    17: "Yaw45Roll90",
    18: "Yaw90Roll90",
    19: "Yaw135Roll90",
    20: "Roll270",
    21: "Yaw45Roll270",
    22: "Yaw90Roll270",
    23: "Yaw135Roll270",
    24: "Pitch90",
    25: "Pitch270",
    26: "Yaw90Pitch180",
    27: "Yaw270Pitch180",
    28: "Pitch90Roll90",
    29: "Pitch90Roll180",
    30: "Pitch90Roll270",
    31: "Pitch180Roll90",
    32: "Pitch180Roll270",
    33: "Pitch270Roll90",
    34: "Pitch270Roll180",
    35: "Pitch270Roll270",
    36: "Yaw90Pitch180Roll90",
    37: "Yaw270Roll90",
    38: "Yaw293Pitch68Roll180",
    39: "Pitch315",
    40: "Pitch315Roll90",
    42: "Roll45",
    43: "Roll315",
}


@dataclass(frozen=True)
class AhrsOrientationEstimate:
    """Computed best-fit orientation and custom fallback angles."""

    best_code: int
    best_name: str
    match_score_percent: float
    is_preset_match: bool
    custom_roll_deg: float
    custom_pitch_deg: float
    custom_yaw_deg: float


class AhrsOrientationDataModel:
    """Business logic for AHRS orientation estimation from three IMU poses."""

    def __init__(self, flight_controller: FlightController) -> None:
        self.flight_controller = flight_controller
        self._got_imu_stream: bool = False
        self._samples: dict[str, tuple[float, float, float]] = {}

    def is_connected(self) -> bool:
        """Check if flight controller is connected."""
        return self.flight_controller.master is not None

    def validate_detection_prerequisites(self) -> tuple[bool, str]:
        """Ensure the active ArduPilot board rotation can be undone before detection."""
        orientation_code = self._current_orientation_code()
        if orientation_code is None:
            return False, _(
                "AHRS_ORIENTATION could not be read or is a custom/unsupported rotation. "
                "Set it to 0, upload it, reboot the flight controller, and reconnect before starting auto-detection."
            )
        return True, ""

    def _current_orientation_code(self) -> int | None:
        """Return a supported integral AHRS_ORIENTATION value from the FC cache."""
        orientation = self.flight_controller.fc_parameters.get("AHRS_ORIENTATION")
        if orientation is None:
            return None
        orientation_code = int(orientation)
        if orientation != orientation_code or orientation_code not in _AHRS_ORIENTATION_NAMES:
            return None
        return orientation_code

    def reset_sequence(self) -> None:
        """Clear all recorded samples for a new detection run."""
        self._samples = {}

    def get_required_steps(self) -> tuple[str, str, str]:
        """Return the ordered capture sequence expected by this model."""
        return _REQUIRED_STEPS

    def has_all_required_samples(self) -> bool:
        """Return True when all three required samples are present."""
        return all(step in self._samples for step in _REQUIRED_STEPS)

    def poll_imu_raw(self) -> tuple[float, float, float] | None:
        """
        Poll the latest IMU reading from the flight controller.

        Returns:
            tuple[float, float, float] | None: (xacc, yacc, zacc) in milli-g, or None if no data arrived.

        """
        imu_sample, self._got_imu_stream = _poll_scaled_imu(self.flight_controller, self._got_imu_stream)
        if imu_sample is None:
            return None

        orientation_code = self._current_orientation_code()
        if orientation_code is None:
            return None

        # ArduPilot publishes SCALED_IMU from AP_InertialSensor::get_accel(),
        # after AHRS_ORIENTATION has rotated board axes into vehicle-body axes.
        # Undo that active rotation so estimation always receives board-frame data.
        board_from_body = self._board_from_body_for_code(orientation_code)
        return self._mat_vec(board_from_body, imu_sample)

    def stop_imu_monitoring(self) -> None:
        """Stop SCALED_IMU streaming so next activation re-requests it."""
        self._got_imu_stream = False

    def record_sample(self, step_name: str, imu_sample: tuple[float, float, float] | None) -> tuple[bool, str]:
        """Record one sample for a required step after basic sanity checks."""
        if step_name not in _REQUIRED_STEPS:
            return False, _("Unknown capture step: %(step)s") % {"step": _(step_name)}
        if imu_sample is None:
            return False, _("No IMU sample is available yet. Keep the vehicle still and try again.")

        xacc, yacc, zacc = imu_sample
        magnitude_ms2 = self.compute_movement_magnitude_ms2(xacc, yacc, zacc)
        if magnitude_ms2 < 7.0 or magnitude_ms2 > 13.0:
            return (
                False,
                _("IMU magnitude %(value).2f m/s^2 is outside the expected still range. Keep the vehicle still and try again.")
                % {"value": magnitude_ms2},
            )

        new_norm = self._normalize(imu_sample)
        if new_norm is not None:
            for prev_step, prev_sample in self._samples.items():
                if prev_step == step_name:
                    continue
                prev_norm = self._normalize(prev_sample)
                if prev_norm is not None and abs(self._dot(new_norm, prev_norm)) > 0.9:
                    return (
                        False,
                        _("%(step)s pose too similar to %(other)s. Reposition the vehicle further and try again.")
                        % {"step": _(step_name), "other": _(prev_step)},
                    )

        self._samples[step_name] = imu_sample
        return True, _("Captured %(step)s sample") % {"step": _(step_name)}

    def estimate_orientation(self) -> tuple[bool, AhrsOrientationEstimate | None, str]:
        """Estimate AHRS orientation from the captured LEVEL/NOSE DOWN/RIGHT samples."""
        if not self.has_all_required_samples():
            return False, None, _("Missing required samples. Capture LEVEL, NOSE DOWN, and RIGHT first.")

        est_board_from_body = self._estimate_board_from_body_matrix()
        if est_board_from_body is None:
            return False, None, _("Unable to estimate orientation from samples. Capture the sequence again.")

        capture_alignment = self._capture_alignment(est_board_from_body)
        if capture_alignment < _MIN_CAPTURE_ALIGNMENT:
            return (
                False,
                None,
                _(
                    "The captured poses are inconsistent with LEVEL, NOSE DOWN, and RIGHT. "
                    "Place the vehicle accurately and capture the sequence again."
                ),
            )

        best_code, best_score = self._best_preset_code(est_board_from_body)
        second_score = self._second_best_score(est_board_from_body, best_code)
        match_score_percent = max(0.0, min(100.0, best_score * 100.0))

        # Custom rotation parameters describe the correction applied by
        # ArduPilot (body from board), which is the inverse/transpose of the
        # board-from-body matrix reconstructed from the captured samples.
        est_body_from_board = [[est_board_from_body[j][i] for j in range(3)] for i in range(3)]
        roll, pitch, yaw = self._matrix_to_euler321_deg(est_body_from_board)
        gap = best_score - second_score
        is_preset_match = bool(best_score >= 0.9 and gap >= 0.03)

        if not is_preset_match:
            match_score_percent = max(0.0, min(match_score_percent, (0.85 + max(0.0, gap)) * 100.0))

        return (
            True,
            AhrsOrientationEstimate(
                best_code=best_code,
                best_name=_AHRS_ORIENTATION_NAMES[best_code],
                match_score_percent=match_score_percent,
                is_preset_match=is_preset_match,
                custom_roll_deg=roll,
                custom_pitch_deg=pitch,
                custom_yaw_deg=yaw,
            ),
            _("Estimation complete"),
        )

    def _estimate_board_from_body_matrix(self) -> list[list[float]] | None:
        """
        Estimate board-from-body rotation matrix from required gravity poses.

        For each pose, specific force in board frame = -(R_board←body · g_body).
        """
        level = self._normalize(self._samples["LEVEL"])
        nose_down = self._normalize(self._samples["NOSE DOWN"])
        right = self._normalize(self._samples["RIGHT"])
        if level is None or nose_down is None or right is None:
            return None

        # Columns of B are images of body basis vectors.
        x_col = self._negate(nose_down)
        y_col = self._negate(right)
        z_col = self._negate(level)

        x_axis = self._normalize(x_col)
        if x_axis is None:
            return None
        y_ortho = self._sub(y_col, self._scale(x_axis, self._dot(y_col, x_axis)))
        y_axis = self._normalize(y_ortho)
        if y_axis is None:
            return None
        z_axis_raw = self._cross(x_axis, y_axis)
        z_axis = self._normalize(z_axis_raw)
        if z_axis is None:
            return None
        if self._dot(z_axis, z_col) < 0.0:
            y_axis = self._negate(y_axis)
            z_axis = self._negate(z_axis)

        return [
            [x_axis[0], y_axis[0], z_axis[0]],
            [x_axis[1], y_axis[1], z_axis[1]],
            [x_axis[2], y_axis[2], z_axis[2]],
        ]

    def _capture_alignment(self, board_from_body: list[list[float]]) -> float:
        """Return the worst alignment between the fitted axes and all three captured poses."""
        expected_columns = (
            self._negate(self._normalize(self._samples["NOSE DOWN"]) or (0.0, 0.0, 0.0)),
            self._negate(self._normalize(self._samples["RIGHT"]) or (0.0, 0.0, 0.0)),
            self._negate(self._normalize(self._samples["LEVEL"]) or (0.0, 0.0, 0.0)),
        )
        fitted_columns = tuple((board_from_body[0][col], board_from_body[1][col], board_from_body[2][col]) for col in range(3))
        return min(self._dot(expected, fitted) for expected, fitted in zip(expected_columns, fitted_columns, strict=True))

    def _best_preset_code(self, est_board_from_body: list[list[float]]) -> tuple[int, float]:
        best_code = 0
        best_score = -1.0
        for code in _AHRS_ORIENTATION_NAMES:
            candidate = self._board_from_body_for_code(code)
            score = self._score_candidate_matrix(candidate, est_board_from_body)
            if score > best_score:
                best_score = score
                best_code = code
        return best_code, best_score

    def _second_best_score(self, est_board_from_body: list[list[float]], best_code: int) -> float:
        second = -1.0
        for code in _AHRS_ORIENTATION_NAMES:
            if code == best_code:
                continue
            candidate = self._board_from_body_for_code(code)
            score = self._score_candidate_matrix(candidate, est_board_from_body)
            second = max(second, score)
        return second

    @staticmethod
    def _score_candidate_matrix(candidate: list[list[float]], estimate: list[list[float]]) -> float:
        """Return mean basis alignment between a preset rotation and the estimated board-from-body matrix."""
        total = 0.0
        for row in range(3):
            for col in range(3):
                total += candidate[row][col] * estimate[row][col]
        return total / 3.0

    def _board_from_body_for_code(self, code: int) -> list[list[float]]:
        if code == 38:
            # ROTATION_ROLL_90_PITCH_68_YAW_293 is a historical, non-integer
            # rotation with coefficients defined directly by ArduPilot.  Its
            # parameter display label (Yaw293Pitch68Roll180) cannot be parsed
            # into an equivalent Euler rotation.
            # https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_Math/vector3.cpp
            body_from_board = [
                [0.14303897231223747, 0.36877648650320383, -0.9184463813430871],
                [-0.3321327777966474, -0.8562894214664188, -0.3955455025629652],
                [-0.9323238012155122, 0.3616245700820924, 0.0],
            ]
            return [[body_from_board[j][i] for j in range(3)] for i in range(3)]

        name = _AHRS_ORIENTATION_NAMES[code]
        if name == "None":
            return self._identity_matrix()

        # Build R_body←board via right-multiplication (intrinsic/body-frame order).
        matrix = self._identity_matrix()
        for axis, value_str in findall(r"(Yaw|Pitch|Roll)(-?\d+(?:\.\d+)?)", name):
            angle_deg = float(value_str)
            if axis == "Yaw":
                rot = self._rot_z(angle_deg)
            elif axis == "Pitch":
                rot = self._rot_y(angle_deg)
            else:
                rot = self._rot_x(angle_deg)
            matrix = self._mat_mul(matrix, rot)

        # Transpose to obtain R_board←body, matching what the estimator produces.
        return [[matrix[j][i] for j in range(3)] for i in range(3)]

    def _matrix_to_euler321_deg(self, matrix: list[list[float]]) -> tuple[float, float, float]:
        # Match ArduPilot Matrix3::to_euler/from_euler exactly. Custom
        # rotations use the 3-2-1 matrix Rz(yaw) * Ry(pitch) * Rx(roll).
        pitch = -asin(max(-1.0, min(1.0, matrix[2][0])))
        roll = atan2(matrix[2][1], matrix[2][2])
        yaw = atan2(matrix[1][0], matrix[0][0])

        return (
            self._wrap_deg(degrees(roll)),
            self._wrap_deg(degrees(pitch)),
            self._wrap_deg(degrees(yaw)),
        )

    @staticmethod
    def _wrap_deg(angle_deg: float) -> float:
        while angle_deg > 180.0:
            angle_deg -= 360.0
        while angle_deg < -180.0:
            angle_deg += 360.0
        return angle_deg

    @staticmethod
    def _identity_matrix() -> list[list[float]]:
        return [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]

    @staticmethod
    def _rot_x(angle_deg: float) -> list[list[float]]:
        a = radians(angle_deg)
        return [[1.0, 0.0, 0.0], [0.0, cos(a), -sin(a)], [0.0, sin(a), cos(a)]]

    @staticmethod
    def _rot_y(angle_deg: float) -> list[list[float]]:
        a = radians(angle_deg)
        return [[cos(a), 0.0, sin(a)], [0.0, 1.0, 0.0], [-sin(a), 0.0, cos(a)]]

    @staticmethod
    def _rot_z(angle_deg: float) -> list[list[float]]:
        a = radians(angle_deg)
        return [[cos(a), -sin(a), 0.0], [sin(a), cos(a), 0.0], [0.0, 0.0, 1.0]]

    @staticmethod
    def _mat_mul(left: list[list[float]], right: list[list[float]]) -> list[list[float]]:
        return [
            [left[row][0] * right[0][col] + left[row][1] * right[1][col] + left[row][2] * right[2][col] for col in range(3)]
            for row in range(3)
        ]

    @staticmethod
    def _mat_vec(matrix: list[list[float]], vector: tuple[float, float, float]) -> tuple[float, float, float]:
        return (
            matrix[0][0] * vector[0] + matrix[0][1] * vector[1] + matrix[0][2] * vector[2],
            matrix[1][0] * vector[0] + matrix[1][1] * vector[1] + matrix[1][2] * vector[2],
            matrix[2][0] * vector[0] + matrix[2][1] * vector[1] + matrix[2][2] * vector[2],
        )

    @staticmethod
    def _dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
        return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]

    @staticmethod
    def _cross(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
        return (
            a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0],
        )

    @staticmethod
    def _scale(a: tuple[float, float, float], scalar: float) -> tuple[float, float, float]:
        return (a[0] * scalar, a[1] * scalar, a[2] * scalar)

    @staticmethod
    def _sub(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
        return (a[0] - b[0], a[1] - b[1], a[2] - b[2])

    @staticmethod
    def _negate(a: tuple[float, float, float]) -> tuple[float, float, float]:
        return (-a[0], -a[1], -a[2])

    @staticmethod
    def _normalize(vector: tuple[float, float, float]) -> tuple[float, float, float] | None:
        mag = sqrt(vector[0] ** 2 + vector[1] ** 2 + vector[2] ** 2)
        if mag < 1e-6:
            return None
        return (vector[0] / mag, vector[1] / mag, vector[2] / mag)

    @staticmethod
    def compute_movement_magnitude_ms2(xacc_mg: float, yacc_mg: float, zacc_mg: float) -> float:
        """Compute the acceleration-vector magnitude in m/s^2 from milli-g components."""
        return _compute_movement_magnitude_ms2(xacc_mg, yacc_mg, zacc_mg)

    @staticmethod
    def compute_detected_position(xacc_mg: float, yacc_mg: float, zacc_mg: float) -> str:
        """Infer a human-readable orientation label from IMU acceleration."""
        return _compute_detected_position(xacc_mg, yacc_mg, zacc_mg)
