"""
Open a selected local flight log in ArduPilot browser-based analysis tools.

Selenium opens a browser controlled by the application; it does not attach to an
existing personal browser profile. The file is handed to the site's own file input,
without reading or uploading its contents through AMC.

SPDX-FileCopyrightText: 2026 ArduPilot Contributors
SPDX-License-Identifier: GPL-3.0-or-later
"""

from atexit import register
from dataclasses import dataclass
from logging import warning
from pathlib import Path
from threading import Lock
from urllib.parse import urlsplit

from selenium.common.exceptions import InvalidSessionIdException, NoSuchWindowException, WebDriverException
from selenium.webdriver.chrome.webdriver import WebDriver as ChromeWebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait

from ardupilot_methodic_configurator import _


@dataclass(frozen=True)
class WebLogTool:
    """Display label and local-log input for a trusted analysis website."""

    label: str
    file_selector: str


# Pin both destination and input: never send local logs to an arbitrary URL.
WEB_LOG_TOOLS: dict[str, WebLogTool] = {
    "https://plotbeta.ardupilot.org/": WebLogTool(_("plotbeta"), "#choosefile"),
    "https://plot.ardupilot.org/": WebLogTool(_("plot"), "#choosefile"),
    "https://firmware.ardupilot.org/Tools/WebTools/HardwareReport/": WebLogTool(_("hardware report"), "#fileItem"),
    "https://firmware.ardupilot.org/Tools/WebTools/MAGFit/": WebLogTool(_("MagFit"), "#fileItem"),
    "https://firmware.ardupilot.org/Tools/WebTools/FilterReview/": WebLogTool(_("Filter Review"), "#fileItem"),
    "https://firmware.ardupilot.org/Tools/WebTools/PIDReview/": WebLogTool(_("PID Review"), "#fileItem"),
    "https://firmware.ardupilot.org/Tools/WebTools/StreamStats/": WebLogTool(_("Stream stats"), "#fileItem"),
    "https://firmware.ardupilot.org/Tools/WebTools/SysID/": WebLogTool(_("System ID"), "#fileItem"),
}


def _new_browser() -> WebDriver:
    """Launch Chrome through Selenium Manager (which supplies a compatible driver)."""
    return ChromeWebDriver()


class _BrowserSession:
    """Keep one Selenium-controlled browser and serialize new-tab operations."""

    def __init__(self) -> None:
        self._driver: WebDriver | None = None
        self._lock = Lock()

    def close(self) -> None:
        """Release the managed browser and driver when AMC exits."""
        with self._lock:
            self._discard_driver()

    def _discard_driver(self) -> None:
        """Forget a driver before best-effort cleanup; caller must hold the lock."""
        driver, self._driver = self._driver, None
        if driver is not None:
            try:
                driver.quit()
            except WebDriverException as error:
                warning("Could not close web log browser: %s", error)

    def open_log(self, url: str, file_path: Path) -> None:
        """Open a browser tab and submit the selected file to the site's input."""
        with self._lock:
            for attempt in range(2):
                open_new_tab = self._driver is not None
                if self._driver is None:
                    self._driver = _new_browser()
                driver = self._driver
                try:
                    if open_new_tab:
                        driver.switch_to.new_window("tab")
                    self._load_log(driver, url, file_path)
                    return
                except (InvalidSessionIdException, NoSuchWindowException) as error:
                    # Losing the active tab does not invalidate other analyses.
                    # Recover focus before retrying in a new tab; replace only
                    # sessions with no usable browsing context.
                    if not isinstance(error, NoSuchWindowException) or not self._switch_to_surviving_tab(driver):
                        self._discard_driver()
                    if attempt:
                        raise

    @staticmethod
    def _switch_to_surviving_tab(driver: WebDriver) -> bool:
        """Recover focus without navigating or closing existing analysis tabs."""
        try:
            for handle in driver.window_handles:
                try:
                    driver.switch_to.window(handle)
                    return True
                except NoSuchWindowException:  # noqa: PERF203 - each remote switch can race with tab closure
                    # A tab can close between enumeration and switching.
                    continue
        except (InvalidSessionIdException, NoSuchWindowException):
            return False
        return False

    @staticmethod
    def _check_destination(driver: WebDriver, url: str) -> None:
        """Require the approved origin and exact tool path, allowing query/fragment state."""
        expected, actual = urlsplit(url), urlsplit(driver.current_url)
        if (actual.scheme, actual.netloc, actual.path) != (expected.scheme, expected.netloc, expected.path):
            msg = _("Web log tool redirected to an unexpected address")
            raise ValueError(msg)

    @staticmethod
    def _load_log(driver: WebDriver, url: str, file_path: Path) -> None:
        """Navigate to an approved tool and pass it the selected local log."""
        driver.set_page_load_timeout(30)
        driver.get(url)
        _BrowserSession._check_destination(driver, url)
        # The plot viewer mounts its input after its JS app starts; WebTools
        # has a separate .param input, so use the site-specific selector.
        input_element = WebDriverWait(driver, 30).until(
            ec.presence_of_element_located((By.CSS_SELECTOR, WEB_LOG_TOOLS[url].file_selector))
        )
        # JavaScript can navigate while the input is being mounted.
        _BrowserSession._check_destination(driver, url)
        input_element.send_keys(str(file_path.resolve()))


_SESSION = _BrowserSession()
register(_SESSION.close)


def open_log_in_web_tool(url: str, file_path: Path) -> None:
    """Open a new managed browser tab and set its file input to the selected local log."""
    if url not in WEB_LOG_TOOLS:
        msg = _("Unsupported web log tool")
        raise ValueError(msg)
    if file_path.suffix.lower() != ".bin" or not file_path.is_file() or file_path.is_symlink():
        raise FileNotFoundError(file_path)

    _SESSION.open_log(url, file_path)
