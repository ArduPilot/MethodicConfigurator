#!/usr/bin/env python3

"""
Acceptance tests for simulating FC parameters from a params.param file using --device=file.

These tests validate that users can create vehicle project templates and use parameter-dependent
features without requiring a physical flight controller by specifying --device=file on the command line.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import os
from argparse import ArgumentParser
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.backend_flightcontroller import DEVICE_FC_PARAM_FROM_FILE, FlightController
from ardupilot_methodic_configurator.backend_flightcontroller_params import FlightControllerParams
from ardupilot_methodic_configurator.data_model_vehicle_project_creator import (
    NewVehicleProjectSettings,
    VehicleProjectCreationError,
)

# pylint: disable=redefined-outer-name


@pytest.fixture
def temp_vehicle_dir() -> str:
    """Fixture providing a temporary directory for vehicle configuration."""
    with TemporaryDirectory(prefix="test_vehicle_") as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_params_file(temp_vehicle_dir: str) -> Path:
    """Fixture providing a sample params.param file for testing."""
    params_path = Path(temp_vehicle_dir) / "params.param"
    params_content = """FRAME_CLASS,1
FRAME_TYPE,1
INS_ACCEL_FILTER,20
INS_GYRO_FILTER,20
MOT_PWM_MAX,2000
MOT_PWM_MIN,1000
MOT_SPIN_ARM,0.1
MOT_SPIN_MIN,0.15
MOT_THST_EXPO,0.65
MOT_THST_HOVER,0.25
BATT_MONITOR,4
BATT_CAPACITY,5200
RC_SPEED,490
SERVO1_FUNCTION,33
SERVO2_FUNCTION,34
SERVO3_FUNCTION,35
SERVO4_FUNCTION,36
"""
    params_path.write_text(params_content, encoding="utf-8")
    return params_path


class TestCommandLineDeviceFileArgument:
    """Test --device=file command-line argument parsing and behavior."""

    def test_user_can_specify_device_file_on_command_line(self) -> None:
        """
        User can specify --device=file on command line to simulate FC parameters.

        GIVEN: User wants to create a template without a physical flight controller
        WHEN: They specify --device=file on the command line
        THEN: The argument should be parsed correctly
        AND: The device should be set to the file simulation constant
        """
        # Given: User wants file-based simulation
        parser = ArgumentParser(prog="amc")
        parser = FlightController.add_argparse_arguments(parser)

        # When: Parse --device=file argument
        args = parser.parse_args(["--device", "file"])

        # Then: Device correctly set to file simulation mode
        assert args.device == DEVICE_FC_PARAM_FROM_FILE
        assert args.device == "file"

    def test_device_file_constant_matches_command_line_value(self) -> None:
        """
        DEVICE_FC_PARAM_FROM_FILE constant matches expected command-line value.

        GIVEN: Developer uses DEVICE_FC_PARAM_FROM_FILE constant in code
        WHEN: User specifies --device=file on command line
        THEN: The constant should match the literal string "file"
        AND: Code using constant should work with command-line argument
        """
        # Given/When/Then: Constant matches expected value
        assert DEVICE_FC_PARAM_FROM_FILE == "file"


class TestFileBasedParameterSimulation:
    """Test loading and using FC parameters from params.param file."""

    def test_user_can_load_parameters_from_file_without_fc_connection(
        self,
        temp_vehicle_dir: str,  # pylint: disable=unused-argument
        sample_params_file: Path,
    ) -> None:
        """
        User can load FC parameters from params.param file without physical flight controller.

        GIVEN: User has params.param file in the current directory
        WHEN: They use --device=file to simulate FC parameters
        THEN: Parameters should be loaded from the file
        AND: No physical FC connection should be required
        """
        # Given: params.param file exists with test parameters
        # Create a mock connection manager for file simulation mode
        mock_conn_mgr = MagicMock()
        mock_conn_mgr.master = None  # No actual connection
        mock_conn_mgr.comport_device = DEVICE_FC_PARAM_FROM_FILE
        mock_conn_mgr.info = MagicMock()

        with patch("ardupilot_methodic_configurator.backend_flightcontroller.FlightController.discover_connections"):
            params_manager = FlightControllerParams(connection_manager=mock_conn_mgr)

            # When: Download parameters in file simulation mode (change to temp dir first)
            with patch("ardupilot_methodic_configurator.data_model_par_dict.open", create=True) as mock_open:
                # Mock file reading to return our sample params content
                mock_file = MagicMock()
                mock_file.__enter__.return_value = sample_params_file.read_text(encoding="utf-8").split("\n")
                mock_open.return_value = mock_file

                params, _defaults = params_manager.download_params()

            # Then: Parameters loaded from file successfully
            assert params is not None
            assert "FRAME_CLASS" in params
            assert params["FRAME_CLASS"] == 1.0
            assert "MOT_SPIN_ARM" in params
            assert params["MOT_SPIN_ARM"] == 0.1
            assert "BATT_MONITOR" in params
            assert params["BATT_MONITOR"] == 4.0

            # And: No FC connection was used
            assert params_manager.master is None

    def test_file_simulation_mode_detected_correctly(self) -> None:
        """
        File simulation mode is correctly detected when device is set to 'file'.

        GIVEN: Flight controller configured with --device=file
        WHEN: Code checks if running in file simulation mode
        THEN: Detection should correctly identify file mode
        AND: Appropriate code paths should be used
        """
        # Given: Connection manager configured for file simulation
        mock_conn_mgr = MagicMock()
        mock_conn_mgr.master = None
        mock_conn_mgr.comport_device = DEVICE_FC_PARAM_FROM_FILE
        mock_conn_mgr.info = MagicMock()

        # When: Create params manager
        with patch("ardupilot_methodic_configurator.backend_flightcontroller.FlightController.discover_connections"):
            params_manager = FlightControllerParams(connection_manager=mock_conn_mgr)

            # Then: File mode correctly detected
            assert params_manager.comport_device == DEVICE_FC_PARAM_FROM_FILE
            assert params_manager.master is None


class TestTemplateCreationWithFileBasedParameters:
    """Test creating vehicle project templates using file-based FC parameter simulation."""

    def test_parameter_dependent_settings_can_be_enabled_with_file_based_params(self) -> None:
        """
        Parameter-dependent settings can be enabled when file-based FC parameters are available.

        GIVEN: User has file-based FC parameters loaded
        WHEN: They configure parameter-dependent settings (component inference, use FC params)
        THEN: These settings should be valid and functional
        AND: Feature behavior should match physical FC connection
        """
        # Given: File-based parameters available (connection=False, but parameters present)
        fc_connected = False  # File simulation - no connection
        fc_parameters = {
            "FRAME_CLASS": 1.0,
            "FRAME_TYPE": 1.0,
            "BATT_MONITOR": 4.0,
            "INS_GYRO_FILTER": 20.0,
        }

        # When: Create settings with parameter-dependent features enabled
        settings = NewVehicleProjectSettings(
            use_fc_params=True,
            infer_comp_specs_and_conn_from_fc_params=True,
        )

        # Then: Settings should validate successfully with parameters (even without connection)
        try:
            settings.validate_fc_dependent_settings(fc_connected, fc_parameters)
        except VehicleProjectCreationError as e:
            pytest.fail(f"Parameter-dependent settings should be valid with fc_parameters: {e}")

    def test_connection_dependent_settings_fail_without_connection(self) -> None:
        """
        Connection-dependent settings fail validation in file simulation mode.

        GIVEN: User has file-based FC parameters but no physical connection
        WHEN: They try to enable connection-dependent settings (parameter reset)
        THEN: Validation should fail with clear error message
        AND: User should understand connection is required for this feature
        """
        # Given: File simulation (no connection, but parameters available)
        fc_connected = False
        fc_parameters = {
            "FRAME_CLASS": 1.0,
        }

        # When: Try to enable connection-dependent reset feature
        settings = NewVehicleProjectSettings(
            reset_fc_parameters_to_their_defaults=True,  # Requires connection
        )

        # Then: Should fail validation without connection
        with pytest.raises(VehicleProjectCreationError, match="no flight controller connected"):
            settings.validate_fc_dependent_settings(fc_connected, fc_parameters)


class TestConnectionDependentFeaturesDisabledWithFileSimulation:
    """Test that connection-dependent features are properly disabled in file simulation mode."""

    def test_static_metadata_distinguishes_connection_vs_parameter_dependencies(self) -> None:
        """
        Static metadata correctly identifies which features need connection vs parameters.

        GIVEN: User reviewing available template creation features
        WHEN: They check which features require connection vs just parameters
        THEN: System should clearly distinguish between the two types
        AND: File simulation mode can use parameter-dependent features
        """
        # Given: Check feature requirements without connection
        fc_connected = False
        fc_parameters = {"FRAME_CLASS": 1.0}

        # When/Then: Connection-dependent feature should be disabled
        metadata = NewVehicleProjectSettings.get_setting_metadata(
            "reset_fc_parameters_to_their_defaults",
            fc_connected,
            fc_parameters,
        )
        assert metadata.enabled is False
        # Disabled features don't show error in tooltip, but in the enabled flag

        # When/Then: Parameter-dependent feature should be enabled with parameters
        metadata = NewVehicleProjectSettings.get_setting_metadata(
            "use_fc_params",
            fc_connected,
            fc_parameters,
        )
        assert metadata.enabled is True  # Has parameters, doesn't need connection

    def test_parameter_dependent_features_work_independently_of_connection(self) -> None:
        """
        Parameter-dependent features work with file-based params even without connection.

        GIVEN: Parameters loaded from file without physical FC connection
        WHEN: User checks which features are available
        THEN: Parameter-dependent features should be enabled
        AND: Connection-dependent features should be disabled
        """
        # Given: File-based parameters without connection
        fc_connected = False  # No connection
        fc_parameters = {
            "FRAME_CLASS": 1.0,
            "BATT_MONITOR": 4.0,
        }

        # When/Then: Parameter-dependent features enabled
        assert NewVehicleProjectSettings.is_setting_enabled("use_fc_params", fc_connected, fc_parameters) is True
        assert (
            NewVehicleProjectSettings.is_setting_enabled(
                "infer_comp_specs_and_conn_from_fc_params", fc_connected, fc_parameters
            )
            is True
        )

        # When/Then: Connection-dependent features disabled
        assert (
            NewVehicleProjectSettings.is_setting_enabled("reset_fc_parameters_to_their_defaults", fc_connected, fc_parameters)
            is False
        )


class TestFileSimulationErrorHandling:
    """Test error handling when params.param file is missing or invalid."""

    def test_clear_error_when_params_file_missing(self, temp_vehicle_dir: str) -> None:
        """
        User gets clear error when params.param file is missing in file simulation mode.

        GIVEN: User specifies --device=file but params.param doesn't exist
        WHEN: System tries to load parameters from file
        THEN: Clear error message should indicate missing file
        AND: User should understand they need to provide params.param
        """
        # Given: File simulation mode without params.param file
        mock_conn_mgr = MagicMock()
        mock_conn_mgr.master = None
        mock_conn_mgr.comport_device = DEVICE_FC_PARAM_FROM_FILE
        mock_conn_mgr.info = MagicMock()

        with patch("ardupilot_methodic_configurator.backend_flightcontroller.FlightController.discover_connections"):
            params_manager = FlightControllerParams(connection_manager=mock_conn_mgr)

            # When/Then: Attempting to download params should raise appropriate error
            with (
                patch(
                    "ardupilot_methodic_configurator.backend_flightcontroller_params.Path.cwd",
                    return_value=Path(temp_vehicle_dir),
                ),
                pytest.raises(FileNotFoundError, match=r"params.param"),
            ):
                params_manager.download_params()

    def test_file_simulation_requires_no_master_connection(self) -> None:
        """
        File simulation mode works correctly without MAVLink master connection.

        GIVEN: User using --device=file for parameter simulation
        WHEN: System operates in file simulation mode
        THEN: No master connection should be required
        AND: All parameter operations should work with master=None
        """
        # Given/When: File simulation mode initialized
        mock_conn_mgr = MagicMock()
        mock_conn_mgr.master = None  # No master connection required
        mock_conn_mgr.comport_device = DEVICE_FC_PARAM_FROM_FILE
        mock_conn_mgr.info = MagicMock()

        with patch("ardupilot_methodic_configurator.backend_flightcontroller.FlightController.discover_connections"):
            params_manager = FlightControllerParams(connection_manager=mock_conn_mgr)

            # Then: Operates correctly without master
            assert params_manager.master is None
            assert params_manager.comport_device == DEVICE_FC_PARAM_FROM_FILE


class TestBackendParameterFileReadingIntegration:
    """Integration tests for actual file reading in backend without heavy mocking."""

    def test_backend_actually_reads_params_from_real_file(self, sample_params_file: Path) -> None:
        """
        Backend actually reads and parses a real params.param file without mocking file I/O.

        GIVEN: A real params.param file exists in the working directory
        WHEN: FlightControllerParams.download_params() is called with device=file
        THEN: Parameters should be read from the actual file using ParDict.from_file
        AND: All parameter values should be correctly parsed
        """
        # Given: Real params.param file exists
        original_cwd = os.getcwd()
        try:
            # Change to directory with params.param
            os.chdir(sample_params_file.parent)

            # Create connection manager for file simulation
            mock_conn_mgr = MagicMock()
            mock_conn_mgr.master = None
            mock_conn_mgr.comport_device = DEVICE_FC_PARAM_FROM_FILE
            mock_conn_mgr.info = MagicMock()

            with patch("ardupilot_methodic_configurator.backend_flightcontroller.FlightController.discover_connections"):
                params_manager = FlightControllerParams(connection_manager=mock_conn_mgr)

                # When: Download parameters (NO MOCKING of file operations)
                params, defaults = params_manager.download_params()

            # Then: Parameters read from actual file
            assert params is not None
            assert len(params) > 0

            # Verify specific parameters from our sample file
            assert "FRAME_CLASS" in params
            assert params["FRAME_CLASS"] == 1.0
            assert "FRAME_TYPE" in params
            assert params["FRAME_TYPE"] == 1.0
            assert "MOT_SPIN_ARM" in params
            assert params["MOT_SPIN_ARM"] == 0.1
            assert "BATT_MONITOR" in params
            assert params["BATT_MONITOR"] == 4.0
            assert "RC_SPEED" in params
            assert params["RC_SPEED"] == 490.0

            # Verify parameters were stored in manager
            assert params_manager.fc_parameters == params

            # Defaults should be empty for file mode
            assert len(defaults) == 0

        finally:
            os.chdir(original_cwd)

    def test_backend_parameter_file_reading_with_comments(self, temp_vehicle_dir: str) -> None:
        """
        Backend correctly handles params.param file with comments and blank lines.

        GIVEN: A params.param file with comments, blank lines, and various formats
        WHEN: Parameters are loaded from the file
        THEN: Comments and blank lines should be ignored
        AND: Only valid parameter lines should be parsed
        """
        # Given: params.param with comments and blank lines
        params_path = Path(temp_vehicle_dir) / "params.param"
        params_content = """# This is a comment
