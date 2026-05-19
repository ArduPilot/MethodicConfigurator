#!/usr/bin/env python3

"""
Unit tests for backend_flightcontroller_params.py.

These tests target specific implementation branches and private methods for
coverage purposes. For behavior-driven tests of flight controller parameter
functionality, see test_backend_flightcontroller_params.py.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from ardupilot_methodic_configurator.backend_flightcontroller_params import FlightControllerParams
from ardupilot_methodic_configurator.data_model_flightcontroller_info import FlightControllerInfo

# pylint: disable=protected-access


class TestDownloadParamsViaMavlink:
    """Unit tests for the _download_params_via_mavlink private method."""

    @pytest.fixture
    def connected_params_mgr(self, mock_connected_master: tuple[MagicMock, Mock]) -> tuple[MagicMock, FlightControllerParams]:
        """Provide a FlightControllerParams instance connected to a mock master."""
        mock_master, mock_conn_mgr = mock_connected_master
        mock_conn_mgr.info = FlightControllerInfo()
        mock_conn_mgr.comport_device = "COM1"
        return mock_master, FlightControllerParams(connection_manager=mock_conn_mgr)

    @pytest.fixture
    def disconnected_params_mgr(self) -> FlightControllerParams:
        """Provide a FlightControllerParams instance with no active connection."""
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = None
        mock_conn_mgr.info = FlightControllerInfo()
        mock_conn_mgr.comport_device = ""
        return FlightControllerParams(connection_manager=mock_conn_mgr)

    def test_download_params_returns_empty_when_master_is_none(self, disconnected_params_mgr: FlightControllerParams) -> None:
        """
        _download_params_via_mavlink returns {} when master is None.

        GIVEN: No flight controller connection (master is None)
        WHEN: _download_params_via_mavlink is called
        THEN: An empty dictionary should be returned
        AND: No exceptions should be raised
        """
        result = disconnected_params_mgr._download_params_via_mavlink()

        assert result == {}

    def test_download_params_handles_none_message(
        self, connected_params_mgr: tuple[MagicMock, FlightControllerParams]
    ) -> None:
        """
        _download_params_via_mavlink returns {} when recv_match times out (returns None).

        GIVEN: Connected FC but recv_match returns None immediately (timeout)
        WHEN: _download_params_via_mavlink is called
        THEN: An empty dictionary should be returned
        AND: No exceptions should be raised
        """
        mock_master, params_mgr = connected_params_mgr
        mock_master.recv_match.return_value = None  # Simulate timeout

        result = params_mgr._download_params_via_mavlink()

        assert result == {}

    def test_download_params_receives_parameters_with_progress_callback(
        self, connected_params_mgr: tuple[MagicMock, FlightControllerParams]
    ) -> None:
        """
        _download_params_via_mavlink calls progress callback while receiving parameters.

        GIVEN: Connected FC that returns two parameter messages then None
        WHEN: _download_params_via_mavlink is called with a progress callback
        THEN: The callback should be called with (1, 2) then (2, 2) as (received, total) pairs
        AND: Both parameters should be present in the result dict with correct values
        """
        mock_master, params_mgr = connected_params_mgr

        param1_msg = MagicMock()
        param1_msg.to_dict.return_value = {"param_id": "PARAM1", "param_value": 1.0}
        param1_msg.param_count = 2

        param2_msg = MagicMock()
        param2_msg.to_dict.return_value = {"param_id": "PARAM2", "param_value": 2.0}
        param2_msg.param_count = 2

        mock_master.recv_match.side_effect = [param1_msg, param2_msg, None]

        progress_calls: list[tuple[int, int]] = []

        def progress_callback(current: int, total: int) -> None:
            progress_calls.append((current, total))

        result = params_mgr._download_params_via_mavlink(progress_callback=progress_callback)

        assert "PARAM1" in result
        assert "PARAM2" in result
        assert result["PARAM1"] == 1.0
        assert result["PARAM2"] == 2.0
        assert (1, 2) in progress_calls
        assert (2, 2) in progress_calls

    def test_download_params_handles_exception_from_recv_match(
        self, connected_params_mgr: tuple[MagicMock, FlightControllerParams]
    ) -> None:
        """
        _download_params_via_mavlink handles exceptions from recv_match gracefully.

        GIVEN: Connected FC where recv_match raises an exception on the first call
        WHEN: _download_params_via_mavlink is called
        THEN: The exception should be caught without propagating
        AND: An empty dict should be returned (no parameters received before the error)
        """
        mock_master, params_mgr = connected_params_mgr
        mock_master.recv_match.side_effect = Exception("Serial port disconnected")

        result = params_mgr._download_params_via_mavlink()

        assert result == {}


class TestDownloadParamsViaMavftp:
    """Unit tests for the _download_params_via_mavftp private method."""

    @pytest.fixture
    def disconnected_params_mgr(self) -> FlightControllerParams:
        """Provide a FlightControllerParams instance with no active connection."""
        mock_conn_mgr = Mock()
        mock_conn_mgr.master = None
        mock_conn_mgr.info = FlightControllerInfo()
        mock_conn_mgr.comport_device = ""
        return FlightControllerParams(connection_manager=mock_conn_mgr)

    def test_download_via_mavftp_returns_empty_when_master_is_none(
        self, disconnected_params_mgr: FlightControllerParams
    ) -> None:
        """
        _download_params_via_mavftp returns empty dicts when master is None.

        GIVEN: No flight controller connection (master is None)
        WHEN: _download_params_via_mavftp is called
        THEN: An empty param dict and an empty ParDict should be returned
        AND: No exceptions should be raised
        """
        result_params, result_defaults = disconnected_params_mgr._download_params_via_mavftp()

        assert result_params == {}
        assert len(result_defaults) == 0

    def test_download_via_mavftp_calls_progress_callback(self, mock_connected_master: tuple[MagicMock, Mock]) -> None:
        """
        _download_params_via_mavftp wires a progress callback through to cmd_getparams.

        GIVEN: Connected FC with MAVFTP support
        WHEN: _download_params_via_mavftp is called with a progress_callback
        THEN: cmd_getparams must be invoked with a callable progress_callback kwarg
        AND: When that inner callback is called with 0.5, the outer callback receives (50, 100)
        """
        _mock_master, mock_conn_mgr = mock_connected_master
        mock_conn_mgr.info = FlightControllerInfo()
        mock_conn_mgr.comport_device = "COM1"
        params_mgr = FlightControllerParams(connection_manager=mock_conn_mgr)

        progress_calls: list[tuple[int, int]] = []

        def progress_callback(current: int, total: int) -> None:
            progress_calls.append((current, total))

        with patch("ardupilot_methodic_configurator.backend_flightcontroller_params.create_mavftp") as mock_mavftp_factory:
            mock_mavftp = MagicMock()
            mock_ftp_reply = MagicMock()
            mock_ftp_reply.error_code = 1  # Simulate failure so no file I/O is needed
            mock_mavftp.process_ftp_reply.return_value = mock_ftp_reply
            mock_mavftp_factory.return_value = mock_mavftp

            params_mgr._download_params_via_mavftp(progress_callback=progress_callback)

        call_args = mock_mavftp.cmd_getparams.call_args
        assert call_args is not None, "cmd_getparams should have been called"
        inner_callback = call_args.kwargs.get("progress_callback")
        assert callable(inner_callback), "cmd_getparams must receive a callable progress_callback keyword argument"

        inner_callback(0.5)  # 50 % completion → progress_callback(50, 100)
        assert (50, 100) in progress_calls


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
