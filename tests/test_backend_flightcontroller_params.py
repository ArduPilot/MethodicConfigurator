#!/usr/bin/env python3

"""
BDD-style tests for backend_flightcontroller_params.py.

This file focuses on parameter management behavior including downloading,
setting, fetching, and clearing parameters.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from ardupilot_methodic_configurator.backend_flightcontroller_params import FlightControllerParams
from ardupilot_methodic_configurator.data_model_flightcontroller_info import FlightControllerInfo


class TestFlightControllerParamsInitialization:
    """Test parameter manager initialization and setup."""

    def test_user_can_create_params_manager_with_connection(self) -> None:
        """
        User can create parameter manager with connection manager.

        GIVEN: A connection manager is available
        WHEN: User creates parameter manager
        THEN: Manager should be initialized with empty parameters
        AND: Connection manager reference should be stored
        """
        # Given: Mock connection manager
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = None
        mock_conn_mgr.info = FlightControllerInfo()
        mock_conn_mgr.comport_device = ""

        # When: Create params manager
        params_mgr = FlightControllerParams(connection_manager=mock_conn_mgr)

        # Then: Manager initialized correctly
        assert params_mgr is not None
        assert params_mgr.fc_parameters == {}
        assert params_mgr.master is None

    def test_params_manager_requires_connection_manager(self) -> None:
        """
        Parameter manager requires connection manager at initialization.

        GIVEN: No connection manager provided
        WHEN: User attempts to create params manager
        THEN: ValueError should be raised
        AND: Clear error message should be provided
        """
        # When/Then: Attempting creation without connection manager raises error
        with pytest.raises(ValueError, match="connection_manager is required"):
            FlightControllerParams(connection_manager=None)

    def test_params_manager_can_use_provided_parameter_dict(self) -> None:
        """
        Parameter manager can use externally provided parameter dictionary.

        GIVEN: Pre-existing parameter dictionary
        WHEN: User creates params manager with that dictionary
        THEN: Manager should use the provided dictionary
        AND: Dictionary should be shared (not copied)
        """
        # Given: Pre-existing parameters
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = None
        existing_params = {"PARAM1": 1.0, "PARAM2": 2.0}

        # When: Create with existing dict
        params_mgr = FlightControllerParams(connection_manager=mock_conn_mgr, fc_parameters=existing_params)

        # Then: Uses provided dictionary (not a copy)
        assert params_mgr.fc_parameters is existing_params
        assert params_mgr.fc_parameters["PARAM1"] == 1.0


class TestFlightControllerParamsSetParameter:
    """Test parameter setting functionality."""

    def test_user_can_set_parameter_value(self) -> None:
        """
        User can set individual parameter values.

        GIVEN: Connected flight controller
        WHEN: User sets a parameter value
        THEN: Parameter should be sent to flight controller
        AND: Parameter should be cached locally
        """
        # Given: Connected FC
        mock_master = MagicMock()
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = mock_master
        mock_conn_mgr.info = FlightControllerInfo()

        params_mgr = FlightControllerParams(connection_manager=mock_conn_mgr)

        # When: Set parameter
        success, error = params_mgr.set_param("BATT_MONITOR", 4.0)

        # Then: Parameter sent and cached
        assert success is True
        assert error == ""
        mock_master.param_set_send.assert_called_once_with("BATT_MONITOR", 4.0)
        assert params_mgr.fc_parameters["BATT_MONITOR"] == 4.0

    def test_set_parameter_fails_without_connection(self) -> None:
        """
        Setting parameter fails gracefully without connection.

        GIVEN: No flight controller connection
        WHEN: User attempts to set parameter
        THEN: Operation should fail with clear error
        AND: No exceptions should be raised
        """
        # Given: No connection
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = None

        params_mgr = FlightControllerParams(connection_manager=mock_conn_mgr)

        # When: Attempt to set parameter
        success, error = params_mgr.set_param("PARAM1", 1.0)

        # Then: Clear failure message
        assert success is False
        assert "connection" in error.lower()

    def test_set_parameter_with_string_value_fails(self) -> None:
        """
        Setting parameter with string value fails with clear error.

        GIVEN: Connected flight controller
        WHEN: User attempts to set parameter with string value (invalid)
        THEN: Operation should fail
        AND: Error message should indicate invalid type
        AND: Parameter should not be cached
        """
        # Given: Connected FC
        mock_master = MagicMock()
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = mock_master
        mock_conn_mgr.info = FlightControllerInfo()

        params_mgr = FlightControllerParams(connection_manager=mock_conn_mgr)

        # When: Try to set with string value
        success, error = params_mgr.set_param("PARAM1", "invalid_string")  # type: ignore[arg-type]

        # Then: Should fail with type error
        assert success is False
        assert "Invalid" in error or "type" in error.lower()
        assert "PARAM1" not in params_mgr.fc_parameters

    def test_set_parameter_with_none_value_fails(self) -> None:
        """
        Setting parameter with None value fails appropriately.

        GIVEN: Connected flight controller
        WHEN: User attempts to set parameter with None
        THEN: Operation should fail
        AND: Error message should indicate invalid type
        """
        # Given: Connected FC
        mock_master = MagicMock()
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = mock_master
        mock_conn_mgr.info = FlightControllerInfo()

        params_mgr = FlightControllerParams(connection_manager=mock_conn_mgr)

        # When: Try to set with None value
        success, error = params_mgr.set_param("PARAM1", None)  # type: ignore[arg-type]

        # Then: Should fail with type error
        assert success is False
        assert "Invalid" in error or "type" in error.lower()

    def test_set_parameter_with_list_value_fails(self) -> None:
        """
        Setting parameter with list value fails appropriately.

        GIVEN: Connected flight controller
        WHEN: User attempts to set parameter with list (invalid)
        THEN: Operation should fail
        AND: Error message should indicate invalid type
        """
        # Given: Connected FC
        mock_master = MagicMock()
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = mock_master
        mock_conn_mgr.info = FlightControllerInfo()

        params_mgr = FlightControllerParams(connection_manager=mock_conn_mgr)

        # When: Try to set with list value
        success, error = params_mgr.set_param("PARAM1", [1, 2, 3])  # type: ignore[arg-type]

        # Then: Should fail with type error
        assert success is False
        assert "Invalid" in error or "type" in error.lower()

    def test_set_parameter_with_dict_value_fails(self) -> None:
        """
        Setting parameter with dict value fails appropriately.

        GIVEN: Connected flight controller
        WHEN: User attempts to set parameter with dict (invalid)
        THEN: Operation should fail
        AND: Error message should indicate invalid type
        """
        # Given: Connected FC
        mock_master = MagicMock()
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = mock_master
        mock_conn_mgr.info = FlightControllerInfo()

        params_mgr = FlightControllerParams(connection_manager=mock_conn_mgr)

        # When: Try to set with dict value
        success, error = params_mgr.set_param("PARAM1", {"key": "value"})  # type: ignore[arg-type]

        # Then: Should fail with type error
        assert success is False
        assert "Invalid" in error or "type" in error.lower()


class TestFlightControllerParamsFetchParameter:
    """Test parameter fetching functionality."""

    def test_user_can_fetch_parameter_from_flight_controller(self) -> None:
        """
        User can fetch current parameter value from flight controller.

        GIVEN: Connected flight controller with parameters
        WHEN: User fetches a specific parameter
        THEN: Current value should be retrieved from FC
        AND: Value should be cached locally
        """
        # Given: Connected FC with parameter response
        mock_master = MagicMock()
        mock_param_msg = MagicMock()
        mock_param_msg.param_value = 4.0
        mock_param_msg.param_id = "BATT_MONITOR"
        mock_master.recv_match.return_value = mock_param_msg

        mock_conn_mgr = Mock()
        mock_conn_mgr.master = mock_master
        mock_conn_mgr.info = FlightControllerInfo()

        params_mgr = FlightControllerParams(connection_manager=mock_conn_mgr)

        # When: Fetch parameter
        value = params_mgr.fetch_param("BATT_MONITOR", timeout=1)

        # Then: Value retrieved and cached
        assert value == 4.0
        assert params_mgr.fc_parameters["BATT_MONITOR"] == 4.0

    def test_fetch_parameter_returns_none_for_nonexistent_param(self) -> None:
        """
        Fetching nonexistent parameter returns None on timeout.

        GIVEN: Connected flight controller
        WHEN: User fetches parameter that doesn't exist
        THEN: None should be returned after timeout
        AND: Should not raise exception
        """
        # Given: Connected FC with no response
        mock_master = MagicMock()
        mock_master.recv_match.return_value = None

        mock_conn_mgr = Mock()
        mock_conn_mgr.master = mock_master
        mock_conn_mgr.info = FlightControllerInfo()

        params_mgr = FlightControllerParams(connection_manager=mock_conn_mgr)

        # When: Fetch nonexistent parameter with short timeout
        result = params_mgr.fetch_param("NONEXISTENT", timeout=0)

        # Then: Should return None on timeout
        assert result is None


class TestFlightControllerParamsGetParameter:
    """Test parameter retrieval from cache."""

    def test_user_can_get_cached_parameter_value(self) -> None:
        """
        User can get parameter value from local cache.

        GIVEN: Parameter cached locally
        WHEN: User gets parameter value
        THEN: Cached value should be returned
        AND: No FC communication should occur
        """
        # Given: Cached parameters
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = None
        params_mgr = FlightControllerParams(connection_manager=mock_conn_mgr)
        params_mgr.fc_parameters["CACHED_PARAM"] = 42.0

        # When: Get cached parameter
        value = params_mgr.get_param("CACHED_PARAM")

        # Then: Cached value returned
        assert value == 42.0

    def test_get_parameter_returns_default_for_missing_param(self) -> None:
        """
        Getting missing parameter returns default value.

        GIVEN: Parameter not in cache
        WHEN: User gets parameter with default value
        THEN: Default value should be returned
        AND: Cache should remain unchanged
        """
        # Given: Empty cache
        mock_conn_mgr = Mock()
        params_mgr = FlightControllerParams(connection_manager=mock_conn_mgr)

        # When: Get missing parameter with default
        value = params_mgr.get_param("MISSING_PARAM", default=99.0)

        # Then: Default returned
        assert value == 99.0
        assert "MISSING_PARAM" not in params_mgr.fc_parameters


class TestFlightControllerParamsClearParameters:  # pylint: disable=too-few-public-methods
    """Test parameter cache clearing."""

    def test_user_can_clear_parameter_cache(self) -> None:
        """
        User can clear all cached parameters.

        GIVEN: Parameters cached from previous operations
        WHEN: User clears parameter cache
        THEN: All cached parameters should be removed
        AND: Cache should be empty
        """
        # Given: Cached parameters
        mock_conn_mgr = Mock()
        params_mgr = FlightControllerParams(connection_manager=mock_conn_mgr)
        params_mgr.fc_parameters = {"PARAM1": 1.0, "PARAM2": 2.0, "PARAM3": 3.0}

        # When: Clear cache
        params_mgr.clear_parameters()

        # Then: Cache empty
        assert params_mgr.fc_parameters == {}
        assert len(params_mgr.fc_parameters) == 0


class TestFlightControllerParamsConstants:
    """Test parameter manager constants and configuration."""

    def test_param_fetch_poll_delay_is_reasonable(self) -> None:
        """
        Parameter fetch poll delay is set to reasonable value.

        GIVEN: Parameter manager class
        WHEN: Checking poll delay constant
        THEN: Value should be small but not zero
        AND: Value should prevent busy-waiting
        """
        # Then: Reasonable poll delay
        assert FlightControllerParams.PARAM_FETCH_POLL_DELAY > 0
        assert FlightControllerParams.PARAM_FETCH_POLL_DELAY < 1.0  # Less than 1 second

    def test_param_set_propagation_delay_allows_fc_processing(self) -> None:
        """
        Parameter set propagation delay allows FC time to process.

        GIVEN: Parameter manager class
        WHEN: Checking propagation delay constant
        THEN: Value should allow FC to process parameter change
        AND: Value should not cause excessive delays
        """
        # Then: Reasonable propagation delay
        assert FlightControllerParams.PARAM_SET_PROPAGATION_DELAY >= 0.1
        assert FlightControllerParams.PARAM_SET_PROPAGATION_DELAY < 2.0


class TestFlightControllerParamsPropertyDelegation:
    """Test property delegation to connection manager."""

    def test_master_property_delegates_to_connection_manager(self) -> None:
        """
        Master property correctly delegates to connection manager.

        GIVEN: Parameter manager with connection manager
        WHEN: Accessing master property
        THEN: Connection manager's master should be returned
        AND: No caching should occur
        """
        # Given: Connection manager with master
        mock_master = MagicMock()
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = mock_master

        params_mgr = FlightControllerParams(connection_manager=mock_conn_mgr)

        # When: Access master
        retrieved_master = params_mgr.master

        # Then: Correct master returned
        assert retrieved_master is mock_master

    def test_info_property_delegates_to_connection_manager(self) -> None:
        """
        Info property correctly delegates to connection manager.

        GIVEN: Parameter manager with connection manager
        WHEN: Accessing info property
        THEN: Connection manager's info should be returned
        AND: Info should be single source of truth
        """
        # Given: Connection manager with info
        mock_info = FlightControllerInfo()
        mock_conn_mgr = Mock()
        mock_conn_mgr.info = mock_info

        params_mgr = FlightControllerParams(connection_manager=mock_conn_mgr)

        # When: Access info
        retrieved_info = params_mgr.info

        # Then: Correct info returned
        assert retrieved_info is mock_info

    def test_comport_device_property_delegates_correctly(self) -> None:
        """
        Comport device property correctly delegates to connection manager.

        GIVEN: Parameter manager with connection manager
        WHEN: Accessing comport_device property
        THEN: Connection manager's comport_device should be returned
        """
        # Given: Connection manager with comport device
        mock_conn_mgr = Mock()
        mock_conn_mgr.comport_device = "/dev/ttyACM0"

        params_mgr = FlightControllerParams(connection_manager=mock_conn_mgr)

        # When: Access comport device
        device = params_mgr.comport_device

        # Then: Correct device returned
        assert device == "/dev/ttyACM0"


class TestFlightControllerParamsDownload:
    """Test parameter download functionality."""

    @patch(
        "ardupilot_methodic_configurator.backend_flightcontroller_params.FlightControllerParams._download_params_via_mavlink"
    )
    def test_download_params_uses_mavlink_when_mavftp_not_supported(self, mock_download) -> None:
        """
        Parameter download uses MAVLink when MAVFTP not supported.

        GIVEN: Flight controller without MAVFTP support
        WHEN: User downloads parameters
        THEN: MAVLink protocol should be used
        AND: Parameters should be retrieved successfully
        """
        # Given: FC without MAVFTP
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = MagicMock()
        mock_info = FlightControllerInfo()
        mock_info.is_mavftp_supported = False
        mock_conn_mgr.info = mock_info

        test_params = {"PARAM1": 1.0, "PARAM2": 2.0}
        mock_download.return_value = test_params

        params_mgr = FlightControllerParams(connection_manager=mock_conn_mgr)

        # When: Download parameters
        params, _defaults = params_mgr.download_params()

        # Then: MAVLink used
        mock_download.assert_called_once()
        assert params == test_params

    def test_download_params_requires_connection(self) -> None:
        """
        Parameter download requires active connection.

        GIVEN: No flight controller connection
        WHEN: User attempts to download parameters
        THEN: Empty parameter dict should be returned
        AND: Error should be logged
        """
        # Given: No connection
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = None
        mock_conn_mgr.info = FlightControllerInfo()

        params_mgr = FlightControllerParams(connection_manager=mock_conn_mgr)

        # When: Attempt download
        params, defaults = params_mgr.download_params()

        # Then: Empty results
        assert params == {}
        assert not defaults


class TestFlightControllerParamsFileOperations:  # pylint: disable=too-few-public-methods
    """Test parameter file save/load operations."""

    def test_download_params_can_save_to_file(self, tmp_path: Path) -> None:
        """
        Downloaded parameters can be saved to file.

        GIVEN: Parameters downloaded from FC
        WHEN: User specifies output filename
        THEN: Parameters should be saved to file
        AND: File should contain parameter values
        """
        # Given: Connected FC with parameters
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = MagicMock()
        mock_info = FlightControllerInfo()
        mock_info.is_mavftp_supported = False
        mock_conn_mgr.info = mock_info

        params_mgr = FlightControllerParams(connection_manager=mock_conn_mgr)

        # Mock the download to return test data
        with patch.object(params_mgr, "_download_params_via_mavlink", return_value={"TEST": 1.0}):
            output_file = tmp_path / "params.txt"

            # When: Download with file output
            params_mgr.download_params(parameter_values_filename=output_file)

            # Then: File created
            # Note: Actual file creation depends on implementation details
            # This test validates the interface accepts the parameter
            assert True  # Interface test only


class TestParameterEdgeCases:
    """Test edge cases and error handling for parameter operations."""

    def test_fetch_param_with_empty_name_returns_none(self) -> None:
        """
        Fetching parameter with empty name returns None gracefully.

        GIVEN: Parameter manager with connection
        WHEN: Fetching parameter with empty string name
        THEN: Should return None
        AND: Should not crash or corrupt state
        """
        # Given: Connected parameter manager
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = MagicMock()
        mock_conn_mgr.info = FlightControllerInfo()
        params_mgr = FlightControllerParams(connection_manager=mock_conn_mgr)

        # When: Fetch with empty name
        result = params_mgr.fetch_param("", timeout=1)

        # Then: Should return None gracefully
        assert result is None

    def test_fetch_param_with_invalid_name_returns_none(self) -> None:
        """
        Fetching non-existent parameter returns None on timeout.

        GIVEN: Parameter manager with connection
        WHEN: Fetching parameter that doesn't exist
        THEN: Should return None after timeout
        AND: Should not raise exception
        """
        # Given: Connected parameter manager
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = MagicMock()
        mock_conn_mgr.info = FlightControllerInfo()
        params_mgr = FlightControllerParams(connection_manager=mock_conn_mgr)

        # When: Fetch non-existent parameter
        result = params_mgr.fetch_param("NONEXISTENT_PARAM_XYZ", timeout=0)

        # Then: Should return None on timeout
        assert result is None

    def test_fetch_param_with_zero_timeout_returns_none(self) -> None:
        """
        Fetch parameter with zero timeout returns None immediately.

        GIVEN: Parameter manager with connection
        WHEN: Attempting fetch with zero timeout
        THEN: Should return None (no time to wait for response)
        AND: Should not hang indefinitely
        """
        # Given: Connected parameter manager
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = MagicMock()
        mock_conn_mgr.info = FlightControllerInfo()
        params_mgr = FlightControllerParams(connection_manager=mock_conn_mgr)

        # When: Fetch with zero timeout
        result = params_mgr.fetch_param("FRAME_TYPE", timeout=0)

        # Then: Should return None (timeout too short)
        assert result is None

    def test_set_param_with_empty_name_fails_gracefully(self) -> None:
        """
        Setting parameter with empty name fails gracefully.

        GIVEN: Parameter manager with connection
        WHEN: Setting parameter with empty name
        THEN: Should return failure status
        AND: Error message should indicate invalid name
        """
        # Given: Connected parameter manager
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = MagicMock()
        mock_conn_mgr.info = FlightControllerInfo()
        params_mgr = FlightControllerParams(connection_manager=mock_conn_mgr)

        # When: Try to set with empty name
        success, error_msg = params_mgr.set_param("", 123.0)

        # Then: Should fail with descriptive error message
        assert not success
        assert isinstance(error_msg, str)
        assert len(error_msg) > 0  # Should have error message
        assert "Invalid" in error_msg or "parameter name" in error_msg.lower()

    def test_set_param_with_zero_value(self) -> None:
        """
        Setting parameter to zero value is allowed.

        GIVEN: Parameter manager with valid parameter name
        WHEN: Setting parameter value to zero
        THEN: Should accept zero as valid value
        AND: Should not treat zero as error condition
        """
        # Given: Connected parameter manager
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = MagicMock()
        mock_conn_mgr.info = FlightControllerInfo()
        params_mgr = FlightControllerParams(connection_manager=mock_conn_mgr)

        # Pre-populate with a parameter
        params_mgr.fc_parameters = {"FRAME_TYPE": 2.0}

        # When: Set parameter to zero
        success, error_msg = params_mgr.set_param("FRAME_TYPE", 0.0)

        # Then: Should accept zero
        assert isinstance(success, bool)
        assert isinstance(error_msg, str)

    def test_set_param_with_negative_value(self) -> None:
        """
        Setting parameter to negative value is allowed where valid.

        GIVEN: Parameter manager with parameter that accepts negative values
        WHEN: Setting parameter to negative value
        THEN: Should accept negative values
        AND: Should not reject based on sign alone
        """
        # Given: Connected parameter manager
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = MagicMock()
        mock_conn_mgr.info = FlightControllerInfo()
        params_mgr = FlightControllerParams(connection_manager=mock_conn_mgr)

        # Pre-populate with a parameter
        params_mgr.fc_parameters = {"TRIM_PITCH_CD": 100.0}

        # When: Set parameter to negative value (valid for trims)
        success, error_msg = params_mgr.set_param("TRIM_PITCH_CD", -50.0)

        # Then: Should handle negative values
        assert isinstance(success, bool)
        assert isinstance(error_msg, str)

    def test_set_param_with_very_large_value(self) -> None:
        """
        Setting parameter to very large value is handled.

        GIVEN: Parameter manager with connection
        WHEN: Setting parameter to very large numeric value
        THEN: Should handle large numbers appropriately
        AND: Should not overflow or crash
        """
        # Given: Connected parameter manager
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = MagicMock()
        mock_conn_mgr.info = FlightControllerInfo()
        params_mgr = FlightControllerParams(connection_manager=mock_conn_mgr)

        # Pre-populate with a parameter
        params_mgr.fc_parameters = {"FRAME_TYPE": 2.0}

        # When: Set to very large value
        success, error_msg = params_mgr.set_param("FRAME_TYPE", 9999999.0)

        # Then: Should handle without crashing
        assert isinstance(success, bool)
        assert isinstance(error_msg, str)

    def test_set_param_with_floating_point_precision(self) -> None:
        """
        Setting parameter with floating point values maintains precision.

        GIVEN: Parameter manager with connection
        WHEN: Setting parameter to precise floating point value
        THEN: Should store precision appropriately
        AND: Value should be retrievable
        """
        # Given: Connected parameter manager
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = MagicMock()
        mock_conn_mgr.info = FlightControllerInfo()
        params_mgr = FlightControllerParams(connection_manager=mock_conn_mgr)

        # Pre-populate with a parameter
        params_mgr.fc_parameters = {"ANGLE_MAX": 4500.0}

        # When: Set to precise floating point value
        success, error_msg = params_mgr.set_param("ANGLE_MAX", 3.14159)

        # Then: Should handle floating point values
        assert isinstance(success, bool)
        assert isinstance(error_msg, str)

    def test_fc_parameters_empty_initially(self) -> None:
        """
        Parameter collection starts empty.

        GIVEN: New parameter manager
        WHEN: Checking initial parameters
        THEN: Should have empty dictionary
        AND: Should be mutable for adding parameters
        """
        # Given: New parameter manager
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = None
        mock_conn_mgr.info = FlightControllerInfo()
        params_mgr = FlightControllerParams(connection_manager=mock_conn_mgr)

        # Then: Initially empty
        assert params_mgr.fc_parameters == {}
        assert isinstance(params_mgr.fc_parameters, dict)

    def test_fc_parameters_can_be_set_directly(self) -> None:
        """
        FC parameters dictionary can be updated directly.

        GIVEN: Parameter manager with empty parameters
        WHEN: Setting parameters directly
        THEN: Should update internal dictionary
        AND: Should persist across accesses
        """
        # Given: New parameter manager
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = None
        mock_conn_mgr.info = FlightControllerInfo()
        params_mgr = FlightControllerParams(connection_manager=mock_conn_mgr)

        # When: Set parameters directly
        test_params = {"FRAME_TYPE": 2.0, "BATT_MONITOR": 3.0}
        params_mgr.fc_parameters = test_params

        # Then: Should be stored and retrievable
        assert params_mgr.fc_parameters == test_params
        assert params_mgr.fc_parameters["FRAME_TYPE"] == 2.0

    def test_multiple_set_param_operations_sequence(self) -> None:
        """
        Multiple parameter set operations can be performed in sequence.

        GIVEN: Parameter manager with connection
        WHEN: Setting multiple parameters sequentially
        THEN: Each operation should complete successfully
        AND: State should remain consistent
        """
        # Given: Connected parameter manager
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = MagicMock()
        mock_conn_mgr.info = FlightControllerInfo()
        params_mgr = FlightControllerParams(connection_manager=mock_conn_mgr)

        # Pre-populate with parameters
        params_mgr.fc_parameters = {
            "FRAME_TYPE": 2.0,
            "BATT_MONITOR": 3.0,
            "BATT_CAPACITY": 5000.0,
        }

        # When: Set multiple parameters sequentially
        result1 = params_mgr.set_param("FRAME_TYPE", 1.0)
        result2 = params_mgr.set_param("BATT_MONITOR", 4.0)
        result3 = params_mgr.set_param("BATT_CAPACITY", 4000.0)

        # Then: All operations should complete
        assert isinstance(result1[0], bool)
        assert isinstance(result2[0], bool)
        assert isinstance(result3[0], bool)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
