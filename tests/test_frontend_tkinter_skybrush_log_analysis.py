#!/usr/bin/env python3

"""
Behavior-driven tests for the Skybrush Log Analysis window.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import hashlib
import re
import tkinter as tk
from collections.abc import Callable, Generator
from pathlib import Path
from tkinter import ttk
from types import SimpleNamespace
from typing import Any
from unittest.mock import ANY, MagicMock, call, patch

import pytest
from skybrush_log_analyzer.config import Config
from skybrush_log_analyzer.errors import (
    AccountUnreachable,
    APIUnreachable,
    BadRequest,
    ConfigError,
    InvalidAPIKey,
    NotFound,
    ResponseParsingFailed,
    ServerError,
    Unauthenticated,
)

from ardupilot_methodic_configurator import __version__
from ardupilot_methodic_configurator.formatting import format_elapsed_time
from ardupilot_methodic_configurator.frontend_tkinter_file_browser_tasks import BackgroundTaskRunner
from ardupilot_methodic_configurator.frontend_tkinter_skybrush_log_analysis import (
    _LOG_TAG,
    FeedbackDialog,
    LoginForm,
    SkybrushLogAnalysisWindow,
    _format_api_version,
    _format_test_message,
    _skybrush_error_message,
    open_skybrush_log_analysis,
)

# pylint: disable=protected-access,redefined-outer-name,too-many-lines

MODULE = "ardupilot_methodic_configurator.frontend_tkinter_skybrush_log_analysis"
ACCOUNT_URL = "https://account.example.test"
API_URL = "https://api.example.test"
MANUAL_URL = "https://ardupilot.github.io/MethodicConfigurator/USERMANUAL_skybrush_log_analyzer.html"

#: Opens the window logged in or out, optionally for another log file.
WindowOpener = Callable[..., SkybrushLogAnalysisWindow]


# ---------------- shared helpers and fixtures ----------------


def finish(runner: BackgroundTaskRunner) -> None:
    """Wait for the runner's worker thread and deliver its result on the test (UI) thread."""
    thread = runner.thread
    assert thread is not None, "Expected a background task to be running"
    thread.join(timeout=5)
    assert not thread.is_alive(), "The background task did not finish in time"
    runner.poll()


def widget_texts(widget: tk.Misc) -> list[str]:
    """Collect the text of the widget and all its descendants that have a text option."""
    texts: list[str] = []
    for child in [widget, *_descendants(widget)]:
        try:
            texts.append(str(child.cget("text")))
        except tk.TclError:
            continue
    return texts


def _descendants(widget: tk.Misc) -> list[tk.Misc]:
    children = widget.winfo_children()
    return [descendant for child in children for descendant in [child, *_descendants(child)]]


def find_button(widget: tk.Misc, text: str) -> ttk.Button:
    """Find the (first) descendant button showing the given text."""
    for child in _descendants(widget):
        if isinstance(child, ttk.Button) and str(child.cget("text")) == text:
            return child
    msg = f"No button with text {text!r}"
    raise AssertionError(msg)


def tags_at_text(text_widget: tk.Text, needle: str) -> tuple[str, ...]:
    """Return the tag names applied at the first character of the needle in the text widget."""
    index = text_widget.search(needle, "1.0", stopindex=tk.END)
    assert index, f"{needle!r} not found in the results"
    return tuple(str(tag) for tag in text_widget.tag_names(index))


def results_of(window: SkybrushLogAnalysisWindow) -> str:
    return window.results_text.get("1.0", "end-1c")


@pytest.fixture
def messagebox_mock() -> Generator[MagicMock, None, None]:
    """Capture message boxes instead of showing them."""
    with patch(f"{MODULE}.messagebox") as mock:
        yield mock


@pytest.fixture(autouse=True)
def browser_mock() -> Generator[MagicMock, None, None]:
    """
    Capture browser openings instead of launching a browser, in every test of this module.

    Autouse, because a test or a mutated code path that reached the real browser would open
    a new browser window on every run (thousands of them during mutation testing).
    The standard library is blocked as well, in case the URL reaches it by another route.
    """
    with (
        patch(f"{MODULE}.webbrowser_open_url", return_value=True) as mock,
        patch(
            "ardupilot_methodic_configurator.backend_internet.webbrowser_open",
            side_effect=AssertionError("tests must not open a real browser"),
        ),
        patch("webbrowser.open", side_effect=AssertionError("tests must not open a real browser")),
        patch("webbrowser.open_new", side_effect=AssertionError("tests must not open a real browser")),
        patch("webbrowser.open_new_tab", side_effect=AssertionError("tests must not open a real browser")),
    ):
        yield mock


@pytest.fixture
def no_screen_rendering() -> Generator[None, None, None]:
    """Keep Tk from rendering to a physical screen, which crashes headless macOS runners."""
    with (
        patch.object(tk.Toplevel, "winfo_fpixels", side_effect=tk.TclError("no display")),
        patch("tkinter.Misc.update"),
        patch("tkinter.Misc.update_idletasks"),
        patch("tkinter.Misc.wait_visibility"),
        patch("tkinter.Misc.wait_window"),
    ):
        yield


@pytest.fixture
def logfile(tmp_path: Path) -> Path:
    """A small flight log on disk."""
    path = tmp_path / "flight_00042.bin"
    path.write_bytes(b"ArduPilot binary log content")
    return path


def make_client(config: Config) -> MagicMock:
    """A Skybrush API client that answers locally with realistic data."""
    client = MagicMock(name="APIClient")
    client.config = config
    client.version.return_value = {"app_version": "1.2.3"}
    client.analyze.return_value = {"raw": "analysis"}
    client.get_analysis_view_intent.return_value = "view-intent"
    client.get_web_login_url.return_value = "https://logs.example.test/sso?token=abc"
    client.suggest.return_value = {"id": 42}
    return client


@pytest.fixture
def skybrush(tmp_path: Path) -> SimpleNamespace:
    """Configuration of the Skybrush account and the client the API calls are answered by."""
    config_dir = tmp_path / "skybrush-config"
    config_dir.mkdir()
    logged_in = Config(api_key="stored-api-key", account_url=ACCOUNT_URL, api_url=API_URL, config_dir=config_dir)
    logged_out = Config(api_key=None, account_url=ACCOUNT_URL, api_url=API_URL, config_dir=config_dir)
    return SimpleNamespace(logged_in=logged_in, logged_out=logged_out, client=make_client(logged_in))


@pytest.fixture
def open_window(
    root: tk.Tk,
    skybrush: SimpleNamespace,
    logfile: Path,
    messagebox_mock: MagicMock,  # noqa: ARG001 # pylint: disable=unused-argument
    no_screen_rendering: None,  # noqa: ARG001 # pylint: disable=unused-argument
) -> Generator[WindowOpener, None, None]:
    """Open the window logged in or out; API calls are answered by the local client."""
    windows: list[SkybrushLogAnalysisWindow] = []
    with (
        patch(f"{MODULE}.APIClient") as api_client_class,
        patch(f"{MODULE}.Config.load") as config_load,
        patch(f"{MODULE}.compact", side_effect=lambda raw: raw.get("view", raw)),
    ):
        api_client_class.return_value = skybrush.client
        skybrush.api_client_class = api_client_class
        skybrush.config_load = config_load
        skybrush.windows = windows

        def opener(logged_in: bool = True, path: Path | None = None) -> SkybrushLogAnalysisWindow:
            config_load.return_value = skybrush.logged_in if logged_in else skybrush.logged_out
            window = SkybrushLogAnalysisWindow(root, str(path or logfile))
            windows.append(window)
            return window

        yield opener
    for window in windows:
        if window.root.winfo_exists():
            window.root.destroy()


@pytest.fixture
def logged_in_window(open_window: WindowOpener) -> SkybrushLogAnalysisWindow:
    """A logged-in window whose header version check has completed."""
    window = open_window(logged_in=True)
    finish(window._auth_runner)
    return window


def sample_view() -> dict[str, Any]:
    """A compact analysis view with notes, counts and two test results."""
    return {
        "note_title": "Flight review",
        "note_description": "Vibration needs attention.",
        "status_counts": {"WARN": 1, "PASS": 2},
        "test_results": [
            {
                "status": "WARN",
                "test_name": "paplan.tests.vibration",
                "title": "Vibration levels",
                "messages": [
                    {"text": "Peak Z-axis vibration", "severity": "warn", "value": 42.7, "unit": "m/s/s"},
                    {"text": "Clipping events", "severity": "info", "value": 3},
                ],
            },
            {"status": "PASS", "test_name": "paplan.tests:battery", "messages": [{"text": "Battery fine"}]},
        ],
    }


# ---------------- error messages ----------------


class TestSkybrushErrorMessages:
    """Every Skybrush API failure is explained to the user in plain words."""

    @pytest.mark.parametrize(
        ("error", "expected"),
        [
            (Unauthenticated(), "Not logged in. Use the Log in button to configure the API key."),
            (
                InvalidAPIKey("rejected", url=ACCOUNT_URL),
                f"The Skybrush API key is invalid or has been revoked. Create a new one at {ACCOUNT_URL}.",
            ),
            (
                AccountUnreachable("timeout", url=ACCOUNT_URL),
                f"Could not reach the Skybrush Account server at {ACCOUNT_URL}.",
            ),
            (
                APIUnreachable("connection refused", url="https://api.example.test"),
                "Could not reach the Skybrush API: connection refused",
            ),
            (
                ConfigError("permission denied"),
                "Could not read or write the 'skybrush-log-analyzer' configuration: permission denied",
            ),
            (BadRequest("log too large"), "The Skybrush API rejected the request: log too large"),
            (NotFound("no such analysis"), "The Skybrush API rejected the request: no such analysis"),
            (ServerError(), "The Skybrush API is currently unavailable."),
            (ResponseParsingFailed(), "The Skybrush API returned an unexpected response."),
        ],
    )
    def test_user_sees_a_specific_message_for_each_api_error(self, error: Exception, expected: str) -> None:
        """
        Each known API error is translated into its own explanation.

        GIVEN: The Skybrush API reports a known kind of failure
        WHEN: The failure is shown to the user
        THEN: The message names the problem, including the server URL or detail it carries
        """
        # Act (When): Translate the error
        message = _skybrush_error_message(error)

        # Assert (Then): The specific explanation is shown
        assert message == expected

    def test_user_sees_the_raw_reason_of_an_unknown_error(self) -> None:
        """
        An unexpected error is still reported, with its own text.

        GIVEN: An error that the Skybrush integration does not know about
        WHEN: The failure is shown to the user
        THEN: A generic failure message includes the original error text
        """
        message = _skybrush_error_message(RuntimeError("disk on fire"))

        assert message == "Skybrush API request failed: disk on fire"


