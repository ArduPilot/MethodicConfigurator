#!/usr/bin/env python3

"""
Tests for the ESC RPM scale plugin data model.

SPDX-FileCopyrightText: 2026 Erwan Billard

SPDX-License-Identifier: GPL-3.0-or-later
"""

# pylint: disable=redefined-outer-name,too-few-public-methods

import json
from math import inf, nan
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import ardupilot_methodic_configurator
from ardupilot_methodic_configurator.plugins.data_model_esc_rpm_scale import (
    DEFAULT_HOBBYWING_6X_SE_SCALE,
    FALLBACK_ESC_OUTPUT_COUNT,
    SCRIPT_FILENAME,
    SCRIPT_REMOTE_PATH,
    SCRIPTING_PROTOCOL,
    EscRpmScaleDataModel,
)
from ardupilot_methodic_configurator.plugins.frontend_tkinter_esc_rpm_scale import register_esc_rpm_scale_plugin
from ardupilot_methodic_configurator.plugins.plugin_constants import PLUGIN_ESC_RPM_SCALE


@pytest.fixture
def filesystem(tmp_path: Path) -> MagicMock:
    fs = MagicMock()
    fs.vehicle_dir = str(tmp_path)
    fs.vehicle_components_fs.data = {"Components": {}}
    return fs


@pytest.fixture
def flight_controller() -> MagicMock:
    fc = MagicMock()
    fc.master = MagicMock()
    fc.upload_file.return_value = True
    # Default to a quad frame so esc_count() resolves without touching disk data.
    fc.fc_parameters = {"FRAME_CLASS": 1.0}
    return fc


@pytest.fixture
def model(flight_controller: MagicMock, filesystem: MagicMock) -> EscRpmScaleDataModel:
    return EscRpmScaleDataModel(flight_controller, filesystem)


class TestHobbywingDetection:
    """Verify ESC and motor product metadata detection."""

    def test_detects_hobbywing_6x_se_in_esc_product(self, model, filesystem) -> None:
        filesystem.vehicle_components_fs.data["Components"]["ESC"] = {
            "Product": {"Manufacturer": "Hobbywing", "Model": "6X SE"}
        }

        assert model.is_hobbywing_6x_se()
        assert model.recommended_scale == DEFAULT_HOBBYWING_6X_SE_SCALE

    def test_detects_normalized_hobbywing_6x_se_in_motor_product(self, model, filesystem) -> None:
        filesystem.vehicle_components_fs.data["Components"]["Motors"] = {
            "Product": {"Manufacturer": "  HOBBYWING ", "Model": "6X-SE"}
        }

        assert model.is_hobbywing_6x_se()

    def test_detects_hobbywing_6xse_without_separator(self, model, filesystem) -> None:
        filesystem.vehicle_components_fs.data["Components"]["ESC"] = {
            "Product": {"Manufacturer": "Hobbywing", "Model": "6XSE"}
        }

        assert model.is_hobbywing_6x_se()

    def test_uses_neutral_scale_for_other_products(self, model, filesystem) -> None:
        filesystem.vehicle_components_fs.data["Components"]["ESC"] = {"Product": {"Manufacturer": "Other", "Model": "6X SE"}}

        assert not model.is_hobbywing_6x_se()
        assert model.recommended_scale == 1.0


class TestScriptingProtocolDetection:
    """Verify ESC->FC telemetry protocol gate detection."""

    def test_detects_scripting_esc_telemetry_protocol(self, model, filesystem) -> None:
        filesystem.vehicle_components_fs.data["Components"]["ESC"] = {
            "ESC->FC Telemetry": {"Type": "SERIAL1", "Protocol": SCRIPTING_PROTOCOL}
        }

        assert model.is_scripting_telemetry_protocol()

    def test_returns_false_when_esc_telemetry_protocol_is_not_scripting(self, model, filesystem) -> None:
        filesystem.vehicle_components_fs.data["Components"]["ESC"] = {
            "ESC->FC Telemetry": {"Type": "SERIAL1", "Protocol": "ESC Telemetry"}
        }

        assert not model.is_scripting_telemetry_protocol()


_MOTOR_DATA = {
    "layouts": [
        {"Class": 1, "Type": 0, "motors": [{}, {}, {}, {}]},
        {"Class": 1, "Type": 1, "motors": [{}, {}, {}, {}]},
        {"Class": 2, "Type": 1, "motors": [{}, {}, {}, {}, {}, {}]},
        {"Class": 3, "Type": 1, "motors": [{}] * 8},
    ]
}


