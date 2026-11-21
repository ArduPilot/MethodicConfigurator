#!/usr/bin/env python3

"""
Behavioral tests for automatic dynamic harmonic-notch proposals.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import json
from dataclasses import asdict
from typing import Any

import numpy as np
import pytest
from numpy.typing import NDArray

from ardupilot_methodic_configurator.log_analysis.data_model_auto_dynamic_notch import (
    AutoDynamicNotchLogAnalysis,
    AutoDynamicNotchLogAvailabilityModel,
    AutoDynamicNotchSettings,
    GyroFftWindow,
    OrderSpectrum,
    TrackingSamples,
    TrackingSource,
    build_order_spectrum,
    fit_tracking_source,
    harmonic_prominence,
    iter_gyro_fft_windows,
)
from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis import analyze_log
from ardupilot_methodic_configurator.log_analysis.data_model_log_analysis_context import LogAnalysisContext
from ardupilot_methodic_configurator.log_analysis.data_model_log_data import LogData, MessageSchema
from ardupilot_methodic_configurator.log_analysis.data_model_parameter_history import ParameterChange, ParameterHistory

# pylint: disable=redefined-outer-name


def _add_columns(log: LogData, name: str, fields: dict[str, NDArray[Any]]) -> None:
    """Build extractor-like structured arrays with already scaled units."""
    dtype = [(field, values.dtype, values.shape[1:]) for field, values in fields.items()]
    records = np.empty(len(next(iter(fields.values()))), dtype=dtype)
    for field, values in fields.items():
        records[field] = values
    log.add_message_columns(name, records)


@pytest.fixture
def flight() -> tuple[LogData, LogAnalysisContext]:  # pylint: disable=too-many-locals
    """Variable-speed quad flight with two IMUs and real batch packet layouts."""
    log = LogData(vehicle_type="ArduCopter", firmware_version=(4, 6, 3))
    suffixes = ("ENABLE", "MODE", "FREQ", "BW", "ATT", "REF", "FM_RAT", "HMNCS", "OPTS")
    parameters = {"INS_HNTCH_" + suffix: 0.0 for suffix in suffixes}
    parameters.update({"INS_LOG_BAT_OPT": 0.0, "INS_LOG_BAT_MASK": 3.0, "INS_GYR_ID": 1.0, "INS_GYR2_ID": 2.0})
    parameters["INS_HNTCH_OPTS"] = 1 | 4 | 8 | 16 | 32 | 64
    documentation = {name: {} for name in parameters if name.startswith("INS_HNTCH_")}
    documentation["INS_HNTCH_MODE"] = {"Values": {0: "Fixed", 1: "Throttle", 3: "ESC Telemetry"}}
    documentation["INS_HNTCH_FREQ"] = {"min": 10.0, "max": 495.0}
    documentation["INS_HNTCH_BW"] = {"fields": {"Range": "5 250"}}
    documentation["INS_HNTCH_REF"] = {"min": 0.0, "max": 1.0}
    context = LogAnalysisContext(
        parameters=parameters,
        configuration_steps={
            "20_notch.param": {"add_parameters": {"INS_HNTCH_" + suffix: {} for suffix in suffixes}},
        },
        apm_doc=documentation,
    )
    random = np.random.default_rng(17)
    header_rows = []
    packet_rows = []
    frequencies = []
    centers = []
    for index in range(12):
        frequency = 80 + 4 * (index // 2)
        time_s = 1 + index
        centers.append(time_s + 0.5)
        frequencies.append(frequency)
        header_rows.append((time_s, index, 1, index % 2, 1000, 1024, 1024, time_s))
        samples = np.arange(1024) / 1024
        x = np.sin(2 * np.pi * frequency * samples) + 0.8 * np.sin(2 * np.pi * frequency * 2 * samples)
        axes = np.array([x, 0.7 * x, 0.5 * x]) + random.normal(0, 0.015, (3, 1024))
        encoded = np.rint(axes * 1000).astype(np.int16)
        packet_rows.extend(
            (time_s + 0.001 * (sequence + 1), index, sequence, *encoded[:, sequence * 32 : (sequence + 1) * 32])
            for sequence in range(32)
        )
    headers = np.array(
        header_rows,
        dtype=[
            ("TimeUS", "f8"),
            ("N", "u2"),
            ("type", "u1"),
            ("instance", "u1"),
            ("mul", "f8"),
            ("smp_cnt", "u2"),
            ("smp_rate", "f8"),
            ("SampleUS", "f8"),
        ],
    )
    packets = np.array(
        packet_rows,
        dtype=[("TimeUS", "f8"), ("N", "u2"), ("seqno", "u2"), ("x", "i2", (32,)), ("y", "i2", (32,)), ("z", "i2", (32,))],
    )
    log.add_message_columns("ISBH", headers)
    log.add_message_columns("ISBD", packets)
    telemetry_times = np.array([time for center in centers for time in (center - 0.5, center, center + 0.4)])
    rpm = np.repeat(np.array(frequencies) * 60, 3)
    _add_columns(log, "ESC", {"TimeUS": telemetry_times, "Instance": np.zeros(len(rpm)), "RPM": rpm})
    throttle = (np.repeat(np.array(frequencies), 3) / 160) ** 2
    _add_columns(log, "RATE", {"TimeUS": telemetry_times, "AOut": throttle})
    return log, context


def _suggestions(result: Any) -> dict[str, int | float]:  # noqa: ANN401
    return {outcome.param_name: outcome.suggested_value for outcome in result.outcomes if outcome.param_name}


def test_flight_proposes_esc_harmonics_without_changing_configuration(flight) -> None:
    """
    Propose a complete, traceable notch configuration from a flight.

    GIVEN a varying-speed flight with first and second harmonic noise,
    WHEN the user analyses its log,
    THEN a complete grouped ESC proposal preserves unrelated options and the inputs.
    """
    log, context = flight
    original = dict(context.parameters)
    availability = AutoDynamicNotchLogAvailabilityModel(log, context).check()
    result = AutoDynamicNotchLogAnalysis(log, context).analyse()
    values = _suggestions(result)
    assert availability.available
    assert result.available, result.reason
    assert values["INS_HNTCH_MODE"] == 3
    assert values["INS_HNTCH_FREQ"] == 64
    assert values["INS_HNTCH_BW"] == 32
    assert int(values["INS_HNTCH_HMNCS"]) & 3 == 3
    assert values["INS_HNTCH_REF"] == 1
    assert values["INS_HNTCH_FM_RAT"] == 1
    assert values["INS_HNTCH_OPTS"] == 4 | 8 | 32
    assert 10 <= values["INS_HNTCH_ATT"] <= 50
    assert len(values) == 9
    assert {outcome.related_step for outcome in result.outcomes if outcome.param_name} == {"20_notch.param"}
    assert {outcome.group for outcome in result.outcomes} == {"First harmonic notch"}
    assert context.parameters == original
    json.dumps(asdict(result), allow_nan=False)


def test_missing_esc_telemetry_falls_back_to_average_throttle(flight) -> None:
    """
    Recover a throttle-based fit when higher-priority sources are unavailable.

    GIVEN gyro noise that follows throttle but ESC telemetry is missing,
    WHEN the user requests a fit,
    THEN average throttle recovers the fundamental and reports earlier source failures.
    """
    log, context = flight
    log.add_message_columns("ESC", np.array([], dtype=[("TimeUS", "f8")]))
    result = AutoDynamicNotchLogAnalysis(log, context).analyse()
    values = _suggestions(result)
    assert result.available, result.reason
    assert values["INS_HNTCH_MODE"] == 1
    assert values["INS_HNTCH_FREQ"] == pytest.approx(91, abs=2)
    assert values["INS_HNTCH_REF"] == pytest.approx(0.32, abs=0.01)
    assert int(values["INS_HNTCH_OPTS"]) & 2 == 0
    assert values["INS_HNTCH_FM_RAT"] < 1
    assert any("Missing" in outcome.message for outcome in result.outcomes)


def test_per_motor_throttle_is_preferred_to_average_throttle(flight) -> None:
    """
    Prefer per-motor thrust reconstruction over average throttle.

    GIVEN motor PWM, thrust-curve parameters, barometer data, and no ESC telemetry,
    WHEN the log is fitted,
    THEN reconstructed motor thrust supplies the multiple-source proposal.
    """
    log, context = flight
    log.add_message_columns("ESC", np.array([], dtype=[("TimeUS", "f8")]))
    context.parameters.update(
        {
            "FRAME_CLASS": 1,
            "BARO_PRIMARY": 0,
            "MOT_THST_EXPO": 0.65,
            "MOT_SPIN_MIN": 0.1,
            "MOT_SPIN_MAX": 0.95,
            "MOT_PWM_MIN": 1000,
            "MOT_PWM_MAX": 2000,
            "MOT_BAT_VOLT_MIN": 0,
            "MOT_BAT_VOLT_MAX": 0,
            "MOT_BAT_IDX": 0,
        }
    )
    rate = log.get_message_columns("RATE")
    thrust = rate["AOut"]
    actuator = ((0.35**2 + 4 * 0.65 * thrust) ** 0.5 - 0.35) / (2 * 0.65)
    output_fields = {"TimeUS": rate["TimeUS"]}
    for channel in range(1, 5):
        context.parameters[f"SERVO{channel}_FUNCTION"] = 32 + channel
        output_fields[f"C{channel}"] = 1000 + 1000 * (0.1 + actuator * 0.85)
    _add_columns(log, "RCOU", output_fields)
    _add_columns(log, "BARO", {"TimeUS": rate["TimeUS"], "I": np.zeros(len(rate)), "Alt": np.zeros(len(rate))})
    result = AutoDynamicNotchLogAnalysis(log, context).analyse()
    values = _suggestions(result)
    assert result.available, result.reason
    assert values["INS_HNTCH_MODE"] == 1
    assert int(values["INS_HNTCH_OPTS"]) & 2
    assert values["INS_HNTCH_FREQ"] == pytest.approx(91, abs=2)
    assert any("Per-motor throttle" in outcome.message for outcome in result.outcomes)


@pytest.mark.parametrize(
    "damage", ["post_filter", "missing_packet", "non_finite", "stopped", "missing_docs", "changed_parameters"]
)
def test_unusable_logs_return_reasons_without_suggestions(flight, damage: str) -> None:
    """
    Reject logs that cannot support meaningful parameter suggestions.

    GIVEN a log with unavailable or invalid fitting prerequisites,
    WHEN the user analyses it,
    THEN availability fails and a direct fitting request cannot return parameter changes.
    """
    log, context = flight
    if damage == "post_filter":
        context.parameters["INS_LOG_BAT_OPT"] = 2
    elif damage == "missing_packet":
        packets = log.get_message_columns("ISBD")
        log.add_message_columns("ISBD", packets[packets["seqno"] != 3])
    elif damage == "non_finite":
        log.get_message_columns("ISBH")["mul"] = np.nan
    elif damage == "stopped":
        log.get_message_columns("ESC")["RPM"] = 0
        log.get_message_columns("RATE")["AOut"] = 0
    elif damage == "missing_docs":
        context.apm_doc = None
    else:
        context.parameter_history = ParameterHistory(context.parameters, {"INS_LOG_BAT_OPT": (ParameterChange(3, 4),)})
    availability = AutoDynamicNotchLogAvailabilityModel(log, context).check()
    result = AutoDynamicNotchLogAnalysis(log, context).analyse()
    assert not availability.available
    assert not result.available
    assert result.reason
    assert not _suggestions(result)


def test_analysis_interval_can_use_parameters_after_a_change(flight) -> None:
    """
    Allow fitting a stable interval following a parameter change.

    GIVEN a motor parameter changed before a selected interval,
    WHEN the user analyses the later stable interval,
    THEN that interval is usable and uses its effective parameter values.
    """
    log, context = flight
    context.parameter_history = ParameterHistory(context.parameters, {"MOT_THST_EXPO": (ParameterChange(2, 0.5),)})
    settings = AutoDynamicNotchSettings(start_time_s=4, end_time_s=10)
    assert AutoDynamicNotchLogAvailabilityModel(log, context, settings).check().available
    assert AutoDynamicNotchLogAnalysis(log, context, settings).analyse().available


def test_telemetry_gaps_are_not_extrapolated_or_bridged() -> None:
    """
    Limit interpolation to valid, recent telemetry coverage.

    GIVEN telemetry with a long gap and an invalid observation,
    WHEN tracking values are interpolated,
    THEN only covered observations and short valid brackets can supply tracking.
    """
    series = TrackingSamples(np.array([1.0, 2.0, 5.0, 6.0]), np.array([10.0, 20.0, 50.0, np.nan]))
    values = series.interpolate(np.array([0.5, 1.0, 1.5, 3.0, 5.5, 7.0]), 1)
    np.testing.assert_allclose(values, [np.nan, 10, 15, np.nan, np.nan, np.nan], equal_nan=True)


def test_batch_fft_matches_webtools_scaling_and_sample_timestamps(flight) -> None:
    """
    Preserve sample units and the upstream FFT convention.

    GIVEN scaled log timestamps and integer gyro packet samples,
    WHEN the FFT adapter reconstructs batches,
    THEN its one-sided Hann spectrum and centers match the WebTools convention.
    """
    log, context = flight
    windows = list(iter_gyro_fft_windows(log, context.parameters, AutoDynamicNotchSettings()))
    assert len(windows) == 12
    assert windows[0].time_s == 1.5
    assert windows[0].instance == 0
    assert windows[1].instance == 1
    assert windows[0].bins_hz[80] == 80
    assert windows[0].power[80] == pytest.approx(0.25 * (1 + 0.7**2 + 0.5**2), rel=0.02)


def test_post_filter_instances_are_excluded_from_combined_logging(flight) -> None:
    """
    Use only pre-filter instances from combined batch logging.

    GIVEN combined pre/post logging with known physical gyro count,
    WHEN gyro windows are reconstructed,
    THEN post-filter instances do not enter the fit.
    """
    log, context = flight
    context.parameters["INS_LOG_BAT_OPT"] = 4
    headers = log.get_message_columns("ISBH")
    headers["instance"][1::2] = 2
    windows = list(iter_gyro_fft_windows(log, context.parameters, AutoDynamicNotchSettings()))
    assert len(windows) == 6
    assert {window.instance for window in windows} == {0}


def test_fitted_values_outside_firmware_limits_reject_the_proposal(flight) -> None:
    """
    Reject a complete fit when its parameters exceed firmware limits.

    GIVEN a documented frequency range too low for the recorded vibration,
    WHEN every tracking source is fitted,
    THEN no incomplete or out-of-range parameter proposal is emitted.
    """
    log, context = flight
    context.apm_doc["INS_HNTCH_FREQ"]["max"] = 20
    result = AutoDynamicNotchLogAnalysis(log, context).analyse()
    assert not result.available
    assert "documented range" in result.reason
    assert not result.outcomes


def test_default_pipeline_exposes_grouped_fit_and_related_parameter_values(flight) -> None:
    """
    Expose the fit through the existing pipeline and summary.

    GIVEN a valid flight and the default analysis registry,
    WHEN the user analyses the log,
    THEN the summary contains the grouped notch fit and its original parameters.
    """
    log, context = flight
    summary = analyze_log(log, context)
    result = next(result for result in summary.analysis_results if result.subsystem_key == "auto_dynamic_notch")
    assert result.available
    assert summary.related_parameter_values["INS_HNTCH_FREQ"] == 0
    assert summary.component_keys_for_subsystem("auto_dynamic_notch") == ("Flight Controller", "ESC", "Motors")


def _prepared_windows(frequencies: list[float], harmonic: float = 1) -> list[GyroFftWindow]:
    """Analytic spectra let tracking checks avoid time-domain FFT leakage."""
    bins = np.arange(0, 1025, dtype=np.float64)
    windows = []
    for index, frequency in enumerate(frequencies):
        power = np.ones(bins.shape)
        power += 1000 * np.exp(-(((bins - frequency * harmonic) / 2) ** 2))
        windows.append(GyroFftWindow(float(index + 1), 0, bins, power))
    return windows


def test_esc_pole_scaling_mismatch_is_rejected() -> None:
    """
    Diagnose a probable motor-pole scaling mismatch.

    GIVEN dominant vibration at a noninteger ESC frequency order,
    WHEN ESC tracking is fitted,
    THEN it is rejected with a motor-pole scaling explanation.
    """
    windows = _prepared_windows([100, 110, 120], harmonic=1.5)
    source = TrackingSource(
        "ESC", 3, multi_source=False, samples=(TrackingSamples(np.array([1.0, 2.0, 3.0]), np.array([100.0, 110.0, 120.0])),)
    )
    with pytest.raises(ValueError, match="motor poles"):
        fit_tracking_source(lambda: iter(windows), source, AutoDynamicNotchSettings())


def test_order_averaging_uses_linear_power_and_majority_coverage() -> None:
    """
    Average power before applying a logarithm and require majority coverage.

    GIVEN windows with unequal power and frequency coverage,
    WHEN an order spectrum is built,
    THEN averaging precedes dB conversion and insufficiently covered bins are unavailable.
    """
    windows = [
        GyroFftWindow(float(index), 0, np.array([0.0, 1.0, 2.0, 3.0]), np.full(4, power))
        for index, power in enumerate((1.0, 9.0, 5.0))
    ]
    spectrum = build_order_spectrum(lambda: iter(windows), lambda time: 1 if time == 0 else 2, np.array([0.5, 1.0, 2.0]))
    assert spectrum.db[0] == pytest.approx(10 * np.log10(5))
    assert np.isnan(spectrum.db[2])


def test_boundary_maxima_and_missing_floor_coverage_do_not_qualify_as_harmonics() -> None:
    """
    Reject spurious peaks at boundaries or across missing spectrum data.

    GIVEN a slope and a spectrum with missing floor coverage,
    WHEN harmonic prominence is evaluated,
    THEN neither can be mistaken for a real harmonic peak.
    """
    grid = np.arange(0.25, 3, 0.005)
    spectrum = OrderSpectrum(grid, grid.copy(), np.array([100.0]), np.array([1.0]))
    assert harmonic_prominence(spectrum, 1, 1) == float("-inf")
    spectrum.db[70] = np.nan
    assert harmonic_prominence(spectrum, 1, 1) == float("-inf")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"fft_window_size": 100},
        {"overlap": 1.0},
        {"telemetry_gap_s": 0},
        {"start_time_s": 10, "end_time_s": 5},
        {"start_time_s": float("nan")},
    ],
)
def test_invalid_analysis_settings_are_rejected(kwargs: dict[str, Any]) -> None:
    """
    Reject invalid analysis settings before processing a log.

    GIVEN invalid FFT or interval settings,
    WHEN the user prepares an analysis,
    THEN the settings are rejected before numerical processing starts.
    """
    with pytest.raises(ValueError, match=r"FFT|Analysis|overlap"):
        AutoDynamicNotchSettings(**kwargs)


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        (3, {"INS_HNTCH_FREQ": 80, "INS_HNTCH_REF": 1, "INS_HNTCH_FM_RAT": 1, "INS_HNTCH_HMNCS": 3, "INS_HNTCH_ATT": 30}),
        (1, {"INS_HNTCH_FREQ": 100, "INS_HNTCH_REF": 0.3, "INS_HNTCH_FM_RAT": 0.7, "INS_HNTCH_HMNCS": 1, "INS_HNTCH_ATT": 20}),
    ],
)
def test_prepared_spectra_match_javascript_reference_fits(mode: int, expected: dict[str, float]) -> None:
    """
    Preserve upstream fitting results for equivalent prepared spectra.

    GIVEN analytic spectra and JavaScript auto-fit.js reference results,
    WHEN the Python fitter receives the same tracking samples,
    THEN frequency, reference, minimum ratio, harmonics, and attenuation match.
    """
    # Expected values were verified by executing the supplied PR #363 script with Node.
    frequencies = np.array([100.0, 110.0, 120.0])
    bins = np.arange(1025, dtype=np.float64)
    windows = []
    for index, frequency in enumerate(frequencies):
        power = np.ones(bins.shape)
        power += 100 * np.exp(-(((bins - frequency) / 2) ** 2))
        power += 1000 * np.exp(-(((bins - 2 * frequency) / 2) ** 2))
        windows.append(GyroFftWindow(float(index + 1), 0, bins, power))
    values = frequencies if mode == 3 else (frequencies / 200) ** 2
    source = TrackingSource(
        "reference", mode, multi_source=False, samples=(TrackingSamples(np.array([1.0, 2.0, 3.0]), values),)
    )
    fit = fit_tracking_source(lambda: iter(windows), source, AutoDynamicNotchSettings())
    actual = fit.parameter_values(0)
    assert {name: actual[name] for name in expected} == expected


def test_fifth_percentile_and_rounding_follow_javascript_conventions() -> None:
    """
    Preserve percentile selection and positive half-value rounding.

    GIVEN ESC tracking values whose low percentile is between samples under interpolation,
    WHEN a fit is produced,
    THEN the observed low sample is selected and its half-Hz result rounds upward.
    """
    frequencies = [100.625, 115.0, 130.0]
    windows = _prepared_windows(frequencies)
    source = TrackingSource(
        "ESC", 3, multi_source=False, samples=(TrackingSamples(np.array([1.0, 2.0, 3.0]), np.array(frequencies)),)
    )
    fit = fit_tracking_source(lambda: iter(windows), source, AutoDynamicNotchSettings())
    assert fit.frequency_hz == 81  # round(100.625 * 0.8) = round(80.5), with JS rounding.
    assert fit.parameter_values(0)["INS_HNTCH_BW"] == 41  # JS rounds 40.5 upward.


def test_extractor_time_scaling_is_applied_once(flight) -> None:
    """
    Use the extractor's scaled representation for both log and sample timestamps.

    GIVEN compact microsecond timestamps with FMTU multipliers,
    WHEN the log is analysed,
    THEN sample centers and tracking alignment use seconds exactly once.
    """
    log, context = flight
    for message in ("ISBH", "ISBD", "ESC", "RATE"):
        records = log.get_message_columns(message)
        fields = list(records.dtype.names)
        multipliers = [1e-6 if name in ("TimeUS", "SampleUS") else 1 for name in fields]
        for name in ("TimeUS", "SampleUS"):
            if name in fields:
                records[name] *= 1e6
        log.schemas[message] = MessageSchema(
            message, 1, 1, "", fields, [""] * len(fields), [""] * len(fields), multipliers, [False] * len(fields)
        )
    windows = list(iter_gyro_fft_windows(log, context.parameters, AutoDynamicNotchSettings()))
    assert windows[0].time_s == 1.5
    result = AutoDynamicNotchLogAnalysis(log, context).analyse()
    assert result.available, result.reason
    assert _suggestions(result)["INS_HNTCH_FREQ"] == 64


def test_missing_batches_are_reported_when_remaining_data_can_be_fitted(flight) -> None:
    """
    Keep valid data usable and explain skipped gyro batches.

    GIVEN one incomplete batch among otherwise usable flight data,
    WHEN the user fits the notch,
    THEN the proposal succeeds with a skipped-batch diagnostic.
    """
    log, context = flight
    packets = log.get_message_columns("ISBD")
    log.add_message_columns("ISBD", packets[~((packets["N"] == 0) & (packets["seqno"] == 4))])
    result = AutoDynamicNotchLogAnalysis(log, context).analyse()
    assert result.available
    assert any("Skipped 1" in outcome.message for outcome in result.outcomes)


@pytest.mark.parametrize("mask", [1, 2])
def test_esc_mask_selects_motor_instances_and_preserves_other_notch_groups(flight, mask: int) -> None:
    """
    Respect a logged motor selection while preserving its mask and other notch groups.

    GIVEN two motors with different RPM and an ESC mask selecting one,
    WHEN the user analyses the flight,
    THEN only the selected motor's RPM can supply a fit.
    """
    log, context = flight
    original = log.get_message_columns("ESC")
    extra = original.copy()
    extra["Instance"] = 1
    extra["RPM"] = extra["RPM"] * 1.5
    records = np.concatenate([original, extra])
    log.add_message_columns("ESC", records[np.argsort(records["TimeUS"], kind="stable")])
    context.parameters.update({"INS_HNTCH_ESC_MASK": mask, "INS_HNTC2_ENABLE": 1, "INS_HNTC2_FREQ": 250})
    result = AutoDynamicNotchLogAnalysis(log, context).analyse()
    assert result.available, result.reason
    values = _suggestions(result)
    assert values["INS_HNTCH_MODE"] == (3 if mask == 1 else 1)
    assert "INS_HNTCH_ESC_MASK" not in values
    assert not any(name.startswith("INS_HNTC2_") for name in values)
    assert context.parameters["INS_HNTCH_ESC_MASK"] == mask


def test_older_firmware_falls_back_from_per_motor_to_average_throttle(flight) -> None:
    """
    Gate per-motor tracking to the firmware release that implements it.

    GIVEN a 4.5 flight without ESC telemetry,
    WHEN throttle-based fitting is attempted,
    THEN average throttle remains available and per-motor tracking is not suggested.
    """
    log, context = flight
    log.firmware_version = (4, 5, 7)
    log.add_message_columns("ESC", np.array([], dtype=[("TimeUS", "f8")]))
    result = AutoDynamicNotchLogAnalysis(log, context).analyse()
    assert result.available
    assert int(_suggestions(result)["INS_HNTCH_OPTS"]) & 2 == 0
    assert any("4.6 or later" in outcome.message for outcome in result.outcomes)