# ---------------- display formatting ----------------


class TestResultFormatting:
    """Version lines and test messages are formatted consistently."""

    @pytest.mark.parametrize(
        ("version", "expected"),
        [
            ({"app_version": "1.2.3"}, "Skybrush API version: 1.2.3"),
            ({"app_version": ""}, "Skybrush API version: ?"),
            ({}, "Skybrush API version: ?"),
        ],
    )
    def test_user_sees_the_api_version_or_a_placeholder(self, version: dict[str, object], expected: str) -> None:
        """
        The API version line always shows something meaningful.

        GIVEN: Version info with or without an application version
        WHEN: The version line is formatted
        THEN: The version is shown, or a question mark when it is unknown
        """
        assert _format_api_version(version) == expected

    @pytest.mark.parametrize(
        ("message", "expected"),
        [
            ({"text": "Battery fine"}, ("Battery fine", "")),
            ({}, ("", "")),
            ({"text": "Peak vibration", "value": 42.7}, ("Peak vibration:", " 42.7")),
            ({"text": "Peak vibration", "value": 42.7, "unit": "m/s/s"}, ("Peak vibration:", " 42.7 m/s/s")),
            ({"text": "Peak vibration", "value": 42.7, "unit": "  "}, ("Peak vibration:", " 42.7")),
            ({"text": "Peak vibration", "value": 42.7, "unit": 5}, ("Peak vibration:", " 42.7")),
            ({"text": "Satellites", "value": 0}, ("Satellites:", " 0")),
            ({"text": "Satellites", "value": ""}, ("Satellites", "")),
            ({"text": "Satellites", "value": None, "unit": "m"}, ("Satellites", "")),
            ({"text": "Mode change", "timestamp": "  00:12  "}, ("[00:12] Mode change", "")),
            ({"text": "Mode change", "timestamp": "   "}, ("Mode change", "")),
            ({"text": "Mode change", "timestamp": True}, ("Mode change", "")),
            ({"text": "Mode change", "timestamp": None}, ("Mode change", "")),
        ],
    )
    def test_user_sees_test_messages_with_bold_values_and_units(
        self, message: dict[str, object], expected: tuple[str, str]
    ) -> None:
        """
        A test message splits into plain text and a bold value with its unit.

        GIVEN: A test-case message with optional value, unit and timestamp
        WHEN: It is formatted for the results view
        THEN: Only a present value is set in bold, with a colon after the text and a valid unit after the value
        """
        assert _format_test_message(message) == expected

    @pytest.mark.parametrize("timestamp", [312.4, 5])
    def test_user_sees_numeric_timestamps_as_elapsed_flight_time(self, timestamp: float) -> None:
        """
        Numeric timestamps are shown as elapsed flight time.

        GIVEN: A test message with a timestamp in seconds since the start of the log
        WHEN: It is formatted for the results view
        THEN: The elapsed time precedes the message text in brackets
        """
        plain, bold = _format_test_message({"text": "Peak vibration", "timestamp": timestamp})

        assert plain == f"[{format_elapsed_time(timestamp)}] Peak vibration"
        assert bold == ""


# ---------------- feedback dialog ----------------


@pytest.fixture
def feedback(
    root: tk.Tk,
    messagebox_mock: MagicMock,
    no_screen_rendering: None,  # noqa: ARG001 # pylint: disable=unused-argument
) -> Generator[SimpleNamespace, None, None]:
    """An open feedback dialog whose submissions are captured."""
    submit = MagicMock(name="submit", return_value=True)
    dialog = FeedbackDialog(root, submit)
    yield SimpleNamespace(dialog=dialog, submit=submit, messagebox=messagebox_mock)
    if dialog._root.winfo_exists():
        dialog._root.destroy()


def fill_feedback(
    dialog: FeedbackDialog, title: str = "Wrong vibration verdict", description: str = "Log shows less."
) -> None:
    dialog._title_entry.delete(0, tk.END)
    dialog._title_entry.insert(0, title)
    dialog._description_text.delete("1.0", tk.END)
    dialog._description_text.insert("1.0", description)


class TestFeedbackCategories:
    """Feedback categories are shown as translated labels but sent as API identifiers."""

    def test_unknown_category_is_shown_as_is(self) -> None:
        """
        A category without a label is shown by its identifier.

        GIVEN: A category the dialog has no label for
        WHEN: Its label is requested
        THEN: The identifier itself is returned
        """
        assert FeedbackDialog.category_label("brand_new") == "brand_new"  # type: ignore[arg-type]

    def test_user_is_told_which_category_to_use_for_a_missing_check(self, feedback: SimpleNamespace) -> None:
        """
        The instructions name the category for missing checks by its label.

        GIVEN: The user opens the feedback dialog
        WHEN: They read the instructions
        THEN: The missing-check hint names the 'Missing or inadequate test' category
        """
        texts = widget_texts(feedback.dialog._root)

        assert any("(category 'Missing or inadequate test')" in text for text in texts)

    @pytest.mark.parametrize(("index", "category"), list(enumerate(FeedbackDialog.CATEGORIES)))
    def test_selected_label_is_submitted_as_its_api_category(
        self, feedback: SimpleNamespace, index: int, category: str
    ) -> None:
        """
        The chosen label is sent as the matching API category.

        GIVEN: The user picked a category label and filled in the form
        WHEN: They submit the feedback
        THEN: The API identifier of that category is submitted
        """
        feedback.dialog._category_box.current(index)
        fill_feedback(feedback.dialog)

        feedback.dialog._on_submit_click()

        assert feedback.submit.call_args.args[0] == category


class TestFeedbackSubmission:
    """The user can submit valid feedback and is told what happened."""

    @pytest.mark.parametrize("title", ["", "   ", "x" * 101])
    def test_user_must_give_a_title_of_1_to_100_characters(self, feedback: SimpleNamespace, title: str) -> None:
        """
        A missing or overlong title is rejected before anything is sent.

        GIVEN: The user entered an empty or too long title
        WHEN: They click Submit
        THEN: An error asks for a title of 1 to 100 characters and nothing is submitted
        """
        fill_feedback(feedback.dialog, title=title)

        feedback.dialog._on_submit_click()

        feedback.messagebox.showerror.assert_called_once()
        assert feedback.messagebox.showerror.call_args == call(
            ANY, "Please provide a title between 1 and 100 characters.", parent=feedback.dialog._root
        )
        feedback.submit.assert_not_called()

    @pytest.mark.parametrize("title", ["x", "y" * 100])
    def test_user_can_submit_titles_at_the_length_limits(self, feedback: SimpleNamespace, title: str) -> None:
        """
        Titles of exactly 1 and 100 characters are accepted.

        GIVEN: The user entered a title at the length limits
        WHEN: They click Submit
        THEN: The feedback is submitted without an error
        """
        fill_feedback(feedback.dialog, title=title)

        feedback.dialog._on_submit_click()

        feedback.messagebox.showerror.assert_not_called()
        feedback.submit.assert_called_once()

    def test_user_must_describe_the_issue(self, feedback: SimpleNamespace) -> None:
        """
        An empty description is rejected before anything is sent.

        GIVEN: The user entered a title but only whitespace as description
        WHEN: They click Submit
        THEN: An error asks for a description and nothing is submitted
        """
        fill_feedback(feedback.dialog, description="  \n ")

        feedback.dialog._on_submit_click()

        assert feedback.messagebox.showerror.call_args == call(
            ANY, "Please describe the issue in the description field.", parent=feedback.dialog._root
        )
        feedback.submit.assert_not_called()

    def test_user_sees_the_feedback_being_sent(self, feedback: SimpleNamespace) -> None:
        """
        Submitting sends the trimmed text and shows progress.

        GIVEN: The user filled in title and description with surrounding whitespace
        WHEN: They click Submit
        THEN: The trimmed title and description are submitted
        AND: Submit is disabled while a progress message is shown
        """
        fill_feedback(feedback.dialog, title="  Wrong verdict  ", description="\n Log shows less. \n")

        feedback.dialog._on_submit_click()

        category, title, description, on_done = feedback.submit.call_args.args
        assert (category, title, description) == ("bug", "Wrong verdict", "Log shows less.")
        assert on_done == feedback.dialog._on_submitted
        assert str(feedback.dialog._submit_button.cget("state")) == "disabled"
        assert feedback.dialog._progress_label.cget("text") == "Sending feedback to the Skybrush team..."

    def test_form_stays_editable_when_the_submission_cannot_start(self, feedback: SimpleNamespace) -> None:
        """
        A submission that could not start leaves the form ready to try again.

        GIVEN: The submission cannot be started
        WHEN: The user clicks Submit
        THEN: Submit stays enabled and no progress message is shown
        """
        feedback.submit.return_value = False
        fill_feedback(feedback.dialog)

        feedback.dialog._on_submit_click()

        assert str(feedback.dialog._submit_button.cget("state")) != "disabled"
        assert feedback.dialog._progress_label.cget("text") == ""

    @pytest.mark.parametrize(
        ("result", "expected"),
        [
            ({"id": 42}, "Thank you for your feedback! The Skybrush team will review your suggestion. (#42)"),
            ({"id": "42"}, "Thank you for your feedback! The Skybrush team will review your suggestion."),
            ({}, "Thank you for your feedback! The Skybrush team will review your suggestion."),
            (None, "Thank you for your feedback! The Skybrush team will review your suggestion."),
        ],
    )
    def test_user_is_thanked_and_the_dialog_closes_after_success(
        self, feedback: SimpleNamespace, result: object, expected: str
    ) -> None:
        """
        A delivered suggestion is confirmed, with its number when the server returns one.

        GIVEN: The user submitted feedback
        WHEN: The Skybrush team received it
        THEN: A thank-you message is shown, with the suggestion number if known
        AND: The dialog closes
        """
        feedback.dialog._on_submitted(result, None)

        feedback.messagebox.showinfo.assert_called_once()
        assert feedback.messagebox.showinfo.call_args == call(ANY, expected, parent=feedback.dialog._root)
        assert not feedback.dialog._root.winfo_exists()

    def test_user_can_retry_after_a_failed_submission(self, feedback: SimpleNamespace) -> None:
        """
        A failed submission keeps the dialog and its text for another try.

        GIVEN: The user submitted feedback
        WHEN: The server could not be reached
        THEN: The reason is shown, Submit is enabled again and the dialog stays open
        """
        fill_feedback(feedback.dialog)
        feedback.dialog._on_submit_click()

        feedback.dialog._on_submitted(None, ServerError())

        assert feedback.messagebox.showerror.call_args == call(
            ANY, "The Skybrush API is currently unavailable.", parent=feedback.dialog._root
        )
        assert str(feedback.dialog._submit_button.cget("state")) == "normal"
        assert feedback.dialog._progress_label.cget("text") == ""
        assert feedback.dialog._root.winfo_exists()
        assert feedback.dialog._title_entry.get() == "Wrong vibration verdict"

    @pytest.mark.parametrize("error", [Unauthenticated(), InvalidAPIKey("rejected", url=ACCOUNT_URL)])
    def test_dialog_closes_when_the_session_was_rejected(self, feedback: SimpleNamespace, error: Exception) -> None:
        """
        A rejected session closes the dialog so that the user can log in again.

        GIVEN: The user submitted feedback
        WHEN: The session turns out to be logged out or the API key is revoked
        THEN: The reason is shown and the dialog closes
        """
        feedback.dialog._on_submitted(None, error)

        assert feedback.messagebox.showerror.call_args == call(
            ANY, _skybrush_error_message(error), parent=feedback.dialog._root
        )
        assert not feedback.dialog._root.winfo_exists()

    def test_late_result_after_closing_the_dialog_is_ignored(self, feedback: SimpleNamespace) -> None:
        """
        A result that arrives after the user closed the dialog shows nothing.

        GIVEN: The user cancelled the dialog while feedback was being sent
        WHEN: The result arrives
        THEN: No message box is shown
        """
        feedback.dialog._root.destroy()

        feedback.dialog._on_submitted({"id": 1}, None)

        feedback.messagebox.showinfo.assert_not_called()
        feedback.messagebox.showerror.assert_not_called()

    def test_dialog_is_shown_modally_over_its_parent(self, root: tk.Tk, feedback: SimpleNamespace) -> None:
        """
        The dialog blocks the window behind it until it is closed.

        GIVEN: The feedback dialog was created
        WHEN: It is shown
        THEN: It stays on top of its parent window
        AND: It grabs the input and the caller waits for it to close
        """
        with patch.object(root, "wait_window") as wait_window:
            feedback.dialog.show()

        assert str(feedback.dialog._root.transient()) == str(root)
        wait_window.assert_called_once_with(feedback.dialog._root)
        assert feedback.dialog._root.grab_current() is not None

    def test_cancel_closes_the_dialog_without_sending(self, feedback: SimpleNamespace) -> None:
        """
        Cancel discards the feedback.

        GIVEN: The user filled in the feedback form
        WHEN: They click Cancel
        THEN: The dialog closes and nothing is sent
        """
        fill_feedback(feedback.dialog)

        find_button(feedback.dialog._root, "Cancel").invoke()

        assert not feedback.dialog._root.winfo_exists()
        feedback.submit.assert_not_called()

    def test_submit_button_sends_the_feedback(self, feedback: SimpleNamespace) -> None:
        """
        The Submit button sends the filled-in form.

        GIVEN: The user filled in the feedback form
        WHEN: They click Submit
        THEN: The feedback is handed over for submission
        """
        fill_feedback(feedback.dialog)

        find_button(feedback.dialog._root, "Submit").invoke()

        assert feedback.submit.call_args.args[1:3] == ("Wrong vibration verdict", "Log shows less.")


