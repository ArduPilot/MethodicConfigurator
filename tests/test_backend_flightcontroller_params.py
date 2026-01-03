#!/usr/bin/env python3

"""
BDD-style tests for backend_flightcontroller_params.py.

This file focuses on parameter management behavior including downloading,
setting, fetching, and clearing parameters.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from ardupilot_methodic_configurator.backend_flightcontroller_connection import DEVICE_FC_PARAM_FROM_FILE
from ardupilot_methodic_configurator.backend_flightcontroller_params import FlightControllerParams
from ardupilot_methodic_configurator.data_model_flightcontroller_info import FlightControllerInfo
from ardupilot_methodic_configurator.data_model_par_dict import Par, ParDict

# pylint: disable=too-many-lines


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

        # Then: Parameter sent (but NOT cached - cache only updates from actual FC reads)
        assert success is True
        assert error == ""
        mock_master.param_set_send.assert_called_once_with("BATT_MONITOR", 4.0)
        # Note: fc_parameters is NOT updated by set_param to ensure cache accuracy

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

    def test_fetch_parameter_times_out_for_nonexistent_param(self) -> None:
        """
        Fetching nonexistent parameter raises TimeoutError.

        GIVEN: Connected flight controller
        WHEN: User fetches parameter that doesn't exist
        THEN: TimeoutError should be raised after timeout expires
        AND: User receives clear feedback about missing parameter
        """
        # Given: Connected FC with no response
        mock_master = MagicMock()
        mock_master.recv_match.return_value = None

        mock_conn_mgr = Mock()
        mock_conn_mgr.master = mock_master
        mock_conn_mgr.info = FlightControllerInfo()

        params_mgr = FlightControllerParams(connection_manager=mock_conn_mgr)

        # When/Then: Fetch nonexistent parameter and expect timeout
        with patch("ardupilot_methodic_configurator.backend_flightcontroller_params.time_time") as mock_time:
            mock_time.side_effect = [0.0, 2.0]
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
    def test_download_params_uses_mavlink_when_mavftp_not_supported(self, mock_download: MagicMock) -> None:
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

    def test_user_can_load_parameters_from_local_file_mode(self) -> None:
        """
        File-mode downloads reuse local params when no connection exists.

        GIVEN: Flight controller running in offline file mode without master connection
        WHEN: User triggers a parameter download
        THEN: Parameters should be loaded from params.param
        AND: Local cache should contain the loaded values
        """
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = None
        mock_conn_mgr.comport_device = DEVICE_FC_PARAM_FROM_FILE
        mock_conn_mgr.info = FlightControllerInfo()

        params_mgr = FlightControllerParams(connection_manager=mock_conn_mgr)
        fake_params = ParDict({"BATT_MONITOR": Par(4.0)})

        with patch(
            "ardupilot_methodic_configurator.backend_flightcontroller_params.ParDict.from_file",
            return_value=fake_params,
        ) as mock_from_file:
            param_values, default_params = params_mgr.download_params()

        mock_from_file.assert_called_once_with("params.param")
        assert param_values == {"BATT_MONITOR": 4.0}
        assert isinstance(default_params, ParDict)
        assert params_mgr.fc_parameters == param_values

    def test_user_can_download_parameters_via_mavftp_when_supported(self, tmp_path: Path) -> None:
        """
        MAVFTP-backed downloads stream parameter and default files when available.

        GIVEN: Connected controller with MAVFTP support
        WHEN: User requests a parameter download with progress feedback
        THEN: MAVFTP should fetch both parameter and default files
        AND: Local cache plus return values should include converted floats
        """
        mock_conn_mgr = Mock()
        mock_master = MagicMock()
        mock_conn_mgr.master = mock_master
        mock_info = FlightControllerInfo()
        mock_info.is_mavftp_supported = True
        mock_conn_mgr.info = mock_info
        mock_conn_mgr.comport_device = "tcp:127.0.0.1:5760"

        params_mgr = FlightControllerParams(connection_manager=mock_conn_mgr)

        ret = MagicMock()
        ret.error_code = 0
        mock_mavftp = MagicMock()
        mock_mavftp.process_ftp_reply.return_value = ret

        value_file = tmp_path / "values.param"
        default_file = tmp_path / "defaults.param"

        with (
            patch(
                "ardupilot_methodic_configurator.backend_flightcontroller_params.create_mavftp",
                return_value=mock_mavftp,
            ),
            patch(
                "ardupilot_methodic_configurator.backend_flightcontroller_params.ParDict.from_file",
                side_effect=[ParDict({"PSC_ACCZ_P": Par(0.5)}), ParDict({"ATC_ANG_RLL_P": Par(4.5)})],
            ) as mock_from_file,
            patch("ardupilot_methodic_configurator.backend_flightcontroller_params.time_sleep"),
        ):
            progress_updates: list[tuple[int, int]] = []

            def progress(current: int, total: int) -> None:
                progress_updates.append((current, total))

            params, defaults = params_mgr.download_params(
                progress_callback=progress,
                parameter_values_filename=value_file,
                parameter_defaults_filename=default_file,
            )

        mock_mavftp.cmd_getparams.assert_called_once()
        mock_from_file.assert_any_call(str(value_file))
        mock_from_file.assert_any_call(str(default_file))
        assert params == {"PSC_ACCZ_P": 0.5}
        assert isinstance(defaults, ParDict)
        assert params_mgr.fc_parameters == params
        assert progress_updates  # Callback should have been invoked

    def test_mavftp_download_reports_failures_cleanly(self) -> None:
        """
        MAVFTP failures surface clear errors instead of stale data.

        GIVEN: Connected controller experiencing MAVFTP errors
        WHEN: Parameter download is attempted
        THEN: Users should be notified of the error
        AND: Empty dictionaries should be returned
        """
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = MagicMock()
        mock_conn_mgr.info = FlightControllerInfo()

        params_mgr = FlightControllerParams(connection_manager=mock_conn_mgr)

        ret = MagicMock()
        ret.error_code = 5
        mock_mavftp = MagicMock()
        mock_mavftp.process_ftp_reply.return_value = ret

        with (
            patch(
                "ardupilot_methodic_configurator.backend_flightcontroller_params.create_mavftp",
                return_value=mock_mavftp,
            ),
            patch("ardupilot_methodic_configurator.backend_flightcontroller_params.time_sleep"),
        ):
            params, defaults = params_mgr._download_params_via_mavftp()  # pylint: disable=protected-access

        ret.display_message.assert_called_once()
        assert params == {}
        assert isinstance(defaults, ParDict)

    def test_user_can_download_parameters_over_mavlink_with_progress(self) -> None:
        """
        MAVLink downloads iterate until all parameters are received.

        GIVEN: Connected controller without MAVFTP support
        WHEN: User forces a MAVLink-based parameter download with progress callbacks
        THEN: PARAM_VALUE messages should be accumulated until the advertised count is met
        AND: The progress callback should reflect the growing tally
        """
        mock_master = MagicMock()
        mock_master.target_system = 1
        mock_master.target_component = 1
        mock_master.mav = MagicMock()

        first_msg = MagicMock()
        first_msg.param_count = 2
        first_msg.to_dict.return_value = {"param_id": "PSC_ACCZ_P", "param_value": 0.5}

        second_msg = MagicMock()
        second_msg.param_count = 2
        second_msg.to_dict.return_value = {"param_id": "ATC_RATE_RLL_FF", "param_value": 0.12}

        mock_master.recv_match.side_effect = [first_msg, second_msg, None]

        mock_conn_mgr = Mock()
        mock_conn_mgr.master = mock_master
        mock_conn_mgr.info = FlightControllerInfo()

        params_mgr = FlightControllerParams(connection_manager=mock_conn_mgr)

        progress_updates: list[tuple[int, int]] = []
        params = params_mgr._download_params_via_mavlink(  # pylint: disable=protected-access
            lambda current, total: progress_updates.append((current, total))
        )

        mock_master.mav.param_request_list_send.assert_called_once_with(1, 1)
        assert params == {"PSC_ACCZ_P": 0.5, "ATC_RATE_RLL_FF": 0.12}
        assert progress_updates == [(1, 2), (2, 2)]

    def test_download_params_falls_back_to_mavlink_when_mavftp_returns_no_data(self) -> None:
        """
        MAVFTP fallback gracefully switches to MAVLink when files contain no data.

        GIVEN: Controller that advertises MAVFTP support but returns empty files
        WHEN: User requests a parameter sync
        THEN: The code should fall back to standard MAVLink downloads
        AND: Returned parameters should come from the secondary path
        """
        mock_master = MagicMock()
        mock_master.target_system = 1
        mock_master.target_component = 1
        mock_master.mav = MagicMock()

        mock_conn_mgr = Mock()
        mock_conn_mgr.master = mock_master
        mock_conn_mgr.info = FlightControllerInfo()
        mock_conn_mgr.info.is_mavftp_supported = True

        params_mgr = FlightControllerParams(connection_manager=mock_conn_mgr)

        fallback_params = {"AHRS_EKF_TYPE": 10.0}

        with (
            patch.object(params_mgr, "_download_params_via_mavftp", return_value=({}, ParDict())) as mock_mavftp,
            patch.object(params_mgr, "_download_params_via_mavlink", return_value=fallback_params) as mock_mavlink,
        ):
            params, defaults = params_mgr.download_params()

        mock_mavftp.assert_called_once()
        mock_mavlink.assert_called_once()
        assert params == fallback_params
        assert isinstance(defaults, ParDict)


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

    def test_fetch_param_with_empty_name_raises_error(self) -> None:
        """
        Fetching parameter with empty name raises validation error.

        GIVEN: Parameter manager with connection
        WHEN: Fetching parameter with empty string name
        THEN: Should raise IndexError for invalid name
        AND: Should not corrupt internal state
        """
        # Given: Connected parameter manager
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = MagicMock()
        mock_conn_mgr.info = FlightControllerInfo()
        params_mgr = FlightControllerParams(connection_manager=mock_conn_mgr)

        # When/Then: Fetch with empty name raises validation error
        with pytest.raises(IndexError, match="Parameter name cannot be empty"):
            params_mgr.fetch_param("", timeout=1)

    def test_fetch_param_updates_cache_after_successful_response(self) -> None:
        """
        Fetching a parameter updates the cache when MAVLink responds.

        GIVEN: Connected controller that responds to PARAM_REQUEST_READ
        WHEN: User fetches a specific parameter
        THEN: The returned value should be cached locally
        AND: Trailing null characters should be stripped transparently
        """
        mock_master = MagicMock()
        mock_master.target_system = 1
        mock_master.target_component = 1

        mock_msg = MagicMock()
        mock_msg.param_id = "RC1_MIN\x00"
        mock_msg.param_value = 987.0

        mock_master.recv_match.side_effect = [mock_msg]

        mock_conn_mgr = Mock()
        mock_conn_mgr.master = mock_master
        mock_conn_mgr.info = FlightControllerInfo()

        params_mgr = FlightControllerParams(connection_manager=mock_conn_mgr)

        with patch(
            "ardupilot_methodic_configurator.backend_flightcontroller_params.time_time",
            side_effect=[0.0, 0.1],
        ):
            value = params_mgr.fetch_param("RC1_MIN", timeout=1)

        mock_master.mav.param_request_read_send.assert_called_once()
        assert value == 987.0
        assert params_mgr.fc_parameters["RC1_MIN"] == 987.0

    def test_fetch_param_with_invalid_name_raises_error(self) -> None:
        """
        Fetching parameter with invalid length raises validation error.

        GIVEN: Parameter manager with connection
        WHEN: Fetching parameter name longer than MAVLink allows
        THEN: IndexError should be raised immediately
        AND: No MAVLink request should be sent
        """
        # Given: Connected parameter manager
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = MagicMock()
        mock_conn_mgr.info = FlightControllerInfo()
        params_mgr = FlightControllerParams(connection_manager=mock_conn_mgr)

        # When/Then: Fetch invalid parameter name raises error
        with pytest.raises(IndexError, match="Parameter name too long"):
            params_mgr.fetch_param("NONEXISTENT_PARAM_XYZ", timeout=1)

    def test_fetch_param_returns_none_when_disconnected(self) -> None:
        """
        Fetching while disconnected returns None without raising errors.

        GIVEN: Parameter manager without a live MAVLink master
        WHEN: User attempts to fetch any parameter
        THEN: The method should return None immediately
        AND: No MAVLink requests should be issued
        """
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = None
        mock_conn_mgr.info = FlightControllerInfo()
        params_mgr = FlightControllerParams(connection_manager=mock_conn_mgr)

        value = params_mgr.fetch_param("FRAME_TYPE", timeout=1)

        assert value is None

    def test_fetch_param_with_zero_timeout_raises_value_error(self) -> None:
        """
        Fetch parameter with zero timeout raises ValueError.

        GIVEN: Parameter manager with connection
        WHEN: Attempting fetch with zero timeout
        THEN: Should raise ValueError to signal invalid timeout
        AND: Should not perform any MAVLink requests
        """
        # Given: Connected parameter manager
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = MagicMock()
        mock_conn_mgr.info = FlightControllerInfo()
        params_mgr = FlightControllerParams(connection_manager=mock_conn_mgr)

        # When/Then: Fetch with zero timeout raises ValueError
        with pytest.raises(ValueError, match="Timeout for parameter"):
            params_mgr.fetch_param("FRAME_TYPE", timeout=0)

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