FRAME_CLASS,1

# Another comment with blank line above
FRAME_TYPE,1  # inline comment
MOT_SPIN_ARM,0.1

BATT_MONITOR,4
"""
        params_path.write_text(params_content, encoding="utf-8")

        original_cwd = os.getcwd()
        try:
            os.chdir(temp_vehicle_dir)

            mock_conn_mgr = MagicMock()
            mock_conn_mgr.master = None
            mock_conn_mgr.comport_device = DEVICE_FC_PARAM_FROM_FILE
            mock_conn_mgr.info = MagicMock()

            with patch("ardupilot_methodic_configurator.backend_flightcontroller.FlightController.discover_connections"):
                params_manager = FlightControllerParams(connection_manager=mock_conn_mgr)

                # When: Load parameters from file with comments
                params, _defaults = params_manager.download_params()

            # Then: Only valid parameters extracted, comments ignored
            assert len(params) == 4
            assert params["FRAME_CLASS"] == 1.0
            assert params["FRAME_TYPE"] == 1.0
            assert params["MOT_SPIN_ARM"] == 0.1
            assert params["BATT_MONITOR"] == 4.0

        finally:
            os.chdir(original_cwd)


class TestFrontendIntegrationWithFileBasedParameters:
    """Integration tests for frontend GUI behavior with file-based FC parameters."""

    def test_frontend_enables_parameter_dependent_checkboxes_with_file_params(self) -> None:
        """
        Frontend correctly enables parameter-dependent checkboxes when fc_parameters available.

        GIVEN: Frontend receives fc_parameters from file (fc_connected=False)
        WHEN: GUI requests settings metadata for checkbox state
        THEN: Parameter-dependent checkboxes should be enabled
        AND: Connection-dependent checkboxes should be disabled
        """
        # Given: File-based parameters (no connection)
        fc_connected = False
        fc_parameters = {
            "FRAME_CLASS": 1.0,
            "FRAME_TYPE": 1.0,
            "BATT_MONITOR": 4.0,
        }

        # When: Frontend gets all settings metadata (simulating GUI initialization)
        all_metadata = NewVehicleProjectSettings.get_all_settings_metadata(fc_connected, fc_parameters)

        # Then: Parameter-dependent features enabled
        assert "use_fc_params" in all_metadata
        assert all_metadata["use_fc_params"].enabled is True

        assert "infer_comp_specs_and_conn_from_fc_params" in all_metadata
        assert all_metadata["infer_comp_specs_and_conn_from_fc_params"].enabled is True

        # And: Connection-dependent features disabled
        assert "reset_fc_parameters_to_their_defaults" in all_metadata
        assert all_metadata["reset_fc_parameters_to_their_defaults"].enabled is False

        # And: Non-dependent features always enabled
        assert "blank_component_data" in all_metadata
        assert all_metadata["blank_component_data"].enabled is True

    def test_frontend_disables_all_fc_features_without_params(self) -> None:
        """
        Frontend disables all FC-dependent features when no parameters available.

        GIVEN: No FC connection and no parameters (typical startup state)
        WHEN: GUI requests settings metadata
        THEN: All FC-dependent checkboxes should be disabled
        AND: Only non-FC-dependent options should be enabled
        """
        # Given: No connection, no parameters
        fc_connected = False
        fc_parameters = None

        # When: Get metadata for GUI
        all_metadata = NewVehicleProjectSettings.get_all_settings_metadata(fc_connected, fc_parameters)

        # Then: All FC-dependent features disabled
        assert all_metadata["use_fc_params"].enabled is False
        assert all_metadata["infer_comp_specs_and_conn_from_fc_params"].enabled is False
        assert all_metadata["reset_fc_parameters_to_their_defaults"].enabled is False

        # And: Non-dependent features enabled
        assert all_metadata["blank_component_data"].enabled is True
        assert all_metadata["copy_vehicle_image"].enabled is True
        assert all_metadata["blank_change_reason"].enabled is True

    def test_frontend_checkbox_states_match_backend_validation_logic(self) -> None:
        """
        Frontend checkbox states match backend validation to prevent user confusion.

        GIVEN: Various FC connection and parameter states
        WHEN: Frontend displays checkboxes and user attempts to use settings
        THEN: Enabled checkboxes should pass backend validation
        AND: Disabled checkboxes would fail backend validation if forced
        """
        test_cases = [
            # (fc_connected, fc_parameters, setting_name, should_be_enabled)
            (False, None, "use_fc_params", False),
            (False, {"FRAME_CLASS": 1.0}, "use_fc_params", True),
            (True, {"FRAME_CLASS": 1.0}, "use_fc_params", True),
            (False, None, "reset_fc_parameters_to_their_defaults", False),
            (False, {"FRAME_CLASS": 1.0}, "reset_fc_parameters_to_their_defaults", False),
            (True, {"FRAME_CLASS": 1.0}, "reset_fc_parameters_to_their_defaults", True),
            (False, None, "blank_component_data", True),
            (True, None, "blank_component_data", True),
        ]

        for fc_connected, fc_parameters, setting_name, expected_enabled in test_cases:
            # When: Check if setting should be enabled in GUI
            is_enabled = NewVehicleProjectSettings.is_setting_enabled(setting_name, fc_connected, fc_parameters)

            # Then: Should match expected state
            assert is_enabled == expected_enabled, (
                f"Setting {setting_name} with fc_connected={fc_connected}, "
                f"fc_parameters={fc_parameters} should be {expected_enabled}"
            )

            # And: Backend validation should align with GUI state
            if expected_enabled:
                # If GUI shows enabled, backend validation should pass
                settings = NewVehicleProjectSettings(**{setting_name: True})
                try:
                    settings.validate_fc_dependent_settings(fc_connected, fc_parameters)
                except VehicleProjectCreationError:
                    pytest.fail(f"Enabled setting {setting_name} failed backend validation")
            else:
                # If GUI shows disabled, backend validation should fail if user forced it
                settings = NewVehicleProjectSettings(**{setting_name: True})
                if NewVehicleProjectSettings.is_fc_conn_dependent_setting(
                    setting_name
                ) or NewVehicleProjectSettings.is_fc_param_dependent_setting(setting_name):
                    with pytest.raises(VehicleProjectCreationError):
                        settings.validate_fc_dependent_settings(fc_connected, fc_parameters)