# ---------------- login form ----------------


@pytest.fixture
def login_form(
    root: tk.Tk,
    messagebox_mock: MagicMock,
    browser_mock: MagicMock,
    no_screen_rendering: None,  # noqa: ARG001 # pylint: disable=unused-argument
) -> Generator[SimpleNamespace, None, None]:
    """A login form whose login attempts are captured."""
    login = MagicMock(name="login", return_value=True)
    form = LoginForm(root, login, ACCOUNT_URL)
    yield SimpleNamespace(form=form, login=login, messagebox=messagebox_mock, browser=browser_mock)
    form.destroy()


class TestLoginForm:
    """The user logs in with an API key from their Skybrush Account."""

    def test_user_must_paste_an_api_key(self, login_form: SimpleNamespace) -> None:
        """
        Logging in without a key is rejected.

        GIVEN: The API key field is empty or only whitespace
        WHEN: The user clicks Log in
        THEN: An error asks for the key and no login is attempted
        """
        login_form.form._key_entry.insert(0, "   ")

        login_form.form._on_login_click()

        assert login_form.messagebox.showerror.call_args == call(ANY, "Please paste your API key.", parent=login_form.form)
        login_form.login.assert_not_called()

    def test_user_sees_the_key_being_validated(self, login_form: SimpleNamespace) -> None:
        """
        The trimmed key is validated in the background.

        GIVEN: The user pasted a key with surrounding whitespace
        WHEN: They click Log in
        THEN: The trimmed key is used, Log in is disabled and progress is shown
        """
        login_form.form._key_entry.insert(0, "  my-api-key  ")

        login_form.form._on_login_click()

        assert login_form.login.call_args.args == ("my-api-key", login_form.form._on_login_done)
        assert str(login_form.form._login_button.cget("state")) == "disabled"
        assert login_form.form._progress_label.cget("text") == "Validating the API key and logging in..."

    def test_form_stays_editable_when_a_login_is_already_running(self, login_form: SimpleNamespace) -> None:
        """
        A login that could not start leaves the form unchanged.

        GIVEN: Another login is still running
        WHEN: The user clicks Log in
        THEN: The button stays enabled and no progress is shown
        """
        login_form.login.return_value = False
        login_form.form._key_entry.insert(0, "my-api-key")

        login_form.form._on_login_click()

        assert str(login_form.form._login_button.cget("state")) != "disabled"
        assert login_form.form._progress_label.cget("text") == ""

    def test_user_sees_why_the_login_failed_and_keeps_the_key(self, login_form: SimpleNamespace) -> None:
        """
        A rejected key is explained and kept for correction.

        GIVEN: The user tried to log in
        WHEN: The account rejects the key
        THEN: The reason is shown, Log in is enabled again and the key stays in the field
        """
        login_form.form._key_entry.insert(0, "my-api-key")
        login_form.form._on_login_click()

        login_form.form._on_login_done(None, InvalidAPIKey("rejected", url=ACCOUNT_URL))

        assert login_form.messagebox.showerror.call_args == call(
            ANY, _skybrush_error_message(InvalidAPIKey("rejected", url=ACCOUNT_URL)), parent=login_form.form
        )
        assert str(login_form.form._login_button.cget("state")) == "normal"
        assert login_form.form._progress_label.cget("text") == ""
        assert login_form.form._key_entry.get() == "my-api-key"

    def test_key_field_is_cleared_after_a_successful_login(self, login_form: SimpleNamespace) -> None:
        """
        A successful login does not leave the secret key on screen.

        GIVEN: The user tried to log in
        WHEN: The login succeeds
        THEN: The key field is emptied and no error is shown
        """
        login_form.form._key_entry.insert(0, "my-api-key")
        login_form.form._on_login_click()

        login_form.form._on_login_done(object(), None)

        assert login_form.form._key_entry.get() == ""
        login_form.messagebox.showerror.assert_not_called()

    def test_late_login_result_after_closing_is_ignored(self, login_form: SimpleNamespace) -> None:
        """
        A login result arriving after the form was closed shows nothing.

        GIVEN: The login form was closed while logging in
        WHEN: The login result arrives
        THEN: No error is shown
        """
        login_form.form.destroy()

        login_form.form._on_login_done(None, Unauthenticated())

        login_form.messagebox.showerror.assert_not_called()

    def test_user_can_open_the_account_page_to_create_a_key(self, login_form: SimpleNamespace) -> None:
        """
        The account page with the API keys is one click away.

        GIVEN: The user needs an API key
        WHEN: They click Open Skybrush Account
        THEN: The account URL opens in the browser
        """
        find_button(login_form.form, "Open Skybrush Account").invoke()

        login_form.browser.assert_called_once_with(ACCOUNT_URL)

    def test_key_is_hidden_while_typing(self, login_form: SimpleNamespace) -> None:
        """
        The API key is masked on screen.

        GIVEN: The login form is shown
        WHEN: The user types the key
        THEN: The field masks the characters
        """
        assert login_form.form._key_entry.cget("show") == "*"

    def test_log_in_button_starts_the_login(self, login_form: SimpleNamespace) -> None:
        """
        The Log in button submits the pasted key.

        GIVEN: The user pasted an API key
        WHEN: They click Log in
        THEN: The key is handed over for validation
        """
        login_form.form._key_entry.insert(0, "pasted-key")

        login_form.form._login_button.invoke()

        assert login_form.login.call_args.args[0] == "pasted-key"


# ---------------- window: log-in state ----------------


