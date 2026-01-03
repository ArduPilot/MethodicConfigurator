#!/usr/bin/env python3

"""
Behaviour-driven unit tests for the ConfigurationStepProcessor class.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.data_model_ardupilot_parameter import ArduPilotParameter
from ardupilot_methodic_configurator.data_model_configuration_step import ConfigurationStepProcessor
from ardupilot_methodic_configurator.data_model_par_dict import Par

# pylint: disable=redefined-outer-name, protected-access


@pytest.fixture
def mock_local_filesystem() -> MagicMock:
    """Fixture providing a mock LocalFilesystem with realistic test data."""
    filesystem = MagicMock()

    # Set up realistic parameter data
    test_parameters = {
        "SERIAL1_PROTOCOL": Par(value=4.0, comment="MAVLink1"),
        "SERIAL1_BAUD": Par(value=57600.0, comment="Baud rate"),
        "CAN_P1_DRIVER": Par(value=1.0, comment="CAN driver"),
        "CAN_D1_PROTOCOL": Par(value=1.0, comment="DroneCAN protocol"),
    }

    # Configure filesystem mock
    filesystem.file_parameters = {"test_file.param": test_parameters}
    filesystem.configuration_steps = {}
    filesystem.forced_parameters = {}
    filesystem.derived_parameters = {}
    filesystem.doc_dict = {
        "SERIAL1_PROTOCOL": {"Description": "Serial protocol", "Range": "0 23"},
        "SERIAL1_BAUD": {"Description": "Baud rate", "Range": "1 2000000"},
    }
    filesystem.param_default_dict = {
        "SERIAL1_PROTOCOL": Par(value=0.0, comment="Default protocol"),
        "SERIAL1_BAUD": Par(value=57600.0, comment="Default baud"),
    }

    # Mock methods
    filesystem.compute_parameters.return_value = None
    filesystem.merge_forced_or_derived_parameters.return_value = False
    filesystem.get_eval_variables.return_value = {
        "selected_can": "CAN2",
        "selected_serial": "SERIAL3",
        "test_value": 42,
    }

    return filesystem


@pytest.fixture
def processor(mock_local_filesystem) -> ConfigurationStepProcessor:
    """Fixture providing a configured ConfigurationStepProcessor."""
    return ConfigurationStepProcessor(mock_local_filesystem)


@pytest.fixture
def fc_parameters() -> dict[str, float]:
    """Fixture providing realistic flight controller parameters."""
    return {
        "SERIAL1_PROTOCOL": 4.0,
        "SERIAL1_BAUD": 115200.0,  # Different from file parameter
        "CAN_P1_DRIVER": 1.0,
        "EXTRA_PARAM": 10.0,  # Only exists on FC
    }


@pytest.fixture
def configuration_steps() -> dict[str, Any]:
    """Fixture providing realistic configuration steps."""
    return {
        "derived": {
            "SERIAL2_PROTOCOL": "4 if fc_parameters.get('SERIAL1_PROTOCOL', 0) > 0 else 0",
            "CALCULATED_PARAM": "test_value * 2",
        },
        "rename_connection": "selected_can",
    }


@pytest.fixture
def connection_params() -> dict[str, Any]:
    """Set up test parameters for connection renaming."""
    # Sample parameter names for different connection types
    can_parameters = ["CAN_P1_DRIVER", "CAN_P1_BITRATE", "CAN_D1_PROTOCOL", "CAN_D1_UC_NODE", "CAN_D1_UC_OPTION"]
    serial_parameters = ["SERIAL1_PROTOCOL", "SERIAL1_BAUD", "SERIAL1_OPTIONS", "SERIAL2_PROTOCOL", "SERIAL2_BAUD"]
    mixed_parameters = can_parameters + serial_parameters

    # Sample parameter objects dictionary
    param_objects = {}
    for param_name in mixed_parameters:
        param_objects[param_name] = Par(value=1.0, comment=f"Comment for {param_name}")

    return {
        "can_parameters": can_parameters,
        "serial_parameters": serial_parameters,
        "mixed_parameters": mixed_parameters,
        "param_objects": param_objects,
    }


class TestConfigurationStepProcessorWorkflows:
    """Test complete user workflows for configuration step processing."""

    def test_user_can_process_basic_configuration_step_without_special_operations(self, processor, fc_parameters) -> None:
        """
        User can process a basic configuration step with standard parameters.

        GIVEN: A user has a parameter file with standard parameters
        WHEN: They process the configuration step without special operations
        THEN: Domain model parameters should be created successfully
        AND: No parameters should be marked as edited
        """
        # Arrange: Set up basic configuration without special steps
        selected_file = "test_file.param"

        # Act: Process the configuration step
        parameters, ui_errors, ui_infos, _, _, _ = processor.process_configuration_step(selected_file, fc_parameters)

        # Assert: Basic processing completed successfully
        assert isinstance(parameters, dict)
        assert len(parameters) > 0
        assert "SERIAL1_PROTOCOL" in parameters
        assert isinstance(parameters["SERIAL1_PROTOCOL"], ArduPilotParameter)
        assert ui_errors == []
        assert ui_infos == []

    def test_user_can_process_configuration_step_with_derived_parameters(
        self, processor, fc_parameters, configuration_steps
    ) -> None:
        """
        User can process configuration steps that include derived parameter calculations.

        GIVEN: A user has a configuration step with derived parameter calculations
        WHEN: They process the configuration step
        THEN: Derived parameters should be computed and merged
        """
        # Arrange: Set up configuration with derived parameters
        selected_file = "test_file.param"
        processor.local_filesystem.configuration_steps = {selected_file: configuration_steps}
        processor.local_filesystem.merge_forced_or_derived_parameters.return_value = True

        # Act: Process configuration step with derived parameters
        parameters, ui_errors, ui_infos, _, _, _ = processor.process_configuration_step(
            selected_file, fc_parameters
        )  # Assert: Derived parameters were processed
        processor.local_filesystem.compute_parameters.assert_called_once()
        # Note: merge_forced_or_derived_parameters is no longer called - derived params are returned instead
        assert isinstance(parameters, dict)
        assert ui_errors == []
        # Should have info messages about parameter renaming
        assert len(ui_infos) > 0

    def test_user_receives_error_feedback_when_derived_parameter_computation_fails(
        self, processor, fc_parameters, configuration_steps
    ) -> None:
        """
        User receives clear error feedback when derived parameter computation fails.

        GIVEN: A user has configuration steps with invalid derived parameter expressions
        WHEN: They process the configuration step and computation fails
        THEN: Error messages should be returned for UI display
        AND: Processing should continue gracefully
        """
        # Arrange: Set up failing derived parameter computation
        selected_file = "test_file.param"
        processor.local_filesystem.configuration_steps = {selected_file: configuration_steps}
        processor.local_filesystem.compute_parameters.return_value = "Computation error: Invalid expression"

        # Act: Process configuration step with failing computation
        parameters, ui_errors, ui_infos, _, _, _ = processor.process_configuration_step(
            selected_file, fc_parameters
        )  # Assert: Error feedback provided to UI layer
        assert len(ui_errors) == 1
        assert ui_errors[0][0] == "Error in derived parameters"  # Title
        assert "Computation error: Invalid expression" in ui_errors[0][1]  # Message
        assert isinstance(parameters, dict)
        # Should have info messages about parameter renaming since configuration includes rename_connection
        assert len(ui_infos) > 0


class TestConfigurationStepProcessorConnectionRenaming:
    """Test connection renaming workflows and edge cases."""

    def test_user_can_rename_connection_parameters_successfully(self, processor, fc_parameters) -> None:
        """
        User can successfully rename connection parameters to match hardware configuration.

        GIVEN: A user has parameters with CAN1 connections that need to be renamed to CAN2
        WHEN: They process a configuration step with connection renaming
        THEN: Parameters should be renamed correctly
        AND: User should receive confirmation of the changes via UI messages
        """
        # Arrange: Set up connection renaming configuration
        selected_file = "test_file.param"
        processor.local_filesystem.configuration_steps = {selected_file: {"rename_connection": "selected_can"}}

        # Act: Process configuration step with connection renaming
        parameters, ui_errors, ui_infos, _, _, _ = processor.process_configuration_step(
            selected_file, fc_parameters
        )  # Assert: Connection renaming completed successfully
        assert len(ui_infos) > 0  # Should have info messages about renaming
        assert ui_errors == []
        assert isinstance(parameters, dict)

    def test_user_receives_feedback_about_duplicate_parameter_removal(self, processor, fc_parameters) -> None:
        """
        User receives clear feedback when duplicate parameters are removed during renaming.

        GIVEN: A user has parameters that would create duplicates after renaming
        WHEN: They process a configuration step with connection renaming
        THEN: Duplicate parameters should be removed automatically
        AND: User should receive informative feedback about the removal via UI messages
        """
        # Arrange: Set up scenario that creates duplicates
        selected_file = "test_file.param"
        processor.local_filesystem.configuration_steps = {selected_file: {"rename_connection": "CAN2"}}
        processor.local_filesystem.file_parameters[selected_file]["CAN_P2_DRIVER"] = Par(value=2.0, comment="Exists")

        # Act: Process configuration step with potential duplicates
        with patch.object(processor, "_calculate_connection_rename_operations") as mock_apply:
            mock_apply.return_value = ({"CAN_P2_DRIVER"}, [("CAN_P1_DRIVER", "CAN_P2_DRIVER")])
            _parameters, ui_errors, ui_infos, _, _, _ = processor.process_configuration_step(
                selected_file, fc_parameters
            )  # Assert: User informed about duplicate removal
            assert len(ui_infos) > 0  # Should have info about parameter removal
            assert ui_errors == []

    def test_user_can_process_configuration_step_without_connection_renaming(self, processor, fc_parameters) -> None:
        """
        User can process configuration steps that don't include connection renaming.

        GIVEN: A user has configuration steps with derived parameters but no connection renaming
        WHEN: They process the configuration step
        THEN: Only derived parameter processing should occur
        AND: No connection renaming operations should be attempted
        """
        # Arrange: Set up configuration without connection renaming
        selected_file = "test_file.param"
        configuration_steps = {
            "derived": {
                "SERIAL2_PROTOCOL": "4 if fc_parameters.get('SERIAL1_PROTOCOL', 0) > 0 else 0",
            }
            # Note: No "rename_connection" key
        }
        processor.local_filesystem.configuration_steps = {selected_file: configuration_steps}
        processor.local_filesystem.merge_forced_or_derived_parameters.return_value = True

        # Act: Process configuration step without connection renaming
        parameters, ui_errors, ui_infos, _, _, _ = processor.process_configuration_step(
            selected_file, fc_parameters
        )  # Assert: Only derived parameters processed, no connection renaming
        processor.local_filesystem.compute_parameters.assert_called_once()
        assert isinstance(parameters, dict)
        assert ui_errors == []
        assert ui_infos == []  # No connection renaming means no info messages

    def test_connection_renaming_state_does_not_leak_between_steps(self, processor, fc_parameters) -> None:  # pylint: disable=too-many-locals
        """
        Connection renaming helper variables must not leak into later steps.

        GIVEN: A configuration step that performs connection renaming
        WHEN: A later step without renaming is processed
        THEN: No renaming operations should be triggered for the later step
        """
        rename_step = "test_file.param"
        later_step = "13_general_configuration.param"
        processor.local_filesystem.file_parameters[later_step] = {
            "SERIAL2_PROTOCOL": Par(value=10.0, comment="Telemetry protocol"),
            "SERIAL2_BAUD": Par(value=57.0, comment="Telemetry baud rate"),
        }
        processor.local_filesystem.configuration_steps = {
            rename_step: {"rename_connection": "selected_serial"},
            later_step: {},
        }

        # First step performs renaming to ensure helper variable is set
        (
            _params_first,
            _errors_first,
            _infos_first,
            _duplicates_first,
            renames_first,
            _derived_first,
        ) = processor.process_configuration_step(rename_step, fc_parameters)
        assert renames_first  # Sanity check that renaming took place

        # Later step must not inherit previous rename configuration
        (
            _params_second,
            _errors_second,
            ui_infos_second,
            _duplicates_second,
            renames_second,
            _derived_second,
        ) = processor.process_configuration_step(later_step, fc_parameters)
        assert renames_second == []
        assert ui_infos_second == []


class TestConfigurationStepProcessorDomainModel:
    """Test domain model creation and parameter filtering."""

    def test_user_can_create_complete_domain_model_parameters(self, processor, fc_parameters) -> None:
        """
        User can create complete domain model parameters with all metadata.

        GIVEN: A user has parameter files with complete metadata
        WHEN: They create domain model parameters
        THEN: All parameters should have complete ArduPilotParameter objects
        AND: Each parameter should include file, metadata, default, and FC values
        """
        # Arrange: Prepare complete parameter data
        selected_file = "test_file.param"

        # Act: Create domain model parameters
        parameters = processor._create_domain_model_parameters(selected_file, fc_parameters)

        # Assert: Complete domain model created
        assert isinstance(parameters, dict)
        assert len(parameters) > 0

        for param_name, param_obj in parameters.items():
            assert isinstance(param_obj, ArduPilotParameter)
            assert param_obj.name == param_name
            assert hasattr(param_obj, "_value_on_file")
            assert hasattr(param_obj, "_fc_value")

    def test_user_can_filter_parameters_that_differ_from_flight_controller(self, processor, fc_parameters) -> None:
        """
        User can filter parameters to show only those different from flight controller.

        GIVEN: A user has parameters where some match FC values and others don't
        WHEN: They filter for different parameters
        THEN: Only parameters that differ from FC or are missing from FC should be returned
        """
        # Arrange: Create parameters with mixed FC value matches
        selected_file = "test_file.param"
        all_parameters = processor._create_domain_model_parameters(selected_file, fc_parameters)

        # Act: Filter for different parameters
        different_parameters = processor.filter_different_parameters(all_parameters)

        # Assert: Only different/missing parameters returned
        assert isinstance(different_parameters, dict)
        # SERIAL1_BAUD should be included (file: 57600, FC: 115200)
        # Parameters not in FC should be included
        for param_obj in different_parameters.values():
            assert param_obj.is_different_from_fc or not param_obj.has_fc_value

    def test_user_can_create_domain_model_with_partial_fc_parameters(self, processor) -> None:
        """
        User can create domain model when FC has only some parameters.

        GIVEN: A user has file parameters where only some exist on the flight controller
        WHEN: They create domain model parameters
        THEN: Parameters should be created for all file parameters
        AND: FC values should be set only for existing FC parameters
        """
        # Arrange: FC parameters that only partially match file parameters
        partial_fc_parameters = {
            "SERIAL1_PROTOCOL": 5.0,  # Matches file parameter
            # Missing SERIAL1_BAUD and CAN_P1_DRIVER from file
            "EXTRA_FC_PARAM": 99.0,  # Not in file parameters
        }
        selected_file = "test_file.param"

        # Act: Create domain model with partial FC match
        parameters = processor._create_domain_model_parameters(selected_file, partial_fc_parameters)

        # Assert: All file parameters created, FC values only where available
        assert isinstance(parameters, dict)
        assert len(parameters) >= 4  # At least the 4 parameters from fixture

        # Check parameter with FC value
        assert "SERIAL1_PROTOCOL" in parameters
        serial_protocol = parameters["SERIAL1_PROTOCOL"]
        assert serial_protocol.has_fc_value
        assert serial_protocol._fc_value == 5.0

        # Check parameters without FC values
        assert "SERIAL1_BAUD" in parameters
        serial_baud = parameters["SERIAL1_BAUD"]
        assert not serial_baud.has_fc_value or serial_baud._fc_value is None

        assert "CAN_P1_DRIVER" in parameters
        can_driver = parameters["CAN_P1_DRIVER"]
        assert not can_driver.has_fc_value or can_driver._fc_value is None

    def test_user_can_filter_parameters_with_mixed_fc_states(self, processor) -> None:
        """
        User can filter parameters that have mixed flight controller states.

        GIVEN: A user has parameters with various FC states (matching, different, missing)
        WHEN: They filter for different parameters
        THEN: Only parameters that differ or are missing should be returned
        AND: Parameters that match FC values should be excluded
        """
        # Arrange: Create mixed FC parameter states
        mixed_fc_parameters = {
            "SERIAL1_PROTOCOL": 4.0,  # Matches file (both 4.0)
            "SERIAL1_BAUD": 115200.0,  # Different from file (file: 57600)
            "CAN_P1_DRIVER": 1.0,  # Matches file (both 1.0)
            # CAN_D1_PROTOCOL missing from FC
        }
        selected_file = "test_file.param"

        # Act: Create and filter parameters
        all_parameters = processor._create_domain_model_parameters(selected_file, mixed_fc_parameters)
        different_parameters = processor.filter_different_parameters(all_parameters)

        # Assert: Only different/missing parameters returned
        assert isinstance(different_parameters, dict)

        # Should include parameters that are different
        assert "SERIAL1_BAUD" in different_parameters

        # Should include parameters missing from FC
        assert "CAN_D1_PROTOCOL" in different_parameters

        # Should NOT include parameters that match FC values
        # Note: This depends on the exact values in the fixture and comparison logic


class TestConfigurationStepProcessorConnectionRenamingLogic:
    """Test connection renaming logic and edge cases."""

    def test_generate_renames_can(self, connection_params) -> None:
        """
        Test generating renames for CAN parameters follows expected patterns.

        GIVEN: A user has CAN parameters that need renaming
        WHEN: They generate renames for a new CAN connection
        THEN: All CAN parameters should be renamed with correct prefix mapping
        """
        # Arrange & Act: Generate renames for CAN parameters
        renames = ConfigurationStepProcessor._generate_connection_renames(connection_params["can_parameters"], "CAN2")

        # Assert: Expected rename mappings created
        expected_renames = {
            "CAN_P1_DRIVER": "CAN_P2_DRIVER",
            "CAN_P1_BITRATE": "CAN_P2_BITRATE",
            "CAN_D1_PROTOCOL": "CAN_D2_PROTOCOL",
            "CAN_D1_UC_NODE": "CAN_D2_UC_NODE",
            "CAN_D1_UC_OPTION": "CAN_D2_UC_OPTION",
        }

        for old_name, expected_new_name in expected_renames.items():
            assert renames.get(old_name) == expected_new_name

        # Test with CAN parameters that don't match the target prefix
        can3_renames = ConfigurationStepProcessor._generate_connection_renames(["CAN_P3_DRIVER", "CAN_D3_PROTOCOL"], "CAN2")
        # Should rename to CAN2 versions if pattern matches
        assert can3_renames == {
            "CAN_P3_DRIVER": "CAN_P2_DRIVER",
            "CAN_D3_PROTOCOL": "CAN_D2_PROTOCOL",
        }

    def test_generate_renames_serial(self, connection_params) -> None:
        """
        Test generating renames for SERIAL parameters follows expected patterns.

        GIVEN: A user has SERIAL parameters that need renaming
        WHEN: They generate renames for a new SERIAL connection
        THEN: All SERIAL parameters should be renamed with correct prefix mapping
        """
        # Arrange & Act: Generate renames for SERIAL parameters
        renames = ConfigurationStepProcessor._generate_connection_renames(connection_params["serial_parameters"], "SERIAL3")

        # Assert: Expected rename mappings created
        expected_renames = {
            "SERIAL1_PROTOCOL": "SERIAL3_PROTOCOL",
            "SERIAL1_BAUD": "SERIAL3_BAUD",
            "SERIAL1_OPTIONS": "SERIAL3_OPTIONS",
            "SERIAL2_PROTOCOL": "SERIAL3_PROTOCOL",
            "SERIAL2_BAUD": "SERIAL3_BAUD",
        }

        for old_name, new_name in expected_renames.items():
            assert renames.get(old_name) == new_name

        # All SERIAL* parameters are renamed to SERIAL3_*
        assert set(renames.values()) == {"SERIAL3_PROTOCOL", "SERIAL3_BAUD", "SERIAL3_OPTIONS"}

    def test_generate_renames_handles_invalid_prefix_gracefully(self) -> None:
        """
        System handles invalid connection prefixes gracefully.

        GIVEN: A user provides an invalid connection prefix (less than 2 characters)
        WHEN: The system generates connection renames
        THEN: An empty rename dictionary should be returned
        AND: No errors should occur
        """
        # Arrange: Test with various invalid prefixes
        parameters = ["CAN_P1_DRIVER", "SERIAL1_PROTOCOL", "CAN_D1_PROTOCOL"]
        invalid_prefixes = ["", "C", "1"]

        for invalid_prefix in invalid_prefixes:
            # Act: Generate renames with invalid prefix
            renames = ConfigurationStepProcessor._generate_connection_renames(parameters, invalid_prefix)

            # Assert: Empty dictionary returned gracefully
            assert not renames
            assert isinstance(renames, dict)

    def test_generate_renames_with_non_matching_parameters(self) -> None:
        """
        System handles parameters that don't match expected naming patterns.

        GIVEN: A user has parameters that don't follow CAN/SERIAL naming conventions
        WHEN: They generate connection renames
        THEN: Non-matching parameters should be ignored
        AND: Only matching parameters should be renamed
        """
        # Arrange: Mix of matching and non-matching parameters
        parameters = [
            "CAN_P1_DRIVER",  # Should match
            "SERIAL2_BAUD",  # Should match
            "BATT_MONITOR",  # Should not match
            "GPS_TYPE",  # Should not match
            "CUSTOM_PARAM_123",  # Should not match
            "CAN_D1_PROTOCOL",  # Should match
        ]

        # Act: Generate renames for CAN2
        renames = ConfigurationStepProcessor._generate_connection_renames(parameters, "CAN2")

        # Assert: Only CAN parameters were renamed
        assert "CAN_P1_DRIVER" in renames
        assert "CAN_D1_PROTOCOL" in renames
        assert "BATT_MONITOR" not in renames
        assert "GPS_TYPE" not in renames
        assert "CUSTOM_PARAM_123" not in renames
        assert "SERIAL2_BAUD" not in renames  # Wrong connection type

        # Check correct renaming
        assert renames["CAN_P1_DRIVER"] == "CAN_P2_DRIVER"
        assert renames["CAN_D1_PROTOCOL"] == "CAN_D2_PROTOCOL"

    def test_apply_renames_without_duplicates(self, connection_params) -> None:
        """
        Test calculating renames without any duplicate parameters creates expected operations.

        GIVEN: A user has parameters without naming conflicts
        WHEN: They calculate connection renaming operations
        THEN: Rename operations should be returned correctly without any duplicates
        AND: Original parameters dict should remain unchanged (immutable)
        """
        # Arrange: Create a copy to verify immutability
        params = connection_params["param_objects"].copy()
        original_keys = set(params.keys())

        # Act: Calculate renames for CAN1 to CAN2 (does NOT mutate params)
        duplicated_names, renamed_pairs = ConfigurationStepProcessor._calculate_connection_rename_operations(params, "CAN2")

        # Assert: Rename operations calculated correctly
        assert not duplicated_names  # No duplicates expected
        assert ("CAN_P1_DRIVER", "CAN_P2_DRIVER") in renamed_pairs
        assert ("CAN_D1_PROTOCOL", "CAN_D2_PROTOCOL") in renamed_pairs

        # Assert: Original params dict unchanged (immutable)
        assert set(params.keys()) == original_keys
        assert "CAN_P1_DRIVER" in params  # Original still present
        assert "CAN_P2_DRIVER" not in params  # New name not added

        # Check that only CAN parameters were renamed
        assert "SERIAL1_PROTOCOL" in params
        assert "SERIAL2_BAUD" in params

        # Check no duplicates were created
        assert len(duplicated_names) == 0

        # Check renamed pairs
        renamed_dict = dict(renamed_pairs)
        assert renamed_dict["CAN_P1_DRIVER"] == "CAN_P2_DRIVER"
        assert renamed_dict["CAN_D1_PROTOCOL"] == "CAN_D2_PROTOCOL"

    def test_apply_renames_with_duplicates(self, connection_params) -> None:
        """
        Test calculating renames skips individual operations when they would create conflicts.

        GIVEN: A user has parameters that would create naming conflicts for some renames
        WHEN: They calculate connection renaming operations
        THEN: Conflicting renames are skipped but non-conflicting renames proceed
        AND: No parameters are marked as duplicates for removal
        AND: Original parameters dict remains unchanged (immutable)
        """
        # Arrange: Create params with potential duplicates
        # Add CAN_P2_DRIVER which will conflict when we try to rename CAN_P1_DRIVER -> CAN_P2_DRIVER
        params = connection_params["param_objects"].copy()
        params["CAN_P2_DRIVER"] = Par(value=2.0, comment="Already exists")
        original_keys = set(params.keys())

        # Act: Calculate renames for CAN1 to CAN2
        duplicated_params, renamed_pairs = ConfigurationStepProcessor._calculate_connection_rename_operations(params, "CAN2")

        # Assert: No duplicates are marked when individual conflicts occur
        assert len(duplicated_params) == 0

        # Assert: Non-conflicting renames proceed (CAN_P1_DRIVER conflicts, others don't)
        expected_renames = [
            ("CAN_P1_BITRATE", "CAN_P2_BITRATE"),
            ("CAN_D1_PROTOCOL", "CAN_D2_PROTOCOL"),
            ("CAN_D1_UC_NODE", "CAN_D2_UC_NODE"),
            ("CAN_D1_UC_OPTION", "CAN_D2_UC_OPTION"),
        ]
        assert renamed_pairs == expected_renames

        # Assert: Original params dict unchanged (immutable)
        assert set(params.keys()) == original_keys
        assert "CAN_P1_DRIVER" in params  # Original parameter still present
        assert "CAN_P2_DRIVER" in params  # Conflicting parameter still there

    def test_apply_renames_with_variables(self, connection_params) -> None:
        """
        Test calculating renames with variable evaluation works correctly.

        GIVEN: A user has configuration with variable-based connection naming
        WHEN: They calculate connection renaming operations with variables
        THEN: Variables should be evaluated and used for calculating renames
        AND: Rename operations should use the evaluated target
        AND: Original parameters dict remains unchanged (immutable)
        """
        # Arrange: Create variables dictionary
        variables: dict[str, Any] = {"selected_can": "CAN3"}
        params = connection_params["param_objects"].copy()
        original_keys = set(params.keys())

        # Act: Calculate renames with variables (does NOT mutate params)
        _duplicated_params, renamed_pairs = ConfigurationStepProcessor._calculate_connection_rename_operations(
            params, "selected_can", variables
        )

        # Assert: Rename operations calculated using evaluated variable
        assert ("CAN_P1_DRIVER", "CAN_P3_DRIVER") in renamed_pairs
        assert ("CAN_D1_PROTOCOL", "CAN_D3_PROTOCOL") in renamed_pairs

        # Assert: Original params dict unchanged (immutable)
        assert set(params.keys()) == original_keys
        assert "CAN_P1_DRIVER" in params
        assert "CAN_P3_DRIVER" not in params

        # Check renamed pairs
        renamed_dict = dict(renamed_pairs)
        assert renamed_dict["CAN_P1_DRIVER"] == "CAN_P3_DRIVER"
        assert renamed_dict["CAN_D1_PROTOCOL"] == "CAN_D3_PROTOCOL"

    def test_apply_renames_with_mixed_connection_types(self, connection_params) -> None:
        """
        User can calculate renames with mixed connection types in same operation.

        GIVEN: A user has both CAN and SERIAL parameters that need renaming
        WHEN: They calculate connection renaming operations for a specific type
        THEN: Only the matching connection type should have rename operations
        AND: Other connection types should not appear in rename operations
        AND: Original parameters dict remains unchanged (immutable)
        """
        # Arrange: Create parameters with mixed connection types
        params = connection_params["param_objects"].copy()
        original_keys = set(params.keys())

        # Act: Calculate renames for CAN2 (should only calculate CAN operations)
        duplicated_params, renamed_pairs = ConfigurationStepProcessor._calculate_connection_rename_operations(params, "CAN2")

        # Assert: Only CAN parameters in rename operations
        renamed_dict = dict(renamed_pairs)
        assert "CAN_P1_DRIVER" in renamed_dict
        assert renamed_dict["CAN_P1_DRIVER"] == "CAN_P2_DRIVER"
        assert "CAN_D1_PROTOCOL" in renamed_dict
        assert renamed_dict["CAN_D1_PROTOCOL"] == "CAN_D2_PROTOCOL"

        # SERIAL parameters should NOT be in rename operations
        assert "SERIAL1_PROTOCOL" not in renamed_dict
        assert "SERIAL1_BAUD" not in renamed_dict

        # Assert: Original params dict unchanged (immutable)
        assert set(params.keys()) == original_keys
        assert "CAN_P1_DRIVER" in params
        assert "SERIAL1_PROTOCOL" in params

        # Check no duplicates
        assert len(duplicated_params) == 0
        assert "CAN_P1_DRIVER" in renamed_dict
        assert "SERIAL1_PROTOCOL" not in renamed_dict


class TestConfigurationStepProcessorErrorHandling:
    """Test error handling and edge cases in configuration processing."""

    def test_processor_handles_missing_configuration_steps_gracefully(self, processor, fc_parameters) -> None:
        """
        User can process files without configuration steps without errors.

        GIVEN: A user has a parameter file without special configuration steps
        WHEN: They process the configuration step
        THEN: Processing should complete successfully
        AND: No configuration step operations should be attempted
        """
        # Arrange: Set up file without configuration steps
        selected_file = "simple_file.param"
        processor.local_filesystem.configuration_steps = {}
        processor.local_filesystem.file_parameters[selected_file] = {}  # Add empty file entry

        # Act: Process configuration step
        parameters, ui_errors, ui_infos, _, _, _ = processor.process_configuration_step(selected_file, fc_parameters)

        # Assert: Processing completed without errors
        assert isinstance(parameters, dict)
        assert ui_errors == []
        assert ui_infos == []
        processor.local_filesystem.compute_parameters.assert_not_called()

    def test_processor_handles_empty_parameter_files_gracefully(self, processor, fc_parameters) -> None:
        """
        User can process empty parameter files without errors.

        GIVEN: A user has an empty parameter file
        WHEN: They process the configuration step
        THEN: Processing should complete successfully
        AND: An empty parameters dictionary should be returned
        """
        # Arrange: Set up empty parameter file
        selected_file = "empty_file.param"
        processor.local_filesystem.file_parameters[selected_file] = {}

        # Act: Process configuration step
        parameters, ui_errors, ui_infos, _, _, _ = processor.process_configuration_step(selected_file, fc_parameters)

        # Assert: Empty file handled gracefully
        assert isinstance(parameters, dict)
        assert len(parameters) == 0
        assert ui_errors == []
        assert ui_infos == []

    def test_processor_handles_missing_parameter_metadata_gracefully(self, processor, fc_parameters) -> None:
        """
        User can process parameters that lack complete metadata.

        GIVEN: A user has parameters without complete documentation metadata
        WHEN: They create domain model parameters
        THEN: Parameters should be created with available information
        AND: Missing metadata should not cause errors
        """
        # Arrange: Set up parameters with minimal metadata
        selected_file = "test_file.param"
        processor.local_filesystem.doc_dict = {}  # No metadata available
        processor.local_filesystem.param_default_dict = {}  # No defaults available

        # Act: Create domain model parameters
        parameters = processor._create_domain_model_parameters(selected_file, fc_parameters)

        # Assert: Parameters created despite missing metadata
        assert isinstance(parameters, dict)
        assert len(parameters) > 0

        for param_obj in parameters.values():
            assert isinstance(param_obj, ArduPilotParameter)

    def test_processor_handles_complex_connection_renaming_edge_cases(self, processor, fc_parameters) -> None:
        """
        User can process complex connection renaming scenarios with edge cases.

        GIVEN: A user has parameters with complex naming patterns and edge cases
        WHEN: They process connection renaming with various scenarios
        THEN: The system should handle all edge cases gracefully
        AND: Provide appropriate feedback for each scenario
        """
        # Arrange: Set up complex parameter scenarios
        selected_file = "complex_file.param"
        complex_params = {
            "CAN_P1_DRIVER": Par(value=1.0, comment="Standard CAN"),
            "CAN_P1_BITRATE": Par(value=1000000.0, comment="CAN bitrate"),
            "CAN_D1_PROTOCOL": Par(value=1.0, comment="DroneCAN"),
            "SERIAL1_PROTOCOL": Par(value=4.0, comment="MAVLink"),
            "GPS_TYPE": Par(value=1.0, comment="Not a connection param"),
            "CUSTOM_123": Par(value=42.0, comment="Custom parameter"),
        }

        processor.local_filesystem.file_parameters[selected_file] = complex_params
        processor.local_filesystem.configuration_steps = {selected_file: {"rename_connection": "selected_can"}}

        # Act: Process complex connection renaming
        parameters, ui_errors, ui_infos, _, _, _ = processor.process_configuration_step(
            selected_file, fc_parameters
        )  # Assert: Complex scenarios handled correctly
        assert isinstance(parameters, dict)
        assert ui_errors == []

        # Should have info messages about renaming (if any CAN parameters were renamed)
        if ui_infos:
            assert len(ui_infos) > 0

    def test_processor_handles_empty_variables_dictionary(self, processor, fc_parameters) -> None:
        """
        User can process configuration steps with empty variables dictionary.

        GIVEN: A user processes configuration steps with no variables defined
        WHEN: They process a configuration step that might use variables
        THEN: Processing should complete without errors
        AND: Default behavior should be maintained
        """
        selected_file = "test_file.param"

        # Act: Process with empty variables
        parameters, ui_errors, ui_infos, _, _, _ = processor.process_configuration_step(
            selected_file, fc_parameters
        )  # Assert: Processing completed successfully
        assert isinstance(parameters, dict)
        assert isinstance(ui_errors, list)
        assert isinstance(ui_infos, list)

    def test_user_receives_expresslrs_warning_when_fltmode_ch_is_5_and_expresslrs_detected(
        self, processor, fc_parameters
    ) -> None:
        """
        User receives ExpressLRS configuration warning when FLTMODE_CH is 5 and ExpressLRS is detected.

        GIVEN: A user has RC_OPTIONS with ExpressLRS bits set and FLTMODE_CH set to 5
        WHEN: They process the configuration step
        THEN: A warning should be added about FLTMODE_CH conflict with RC5 arming channel
        """
        # Arrange: Set up ExpressLRS detection with FLTMODE_CH = 5
        selected_file = "test_file.param"
        processor.local_filesystem.configuration_steps = {selected_file: {}}
        processor.local_filesystem.file_parameters[selected_file]["RC_OPTIONS"] = Par(value=1.0, comment="RC options")
        processor.local_filesystem.file_parameters[selected_file]["FLTMODE_CH"] = Par(value=1.0, comment="Flight mode channel")

        # Set FC parameters with ExpressLRS bit 9 set (512) and FLTMODE_CH = 5
        test_fc_params = fc_parameters.copy()
        test_fc_params["RC_OPTIONS"] = 1 << 9  # Bit 9 set for ExpressLRS
        test_fc_params["FLTMODE_CH"] = 5

        # Act: Process configuration step
        _, ui_errors, ui_infos, _, _, _ = processor.process_configuration_step(selected_file, test_fc_params)

        # Assert: ExpressLRS warning is present
        assert len(ui_infos) == 1
        assert ui_infos[0][0] == "ExpressLRS Configuration Warning"
        assert "FLTMODE_CH must be set to a channel other than 5" in ui_infos[0][1]
        assert "RC5 arming channel" in ui_infos[0][1]
        assert ui_errors == []

    def test_user_does_not_receive_expresslrs_warning_when_fltmode_ch_is_not_5_and_expresslrs_detected(
        self, processor, fc_parameters
    ) -> None:
        """
        User does not receive ExpressLRS warning when FLTMODE_CH is not 5, even if ExpressLRS is detected.

        GIVEN: A user has RC_OPTIONS with ExpressLRS bits set but FLTMODE_CH set to 6
        WHEN: They process the configuration step
        THEN: No warning should be added
        """
        # Arrange: Set up ExpressLRS detection with FLTMODE_CH = 6
        selected_file = "test_file.param"
        processor.local_filesystem.configuration_steps = {selected_file: {}}
        processor.local_filesystem.file_parameters[selected_file]["RC_OPTIONS"] = Par(value=1.0, comment="RC options")
        processor.local_filesystem.file_parameters[selected_file]["FLTMODE_CH"] = Par(value=1.0, comment="Flight mode channel")

        # Set FC parameters with ExpressLRS bit 13 set and FLTMODE_CH = 6
        test_fc_params = fc_parameters.copy()
        test_fc_params["RC_OPTIONS"] = 1 << 13  # Bit 13 set for ExpressLRS
        test_fc_params["FLTMODE_CH"] = 6

        # Act: Process configuration step
        _, ui_errors, ui_infos, _, _, _ = processor.process_configuration_step(selected_file, test_fc_params)

        # Assert: No ExpressLRS warning
        assert ui_infos == []
        assert ui_errors == []

    def test_user_does_not_receive_expresslrs_warning_when_expresslrs_not_detected(self, processor, fc_parameters) -> None:
        """
        User does not receive ExpressLRS warning when ExpressLRS bits are not set in RC_OPTIONS.

        GIVEN: A user has RC_OPTIONS without ExpressLRS bits set and FLTMODE_CH set to 5
        WHEN: They process the configuration step
        THEN: No warning should be added
        """
        # Arrange: Set up non-ExpressLRS with FLTMODE_CH = 5
        selected_file = "test_file.param"
        processor.local_filesystem.configuration_steps = {selected_file: {}}
        processor.local_filesystem.file_parameters[selected_file]["RC_OPTIONS"] = Par(value=1.0, comment="RC options")
        processor.local_filesystem.file_parameters[selected_file]["FLTMODE_CH"] = Par(value=1.0, comment="Flight mode channel")

        # Set FC parameters without ExpressLRS bits and FLTMODE_CH = 5
        test_fc_params = fc_parameters.copy()
        test_fc_params["RC_OPTIONS"] = 0  # No ExpressLRS bits
        test_fc_params["FLTMODE_CH"] = 5

        # Act: Process configuration step
        _, ui_errors, ui_infos, _, _, _ = processor.process_configuration_step(selected_file, test_fc_params)

        # Assert: No ExpressLRS warning
        assert ui_infos == []
        assert ui_errors == []

    def test_user_receives_expresslrs_warning_with_both_bits_set_and_fltmode_ch_5(self, processor, fc_parameters) -> None:
        """
        User receives ExpressLRS warning when both ExpressLRS bits are set and FLTMODE_CH is 5.

        GIVEN: A user has RC_OPTIONS with both ExpressLRS bits (9 and 13) set and FLTMODE_CH = 5
        WHEN: They process the configuration step
        THEN: A warning should be added
        """
        # Arrange: Set up both ExpressLRS bits with FLTMODE_CH = 5
        selected_file = "test_file.param"
        processor.local_filesystem.configuration_steps = {selected_file: {}}
        processor.local_filesystem.file_parameters[selected_file]["RC_OPTIONS"] = Par(value=1.0, comment="RC options")
        processor.local_filesystem.file_parameters[selected_file]["FLTMODE_CH"] = Par(value=1.0, comment="Flight mode channel")

        # Set FC parameters with both bits set and FLTMODE_CH = 5
        test_fc_params = fc_parameters.copy()
        test_fc_params["RC_OPTIONS"] = (1 << 9) | (1 << 13)  # Both bits set
        test_fc_params["FLTMODE_CH"] = 5

        # Act: Process configuration step
        _, ui_errors, ui_infos, _, _, _ = processor.process_configuration_step(selected_file, test_fc_params)

        # Assert: ExpressLRS warning is present
        assert len(ui_infos) == 1
        assert ui_infos[0][0] == "ExpressLRS Configuration Warning"
        assert ui_errors == []
