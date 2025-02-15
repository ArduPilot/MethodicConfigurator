#!/usr/bin/env python3

"""
Tests for the backend_internet.py file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import os
from unittest.mock import Mock, patch

import pytest
from requests import HTTPError as requests_HTTPError
from requests import RequestException as requests_RequestException

from ardupilot_methodic_configurator.backend_internet import (
    download_and_install_on_windows,
    download_and_install_pip_release,
    download_file_from_url,
    get_release_info,
)


def test_download_file_from_url_empty_params() -> None:
    assert not download_file_from_url("", "")
    assert not download_file_from_url("http://test.com", "")
    assert not download_file_from_url("", "test.txt")


@pytest.mark.parametrize(
    "env_vars",
    [
        {},
        {"HTTP_PROXY": "http://proxy:8080"},
        {"HTTPS_PROXY": "https://proxy:8080"},
        {"NO_PROXY": "localhost"},
    ],
)
def test_download_file_from_url_proxy_handling(env_vars) -> None:
    with patch.dict(os.environ, env_vars, clear=True), patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 404
        assert not download_file_from_url("http://test.com", "test.txt", timeout=3)


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
def test_download_file_success(mock_get, tmp_path) -> None:
    # Setup mock response
    mock_response = Mock()
    mock_response.headers = {"content-length": "100"}
    mock_response.iter_content.return_value = [b"test data"]
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    test_file = tmp_path / "test.txt"
    assert download_file_from_url("http://test.com", str(test_file))
    assert test_file.read_bytes() == b"test data"


@pytest.fixture
def mock_get_() -> Mock:
    with patch("ardupilot_methodic_configurator.backend_internet.requests_get") as _mock:
        yield _mock


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
def test_download_file_invalid_content_length(mock_get) -> None:
    # Test handling of invalid content-length header
    mock_response = Mock()
    mock_response.headers = {"content-length": "invalid"}
    mock_response.iter_content.return_value = [b"test data"]
    mock_get.return_value = mock_response
    assert not download_file_from_url("http://test.com", "test.txt")


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
def test_download_file_missing_content_length(mock_get) -> None:
    # Test handling of missing content-length header
    mock_response = Mock()
    mock_response.headers = {}
    mock_response.iter_content.return_value = [b"test data"]
    mock_get.return_value = mock_response
    assert download_file_from_url("http://test.com", "test.txt")


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
def test_download_file_empty_response(mock_get) -> None:
    # Test handling of empty response
    mock_response = Mock()
    mock_response.headers = {"content-length": "0"}
    mock_response.iter_content.return_value = []
    mock_get.return_value = mock_response
    assert not download_file_from_url("http://test.com", "test.txt")


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
def test_download_file_http_error(mock_get) -> None:
    # Test HTTP error handling
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = requests_HTTPError("404 Not Found")
    mock_get.return_value = mock_response
    assert not download_file_from_url("http://test.com", "test.txt")


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
def test_download_file_with_progress_no_content_length(mock_get, tmp_path) -> None:
    # Test progress callback without content-length header
    mock_response = Mock()
    mock_response.headers = {}
    mock_response.iter_content.return_value = [b"data"] * 4
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    progress_callback = Mock()
    test_file = tmp_path / "test.txt"

    assert download_file_from_url("http://test.com", str(test_file), progress_callback=progress_callback)
    assert progress_callback.call_count == 1  # Only final callback
    progress_callback.assert_called_with(100.0, "Download complete")


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
def test_download_file_proxy_configuration(mock_get, monkeypatch) -> None:
    # Test proxy configuration handling
    mock_response = Mock()
    mock_response.headers = {"content-length": "100"}
    mock_response.iter_content.return_value = [b"test data"]
    mock_get.return_value = mock_response

    # Set environment variables
    monkeypatch.setenv("HTTP_PROXY", "http://proxy:8080")
    monkeypatch.setenv("HTTPS_PROXY", "https://proxy:8080")
    monkeypatch.setenv("NO_PROXY", "localhost")

    assert download_file_from_url("http://test.com", "test.txt", timeout=3)
    mock_get.assert_called_once_with(
        "http://test.com",
        stream=True,
        timeout=3,
        proxies={"http": "http://proxy:8080", "https": "https://proxy:8080", "no_proxy": "localhost"},
        verify=True,
    )


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
def test_download_file_value_error(mock_get) -> None:
    # Test handling of ValueError during download
    mock_response = Mock()
    mock_response.headers = {"content-length": "100"}
    mock_response.iter_content.side_effect = ValueError("Invalid data")
    mock_get.return_value = mock_response
    assert not download_file_from_url("http://test.com", "test.txt")


def test_download_file_from_url_invalid_url() -> None:
    # Test with invalid URL format
    assert not download_file_from_url("not_a_valid_url", "test.txt")


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
def test_download_file_unicode_error(mock_get) -> None:
    # Test handling of Unicode decode errors
    mock_response = Mock()
    mock_response.headers = {"content-length": "100"}
    mock_response.iter_content.return_value = [bytes([0xFF, 0xFE, 0xFD])]  # Invalid UTF-8
    mock_get.return_value = mock_response
    assert download_file_from_url("http://test.com", "test.txt")


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
def test_get_release_info_invalid_release(mock_get) -> None:
    mock_get.side_effect = requests_RequestException()
    with pytest.raises(requests_RequestException):
        get_release_info("latest", should_be_pre_release=False)


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
def test_get_release_info_prerelease_mismatch(mock_get) -> None:
    mock_response = Mock()
    mock_response.json.return_value = {"prerelease": True}
    mock_get.return_value = mock_response


@patch("ardupilot_methodic_configurator.backend_internet.download_file_from_url")
def test_download_and_install_windows_download_failure(mock_download) -> None:
    mock_download.return_value = False
    assert not download_and_install_on_windows("http://test.com", "test.exe")


@patch("os.system")
def test_download_and_install_pip_release(mock_system) -> None:
    mock_system.return_value = 0
    assert download_and_install_pip_release() == 0


class TestDownloadFile:
    """Tests for the download_file_from_url function."""

    @pytest.fixture
    def mock_response(self) -> Mock:
        response = Mock()
        response.headers = {"content-length": "100"}
        response.iter_content.return_value = [b"test data"]
        response.raise_for_status.return_value = None
        return response

    @pytest.fixture
    def mock_get(self) -> Mock:
        with patch("ardupilot_methodic_configurator.backend_internet.requests_get") as _mock:
            yield _mock

    def test_download_file_network_errors(self, mock_get, caplog) -> None:
        errors = [
            requests_HTTPError("404 Not Found"),
            requests_RequestException("Connection failed"),
            ValueError("Invalid response"),
            OSError("File system error"),
        ]

        for error in errors:
            mock_get.side_effect = error
            assert not download_file_from_url("http://test.com", "test.txt")
            assert str(error) in caplog.text
            caplog.clear()

    def test_download_file_progress_tracking(self, mock_get, mock_response, tmp_path) -> None:
        mock_get.return_value = mock_response
        progress_values = []

        def progress_callback(progress: float, msg: str) -> None:
            progress_values.append((progress, msg))

        test_file = tmp_path / "test.txt"
        assert download_file_from_url("http://test.com", str(test_file), progress_callback=progress_callback)

        # Verify progress tracking
        assert len(progress_values) > 0
        assert progress_values[-1][0] == 100.0
        assert "Download complete" in progress_values[-1][1]
        assert test_file.exists()
        assert test_file.read_bytes() == b"test data"

    def test_download_file_proxy_configs(self, mock_get, monkeypatch) -> None:
        proxy_configs = [
            {"HTTP_PROXY": "http://proxy1:8080"},
            {"HTTPS_PROXY": "https://proxy2:8080"},
            {"HTTP_PROXY": "http://proxy3:8080", "NO_PROXY": "localhost"},
        ]

        mock_response = Mock()
        mock_response.headers = {"content-length": "100"}
        mock_response.iter_content.return_value = [b"test data"]
        mock_get.return_value = mock_response

        for config in proxy_configs:
            # Clear previous env vars
            monkeypatch.delenv("HTTP_PROXY", raising=False)
            monkeypatch.delenv("HTTPS_PROXY", raising=False)
            monkeypatch.delenv("NO_PROXY", raising=False)

            # Set new config
            for key, value in config.items():
                monkeypatch.setenv(key, value)

            download_file_from_url("http://test.com", "test.txt")

            expected_proxies = {}
            if "HTTP_PROXY" in config:
                expected_proxies["http"] = config["HTTP_PROXY"]
            if "HTTPS_PROXY" in config:
                expected_proxies["https"] = config["HTTPS_PROXY"]
            if "NO_PROXY" in config:
                expected_proxies["no_proxy"] = config["NO_PROXY"]

            mock_get.assert_called_with("http://test.com", stream=True, timeout=30, proxies=expected_proxies, verify=True)
            mock_get.reset_mock()

    def test_download_file_filesystem_operations(self, mock_get, mock_response, tmp_path) -> None:
        mock_get.return_value = mock_response
        mock_get.configure(timeout=5)

        # Test directory creation
        nested_path = tmp_path / "deep" / "nested" / "path"
        test_file = nested_path / "test.txt"

        assert download_file_from_url("http://test.com", str(test_file))
        assert test_file.exists()
        assert test_file.read_bytes() == b"test data"

        # Test file overwrite
        assert download_file_from_url("http://test.com", str(test_file))
        assert test_file.exists()