class TestWindowLoginState:
    """The window reflects whether the user is logged in to the Skybrush Account."""

    def test_logged_out_user_sees_the_login_form_and_disabled_actions(self, open_window: WindowOpener, logfile: Path) -> None:
        """
        Without a stored API key the user is asked to log in.

        GIVEN: No API key is stored
        WHEN: The window opens
        THEN: The login form is shown instead of the results, and the service buttons are disabled
        AND: The header explains that a log-in is needed
        """
        window = open_window(logged_in=False)

        assert window._client is None
        assert window._login_form.winfo_manager() == "pack"
        assert window._results_row.winfo_manager() == ""
        for button in (window._logout_button, window._run_analysis_button, window._open_web_button, window._feedback_button):
            assert str(button.cget("state")) == "disabled"
        assert window._auth_status_label.cget("text") == "Not logged in. Use the Log in button to configure the API key."
        assert str(window._auth_status_label.cget("foreground")) == "red3"
        assert window._version_label.cget("text") == "Skybrush API version: requires logging in"
        assert window.root.title() == "Skybrush Log Analysis"
        assert f"Selected log: {logfile.name}" in widget_texts(window.root)

    def test_logged_in_user_sees_the_api_version_and_account(
        self, open_window: WindowOpener, skybrush: SimpleNamespace
    ) -> None:
        """
        A stored API key logs the user in and fetches the API version.

        GIVEN: An API key is stored
        WHEN: The window opens and the version check completes
        THEN: The stored configuration is used to connect
        AND: The results area and enabled service buttons are shown
        AND: The header shows the API version and the account the user is authenticated at
        """
        window = open_window(logged_in=True)
        skybrush.api_client_class.assert_called_once_with(skybrush.logged_in)
        assert window._version_label.cget("text") == "Fetching Skybrush API version..."

        finish(window._auth_runner)

        assert window._results_row.winfo_manager() == "pack"
        assert window._login_form.winfo_manager() == ""
        for button in (window._logout_button, window._run_analysis_button, window._open_web_button, window._feedback_button):
            assert str(button.cget("state")) == "normal"
        assert window._version_label.cget("text") == "Skybrush API version: 1.2.3"
        assert window._auth_status_label.cget("text") == f"Authenticated at {ACCOUNT_URL}"
        assert str(window._auth_status_label.cget("foreground")) == "dark green"
        assert "No analysis results yet" in results_of(window)

    def test_revoked_key_logs_the_user_out(self, open_window: WindowOpener, skybrush: SimpleNamespace) -> None:
        """
        A key revoked since it was stored ends the session.

        GIVEN: The stored API key was revoked
        WHEN: The window checks the log-in at start
        THEN: The login form is shown with the reason in the header
        """
        skybrush.client.version.side_effect = InvalidAPIKey("revoked", url=ACCOUNT_URL)
        window = open_window(logged_in=True)

        finish(window._auth_runner)

        assert window._client is None
        assert window._login_form.winfo_manager() == "pack"
        assert window._auth_status_label.cget("text") == _skybrush_error_message(InvalidAPIKey("x", url=ACCOUNT_URL))
        assert str(window._auth_status_label.cget("foreground")) == "red3"

    def test_unreachable_api_keeps_the_session_but_shows_the_problem(
        self, open_window: WindowOpener, skybrush: SimpleNamespace
    ) -> None:
        """
        A temporary network problem does not log the user out.

        GIVEN: The API cannot be reached when the window opens
        WHEN: The version check fails
        THEN: The user stays logged in, the version is unknown and the reason is shown
        """
        error = APIUnreachable("timeout", url="https://api.example.test")
        skybrush.client.version.side_effect = error
        window = open_window(logged_in=True)

        with patch(f"{MODULE}.logging_error") as log_error:
            finish(window._auth_runner)

        assert window._client is skybrush.client
        assert window._version_label.cget("text") == "Skybrush API version unknown"
        assert window._auth_status_label.cget("text") == "Could not reach the Skybrush API: timeout"
        assert str(window._auth_status_label.cget("foreground")) == "red3"
        log_error.assert_called_once()
        assert log_error.call_args.args[1:] == (_LOG_TAG, error)

    def test_key_revoked_during_a_version_retry_logs_out_and_clears_the_status(
        self, logged_in_window: SkybrushLogAnalysisWindow, skybrush: SimpleNamespace
    ) -> None:
        """
        A session rejected in the background leaves no stale status behind.

        GIVEN: An analysis completed while the API version was still unknown
        WHEN: The retried version check finds that the key was revoked
        THEN: The user is logged out and the 'Analysis completed' status is cleared
        """
        logged_in_window._version_info = {}
        skybrush.client.analyze.return_value = {"view": sample_view()}
        skybrush.client.version.side_effect = InvalidAPIKey("revoked", url=ACCOUNT_URL)
        logged_in_window._on_run_analysis_click()
        finish(logged_in_window._analysis_runner)
        assert logged_in_window.status_label.cget("text") == "Analysis completed"

        with patch(f"{MODULE}.logging_error"):
            finish(logged_in_window._auth_runner)

        assert logged_in_window._client is None
        assert logged_in_window.status_label.cget("text") == ""

    def test_login_form_in_the_window_logs_in_and_links_to_the_account(
        self, open_window: WindowOpener, skybrush: SimpleNamespace, browser_mock: MagicMock
    ) -> None:
        """
        The login form shown in the logged-out window is connected to the window.

        GIVEN: The user is logged out
        WHEN: They open the account page and log in with a pasted key
        THEN: The configured account page opens and the window logs in with that key
        """
        window = open_window(logged_in=False)
        skybrush.api_client_class.login.return_value = skybrush.client
        assert window._login_form.winfo_toplevel() is window.root

        find_button(window._login_form, "Open Skybrush Account").invoke()
        window._login_form._key_entry.insert(0, "pasted-key")
        window._login_form._login_button.invoke()
        finish(window._login_runner)

        browser_mock.assert_called_once_with(ACCOUNT_URL)
        skybrush.api_client_class.login.assert_called_once_with(skybrush.logged_out.config_dir, "pasted-key")
        assert window._client is skybrush.client

    def test_background_results_are_delivered_only_while_the_window_is_open(
        self, logged_in_window: SkybrushLogAnalysisWindow
    ) -> None:
        """
        Results of background work arrive on the Tk event loop, but not after the window closed.

        GIVEN: A background task scheduled its completion callback
        WHEN: The event loop runs the callback while the window is open, and again after it closed
        THEN: The callback runs only while the window is open
        """
        callback = MagicMock()
        with patch.object(logged_in_window.root, "after") as after:
            logged_in_window._schedule_while_open(25, callback)
        delay, scheduled = after.call_args.args

        scheduled()
        logged_in_window.root.destroy()
        scheduled()

        assert delay == 25
        callback.assert_called_once_with()

    def test_user_logs_in_with_a_new_api_key(self, open_window: WindowOpener, skybrush: SimpleNamespace) -> None:
        """
        Logging in stores the key and switches to the results view.

        GIVEN: The user is logged out
        WHEN: They log in with a valid API key
        THEN: The key is validated against their configuration directory
        AND: The results view is shown, the status confirms the login and the API version is fetched
        """
        window = open_window(logged_in=False)
        skybrush.api_client_class.login.return_value = skybrush.client
        on_done = MagicMock()

        assert window._start_login("new-key", on_done) is True
        finish(window._login_runner)

        skybrush.api_client_class.login.assert_called_once_with(skybrush.logged_out.config_dir, "new-key")
        on_done.assert_called_once_with(skybrush.client, None)
        assert window._client is skybrush.client
        assert window._results_row.winfo_manager() == "pack"
        assert window.status_label.cget("text") == "Logged in to the Skybrush Account"
        finish(window._auth_runner)
        assert window._version_label.cget("text") == "Skybrush API version: 1.2.3"

    def test_failed_login_keeps_the_user_logged_out(self, open_window: WindowOpener, skybrush: SimpleNamespace) -> None:
        """
        A rejected key leaves the window logged out.

        GIVEN: The user is logged out
        WHEN: They log in with a key the account rejects
        THEN: The error is passed to the form and the window stays logged out
        """
        window = open_window(logged_in=False)
        error = InvalidAPIKey("rejected", url=ACCOUNT_URL)
        skybrush.api_client_class.login.side_effect = error
        on_done = MagicMock()

        window._start_login("bad-key", on_done)
        finish(window._login_runner)

        on_done.assert_called_once_with(None, error)
        assert window._client is None
        assert window.status_label.cget("text") == ""

    def test_second_login_while_logging_in_is_refused(self, open_window: WindowOpener) -> None:
        """
        Only one login runs at a time.

        GIVEN: A login is already running
        WHEN: The user starts another one
        THEN: It is refused
        """
        window = open_window(logged_in=False)
        window._start_login("key", MagicMock())

        assert window._start_login("key", MagicMock()) is False
        finish(window._login_runner)

    def test_user_logs_out_and_the_key_is_removed(
        self, logged_in_window: SkybrushLogAnalysisWindow, skybrush: SimpleNamespace
    ) -> None:
        """
        Logging out removes the key and shows the login form.

        GIVEN: The user is logged in
        WHEN: They click Log out
        THEN: The stored key is removed and the window is logged out
        AND: The header asks the user to log in
        """
        logged_in_window._logout_button.invoke()

        skybrush.client.logout.assert_called_once()
        assert logged_in_window._client is None
        assert logged_in_window._version_info == {}
        assert logged_in_window._login_form.winfo_manager() == "pack"
        assert logged_in_window.status_label.cget("text") == "Logged out"
        assert logged_in_window._version_label.cget("text") == "Skybrush API version: requires logging in"
        assert logged_in_window._auth_status_label.cget("text") == (
            "Not logged in. Use the Log in button to configure the API key."
        )

    def test_user_is_logged_out_even_if_the_key_cannot_be_removed(
        self, logged_in_window: SkybrushLogAnalysisWindow, skybrush: SimpleNamespace, messagebox_mock: MagicMock
    ) -> None:
        """
        A configuration write error is reported, but the session still ends.

        GIVEN: The user is logged in
        WHEN: They log out and the stored key cannot be removed
        THEN: The error is shown and the window is logged out anyway
        """
        skybrush.client.logout.side_effect = ConfigError("read-only")

        logged_in_window._apply_logout()

        assert messagebox_mock.showerror.call_args == call(
            ANY,
            "Could not read or write the 'skybrush-log-analyzer' configuration: read-only",
            parent=logged_in_window.root,
        )
        assert logged_in_window._client is None

    def test_logout_without_a_session_does_nothing(self, open_window: WindowOpener, skybrush: SimpleNamespace) -> None:
        """
        Logging out twice is harmless.

        GIVEN: The user is logged out
        WHEN: A logout is requested
        THEN: No configuration is touched and the status is unchanged
        """
        window = open_window(logged_in=False)

        window._apply_logout()

        skybrush.client.logout.assert_not_called()
        assert window.status_label.cget("text") == ""

    def test_stale_version_check_restarts_for_the_current_session(
        self, open_window: WindowOpener, skybrush: SimpleNamespace
    ) -> None:
        """
        A version check of an old session triggers a check of the new one.

        GIVEN: The user logged in again while the previous session's version check was running
        WHEN: The old check completes
        THEN: Its result is ignored and the version of the new session is fetched
        """
        window = open_window(logged_in=True)
        new_client = make_client(skybrush.logged_in)
        new_client.version.return_value = {"app_version": "2.0.0"}
        window._client = new_client

        finish(window._auth_runner)
        assert window._version_label.cget("text") == "Fetching Skybrush API version..."
        finish(window._auth_runner)

        assert window._version_label.cget("text") == "Skybrush API version: 2.0.0"

    def test_stale_version_check_after_logout_is_ignored(self, open_window: WindowOpener) -> None:
        """
        A version check that finishes after logging out changes nothing.

        GIVEN: The user logged out while the version check was running
        WHEN: The check completes
        THEN: The window stays logged out and no new check starts
        """
        window = open_window(logged_in=True)
        window._apply_logout()

        finish(window._auth_runner)

        assert window._client is None
        assert not window._auth_runner.active
        assert window._version_label.cget("text") == "Skybrush API version: requires logging in"

    def test_version_check_is_retried_only_while_the_version_is_unknown(
        self, logged_in_window: SkybrushLogAnalysisWindow, skybrush: SimpleNamespace
    ) -> None:
        """
        A known API version is not fetched again.

        GIVEN: The API version is already known
        WHEN: A retry of the version check is requested
        THEN: No new check starts; once the version is unknown, a retry starts one
        """
        logged_in_window._retry_pending_version_check()
        assert not logged_in_window._auth_runner.active

        logged_in_window._version_info = {}
        logged_in_window._retry_pending_version_check()
        assert logged_in_window._auth_runner.active
        finish(logged_in_window._auth_runner)
        assert skybrush.client.version.call_count == 2

    def test_header_check_that_cannot_start_clears_the_status(self, logged_in_window: SkybrushLogAnalysisWindow) -> None:
        """
        A header check that cannot start does not show a stale status.

        GIVEN: A version check is already running
        WHEN: Another header check is requested
        THEN: The log-in status line is cleared
        """
        logged_in_window._version_info = {}
        logged_in_window._start_header_status_checks()

        logged_in_window._start_header_status_checks()

        assert logged_in_window._auth_status_label.cget("text") == ""
        assert str(logged_in_window._auth_status_label.cget("foreground")) == "gray50"
        finish(logged_in_window._auth_runner)


