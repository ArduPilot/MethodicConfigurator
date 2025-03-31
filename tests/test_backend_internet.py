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
from requests import Timeout as requests_Timeout

from ardupilot_methodic_configurator.backend_internet import (
    download_and_install_on_windows,
    download_and_install_pip_release,
    download_file_from_url,
    get_release_info,
    verify_and_open_url,
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


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
@patch("ardupilot_methodic_configurator.backend_internet.webbrowser_open")
def test_verify_and_open_url_success(mock_webbrowser_open, mock_get) -> None:
    """Test successful URL verification and opening."""
    # Setup mock responses
    mock_response = Mock()
    mock_response.status_code = 200
    mock_get.return_value = mock_response
    mock_webbrowser_open.return_value = True

    # Call function and verify results
    assert verify_and_open_url("https://example.com")
    mock_get.assert_called_once()
    mock_webbrowser_open.assert_called_once_with(url="https://example.com", new=0, autoraise=True)


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
@patch("ardupilot_methodic_configurator.backend_internet.webbrowser_open")
def test_verify_and_open_url_empty_url(mock_webbrowser_open, mock_get) -> None:
    """Test with empty URL."""
    assert not verify_and_open_url("")
    mock_get.assert_not_called()
    mock_webbrowser_open.assert_not_called()


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
@patch("ardupilot_methodic_configurator.backend_internet.webbrowser_open")
def test_verify_and_open_url_http_error(mock_webbrowser_open, mock_get) -> None:
    """Test with HTTP error response."""
    mock_response = Mock()
    mock_response.status_code = 404
    mock_get.return_value = mock_response

    assert not verify_and_open_url("https://example.com")
    mock_get.assert_called_once()
    mock_webbrowser_open.assert_not_called()


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
@patch("ardupilot_methodic_configurator.backend_internet.webbrowser_open")
def test_verify_and_open_url_request_exception(mock_webbrowser_open, mock_get) -> None:
    """Test with request exception."""
    mock_get.side_effect = requests_RequestException("Connection failed")

    assert not verify_and_open_url("https://example.com")
    mock_get.assert_called_once()
    mock_webbrowser_open.assert_not_called()


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
@patch("ardupilot_methodic_configurator.backend_internet.webbrowser_open")
def test_verify_and_open_url_timeout(mock_webbrowser_open, mock_get) -> None:
    """Test with request timeout."""
    mock_get.side_effect = requests_Timeout("Request timed out")

    assert not verify_and_open_url("https://example.com")
    mock_get.assert_called_once()
    mock_webbrowser_open.assert_not_called()


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
@patch("ardupilot_methodic_configurator.backend_internet.webbrowser_open")
def test_verify_and_open_url_browser_exception(mock_webbrowser_open, mock_get) -> None:
    """Test with browser opening exception."""
    # Setup successful HTTP response but browser error
    mock_response = Mock()
    mock_response.status_code = 200
    mock_get.return_value = mock_response
    mock_webbrowser_open.side_effect = Exception("Browser failed to open")

    assert not verify_and_open_url("https://example.com")
    mock_get.assert_called_once()
    mock_webbrowser_open.assert_called_once()


@pytest.mark.parametrize(
    "env_vars",
    [
        {},
        {"HTTP_PROXY": "http://proxy:8080"},
        {"HTTPS_PROXY": "https://proxy:8080"},
        {"NO_PROXY": "localhost"},
        {"HTTP_PROXY": "http://proxy:8080", "HTTPS_PROXY": "https://proxy:8080"},
    ],
)
@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
@patch("ardupilot_methodic_configurator.backend_internet.webbrowser_open")
def test_verify_and_open_url_proxy_handling(mock_webbrowser_open, mock_get, env_vars, monkeypatch) -> None:
    """Test proxy handling with different environment variables."""
    # Clear existing env vars
    for var in ["HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "no_proxy"]:
        monkeypatch.delenv(var, raising=False)

    # Set test env vars
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)

    # Setup successful response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_get.return_value = mock_response
    mock_webbrowser_open.return_value = True

    # Call function
    assert verify_and_open_url("https://example.com")

    # Verify correct proxies were used
    expected_proxies = {k.lower().replace("_proxy", ""): v for k, v in env_vars.items() if k.upper() != "NO_PROXY"}
    if "NO_PROXY" in env_vars:
        expected_proxies["no_proxy"] = env_vars["NO_PROXY"]

    # Get the actual proxies passed to requests_get
    call_args = mock_get.call_args
    if expected_proxies:
        assert "proxies" in call_args[1]
        for key, value in expected_proxies.items():
            assert call_args[1]["proxies"][key] == value
    else:
        # Empty dict should be passed when no proxies are configured
        assert call_args[1]["proxies"] == {}


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
def test_get_release_info_success(mock_get) -> None:
    """Test successful retrieval of release information."""
    mock_response = Mock()
    mock_release_data = {
        "tag_name": "v1.0.0",
        "name": "Release 1.0.0",
        "body": "Release notes",
        "prerelease": False,
        "assets": [{"name": "asset1", "browser_download_url": "http://example.com/asset1"}],
    }
    mock_response.json.return_value = mock_release_data
    mock_get.return_value = mock_response

    release_info = get_release_info("latest", should_be_pre_release=False)

    mock_get.assert_called_once()
    assert release_info == mock_release_data
    assert release_info["tag_name"] == "v1.0.0"


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
def test_get_release_info_empty_name(mock_get) -> None:
    """Test with empty release name."""
    with pytest.raises(ValueError, match="Release name cannot be empty"):
        get_release_info("", should_be_pre_release=False)
    mock_get.assert_not_called()


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
def test_get_release_info_http_error(mock_get) -> None:
    """Test handling of HTTP errors."""
    mock_response = Mock()
    mock_response.status_code = 404
    mock_error = requests_HTTPError("404 Not Found")
    mock_error.response = mock_response
    mock_get.side_effect = mock_error

    with pytest.raises(requests_HTTPError):
        get_release_info("latest", should_be_pre_release=False)
    mock_get.assert_called_once()


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
def test_get_release_info_rate_limit_error(mock_get) -> None:
    """Test handling of GitHub API rate limit errors."""
    mock_response = Mock()
    mock_response.status_code = 403
    mock_response.headers = {"X-RateLimit-Reset": "1609459200"}  # 2021-01-01 00:00:00 UTC
    mock_error = requests_HTTPError("API rate limit exceeded")
    mock_error.response = mock_response
    mock_get.side_effect = mock_error

    with pytest.raises(requests_HTTPError):
        get_release_info("latest", should_be_pre_release=False)
    mock_get.assert_called_once()


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
def test_get_release_info_request_exception(mock_get) -> None:
    """Test handling of general request exceptions."""
    mock_get.side_effect = requests_RequestException("Connection failed")

    with pytest.raises(requests_RequestException):
        get_release_info("latest", should_be_pre_release=False)
    mock_get.assert_called_once()


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
def test_get_release_info_timeout(mock_get) -> None:
    """Test handling of request timeouts."""
    mock_get.side_effect = requests_Timeout("Request timed out")

    with pytest.raises(requests_RequestException):
        get_release_info("latest", should_be_pre_release=False)
    mock_get.assert_called_once()


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
def test_get_release_info_value_error(mock_get) -> None:
    """Test handling of invalid JSON responses."""
    mock_response = Mock()
    mock_response.json.side_effect = ValueError("Invalid JSON")
    mock_get.return_value = mock_response

    with pytest.raises(ValueError, match="Invalid JSON"):
        get_release_info("latest", should_be_pre_release=False)


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
def test_get_release_info_key_error(mock_get) -> None:
    """Test handling of missing keys in response."""
    mock_response = Mock()
    mock_response.json.return_value = {"name": "Release 1.0.0"}  # Missing 'prerelease' key
    mock_get.return_value = mock_response

    with pytest.raises(KeyError):
        get_release_info("latest", should_be_pre_release=False)


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
def test_get_release_info_correct_url_formation(mock_get) -> None:
    """Test correct URL formation with different input formats."""
    mock_response = Mock()
    mock_response.json.return_value = {"prerelease": False}
    mock_get.return_value = mock_response

    # Test with leading slash
    get_release_info("/latest", should_be_pre_release=False)
    mock_get.assert_called_with("https://api.github.com/repos/ArduPilot/MethodicConfigurator/releases/latest", timeout=30)
    mock_get.reset_mock()

    # Test without leading slash
    get_release_info("latest", should_be_pre_release=False)
    mock_get.assert_called_with("https://api.github.com/repos/ArduPilot/MethodicConfigurator/releases/latest", timeout=30)
    mock_get.reset_mock()

    # Test with tag name
    get_release_info("tags/v1.0.0", should_be_pre_release=False)
    mock_get.assert_called_with("https://api.github.com/repos/ArduPilot/MethodicConfigurator/releases/tags/v1.0.0", timeout=30)


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
def test_get_release_info_custom_timeout(mock_get) -> None:
    """Test custom timeout parameter."""
    mock_response = Mock()
    mock_response.json.return_value = {"prerelease": False}
    mock_get.return_value = mock_response

    get_release_info("latest", should_be_pre_release=False, timeout=60)
    mock_get.assert_called_with("https://api.github.com/repos/ArduPilot/MethodicConfigurator/releases/latest", timeout=60)


@patch("ardupilot_methodic_configurator.backend_internet.requests_get")
def test_get_release_info_prerelease_expectation_violated(mock_get) -> None:
    """Test when prerelease expectation is violated."""
    # Case 1: Expected prerelease but got stable
    mock_response = Mock()
    mock_response.json.return_value = {"prerelease": False}
    mock_get.return_value = mock_response

    # Should log an error but still return the data
    result = get_release_info("latest", should_be_pre_release=True)
    assert not result["prerelease"]
    mock_get.reset_mock()

    # Case 2: Expected stable but got prerelease
    mock_response = Mock()
    mock_response.json.return_value = {"prerelease": True}
    mock_get.return_value = mock_response

    # Should log an error but still return the data
    result = get_release_info("latest", should_be_pre_release=False)
    assert result["prerelease"]
