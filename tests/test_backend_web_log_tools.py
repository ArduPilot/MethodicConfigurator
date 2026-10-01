#!/usr/bin/env python3

"""
Behavior-driven tests for loading local ArduPilot logs in web tools.

SPDX-FileCopyrightText: 2026 ArduPilot Contributors
SPDX-License-Identifier: GPL-3.0-or-later
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from selenium.common.exceptions import InvalidSessionIdException, NoSuchWindowException, WebDriverException

from ardupilot_methodic_configurator import backend_web_log_tools
from ardupilot_methodic_configurator.backend_web_log_tools import open_log_in_web_tool


@pytest.fixture(autouse=True)
def reset_browser(monkeypatch: pytest.MonkeyPatch) -> None:
    """Do not share a browser session between tests or quit a real browser at exit."""
    monkeypatch.setattr(backend_web_log_tools._SESSION, "_driver", None)  # pylint: disable=protected-access


@pytest.mark.parametrize(
    ("url", "file_selector"),
    [
        ("https://plotbeta.ardupilot.org/", "#choosefile"),
        ("https://plot.ardupilot.org/", "#choosefile"),
        ("https://firmware.ardupilot.org/Tools/WebTools/HardwareReport/", "#fileItem"),
        ("https://firmware.ardupilot.org/Tools/WebTools/MAGFit/", "#fileItem"),
        ("https://firmware.ardupilot.org/Tools/WebTools/FilterReview/", "#fileItem"),
        ("https://firmware.ardupilot.org/Tools/WebTools/PIDReview/", "#fileItem"),
        ("https://firmware.ardupilot.org/Tools/WebTools/StreamStats/", "#fileItem"),
        ("https://firmware.ardupilot.org/Tools/WebTools/SysID/", "#fileItem"),
    ],
)
def test_web_tool_opens_tab_and_uploads_selected_log(tmp_path: Path, url: str, file_selector: str) -> None:
    """GIVEN a local log, WHEN choosing a tool, THEN a managed browser tab receives the actual file."""
    log = tmp_path / "flight.bin"
    log.write_bytes(b"test log")
    driver = MagicMock()
    driver.window_handles = ["first"]
    driver.current_url = url
    with patch("ardupilot_methodic_configurator.backend_web_log_tools._new_browser", return_value=driver):
        open_log_in_web_tool(url, log)
        open_log_in_web_tool(url, log)

    driver.switch_to.new_window.assert_called_once_with("tab")
    assert driver.get.call_count == 2
    driver.get.assert_called_with(url)
    driver.find_element.assert_called_with("css selector", file_selector)
    assert driver.find_element.return_value.send_keys.call_count == 2
    driver.find_element.return_value.send_keys.assert_called_with(str(log.resolve()))


def test_web_tool_rejects_unrecognized_destinations_without_starting_browser(tmp_path: Path) -> None:
    """GIVEN an untrusted URL, WHEN requested, THEN no log is loaded into an arbitrary website."""
    log = tmp_path / "flight.bin"
    log.write_bytes(b"test log")
    with (
        patch("ardupilot_methodic_configurator.backend_web_log_tools._new_browser") as create_browser,
        pytest.raises(ValueError, match="Unsupported web log tool"),
    ):
        open_log_in_web_tool("https://example.org/collect", log)
    create_browser.assert_not_called()


def test_web_tool_refuses_missing_file_before_starting_browser(tmp_path: Path) -> None:
    """GIVEN a log deleted after listing, WHEN requested, THEN no browser is started."""
    with (
        patch("ardupilot_methodic_configurator.backend_web_log_tools._new_browser") as create_browser,
        pytest.raises(FileNotFoundError),
    ):
        open_log_in_web_tool("https://plot.ardupilot.org/", tmp_path / "missing.bin")
    create_browser.assert_not_called()


def test_web_tool_does_not_upload_after_redirect(tmp_path: Path) -> None:
    """GIVEN a redirected site, WHEN loading it, THEN do not send the local log to the new host."""
    log = tmp_path / "flight.bin"
    log.write_bytes(b"test log")
    driver = MagicMock()
    driver.current_url = "https://example.org/collect"
    with (
        patch("ardupilot_methodic_configurator.backend_web_log_tools._new_browser", return_value=driver),
        pytest.raises(ValueError, match="redirected"),
    ):
        open_log_in_web_tool("https://plot.ardupilot.org/", log)

    driver.find_element.assert_not_called()


@pytest.fixture(name="local_log")
def _local_log(tmp_path: Path) -> Path:
    """Provide a real local log without starting a browser."""
    log = tmp_path / "flight.bin"
    log.write_bytes(b"test log")
    return log


def test_log_is_not_sent_if_site_redirects_while_input_is_loading(local_log: Path) -> None:
    """GIVEN delayed JS navigation, WHEN the input appears, THEN reject the changed destination."""
    driver = MagicMock()
    driver.current_url = "https://plot.ardupilot.org/"

    def find_input(*_args: object) -> MagicMock:
        driver.current_url = "https://example.org/collect"
        return driver.find_element.return_value

    driver.find_element.side_effect = find_input
    with (
        patch("ardupilot_methodic_configurator.backend_web_log_tools._new_browser", return_value=driver),
        pytest.raises(ValueError, match="redirected"),
    ):
        open_log_in_web_tool("https://plot.ardupilot.org/", local_log)
    driver.find_element.return_value.send_keys.assert_not_called()


def test_log_is_not_sent_to_a_different_tool_on_the_same_host(local_log: Path) -> None:
    """GIVEN a same-host redirect, WHEN opening a tool, THEN do not expose the log to another path."""
    url = "https://firmware.ardupilot.org/Tools/WebTools/MAGFit/"
    driver = MagicMock()
    driver.current_url = url + "unexpected/"
    with (
        patch("ardupilot_methodic_configurator.backend_web_log_tools._new_browser", return_value=driver),
        pytest.raises(ValueError, match="redirected"),
    ):
        open_log_in_web_tool(url, local_log)
    driver.find_element.assert_not_called()


def test_user_can_restart_browser_after_failed_shutdown(local_log: Path) -> None:
    """GIVEN quit fails, WHEN closing and reopening, THEN forget the driver and start a fresh session."""
    session = backend_web_log_tools._BrowserSession()  # pylint: disable=protected-access
    old_driver = MagicMock()
    old_driver.quit.side_effect = WebDriverException("browser already gone")
    session._driver = old_driver  # pylint: disable=protected-access
    new_driver = MagicMock()
    new_driver.current_url = "https://plot.ardupilot.org/"
    with patch("ardupilot_methodic_configurator.backend_web_log_tools._new_browser", return_value=new_driver):
        session.close()
        session.close()
        session.open_log("https://plot.ardupilot.org/", local_log)
    old_driver.quit.assert_called_once()
    new_driver.get.assert_called_once()
    new_driver.switch_to.new_window.assert_not_called()


def test_restarting_closed_browser_releases_stale_driver(local_log: Path) -> None:
    """GIVEN Chrome was closed, WHEN another tool opens, THEN release its old driver before retrying."""
    session = backend_web_log_tools._BrowserSession()  # pylint: disable=protected-access
    old_driver = MagicMock()
    old_driver.switch_to.new_window.side_effect = InvalidSessionIdException("closed")
    session._driver = old_driver  # pylint: disable=protected-access
    new_driver = MagicMock()
    new_driver.current_url = "https://plot.ardupilot.org/"
    with patch("ardupilot_methodic_configurator.backend_web_log_tools._new_browser", return_value=new_driver):
        session.open_log("https://plot.ardupilot.org/", local_log)
    old_driver.quit.assert_called_once()
    new_driver.find_element.return_value.send_keys.assert_called_once_with(str(local_log.resolve()))


def test_failed_restart_does_not_leave_a_stale_session(local_log: Path) -> None:
    """GIVEN a closed browser, WHEN replacement startup fails, THEN a later action can retry cleanly."""
    session = backend_web_log_tools._BrowserSession()  # pylint: disable=protected-access
    old_driver = MagicMock()
    old_driver.switch_to.new_window.side_effect = InvalidSessionIdException("closed")
    session._driver = old_driver  # pylint: disable=protected-access
    with (
        patch(
            "ardupilot_methodic_configurator.backend_web_log_tools._new_browser",
            side_effect=WebDriverException("cannot launch"),
        ),
        pytest.raises(WebDriverException, match="cannot launch"),
    ):
        session.open_log("https://plot.ardupilot.org/", local_log)
    assert session._driver is None  # pylint: disable=protected-access


def test_browser_navigation_has_a_bounded_timeout(local_log: Path) -> None:
    """GIVEN a slow site, WHEN opening a log, THEN navigation is bounded before issuing the request."""
    driver = MagicMock()
    driver.current_url = "https://plot.ardupilot.org/"
    with patch("ardupilot_methodic_configurator.backend_web_log_tools._new_browser", return_value=driver):
        open_log_in_web_tool("https://plot.ardupilot.org/", local_log)
    assert driver.method_calls.index(("set_page_load_timeout", (30,), {})) < driver.method_calls.index(
        ("get", ("https://plot.ardupilot.org/",), {})
    )


@pytest.mark.parametrize("state", ["?view=log", "#viewer", "?view=log#viewer"])
def test_tool_can_use_query_and_fragment_state(local_log: Path, state: str) -> None:
    """GIVEN tool UI state in its URL, WHEN the input loads, THEN the selected tool still receives the log."""
    driver = MagicMock()
    driver.current_url = "https://plot.ardupilot.org/" + state
    with patch("ardupilot_methodic_configurator.backend_web_log_tools._new_browser", return_value=driver):
        open_log_in_web_tool("https://plot.ardupilot.org/", local_log)
    driver.find_element.return_value.send_keys.assert_called_once_with(str(local_log.resolve()))


@pytest.mark.parametrize("error_type", [InvalidSessionIdException, NoSuchWindowException])
def test_browser_recovery_retries_once_and_releases_failed_replacement(local_log: Path, error_type: type[Exception]) -> None:
    """GIVEN repeatedly closed browsers, WHEN opening a log, THEN retry only once and retain no dead driver."""
    session = backend_web_log_tools._BrowserSession()  # pylint: disable=protected-access
    drivers = [MagicMock(), MagicMock()]
    for driver in drivers:
        driver.window_handles = []
        driver.get.side_effect = error_type("closed")
    with (
        patch("ardupilot_methodic_configurator.backend_web_log_tools._new_browser", side_effect=drivers) as create_browser,
        pytest.raises(error_type),
    ):
        session.open_log("https://plot.ardupilot.org/", local_log)
    assert create_browser.call_count == 2
    for driver in drivers:
        driver.quit.assert_called_once()
    assert session._driver is None  # pylint: disable=protected-access


@pytest.mark.parametrize("closed_during", ["new_tab", "navigation"])
def test_closing_active_tab_preserves_other_analysis_tabs(local_log: Path, closed_during: str) -> None:
    """GIVEN a surviving analysis tab, WHEN the active tab closes, THEN load a new tab without quitting Chrome."""
    session = backend_web_log_tools._BrowserSession()  # pylint: disable=protected-access
    driver = MagicMock()
    driver.current_url = "https://plot.ardupilot.org/"
    driver.window_handles = ["existing-analysis"]
    operation = driver.switch_to.new_window if closed_during == "new_tab" else driver.get
    operation.side_effect = [NoSuchWindowException("active tab closed"), None]
    session._driver = driver  # pylint: disable=protected-access
    with patch("ardupilot_methodic_configurator.backend_web_log_tools._new_browser", return_value=driver) as create_browser:
        session.open_log(driver.current_url, local_log)
    create_browser.assert_not_called()
    driver.quit.assert_not_called()
    driver.switch_to.window.assert_called_once_with("existing-analysis")
    assert driver.switch_to.new_window.call_count == 2
    driver.find_element.return_value.send_keys.assert_called_once_with(str(local_log.resolve()))


def test_recovery_skips_a_surviving_tab_that_closes_before_switch(local_log: Path) -> None:
    """GIVEN two analysis tabs, WHEN one closes during recovery, THEN recover using the other without quitting."""
    session = backend_web_log_tools._BrowserSession()  # pylint: disable=protected-access
    driver = MagicMock()
    driver.current_url = "https://plot.ardupilot.org/"
    driver.window_handles = ["closing-analysis", "existing-analysis"]
    driver.switch_to.new_window.side_effect = [NoSuchWindowException("active tab closed"), None]
    driver.switch_to.window.side_effect = [NoSuchWindowException("also closed"), None]
    session._driver = driver  # pylint: disable=protected-access
    with patch("ardupilot_methodic_configurator.backend_web_log_tools._new_browser", return_value=driver) as create_browser:
        session.open_log(driver.current_url, local_log)
    create_browser.assert_not_called()
    driver.quit.assert_not_called()
    assert [args.args[0] for args in driver.switch_to.window.call_args_list] == ["closing-analysis", "existing-analysis"]
    driver.find_element.return_value.send_keys.assert_called_once()


def test_repeated_tab_closure_reports_failure_without_destroying_analysis(local_log: Path) -> None:
    """GIVEN an analysis tab survives, WHEN both attempts lose their active tab, THEN stop retrying but retain Chrome."""
    session = backend_web_log_tools._BrowserSession()  # pylint: disable=protected-access
    driver = MagicMock()
    driver.current_url = "https://plot.ardupilot.org/"
    driver.window_handles = ["existing-analysis"]
    driver.switch_to.new_window.side_effect = NoSuchWindowException("active tab closed")
    session._driver = driver  # pylint: disable=protected-access
    with (
        patch("ardupilot_methodic_configurator.backend_web_log_tools._new_browser", return_value=driver) as create_browser,
        pytest.raises(NoSuchWindowException),
    ):
        session.open_log(driver.current_url, local_log)
    create_browser.assert_not_called()
    driver.quit.assert_not_called()
    assert driver.switch_to.new_window.call_count == 2
    assert session._driver is driver  # pylint: disable=protected-access


@pytest.mark.parametrize("remaining_tab", ["none", "closed", "invalid_session"])
def test_closed_active_tab_restarts_browser_when_no_usable_tab_remains(local_log: Path, remaining_tab: str) -> None:
    """GIVEN no usable browsing context, WHEN the active tab closes, THEN release the dead session and restart."""
    session = backend_web_log_tools._BrowserSession()  # pylint: disable=protected-access
    driver = MagicMock()
    driver.window_handles = [] if remaining_tab == "none" else ["last-tab"]
    driver.switch_to.new_window.side_effect = NoSuchWindowException("active tab closed")
    driver.switch_to.window.side_effect = (
        InvalidSessionIdException("session gone") if remaining_tab == "invalid_session" else NoSuchWindowException("closed")
    )
    session._driver = driver  # pylint: disable=protected-access
    replacement = MagicMock()
    replacement.current_url = "https://plot.ardupilot.org/"
    with patch("ardupilot_methodic_configurator.backend_web_log_tools._new_browser", return_value=replacement):
        session.open_log(replacement.current_url, local_log)
    driver.quit.assert_called_once()
    replacement.find_element.return_value.send_keys.assert_called_once_with(str(local_log.resolve()))