# ---------------- window: analysis ----------------


class TestAnalysis:
    """The user uploads the selected log and reads the analysis results."""

    def test_user_reads_the_analysis_results(
        self, logged_in_window: SkybrushLogAnalysisWindow, skybrush: SimpleNamespace, logfile: Path
    ) -> None:
        """
        A completed analysis shows notes, a status summary and every test result.

        GIVEN: The user is logged in with a log selected
        WHEN: They click Analyze and the analysis completes
        THEN: The selected log is uploaded and the results are shown
        AND: The status confirms the completed analysis
        """
        skybrush.client.analyze.return_value = {"view": sample_view()}

        logged_in_window._run_analysis_button.invoke()
        assert str(logged_in_window._run_analysis_button.cget("state")) == "disabled"
        assert logged_in_window.status_label.cget("text") == (
            "Uploading log and running analysis through the Skybrush API - this can take a while"
        )
        finish(logged_in_window._analysis_runner)

        skybrush.client.analyze.assert_called_once_with(logfile)
        assert results_of(logged_in_window) == (
            "Flight review\n"
            "Vibration needs attention.\n\n"
            "Test cases: WARN: 1, PASS: 2\n\n"
            "[WARN] vibration - Vibration levels\n"
            "    • Peak Z-axis vibration: 42.7 m/s/s\n"
            "    • Clipping events: 3\n"
            "\n"
            "[PASS] battery\n"
            "    • Battery fine\n"
            "\n"
        )
        assert logged_in_window.status_label.cget("text") == "Analysis completed"
        assert str(logged_in_window._run_analysis_button.cget("state")) == "normal"
        assert str(logged_in_window.results_text.cget("state")) == "disabled"

    def test_user_sees_results_colored_by_their_status(
        self, logged_in_window: SkybrushLogAnalysisWindow, skybrush: SimpleNamespace
    ) -> None:
        """
        Statuses and message severities are colored, and values are bold.

        GIVEN: An analysis with warnings, passes and informational messages
        WHEN: The results are shown
        THEN: Each line carries the tag of its status or severity, and values are bold
        """
        skybrush.client.analyze.return_value = {"view": sample_view()}
        logged_in_window._on_run_analysis_click()
        finish(logged_in_window._analysis_runner)
        text = logged_in_window.results_text

        assert tags_at_text(text, "Flight review") == ("heading",)
        assert set(tags_at_text(text, "Test cases:")) == {"summary"}
        assert set(tags_at_text(text, "WARN: 1")) == {"summary", "status_WARN"}
        assert set(tags_at_text(text, "PASS: 2")) == {"summary", "status_PASS"}
        assert tags_at_text(text, "[WARN] vibration") == ("status_WARN",)
        assert tags_at_text(text, "[PASS] battery") == ("status_PASS",)
        assert tags_at_text(text, "Peak Z-axis") == ("status_WARN",)
        assert set(tags_at_text(text, "42.7 m/s/s")) == {"status_WARN", "bold"}
        assert set(tags_at_text(text, "Clipping events")) == {"status_INFO"}
        assert tags_at_text(text, "Battery fine") == ("bullet",)
        assert str(text.tag_cget("status_WARN", "foreground")) == "dark orange"
        assert str(text.tag_cget("status_FAIL", "foreground")) == "red3"

    def test_user_sees_unknown_statuses_and_untitled_results_plainly(
        self, logged_in_window: SkybrushLogAnalysisWindow, skybrush: SimpleNamespace
    ) -> None:
        """
        Results without a known status, name or title are still listed.

        GIVEN: An analysis result with an unknown status and no title, plus one without a status
        WHEN: The results are shown
        THEN: Unknown statuses are muted and missing ones are shown as UNKNOWN, without a title separator
        """
        view = {
            "status_counts": {},
            "test_results": [
                {"status": "WEIRD", "test_name": "custom.check", "title": "", "messages": None},
                {"test_name": None},
            ],
        }
        skybrush.client.analyze.return_value = {"view": view}

        logged_in_window._on_run_analysis_click()
        finish(logged_in_window._analysis_runner)

        assert results_of(logged_in_window) == "[WEIRD] custom.check\n\n[UNKNOWN] \n\n"
        assert tags_at_text(logged_in_window.results_text, "[WEIRD]") == ("muted",)
        assert tags_at_text(logged_in_window.results_text, "[UNKNOWN]") == ("muted",)

    def test_user_is_told_when_the_analysis_has_no_test_results(
        self, logged_in_window: SkybrushLogAnalysisWindow, skybrush: SimpleNamespace
    ) -> None:
        """
        An empty analysis says so instead of showing nothing.

        GIVEN: The analysis returned no notes, counts or test results
        WHEN: The results are shown
        THEN: A muted note says that no test results were returned
        """
        skybrush.client.analyze.return_value = {"view": {"status_counts": {}, "test_results": []}}

        logged_in_window._on_run_analysis_click()
        finish(logged_in_window._analysis_runner)

        assert results_of(logged_in_window) == "No test results were returned by the analysis.\n"
        assert tags_at_text(logged_in_window.results_text, "No test results") == ("muted",)

    def test_user_is_told_when_the_log_file_is_missing(
        self, open_window: WindowOpener, tmp_path: Path, skybrush: SimpleNamespace, messagebox_mock: MagicMock
    ) -> None:
        """
        A log file deleted after selecting it is reported, not uploaded.

        GIVEN: The selected log no longer exists
        WHEN: The user clicks Analyze
        THEN: An error names the missing file and nothing is uploaded
        """
        missing = tmp_path / "gone.bin"
        window = open_window(logged_in=True, path=missing)
        finish(window._auth_runner)

        window._on_run_analysis_click()

        assert messagebox_mock.showerror.call_args == call(ANY, f"Log file not found: {missing}", parent=window.root)
        assert not window._analysis_runner.active
        skybrush.client.analyze.assert_not_called()

    def test_analyze_does_nothing_while_logged_out_or_already_running(
        self, logged_in_window: SkybrushLogAnalysisWindow, skybrush: SimpleNamespace
    ) -> None:
        """
        Analyses do not overlap and need a session.

        GIVEN: An analysis is running
        WHEN: The user requests another one, or requests one while logged out
        THEN: Only the first analysis is uploaded
        """
        skybrush.client.analyze.return_value = {"view": sample_view()}
        logged_in_window._on_run_analysis_click()
        logged_in_window._on_run_analysis_click()
        finish(logged_in_window._analysis_runner)

        logged_in_window._client = None
        logged_in_window._on_run_analysis_click()

        assert skybrush.client.analyze.call_count == 1
        assert not logged_in_window._analysis_runner.active

    def test_user_sees_why_the_analysis_failed(
        self, logged_in_window: SkybrushLogAnalysisWindow, skybrush: SimpleNamespace, messagebox_mock: MagicMock
    ) -> None:
        """
        A failed analysis is explained in the results and in a message box.

        GIVEN: The user is logged in
        WHEN: The analysis fails on the server
        THEN: The reason replaces the results and is shown in an error box, and the status is cleared
        AND: The user stays logged in
        """
        error = BadRequest("not an ArduPilot log")
        skybrush.client.analyze.side_effect = error

        logged_in_window._on_run_analysis_click()
        with patch(f"{MODULE}.logging_error") as log_error:
            finish(logged_in_window._analysis_runner)

        expected = "The Skybrush API rejected the request: not an ArduPilot log"
        assert results_of(logged_in_window) == expected + "\n"
        assert tags_at_text(logged_in_window.results_text, "The Skybrush API") == ("error",)
        assert messagebox_mock.showerror.call_args == call(ANY, expected, parent=logged_in_window.root)
        assert logged_in_window.status_label.cget("text") == ""
        assert logged_in_window._client is skybrush.client
        log_error.assert_called_once()
        assert log_error.call_args.args[1:] == (_LOG_TAG, error)

    def test_analysis_with_a_rejected_session_logs_the_user_out(
        self, logged_in_window: SkybrushLogAnalysisWindow, skybrush: SimpleNamespace
    ) -> None:
        """
        An analysis refused for a revoked key ends the session.

        GIVEN: The user's API key was revoked meanwhile
        WHEN: The analysis is refused
        THEN: The window is logged out
        """
        skybrush.client.analyze.side_effect = Unauthenticated()

        logged_in_window._on_run_analysis_click()
        finish(logged_in_window._analysis_runner)

        assert logged_in_window._client is None
        assert logged_in_window._login_form.winfo_manager() == "pack"

    def test_analysis_of_an_ended_session_is_discarded(
        self, logged_in_window: SkybrushLogAnalysisWindow, skybrush: SimpleNamespace
    ) -> None:
        """
        Results arriving after logging out are not shown.

        GIVEN: The user logged out while an analysis was running
        WHEN: The analysis completes
        THEN: The results are not shown
        """
        skybrush.client.analyze.return_value = {"view": sample_view()}
        logged_in_window._on_run_analysis_click()
        logged_in_window._apply_logout()

        finish(logged_in_window._analysis_runner)

        assert "Flight review" not in results_of(logged_in_window)
        assert logged_in_window.status_label.cget("text") == "Logged out"

    def test_successful_analysis_retries_an_unknown_api_version(
        self, logged_in_window: SkybrushLogAnalysisWindow, skybrush: SimpleNamespace
    ) -> None:
        """
        Reaching the server again fills in a version that failed to load.

        GIVEN: The API version could not be fetched earlier
        WHEN: An analysis completes successfully
        THEN: The version check is retried
        """
        logged_in_window._version_info = {}
        skybrush.client.analyze.return_value = {"view": sample_view()}

        logged_in_window._on_run_analysis_click()
        finish(logged_in_window._analysis_runner)

        assert logged_in_window._auth_runner.active
        finish(logged_in_window._auth_runner)
        assert logged_in_window._version_info == {"app_version": "1.2.3"}


