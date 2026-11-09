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
