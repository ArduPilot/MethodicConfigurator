#!/usr/bin/env python3

"""
Tests for the attitude-control saturation log analysis.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import numpy as np
import pytest

from ardupilot_methodic_configurator.log_analysis.data_model_availability_attitude_saturation import (
    AttitudeSaturationLogAnalysis,
    AttitudeSaturationLogAvailabilityModel,
)
from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis import LOG_ANALYSIS_SUBSYSTEMS
from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis_context import LogAnalysisContext
from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis_result import LogAnalysis
from ardupilot_methodic_configurator.log_analysis.data_model_log_availability import LogAvailabilityState
from ardupilot_methodic_configurator.log_analysis.data_model_log_data import LogData
from ardupilot_methodic_configurator.log_analysis.data_model_parameter_history import ParameterChange, ParameterHistory

# pylint: disable=too-many-lines


SAMPLES = 1000  # 100 s at 10 Hz
STABILIZE = 0
ACRO = 1
LOITER = 5


def _time() -> np.ndarray:
    return np.arange(SAMPLES) * 0.1


def _context(
    parameters: dict[str, float], apm_doc: dict | None = None, history: ParameterHistory | None = None
) -> LogAnalysisContext:
    steps = {"28_attitude.param": {"derived_parameters": {}, "forced_parameters": {name: {} for name in parameters}}}
    return LogAnalysisContext(
        parameters=parameters, configuration_steps=steps, apm_doc=apm_doc, parameter_history=history or ParameterHistory()
    )


def _add_rate(log: LogData, **targets: np.ndarray) -> None:
    zeros = np.zeros(SAMPLES)
    columns = {"RDes": zeros, "PDes": zeros, "YDes": zeros, **targets}
    log.add_message_columns("RATE", _array(TimeUS=_time(), **columns))


def _add_pid(log: LogData, message: str, dmod: np.ndarray | None = None, flags: np.ndarray | None = None) -> None:
    log.add_message_columns(
        message,
        _array(
            TimeUS=_time(),
            Dmod=np.ones(SAMPLES) if dmod is None else dmod,
            Flags=np.zeros(SAMPLES) if flags is None else flags,
        ),
    )


def _add_att(log: LogData, roll: np.ndarray, pitch: np.ndarray | None = None) -> None:
    log.add_message_columns(
        "ATT", _array(TimeUS=_time(), DesRoll=roll, DesPitch=np.zeros(SAMPLES) if pitch is None else pitch)
    )


def _add_modes(log: LogData, *changes: tuple[float, int]) -> None:
    log.add_message_columns("MODE", _array(TimeUS=[t for t, _ in changes], ModeNum=[m for _, m in changes]))


def _array(**fields: np.ndarray | list) -> np.ndarray:
    length = len(next(iter(fields.values())))
    records = np.zeros(length, dtype=[(name, "f8") for name in fields])
    for name, values in fields.items():
        records[name] = values
    return records


def _analyse(log: LogData, parameters: dict[str, float], history: ParameterHistory | None = None) -> list[LogAnalysis]:
    return AttitudeSaturationLogAnalysis(log, _context(parameters, history=history)).analyse().outcomes


def _window(fraction: float, value: float, base: float = 0.0) -> np.ndarray:
    """Return a series that holds ``value`` for the given leading fraction of the samples."""
    series = np.full(SAMPLES, base)
    series[: int(SAMPLES * fraction)] = value
    return series


def test_user_is_warned_critically_when_roll_rate_target_is_clipped_by_atc_rate_r_max_for_a_long_time() -> None:
    """
    Roll rate targets stuck at ATC_RATE_R_MAX mean the vehicle cannot rotate as requested.

    GIVEN a log where the roll rate target sits at ATC_RATE_R_MAX for 30% of the time
    WHEN the attitude saturation analysis runs
    THEN a critical finding names ATC_RATE_R_MAX and says attitude control is severely reduced
    """
    log = LogData(vehicle_type="ArduCopter")
    _add_rate(log, RDes=_window(0.3, -200.0))

    outcomes = _analyse(log, {"ATC_RATE_R_MAX": 200.0})

    assert len(outcomes) == 1
    assert outcomes[0].severity == "critical"
    assert outcomes[0].param_name == "ATC_RATE_R_MAX"
    assert "severely reduce attitude control" in outcomes[0].message
    assert outcomes[0].evidence is not None
    assert outcomes[0].evidence["saturated_percent"] == pytest.approx(30.0, abs=0.05)


def test_user_gets_a_warning_for_occasional_rate_limit_saturation() -> None:
    """
    User gets a warning for occasional rate limit saturation.

    GIVEN pitch rate targets at ATC_RATE_P_MAX for 3% of the time
    WHEN the analysis runs
    THEN the finding is only a warning
    """
    log = LogData(vehicle_type="ArduCopter")
    _add_rate(log, PDes=_window(0.03, 90.0))

    outcomes = _analyse(log, {"ATC_RATE_P_MAX": 90.0})

    assert [outcome.severity for outcome in outcomes] == ["warning"]
    assert outcomes[0].param_name == "ATC_RATE_P_MAX"


def test_user_is_not_warned_when_the_rate_limit_is_disabled_or_never_reached() -> None:
    """
    User is not warned when the rate limit is disabled or never reached.

    GIVEN rate targets that would match 200 deg/s
    WHEN ATC_RATE_R_MAX is 0 (disabled) or higher than any target
    THEN nothing is reported
    """
    log = LogData(vehicle_type="ArduCopter")
    _add_rate(log, RDes=_window(0.5, 200.0))

    assert not _analyse(log, {"ATC_RATE_R_MAX": 0.0})
    assert not _analyse(log, {"ATC_RATE_R_MAX": 360.0})


def test_saturation_before_arming_is_ignored() -> None:
    """
    Saturation before arming is ignored.

    GIVEN a clipped roll rate target that only occurs while disarmed
    WHEN ARM messages show the vehicle armed later
    THEN the disarmed samples do not count
    """
    log = LogData(vehicle_type="ArduCopter")
    _add_rate(log, RDes=_window(0.3, 200.0))
    log.add_message_columns("ARM", _array(ArmState=[1.0, 0.0], TimeUS=[40.0, 90.0]))

    assert not _analyse(log, {"ATC_RATE_R_MAX": 200.0})


def test_user_is_warned_critically_when_slew_limiter_cuts_pd_gain_in_half() -> None:
    """
    User is warned critically when slew limiter cuts pd gain in half.

    GIVEN the roll slew limiter scaling P and D to 0.3 for 20% of the time
    WHEN the analysis runs
    THEN a critical ATC_RAT_RLL_SMAX finding is reported
    """
    log = LogData(vehicle_type="ArduCopter")
    _add_pid(log, "PIDR", dmod=_window(0.2, 0.3, base=1.0))

    outcomes = _analyse(log, {"ATC_RAT_RLL_SMAX": 25.0})

    assert len(outcomes) == 1
    assert outcomes[0].severity == "critical"
    assert outcomes[0].param_name == "ATC_RAT_RLL_SMAX"
    assert outcomes[0].evidence is not None
    assert outcomes[0].evidence["minimum_dmod"] == pytest.approx(0.3)


def test_mild_slew_limiting_is_only_a_warning_and_disabled_slew_limiter_is_ignored() -> None:
    """
    Mild slew limiting is only a warning and disabled slew limiter is ignored.

    GIVEN Dmod around 0.8 for 5% of the time on the yaw axis
    WHEN ATC_RAT_YAW_SMAX is set the user gets a warning, and when it is 0 nothing is reported
    """
    log = LogData(vehicle_type="ArduCopter")
    _add_pid(log, "PIDY", dmod=_window(0.05, 0.8, base=1.0))

    warned = _analyse(log, {"ATC_RAT_YAW_SMAX": 10.0})

    assert [outcome.severity for outcome in warned] == ["warning"]
    assert not _analyse(log, {"ATC_RAT_YAW_SMAX": 0.0})


def test_user_is_warned_when_pd_sum_limit_pdmx_is_active() -> None:
    """
    User is warned when pd sum limit pdmx is active.

    GIVEN the PD-sum-limit flag set for 15% of the pitch PID samples
    WHEN ATC_RAT_PIT_PDMX is enabled
    THEN a critical ATC_RAT_PIT_PDMX finding is reported and the I-term limit flag alone is not mistaken for it
    """
    log = LogData(vehicle_type="ArduCopter")
    _add_pid(log, "PIDP", flags=_window(0.15, 3.0))
    _add_pid(log, "PIDR", flags=_window(0.5, 1.0))

    outcomes = _analyse(log, {"ATC_RAT_PIT_PDMX": 0.5, "ATC_RAT_RLL_PDMX": 0.5})

    assert [(outcome.param_name, outcome.severity) for outcome in outcomes] == [("ATC_RAT_PIT_PDMX", "critical")]


def test_pilot_lean_limit_finding_reports_full_range_without_acceleration_advice() -> None:
    """
    Full pilot lean input is described without inferring acceleration saturation.

    GIVEN a desired roll of 30 deg while ANGLE_MAX is 3000 cdeg
    WHEN the analysis runs in Stabilize
    THEN a warning names ANGLE_MAX and explains that the full pilot lean range was used
    """
    log = LogData(vehicle_type="ArduCopter")
    _add_att(log, _window(0.2, 30.0))
    _add_modes(log, (0.0, STABILIZE))

    outcomes = _analyse(log, {"ANGLE_MAX": 3000.0})

    assert len(outcomes) == 1
    assert outcomes[0].severity == "warning"
    assert outcomes[0].param_name == "ANGLE_MAX"
    assert "full pilot lean range" in outcomes[0].message
    assert "demanded acceleration" not in outcomes[0].message
    assert "Raise ANGLE_MAX" not in outcomes[0].message


def test_atc_angle_max_is_used_instead_of_angle_max_on_new_firmware() -> None:
    """
    Atc angle max is used instead of angle max on new firmware.

    GIVEN a desired combined roll and pitch tilt of about 30 deg
    WHEN ATC_ANGLE_MAX (degrees, firmware 4.7+) is 30
    THEN the finding names ATC_ANGLE_MAX
    """
    log = LogData(vehicle_type="ArduCopter")
    tilt_component = np.degrees(np.arccos(np.sqrt(np.cos(np.radians(30.0)))))  # roll and pitch each give half the tilt cosine
    _add_att(log, _window(0.2, tilt_component), _window(0.2, tilt_component))
    _add_modes(log, (0.0, STABILIZE))

    outcomes = _analyse(log, {"ATC_ANGLE_MAX": 30.0})

    assert [outcome.param_name for outcome in outcomes] == ["ATC_ANGLE_MAX"]


def test_loiter_final_target_uses_position_ceiling_and_other_modes_use_vehicle_ceiling() -> None:
    """
    Final Loiter targets are checked against the position-controller ceiling.

    GIVEN 20 deg lean in Loiter for the first half of the log and 20 deg lean in Stabilize afterwards
    WHEN PSC_ANGLE_MAX is 20, LOIT_ANG_MAX is 10 and ANGLE_MAX is 45 deg
    THEN only the Loiter portion is reported, against PSC_ANGLE_MAX
    """
    log = LogData(vehicle_type="ArduCopter")
    roll = np.full(SAMPLES, 20.0)
    _add_att(log, roll)
    _add_modes(log, (0.0, LOITER), (50.0, STABILIZE))

    outcomes = _analyse(log, {"ANGLE_MAX": 4500.0, "PSC_ANGLE_MAX": 20.0, "LOIT_ANG_MAX": 10.0})

    assert [outcome.param_name for outcome in outcomes] == ["PSC_ANGLE_MAX"]
    assert outcomes[0].evidence is not None
    assert outcomes[0].evidence["saturated_percent"] == pytest.approx(100.0)
    assert outcomes[0].evidence["saturated_seconds"] == pytest.approx(50.0, abs=1.0)
    assert "position controller" in outcomes[0].message


@pytest.mark.parametrize("pilot_limit", [None, 0.0, 20.0])
def test_loiter_position_corrections_above_the_pilot_limit_are_not_reported(pilot_limit: float | None) -> None:
    """
    Loiter position corrections can exceed the pilot's lean limit.

    GIVEN 20 deg lean in Loiter
    WHEN ANGLE_MAX is 3000 cdeg and LOIT_ANG_MAX is absent, zero or 20 deg
    THEN no saturation is reported against the pilot limit
    """
    log = LogData(vehicle_type="ArduCopter")
    _add_att(log, np.full(SAMPLES, 20.0))
    _add_modes(log, (0.0, LOITER))

    parameters = {"ANGLE_MAX": 3000.0}
    if pilot_limit is not None:
        parameters["LOIT_ANG_MAX"] = pilot_limit
    assert not _analyse(log, parameters)


def test_psc_angle_max_limits_position_controlled_modes() -> None:
    """
    Psc angle max limits position controlled modes.

    GIVEN 25 deg lean in Auto mode
    WHEN PSC_ANGLE_MAX is 25 and ANGLE_MAX is 45 deg
    THEN saturation is reported against PSC_ANGLE_MAX
    """
    log = LogData(vehicle_type="ArduCopter")
    _add_att(log, np.full(SAMPLES, 25.0))
    _add_modes(log, (0.0, 3))

    outcomes = _analyse(log, {"ANGLE_MAX": 4500.0, "PSC_ANGLE_MAX": 25.0})

    assert [outcome.param_name for outcome in outcomes] == ["PSC_ANGLE_MAX"]


@pytest.mark.parametrize("mode", [9, 22], ids=["land", "flowhold"])
@pytest.mark.parametrize(
    "parameters",
    [
        {"ANGLE_MAX": 4500.0, "PSC_ANGLE_MAX": 20.0},
        {"ANGLE_MAX": 2000.0},
        {"ATC_ANGLE_MAX": 20.0},
    ],
    ids=["position-ceiling", "legacy-vehicle-ceiling", "vehicle-ceiling"],
)
def test_land_and_flowhold_do_not_receive_inferred_lean_limit_advice(mode: int, parameters: dict[str, float]) -> None:
    """
    Modes with unproven horizontal control or different angle constraints retain independent findings.

    GIVEN Land or FlowHold targets at an apparent lean ceiling and prolonged roll-rate limiting
    WHEN the user analyses the log with position or vehicle lean limits
    THEN only the independent rate-limit finding is reported
    """
    log = LogData(vehicle_type="ArduCopter")
    _add_att(log, np.full(SAMPLES, 20.0))
    _add_rate(log, RDes=_window(0.3, 200.0))
    _add_modes(log, (0.0, mode))

    outcomes = _analyse(log, {**parameters, "ATC_RATE_R_MAX": 200.0})

    assert [outcome.param_name for outcome in outcomes] == ["ATC_RATE_R_MAX"]


@pytest.mark.parametrize("mode", [9, 22], ids=["land", "flowhold"])
def test_land_and_flowhold_intervals_do_not_count_towards_loiter_saturation(mode: int) -> None:
    """
    Excluded modes do not extend lean-limit findings across gaps between supported modes.

    GIVEN sparse attitude samples with Land or FlowHold between Loiter intervals at the position ceiling
    WHEN the user analyses the log
    THEN only the sixty seconds in Loiter count towards the lean-limit finding
    """
    log = LogData(vehicle_type="ArduCopter")
    log.add_message_columns("ATT", _array(TimeUS=[0.0, 100.0], DesRoll=[20.0] * 2, DesPitch=[0.0] * 2))
    _add_modes(log, (0.0, LOITER), (30.0, mode), (70.0, LOITER))

    outcomes = _analyse(log, {"ANGLE_MAX": 4500.0, "PSC_ANGLE_MAX": 20.0})

    assert [outcome.param_name for outcome in outcomes] == ["PSC_ANGLE_MAX"]
    assert outcomes[0].evidence is not None
    assert outcomes[0].evidence["saturated_seconds"] == pytest.approx(60.0)
    assert outcomes[0].value == pytest.approx(100.0)
    assert outcomes[0].end_timestamp_us == 100e6


def test_modes_that_bypass_the_lean_limit_are_not_reported() -> None:
    """
    Modes that bypass the lean limit are not reported.

    GIVEN a full-limit lean angle in Acro
    WHEN the analysis runs
    THEN no lean-angle saturation is reported
    """
    log = LogData(vehicle_type="ArduCopter")
    _add_att(log, np.full(SAMPLES, 45.0))
    _add_modes(log, (0.0, ACRO))

    assert not _analyse(log, {"ANGLE_MAX": 3000.0})


@pytest.mark.parametrize("mode", [4, 20])
@pytest.mark.parametrize("attitude_command_logged", [False, True])
def test_guided_attitude_targets_do_not_produce_position_limit_advice(mode: int, attitude_command_logged: bool) -> None:
    """
    Externally commanded attitudes do not imply a position-controller lean limit.

    GIVEN Guided or Guided_NoGPS targets at PSC_ANGLE_MAX, with or without attitude-target telemetry
    WHEN the analysis runs
    THEN lean-limit advice is omitted while an independent rate-limit finding is retained
    """
    log = LogData(vehicle_type="ArduCopter")
    _add_att(log, np.full(SAMPLES, 30.0))
    _add_rate(log, RDes=_window(0.3, 200.0))
    _add_modes(log, (0.0, mode))
    if attitude_command_logged:
        log.add_message_columns("GUIA", _array(TimeUS=[0.0], Type=[6.0]))

    outcomes = _analyse(log, {"ANGLE_MAX": 3000.0, "PSC_ANGLE_MAX": 30.0, "ATC_RATE_R_MAX": 200.0})

    assert [outcome.param_name for outcome in outcomes] == ["ATC_RATE_R_MAX"]


@pytest.mark.parametrize("mode", [3, 4])
def test_guided_submode_changes_between_samples_bound_position_limit_findings(mode: int) -> None:
    """
    Auto and Guided position-control periods retain their own duration when commands change submode.

    GIVEN sparse Auto or Guided attitude samples and position targets interrupted by attitude commands from 30 to 70 seconds
    WHEN the lean-limit check runs
    THEN only the sixty position-controlled seconds are reported
    """
    log = LogData(vehicle_type="ArduCopter")
    log.add_message_columns("ATT", _array(TimeUS=[0.0, 100.0], DesRoll=[30.0] * 2, DesPitch=[0.0] * 2))
    _add_modes(log, (0.0, mode))
    log.add_message_columns("GUIP", _array(TimeUS=[70.0, 0.0], Type=[2.0, 2.0]))
    log.add_message_columns("GUIA", _array(TimeUS=[30.0], Type=[6.0]))

    outcomes = _analyse(log, {"ANGLE_MAX": 4500.0, "PSC_ANGLE_MAX": 30.0})

    assert [outcome.param_name for outcome in outcomes] == ["PSC_ANGLE_MAX"]
    assert outcomes[0].evidence is not None
    assert outcomes[0].evidence["saturated_seconds"] == pytest.approx(60.0)
    assert outcomes[0].value == pytest.approx(100.0)
    assert outcomes[0].end_timestamp_us == 100e6


@pytest.mark.parametrize("resume_message", [None, "MODE", "CMD", "MISE", "GUIP"])
def test_auto_attitude_legs_are_skipped_until_navigation_resumes(resume_message: str | None) -> None:
    """
    Auto attitude commands bypass the position ceiling until navigation resumes.

    GIVEN sparse Auto attitude samples with a GUIA command at 30 seconds
    WHEN navigation resumes at 70 seconds through MODE, CMD, MISE or GUIP, or never resumes
    THEN only the position-controlled time receives lean-limit advice
    """
    log = LogData(vehicle_type="ArduCopter")
    log.add_message_columns("ATT", _array(TimeUS=[0.0, 100.0], DesRoll=[30.0] * 2, DesPitch=[0.0] * 2))
    _add_modes(log, (0.0, 3))
    log.add_message_columns("GUIA", _array(TimeUS=[30.0], Type=[6.0]))
    if resume_message == "MODE":
        _add_modes(log, (0.0, 3), (70.0, 3))
    elif resume_message in {"CMD", "MISE"}:
        log.add_message_columns(resume_message, _array(TimeUS=[70.0], CId=[16.0]))
    elif resume_message is not None:
        log.add_message_columns(resume_message, _array(TimeUS=[70.0]))

    outcomes = _analyse(log, {"ANGLE_MAX": 4500.0, "PSC_ANGLE_MAX": 30.0})

    assert [outcome.param_name for outcome in outcomes] == ["PSC_ANGLE_MAX"]
    assert outcomes[0].evidence is not None
    assert outcomes[0].evidence["saturated_seconds"] == pytest.approx(30.0 if resume_message is None else 60.0)
    assert outcomes[0].value == pytest.approx(100.0)
    assert outcomes[0].end_timestamp_us == (30e6 if resume_message is None else 100e6)


@pytest.mark.parametrize("reset_message", ["MODE", "CMD", "MISE", "GUIP"])
def test_auto_attitude_targets_override_simultaneous_navigation_events(reset_message: str) -> None:
    """
    Auto attitude legs do not produce false position-limit advice or hide independent findings.

    GIVEN Auto attitude targets at PSC_ANGLE_MAX and a simultaneous MODE, CMD, MISE or GUIP event
    WHEN the attitude saturation analysis runs
    THEN only the independent rate-limit finding is retained
    """
    log = LogData(vehicle_type="ArduCopter")
    _add_att(log, np.full(SAMPLES, 30.0))
    _add_rate(log, RDes=_window(0.3, 200.0))
    _add_modes(log, (0.0, 3))
    log.add_message_columns("GUIA", _array(TimeUS=[0.0], Type=[6.0]))
    if reset_message in {"CMD", "MISE"}:
        log.add_message_columns(reset_message, _array(TimeUS=[0.0], CId=[16.0]))
    elif reset_message != "MODE":
        log.add_message_columns(reset_message, _array(TimeUS=[0.0]))

    outcomes = _analyse(log, {"ANGLE_MAX": 3000.0, "PSC_ANGLE_MAX": 30.0, "ATC_RATE_R_MAX": 200.0})

    assert [outcome.param_name for outcome in outcomes] == ["ATC_RATE_R_MAX"]


@pytest.mark.parametrize("mission_message", ["MISE", "CMD"])
@pytest.mark.parametrize("attitude_command", [42703, 42702, 92])
def test_auto_mission_attitude_legs_ignore_parallel_do_and_condition_items(
    mission_message: str, attitude_command: int
) -> None:
    """
    Mission navigation transitions bound Auto attitude legs even without GUIA telemetry.

    GIVEN an Auto NAV_ATTITUDE_TIME, NAV_SCRIPT_TIME or NAVGUIDED attitude leg between 30 and 70 seconds
    WHEN DO_CHANGE_SPEED and CONDITION_DELAY execute alongside it before the next waypoint
    THEN only the sixty position-controlled seconds receive PSC_ANGLE_MAX advice
    """
    log = LogData(vehicle_type="ArduCopter")
    log.add_message_columns("ATT", _array(TimeUS=[0.0, 100.0], DesRoll=[30.0] * 2, DesPitch=[0.0] * 2))
    _add_modes(log, (0.0, 3))
    log.add_message_columns(
        mission_message,
        _array(TimeUS=[0.0, 30.0, 50.0, 60.0, 70.0], CId=[16, attitude_command, 178, 112, 16]),
    )
    if attitude_command != 42703:
        log.add_message_columns("GUIA", _array(TimeUS=[30.0], Type=[6.0]))

    outcomes = _analyse(log, {"ANGLE_MAX": 4500.0, "PSC_ANGLE_MAX": 30.0})

    assert [outcome.param_name for outcome in outcomes] == ["PSC_ANGLE_MAX"]
    assert outcomes[0].evidence is not None
    assert outcomes[0].evidence["saturated_seconds"] == pytest.approx(60.0)
    assert outcomes[0].value == pytest.approx(100.0)
    assert outcomes[0].end_timestamp_us == 100e6


def test_auto_uses_mise_execution_instead_of_uploaded_cmd_dump() -> None:
    """
    Uploaded mission contents do not change the current Auto navigation state.

    GIVEN a GUIA leg from 30 to 70 seconds with MISE execution and a CMD mission dump
    WHEN the dump contains waypoints during the attitude leg and NAV_ATTITUDE_TIME after it
    THEN only the sixty position-controlled seconds receive PSC_ANGLE_MAX advice
    """
    log = LogData(vehicle_type="ArduCopter")
    log.add_message_columns("ATT", _array(TimeUS=[0.0, 100.0], DesRoll=[30.0] * 2, DesPitch=[0.0] * 2))
    _add_modes(log, (0.0, 3))
    log.add_message_columns("GUIA", _array(TimeUS=[30.0], Type=[6.0]))
    log.add_message_columns("MISE", _array(TimeUS=[0.0, 70.0], CId=[16, 16]))
    log.add_message_columns("CMD", _array(TimeUS=[40.0, 80.0], CId=[16, 42703]))

    outcomes = _analyse(log, {"ANGLE_MAX": 4500.0, "PSC_ANGLE_MAX": 30.0})

    assert [outcome.param_name for outcome in outcomes] == ["PSC_ANGLE_MAX"]
    assert outcomes[0].evidence is not None
    assert outcomes[0].evidence["saturated_seconds"] == pytest.approx(60.0)


def test_guided_reentry_requires_new_position_target_evidence() -> None:
    """
    Reentering Guided cannot reuse a previous flight-mode session's submode evidence.

    GIVEN position targets before leaving Guided, followed by reentry and later attitude and position commands
    WHEN the lean-limit check runs
    THEN the unknown reentry period and attitude-command period do not count
    """
    log = LogData(vehicle_type="ArduCopter")
    log.add_message_columns("ATT", _array(TimeUS=[0.0, 100.0], DesRoll=[30.0] * 2, DesPitch=[0.0] * 2))
    _add_modes(log, (0.0, 4), (40.0, STABILIZE), (60.0, 4))
    log.add_message_columns("GUIP", _array(TimeUS=[0.0, 90.0], Type=[2.0, 2.0]))
    log.add_message_columns("GUIA", _array(TimeUS=[70.0], Type=[6.0]))

    outcomes = _analyse(log, {"ANGLE_MAX": 4500.0, "PSC_ANGLE_MAX": 30.0})

    assert [outcome.param_name for outcome in outcomes] == ["PSC_ANGLE_MAX"]
    assert outcomes[0].evidence is not None
    assert outcomes[0].evidence["saturated_seconds"] == pytest.approx(50.0)


def test_pilot_and_position_modes_keep_distinct_advice_when_using_the_same_limit() -> None:
    """
    A position ceiling falling back to ANGLE_MAX retains position-control advice.

    GIVEN full-range lean in Stabilize and Loiter, both using ANGLE_MAX
    WHEN the analysis runs
    THEN pilot-input usage and position-controller limiting receive separate findings
    """
    log = LogData(vehicle_type="ArduCopter")
    _add_att(log, np.full(SAMPLES, 30.0))
    _add_modes(log, (0.0, STABILIZE), (50.0, LOITER))

    outcomes = _analyse(log, {"ANGLE_MAX": 3000.0})

    assert len(outcomes) == 2
    pilot, position = outcomes
    assert pilot.param_name == position.param_name == "ANGLE_MAX"
    assert "full pilot lean range" in pilot.message
    assert "Raise ANGLE_MAX" not in pilot.message
    assert "demanded acceleration" in position.message
    assert "Raise ANGLE_MAX" in position.message
    assert pilot.evidence is not None
    assert position.evidence is not None
    assert pilot.evidence["saturated_seconds"] == pytest.approx(50.0)
    assert position.evidence["saturated_seconds"] == pytest.approx(49.9)


def test_lean_angle_below_the_limit_is_not_reported() -> None:
    log = LogData(vehicle_type="ArduCopter")
    _add_att(log, np.full(SAMPLES, 15.0))
    _add_modes(log, (0.0, STABILIZE))

    assert not _analyse(log, {"ANGLE_MAX": 3000.0})


def test_analysis_without_any_attitude_parameters_reports_nothing() -> None:
    log = LogData(vehicle_type="ArduCopter")
    _add_att(log, np.full(SAMPLES, 45.0))

    assert not _analyse(log, {})


def test_availability_is_unavailable_and_suggests_logging_bit_when_attitude_logging_is_off() -> None:
    """
    Availability is unavailable and suggests logging bit when attitude logging is off.

    GIVEN no ATT, RATE or PID messages and LOG_BITMASK without attitude bits
    WHEN availability is checked
    THEN the user is told to enable attitude logging and gets the suggested bitmask
    """
    context = _context(
        {"LOG_BITMASK": 0.0}, apm_doc={"LOG_BITMASK": {"fields": {"Bitmask": "0:Fast Attitude,1:Medium Attitude,12:PID"}}}
    )

    result = AttitudeSaturationLogAvailabilityModel(LogData(vehicle_type="ArduCopter"), context).check()

    assert result.available is False
    assert result.state == LogAvailabilityState.WARNING
    assert result.issues[0].param_name == "LOG_BITMASK"
    assert result.issues[0].suggested_value == 2.0


def test_availability_reports_missing_pid_logging_when_only_attitude_is_logged() -> None:
    """
    Availability reports missing pid logging when only attitude is logged.

    GIVEN ATT and RATE data without PID messages and PID logging disabled
    WHEN availability is checked
    THEN the analysis is available but the user is told how to enable PID logging
    """
    log = LogData(vehicle_type="ArduCopter")
    _add_att(log, np.zeros(SAMPLES))
    _add_rate(log)
    context = _context({"LOG_BITMASK": 0.0}, apm_doc={"LOG_BITMASK": {"fields": {"Bitmask": "0:Fast Attitude,12:PID"}}})

    result = AttitudeSaturationLogAvailabilityModel(log, context).check()

    assert result.available is True
    assert result.state == LogAvailabilityState.WARNING
    assert result.issues[0].param_name == "LOG_BITMASK"
    assert result.issues[0].suggested_value == float(1 << 12)


@pytest.mark.parametrize("empty_rate_records", [False, True])
@pytest.mark.parametrize("vehicle_type", ["ArduCopter", "Heli"])
def test_missing_rate_logging_warns_and_preserves_pid_analysis(vehicle_type: str, empty_rate_records: bool) -> None:
    """
    Missing RATE data warns about skipped rate limits while other saturation checks remain available.

    GIVEN ATT and PID data with PID logging enabled but both attitude logging bits disabled
    WHEN availability and saturation are checked without RATE records
    THEN the user gets an attitude logging fix and the PID slew-limit finding is retained
    """
    log = LogData(vehicle_type=vehicle_type)
    _add_att(log, np.zeros(SAMPLES))
    for message in ("PIDR", "PIDP", "PIDY"):
        _add_pid(log, message, dmod=_window(0.2, 0.3, base=1.0))
    if empty_rate_records:
        log.add_message_columns("RATE", _array(TimeUS=[], RDes=[], PDes=[], YDes=[]))
    context = _context(
        {"LOG_BITMASK": float(1 << 12), "ATC_RAT_RLL_SMAX": 25.0, "ATC_RATE_R_MAX": 200.0},
        apm_doc={"LOG_BITMASK": {"fields": {"Bitmask": "0:Fast Attitude,1:Medium Attitude,12:PID"}}},
    )

    result = AttitudeSaturationLogAvailabilityModel(log, context).check()
    outcomes = AttitudeSaturationLogAnalysis(log, context).analyse().outcomes

    assert result.available is True
    assert result.state == LogAvailabilityState.WARNING
    assert len(result.issues) == 1
    issue = result.issues[0]
    assert "No RATE messages" in issue.message
    assert "ATC_RATE_*_MAX" in issue.message
    assert "skipped" in issue.message
    assert "Fast Attitude or Medium Attitude" in issue.message
    assert "LOG_BITMASK" in issue.message
    assert issue.config_step == "28_attitude.param"
    assert issue.param_name == "LOG_BITMASK"
    assert issue.suggested_value == float((1 << 12) | (1 << 1))
    assert [outcome.param_name for outcome in outcomes] == ["ATC_RAT_RLL_SMAX"]


@pytest.mark.parametrize(
    ("bitmask", "metadata"),
    [
        (4097.0, "0:Fast Attitude,1:Medium Attitude,12:PID"),
        (4098.0, "0:Fast Attitude,1:Medium Attitude,12:PID"),
        (None, "0:Fast Attitude,1:Medium Attitude,12:PID"),
        (4096.0, None),
        (4096.0, "12:PID"),
    ],
)
def test_missing_rate_records_warn_without_an_unverified_logging_fix(bitmask: float | None, metadata: str | None) -> None:
    """
    Missing RATE telemetry is reported without inventing an unnecessary or unknown bitmask change.

    GIVEN ATT and PID data with attitude logging enabled or incomplete LOG_BITMASK information
    WHEN availability is checked without RATE records
    THEN the skipped rate-limit check is reported without an automatic logging fix
    """
    log = LogData(vehicle_type="ArduCopter")
    _add_att(log, np.zeros(SAMPLES))
    _add_pid(log, "PIDR")
    context = _context(
        {} if bitmask is None else {"LOG_BITMASK": bitmask},
        apm_doc=None if metadata is None else {"LOG_BITMASK": {"fields": {"Bitmask": metadata}}},
    )

    result = AttitudeSaturationLogAvailabilityModel(log, context).check()

    assert result.available is True
    assert result.state == LogAvailabilityState.WARNING
    assert len(result.issues) == 1
    assert "ATC_RATE_*_MAX" in result.issues[0].message
    assert result.issues[0].param_name is None
    assert result.issues[0].suggested_value is None


def test_availability_is_clean_when_all_messages_are_present() -> None:
    log = LogData(vehicle_type="ArduCopter")
    _add_att(log, np.zeros(SAMPLES))
    _add_rate(log)
    for message in ("PIDR", "PIDP", "PIDY"):
        _add_pid(log, message)

    result = AttitudeSaturationLogAvailabilityModel(log, _context({})).check()

    assert result.available is True
    assert result.state == LogAvailabilityState.INFO
    assert not result.issues


def test_attitude_saturation_analysis_is_registered_in_the_default_subsystems() -> None:
    spec = next(spec for spec in LOG_ANALYSIS_SUBSYSTEMS if spec.key == "attitude_saturation")

    assert spec.availability_model is AttitudeSaturationLogAvailabilityModel
    assert spec.analysis_model is AttitudeSaturationLogAnalysis


@pytest.mark.parametrize(
    ("transitions", "duration"),
    [
        ([(40.0, 1)], 59.9),
        ([(0.0, 0), (40.0, 1), (50.0, 1), (70.0, 0)], 30.0),
        ([(70.0, 0), (40.0, 1)], 30.0),
        ([(40.0, 0)], 40.0),
        ([(99.9, 1)], 0.0),
    ],
)
def test_arm_transitions_bound_observed_time_including_a_missing_initial_arm(
    transitions: list[tuple[float, int]], duration: float
) -> None:
    """
    ARM transitions infer the initial state and survive an unfinished log.

    GIVEN rate targets at the limit and complete, incomplete or disarm-only ARM telemetry
    WHEN the user analyses the log
    THEN the state before the first transition is its opposite, and zero-duration intervals produce no finding
    """
    log = LogData(vehicle_type="ArduCopter")
    _add_rate(log, RDes=np.full(SAMPLES, 200.0))
    log.add_message_columns("ARM", _array(TimeUS=[t for t, _ in transitions], ArmState=[state for _, state in transitions]))

    outcomes = _analyse(log, {"ATC_RATE_R_MAX": 200.0})

    if duration == 0.0:
        assert not outcomes
    else:
        assert len(outcomes) == 1
        assert outcomes[0].evidence is not None
        assert outcomes[0].evidence["saturated_seconds"] == pytest.approx(duration)
        assert outcomes[0].evidence["saturated_percent"] == pytest.approx(100.0)


def test_arm_and_disarm_between_samples_bound_the_reported_duration() -> None:
    """
    Arming changes between samples bound the duration of a finding.

    GIVEN rate samples ten seconds apart and an armed interval from five to fifteen seconds
    WHEN the user analyses the log
    THEN the finding covers exactly the ten armed seconds
    """
    log = LogData(vehicle_type="ArduCopter")
    log.add_message_columns("RATE", _array(TimeUS=[0.0, 10.0, 20.0], RDes=[200.0] * 3))
    log.add_message_columns("ARM", _array(TimeUS=[5.0, 15.0], ArmState=[1.0, 0.0]))

    outcomes = _analyse(log, {"ATC_RATE_R_MAX": 200.0})

    assert len(outcomes) == 1
    assert outcomes[0].timestamp_us == 5e6
    assert outcomes[0].end_timestamp_us == 15e6
    assert outcomes[0].evidence is not None
    assert outcomes[0].evidence["saturated_seconds"] == pytest.approx(10.0)


@pytest.mark.parametrize("vehicle_type", ["ArduPlane", "Rover", "ArduSub", None])
def test_other_or_unknown_vehicle_types_do_not_receive_copter_limit_advice(vehicle_type: str | None) -> None:
    """
    Copter-specific advice is omitted for incompatible or unknown vehicles.

    GIVEN saturated attitude telemetry from another or unidentified vehicle
    WHEN the user checks availability and analyses it
    THEN the subsystem is unavailable without Copter parameter advice
    """
    log = LogData(vehicle_type=vehicle_type)
    _add_rate(log, RDes=np.full(SAMPLES, 200.0))
    _add_pid(log, "PIDR", dmod=np.full(SAMPLES, 0.3), flags=np.full(SAMPLES, 2.0))
    context = _context({"ATC_RATE_R_MAX": 200.0, "ATC_RAT_RLL_SMAX": 25.0, "ATC_RAT_RLL_PDMX": 0.5})

    availability = AttitudeSaturationLogAvailabilityModel(log, context).check()
    analysis = AttitudeSaturationLogAnalysis(log, context).analyse()

    assert not availability.available
    assert availability.state == LogAvailabilityState.INFO
    assert not availability.issues
    assert not analysis.available
    assert not analysis.outcomes


@pytest.mark.parametrize("vehicle_type", ["ArduCopter", "Heli"])
def test_copter_and_helicopter_logs_can_receive_attitude_limit_findings(vehicle_type: str) -> None:
    """
    Copter and helicopter logs receive supported limit findings.

    GIVEN a supported vehicle with rate targets at its configured limit
    WHEN the user analyses the log
    THEN the configured parameter is identified
    """
    log = LogData(vehicle_type=vehicle_type)
    _add_rate(log, RDes=_window(0.3, 200.0))

    assert [outcome.param_name for outcome in _analyse(log, {"ATC_RATE_R_MAX": 200.0})] == ["ATC_RATE_R_MAX"]


@pytest.mark.parametrize("limit", [None, 0.0, -1.0])
def test_pid_flags_and_gain_reduction_need_a_present_enabled_limit(limit: float | None) -> None:
    """
    Controller telemetry cannot invent a missing limiter parameter.

    GIVEN gain reductions and PD-limit flags with absent or disabled parameters
    WHEN the user analyses the log
    THEN neither limiter is reported
    """
    log = LogData(vehicle_type="ArduCopter")
    _add_pid(log, "PIDR", dmod=np.full(SAMPLES, 0.3), flags=np.full(SAMPLES, 2.0))
    parameters = {} if limit is None else {"ATC_RAT_RLL_SMAX": limit, "ATC_RAT_RLL_PDMX": limit}

    assert not _analyse(log, parameters)


@pytest.mark.parametrize("roll_sign", [-1.0, 1.0])
def test_combined_roll_pitch_targets_reach_the_elliptical_limit(roll_sign: float) -> None:
    """
    Combined roll and pitch demands can reach the shared limit below either axis maximum.

    GIVEN roll at 60% and pitch at 80% of unequal configured limits
    WHEN the user analyses a prolonged combined demand
    THEN one finding names both parameters and reports the shared envelope
    """
    log = LogData(vehicle_type="ArduCopter")
    _add_rate(log, RDes=_window(0.3, roll_sign * 60.0), PDes=_window(0.3, 64.0))

    outcomes = _analyse(log, {"ATC_RATE_R_MAX": 100.0, "ATC_RATE_P_MAX": 80.0})

    assert len(outcomes) == 1
    assert outcomes[0].severity == "critical"
    assert "ATC_RATE_R_MAX" in outcomes[0].message
    assert "ATC_RATE_P_MAX" in outcomes[0].message
    assert outcomes[0].evidence is not None
    assert outcomes[0].evidence["roll_limit"] == 100.0
    assert outcomes[0].evidence["pitch_limit"] == 80.0


def test_disabled_pitch_limit_leaves_only_the_roll_axis_limit() -> None:
    """
    A disabled pitch limit cannot contribute to the roll envelope.

    GIVEN roll below its limit and a large pitch rate with pitch limiting disabled
    WHEN the user analyses the log
    THEN no combined-limit finding is produced
    """
    log = LogData(vehicle_type="ArduCopter")
    _add_rate(log, RDes=np.full(SAMPLES, 60.0), PDes=np.full(SAMPLES, 800.0))

    assert not _analyse(log, {"ATC_RATE_R_MAX": 100.0, "ATC_RATE_P_MAX": 0.0})


def test_invalid_data_for_disabled_axes_does_not_hide_a_valid_rate_finding() -> None:
    """
    A valid enabled axis can be checked without unrelated telemetry.

    GIVEN roll targets at the limit and non-finite pitch and yaw targets
    WHEN only the roll limit is enabled
    THEN the roll finding remains available
    """
    log = LogData(vehicle_type="ArduCopter")
    _add_rate(log, RDes=_window(0.3, 200.0), PDes=np.full(SAMPLES, np.nan), YDes=np.full(SAMPLES, np.nan))

    assert [outcome.param_name for outcome in _analyse(log, {"ATC_RATE_R_MAX": 200.0})] == ["ATC_RATE_R_MAX"]


@pytest.mark.parametrize("message", ["RATE", "PIDR"])
def test_a_dense_short_burst_is_not_mistaken_for_long_saturation(message: str) -> None:
    """
    Dense samples do not exaggerate a short limiter episode.

    GIVEN three saturated samples covering 0.03 seconds in a hundred-second log
    WHEN the user analyses the unevenly sampled data
    THEN no duration or percentage threshold is met
    """
    log = LogData(vehicle_type="ArduCopter")
    times = [0.0, 0.01, 0.02, 0.03, 100.0]
    fields = {"RDes": [200.0, 200.0, 200.0, 0.0, 0.0]} if message == "RATE" else {"Dmod": [0.3, 0.3, 0.3, 1.0, 1.0]}
    log.add_message_columns(message, _array(TimeUS=times, **fields))

    assert not _analyse(log, {"ATC_RATE_R_MAX": 200.0, "ATC_RAT_RLL_SMAX": 25.0})


def test_uneven_sampling_reports_elapsed_duration_instead_of_sample_fraction() -> None:
    """
    Limiter duration follows elapsed time between the original samples.

    GIVEN one saturated interval lasting ninety seconds in a hundred-second log
    WHEN the user analyses the sparse rate samples
    THEN the finding reports ninety seconds and ninety percent
    """
    log = LogData(vehicle_type="ArduCopter")
    log.add_message_columns("RATE", _array(TimeUS=[0.0, 90.0, 90.1, 100.0], RDes=[200.0, 0.0, 0.0, 0.0]))

    outcomes = _analyse(log, {"ATC_RATE_R_MAX": 200.0})

    assert len(outcomes) == 1
    assert outcomes[0].evidence is not None
    assert outcomes[0].evidence["saturated_seconds"] == pytest.approx(90.0)
    assert outcomes[0].value == pytest.approx(90.0)
    assert outcomes[0].timestamp_us == 0.0
    assert outcomes[0].end_timestamp_us == 90e6


def test_separate_loiter_intervals_do_not_count_the_time_between_them() -> None:
    """
    Separated Loiter samples retain their original interval weights.

    GIVEN two one-second Loiter intervals separated by a long Stabilize phase
    WHEN the user analyses targets at the Loiter position ceiling
    THEN only two seconds are reported
    """
    log = LogData(vehicle_type="ArduCopter")
    log.add_message_columns("ATT", _array(TimeUS=[0.0, 1.0, 2.0, 100.0, 101.0, 102.0], DesRoll=[25.0] * 6, DesPitch=[0.0] * 6))
    _add_modes(log, (0.0, LOITER), (1.0, STABILIZE), (100.0, LOITER), (101.0, STABILIZE))

    outcomes = _analyse(log, {"ANGLE_MAX": 4500.0, "PSC_ANGLE_MAX": 25.0})

    assert len(outcomes) == 1
    assert outcomes[0].evidence is not None
    assert outcomes[0].evidence["saturated_seconds"] == pytest.approx(2.0)
    assert outcomes[0].value == pytest.approx(100.0)


@pytest.mark.parametrize("first_mode", [None, 90.0])
def test_lean_targets_without_a_known_mode_are_skipped(first_mode: float | None) -> None:
    """
    Lean targets need a known applicable flight mode.

    GIVEN full-limit targets before the first MODE record or without MODE telemetry
    WHEN the user analyses the log
    THEN unknown-mode samples do not produce findings
    """
    log = LogData(vehicle_type="ArduCopter")
    _add_att(log, _window(0.2, 30.0))
    if first_mode is not None:
        _add_modes(log, (first_mode, STABILIZE))

    assert not _analyse(log, {"ANGLE_MAX": 3000.0})


@pytest.mark.parametrize("target", [35.0, 45.0])
def test_position_ceiling_can_be_higher_than_the_vehicle_pilot_limit(target: float) -> None:
    """
    An explicit PSC angle limit overrides the vehicle pilot limit.

    GIVEN Auto targets above the pilot limit of thirty degrees
    WHEN PSC_ANGLE_MAX is forty-five degrees
    THEN only targets reaching forty-five degrees produce a finding
    """
    log = LogData(vehicle_type="ArduCopter")
    _add_att(log, np.full(SAMPLES, target))
    _add_modes(log, (0.0, 3))

    outcomes = _analyse(log, {"ANGLE_MAX": 3000.0, "PSC_ANGLE_MAX": 45.0})

    assert [outcome.param_name for outcome in outcomes] == (["PSC_ANGLE_MAX"] if target == 45.0 else [])


@pytest.mark.parametrize(
    "limiter",
    [
        ("RATE", "RDes", 200.0, "ATC_RATE_R_MAX", 200.0),
        ("PIDR", "Dmod", 0.3, "ATC_RAT_RLL_SMAX", 25.0),
        ("PIDR", "Flags", 2.0, "ATC_RAT_RLL_PDMX", 0.5),
    ],
)
@pytest.mark.parametrize("initially_enabled", [False, True])
def test_limit_checks_use_the_parameter_value_active_during_the_incident(
    limiter: tuple[str, str, float, str, float], initially_enabled: bool
) -> None:
    """
    Later parameter changes cannot rewrite an earlier limiter episode.

    GIVEN limiter evidence only in the first thirty seconds and an enable change at fifty seconds
    WHEN the user analyses the log with the final value and timestamped history
    THEN the episode is reported only if the limiter was enabled then
    """
    message, field, value, parameter, limit = limiter
    log = LogData(vehicle_type="ArduCopter")
    baseline = 1.0 if field == "Dmod" else 0.0
    log.add_message_columns(message, _array(TimeUS=_time(), **{field: _window(0.3, value, baseline)}))
    initial, final = (limit, 0.0) if initially_enabled else (0.0, limit)
    history = ParameterHistory(initial_values={parameter: initial}, changes={parameter: (ParameterChange(50.0, final),)})

    outcomes = _analyse(log, {parameter: final}, history)

    assert [outcome.param_name for outcome in outcomes] == ([parameter] if initially_enabled else [])
    if outcomes:
        assert outcomes[0].evidence is not None
        assert outcomes[0].evidence["saturated_seconds"] == pytest.approx(30.0)


def test_parameter_changes_between_samples_bound_the_active_limit_duration() -> None:
    """
    A setting changed between samples applies at its logged timestamp.

    GIVEN ten-second rate samples and a limiter enabled only from five to fifteen seconds
    WHEN the user analyses the historical setting
    THEN exactly ten of the twenty observed seconds are reported
    """
    log = LogData(vehicle_type="ArduCopter")
    log.add_message_columns("RATE", _array(TimeUS=[0.0, 10.0, 20.0], RDes=[200.0] * 3))
    history = ParameterHistory(
        initial_values={"ATC_RATE_R_MAX": 0.0},
        changes={"ATC_RATE_R_MAX": (ParameterChange(5.0, 200.0), ParameterChange(15.0, 0.0))},
    )

    outcomes = _analyse(log, {"ATC_RATE_R_MAX": 0.0}, history)

    assert len(outcomes) == 1
    assert outcomes[0].value == pytest.approx(50.0)
    assert outcomes[0].evidence is not None
    assert outcomes[0].evidence["saturated_seconds"] == pytest.approx(10.0)


def test_lean_angle_check_uses_historical_limits() -> None:
    """
    Lean targets are compared with the limit active at each time.

    GIVEN thirty-degree targets and an angle limit raised from thirty to forty-five degrees halfway through
    WHEN the user analyses the parameter history
    THEN only the first fifty seconds reach the limit
    """
    log = LogData(vehicle_type="ArduCopter")
    _add_att(log, np.full(SAMPLES, 30.0))
    _add_modes(log, (0.0, STABILIZE))
    history = ParameterHistory(initial_values={"ANGLE_MAX": 3000.0}, changes={"ANGLE_MAX": (ParameterChange(50.0, 4500.0),)})

    outcomes = _analyse(log, {"ANGLE_MAX": 4500.0}, history)

    assert len(outcomes) == 1
    assert outcomes[0].evidence is not None
    assert outcomes[0].evidence["saturated_seconds"] == pytest.approx(50.0)


# Samples spaced 0.5 s apart keep every duration exact in binary floating point, so fractions can land on the
# thresholds exactly: 101 samples give 100 intervals of 0.5 s, i.e. 50 s of armed time.
HALF_SECOND = 0.5
BOUNDARY_SAMPLES = 101


def _leading(count: int, value: float, total: int, base: float = 0.0) -> np.ndarray:
    """Return a series that holds ``value`` for the first ``count`` samples and ``base`` afterwards."""
    series = np.full(total, base)
    series[:count] = value
    return series


def _add_spaced_pid(
    log: LogData, message: str, total: int, *, dmod: np.ndarray | None = None, flags: np.ndarray | None = None
) -> None:
    time_s = np.arange(total) * HALF_SECOND
    log.add_message_columns(
        message,
        _array(
            TimeUS=time_s,
            Dmod=np.ones(total) if dmod is None else dmod,
            Flags=np.zeros(total) if flags is None else flags,
        ),
    )


def test_pd_sum_limit_active_for_exactly_ten_percent_of_armed_time_is_critical() -> None:
    """
    Ten percent of armed time is the inclusive threshold for a critical PD-sum finding.

    GIVEN the PD-sum flag set for 5 s of a 50 s armed log
    WHEN the analysis runs
    THEN the finding is critical and reports exactly 10% saturation
    """
    log = LogData(vehicle_type="ArduCopter")
    _add_spaced_pid(log, "PIDP", BOUNDARY_SAMPLES, flags=_leading(10, 2.0, BOUNDARY_SAMPLES))

    outcomes = _analyse(log, {"ATC_RAT_PIT_PDMX": 0.5})

    assert [outcome.severity for outcome in outcomes] == ["critical"]
    assert outcomes[0].evidence is not None
    assert outcomes[0].evidence["saturated_percent"] == pytest.approx(10.0)


def test_pd_sum_limit_active_for_less_than_ten_percent_of_armed_time_is_only_a_warning() -> None:
    """
    Saturation just below ten percent of armed time is only a warning.

    GIVEN the PD-sum flag set for 4.5 s of a 50 s armed log
    WHEN the analysis runs
    THEN the finding is a warning rather than critical
    """
    log = LogData(vehicle_type="ArduCopter")
    _add_spaced_pid(log, "PIDP", BOUNDARY_SAMPLES, flags=_leading(9, 2.0, BOUNDARY_SAMPLES))

    outcomes = _analyse(log, {"ATC_RAT_PIT_PDMX": 0.5})

    assert [outcome.severity for outcome in outcomes] == ["warning"]


def test_one_percent_saturation_is_reported_even_when_shorter_than_one_second() -> None:
    """
    A brief saturation that makes up one percent of armed time is reported.

    GIVEN the PD-sum flag set for a single 0.5 s sample, which is exactly 1% of a 50 s armed log
    WHEN the analysis runs
    THEN the finding is reported because the percentage threshold is inclusive
    """
    log = LogData(vehicle_type="ArduCopter")
    _add_spaced_pid(log, "PIDP", BOUNDARY_SAMPLES, flags=_leading(1, 2.0, BOUNDARY_SAMPLES))

    outcomes = _analyse(log, {"ATC_RAT_PIT_PDMX": 0.5})

    assert [outcome.severity for outcome in outcomes] == ["warning"]


@pytest.mark.parametrize(("saturated_samples", "reported"), [(1, False), (2, True)])
def test_brief_saturation_is_only_reported_once_it_lasts_one_second(saturated_samples: int, reported: bool) -> None:
    """
    Saturation below one percent of armed time is reported only once it lasts at least one second.

    GIVEN the PD-sum flag set for 0.5 s or 1.0 s of a 500 s armed log, which is 0.1% or 0.2% of the time
    WHEN the analysis runs
    THEN only the 1.0 s episode is reported
    """
    total = 1001
    log = LogData(vehicle_type="ArduCopter")
    _add_spaced_pid(log, "PIDP", total, flags=_leading(saturated_samples, 2.0, total))

    outcomes = _analyse(log, {"ATC_RAT_PIT_PDMX": 0.5})

    assert bool(outcomes) is reported


def test_finding_timestamps_span_the_first_sample_to_the_end_of_the_saturated_interval() -> None:
    """
    Finding timestamps cover the whole saturated interval, not just its first sample.

    GIVEN the PD-sum flag set for samples 10 to 19, spanning 5.0 s to 10.0 s
    WHEN the analysis runs
    THEN the finding starts at 5.0 s, ends at 10.0 s and reports 5.0 saturated seconds
    """
    flags = np.zeros(BOUNDARY_SAMPLES)
    flags[10:20] = 2.0
    log = LogData(vehicle_type="ArduCopter")
    _add_spaced_pid(log, "PIDP", BOUNDARY_SAMPLES, flags=flags)

    outcomes = _analyse(log, {"ATC_RAT_PIT_PDMX": 0.5})

    assert len(outcomes) == 1
    assert outcomes[0].timestamp_us == pytest.approx(5.0e6)
    assert outcomes[0].end_timestamp_us == pytest.approx(10.0e6)
    assert outcomes[0].evidence is not None
    assert outcomes[0].evidence["saturated_seconds"] == pytest.approx(5.0)


@pytest.mark.parametrize(("target_percent", "reported"), [(97.0, False), (99.0, True)])
def test_rate_target_must_come_within_two_percent_of_the_envelope_to_count_as_limited(
    target_percent: float, reported: bool
) -> None:
    """
    Rate targets count as limited only when they reach 98% of the configured envelope.

    GIVEN roll rate targets at 97% or 99% of ATC_RATE_R_MAX for half of the armed time
    WHEN the analysis runs
    THEN only the target at 99% of the envelope is reported
    """
    log = LogData(vehicle_type="ArduCopter")
    _add_rate(log, RDes=_window(0.5, target_percent))

    outcomes = _analyse(log, {"ATC_RATE_R_MAX": 100.0})

    assert bool(outcomes) is reported


def test_yaw_rate_limit_is_reported_with_yaw_specific_evidence() -> None:
    """
    A yaw rate limit is reported on its own parameter, without roll or pitch evidence.

    GIVEN yaw rate targets at ATC_RATE_Y_MAX for 30% of the time
    WHEN the analysis runs
    THEN the finding names ATC_RATE_Y_MAX, mentions Yaw and reports the single yaw limit
    """
    log = LogData(vehicle_type="ArduCopter")
    _add_rate(log, YDes=_window(0.3, 180.0))

    outcomes = _analyse(log, {"ATC_RATE_Y_MAX": 180.0})

    assert len(outcomes) == 1
    assert outcomes[0].param_name == "ATC_RATE_Y_MAX"
    assert "Yaw" in outcomes[0].message
    assert outcomes[0].evidence is not None
    assert outcomes[0].evidence["limit"] == pytest.approx(180.0)
    assert "roll_limit" not in outcomes[0].evidence


@pytest.mark.parametrize(
    ("samples", "dmod", "expected_severity"),
    [
        (5, 0.4, "critical"),  # 5% of armed time with Dmod below 0.5 is the severe threshold
        (4, 0.4, "warning"),  # 4% is below it
        (5, 0.5, "warning"),  # Dmod exactly 0.5 is not below the severe Dmod threshold
    ],
)
def test_slew_limiter_severity_follows_inclusive_thresholds(samples: int, dmod: float, expected_severity: str) -> None:
    """
    The slew limiter is critical only when severe Dmod reductions cover at least 5% of armed time.

    GIVEN the roll slew limiter scaling P and D for 0.5 s per sample across a 50 s armed log
    WHEN the number of severely reduced samples and their Dmod value change
    THEN the severity follows the inclusive 5% and strict Dmod 0.5 thresholds
    """
    log = LogData(vehicle_type="ArduCopter")
    _add_spaced_pid(log, "PIDR", BOUNDARY_SAMPLES, dmod=_leading(samples, dmod, BOUNDARY_SAMPLES, base=1.0))

    outcomes = _analyse(log, {"ATC_RAT_RLL_SMAX": 25.0})

    assert [outcome.severity for outcome in outcomes] == [expected_severity]


def test_slew_limiter_at_dmod_point_nine_is_not_a_reduction() -> None:
    """
    A Dmod of exactly 0.9 does not count as a slew-limited reduction.

    GIVEN Dmod equal to 0.9 for the whole armed time on the roll axis
    WHEN the analysis runs with ATC_RAT_RLL_SMAX enabled
    THEN nothing is reported
    """
    log = LogData(vehicle_type="ArduCopter")
    _add_spaced_pid(log, "PIDR", BOUNDARY_SAMPLES, dmod=np.full(BOUNDARY_SAMPLES, 0.9))

    assert not _analyse(log, {"ATC_RAT_RLL_SMAX": 25.0})


def test_non_finite_slew_limit_is_treated_as_disabled() -> None:
    """
    A non-finite limiter value disables the check instead of producing a finding.

    GIVEN a clearly reduced roll slew-limiter Dmod
    WHEN ATC_RAT_RLL_SMAX is NaN
    THEN nothing is reported
    """
    log = LogData(vehicle_type="ArduCopter")
    _add_spaced_pid(log, "PIDR", BOUNDARY_SAMPLES, dmod=_leading(20, 0.3, BOUNDARY_SAMPLES, base=1.0))

    assert not _analyse(log, {"ATC_RAT_RLL_SMAX": float("nan")})


@pytest.mark.parametrize(("roll_deg", "clipped"), [(29.6, True), (29.2, False)])
def test_lean_angle_counts_as_clipped_only_within_half_a_degree_of_the_limit(roll_deg: float, clipped: bool) -> None:
    """
    Desired lean angles count as clipped only within half a degree of the configured limit.

    GIVEN a desired roll of 29.6 or 29.2 degrees for half of the time with ATC_ANGLE_MAX at 30 degrees
    WHEN the analysis runs in Stabilize mode
    THEN only 29.6 degrees, which is within 0.5 degrees of the limit, is reported
    """
    log = LogData(vehicle_type="ArduCopter")
    _add_att(log, _window(0.5, roll_deg))
    _add_modes(log, (0.0, STABILIZE))

    outcomes = _analyse(log, {"ATC_ANGLE_MAX": 30.0})

    assert bool(outcomes) is clipped


def test_availability_explains_missing_messages_when_attitude_logging_is_already_enabled() -> None:
    """
    Missing attitude messages with attitude logging enabled point to the logging options, not LOG_BITMASK.

    GIVEN no ATT, RATE or PID messages and LOG_BITMASK with the Fast Attitude bit set
    WHEN availability is checked
    THEN the analysis is unavailable with a warning and no LOG_BITMASK change is suggested
    """
    context = _context(
        {"LOG_BITMASK": 1.0}, apm_doc={"LOG_BITMASK": {"fields": {"Bitmask": "0:Fast Attitude,1:Medium Attitude"}}}
    )

    result = AttitudeSaturationLogAvailabilityModel(LogData(vehicle_type="ArduCopter"), context).check()

    assert result.available is False
    assert result.state == LogAvailabilityState.WARNING
    assert "logging enabled" in result.reason
    assert len(result.issues) == 1
    assert result.issues[0].param_name is None
    assert result.issues[0].suggested_value is None


def test_availability_without_bitmask_metadata_gives_a_generic_attitude_diagnosis() -> None:
    """
    Without LOG_BITMASK metadata the attitude diagnosis cannot suggest a bit to enable.

    GIVEN no attitude messages and no LOG_BITMASK parameter or metadata
    WHEN availability is checked
    THEN the analysis is unavailable with a warning and no parameter change is suggested
    """
    result = AttitudeSaturationLogAvailabilityModel(LogData(vehicle_type="ArduCopter"), _context({})).check()

    assert result.available is False
    assert result.state == LogAvailabilityState.WARNING
    assert len(result.issues) == 1
    assert result.issues[0].param_name is None
    assert result.issues[0].suggested_value is None


def test_pid_logging_is_not_suggested_again_when_the_pid_bit_is_already_enabled() -> None:
    """
    A PID bit that is already enabled does not produce a LOG_BITMASK suggestion.

    GIVEN ATT and RATE messages without PID messages and LOG_BITMASK already including the PID bit
    WHEN availability is checked
    THEN the user is told PID messages are missing but no LOG_BITMASK change is suggested
    """
    log = LogData(vehicle_type="ArduCopter")
    _add_att(log, np.zeros(SAMPLES))
    _add_rate(log)
    context = _context(
        {"LOG_BITMASK": float(1 << 12)}, apm_doc={"LOG_BITMASK": {"fields": {"Bitmask": "0:Fast Attitude,12:PID"}}}
    )

    result = AttitudeSaturationLogAvailabilityModel(log, context).check()

    assert result.available is True
    assert len(result.issues) == 1
    assert result.issues[0].param_name is None
    assert result.issues[0].suggested_value is None


def test_pid_logging_is_not_suggested_without_bitmask_value() -> None:
    """
    Without a LOG_BITMASK value the missing-PID warning gives no parameter suggestion.

    GIVEN ATT and RATE messages without PID messages and no LOG_BITMASK parameter
    WHEN availability is checked
    THEN the user is warned about missing PID messages without a suggested LOG_BITMASK change
    """
    log = LogData(vehicle_type="ArduCopter")
    _add_att(log, np.zeros(SAMPLES))
    _add_rate(log)

    result = AttitudeSaturationLogAvailabilityModel(log, _context({})).check()

    assert len(result.issues) == 1
    assert result.issues[0].param_name is None
    assert result.issues[0].suggested_value is None


# Fast Attitude sits at bit 2 and Medium Attitude at bit 3 so that bit-shift mistakes change the outcome
_BITMASK_DOC = {"LOG_BITMASK": {"fields": {"Bitmask": "2:Fast Attitude,3:Medium Attitude,12:PID"}}}
_TELEMETRY_REASON = "Attitude telemetry (ATT, RATE, PID*) not logged but logging enabled; check the attitude logging options"


def test_disabled_attitude_logging_suggests_the_medium_attitude_bit_with_full_guidance() -> None:
    """
    Disabled attitude logging gets a complete explanation and the Medium Attitude bit suggestion.

    GIVEN no attitude messages and LOG_BITMASK with both attitude bits disabled
    WHEN availability is checked
    THEN the result is named, explains the disabled logging and suggests setting the Medium Attitude bit
    """
    context = _context({"LOG_BITMASK": 0.0}, apm_doc=_BITMASK_DOC)

    result = AttitudeSaturationLogAvailabilityModel(LogData(vehicle_type="ArduCopter"), context).check()

    assert result.available is False
    assert result.state == LogAvailabilityState.WARNING
    assert result.name == "Attitude saturation"
    assert result.reason == "Attitude logging is disabled in LOG_BITMASK"
    assert len(result.issues) == 1
    issue = result.issues[0]
    assert issue.message == "Enable Fast Attitude or Medium Attitude logging (LOG_BITMASK bit)"
    assert issue.config_step == "28_attitude.param"
    assert issue.param_name == "LOG_BITMASK"
    assert issue.suggested_value == float(1 << 3)


@pytest.mark.parametrize("bitmask", [float(1 << 2), float(1 << 3)])
def test_attitude_logging_enabled_on_either_bit_is_not_reported_as_disabled(bitmask: float) -> None:
    """
    Enabling either attitude bit is recognised, so the user is not told to enable logging again.

    GIVEN no attitude messages and LOG_BITMASK with only the Fast or only the Medium Attitude bit set
    WHEN availability is checked
    THEN the user is pointed at the attitude logging options instead of LOG_BITMASK
    """
    context = _context({"LOG_BITMASK": bitmask}, apm_doc=_BITMASK_DOC)

    result = AttitudeSaturationLogAvailabilityModel(LogData(vehicle_type="ArduCopter"), context).check()

    assert result.reason == _TELEMETRY_REASON
    assert [issue.message for issue in result.issues] == ["No ATT, RATE or PID messages found"]
    assert result.issues[0].param_name is None
    assert result.issues[0].suggested_value is None


def test_missing_log_bitmask_parameter_gives_a_generic_diagnosis_without_error() -> None:
    """
    A missing LOG_BITMASK parameter must not stop the availability check.

    GIVEN no attitude messages, no LOG_BITMASK parameter and LOG_BITMASK metadata available
    WHEN availability is checked
    THEN the generic attitude diagnosis is returned without suggesting a parameter change
    """
    context = _context({}, apm_doc=_BITMASK_DOC)

    result = AttitudeSaturationLogAvailabilityModel(LogData(vehicle_type="ArduCopter"), context).check()

    assert result.available is False
    assert result.state == LogAvailabilityState.WARNING
    assert result.reason == _TELEMETRY_REASON
    assert [issue.message for issue in result.issues] == ["No ATT, RATE or PID messages found"]
    assert result.issues[0].param_name is None


def test_missing_rate_messages_suggest_the_medium_attitude_bit_with_exact_guidance() -> None:
    """
    Missing RATE messages name the skipped checks and suggest enabling attitude logging.

    GIVEN ATT and PID messages without RATE messages and attitude logging disabled in LOG_BITMASK
    WHEN availability is checked
    THEN the analysis stays available and the RATE warning names the skipped checks and the Medium Attitude bit
    """
    log = LogData(vehicle_type="ArduCopter")
    _add_att(log, np.zeros(SAMPLES))
    _add_pid(log, "PIDR")
    context = _context({"LOG_BITMASK": 0.0}, apm_doc=_BITMASK_DOC)

    result = AttitudeSaturationLogAvailabilityModel(log, context).check()

    assert result.available is True
    assert result.name == "Attitude saturation"
    assert len(result.issues) == 1
    issue = result.issues[0]
    assert issue.message == (
        "No RATE messages found, ATC_RATE_*_MAX saturation checks were skipped. "
        "Check Fast Attitude or Medium Attitude logging (LOG_BITMASK bit)"
    )
    assert issue.config_step == "28_attitude.param"
    assert issue.param_name == "LOG_BITMASK"
    assert issue.suggested_value == float(1 << 3)


def test_missing_pid_messages_suggest_the_pid_bit_with_exact_guidance() -> None:
    """
    Missing PID messages name the skipped checks and suggest the PID logging bit.

    GIVEN ATT and RATE messages without PID messages and PID logging disabled in LOG_BITMASK
    WHEN availability is checked
    THEN the PID warning names the skipped checks and suggests the PID bit
    """
    log = LogData(vehicle_type="ArduCopter")
    _add_att(log, np.zeros(SAMPLES))
    _add_rate(log)
    context = _context({"LOG_BITMASK": 0.0}, apm_doc=_BITMASK_DOC)

    result = AttitudeSaturationLogAvailabilityModel(log, context).check()

    assert len(result.issues) == 1
    issue = result.issues[0]
    assert issue.message == (
        "No PIDR, PIDP or PIDY messages found, ATC_RAT_*_SMAX and ATC_RAT_*_PDMX saturation cannot be checked"
    )
    assert issue.config_step == "28_attitude.param"
    assert issue.param_name == "LOG_BITMASK"
    assert issue.suggested_value == float(1 << 12)


def test_missing_pid_messages_without_a_log_bitmask_value_warn_without_error() -> None:
    """
    Without a LOG_BITMASK value the PID warning is still shown and no parameter change is suggested.

    GIVEN ATT and RATE messages without PID messages, no LOG_BITMASK parameter and LOG_BITMASK metadata
    WHEN availability is checked
    THEN the PID warning is shown without a suggested parameter change
    """
    log = LogData(vehicle_type="ArduCopter")
    _add_att(log, np.zeros(SAMPLES))
    _add_rate(log)
    context = _context({}, apm_doc=_BITMASK_DOC)

    result = AttitudeSaturationLogAvailabilityModel(log, context).check()

    assert len(result.issues) == 1
    assert result.issues[0].message.startswith("No PIDR, PIDP or PIDY messages found")
    assert result.issues[0].param_name is None
    assert result.issues[0].suggested_value is None


def test_single_attitude_sample_is_enough_to_count_as_logged() -> None:
    """
    A single logged attitude sample means ATT is present, so the absence diagnosis is not shown.

    GIVEN an ATT message holding one sample and no other attitude messages
    WHEN availability is checked
    THEN the absence diagnosis is not reported
    """
    log = LogData(vehicle_type="ArduCopter")
    log.add_message_columns("ATT", _array(TimeUS=np.array([0.0]), DesRoll=np.array([0.0]), DesPitch=np.array([0.0])))

    result = AttitudeSaturationLogAvailabilityModel(log, _context({})).check()

    assert "No ATT, RATE or PID messages found" not in [issue.message for issue in result.issues]


def test_availability_is_informational_for_vehicles_other_than_copter_and_heli() -> None:
    """
    Attitude saturation is not checked for other vehicles, and the user is told why.

    GIVEN a log from a Plane
    WHEN availability is checked
    THEN the result is an unavailable informational note with no issues
    """
    result = AttitudeSaturationLogAvailabilityModel(LogData(vehicle_type="Plane"), _context({})).check()

    assert result.available is False
    assert result.state == LogAvailabilityState.INFO
    assert not result.issues
    assert result.reason == "Attitude saturation analysis applies only to Copter and helicopter logs"
    assert result.name == "Attitude saturation"


def test_critical_slew_limit_finding_has_exact_wording_and_evidence() -> None:
    """
    The critical slew limiter finding tells the user exactly what happened and what to change.

    GIVEN the roll slew limiter scaling P and D to 0.3 for 20% of the armed time
    WHEN the analysis runs
    THEN the message names the axis, parameter, percentages and advice verbatim
    AND the finding is attributed to the PIDR message with the minimum Dmod as evidence
    """
    log = LogData(vehicle_type="ArduCopter")
    _add_pid(log, "PIDR", dmod=_window(0.2, 0.3, base=1.0))

    outcomes = _analyse(log, {"ATC_RAT_RLL_SMAX": 25.0})

    assert len(outcomes) == 1
    assert outcomes[0].message == (
        "Roll rate controller P and D gains were cut below 50% by the ATC_RAT_RLL_SMAX slew limiter for "
        "20.0% of the armed time. This severely reduces attitude control. "
        "Reduce the P and D gains or increase ATC_RAT_RLL_SMAX."
    )
    assert outcomes[0].source == "PIDR"
    assert outcomes[0].evidence is not None
    assert outcomes[0].evidence["severe_percent"] == pytest.approx(20.02, abs=0.01)
    assert outcomes[0].evidence["minimum_dmod"] == pytest.approx(0.3)


def test_warning_slew_limit_finding_has_exact_wording() -> None:
    """
    The warning slew limiter finding explains the oscillation risk and how to proceed.

    GIVEN the yaw slew limiter reducing P and D to 0.8 for 5% of the armed time, but never below 0.5
    WHEN the analysis runs
    THEN the warning message gives the reduction threshold, percentage, seconds and advice verbatim
    """
    log = LogData(vehicle_type="ArduCopter")
    _add_pid(log, "PIDY", dmod=_window(0.05, 0.8, base=1.0))

    outcomes = _analyse(log, {"ATC_RAT_YAW_SMAX": 10.0})

    assert len(outcomes) == 1
    assert outcomes[0].severity == "warning"
    assert outcomes[0].message == (
        "Yaw rate controller P and D gains were reduced below 90% by the ATC_RAT_YAW_SMAX slew limiter for "
        "5.0% of the armed time (5.0 s), which indicates an oscillation tendency. "
        "Check the tune before increasing ATC_RAT_YAW_SMAX."
    )


def test_slew_limit_scan_continues_to_the_next_axis_when_one_axis_is_not_reportable() -> None:
    """
    An unremarkable roll axis does not hide a slew-limited pitch axis.

    GIVEN roll Dmod at 1.0 everywhere, which is never reportable, and pitch Dmod at 0.3 for 20% of the time
    WHEN the analysis runs
    THEN the pitch finding is still reported
    """
    log = LogData(vehicle_type="ArduCopter")
    _add_pid(log, "PIDR")
    _add_pid(log, "PIDP", dmod=_window(0.2, 0.3, base=1.0))

    outcomes = _analyse(log, {"ATC_RAT_RLL_SMAX": 25.0, "ATC_RAT_PIT_SMAX": 25.0})

    assert [outcome.param_name for outcome in outcomes] == ["ATC_RAT_PIT_SMAX"]


def test_slew_minimum_dmod_ignores_intervals_where_the_slew_limiter_is_disabled() -> None:
    """
    Evidence reports the lowest Dmod only while the slew limiter is enabled.

    GIVEN ATC_RAT_RLL_SMAX is 0 for the first half of the log with Dmod at 0.1, then 25
    AND Dmod is reduced to 0.3 for 2 s after it is enabled
    WHEN the analysis runs
    THEN the reported minimum Dmod is 0.3, not the disabled-interval 0.1
    """
    log = LogData(vehicle_type="ArduCopter")
    dmod = np.ones(SAMPLES)
    dmod[: SAMPLES // 2] = 0.1
    dmod[SAMPLES // 2 : SAMPLES // 2 + 20] = 0.3
    _add_pid(log, "PIDR", dmod=dmod)
    history = ParameterHistory(
        initial_values={"ATC_RAT_RLL_SMAX": 0.0},
        changes={"ATC_RAT_RLL_SMAX": (ParameterChange(50.0, 25.0),)},
    )

    outcomes = _analyse(log, {"ATC_RAT_RLL_SMAX": 25.0}, history=history)

    assert len(outcomes) == 1
    assert outcomes[0].evidence is not None
    assert outcomes[0].evidence["minimum_dmod"] == pytest.approx(0.3)


def test_slew_minimum_dmod_ignores_the_final_untimed_sample() -> None:
    """
    The last logged sample has no elapsed time, so its Dmod must not reach the evidence.

    GIVEN roll Dmod at 0.3 for 20% of the time and a final sample at 0.1 with zero weight
    WHEN the analysis runs
    THEN the reported minimum Dmod is 0.3
    """
    log = LogData(vehicle_type="ArduCopter")
    dmod = _window(0.2, 0.3, base=1.0)
    dmod[-1] = 0.1
    _add_pid(log, "PIDR", dmod=dmod)

    outcomes = _analyse(log, {"ATC_RAT_RLL_SMAX": 25.0})

    assert len(outcomes) == 1
    assert outcomes[0].evidence is not None
    assert outcomes[0].evidence["minimum_dmod"] == pytest.approx(0.3)


def test_roll_and_pitch_rate_limit_is_reported_once_as_a_shared_envelope() -> None:
    """
    Roll and pitch rate limits share one ellipse, so the finding names both axes together.

    GIVEN roll and pitch rate targets at 200 and 90 deg/s for 30% of the armed time
    WHEN the analysis runs
    THEN a single warning names the roll/pitch envelope and its limits verbatim
    """
    log = LogData(vehicle_type="ArduCopter")
    _add_rate(log, RDes=_window(0.3, 200.0), PDes=_window(0.3, 90.0))

    outcomes = _analyse(log, {"ATC_RATE_R_MAX": 200.0, "ATC_RATE_P_MAX": 90.0})

    assert len(outcomes) == 1
    assert outcomes[0].severity == "critical"
    assert outcomes[0].message == (
        "Roll/pitch rate target reached the configured ATC_RATE_R_MAX / ATC_RATE_P_MAX envelope "
        "(200 deg/s / 90 deg/s) for 30.0% of the armed time (30.0 s). "
        "RATE targets near or above this envelope suggest rate limiting but do not prove clipping. "
        "Check target tracking and disturbances before changing the limits. "
        "Frequent rate limiting can severely reduce attitude control."
    )


def test_analysis_result_for_copter_reports_available_named_outcomes() -> None:
    """
    A Copter log yields an available analysis result carrying its named outcomes.

    GIVEN a Copter log with roll rate targets at the envelope for 30% of the armed time
    WHEN the full analysis is run
    THEN the result is available, named Attitude Saturation Analysis, and carries the finding
    """
    log = LogData(vehicle_type="ArduCopter")
    _add_rate(log, RDes=_window(0.3, 200.0))
    context = _context({"ATC_RATE_R_MAX": 200.0})

    result = AttitudeSaturationLogAnalysis(log, context).analyse()

    assert result.available is True
    assert result.name == "Attitude Saturation Analysis"
    assert result.reason == "Attitude saturation analysis complete"
    assert [outcome.param_name for outcome in result.outcomes] == ["ATC_RATE_R_MAX"]


def test_analysis_result_for_plane_is_unavailable_with_an_explanation() -> None:
    """
    Attitude saturation analysis is not applied to Plane logs, and the result says why.

    GIVEN a Plane log that contains roll rate targets at the envelope
    WHEN the full analysis is run
    THEN the result is unavailable with no outcomes and the Copter and helicopter explanation
    """
    log = LogData(vehicle_type="ArduPlane")
    _add_rate(log, RDes=_window(0.3, 200.0))
    context = _context({"ATC_RATE_R_MAX": 200.0})

    result = AttitudeSaturationLogAnalysis(log, context).analyse()

    assert result.available is False
    assert not result.outcomes
    assert result.name == "Attitude Saturation Analysis"
    assert result.reason == "Attitude saturation analysis applies only to Copter and helicopter logs"


def test_lean_angle_limit_finding_has_exact_wording() -> None:
    """
    The lean-angle finding gives the limited angle, parameter, share of time and advice verbatim.

    GIVEN a desired roll of 29.6 degrees for half of the armed time in Stabilize with ATC_ANGLE_MAX at 30
    WHEN the analysis runs
    THEN the single finding message matches the expected wording exactly
    """
    log = LogData(vehicle_type="ArduCopter")
    _add_att(log, _window(0.5, 29.6))
    _add_modes(log, (0.0, STABILIZE))

    outcomes = _analyse(log, {"ATC_ANGLE_MAX": 30.0})

    assert len(outcomes) == 1
    assert outcomes[0].severity == "warning"
    assert outcomes[0].source == "ATT"
    assert outcomes[0].message == (
        "The full pilot lean range of 30 deg allowed by ATC_ANGLE_MAX was used for 50.1% of the armed time "
        "in the flight modes it applies to (50.0 s). "
        "Review pilot inputs and the configured lean range."
    )