# ---------------- window: find bar ----------------


@pytest.fixture
def window_with_results(logged_in_window: SkybrushLogAnalysisWindow, skybrush: SimpleNamespace) -> SkybrushLogAnalysisWindow:
    """A logged-in window showing analysis results that mention 'vibration' four times and 'battery' twice."""
    skybrush.client.analyze.return_value = {"view": sample_view()}
    logged_in_window._on_run_analysis_click()
    finish(logged_in_window._analysis_runner)
    return logged_in_window


def search(window: SkybrushLogAnalysisWindow, query: str) -> None:
    window._find_entry.delete(0, tk.END)
    window._find_entry.insert(0, query)
    window._on_find_query_changed(MagicMock())


def match_range(window: SkybrushLogAnalysisWindow, number: int) -> tuple[str, str]:
    """Return the normalized start and end index of the numbered match."""
    start, end = window._find_matches[number]
    return window.results_text.index(start), window.results_text.index(end)


def highlighted_texts(window: SkybrushLogAnalysisWindow) -> list[str]:
    """Return the text under each search highlight."""
    ranges = window.results_text.tag_ranges("search_all")
    return [window.results_text.get(start, end) for start, end in zip(ranges[::2], ranges[1::2], strict=True)]


def current_match(window: SkybrushLogAnalysisWindow) -> tuple[str, str]:
    ranges = window.results_text.tag_ranges("search_current")
    return str(ranges[0]), str(ranges[1])


class TestFindBar:
    """The user searches the analysis results like in a web browser."""

    def test_user_finds_all_occurrences_ignoring_case(self, window_with_results: SkybrushLogAnalysisWindow) -> None:
        """
        Ctrl-F highlights every match and selects the first one.

        GIVEN: Results that mention 'vibration' four times in different capitalization
        WHEN: The user opens the find bar and searches for 'VIBRATION'
        THEN: All four matches are highlighted, the first is current and selected, and the count is shown
        """
        window = window_with_results
        window._show_find_bar()
        assert window._find_bar.winfo_manager() == "pack"

        search(window, "VIBRATION")

        assert highlighted_texts(window) == ["Vibration", "vibration", "Vibration", "vibration"]
        assert window._find_count_label.cget("text") == "1/4"
        assert current_match(window) == match_range(window, 0)
        assert window.results_text.get(*current_match(window)) == "Vibration"
        assert tuple(str(index) for index in window.results_text.tag_ranges("sel")) == current_match(window)

    def test_user_steps_through_matches_with_wraparound(self, window_with_results: SkybrushLogAnalysisWindow) -> None:
        """
        Next and previous cycle through the matches.

        GIVEN: A search with four matches, the first one current
        WHEN: The user moves to the next and previous matches
        THEN: The current match moves accordingly and wraps around at both ends
        """
        window = window_with_results
        window._show_find_bar()
        search(window, "vibration")

        window._on_find_next_key(None)
        assert window._find_count_label.cget("text") == "2/4"
        window._jump_to_match(1)
        window._jump_to_match(1)
        assert window._find_count_label.cget("text") == "4/4"
        window._jump_to_match(1)
        assert window._find_count_label.cget("text") == "1/4"
        window._on_find_prev_key(None)
        assert window._find_count_label.cget("text") == "4/4"
        assert current_match(window) == match_range(window, 3)
        assert len(window.results_text.tag_ranges("search_current")) == 2
        assert tuple(str(index) for index in window.results_text.tag_ranges("sel")) == current_match(window)

    def test_user_is_told_when_nothing_matches(self, window_with_results: SkybrushLogAnalysisWindow) -> None:
        """
        A search without matches says so.

        GIVEN: The find bar is open
        WHEN: The user searches for text that is not in the results
        THEN: 'No matches' is shown and nothing is highlighted
        """
        window = window_with_results
        window._show_find_bar()

        search(window, "propeller")

        assert window._find_count_label.cget("text") == "No matches"
        assert window.results_text.tag_ranges("search_all") == ()
        window._jump_to_match(1)
        assert window._find_count_label.cget("text") == "No matches"

    def test_clearing_the_query_removes_the_highlights(self, window_with_results: SkybrushLogAnalysisWindow) -> None:
        """
        An empty query highlights nothing.

        GIVEN: A search with highlighted matches
        WHEN: The user clears the query
        THEN: All highlights and the count disappear
        """
        window = window_with_results
        window._show_find_bar()
        search(window, "vibration")

        search(window, "")

        assert window.results_text.tag_ranges("search_all") == ()
        assert window.results_text.tag_ranges("search_current") == ()
        assert window._find_count_label.cget("text") == ""
        assert window._find_matches == []

    def test_key_release_without_a_query_change_keeps_the_current_match(
        self, window_with_results: SkybrushLogAnalysisWindow
    ) -> None:
        """
        Releasing F3 or arrow keys does not restart the search.

        GIVEN: The user moved to the second match
        WHEN: A key is released without changing the query
        THEN: The second match stays current
        """
        window = window_with_results
        window._show_find_bar()
        search(window, "vibration")
        window._jump_to_match(1)

        window._on_find_query_changed(MagicMock())

        assert window._find_count_label.cget("text") == "2/4"

    def test_new_results_keep_highlights_without_jumping_to_a_match(
        self, window_with_results: SkybrushLogAnalysisWindow
    ) -> None:
        """
        Re-rendered results are searched again without moving the view.

        GIVEN: The find bar is open and the user moved to the second match
        WHEN: The analysis is run again and the results are redrawn
        THEN: All matches in the new results are highlighted again
        AND: No match is selected, so the results stay scrolled to the top
        AND: The next F3 press starts again from the first match
        """
        window = window_with_results
        window._show_find_bar()
        search(window, "vibration")
        window._jump_to_match(1)

        window._on_run_analysis_click()
        finish(window._analysis_runner)

        assert len(window._find_matches) == 4
        assert [text.lower() for text in highlighted_texts(window)] == ["vibration"] * 4
        assert window.results_text.tag_ranges("search_current") == ()
        assert window.results_text.tag_ranges("sel") == ()
        assert window._find_index == -1
        assert window._find_count_label.cget("text") == ""
        window._on_find_next_key(None)
        assert window._find_count_label.cget("text") == "1/4"
        assert current_match(window) == match_range(window, 0)

    def test_reopening_the_find_bar_repeats_the_previous_search(self, window_with_results: SkybrushLogAnalysisWindow) -> None:
        """
        Ctrl-F after closing the find bar picks up the previous query.

        GIVEN: The user searched for 'battery' and closed the find bar
        WHEN: They press Ctrl-F again
        THEN: The previous query is selected, so typing replaces it
        AND: The first match is current again
        """
        window = window_with_results
        window._show_find_bar()
        search(window, "battery")
        window._jump_to_match(1)
        window._hide_find_bar()

        window._show_find_bar()

        assert window._find_entry.selection_present()
        assert (window._find_entry.index("sel.first"), window._find_entry.index("sel.last")) == (0, len("battery"))
        assert window._find_count_label.cget("text") == "1/2"
        assert current_match(window) == match_range(window, 0)

    def test_user_closes_the_find_bar_with_escape(self, window_with_results: SkybrushLogAnalysisWindow) -> None:
        """
        Escape hides the find bar and its highlights.

        GIVEN: The find bar is open with highlighted matches
        WHEN: The user presses Escape
        THEN: The find bar disappears together with all highlights
        """
        window = window_with_results
        window._show_find_bar()
        search(window, "vibration")

        window._on_escape_key(None)

        assert window._find_bar.winfo_manager() == ""
        assert not window._find_bar_visible
        assert window.results_text.tag_ranges("search_all") == ()
        assert window.results_text.tag_ranges("sel") == ()
        assert window._find_index == -1

    def test_find_keys_do_nothing_while_the_find_bar_is_hidden(self, window_with_results: SkybrushLogAnalysisWindow) -> None:
        """
        F3, Shift-F3 and Escape only act on an open find bar.

        GIVEN: The user searched and then closed the find bar
        WHEN: They press F3, Shift-F3 or Escape
        THEN: No match is selected and the find bar stays hidden
        """
        window = window_with_results
        window._show_find_bar()
        search(window, "vibration")
        window._hide_find_bar()
        window._find_matches = [("1.0", "1.5")]

        window._on_find_next_key(None)
        window._on_find_prev_key(None)
        window._on_escape_key(None)

        assert window._find_index == -1
        assert window._find_bar.winfo_manager() == ""

    def test_find_bar_is_not_available_while_logged_out(self, open_window: WindowOpener) -> None:
        """
        There are no results to search while logged out.

        GIVEN: The user is logged out
        WHEN: They press Ctrl-F
        THEN: The find bar does not open
        """
        window = open_window(logged_in=False)

        window._show_find_bar()

        assert not window._find_bar_visible
        assert window._find_bar.winfo_manager() == ""

    def test_matches_are_refreshed_when_new_results_arrive(
        self, window_with_results: SkybrushLogAnalysisWindow, skybrush: SimpleNamespace
    ) -> None:
        """
        An open search follows the newly displayed results.

        GIVEN: The find bar is open with a search for 'battery'
        WHEN: A new analysis without any battery result is shown
        THEN: The search reports that nothing matches anymore
        """
        window = window_with_results
        window._show_find_bar()
        search(window, "battery")
        assert window._find_count_label.cget("text") == "1/2"
        skybrush.client.analyze.return_value = {"view": {"status_counts": {}, "test_results": []}}

        window._on_run_analysis_click()
        finish(window._analysis_runner)

        assert window._find_count_label.cget("text") == "No matches"

    def test_logging_out_closes_the_find_bar(self, window_with_results: SkybrushLogAnalysisWindow) -> None:
        """
        The find bar disappears together with the results when logging out.

        GIVEN: The find bar is open
        WHEN: The user logs out
        THEN: The find bar is hidden
        """
        window = window_with_results
        window._show_find_bar()

        window._apply_logout()

        assert not window._find_bar_visible
        assert window._find_bar.winfo_manager() == ""


