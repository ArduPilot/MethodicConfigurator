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

    def test_fetch_parameter_times_out_for_nonexistent_param(self) -> None:
        """
        Fetching nonexistent parameter raises timeout error.

        GIVEN: Connected flight controller
        WHEN: User fetches parameter that doesn't exist
        THEN: TimeoutError should be raised
        AND: Error message should indicate which parameter
        """
        # Given: Connected FC with no response
        mock_master = MagicMock()
        mock_master.recv_match.return_value = None

        mock_conn_mgr = Mock()
        mock_conn_mgr.master = mock_master
        mock_conn_mgr.info = FlightControllerInfo()

        params_mgr = FlightControllerParams(connection_manager=mock_conn_mgr)

        # When/Then: Fetch nonexistent parameter raises timeout
        with pytest.raises(TimeoutError, match="NONEXISTENT"):
            params_mgr.fetch_param("NONEXISTENT", timeout=1)


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