class TestEscCountDerivation:
    """Verify the ESC output count is derived from the FRAME_CLASS parameter."""

    @pytest.mark.parametrize(
        ("frame_class", "expected"),
        [(1, 4), (2, 6), (3, 8)],
    )
    def test_esc_count_for_frame_class_reads_layout(self, frame_class, expected) -> None:
        assert EscRpmScaleDataModel.esc_count_for_frame_class(frame_class, _MOTOR_DATA) == expected

    def test_esc_count_for_unknown_frame_class_returns_none(self) -> None:
        assert EscRpmScaleDataModel.esc_count_for_frame_class(99, _MOTOR_DATA) is None

    def test_esc_count_derives_from_frame_class_parameter(self, model, flight_controller) -> None:
        flight_controller.fc_parameters = {"FRAME_CLASS": 2.0}
        with patch.object(model._motor_data_loader, "load_json_data", return_value=_MOTOR_DATA):  # pylint: disable=protected-access
            assert model.esc_count() == 6

    def test_esc_count_supports_quadplane_frame_class(self, model, flight_controller) -> None:
        flight_controller.fc_parameters = {"Q_FRAME_CLASS": 3.0}
        with patch.object(model._motor_data_loader, "load_json_data", return_value=_MOTOR_DATA):  # pylint: disable=protected-access
            assert model.esc_count() == 8

    def test_esc_count_falls_back_without_frame_class(self, model, flight_controller) -> None:
        flight_controller.fc_parameters = {}
        assert model.esc_count() == FALLBACK_ESC_OUTPUT_COUNT

    def test_esc_count_falls_back_when_fc_not_connected(self, model, flight_controller) -> None:
        flight_controller.fc_parameters = None
        assert model.esc_count() == FALLBACK_ESC_OUTPUT_COUNT

    def test_esc_count_falls_back_for_unknown_frame_class(self, model, flight_controller) -> None:
        flight_controller.fc_parameters = {"FRAME_CLASS": 99.0}
        with patch.object(model._motor_data_loader, "load_json_data", return_value=_MOTOR_DATA):  # pylint: disable=protected-access
            assert model.esc_count() == FALLBACK_ESC_OUTPUT_COUNT

    def test_real_motor_data_covers_every_frame_class(self) -> None:
        """The shipped motor layout data must resolve a count for each frame class."""
        package_dir = Path(ardupilot_methodic_configurator.__file__).resolve().parent
        motor_data = json.loads((package_dir / "plugins" / "AP_Motors_test.json").read_text(encoding="utf-8"))
        for layout in motor_data["layouts"]:
            count = EscRpmScaleDataModel.esc_count_for_frame_class(layout["Class"], motor_data)
            assert count == len(layout["motors"])


class TestScriptGeneration:
    """Verify pure Lua script generation and local persistence."""

    def test_generates_scale_calls_for_requested_esc_outputs(self, model) -> None:
        assert model.generate_script(0.714, 4) == (
            "esc_telem:set_rpm_scale(0, 0.714)\n"
            "esc_telem:set_rpm_scale(1, 0.714)\n"
            "esc_telem:set_rpm_scale(2, 0.714)\n"
            "esc_telem:set_rpm_scale(3, 0.714)\n"
            'gcs:send_text(0, "LUA set RPM scale to 0.714")\n'
        )

    def test_generates_scale_calls_for_hexa_frame(self, model) -> None:
        script = model.generate_script(0.5, 6)
        assert script.count("esc_telem:set_rpm_scale(") == 6
        assert "esc_telem:set_rpm_scale(5, 0.5)" in script

    @pytest.mark.parametrize("scale_factor", [0.0, -1.0, inf, nan])
    def test_rejects_invalid_scale_factors(self, model, scale_factor) -> None:
        with pytest.raises(ValueError, match="finite positive"):
            model.generate_script(scale_factor, 4)

    def test_rejects_non_positive_esc_count(self, model) -> None:
        with pytest.raises(ValueError, match="output count must be positive"):
            model.generate_script(0.714, 0)

    def test_writes_script_to_active_vehicle_directory(self, model, tmp_path: Path) -> None:
        script_path = model.write_script(0.714)

        assert script_path == tmp_path / SCRIPT_FILENAME
        assert script_path.read_text(encoding="utf-8") == model.generate_script(0.714, model.esc_count())


class TestScriptUpload:
    """Verify the existing flight-controller upload API handoff."""

    def test_generates_file_before_uploading_with_existing_fc_api(self, model, flight_controller, tmp_path) -> None:
        assert model.generate_and_upload_script(0.714)

        script_path = tmp_path / SCRIPT_FILENAME
        assert script_path.is_file()
        flight_controller.upload_file.assert_called_once_with(str(script_path), SCRIPT_REMOTE_PATH, None)

    def test_does_not_generate_or_upload_without_fc_connection(self, model, flight_controller, tmp_path) -> None:
        flight_controller.master = None

        assert not model.generate_and_upload_script(0.714)
        assert not (tmp_path / SCRIPT_FILENAME).exists()
        flight_controller.upload_file.assert_not_called()


class TestConfigurationStepIntegration:
    """Verify every vehicle workflow exposes the plugin and enables scripting."""

    @pytest.mark.parametrize("vehicle_type", ["ArduCopter", "ArduPlane", "Heli", "Rover"])
    def test_esc_telemetry_step_registers_plugin(self, vehicle_type: str) -> None:
        package_dir = Path(ardupilot_methodic_configurator.__file__).resolve().parent
        config_path = package_dir / f"configuration_steps_{vehicle_type}.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        step = config["steps"]["09_esc_telemetry.param"]

        assert step["plugin"]["name"] == PLUGIN_ESC_RPM_SCALE
        assert step["plugin"]["placement"] == "left"
        if vehicle_type == "ArduCopter":
            assert step["plugin"].get("if") == "vehicle_components['ESC']['ESC->FC Telemetry']['Protocol'] == 'Scripting'"
        else:
            assert "if" not in step["plugin"]
        scripting_condition = step["derived_parameters"]["SCR_ENABLE"]["if"]
        assert scripting_condition == "vehicle_components['ESC']['ESC->FC Telemetry']['Protocol'] == 'Scripting'"


class TestPluginRegistration:
    """Verify factory registration wiring."""

    def test_registers_esc_rpm_scale_creator(self) -> None:
        with patch(
            "ardupilot_methodic_configurator.plugins.frontend_tkinter_esc_rpm_scale.plugin_factory.register"
        ) as register:
            register_esc_rpm_scale_plugin()

        register.assert_called_once()
        assert register.call_args.args[0] == PLUGIN_ESC_RPM_SCALE