# ---------------- window: web analyzer and help ----------------


class TestBrowserLinks:
    """The user opens the web analyzer and the user manual in the browser."""

    def test_user_opens_this_logs_analysis_in_the_web_analyzer(
        self,
        logged_in_window: SkybrushLogAnalysisWindow,
        skybrush: SimpleNamespace,
        browser_mock: MagicMock,
        logfile: Path,
    ) -> None:
        """
        The web analyzer opens logged in, on the analysis of the selected log.

        GIVEN: The user is logged in with a log selected
        WHEN: They click Open in Skybrush Log Analyzer
        THEN: A log-in link deep-linking to this log's analysis opens in the browser
        """
        logged_in_window._open_web_button.invoke()
        assert str(logged_in_window._open_web_button.cget("state")) == "disabled"
        assert logged_in_window.status_label.cget("text") == (
            "Requesting a log-in link for the Skybrush Log Analyzer web application"
        )
        finish(logged_in_window._web_login_runner)

        skybrush.client.get_analysis_view_intent.assert_called_once_with(logfile)
        skybrush.client.get_web_login_url.assert_called_once_with(intent="view-intent")
        browser_mock.assert_called_once_with("https://logs.example.test/sso?token=abc")
        assert logged_in_window.status_label.cget("text") == "Skybrush Log Analyzer opened in the default browser"
        assert str(logged_in_window._open_web_button.cget("state")) == "normal"

    def test_web_analyzer_opens_its_overview_for_a_log_without_stored_analysis(
        self, logged_in_window: SkybrushLogAnalysisWindow, skybrush: SimpleNamespace
    ) -> None:
        """
        A log that was never analyzed opens the generic analyzer view.

        GIVEN: The account has no stored analysis of the selected log
        WHEN: The user opens the web analyzer
        THEN: A log-in link without a deep link is requested
        """
        skybrush.client.get_analysis_view_intent.side_effect = NotFound("no analysis")

        logged_in_window._on_open_in_browser_click()
        finish(logged_in_window._web_login_runner)

        skybrush.client.get_web_login_url.assert_called_once_with(intent=None)

    def test_user_is_told_when_no_browser_can_be_opened(
        self, logged_in_window: SkybrushLogAnalysisWindow, browser_mock: MagicMock, messagebox_mock: MagicMock
    ) -> None:
        """
        A missing default browser is reported.

        GIVEN: No default web browser is available
        WHEN: The user opens the web analyzer
        THEN: An error says the browser could not be opened
        """
        browser_mock.return_value = False

        logged_in_window._on_open_in_browser_click()
        finish(logged_in_window._web_login_runner)

        assert messagebox_mock.showerror.call_args == call(
            ANY, "Could not open the default web browser.", parent=logged_in_window.root
        )

    def test_user_sees_why_the_web_login_link_failed(
        self,
        logged_in_window: SkybrushLogAnalysisWindow,
        skybrush: SimpleNamespace,
        browser_mock: MagicMock,
        messagebox_mock: MagicMock,
    ) -> None:
        """
        A failure to get the log-in link is explained.

        GIVEN: The user is logged in
        WHEN: The log-in link cannot be acquired because the key was revoked
        THEN: The reason is shown, no browser opens and the user is logged out
        """
        error = InvalidAPIKey("revoked", url=ACCOUNT_URL)
        skybrush.client.get_web_login_url.side_effect = error

        logged_in_window._on_open_in_browser_click()
        with patch(f"{MODULE}.logging_error") as log_error:
            finish(logged_in_window._web_login_runner)

        assert messagebox_mock.showerror.call_args == call(
            ANY,
            _skybrush_error_message(InvalidAPIKey("revoked", url=ACCOUNT_URL)),
            parent=logged_in_window.root,
        )
        browser_mock.assert_not_called()
        assert logged_in_window._client is None
        log_error.assert_called_once()
        assert log_error.call_args.args[1:] == (_LOG_TAG, error)

    def test_user_can_retry_after_the_web_login_link_was_unavailable(
        self, logged_in_window: SkybrushLogAnalysisWindow, skybrush: SimpleNamespace, browser_mock: MagicMock
    ) -> None:
        """
        A temporary server problem does not end the session.

        GIVEN: The user is logged in
        WHEN: The log-in link cannot be acquired because the server is unavailable
        THEN: The progress status is cleared, no browser opens and the user stays logged in
        """
        skybrush.client.get_web_login_url.side_effect = ServerError()
        logged_in_window._on_open_in_browser_click()
        assert logged_in_window.status_label.cget("text") != ""

        with patch(f"{MODULE}.logging_error"):
            finish(logged_in_window._web_login_runner)

        assert logged_in_window.status_label.cget("text") == ""
        browser_mock.assert_not_called()
        assert logged_in_window._client is skybrush.client

    def test_web_login_link_of_an_ended_session_is_not_opened(
        self, logged_in_window: SkybrushLogAnalysisWindow, browser_mock: MagicMock
    ) -> None:
        """
        A link that arrives after logging out is discarded.

        GIVEN: The user logged out while the log-in link was being requested
        WHEN: The link arrives
        THEN: The browser is not opened
        """
        logged_in_window._on_open_in_browser_click()
        logged_in_window._apply_logout()

        finish(logged_in_window._web_login_runner)

        browser_mock.assert_not_called()

    def test_web_analyzer_requests_do_not_overlap_and_need_a_session(
        self, logged_in_window: SkybrushLogAnalysisWindow, skybrush: SimpleNamespace
    ) -> None:
        """
        Only one log-in link is requested at a time, and only while logged in.

        GIVEN: A log-in link is being requested
        WHEN: The user clicks again, or clicks while logged out
        THEN: Only one link is requested
        """
        logged_in_window._on_open_in_browser_click()
        logged_in_window._on_open_in_browser_click()
        finish(logged_in_window._web_login_runner)
        logged_in_window._client = None
        logged_in_window._on_open_in_browser_click()

        assert skybrush.client.get_web_login_url.call_count == 1
        assert not logged_in_window._web_login_runner.active

    def test_user_opens_the_user_manual_with_help(
        self, logged_in_window: SkybrushLogAnalysisWindow, browser_mock: MagicMock
    ) -> None:
        """
        Help opens the Skybrush Log Analysis user manual.

        GIVEN: The Skybrush Log Analysis window is open
        WHEN: The user clicks Help
        THEN: The user manual page opens in the browser
        """
        logged_in_window._help_button.invoke()

        browser_mock.assert_called_once_with(MANUAL_URL)


# ---------------- window: feedback ----------------


class TestFeedbackSending:
    """The user sends feedback about the analysis to the Skybrush team."""

    def test_feedback_carries_the_log_and_version_details(
        self, logged_in_window: SkybrushLogAnalysisWindow, skybrush: SimpleNamespace, logfile: Path
    ) -> None:
        """
        Submitted feedback identifies the log and the software versions.

        GIVEN: The user is logged in with a log selected and a known API version
        WHEN: They submit feedback
        THEN: The description is sent with the AMC version, log name, log hash and API version appended
        AND: The result is passed back to the dialog
        """
        on_done = MagicMock()

        started = logged_in_window._start_suggestion("test_case", "Missing check", "Please add a GPS glitch test.", on_done)
        assert started is True
        assert str(logged_in_window._feedback_button.cget("state")) == "disabled"
        finish(logged_in_window._feedback_runner)

        expected_content = "\n".join(
            [
                "Please add a GPS glitch test.",
                "",
                "---",
                f"ArduPilot Methodic Configurator {__version__}",
                f"Flight log: {logfile.name}",
                f"Log file SHA-256: {hashlib.sha256(logfile.read_bytes()).hexdigest()}",
                "Skybrush API version: 1.2.3",
            ]
        )
        skybrush.client.suggest.assert_called_once_with(category="test_case", title="Missing check", content=expected_content)
        on_done.assert_called_once_with({"id": 42}, None)
        assert str(logged_in_window._feedback_button.cget("state")) == "normal"

    def test_feedback_without_a_log_file_or_version_omits_those_details(
        self, open_window: WindowOpener, tmp_path: Path, skybrush: SimpleNamespace
    ) -> None:
        """
        Details that are not available are left out.

        GIVEN: The selected log no longer exists and the API version is unknown
        WHEN: The user submits feedback
        THEN: Only the description and the AMC version are sent
        """
        skybrush.client.version.side_effect = ServerError()
        window = open_window(logged_in=True, path=tmp_path / "gone.bin")
        with patch(f"{MODULE}.logging_error"):
            finish(window._auth_runner)

        window._start_suggestion("other", "Hello", "Nice tool.", MagicMock())
        finish(window._feedback_runner)

        assert skybrush.client.suggest.call_args.kwargs["content"] == (
            f"Nice tool.\n\n---\nArduPilot Methodic Configurator {__version__}"
        )

    def test_feedback_omits_the_hash_of_an_unreadable_log(
        self, logged_in_window: SkybrushLogAnalysisWindow, skybrush: SimpleNamespace, logfile: Path
    ) -> None:
        """
        A log that cannot be read is named but not hashed.

        GIVEN: The selected log cannot be read
        WHEN: The user submits feedback
        THEN: The log name is sent without its hash
        """
        with patch(f"{MODULE}.calculate_file_hash", side_effect=OSError("locked")):
            logged_in_window._start_suggestion("bug", "Title", "Text.", MagicMock())
            finish(logged_in_window._feedback_runner)

        content = skybrush.client.suggest.call_args.kwargs["content"]
        assert f"Flight log: {logfile.name}" in content
        assert "SHA-256" not in content

    def test_feedback_after_the_session_ended_reports_not_logged_in(
        self, logged_in_window: SkybrushLogAnalysisWindow, skybrush: SimpleNamespace
    ) -> None:
        """
        Submitting without a session is reported back to the dialog.

        GIVEN: The session ended while the feedback dialog was open
        WHEN: The user submits feedback
        THEN: The dialog is told the user is not logged in, and nothing is sent
        """
        logged_in_window._apply_logout()
        on_done = MagicMock()

        started = logged_in_window._start_suggestion("bug", "Title", "Text.", on_done)

        assert started is False
        (result, error), _kwargs = on_done.call_args
        assert result is None
        assert isinstance(error, Unauthenticated)
        skybrush.client.suggest.assert_not_called()

    def test_only_one_feedback_is_sent_at_a_time(
        self, logged_in_window: SkybrushLogAnalysisWindow, skybrush: SimpleNamespace
    ) -> None:
        """
        A second submission while one is being sent is refused.

        GIVEN: Feedback is being sent
        WHEN: Another submission is requested
        THEN: It is refused without reporting an error
        """
        logged_in_window._start_suggestion("bug", "First", "Text.", MagicMock())
        second_done = MagicMock()

        assert logged_in_window._start_suggestion("bug", "Second", "Text.", second_done) is False
        finish(logged_in_window._feedback_runner)

        second_done.assert_not_called()
        assert skybrush.client.suggest.call_count == 1

    def test_feedback_rejected_for_a_revoked_key_logs_the_user_out(
        self, logged_in_window: SkybrushLogAnalysisWindow, skybrush: SimpleNamespace
    ) -> None:
        """
        Feedback refused for a revoked key ends the session.

        GIVEN: The user's API key was revoked meanwhile
        WHEN: Their feedback is refused
        THEN: The error is passed to the dialog and the window is logged out
        """
        error = InvalidAPIKey("revoked", url=ACCOUNT_URL)
        skybrush.client.suggest.side_effect = error
        on_done = MagicMock()

        logged_in_window._start_suggestion("bug", "Title", "Text.", on_done)
        finish(logged_in_window._feedback_runner)

        on_done.assert_called_once_with(None, error)
        assert logged_in_window._client is None

    def test_sent_feedback_retries_an_unknown_api_version(
        self, logged_in_window: SkybrushLogAnalysisWindow, skybrush: SimpleNamespace
    ) -> None:
        """
        Reaching the server again fills in a version that failed to load.

        GIVEN: The API version could not be fetched earlier
        WHEN: Feedback is delivered
        THEN: The version check is retried
        """
        logged_in_window._version_info = {}

        logged_in_window._start_suggestion("bug", "Title", "Text.", MagicMock())
        finish(logged_in_window._feedback_runner)

        assert logged_in_window._auth_runner.active
        finish(logged_in_window._auth_runner)
        assert skybrush.client.version.call_count == 2

    def test_feedback_result_of_an_ended_session_changes_nothing_else(
        self, logged_in_window: SkybrushLogAnalysisWindow, skybrush: SimpleNamespace
    ) -> None:
        """
        A feedback result arriving after logging out only reaches the dialog.

        GIVEN: The user logged out while feedback was being sent
        WHEN: The server rejects it for the old session
        THEN: The dialog gets the result, and the logged-out window starts no checks
        """
        skybrush.client.suggest.side_effect = Unauthenticated()
        on_done = MagicMock()
        logged_in_window._start_suggestion("bug", "Title", "Text.", on_done)
        logged_in_window._apply_logout()

        finish(logged_in_window._feedback_runner)

        on_done.assert_called_once()
        assert not logged_in_window._auth_runner.active
        assert logged_in_window.status_label.cget("text") == "Logged out"

    def test_user_opens_the_feedback_dialog(self, logged_in_window: SkybrushLogAnalysisWindow) -> None:
        """
        Send feedback opens the dialog connected to this window.

        GIVEN: The user is logged in
        WHEN: They click Send feedback
        THEN: The feedback dialog opens and submits through this window
        """
        with patch(f"{MODULE}.FeedbackDialog") as dialog_class:
            logged_in_window._feedback_button.invoke()

        dialog_class.assert_called_once_with(logged_in_window.root, logged_in_window._start_suggestion)
        dialog_class.return_value.show.assert_called_once()


# ---------------- window layout and wiring ----------------


def fire_binding(widget: tk.Misc, sequence: str) -> None:
    """Run the Python callback bound to an event sequence, as Tk would when the event occurs."""
    script = widget.bind(sequence)
    assert script, f"{sequence} is not bound"
    match = re.search(r"\[(.+?)\]", script)
    assert match is not None
    command, *fields = match.group(1).split()
    widget.tk.call(command, *(str(widget) if field == "%W" else "0" for field in fields))


class TestWindowControls:
    """The window's buttons and keyboard shortcuts trigger their actions."""

    def test_open_in_browser_button_requests_a_log_in_link(self, logged_in_window: SkybrushLogAnalysisWindow) -> None:
        """
        The web analyzer button starts the log-in link request.

        GIVEN: The user is logged in
        WHEN: They click 'Open in Skybrush Log Analyzer'
        THEN: A log-in link is requested in the background
        """
        logged_in_window._open_web_button.invoke()

        assert logged_in_window._web_login_runner.active
        finish(logged_in_window._web_login_runner)

    def test_new_results_are_shown_from_the_top(
        self, logged_in_window: SkybrushLogAnalysisWindow, skybrush: SimpleNamespace
    ) -> None:
        """
        A long result list starts at its beginning.

        GIVEN: An analysis with many test results
        WHEN: The results are shown
        THEN: The view starts at the top of the results
        """
        view = sample_view()
        view["test_results"] = [{"status": "PASS", "test_name": f"test_{index}"} for index in range(80)]
        skybrush.client.analyze.return_value = {"view": view}

        logged_in_window._on_run_analysis_click()
        finish(logged_in_window._analysis_runner)

        assert logged_in_window.results_text.yview()[0] == 0.0
        assert logged_in_window.results_text.yview()[1] < 1.0

    def test_keyboard_shortcuts_control_the_find_bar(self, window_with_results: SkybrushLogAnalysisWindow) -> None:
        """
        Browser-like shortcuts open, step through and close the search.

        GIVEN: Results are shown
        WHEN: The user presses Ctrl-F, types a query, presses F3, Shift-F3 and Escape
        THEN: The find bar opens, moves to the next and previous match, and closes
        """
        window = window_with_results

        fire_binding(window.root, "<Control-f>")
        assert window._find_bar_visible
        search(window, "vibration")
        fire_binding(window.root, "<F3>")
        assert window._find_count_label.cget("text") == "2/4"
        fire_binding(window.root, "<Shift-F3>")
        assert window._find_count_label.cget("text") == "1/4"
        fire_binding(window.root, "<Escape>")
        assert not window._find_bar_visible

    def test_find_field_keys_and_buttons_navigate_matches(self, window_with_results: SkybrushLogAnalysisWindow) -> None:
        """
        The find field and its buttons work like in a web browser.

        GIVEN: The find bar is open and the user typed a query
        WHEN: They press Enter, Shift-Enter, the arrow buttons and finally Escape or the close button
        THEN: The current match moves forward and back, and the find bar closes
        """
        window = window_with_results
        window._show_find_bar()
        window._find_entry.insert(0, "vibration")
        fire_binding(window._find_entry, "<KeyRelease>")
        assert window._find_count_label.cget("text") == "1/4"

        fire_binding(window._find_entry, "<Return>")
        assert window._find_count_label.cget("text") == "2/4"
        fire_binding(window._find_entry, "<Shift-Return>")
        assert window._find_count_label.cget("text") == "1/4"
        find_button(window._find_bar, "↓").invoke()
        assert window._find_count_label.cget("text") == "2/4"
        find_button(window._find_bar, "↑").invoke()
        assert window._find_count_label.cget("text") == "1/4"
        fire_binding(window._find_entry, "<Escape>")
        assert not window._find_bar_visible
        window._show_find_bar()
        find_button(window._find_bar, "✕").invoke()
        assert not window._find_bar_visible

    def test_close_button_closes_the_window(self, logged_in_window: SkybrushLogAnalysisWindow) -> None:
        """
        Close closes the window.

        GIVEN: The window is open
        WHEN: The user clicks Close
        THEN: The window closes
        """
        find_button(logged_in_window.root, "Close").invoke()

        assert not logged_in_window.root.winfo_exists()


# ---------------- opening the window from the parameter editor ----------------


class TestOpeningTheAnalysisWindow:
    """The parameter editor opens an analysis window for each selected log."""

    @pytest.mark.parametrize(
        "error",
        [PermissionError("Permission denied: 'config.toml'"), ConfigError("Permission denied: 'config.toml'")],
    )
    @pytest.mark.usefixtures("open_window")
    def test_user_is_told_when_the_configuration_cannot_be_read(
        self,
        root: tk.Tk,
        skybrush: SimpleNamespace,
        messagebox_mock: MagicMock,
        logfile: Path,
        error: Exception,
    ) -> None:
        """
        An unreadable configuration is reported instead of crashing.

        GIVEN: The Skybrush configuration file cannot be read
        WHEN: The user selects a log to analyze
        THEN: A localized error explains the problem and no window opens
        """
        skybrush.config_load.side_effect = error
        toplevels_before = len(root.winfo_children())

        with patch(f"{MODULE}.logging_error") as log_error:
            window = open_skybrush_log_analysis(root, str(logfile))

        assert window is None
        assert messagebox_mock.showerror.call_args.args[1] == (
            "Could not read or write the 'skybrush-log-analyzer' configuration: Permission denied: 'config.toml'"
        )
        assert messagebox_mock.showerror.call_args.kwargs["parent"] is root
        assert len(root.winfo_children()) == toplevels_before
        assert log_error.call_args.args[1:] == (_LOG_TAG, error)

    @pytest.mark.usefixtures("open_window")
    def test_user_opens_the_analysis_window_for_the_selected_log(
        self,
        root: tk.Tk,
        skybrush: SimpleNamespace,
        logfile: Path,
    ) -> None:
        """
        The first selected log opens the analysis window.

        GIVEN: No analysis window is open
        WHEN: The user selects a log to analyze
        THEN: A window opens for that log and becomes the open analysis window
        """
        skybrush.config_load.return_value = skybrush.logged_in

        window = open_skybrush_log_analysis(root, str(logfile))
        assert window is not None
        skybrush.windows.append(window)

        assert window.logfile == str(logfile)
        finish(window._auth_runner)

    @pytest.mark.usefixtures("open_window")
    def test_user_can_analyze_several_logs_side_by_side(
        self, root: tk.Tk, skybrush: SimpleNamespace, logfile: Path, tmp_path: Path
    ) -> None:
        """
        Every selected log opens its own window.

        GIVEN: An analysis window is already open for one log
        WHEN: The user selects another log to analyze
        THEN: A second window opens for it, and the first one keeps its log
        """
        skybrush.config_load.return_value = skybrush.logged_in
        other_log = tmp_path / "flight_00043.bin"

        first = open_skybrush_log_analysis(root, str(logfile))
        second = open_skybrush_log_analysis(root, str(other_log))
        assert first is not None
        assert second is not None
        skybrush.windows.extend([first, second])

        assert second is not first
        assert first.root.winfo_exists()
        assert (first.logfile, second.logfile) == (str(logfile), str(other_log))
        finish(first._auth_runner)
        finish(second._auth_runner)
