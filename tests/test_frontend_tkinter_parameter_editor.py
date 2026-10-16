#!/usr/bin/env python3

"""
Behaviour-driven tests for the parameter editor window.

Many fixtures are configured in the tests/conftest.py file.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import re
import threading
import tkinter as tk
from contextlib import contextmanager, nullcontext
from functools import partial
from sys import platform as sys_platform
from threading import Event, get_ident
from tkinter import font as tkfont
from tkinter import ttk
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
from unittest.mock import ANY, MagicMock, patch
from unittest.mock import call as mock_call

import pytest

import ardupilot_methodic_configurator.frontend_tkinter_parameter_editor as parameter_editor_module
from ardupilot_methodic_configurator.backend_filesystem import Par
from ardupilot_methodic_configurator.backend_flightcontroller_reconnect import FlightControllerReconnect
from ardupilot_methodic_configurator.data_model_ardupilot_parameter import ArduPilotParameter
from ardupilot_methodic_configurator.data_model_parameter_editor import LogAnalysisInputs, ParameterEditor
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_connection_recovery import (
    ConnectionRecovery,
    RecoveryCallbacks,
    RecoveryState,
)
from ardupilot_methodic_configurator.frontend_tkinter_navigation_lock import NavigationLock
from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor import (
    ParameterEditorAction,
    ParameterEditorUiServices,
    ParameterEditorWindow,
)
from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table import ParameterEditorTable
from ardupilot_methodic_configurator.frontend_tkinter_scroll_frame import ScrollFrame
from ardupilot_methodic_configurator.frontend_tkinter_show import MonitorBounds
from ardupilot_methodic_configurator.frontend_tkinter_stage_progress import StageProgressBar
from ardupilot_methodic_configurator.log_analysis.data_model_log_data import LogData
from ardupilot_methodic_configurator.plugins.data_model_accelerometer_calibration import AccelerometerCalibrationDataModel
from ardupilot_methodic_configurator.plugins.data_model_ahrs_orientation import AhrsOrientationDataModel
from ardupilot_methodic_configurator.plugins.data_model_autotune_gain_backoff import AutotuneGainBackoffDataModel
from ardupilot_methodic_configurator.plugins.frontend_tkinter_accelerometer_calibration import AccelerometerCalibrationView
from ardupilot_methodic_configurator.plugins.frontend_tkinter_ahrs_orientation import AhrsOrientationView
from ardupilot_methodic_configurator.plugins.frontend_tkinter_autotune_gain_backoff import AutotuneGainBackoffView
from ardupilot_methodic_configurator.plugins.plugin_constants import (
    PLUGIN_AHRS_ORIENTATION,
    PLUGIN_AUTOTUNE_GAIN_BACKOFF,
    PLUGIN_RC_CALIBRATION,
)
from ardupilot_methodic_configurator.plugins.plugin_factory import PluginFactory
from ardupilot_methodic_configurator.plugins.plugin_protocol import PluginPauseReason

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Iterator

    from ardupilot_methodic_configurator.plugins.plugin_protocol import PluginView

# pylint: disable=too-many-lines, redefined-outer-name, protected-access

# ============================== SHARED FIXTURES ==============================


def _wait_for_layout(window: tk.Toplevel, ready: Callable[[], bool]) -> None:
    """Let Windows deliver geometry events, with a deadline so broken layouts still fail."""
    completed = tk.BooleanVar(master=window, value=False)
    poll_job: str | None = None

    def check() -> None:
        nonlocal poll_job
        if ready():
            completed.set(True)
        else:
            poll_job = window.after(10, check)

    timeout_job = window.after(2000, lambda: completed.set(False))
    # Always service the event queue before sampling newly mapped child geometry.
    poll_job = window.after(0, check)
    try:
        window.wait_variable(completed)
        assert completed.get(), "Window geometry did not settle before the layout check"
    finally:
        window.after_cancel(timeout_job)
        if poll_job is not None:
            window.after_cancel(poll_job)


def _set_layout_dpi(root: tk.Tk, dpi: int) -> None:
    """Set DPI before creating widgets and refresh fonts cached by the shared Tk root."""
    root.tk.call("tk", "scaling", dpi / 72)
    for name in tkfont.names(root):
        if name.startswith("Tk"):
            tkfont.nametofont(name, root=root).configure(family="Arial", size=10)


@contextmanager
def _layout_display(root: tk.Tk, dpi: int = 96) -> Generator[tk.Tk, None, None]:
    """Give fixed-pixel scenarios explicit fonts, DPI and theme, without leaking them."""
    original_scaling = float(root.tk.call("tk", "scaling"))
    fonts = {name: tkfont.nametofont(name, root=root) for name in tkfont.names(root) if name.startswith("Tk")}
    original_fonts = {name: font.configure() for name, font in fonts.items()}
    style = ttk.Style(root)
    original_theme = style.theme_use()
    try:
        style.theme_use("alt")
        _set_layout_dpi(root, dpi)
        root.update_idletasks()
        yield root
    finally:
        root.tk.call("tk", "scaling", original_scaling)
        for name, font in fonts.items():
            original_font = original_fonts[name]
            assert original_font is not None
            font.configure(**original_font)
        style.theme_use(original_theme)
        root.update_idletasks()


@pytest.fixture
def layout_root(root: tk.Tk) -> Iterator[tk.Tk]:
    """Match fixed-pixel windows to 96 DPI; individual scenarios may select another DPI."""
    with _layout_display(root) as configured_root:
        yield configured_root


def _configure_root_stubs(root: MagicMock) -> None:
    root.quit = MagicMock()
    root.after = MagicMock()
    root.wait_window = MagicMock()
    root.winfo_rootx = MagicMock(return_value=0)
    root.winfo_rooty = MagicMock(return_value=0)
    root.winfo_width = MagicMock(return_value=800)
    root.winfo_height = MagicMock(return_value=600)
    root.winfo_x = MagicMock(return_value=0)
    root.winfo_y = MagicMock(return_value=0)
    root.geometry = MagicMock(return_value="800x600+0+0")
    root.state = MagicMock(return_value="normal")
    root.attributes = MagicMock(return_value=0)
    root.tk.getboolean.side_effect = lambda value: str(value).lower() in ("1", "true")


def _build_parameter_area_container() -> MagicMock:
    container = MagicMock()
    container.destroy = MagicMock()
    container.pack = MagicMock()
    container.winfo_children = MagicMock(return_value=[])
    container.cget.return_value = 0
    return container


def _configure_layout_stubs(editor: ParameterEditorWindow) -> None:
    """Supply numeric widget dimensions when the widget factory is stubbed out."""
    if not hasattr(editor, "main_frame"):
        editor.main_frame = MagicMock()
    main_frame = cast("MagicMock", editor.main_frame)
    main_frame.winfo_children = MagicMock(return_value=[])
    main_frame.winfo_height = MagicMock(return_value=600)
    editor.parameter_area_container = _build_parameter_area_container()


def _create_editor(parameter_editor: MagicMock) -> ParameterEditorWindow:  # noqa: PLR0915, RUF100 # pylint: disable=too-many-statements
    editor = ParameterEditorWindow.__new__(ParameterEditorWindow)
    editor.navigation_lock = NavigationLock()
    editor._connection_recovery = None
    editor.parameter_editor = parameter_editor
    editor.root = MagicMock()
    _configure_root_stubs(editor.root)
    editor.dpi_scaling_factor = 1.0
    editor.gui_complexity = "normal"
    editor.stage_progress_bar = MagicMock()
    editor.documentation_frame = MagicMock()
    editor.documentation_frame.get_auto_open_documentation_in_browser.return_value = False
    editor.documentation_frame.refresh_documentation_labels = MagicMock()
    editor.documentation_frame.update_why_why_now_tooltip = MagicMock()
    editor.parameter_editor_table = MagicMock()
    editor.parameter_editor_table.bitmask_editor_open = False
    editor.parameter_editor_table.repopulate = MagicMock()
    editor.parameter_editor_table.get_upload_selected_params = MagicMock(return_value={})
    editor.parameter_editor_table.view_port = MagicMock()
    editor._log_availability_report_window = None
    editor._log_report_return_pending = False
    focus_widget = MagicMock()
    editor.parameter_editor_table.view_port.focus_get.return_value = focus_widget
    progress_windows: list[MagicMock] = []

    def _progress_factory(*_args, **_kwargs) -> MagicMock:  # type: ignore[no-untyped-def]
        progress = MagicMock()
        progress.update_progress_bar = MagicMock()
        progress.update_progress_bar_300_pct = MagicMock()
        progress.destroy = MagicMock()
        progress_windows.append(progress)

        return progress

    editor._test_progress_windows = progress_windows  # type: ignore[attr-defined]
    editor.ui = ParameterEditorUiServices(
        create_progress_window=_progress_factory,
        ask_yesno=MagicMock(return_value=True),
        ask_retry_cancel=MagicMock(return_value=True),
        show_warning=MagicMock(),
        show_error=MagicMock(),
        show_info=MagicMock(),
        asksaveasfilename=MagicMock(return_value=""),
        askopenfilename=MagicMock(return_value=""),
        exit_callback=MagicMock(),
        extract_log_data=MagicMock(return_value=_log_data("ArduPlane", (4, 5, 5))),
        analyze_log_data_callback=MagicMock(),
        load_apm_doc=MagicMock(return_value={"LOG_BITMASK": {"fields": {"Bitmask": "9:Battery Monitor"}}}),
    )
    editor.current_plugin = None
    editor.current_plugin_view = None
    editor.file_selection_combobox = MagicMock()
    editor.file_selection_combobox.get.return_value = "01_initial.param"
    editor.file_selection_combobox.set = MagicMock()
    editor.file_selection_combobox.__getitem__.return_value = ("01_initial.param",)
    editor.show_only_differences = MagicMock()
    editor.show_only_differences.get.return_value = False
    editor.annotate_params_into_files = MagicMock()
    editor.annotate_params_into_files.get.return_value = False
    editor.skip_button = MagicMock()
    editor._param_download_progress_window = None
    editor._param_download_progress_window_upload = None
    editor._reset_progress_window = None
    editor.file_upload_progress_window = None
    editor._configured_upload_active = False
    editor._param_file_change_active = False
    editor._close_after_configured_upload = False
    editor._close_pending = False
    editor._tempcal_imu_progress_window = None
    _configure_layout_stubs(editor)
    parameter_area_container = _build_parameter_area_container()
    editor.parameter_area_container = parameter_area_container
    editor.parameter_container = parameter_area_container
    editor.parameter_area_paned = None
    editor.inline_component_editor = None
    editor.inline_component_scroll_frame = None
    editor._inline_component_chrome_height = 0
    editor._parameter_area_resize_pending = False
    editor._parameter_area_resize_running = False
    editor._inline_component_name = None
    editor._updating_inline_editor = False
    editor._requested_action = ParameterEditorAction.FINISHED
    editor.inline_component_container = MagicMock()
    editor.inline_component_container.winfo_reqheight.return_value = 74
    editor.inline_component_container.cget.return_value = 0
    return editor


def _log_data(vehicle_type: str = "ArduPlane", firmware_version: tuple[int, int, int] = (4, 5, 5)) -> LogData:
    log_data = LogData()
    log_data.vehicle_type = vehicle_type
    log_data.firmware_version = firmware_version
    return log_data


@pytest.fixture
def parameter_editor() -> MagicMock:
    """Provide a realistic parameter editor data model double."""
    manager = MagicMock()
    manager.current_file = "00_previous.param"
    manager.configuration_phases.return_value = True
    manager.handle_param_file_change_workflow.return_value = ("01_initial.param", True)
    manager.get_plugin.return_value = None
    manager.get_current_component.return_value = None
    manager.handle_write_changes_workflow = MagicMock()
    manager.handle_copy_fc_values_workflow = MagicMock(return_value="close")
    manager.open_documentation_in_browser = MagicMock()

    def _download_fc_parameters(
        get_progress_callback: Callable | None = None, *, response_timeout: float | None = None
    ) -> None:
        assert response_timeout is None
        if get_progress_callback is not None:
            callback = get_progress_callback()
            if callback is not None:
                callback(50, 100)

    manager.download_flight_controller_parameters = MagicMock(side_effect=_download_fc_parameters)
    manager.upload_selected_params_workflow = MagicMock()
    manager.write_summary_files_workflow = MagicMock()
    manager.last_upload_progress_callback = None
    manager.get_log_analysis_context_inputs = MagicMock(
        return_value=LogAnalysisInputs(
            project_vehicle_type="ArduPlane",
            project_firmware_version="4.5.5",
            vehicle_components={},
            configuration_steps={"project_step.param": {}},
            apm_doc={"LOG_BITMASK": {"fields": {"Bitmask": "9:Battery Monitor"}}},
        )
    )

    def _should_upload_file_to_fc(
        _selected_file: str,
        *,
        get_progress_callback: Callable[[], Callable | None] | None = None,
        **_ignored: object,
    ) -> bool:
        if get_progress_callback is not None:
            manager.last_upload_progress_callback = get_progress_callback()
            if manager.last_upload_progress_callback is not None:
                manager.last_upload_progress_callback(10, 20)
        return True

    manager.should_upload_file_to_fc_workflow = MagicMock(side_effect=_should_upload_file_to_fc)
    manager._should_download_file_from_url_workflow = MagicMock()
    manager.handle_imu_temperature_calibration_workflow = MagicMock()
    manager._handle_file_jump_workflow = MagicMock()
    manager.get_non_default_params = MagicMock(return_value={})
    manager.is_fc_connected = True
    manager.is_configuration_step_optional.return_value = False
    manager.get_next_non_optional_file.return_value = None
    manager.get_previous_non_optional_file.return_value = None
    manager.fc_parameters = {"ROLL_P": 0.12}
    return manager


class _DummyTkRoot:  # pylint: disable=too-many-instance-attributes, too-few-public-methods
    """Minimal Tk root stand-in that tracks method calls like a MagicMock."""

    def __init__(self, *args: object, **kwargs: object) -> None:  # pylint: disable=unused-argument
        self.tk = MagicMock()
        self.tk.call = MagicMock(return_value=1.0)
        self._last_child_ids: dict[str, int] | None = {}
        self.children: dict[str, object] = {}
        self._w = "."
        self.title = MagicMock()
        self.geometry = MagicMock()
        self.geometry.return_value = "990x630+0+0"
        self.state = MagicMock(return_value="normal")
        self.attributes = MagicMock(return_value=0)
        self.tk.getboolean.side_effect = lambda value: str(value).lower() in ("1", "true")
        self.protocol = MagicMock()
        self.withdraw = MagicMock()
        self.destroy = MagicMock()
        self.deiconify = MagicMock()
        self.update_idletasks = MagicMock()
        self.after = MagicMock()
        self.after_idle = MagicMock()
        self.winfo_fpixels = MagicMock(return_value=96.0)
        self.winfo_reqheight = MagicMock(return_value=630)
        self.winfo_width = MagicMock(return_value=1)
        self.winfo_height = MagicMock(return_value=1)
        self.winfo_reqwidth = MagicMock(return_value=990)
        self.winfo_pointerx = MagicMock(return_value=0)
        self.winfo_pointery = MagicMock(return_value=0)
        self.winfo_screenwidth = MagicMock(return_value=1920)
        self.winfo_screenheight = MagicMock(return_value=1080)
        self.winfo_rootx = MagicMock(return_value=0)
        self.winfo_rooty = MagicMock(return_value=0)
        self.winfo_x = MagicMock(return_value=0)
        self.winfo_y = MagicMock(return_value=0)
        self.update = MagicMock()
        self.bind = MagicMock()


@pytest.fixture(autouse=True)
def monitor_bounds() -> Iterator[MagicMock]:
    """Keep monitor detection independent of the host display and mocked Tk handles."""
    with patch.object(parameter_editor_module, "get_monitor_bounds", return_value=MonitorBounds(0, 0, 1920, 1080)) as bounds:
        yield bounds


@pytest.fixture
def parameter_editor_window(parameter_editor: MagicMock) -> ParameterEditorWindow:
    """Create a headless parameter editor instance."""
    return _create_editor(parameter_editor)


@pytest.fixture
def editor_factory(parameter_editor: MagicMock) -> Callable[[], ParameterEditorWindow]:
    """Factory fixture that returns isolated editor instances."""

    def _factory() -> ParameterEditorWindow:
        return _create_editor(parameter_editor)

    return _factory


class TestParameterEditorUiServices:  # pylint: disable=too-few-public-methods
    """Cover the ParameterEditorUiServices helper container."""

    def test_user_creates_progress_window_with_default_services(self) -> None:
        """Default services should instantiate ProgressWindow on demand."""
        parent = MagicMock()
        show_only_on_update = True
        progress_window = MagicMock()
        with patch(
            "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ProgressWindow",
            return_value=progress_window,
        ) as mock_progress:
            services = ParameterEditorUiServices.default()
            window = services.create_progress_window(parent, "Title", "Template", show_only_on_update)

        mock_progress.assert_called_once_with(
            parent,
            "Title",
            "Template",
            only_show_when_update_progress_called=True,
            auto_close_on_complete=True,
        )
        assert window is progress_window


# ============================== PARAMETER FILE FLOW ==============================


class TestWindowSizing:
    """Keep navigation controls visible while respecting the user's window size."""

    @pytest.mark.parametrize("ambient_dpi", [96, 144], ids=["96dpi-desktop", "144dpi-desktop"])
    @pytest.mark.parametrize("fail", [False, True], ids=["success", "failure"])
    def test_layout_scenarios_restore_shared_display_settings(self, root: tk.Tk, ambient_dpi: int, fail: bool) -> None:
        """
        Fixed-pixel scenarios must not change the display used by later tests.

        GIVEN: A shared Tk root with a desktop DPI and a customized default font
        WHEN: A 96-DPI layout scenario completes or raises an error
        THEN: Its scaling, named fonts and theme are restored for the next user scenario
        """
        with _layout_display(root, ambient_dpi):
            tkfont.nametofont("TkDefaultFont", root=root).configure(family="Courier", size=14)
            style = ttk.Style(root)
            style.theme_use("clam")
            original_scaling = float(root.tk.call("tk", "scaling"))
            original_fonts = {
                name: tkfont.nametofont(name, root=root).configure() for name in tkfont.names(root) if name.startswith("Tk")
            }
            failure_message = "layout scenario failed"
            with (
                pytest.raises(RuntimeError, match=failure_message) if fail else nullcontext(),
                _layout_display(root),
            ):
                assert float(root.tk.call("tk", "scaling")) == pytest.approx(96 / 72, rel=0.01)
                default_font = tkfont.nametofont("TkDefaultFont", root=root)
                assert default_font.cget("size") == 10
                assert default_font.metrics("linespace") == tkfont.Font(root=root, family="Arial", size=10).metrics(
                    "linespace"
                )
                assert style.theme_use() == "alt"
                if fail:
                    raise RuntimeError(failure_message)
            assert float(root.tk.call("tk", "scaling")) == pytest.approx(original_scaling, rel=0.01)
            assert style.theme_use() == "clam"
            assert {name: tkfont.nametofont(name, root=root).configure() for name in original_fonts} == original_fonts

    @pytest.mark.parametrize("height", [500, 688], ids=["short-window", "768-screen"])
    @pytest.mark.parametrize("complexity", ["simple", "normal"])
    def test_user_can_reclaim_table_space_by_collapsing_information_sections(  # noqa: PLR0915 # pylint: disable=too-many-locals,too-many-statements
        self,
        parameter_editor_window: ParameterEditorWindow,
        root: tk.Tk,
        height: int,
        complexity: str,
    ) -> None:
        """
        Collapsing progress and documentation gives space back to the parameter table.

        GIVEN: The real information sections and parameter table in a short editor window
        WHEN: The user collapses each section, changes steps and expands them again
        THEN: Table space grows, edits and section state survive, and navigation stays visible
        """
        editor = parameter_editor_window
        model = cast("MagicMock", editor.parameter_editor)
        model.get_last_configuration_step_number.return_value = 30
        model.get_sorted_phases_with_end_and_weight.return_value = {
            "Hardware setup": {"start": 1, "end": 10, "weight": 9},
            "Flight tuning": {"start": 10, "end": 30, "weight": 20},
        }
        model.get_documentation_frame_title.return_value = "Initial setup Documentation"
        model.get_documentation_text_and_url.side_effect = lambda key: (
            ("75", "") if key == "mandatory" else ("Setup guide", "https://ardupilot.org/")
        )
        model.parse_mandatory_level_percentage.return_value = (75, "Required setup")
        model.get_why_why_now_tooltip.return_value = "Configure the vehicle before flying."
        model.current_step_parameters = {"TEST_GAIN": ArduPilotParameter("TEST_GAIN", Par(0.2, "Gain"))}
        model.should_display_bitmask_parameter_editor_usage.return_value = False
        window = tk.Toplevel(root)
        window.geometry(f"990x{height}+0+0")
        window.update_idletasks()
        editor.root = window
        editor.gui_complexity = complexity
        editor.main_frame = ttk.Frame(window)
        editor.main_frame.place(width=990, height=height)
        header = ttk.Frame(editor.main_frame, height=100)
        header.pack(side="top", fill="x")
        header.pack_propagate(flag=False)

        try:
            with patch.object(
                parameter_editor_module.ProgramSettings,
                "get_setting",
                side_effect=lambda key: complexity if key == "gui_complexity" else False,
            ):
                editor._create_progress_and_documentation_widgets()
            editor.parameter_area_container = ttk.Frame(editor.main_frame)
            editor.parameter_area_container.pack(side="top", fill="both", expand=True)
            editor.parameter_container = editor.parameter_area_container
            table = parameter_editor_module.ParameterEditorTable(editor.parameter_container, model, editor)
            editor.parameter_editor_table = table
            table.pack(fill="both", expand=True)
            table.repopulate_table(show_only_differences=False, gui_complexity=complexity)
            buttons = ttk.Frame(editor.main_frame)
            buttons.pack(side="bottom", fill="x", pady=10)
            ttk.Button(buttons, text="Upload parameters\nand advance").pack()
            root.update_idletasks()
            editor._bind_parameter_layout_events()
            editor._resize_parameter_area_to_fit()
            root.update_idletasks()
            initial_table_height = editor.parameter_area_container.winfo_height()
            value_widget = table._new_value_widgets["TEST_GAIN"]
            value_widget.delete(0, tk.END)
            value_widget.insert(0, "0.15")
            docs = editor.documentation_frame.documentation_frame
            progress = editor.stage_progress_bar
            assert docs.expanded
            assert progress.expanded

            docs.header_label.event_generate("<Button-1>")
            root.update_idletasks()
            after_docs_height = editor.parameter_area_container.winfo_height()
            assert after_docs_height > initial_table_height
            assert docs.header_label.winfo_ismapped()
            assert not docs.content_frame.winfo_ismapped()

            progress.header_label.event_generate("<Button-1>")
            root.update_idletasks()
            assert editor.parameter_area_container.winfo_height() > after_docs_height
            assert progress.header_label.winfo_ismapped()
            assert not progress.content_frame.winfo_ismapped()
            model.get_documentation_frame_title.return_value = "Flight tuning Documentation"
            editor.documentation_frame.refresh_documentation_labels()
            progress.update_progress(15)
            assert not docs.expanded
            assert not progress.expanded
            assert docs.header_label.cget("text") == "▶ Flight tuning Documentation"
            assert cast("ttk.Progressbar", progress.phase_bars[1]["bar"]).cget("value") == 5
            assert editor.parameter_editor_table is table
            assert value_widget.get() == "0.15"
            assert buttons.winfo_height() == buttons.winfo_reqheight()
            assert buttons.winfo_y() + buttons.winfo_height() <= height - 10

            for section in (progress, docs):
                section.header_label.event_generate("<Button-1>")
            root.update_idletasks()

            assert docs.content_frame.winfo_ismapped()
            assert progress.content_frame.winfo_ismapped()
            assert editor.parameter_area_container.winfo_height() == initial_table_height
            assert table._new_value_widgets["TEST_GAIN"] is value_widget
            assert value_widget.get() == "0.15"
            assert buttons.winfo_height() == buttons.winfo_reqheight()
            assert buttons.winfo_y() + buttons.winfo_height() <= height - 10
        finally:
            window.destroy()

    @pytest.mark.parametrize("height_option", [0, "0", pytest.param("pixel", id="truthy-tcl-pixel-zero")])
    def test_new_parameter_panes_are_measured_for_all_tk_zero_representations(
        self, parameter_editor_window: ParameterEditorWindow, height_option: int | str
    ) -> None:
        """
        Unset Tk distances must not prevent the new panes from being measured.

        GIVEN: Tk returns zero as an integer, string or truthy Tcl pixel object
        WHEN: A new parameter area is fitted with a resize callback queued
        THEN: Idle geometry is flushed before its height is fixed, without re-entry
        """
        editor = parameter_editor_window
        pixel_zero = MagicMock()
        pixel_zero.__str__.return_value = "0"
        container = cast("MagicMock", editor.parameter_area_container)
        container.cget.return_value = pixel_zero if height_option == "pixel" else height_option
        flushing = False

        def settle_geometry() -> None:
            nonlocal flushing
            assert not flushing, "Measuring panes must not recursively flush geometry"
            flushing = True
            editor._resize_parameter_area_to_fit()
            editor._on_main_frame_resize(tk.Event())
            flushing = False

        container.update_idletasks.side_effect = settle_geometry

        editor._resize_parameter_area_to_fit()

        container.update_idletasks.assert_called_once()
        container.configure.assert_called_once_with(height=600)
        cast("MagicMock", editor.root).after_idle.assert_not_called()
        assert not editor._parameter_area_resize_running

    @pytest.mark.parametrize("padding", [10, (10,), (10, 10), "10", "10 10", (4, 16), "4 16"])
    def test_bottom_buttons_keep_their_full_height(
        self, parameter_editor_window: ParameterEditorWindow, padding: int | tuple[int, ...] | str
    ) -> None:
        """
        Symmetric and asymmetric padding reserve space on both sides of the buttons.

        GIVEN: Fixed controls and two-line buttons with 20 pixels of total padding
        WHEN: The parameter table is fitted to the window
        THEN: The table leaves enough room for the full button row and all padding
        """
        editor = parameter_editor_window
        controls = []
        for height, pady in [(600, 2), (100, (2, 2)), (45, padding)]:
            widget = MagicMock()
            widget.winfo_manager.return_value = "pack"
            widget.winfo_reqheight.return_value = height
            widget.pack_info.return_value = {"pady": pady}
            widget.winfo_pixels.side_effect = int
            controls.append(widget)
        hidden_editor = MagicMock()
        hidden_editor.winfo_manager.return_value = ""
        editor.root.tk.splitlist.side_effect = lambda value: tuple(value.split())
        editor.main_frame.winfo_children.return_value = [*controls, editor.parameter_area_container, hidden_editor]
        editor.main_frame.winfo_height.return_value = 854

        editor._resize_parameter_area_to_fit()

        editor.parameter_area_container.configure.assert_called_once_with(height=81)

    @pytest.mark.parametrize(
        ("screen_height", "root_y", "requested_height", "scaling", "expected_height", "expected_y"),
        [
            (768, 69, 854, 1.0, 688, 40),
            (900, 121, 817, 1.0, 820, 40),
            (1080, 193, 931, 1.0, 931, 109),
            (1080, 193, 931, 1.5, 960, 60),
        ],
    )
    # pylint: disable-next=too-many-arguments, too-many-positional-arguments
    def test_startup_keeps_bottom_controls_on_screen(
        self,
        parameter_editor_window: ParameterEditorWindow,
        monitor_bounds: MagicMock,
        screen_height: int,
        root_y: int,
        requested_height: int,
        scaling: float,
        expected_height: int,
        expected_y: int,
    ) -> None:
        """
        Startup accounts for the window's position as well as the monitor height.

        GIVEN: The initial smaller window has already been centered
        WHEN: The final startup size is applied
        THEN: Its bottom remains within the monitor with room for desktop panels
        """
        editor = parameter_editor_window
        editor.dpi_scaling_factor = scaling
        monitor_bounds.return_value = MonitorBounds(0, 0, 1920, screen_height)
        editor.root.winfo_reqheight.return_value = requested_height
        editor.root.winfo_rooty.return_value = root_y
        editor.root.winfo_y.return_value = root_y
        editor.root.geometry.return_value = f"800x600+0+{root_y}"

        editor._fit_window_to_screen_height(initialize=True)

        editor.root.geometry.assert_any_call(f"{round(990 * scaling)}x{expected_height}+0+{expected_y}")
        assert expected_y + expected_height <= screen_height - round(40 * scaling)

    @pytest.mark.parametrize("component_name", [None, "Battery", "Motor"])
    def test_changing_steps_preserves_user_window_size(
        self, parameter_editor_window: ParameterEditorWindow, component_name: str | None
    ) -> None:
        """
        Repeated step changes preserve a manually resized window.

        GIVEN: A user resized the window to 1400 by 700 pixels
        WHEN: Several steps rebuild or hide the inline component editor
        THEN: The window retains its size even when widgets request more height
        """
        editor = parameter_editor_window
        editor.root.winfo_width.return_value = 1400
        editor.root.winfo_height.return_value = 700
        editor.root.winfo_rooty.return_value = 100
        editor.root.winfo_y.return_value = 100
        editor.root.winfo_reqheight.return_value = 1200

        with (
            patch.object(parameter_editor_module, "ComponentEditorWindow"),
            patch.object(parameter_editor_module, "ScrollFrame") as scroll_frame,
        ):
            scroll_frame.return_value.winfo_reqheight.return_value = 50
            scroll_frame.return_value.winfo_height.return_value = 1
            scroll_frame.return_value.view_port.winfo_reqheight.return_value = 272
            for _ in range(5):
                editor._update_inline_component_editor(component_name)

        editor.root.geometry.assert_not_called()

    def test_oversized_window_is_clamped_on_an_offset_monitor(
        self, parameter_editor_window: ParameterEditorWindow, monitor_bounds: MagicMock
    ) -> None:
        """
        Later sizing uses the active monitor, including negative desktop coordinates.

        GIVEN: An oversized user window on a monitor above and right of the primary one
        WHEN: A step changes
        THEN: Only the height and vertical position are clamped, preserving width
        """
        editor = parameter_editor_window
        monitor_bounds.return_value = MonitorBounds(1920, -900, 3520, 0)
        editor.root.winfo_width.return_value = 1400
        editor.root.winfo_height.return_value = 1200
        editor.root.winfo_rooty.return_value = -400
        editor.root.winfo_y.return_value = -400
        editor.root.winfo_x.return_value = 2000
        editor.root.geometry.return_value = "1400x1200+2000+-400"

        editor._fit_window_to_screen_height()

        editor.root.geometry.assert_any_call("1400x820+2000+-860")

    @pytest.mark.parametrize("screen_height", [768, 900])
    def test_decorated_window_settles_after_startup(
        self, parameter_editor_window: ParameterEditorWindow, monitor_bounds: MagicMock, screen_height: int
    ) -> None:
        """
        Repeated fits keep decorated X11 windows in the same place.

        GIVEN: Client coordinates include a five-pixel border and 23-pixel title bar
        WHEN: Startup sizes the editor and eight subsequent steps fit it again
        THEN: Neither axis drifts and the client bottom respects the panel margin
        """
        editor = parameter_editor_window
        monitor_bounds.return_value = MonitorBounds(0, 0, 1600, screen_height)
        frame = [167, 100, 990, 630]
        positions = []

        def geometry(value: str | None = None) -> str:
            if value is not None:
                match = re.fullmatch(r"(\d+)x(\d+)\+(-?\d+)\+(-?\d+)", value)
                assert match is not None
                width, height, x_pos, y_pos = map(int, match.groups())
                frame[:] = [x_pos, y_pos, width, height]
                positions.append(tuple(frame))
            return f"{frame[2]}x{frame[3]}+{frame[0]}+{frame[1]}"

        editor.root.geometry.side_effect = geometry
        editor.root.winfo_rootx.side_effect = editor.root.winfo_x.side_effect = lambda: frame[0] + 5
        editor.root.winfo_rooty.side_effect = editor.root.winfo_y.side_effect = lambda: frame[1] + 23
        editor.root.winfo_width.side_effect = lambda: frame[2]
        editor.root.winfo_height.side_effect = lambda: frame[3]
        editor.root.winfo_reqheight.return_value = 900

        editor._fit_window_to_screen_height(initialize=True)
        for _ in range(8):
            editor._fit_window_to_screen_height()

        assert positions == [(167, 17, 990, screen_height - 80)]
        assert editor.root.winfo_rooty() == 40
        assert editor.root.winfo_rooty() + editor.root.winfo_height() == screen_height - 40

    @pytest.mark.parametrize("height", [600, 730])
    def test_visible_window_at_top_edge_keeps_user_position(
        self, parameter_editor_window: ParameterEditorWindow, monitor_bounds: MagicMock, height: int
    ) -> None:
        """
        User positions inside the monitor need no correction.

        GIVEN: A decorated window at frame +100+0, entirely visible on a 768-pixel monitor
        WHEN: A step changes, even with less than the preferred margin
        THEN: Its size and position remain unchanged
        """
        editor = parameter_editor_window
        monitor_bounds.return_value = MonitorBounds(0, 0, 1366, 768)
        editor.root.winfo_rooty.return_value = 23
        editor.root.winfo_height.return_value = height

        editor._fit_window_to_screen_height()

        editor.root.geometry.assert_not_called()

    @pytest.mark.parametrize("mode", ["state", "-zoomed", "-fullscreen"])
    def test_step_changes_preserve_window_manager_mode(
        self, parameter_editor_window: ParameterEditorWindow, mode: str
    ) -> None:
        """
        The window manager retains control of maximised and full-screen windows.

        GIVEN: A window maximised by state, by X11 attributes, or in full screen
        WHEN: A step changes while its height exceeds the normal sizing limit
        THEN: Geometry is untouched and the table still fits the available space
        """
        editor = parameter_editor_window
        editor.root.winfo_height.return_value = 1200
        if mode == "state":
            editor.root.state.return_value = "zoomed"
        else:
            editor.root.attributes.side_effect = lambda attribute: "1" if attribute == mode else "0"

        editor._fit_window_to_screen_height()

        editor.root.geometry.assert_not_called()
        editor.parameter_area_container.configure.assert_called_once_with(height=600)

    def test_unsupported_zoom_attribute_still_allows_normal_window_fitting(
        self, parameter_editor_window: ParameterEditorWindow
    ) -> None:
        """
        Windows and macOS can omit the X11 zoom attribute.

        GIVEN: Querying -zoomed raises TclError but full screen is false
        WHEN: An oversized normal window is fitted
        THEN: Its height is reduced without an unsupported-attribute error
        """
        editor = parameter_editor_window
        editor.root.attributes.side_effect = [tk.TclError("unsupported attribute"), 0]
        editor.root.winfo_height.return_value = 1200

        editor._fit_window_to_screen_height()

        editor.root.geometry.assert_any_call("800x1000+0+40")

    def test_clamping_preserves_right_and_bottom_geometry_anchors(
        self, parameter_editor_window: ParameterEditorWindow
    ) -> None:
        """
        Negative WM geometry offsets retain their screen-edge anchor semantics.

        GIVEN: An oversized decorated window anchored 77 pixels right and 100 pixels bottom
        WHEN: Its client height and top are clamped to the monitor
        THEN: The right anchor stays unchanged and the bottom anchor accounts for resizing
        """
        editor = parameter_editor_window
        editor.root.geometry.return_value = "1400x1200-77-100"
        editor.root.winfo_width.return_value = 1400
        editor.root.winfo_height.return_value = 1200
        editor.root.winfo_rooty.return_value = -225

        editor._fit_window_to_screen_height()

        editor.root.geometry.assert_any_call("1400x1000-77-35")

    def test_wrapped_controls_refit_the_table_after_idle(self, parameter_editor_window: ParameterEditorWindow) -> None:
        """
        Narrowing the window leaves the full button row visible after labels wrap.

        GIVEN: The header initially requests 100 pixels and wraps after Configure
        WHEN: Several resize events arrive before idle layout completes
        THEN: A single deferred fit accounts for the new 115-pixel header height
        """
        editor = parameter_editor_window
        header = MagicMock()
        header.winfo_manager.return_value = "pack"
        header.winfo_reqheight.return_value = 100
        header.pack_info.return_value = {"pady": 0}
        header.winfo_pixels.side_effect = int
        editor.main_frame.winfo_children.return_value = [header, editor.parameter_area_container]

        editor._on_main_frame_resize(MagicMock())
        editor._on_main_frame_resize(MagicMock())
        editor.parameter_area_container.configure.assert_not_called()
        header.winfo_reqheight.return_value = 115
        editor.root.after_idle.call_args.args[0]()

        editor.root.after_idle.assert_called_once()
        editor.parameter_area_container.configure.assert_called_once_with(height=485)
        assert not editor._parameter_area_resize_pending

    @pytest.mark.parametrize(
        ("frame_height", "component_height", "table_height", "plugin_height"),
        [(600, 172, 120, None), (854, 304, 242, None), (600, 92, 200, 200)],
    )
    def test_component_fields_scroll_to_preserve_the_parameter_area(
        self,
        parameter_editor_window: ParameterEditorWindow,
        frame_height: int,
        component_height: int,
        table_height: int,
        plugin_height: int | None,
    ) -> None:
        """
        Component-heavy steps preserve useful table and plugin space on short screens.

        GIVEN: Fixed controls consume 300 pixels beside a 272-pixel component editor
        WHEN: The remaining space is allocated on small or large windows
        THEN: The table or left plugin gets usable height and component fields can scroll
        """
        editor = parameter_editor_window
        if plugin_height is not None:
            editor.current_plugin = {"placement": "left"}
            plugin_view = MagicMock()
            plugin_view.winfo_reqheight.return_value = plugin_height
            editor.current_plugin_view = plugin_view
        fixed_controls = MagicMock()
        fixed_controls.winfo_manager.return_value = "pack"
        fixed_controls.winfo_reqheight.return_value = 300
        fixed_controls.pack_info.return_value = {"pady": 0}
        fixed_controls.winfo_pixels.side_effect = int
        editor.inline_component_container.winfo_manager.return_value = "pack"
        editor.inline_component_container.pack_info.return_value = {"pady": 4}
        editor.inline_component_container.winfo_pixels.side_effect = int
        editor.inline_component_scroll_frame = MagicMock()
        editor.inline_component_scroll_frame.view_port.winfo_reqheight.return_value = 272
        editor.inline_component_scroll_frame.winfo_height.return_value = 100
        editor.inline_component_container.winfo_height.return_value = 124
        editor._inline_component_chrome_height = 0
        editor.main_frame.winfo_height.return_value = frame_height
        editor.main_frame.winfo_children.return_value = [
            fixed_controls,
            editor.inline_component_container,
            editor.parameter_area_container,
        ]

        editor._resize_parameter_area_to_fit()

        editor.inline_component_container.configure.assert_called_once_with(height=component_height)
        editor.inline_component_scroll_frame.canvas.configure.assert_called_once_with(height=280)
        editor.parameter_area_container.configure.assert_called_once_with(height=table_height)

    @pytest.mark.parametrize("scaling", [1.0, 1.5], ids=["96dpi", "144dpi"])
    def test_growing_window_never_shrinks_either_scrollable_panel(
        self, parameter_editor_window: ParameterEditorWindow, scaling: float
    ) -> None:
        """
        Each extra pixel of window height preserves both panels' visible content.

        GIVEN: Component fields overflow the space beside a scrollable parameter table
        WHEN: The user grows the window through the two panels' minimum-height boundary
        THEN: Neither panel shrinks or jumps, and together they use the available height
        """
        editor = parameter_editor_window
        editor.dpi_scaling_factor = scaling
        fixed_controls = MagicMock()
        fixed_controls.winfo_manager.return_value = "pack"
        fixed_controls.winfo_reqheight.return_value = 300
        fixed_controls.pack_info.return_value = {"pady": 0}
        fixed_controls.winfo_pixels.side_effect = int
        editor.inline_component_container.winfo_manager.return_value = "pack"
        editor.inline_component_container.pack_info.return_value = {"pady": 0}
        editor.inline_component_container.winfo_pixels.side_effect = int
        editor.inline_component_scroll_frame = MagicMock()
        editor.inline_component_scroll_frame.view_port.winfo_reqheight.return_value = 600
        editor.inline_component_scroll_frame.winfo_height.return_value = 100
        editor.inline_component_container.winfo_height.return_value = 100 + round(28 * scaling)
        editor._inline_component_chrome_height = 0
        editor.main_frame.winfo_children.return_value = [
            fixed_controls,
            editor.inline_component_container,
            editor.parameter_area_container,
        ]

        boundary = round(80 * scaling) + round(120 * scaling)
        previous_heights: tuple[int, int] | None = None
        for available_height in range(boundary - 5, boundary + 6):
            editor.main_frame.winfo_height.return_value = 300 + available_height
            editor._resize_parameter_area_to_fit()
            component_height = editor.inline_component_container.configure.call_args.kwargs["height"]
            table_height = editor.parameter_area_container.configure.call_args.kwargs["height"]
            assert component_height + table_height == available_height
            if previous_heights is not None:
                assert 0 <= component_height - previous_heights[0] <= 1
                assert 0 <= table_height - previous_heights[1] <= 1
            previous_heights = (component_height, table_height)

    def test_fixed_widget_growth_keeps_real_buttons_visible(
        self, parameter_editor_window: ParameterEditorWindow, layout_root: tk.Tk
    ) -> None:
        """
        Real Tk layout settles after the stage bar wraps at a narrower width.

        GIVEN: Normal mode displays eight labelled phases above the table and buttons
        WHEN: The window is narrowed in single jumps and Tk processes idle layout
        THEN: The button row stays fully visible and the table gives space to wrapping
        """
        root = layout_root
        editor = parameter_editor_window
        editor.root = root
        editor.main_frame = ttk.Frame(root)
        editor.main_frame.place(width=1031, height=600)
        phases = {f"Configuration phase {number}": {"start": number, "end": number + 1} for number in range(8)}
        stage_bar = StageProgressBar(editor.main_frame, phases, 9, "normal")
        stage_bar.pack(side="top", fill="x")
        editor.parameter_area_container = ttk.Frame(editor.main_frame, height=500)
        editor.parameter_area_container.pack(side="top", fill="both", expand=True)
        buttons = ttk.Frame(editor.main_frame)
        buttons.pack(side="bottom", fill="x", pady=10)
        ttk.Button(buttons, text="Upload parameters\nand advance").pack()
        editor._bind_parameter_layout_events()

        try:
            root.update_idletasks()
            initial_header_height = stage_bar.winfo_reqheight()
            for width in (950, 800, 400):
                editor.main_frame.place_configure(width=width)
                root.update_idletasks()
                assert buttons.winfo_height() == buttons.winfo_reqheight()
                assert buttons.winfo_y() + buttons.winfo_height() <= editor.main_frame.winfo_height() - 10
                assert editor.parameter_area_container.winfo_height() + stage_bar.winfo_reqheight() == (
                    editor.main_frame.winfo_height() - buttons.winfo_reqheight() - 20
                )
            assert stage_bar.winfo_reqheight() > initial_header_height
        finally:
            editor.main_frame.destroy()

    @staticmethod
    def _assert_real_component_fields_visible(editor: ParameterEditorWindow, field_count: int) -> int:
        """Check settled panel geometry and reach the last field through its real canvas."""
        scroll_frame = editor.inline_component_scroll_frame
        assert scroll_frame is not None
        assert editor._inline_component_chrome_height > 0
        panel_height = editor.inline_component_container.winfo_height()
        assert panel_height == int(editor.inline_component_container.cget("height"))
        assert panel_height == editor.inline_component_container.winfo_reqheight()
        last_field = scroll_frame.view_port.winfo_children()[-1]
        assert scroll_frame.canvas.winfo_height() >= last_field.winfo_height() + 8
        assert editor.parameter_area_container.winfo_height() >= last_field.winfo_height() + 8
        if field_count == 3:
            assert panel_height == scroll_frame.view_port.winfo_reqheight() + 8 + editor._inline_component_chrome_height
            assert scroll_frame.canvas.winfo_height() >= scroll_frame.view_port.winfo_reqheight() + 8
        else:
            assert scroll_frame.view_port.winfo_reqheight() > scroll_frame.canvas.winfo_height()
            scroll_frame.canvas.yview_moveto(1)
            assert scroll_frame.canvas.yview()[0] > 0
        field_bottom = (
            scroll_frame.canvas.coords(scroll_frame.canvas_window)[1] + last_field.winfo_y() + last_field.winfo_height()
        )
        assert field_bottom <= scroll_frame.canvas.canvasy(scroll_frame.canvas.winfo_height()) + 1
        return panel_height

    @staticmethod
    def _assert_real_panels_grow_continuously(editor: ParameterEditorWindow, root: tk.Tk, fixed_height: int) -> None:
        """Exercise the actual Configure bindings across the allocation boundary."""
        boundary = round(80 * editor.dpi_scaling_factor) + round(120 * editor.dpi_scaling_factor)
        previous_heights: tuple[int, int] | None = None
        for available_height in range(boundary - 5, boundary + 6):
            editor.main_frame.place_configure(height=fixed_height + available_height)
            root.update_idletasks()
            panel_heights = (
                editor.inline_component_container.winfo_height(),
                editor.parameter_area_container.winfo_height(),
            )
            assert sum(panel_heights) == available_height
            if previous_heights is not None:
                assert all(
                    0 <= current - previous <= 1 for current, previous in zip(panel_heights, previous_heights, strict=True)
                )
            previous_heights = panel_heights

    @pytest.mark.parametrize("defer_geometry", [False, True], ids=["immediate", "sequoia"])
    @pytest.mark.parametrize("field_count", [3, 40], ids=["fitting-fields", "scrolling-fields"])
    @pytest.mark.parametrize(
        ("width", "height", "dpi"),
        [
            pytest.param(1920, 1000, 96, id="1920x1080"),
            pytest.param(1366, 688, 96, id="1366x768"),
            pytest.param(1600, 820, 96, id="1600x900"),
            pytest.param(1920, 960, 144, id="1920x1080-144dpi"),
            pytest.param(1100, 500, 96, id="1100x500-window"),
            pytest.param(1024, 516, 96, id="1024x600"),
            pytest.param(1280, 636, 96, id="1280x720"),
        ],
    )
    def test_real_component_fields_remain_accessible_after_rebuilding(  # noqa: PLR0915 # pylint: disable=too-many-locals,too-many-arguments,too-many-positional-arguments
        self,
        parameter_editor_window: ParameterEditorWindow,
        layout_root: tk.Tk,
        width: int,
        height: int,
        dpi: int,
        field_count: int,
        defer_geometry: bool,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        A scrolling component editor keeps both fields and parameter rows accessible.

        GIVEN: Real Tk widgets at the reported display widths, client heights and DPI
        WHEN: Equal-height editors are rebuilt consecutively and across a component-less step
        THEN: Fitting fields stay fully visible, overflowing fields scroll, and buttons remain visible
        """
        root = layout_root
        monkeypatch.setattr(parameter_editor_module, "is_macos_sequoia_or_older", lambda: defer_geometry)
        editor = parameter_editor_window
        _set_layout_dpi(root, dpi)
        field_font = tkfont.Font(root=root, family="Arial", size=10)
        assert float(root.tk.call("tk", "scaling")) == pytest.approx(dpi / 72, rel=0.01)
        editor.dpi_scaling_factor = dpi / 96
        editor.root = root
        editor.main_frame = ttk.Frame(root)
        editor.main_frame.place(width=width, height=height)
        header = ttk.Frame(editor.main_frame, height=round((200 if field_count == 3 else 300) * editor.dpi_scaling_factor))
        header.pack(side="top", fill="x")
        header.pack_propagate(flag=False)
        editor.inline_component_container = ttk.LabelFrame(editor.main_frame)
        editor.parameter_area_container = ttk.Frame(editor.main_frame, height=500)
        editor.parameter_area_container.pack(side="top", fill="both", expand=True)
        buttons = ttk.Frame(editor.main_frame)
        buttons.pack(side="bottom", fill="x", pady=10)
        ttk.Button(buttons, text="Upload parameters\nand advance").pack()
        editor._bind_parameter_layout_events()

        def create_component_editor(*_args: object, embedded_parent_frame: tk.Widget, **_kwargs: object) -> MagicMock:
            def populate(_name: str) -> None:
                for _ in range(field_count):
                    ttk.Entry(embedded_parent_frame, font=field_font).pack(side="top", fill="x")
                if not defer_geometry:
                    embedded_parent_frame.update_idletasks()

            return MagicMock(populate_single_component=MagicMock(side_effect=populate))

        try:
            initial_panel_height: int | None = None
            with patch.object(parameter_editor_module, "ComponentEditorWindow", side_effect=create_component_editor):
                for name in ("Battery", "Motor", "Battery", None, "Motor", "Battery"):
                    editor._update_inline_component_editor(name)
                    root.update_idletasks()
                    assert editor.main_frame.winfo_width() == width
                    assert editor.main_frame.winfo_height() == height
                    assert buttons.winfo_height() == buttons.winfo_reqheight()
                    assert buttons.winfo_y() + buttons.winfo_height() <= height - 10
                    if name is None:
                        assert editor.inline_component_scroll_frame is None
                        assert editor.inline_component_container.winfo_manager() == ""
                        assert editor.parameter_area_container.winfo_height() == (
                            height - header.winfo_reqheight() - buttons.winfo_reqheight() - 20
                        )
                        continue
                    panel_height = self._assert_real_component_fields_visible(editor, field_count)
                    if initial_panel_height is None:
                        initial_panel_height = panel_height
                    assert panel_height == initial_panel_height
                if field_count == 40:
                    fixed_height = header.winfo_reqheight() + buttons.winfo_reqheight() + 20
                    self._assert_real_panels_grow_continuously(editor, root, fixed_height)
        finally:
            editor.main_frame.destroy()
            root.update_idletasks()


class TestParameterFileSelection:
    """Exercise the behaviours around selecting and loading parameter files."""

    def test_window_initialization_sets_attributes(self, parameter_editor: MagicMock) -> None:
        """ParameterEditorWindow stores dependencies and GUI settings during init."""
        parameter_editor.get_last_configuration_step_number.return_value = None

        def fake_get_setting(key: str) -> object:
            return {"gui_complexity": "normal", "annotate_docs_into_param_files": False}.get(key, False)

        with (
            patch("tkinter.Tk", _DummyTkRoot),
            patch.object(ParameterEditorWindow, "_create_conf_widgets"),
            patch.object(
                ParameterEditorWindow, "_create_parameter_area_widgets", autospec=True, side_effect=_configure_layout_stubs
            ),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.DocumentationFrame",
                return_value=MagicMock(documentation_frame=MagicMock()),
            ),
            patch("ardupilot_methodic_configurator.frontend_tkinter_base_window.ttk.Style"),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_font.safe_font_nametofont",
                return_value=None,
            ),
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.FreeDesktop.setup_startup_notification"),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.UsagePopupWindow.should_display",
                return_value=False,
            ),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ProgramSettings.get_setting",
                side_effect=fake_get_setting,
            ),
        ):
            window = ParameterEditorWindow(parameter_editor)

        assert window.parameter_editor is parameter_editor
        assert window.gui_complexity == "normal"
        assert window.current_plugin is None
        assert window.current_plugin_view is None

    def test_window_title_and_geometry_setup(self, parameter_editor: MagicMock) -> None:
        """Window title, geometry, and protocol handlers are configured during init."""
        parameter_editor.get_last_configuration_step_number.return_value = None

        with (
            patch("tkinter.Tk", _DummyTkRoot),
            patch.object(ParameterEditorWindow, "_create_conf_widgets"),
            patch.object(
                ParameterEditorWindow, "_create_parameter_area_widgets", autospec=True, side_effect=_configure_layout_stubs
            ),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.DocumentationFrame",
                return_value=MagicMock(documentation_frame=MagicMock()),
            ),
            patch("ardupilot_methodic_configurator.frontend_tkinter_base_window.ttk.Style"),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_font.safe_font_nametofont",
                return_value=None,
            ),
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.FreeDesktop.setup_startup_notification"),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.UsagePopupWindow.should_display",
                return_value=False,
            ),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ProgramSettings.get_setting",
                side_effect=lambda key: "normal" if key == "gui_complexity" else False,
            ),
            # Suppress Win32 DPI so _DummyTkRoot.winfo_fpixels(96) drives scaling=1.0
            # at any real system DPI setting.
            patch.object(BaseWindow, "_get_win32_system_dpi", return_value=0),
        ):
            window = ParameterEditorWindow(parameter_editor)

        root = cast("_DummyTkRoot", window.root)
        root.title.assert_called_once()
        root.geometry.assert_any_call("990x630")
        root.protocol.assert_called_once_with("WM_DELETE_WINDOW", ANY)

    def test_stage_progress_bar_initializes_when_steps_known(self, parameter_editor: MagicMock) -> None:
        """Stage progress bar only appears when the configuration has multiple steps."""
        parameter_editor.get_last_configuration_step_number.return_value = 5
        parameter_editor.get_sorted_phases_with_end_and_weight.return_value = [
            ("Phase 1", 1, 1.0),
            ("Phase 2", 2, 1.0),
        ]

        with (
            patch("tkinter.Tk", _DummyTkRoot),
            patch.object(ParameterEditorWindow, "_create_conf_widgets"),
            patch.object(
                ParameterEditorWindow, "_create_parameter_area_widgets", autospec=True, side_effect=_configure_layout_stubs
            ),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.DocumentationFrame",
                return_value=MagicMock(documentation_frame=MagicMock()),
            ),
            patch("ardupilot_methodic_configurator.frontend_tkinter_base_window.ttk.Style"),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_font.safe_font_nametofont",
                return_value=None,
            ),
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.FreeDesktop.setup_startup_notification"),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.UsagePopupWindow.should_display",
                return_value=False,
            ),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ProgramSettings.get_setting",
                side_effect=["normal", False],
            ),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.StageProgressBar",
                return_value=MagicMock(pack=MagicMock()),
            ) as mock_stage,
        ):
            window = ParameterEditorWindow(parameter_editor)

        mock_stage.assert_called_once_with(
            window.main_frame,
            parameter_editor.get_sorted_phases_with_end_and_weight.return_value,
            5,
            window.gui_complexity,
        )
        mock_stage.return_value.pack.assert_called_once_with(side=tk.TOP, fill="x", expand=False, pady=(2, 2), padx=(4, 4))
        assert window.stage_progress_bar is mock_stage.return_value


class TestUsagePopupScheduling:
    """Ensure the parameter editor schedules its usage popup correctly."""

    @contextmanager
    def _window_with_common_patches(
        self,
        parameter_editor: MagicMock,
        *,
        should_display: bool,
    ) -> Generator[tuple[ParameterEditorWindow, MagicMock], None, None]:
        parameter_editor.get_last_configuration_step_number.return_value = None

        def fake_get_setting(key: str) -> object:
            return {"gui_complexity": "normal", "annotate_docs_into_param_files": False}.get(key, False)

        with (
            patch("tkinter.Tk", _DummyTkRoot),
            patch.object(ParameterEditorWindow, "_create_conf_widgets"),
            patch.object(
                ParameterEditorWindow, "_create_parameter_area_widgets", autospec=True, side_effect=_configure_layout_stubs
            ),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.DocumentationFrame",
                return_value=MagicMock(documentation_frame=MagicMock()),
            ),
            patch("ardupilot_methodic_configurator.frontend_tkinter_base_window.ttk.Style"),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_font.safe_font_nametofont",
                return_value=None,
            ),
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.FreeDesktop.setup_startup_notification"),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ProgramSettings.get_setting",
                side_effect=fake_get_setting,
            ),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.UsagePopupWindow.should_display",
                return_value=should_display,
            ),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.display_parameter_editor_usage_popup"
            ) as mock_display,
        ):
            window = ParameterEditorWindow(parameter_editor)
            yield window, mock_display

    def test_usage_popup_runs_when_enabled(self, parameter_editor: MagicMock) -> None:
        """Parameter editor schedules its usage popup when user preference allows it."""
        with self._window_with_common_patches(parameter_editor, should_display=True) as (window, mock_display):
            root = cast("_DummyTkRoot", window.root)
            popup_calls = [call for call in root.after.call_args_list if call.args[0] == 100]
            assert len(popup_calls) == 1
            popup_callback = popup_calls[0].args[1]
            popup_callback()
            mock_display.assert_called_once_with(root)

    def test_usage_popup_not_scheduled_when_disabled(self, parameter_editor: MagicMock) -> None:
        """Preference disabling the popup prevents the helper from being scheduled."""
        with self._window_with_common_patches(parameter_editor, should_display=False) as (window, mock_display):
            root = cast("_DummyTkRoot", window.root)
            assert all(call.args[0] != 100 for call in root.after.call_args_list)
            mock_display.assert_not_called()


class TestRunLoop:
    """Ensure the run helper starts Tk's event loop."""

    def test_run_enters_mainloop(self, parameter_editor_window: ParameterEditorWindow) -> None:
        parameter_editor_window.root.mainloop = MagicMock()

        result = parameter_editor_window.run()

        parameter_editor_window.root.mainloop.assert_called_once_with()
        assert result is ParameterEditorAction.FINISHED

    def test_standalone_harness_handles_edit_components_action(self) -> None:
        """The standalone module reopens the component editor and rebuilds its parameter model."""
        events: list[str] = []
        models = [MagicMock(current_file="04_board_orientation.param"), MagicMock(current_file="12_battery.param")]
        model_iterator = iter(models)
        windows = [MagicMock(), MagicMock()]
        windows[0].run.side_effect = lambda: (
            setattr(models[0], "current_file", "12_battery.param") or ParameterEditorAction.EDIT_COMPONENTS
        )
        windows[1].run.return_value = ParameterEditorAction.FINISHED
        component_window = MagicMock()
        component_window.root.mainloop.side_effect = lambda: events.append("component editor")
        flight_controller = MagicMock()
        filesystem = MagicMock(vehicle_type="ArduCopter")

        with (
            patch.object(
                parameter_editor_module,
                "ParameterEditor",
                side_effect=lambda *_args: next(model_iterator),
            ) as make_model,
            patch.object(parameter_editor_module, "ParameterEditorWindow", side_effect=windows),
            patch.object(parameter_editor_module, "ComponentEditorWindow", return_value=component_window),
        ):
            parameter_editor_module.run_standalone_parameter_editor(flight_controller, filesystem)

        assert [call.args[0] for call in make_model.call_args_list] == [
            "04_board_orientation.param",
            "12_battery.param",
        ]
        component_window.set_vehicle_type_and_version.assert_called_once_with(
            "ArduCopter", flight_controller.info.flight_sw_version_and_type
        )
        component_window.populate_frames.assert_called_once_with()
        assert events == ["component editor"]


class TestWidgetFactoryMethods:
    """Cover the widget factory helpers inside the parameter editor window."""

    @pytest.mark.parametrize(
        ("is_fc_connected", "expected_state"),
        [(True, "normal"), (False, "disabled")],
    )
    def test_fc_banner_button_reflects_connection_state(
        self,
        parameter_editor: MagicMock,
        is_fc_connected: bool,
        expected_state: str,
    ) -> None:
        """
        FC banner button is available only when the flight controller is connected.

        GIVEN: The parameter editor reports a connected or disconnected flight controller
        WHEN: Configuration widgets are created
        THEN: The FC banner button has the matching enabled state
        """
        editor = _create_editor(parameter_editor)
        editor.main_frame = MagicMock()
        parameter_editor.is_fc_connected = is_fc_connected
        parameter_editor.parameter_files.return_value = ["01_initial.param"]
        parameter_editor.get_vehicle_directory.return_value = "vehicle_dir"

        directory_widget = MagicMock()
        button_widgets: dict[Callable[..., None], MagicMock] = {}

        def create_button(_parent: object, *, command: Callable[..., None], **_kwargs: object) -> MagicMock:
            button = MagicMock()
            button_widgets[command] = button
            return button

        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ttk.Frame", return_value=MagicMock()),
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ttk.Label", return_value=MagicMock()),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.get_widget_font_family_and_size",
                return_value=("TkDefaultFont", 10),
            ),
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ttk.Style"),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.VehicleDirectorySelectionWidgets",
                return_value=directory_widget,
            ),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.AutoResizeCombobox",
                return_value=MagicMock(),
            ),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ttk.Button",
                side_effect=create_button,
            ),
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.show_tooltip"),
            patch.object(
                ParameterEditorWindow,
                "put_image_in_label",
                return_value=MagicMock(pack=MagicMock(), bind=MagicMock()),
            ),
        ):
            editor._create_conf_widgets("__VERSION__")

        button_widgets[editor.on_fc_banner_click].configure.assert_called_once_with(state=expected_state)
        button_widgets[editor.on_zip_vehicle_for_forum_help_click].configure.assert_called_once_with(state="normal")

    def test_user_can_open_the_flight_controller_banner(self, parameter_editor_window: ParameterEditorWindow) -> None:
        """
        User can open the latest flight-controller banner from the parameter editor.

        GIVEN: Captured banner text is available in the data model
        WHEN: User clicks the FC banner action
        THEN: A banner window opens with the captured text
        """
        banner_text = ["ArduCopter V4.5.0", "ChibiOS: abc1234"]
        parameter_editor_window.parameter_editor.get_fc_banner_text.return_value = banner_text

        with patch(
            "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.FlightControllerBannerWindow"
        ) as banner_window:
            parameter_editor_window.on_fc_banner_click()

        banner_window.assert_called_once_with(
            parameter_editor_window.root,
            banner_text,
            parameter_editor_window.parameter_editor.get_fc_status_text.return_value,
            parameter_editor_window.parameter_editor.fc_parameters,
            status_text_provider=parameter_editor_window.parameter_editor.poll_fc_status_text,
            navigation_lock=parameter_editor_window.navigation_lock,
        )

    @pytest.mark.parametrize("parent_exists", [True, False])
    def test_diagnostics_pauses_plugin_receivers_until_closed(
        self, parameter_editor_window: ParameterEditorWindow, parent_exists: bool
    ) -> None:
        """GIVEN a polling plugin, WHEN diagnostics opens, THEN polling stops and resumes only after closing."""
        editor = parameter_editor_window
        plugin = MagicMock(spec=["on_deactivate", "on_activate"])
        editor.current_plugin_view = plugin
        editor.root.winfo_exists.return_value = parent_exists
        popup = MagicMock()

        def create_banner(*_args: object, **_kwargs: object) -> MagicMock:
            plugin.on_deactivate.assert_called_once_with()
            return popup

        def wait_for_close(_root: object) -> None:
            plugin.on_deactivate.assert_called_once_with()
            plugin.on_activate.assert_not_called()

        editor.root.wait_window.side_effect = wait_for_close
        with patch.object(parameter_editor_module, "FlightControllerBannerWindow", side_effect=create_banner):
            editor.on_fc_banner_click()

        editor.root.wait_window.assert_called_once_with(popup.root)
        if parent_exists:
            plugin.on_activate.assert_called_once_with()
        else:
            plugin.on_activate.assert_not_called()

    def test_plugin_receiver_resumes_when_diagnostics_cannot_open(
        self, parameter_editor_window: ParameterEditorWindow
    ) -> None:
        """GIVEN a polling plugin, WHEN popup creation fails, THEN plugin monitoring can continue."""
        editor = parameter_editor_window
        plugin = MagicMock(spec=["on_deactivate", "on_activate"])
        editor.current_plugin_view = plugin
        editor.root.winfo_exists.return_value = True
        with (
            patch.object(parameter_editor_module, "FlightControllerBannerWindow", side_effect=tk.TclError("closed")),
            pytest.raises(tk.TclError, match="closed"),
        ):
            editor.on_fc_banner_click()

        plugin.on_deactivate.assert_called_once_with()
        plugin.on_activate.assert_called_once_with()

    @pytest.mark.parametrize("partial_hook", ["on_suspend", "on_resume"])
    def test_incomplete_suspend_interface_keeps_legacy_plugin_safety_cleanup(
        self, parameter_editor_window: ParameterEditorWindow, partial_hook: str
    ) -> None:
        """
        Incomplete optional hooks must not bypass existing safety cleanup.

        GIVEN: A plugin with only one of the optional suspend/resume hooks
        WHEN: Diagnostics opens and closes
        THEN: Both legacy lifecycle hooks run and the incomplete optional hook is ignored
        """
        editor = parameter_editor_window
        plugin = MagicMock(spec=["on_deactivate", "on_activate", partial_hook])
        editor.current_plugin_view = plugin
        editor.root.winfo_exists.return_value = True
        with patch.object(parameter_editor_module, "FlightControllerBannerWindow"):
            editor.on_fc_banner_click()
        plugin.on_deactivate.assert_called_once_with()
        plugin.on_activate.assert_called_once_with()
        getattr(plugin, partial_hook).assert_not_called()

    @pytest.mark.parametrize("plugin_replaced", [False, True])
    def test_suspended_plugin_does_not_resume_after_parent_or_plugin_is_removed(
        self, parameter_editor_window: ParameterEditorWindow, plugin_replaced: bool
    ) -> None:
        """
        Diagnostics must not restart receivers for a removed view.

        GIVEN: A plugin offering state-preserving suspend/resume hooks
        WHEN: The parent closes or the plugin is replaced while diagnostics is open
        THEN: The old view remains suspended and legacy lifecycle hooks do not run
        """
        editor = parameter_editor_window
        plugin = MagicMock(spec=["on_suspend", "on_resume", "on_deactivate", "on_activate"])
        editor.current_plugin_view = plugin
        editor.root.winfo_exists.return_value = plugin_replaced

        def remove_owner(_root: object) -> None:
            if plugin_replaced:
                editor.current_plugin_view = None

        editor.root.wait_window.side_effect = remove_owner
        with patch.object(parameter_editor_module, "FlightControllerBannerWindow"):
            editor.on_fc_banner_click()
        plugin.on_suspend.assert_called_once_with(PluginPauseReason.EXCLUSIVE_OPERATION)
        plugin.on_resume.assert_not_called()
        plugin.on_deactivate.assert_not_called()
        plugin.on_activate.assert_not_called()

    def test_busy_controller_does_not_pause_plugin_or_open_diagnostics(
        self, parameter_editor_window: ParameterEditorWindow
    ) -> None:
        """GIVEN an FC operation in progress, WHEN diagnostics is requested, THEN the existing owner continues."""
        editor = parameter_editor_window
        plugin = MagicMock(spec=["on_deactivate", "on_activate"])
        editor.current_plugin_view = plugin
        editor.navigation_lock.acquire(plugin)
        with patch.object(parameter_editor_module, "FlightControllerBannerWindow") as banner_window:
            editor.on_fc_banner_click()

        banner_window.assert_not_called()
        plugin.on_deactivate.assert_not_called()
        plugin.on_activate.assert_not_called()

    @pytest.mark.parametrize("plugin_hooks", [("on_suspend", "on_resume"), ("on_deactivate", "on_activate")])
    def test_diagnostics_is_refused_while_file_browser_is_open(
        self, parameter_editor_window: ParameterEditorWindow, plugin_hooks: tuple[str, str]
    ) -> None:
        """
        Keep diagnostics from consuming replies intended for the flight-controller file browser.

        GIVEN: The file browser is open without holding the navigation lock, as on macOS
        WHEN: The user requests diagnostics
        THEN: The browser stays open, no diagnostics reader starts, and the plugin keeps running
        """
        editor = parameter_editor_window
        browser = MagicMock()
        browser.root.winfo_exists.return_value = True
        editor._file_browser_window = browser
        plugin = MagicMock(spec=plugin_hooks)
        editor.current_plugin_view = plugin
        assert not editor.navigation_lock.locked

        with patch.object(parameter_editor_module, "FlightControllerBannerWindow") as banner_window:
            editor.on_fc_banner_click()

        banner_window.assert_not_called()
        editor.root.wait_window.assert_not_called()
        editor.parameter_editor.get_fc_banner_text.assert_not_called()
        editor.parameter_editor.poll_fc_status_text.assert_not_called()
        editor.ui.show_error.assert_called_once_with(
            "File browser is open",
            "Close the flight-controller file browser before opening diagnostics.",
        )
        browser.root.destroy.assert_not_called()
        assert editor._file_browser_window is browser
        assert not plugin.mock_calls
        assert not editor.navigation_lock.locked

    @pytest.mark.parametrize("browser_destroyed", [False, True])
    def test_user_can_open_diagnostics_after_file_browser_is_destroyed(
        self, parameter_editor_window: ParameterEditorWindow, browser_destroyed: bool
    ) -> None:
        """
        A stale browser reference must not prevent diagnostics from opening.

        GIVEN: The file browser has closed but the editor still references its window
        WHEN: The user requests diagnostics and Tk reports a missing window or interpreter
        THEN: Diagnostics opens without reporting that the file browser is open
        """
        editor = parameter_editor_window
        browser = MagicMock()
        browser.root.winfo_exists.return_value = False
        if browser_destroyed:
            browser.root.winfo_exists.side_effect = tk.TclError("application has been destroyed")
        editor._file_browser_window = browser

        with patch.object(parameter_editor_module, "FlightControllerBannerWindow") as banner_window:
            editor.on_fc_banner_click()

        banner_window.assert_called_once()
        editor.root.wait_window.assert_called_once_with(banner_window.return_value.root)
        editor.ui.show_error.assert_not_called()
        if browser_destroyed:
            assert editor._file_browser_window is None

    def test_create_conf_widgets_configures_combobox(self, parameter_editor: MagicMock) -> None:
        editor = _create_editor(parameter_editor)
        editor.main_frame = MagicMock()
        editor.gui_complexity = "normal"
        parameter_editor.parameter_files.return_value = ["01_initial.param"]
        parameter_editor.current_file = "01_initial.param"
        parameter_editor.get_vehicle_directory.return_value = "vehicle_dir"

        directory_widget = MagicMock()
        directory_widget.container_frame = MagicMock()

        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ttk.Frame", return_value=MagicMock()),
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ttk.Label", return_value=MagicMock()),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.VehicleDirectorySelectionWidgets",
                return_value=directory_widget,
            ) as mock_dir_widgets,
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.AutoResizeCombobox",
                return_value=MagicMock(),
            ) as mock_combobox,
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.show_tooltip"),
            patch.object(
                ParameterEditorWindow,
                "put_image_in_label",
                return_value=MagicMock(pack=MagicMock(), bind=MagicMock()),
            ),
        ):
            editor._create_conf_widgets("__VERSION__")

        mock_dir_widgets.assert_called_once()
        mock_combobox.assert_called_once()
        mock_combobox.return_value.bind.assert_called_once_with(
            "<<ComboboxSelected>>",
            editor.on_param_file_combobox_change,
        )

    def test_simple_gui_skips_checkbox_tooltips(self, parameter_editor: MagicMock) -> None:
        editor = _create_editor(parameter_editor)
        editor.main_frame = MagicMock()
        editor.gui_complexity = "simple"
        parameter_editor.parameter_documentation_available.return_value = True

        parameter_table = MagicMock(pack=MagicMock())
        only_changed_checkbox = MagicMock(pack=MagicMock())
        annotate_checkbox = MagicMock(pack=MagicMock())

        with (
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ProgramSettings.get_setting",
                return_value=False,
            ),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ParameterEditorTable",
                return_value=parameter_table,
            ),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ttk.Frame",
                return_value=MagicMock(pack=MagicMock()),
            ),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ttk.Checkbutton",
                side_effect=[only_changed_checkbox, annotate_checkbox],
            ),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ttk.Button",
                return_value=MagicMock(configure=MagicMock(), pack=MagicMock()),
            ),
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.show_tooltip") as mock_tooltip,
            patch.object(ParameterEditorWindow, "repopulate_parameter_table"),
        ):
            editor._create_parameter_area_widgets()

        only_changed_checkbox.pack.assert_not_called()
        annotate_checkbox.pack.assert_not_called()
        for call in mock_tooltip.call_args_list:
            assert call.args[0] is not only_changed_checkbox
            assert call.args[0] is not annotate_checkbox

    def test_update_inline_component_editor_hides_container_when_component_is_removed(
        self, parameter_editor: MagicMock
    ) -> None:
        editor = _create_editor(parameter_editor)
        editor.inline_component_container = MagicMock(
            pack=MagicMock(), pack_forget=MagicMock(), winfo_children=MagicMock(return_value=[]), configure=MagicMock()
        )
        editor._inline_component_name = "Motor"
        editor.inline_component_editor = MagicMock()

        editor._update_inline_component_editor(None)

        editor.inline_component_container.pack_forget.assert_called_once()
        editor.inline_component_container.configure.assert_called_once_with(text="")
        assert editor.inline_component_editor is None
        assert editor._inline_component_name is None

    def test_create_parameter_area_widgets_sets_skip_button_state(self, parameter_editor: MagicMock) -> None:
        editor = _create_editor(parameter_editor)
        editor.main_frame = MagicMock()
        editor.gui_complexity = "simple"
        parameter_editor.parameter_documentation_available.return_value = True
        parameter_editor.is_fc_connected = True
        parameter_editor.is_mavftp_supported = False
        parameter_editor.is_configuration_step_optional.return_value = False

        parameter_table = MagicMock(pack=MagicMock())

        with (
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ProgramSettings.get_setting",
                side_effect=lambda _key: False,
            ),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ParameterEditorTable",
                return_value=parameter_table,
            ),
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ttk.Frame", return_value=MagicMock()),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ttk.Checkbutton",
                return_value=MagicMock(pack=MagicMock()),
            ),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ttk.Button",
                return_value=MagicMock(configure=MagicMock(), pack=MagicMock()),
            ) as mock_button,
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.show_tooltip"),
            patch.object(ParameterEditorWindow, "repopulate_parameter_table"),
        ):
            editor._create_parameter_area_widgets()

        mock_button.return_value.configure.assert_called_with(state="disabled")


class TestAnalyseLogClick:
    """Cover the on_analyse_log_click."""

    def test_user_cancels_file_dialog_returns_early(self, parameter_editor_window: ParameterEditorWindow) -> None:
        parameter_editor_window.ui.askopenfilename = MagicMock(return_value="")

        with patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.threading.Thread") as mock_thread:
            parameter_editor_window.on_analyse_log_click()

        # Assert
        mock_thread.assert_not_called()
        parameter_editor_window.ui.show_error.assert_not_called()

    def test_analysis_failure_shows_error_dialog(self, parameter_editor_window: ParameterEditorWindow) -> None:
        # Arrange
        parameter_editor_window.ui.askopenfilename = MagicMock(return_value="/fake/log.bin")

        # Capture the run_analysis closure from the thread constructor
        captured_targets: list = []

        def fake_thread(target: object, **_kwargs: object) -> MagicMock:
            captured_targets.append(target)
            t = MagicMock()
            t.is_alive.return_value = False
            return t

        with (
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.threading.Thread",
                side_effect=fake_thread,
            ),
        ):
            parameter_editor_window.ui.extract_log_data = MagicMock(side_effect=RuntimeError("bad log"))
            parameter_editor_window.on_analyse_log_click()

            # run_analysis runs in a thread normally
            assert len(captured_targets) == 1
            captured_targets[0]()

            # check_done was scheduled via root.after
            check_done = parameter_editor_window.root.after.call_args_list[-1].args[1]
            check_done()

        # Assert
        parameter_editor_window.ui.show_error.assert_called_once()
        assert "Log Analysis Error" in parameter_editor_window.ui.show_error.call_args.args[0]
        parameter_editor_window._test_progress_windows[0].destroy.assert_called_once()  # type: ignore[attr-defined]

    def test_analysis_success_opens_report_window(self, parameter_editor_window: ParameterEditorWindow) -> None:
        # Arrange
        parameter_editor_window.ui.askopenfilename = MagicMock(return_value="/fake/log.bin")
        fake_summary = MagicMock()

        captured_targets: list = []

        def fake_thread(target: object, **_kwargs: object) -> MagicMock:
            captured_targets.append(target)
            t = MagicMock()
            t.is_alive.return_value = False
            return t

        with (
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.threading.Thread",
                side_effect=fake_thread,
            ),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.LogAvailabilityReportWindow"
            ) as mock_report,
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.UsagePopupWindow.should_display",
                return_value=False,
            ),
        ):
            log_data = _log_data()
            parameter_editor_window.ui.extract_log_data = MagicMock(return_value=log_data)
            parameter_editor_window.ui.analyze_log_data = MagicMock(return_value=fake_summary)
            parameter_editor_window.on_analyse_log_click()

            assert len(captured_targets) == 1
            captured_targets[0]()

            check_done = parameter_editor_window.root.after.call_args_list[-1].args[1]
            check_done()

        # Assert — report window opened with correct args
        mock_report.assert_called_once_with(
            parameter_editor_window.root,
            fake_summary,
            parameter_editor_window.parameter_editor.get_vehicle_directory(),
            is_fc_connected=True,
            upload_callback=parameter_editor_window.upload_selected_params,
            navigate_callback=parameter_editor_window._navigate_to_config_step,
            report=None,
        )
        mock_report.return_value.run.assert_not_called()
        parameter_editor_window._test_progress_windows[0].destroy.assert_called_once()  # type: ignore[attr-defined]
        parameter_editor_window.ui.show_error.assert_not_called()
        parameter_editor_window.ui.extract_log_data.assert_called_once()
        assert parameter_editor_window.ui.extract_log_data.call_args.args[0] == "/fake/log.bin"
        parameter_editor_window.ui.analyze_log_data.assert_called_once_with(
            log_data,
            project_vehicle_type="ArduPlane",
            project_firmware_version="4.5.5",
            vehicle_components={},
            configuration_steps={"project_step.param": {}},
            apm_doc={"LOG_BITMASK": {"fields": {"Bitmask": "9:Battery Monitor"}}},
            validate_project=False,
        )

    def test_analysis_progress_switches_to_determinate_mode(self, parameter_editor_window: ParameterEditorWindow) -> None:
        """The extraction progress callback should turn the scan window into a standard progress bar."""
        parameter_editor_window.ui.askopenfilename = MagicMock(return_value="/fake/log.bin")
        fake_summary = MagicMock()
        log_data = _log_data()
        captured_progress_callbacks: list = []

        def fake_extract(_filepath: str, progress_callback: Callable[[int, int], None] | None = None) -> LogData:
            captured_progress_callbacks.append(progress_callback)
            if progress_callback is not None:
                progress_callback(2, 10)
            return log_data

        captured_targets: list = []

        def fake_thread(target: object, **_kwargs: object) -> MagicMock:
            captured_targets.append(target)
            t = MagicMock()
            t.is_alive.return_value = False
            return t

        with (
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.threading.Thread",
                side_effect=fake_thread,
            ),
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.LogAvailabilityReportWindow"),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.UsagePopupWindow.should_display",
                return_value=False,
            ),
        ):
            parameter_editor_window.ui.extract_log_data = MagicMock(side_effect=fake_extract)
            parameter_editor_window.ui.analyze_log_data = MagicMock(return_value=fake_summary)
            parameter_editor_window.on_analyse_log_click()
            captured_targets[0]()

            check_done = next(
                c.args[1] for c in reversed(parameter_editor_window.root.after.call_args_list) if c.args[0] == 100
            )
            check_done()

        progress = parameter_editor_window._test_progress_windows[0]  # type: ignore[attr-defined]
        progress.progress_bar.stop.assert_called_once()
        progress.progress_bar.configure.assert_any_call(mode="determinate")
        progress.update_progress_bar.assert_called_once_with(2, 10)
        assert captured_progress_callbacks[0] is not None

    def test_analysis_rejects_log_from_different_vehicle_type(self, parameter_editor_window: ParameterEditorWindow) -> None:
        """A log from a different vehicle type should stop before full log extraction."""
        parameter_editor_window.ui.askopenfilename = MagicMock(return_value="/fake/log.bin")
        parameter_editor_window.ui.ask_yesno = MagicMock(return_value=False)
        parameter_editor_window.parameter_editor.get_log_analysis_context_inputs.return_value = LogAnalysisInputs(
            project_vehicle_type="ArduCopter",
            project_firmware_version="4.5.5",
            vehicle_components={},
            configuration_steps={},
            apm_doc=None,
        )

        captured_targets: list = []

        def fake_thread(target: object, **_kwargs: object) -> MagicMock:
            captured_targets.append(target)
            t = MagicMock()
            t.is_alive.return_value = False
            return t

        with patch(
            "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.threading.Thread",
            side_effect=fake_thread,
        ):
            parameter_editor_window.on_analyse_log_click()
            captured_targets[0]()
            check_done = parameter_editor_window.root.after.call_args_list[-1].args[1]
            check_done()

        parameter_editor_window._test_progress_windows[0].destroy.assert_called_once()  # type: ignore[attr-defined]
        parameter_editor_window.ui.ask_yesno.assert_called_once()
        message = parameter_editor_window.ui.ask_yesno.call_args.args[1]
        assert "selected log is from ArduPlane" in message
        assert "currently open vehicle is ArduCopter" in message
        parameter_editor_window.ui.analyze_log_data.assert_not_called()

    def test_analysis_rejects_log_from_different_firmware_version(
        self, parameter_editor_window: ParameterEditorWindow
    ) -> None:
        """A log from a different firmware version should stop before full log extraction."""
        parameter_editor_window.ui.askopenfilename = MagicMock(return_value="/fake/log.bin")
        parameter_editor_window.ui.ask_yesno = MagicMock(return_value=False)
        parameter_editor_window.parameter_editor.get_log_analysis_context_inputs.return_value = LogAnalysisInputs(
            project_vehicle_type="ArduPlane",
            project_firmware_version="4.6.0",
            vehicle_components={},
            configuration_steps={},
            apm_doc=None,
        )

        captured_targets = []

        def fake_thread(target: object, **_kwargs: object) -> MagicMock:
            captured_targets.append(target)
            t = MagicMock()
            t.is_alive.return_value = False
            return t

        with patch(
            "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.threading.Thread",
            side_effect=fake_thread,
        ):
            parameter_editor_window.on_analyse_log_click()
            captured_targets[0]()
            check_done = parameter_editor_window.root.after.call_args_list[-1].args[1]
            check_done()

        parameter_editor_window._test_progress_windows[0].destroy.assert_called_once()  # type: ignore[attr-defined]
        parameter_editor_window.ui.ask_yesno.assert_called_once()
        message = parameter_editor_window.ui.ask_yesno.call_args.args[1]
        assert "selected log firmware version is 4.5.5" in message
        assert "currently open vehicle firmware version is 4.6.0" in message
        parameter_editor_window.ui.analyze_log_data.assert_not_called()

    def test_analysis_mismatch_loads_log_metadata_before_analysis(
        self, parameter_editor_window: ParameterEditorWindow
    ) -> None:
        """A user-approved mismatch should load log firmware metadata through UI services."""
        parameter_editor_window.ui.askopenfilename = MagicMock(return_value="/fake/log.bin")
        parameter_editor_window.ui.ask_yesno = MagicMock(return_value=True)
        parameter_editor_window.ui.extract_log_data = MagicMock(return_value=_log_data("ArduCopter", (4, 6, 3)))
        parameter_editor_window.ui.load_apm_doc = MagicMock(return_value={"LOG_BITMASK": {"fields": {"Bitmask": "9:Battery"}}})
        parameter_editor_window.ui.analyze_log_data = MagicMock(return_value=MagicMock())
        parameter_editor_window.parameter_editor.get_vehicle_directory.return_value = "C:/vehicle"
        parameter_editor_window.parameter_editor.get_log_analysis_context_inputs.side_effect = [
            LogAnalysisInputs("ArduPlane", "4.5.5", {}, {}, None),
            LogAnalysisInputs("ArduPlane", "4.5.5", {}, {}, {"LOG_BITMASK": {}}),
        ]

        captured_targets = []

        def fake_thread(target: object, **_kwargs: object) -> MagicMock:
            captured_targets.append(target)
            t = MagicMock()
            t.is_alive.return_value = False
            return t

        with (
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.threading.Thread",
                side_effect=fake_thread,
            ) as mock_thread,
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.LogAvailabilityReportWindow"),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.UsagePopupWindow.should_display",
                return_value=False,
            ),
        ):
            parameter_editor_window.on_analyse_log_click()
            captured_targets[0]()
            check_done = parameter_editor_window.root.after.call_args_list[-1].args[1]
            check_done()

        parameter_editor_window.ui.load_apm_doc.assert_called_once_with("C:/vehicle", "ArduCopter", "4.6.3")
        parameter_editor_window.parameter_editor.get_log_analysis_context_inputs.assert_any_call(
            apm_doc={"LOG_BITMASK": {"fields": {"Bitmask": "9:Battery"}}}
        )
        assert parameter_editor_window._test_progress_windows[0].destroy.call_count == 1  # type: ignore[attr-defined]
        assert parameter_editor_window._test_progress_windows[1].destroy.call_count == 1  # type: ignore[attr-defined]
        mock_thread.assert_called_once()

    def test_analysis_mismatch_metadata_failure_destroys_each_progress_once(
        self, parameter_editor_window: ParameterEditorWindow
    ) -> None:
        """Metadata load failures should not double-destroy the replaced progress window."""
        parameter_editor_window.ui.askopenfilename = MagicMock(return_value="/fake/log.bin")
        parameter_editor_window.ui.ask_yesno = MagicMock(return_value=True)
        parameter_editor_window.ui.extract_log_data = MagicMock(return_value=_log_data("ArduCopter", (4, 6, 3)))
        parameter_editor_window.ui.load_apm_doc = MagicMock(side_effect=RuntimeError("metadata unavailable"))
        parameter_editor_window.parameter_editor.get_vehicle_directory.return_value = "C:/vehicle"
        parameter_editor_window.parameter_editor.get_log_analysis_context_inputs.return_value = LogAnalysisInputs(
            "ArduPlane", "4.5.5", {}, {}, None
        )

        captured_targets = []

        def fake_thread(target: object, **_kwargs: object) -> MagicMock:
            captured_targets.append(target)
            t = MagicMock()
            t.is_alive.return_value = False
            return t

        with patch(
            "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.threading.Thread",
            side_effect=fake_thread,
        ):
            parameter_editor_window.on_analyse_log_click()
            captured_targets[0]()
            check_done = parameter_editor_window.root.after.call_args_list[-1].args[1]
            check_done()

        assert parameter_editor_window._test_progress_windows[0].destroy.call_count == 1  # type: ignore[attr-defined]
        assert parameter_editor_window._test_progress_windows[1].destroy.call_count == 1  # type: ignore[attr-defined]
        parameter_editor_window.ui.show_error.assert_called_once()
        parameter_editor_window.ui.analyze_log_data.assert_not_called()


class TestTemperatureCalibrationWorkflows:
    """Ensure IMU temperature calibration callbacks stay healthy."""

    def test_user_runs_tempcal_workflow_with_progress_feedback(
        self, parameter_editor_window: ParameterEditorWindow, parameter_editor: MagicMock
    ) -> None:
        progress_window = MagicMock()
        progress_window.update_progress_bar_300_pct = MagicMock()
        progress_window.destroy = MagicMock()
        parameter_editor_window.ui.create_progress_window = MagicMock(return_value=progress_window)

        def fake_workflow(  # pylint: disable=too-many-arguments
            selected_file: str,
            *,
            ask_user_confirmation: Callable[[str, str], bool],
            select_file: Callable[[str, list[str]], str | None],
            show_warning: Callable[[str, str], None],
            show_error: Callable[[str, str], None],
            get_progress_callback: Callable[[], Callable | None],
        ) -> bool:
            assert selected_file == "01_initial.param"
            assert ask_user_confirmation is parameter_editor_window.ui.ask_yesno
            assert callable(select_file)
            assert show_warning is parameter_editor_window.ui.show_warning
            assert callable(show_error)
            callback = get_progress_callback()
            assert callback is progress_window.update_progress_bar_300_pct
            assert callback is not None
            callback(10, 30)
            return True

        parameter_editor.handle_imu_temperature_calibration_workflow.side_effect = fake_workflow

        parameter_editor_window._do_tempcal_imu("01_initial.param")

        parameter_editor_window.ui.create_progress_window.assert_called_once()
        progress_window.destroy.assert_called_once()
        assert parameter_editor_window._tempcal_imu_progress_window is None

    def test_user_closes_tempcal_window_even_when_workflow_errors(
        self, parameter_editor_window: ParameterEditorWindow, parameter_editor: MagicMock
    ) -> None:
        progress_window = MagicMock()
        progress_window.update_progress_bar_300_pct = MagicMock()
        progress_window.destroy = MagicMock()
        parameter_editor_window.ui.create_progress_window = MagicMock(return_value=progress_window)

        def failing_workflow(  # pylint: disable=too-many-arguments
            selected_file: str,
            *,
            ask_user_confirmation: Callable[[str, str], bool],
            select_file: Callable[[str, list[str]], str | None],
            show_warning: Callable[[str, str], None],
            show_error: Callable[[str, str], None],
            get_progress_callback: Callable[[], Callable | None],
        ) -> bool:
            assert selected_file == "01_initial.param"
            assert ask_user_confirmation is parameter_editor_window.ui.ask_yesno
            assert callable(select_file)
            assert show_warning is parameter_editor_window.ui.show_warning
            assert callable(show_error)
            callback = get_progress_callback()
            assert callback is progress_window.update_progress_bar_300_pct
            assert callback is not None
            callback(1, 3)
            msg = "boom"
            raise RuntimeError(msg)

        parameter_editor.handle_imu_temperature_calibration_workflow.side_effect = failing_workflow

        with pytest.raises(RuntimeError):
            parameter_editor_window._do_tempcal_imu("01_initial.param")

        progress_window.destroy.assert_called_once()
        assert parameter_editor_window._tempcal_imu_progress_window is None


class TestFileUploadHelpers:
    """Validate upload helper plumbing."""

    def test_user_triggers_upload_progress_feedback(
        self, parameter_editor_window: ParameterEditorWindow, parameter_editor: MagicMock
    ) -> None:
        progress_window = MagicMock()
        progress_window.update_progress_bar = MagicMock()
        progress_window.destroy = MagicMock()
        parameter_editor_window.ui.create_progress_window = MagicMock(return_value=progress_window)

        def fake_upload(
            selected_file: str,
            *,
            ask_confirmation: Callable[[str, str], bool],
            show_error: Callable[[str, str], None],
            show_warning: Callable[[str, str], None],
            get_progress_callback: Callable[[], Callable | None],
            **_execution: object,
        ) -> bool:
            assert selected_file == "01_initial.param"
            assert callable(ask_confirmation)
            assert callable(show_error)
            assert show_warning is parameter_editor_window.ui.show_warning
            callback = get_progress_callback()
            assert callback is not None
            callback(5, 10)
            snapshot = progress_window.update_transfer_progress.call_args.args[0]
            assert snapshot.transferred_bytes == 5
            assert snapshot.total_bytes == 10
            assert snapshot.direction.name == "UPLOAD"
            return True

        parameter_editor.should_upload_file_to_fc_workflow.side_effect = fake_upload

        assert parameter_editor_window._should_upload_file_to_fc("01_initial.param") is True

        parameter_editor_window.ui.create_progress_window.assert_called_once()
        progress_window.destroy.assert_called_once()
        assert parameter_editor_window.file_upload_progress_window is None

    def test_user_still_cleans_upload_progress_window_on_error(
        self, parameter_editor_window: ParameterEditorWindow, parameter_editor: MagicMock
    ) -> None:
        progress_window = MagicMock()
        progress_window.update_progress_bar = MagicMock()
        progress_window.destroy = MagicMock()
        parameter_editor_window.ui.create_progress_window = MagicMock(return_value=progress_window)
        parameter_editor_window.ui.ask_retry_cancel = MagicMock(return_value=False)

        def failing_upload(
            selected_file: str,
            *,
            ask_confirmation: Callable[[str, str], bool],
            show_error: Callable[[str, str], None],
            show_warning: Callable[[str, str], None],
            get_progress_callback: Callable[[], Callable | None],
            **_execution: object,
        ) -> None:
            assert selected_file == "01_initial.param"
            assert callable(ask_confirmation)
            assert callable(show_error)
            assert show_warning is parameter_editor_window.ui.show_warning
            callback = get_progress_callback()
            assert callback is not None
            callback(1, 2)
            msg = "boom"
            raise RuntimeError(msg)

        parameter_editor.should_upload_file_to_fc_workflow.side_effect = failing_upload

        assert parameter_editor_window._should_upload_file_to_fc("01_initial.param") is False

        parameter_editor_window.ui.ask_retry_cancel.assert_called_once()
        parameter_editor_window.ui.show_error.assert_not_called()
        progress_window.destroy.assert_called_once()
        assert parameter_editor_window.file_upload_progress_window is None

    def test_user_can_retry_file_upload_after_reported_failure(
        self, parameter_editor_window: ParameterEditorWindow, parameter_editor: MagicMock
    ) -> None:
        first_progress_window = MagicMock(update_progress_bar=MagicMock(), destroy=MagicMock())
        second_progress_window = MagicMock(update_progress_bar=MagicMock(), destroy=MagicMock())
        parameter_editor_window.ui.create_progress_window = MagicMock(
            side_effect=[first_progress_window, second_progress_window]
        )
        parameter_editor_window.ui.ask_retry_cancel = MagicMock(return_value=True)
        parameter_editor.should_upload_file_to_fc_workflow.side_effect = [False, True]

        assert parameter_editor_window._should_upload_file_to_fc("01_initial.param") is True

        assert parameter_editor.should_upload_file_to_fc_workflow.call_count == 2
        parameter_editor_window.ui.ask_retry_cancel.assert_called_once()
        first_progress_window.destroy.assert_not_called()  # No progress callback was requested on this attempt.
        second_progress_window.destroy.assert_not_called()  # No progress callback was requested on this attempt.
        assert parameter_editor_window.file_upload_progress_window is None


class TestProgressBarUpdates:
    """Cover per-file progress tracking."""

    def test_user_updates_stage_progress_bar(self, parameter_editor_window: ParameterEditorWindow) -> None:
        param_editor_mock = cast("MagicMock", parameter_editor_window.parameter_editor)
        param_editor_mock.configuration_phases.return_value = True

        parameter_editor_window._update_progress_bar_from_file("05_stage.param")

        stage_bar = cast("MagicMock", parameter_editor_window.stage_progress_bar)
        stage_bar.update_progress.assert_called_once_with(5)

    def test_user_gets_feedback_when_filename_prefix_missing_digits(
        self, parameter_editor_window: ParameterEditorWindow
    ) -> None:
        param_editor_mock = cast("MagicMock", parameter_editor_window.parameter_editor)
        param_editor_mock.configuration_phases.return_value = True

        with patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.logging_error") as mock_error:
            parameter_editor_window._update_progress_bar_from_file("XX_invalid.param")

        mock_error.assert_called_once()


class TestParameterDownloads:
    """Exercise FC parameter download flows."""

    @pytest.mark.parametrize("worker_download", [False, True], ids=["synchronous", "sequoia-worker"])
    @pytest.mark.parametrize("fails", [False, True], ids=["success", "failure"])
    def test_calibration_readback_keeps_controls_locked_until_completion(
        self,
        parameter_editor_window: ParameterEditorWindow,
        root: tk.Tk,
        monkeypatch: pytest.MonkeyPatch,
        worker_download: bool,
        fails: bool,
    ) -> None:
        """
        Calibration readback yields telemetry without releasing calibration ownership.

        GIVEN: Full accelerometer calibration has completed with navigation locked
        WHEN: Its parameter readback reports progress and succeeds or raises
        THEN: Calibration and upload remain blocked until readback and result handling finish
        """
        editor = parameter_editor_window
        editor.root = root
        model = MagicMock(spec=AccelerometerCalibrationDataModel)
        model.start_full_calibration.return_value = (True, "Started")
        view = AccelerometerCalibrationView(ttk.Frame(root), model, editor)
        editor.current_plugin_view = view
        backend = cast("MagicMock", editor.parameter_editor)
        backend.fc_parameters = {}
        progress_window = MagicMock()
        editor.ui.create_progress_window = MagicMock(return_value=progress_window)
        monkeypatch.setattr(parameter_editor_module, "is_macos_sequoia_or_older", lambda: worker_download)
        monkeypatch.setattr(tk.Misc, "update", lambda _self: None)
        monkeypatch.setattr(tk.Misc, "update_idletasks", lambda _self: None)

        def check_locked(*_args: object) -> None:
            assert editor.navigation_lock.locked
            assert view._simple_btn.instate(["disabled"])
            assert view._full_btn.instate(["disabled"])
            assert editor.upload_selected_params({"TEST": 1.0}) is False

        def check_paused(*args: object) -> None:
            check_locked(*args)
            assert view._imu_poll_job is None

        progress_window.update_progress_bar.side_effect = check_paused
        progress_window.destroy.side_effect = check_paused

        def download(get_progress: Callable[[], Callable], *, response_timeout: float | None) -> tuple[dict, dict]:
            assert response_timeout is None
            get_progress()(1, 2)
            if fails:
                message = "Calibration readback failed"
                raise OSError(message)
            return {"TEST": 1.0}, {}

        backend.download_flight_controller_parameters.side_effect = download
        try:
            view._on_start_full_calibration()
            with (
                pytest.raises(OSError, match="Calibration readback failed") if fails else nullcontext(),
                patch(
                    "ardupilot_methodic_configurator.plugins.frontend_tkinter_accelerometer_calibration.showinfo",
                    side_effect=check_locked,
                ) as show_result,
            ):
                view._end_full_calibration(success=True)

            assert show_result.call_count == (0 if fails else 1)
            progress_window.update_progress_bar.assert_called_once_with(1, 2)
            progress_window.destroy.assert_called_once()
            backend.upload_selected_params_workflow.assert_not_called()
            assert not editor.navigation_lock.locked
            assert view._simple_btn.instate(["!disabled"])
            assert view._full_btn.instate(["!disabled"])
            assert view._imu_poll_job is not None
        finally:
            view.master.destroy()

    @pytest.mark.parametrize("worker_download", [False, True], ids=["synchronous", "sequoia-worker"])
    @pytest.mark.parametrize("fails", [False, True], ids=["success", "failure"])
    def test_parameter_download_pauses_plugin_reception_until_cleanup(
        self,
        parameter_editor_window: ParameterEditorWindow,
        root: tk.Tk,
        monkeypatch: pytest.MonkeyPatch,
        worker_download: bool,
        fails: bool,
    ) -> None:
        """
        Preserve parameter replies while downloading with a telemetry plugin active.

        GIVEN: A plugin owns MAVLink reception and a parameter download is requested
        WHEN: The download reports progress, then succeeds or fails
        THEN: Plugin reception stays paused through progress cleanup and resumes on Tk
        """
        editor = parameter_editor_window
        editor.root = root
        ui_thread = get_ident()
        paused = Event()
        plugin = MagicMock(spec=["on_suspend", "on_resume"])

        def suspend(reason: PluginPauseReason) -> None:
            assert get_ident() == ui_thread
            assert reason is PluginPauseReason.EXCLUSIVE_OPERATION
            paused.set()

        def resume() -> None:
            assert get_ident() == ui_thread
            paused.clear()

        plugin.on_suspend.side_effect = suspend
        plugin.on_resume.side_effect = resume
        editor.current_plugin_view = plugin
        progress_window = MagicMock()
        progress_window.destroy.side_effect = lambda: paused.is_set() or pytest.fail("Plugin resumed before cleanup")
        editor.ui.create_progress_window = MagicMock(return_value=progress_window)
        monkeypatch.setattr(parameter_editor_module, "is_macos_sequoia_or_older", lambda: worker_download)
        monkeypatch.setattr(tk.Misc, "update", lambda _self: None)
        monkeypatch.setattr(tk.Misc, "update_idletasks", lambda _self: None)

        def download(get_progress: Callable[[], Callable], *, response_timeout: float | None) -> tuple[dict, dict]:
            assert paused.is_set(), "Plugin reception would consume parameter replies"
            assert (get_ident() != ui_thread) == worker_download
            assert response_timeout == 5.0
            get_progress()(1, 2)
            if fails:
                message = "Parameter download failed"
                raise RuntimeError(message)
            return {"TEST": 1.0}, {}

        cast("MagicMock", editor.parameter_editor).download_flight_controller_parameters.side_effect = download

        if fails:
            with pytest.raises(RuntimeError, match="Parameter download failed"):
                editor.download_flight_controller_parameters(redownload=True, response_timeout=5.0)
        else:
            assert editor.download_flight_controller_parameters(redownload=True, response_timeout=5.0) == ({"TEST": 1.0}, {})

        plugin.on_suspend.assert_called_once()
        plugin.on_resume.assert_called_once()
        assert not paused.is_set()
        progress_window.destroy.assert_called_once()
        assert editor._param_download_progress_window is None

    def test_user_downloads_parameters_with_progress_window(self, parameter_editor_window: ParameterEditorWindow) -> None:
        progress_window = MagicMock()
        progress_window.update_progress_bar = MagicMock()
        progress_window.destroy = MagicMock()
        parameter_editor_window.ui.create_progress_window = MagicMock(return_value=progress_window)
        parameter_editor_window.on_param_file_combobox_change = MagicMock()

        parameter_editor_window.download_flight_controller_parameters()

        parameter_editor_window.ui.create_progress_window.assert_called_once()
        progress_window.destroy.assert_called_once()
        parameter_editor_window.on_param_file_combobox_change.assert_called_once_with(None, forced=True)
        assert parameter_editor_window._param_download_progress_window is None

    def test_user_skips_table_refresh_on_redownload(self, parameter_editor_window: ParameterEditorWindow) -> None:
        parameter_editor_window.ui.create_progress_window = MagicMock()
        parameter_editor_window.on_param_file_combobox_change = MagicMock()

        parameter_editor_window.download_flight_controller_parameters(redownload=True)

        parameter_editor_window.on_param_file_combobox_change.assert_not_called()


class TestUploadSelectedParameters:
    """Cover progress-window lifecycle when uploading parameters."""

    def test_user_sees_progress_while_resetting_all_parameters_to_defaults(
        self, parameter_editor_window: ParameterEditorWindow
    ) -> None:
        reset_reconnect_progress_window = MagicMock()
        reset_reconnect_progress_window.update_progress_bar_with_message = MagicMock()
        download_progress_window = MagicMock()
        parameter_editor_window.ui.create_progress_window = MagicMock(
            side_effect=[reset_reconnect_progress_window, download_progress_window]
        )
        download_callback: Callable[[], Callable | None] | None = None

        def reset_and_download(*args: object) -> bool:
            nonlocal download_callback
            progress_callback = cast("Callable[[int, int], None]", args[1])
            download_callback = cast("Callable[[], Callable | None]", args[2])
            download_progress = download_callback()
            assert download_progress is not None
            download_progress(3, 4)
            progress_callback(10, 100)
            progress_callback(30, 100)
            progress_callback(90, 100)
            progress_callback(100, 100)
            return True

        parameter_editor_window.parameter_editor.reset_all_parameters_to_default.side_effect = reset_and_download
        parameter_editor_window.repopulate_parameter_table = MagicMock()

        result = parameter_editor_window.reset_all_parameters_to_default()

        assert result is True
        parameter_editor_window.ui.create_progress_window.assert_any_call(
            parameter_editor_window.root,
            "Restarting Flight Controller",
            "Reset command sent",
            True,  # noqa: FBT003
            auto_close_on_complete=False,
        )
        parameter_editor_window.ui.create_progress_window.assert_any_call(
            parameter_editor_window.root,
            "Re-downloading FC parameters",
            "Downloaded {} of {} parameters",
            False,  # noqa: FBT003
        )
        reset_reconnect_progress_window.update_progress_bar_with_message.assert_has_calls(
            [
                mock_call(10, 100, "Reset command sent"),
                mock_call(30, 100, "Reconnecting to flight controller"),
                mock_call(90, 100, "Retrieving flight controller information"),
                mock_call(100, 100, "Flight Controller connected"),
            ]
        )
        reset_reconnect_progress_window.destroy.assert_called_once_with()
        download_progress_window.destroy.assert_called_once_with()
        reset_call = parameter_editor_window.parameter_editor.reset_all_parameters_to_default.call_args
        assert callable(reset_call.args[0])
        assert callable(reset_call.args[1])
        assert reset_call.args[2] is download_callback
        parameter_editor_window.repopulate_parameter_table.assert_called_once_with()

    def test_user_sees_reset_and_download_progress_windows(self, parameter_editor_window: ParameterEditorWindow) -> None:
        reset_reconnect_window = MagicMock()
        reset_reconnect_window.update_progress_bar_with_message = MagicMock()
        reset_reconnect_window.destroy = MagicMock()
        download_window = MagicMock()
        download_window.update_progress_bar = MagicMock()
        download_window.destroy = MagicMock()
        upload_window = MagicMock()
        upload_window.update_progress_bar = MagicMock()
        upload_window.destroy = MagicMock()

        def fake_progress_window(_parent: object, title: str, *_args: object, **_kwargs: object) -> MagicMock:
            if "Restarting" in title:
                return reset_reconnect_window
            if "Uploading" in title:
                return upload_window
            return download_window

        parameter_editor_window.ui.create_progress_window = MagicMock(side_effect=fake_progress_window)

        param_editor_mock = cast("MagicMock", parameter_editor_window.parameter_editor)

        def fake_upload_workflow(  # pylint: disable=too-many-arguments
            selected_params: dict,
            *,
            ask_confirmation: Callable[[str, str], bool],
            ask_retry_cancel: Callable[[str, str], bool],
            show_error: Callable[[str, str], None],
            get_upload_progress_callback: Callable[[], Callable | None],
            get_connection_progress_callback: Callable[[], Callable | None],
            get_download_progress_callback: Callable[[], Callable | None],
        ) -> None:
            assert selected_params == {"ROLL_P": 0.12}
            assert callable(ask_confirmation)
            assert callable(ask_retry_cancel)
            assert callable(show_error)
            upload_cb = get_upload_progress_callback()
            connection_cb = get_connection_progress_callback()
            download_cb = get_download_progress_callback()
            assert upload_cb is not None
            assert connection_cb is not None
            assert download_cb is not None
            upload_cb(0, 1)
            connection_cb(10, 100)
            connection_cb(30, 100)
            connection_cb(50, 100)
            connection_cb(70, 100)
            connection_cb(90, 100)
            connection_cb(100, 100)
            download_cb(3, 4)

        param_editor_mock.upload_selected_params_workflow.side_effect = fake_upload_workflow

        parameter_editor_window.upload_selected_params({"ROLL_P": 0.12})

        upload_window.destroy.assert_called_once()
        reset_reconnect_window.update_progress_bar_with_message.assert_has_calls(
            [
                mock_call(10, 100, "Reset command sent"),
                mock_call(30, 100, "Reconnecting to flight controller"),
                mock_call(50, 100, "Reconnecting to flight controller"),
                mock_call(70, 100, "Reconnecting to flight controller"),
                mock_call(90, 100, "Retrieving flight controller information"),
                mock_call(100, 100, "Flight Controller connected"),
            ]
        )
        reset_reconnect_window.destroy.assert_called_once()
        download_window.destroy.assert_called_once()
        assert parameter_editor_window._reset_progress_window is None
        assert parameter_editor_window._param_download_progress_window_upload is None

    def test_user_still_cleans_upload_windows_on_failure(self, parameter_editor_window: ParameterEditorWindow) -> None:
        upload_window = MagicMock()
        upload_window.update_progress_bar = MagicMock()
        upload_window.destroy = MagicMock()
        reset_reconnect_window = MagicMock()
        reset_reconnect_window.update_progress_bar_with_message = MagicMock()
        reset_reconnect_window.destroy = MagicMock()
        download_window = MagicMock()
        download_window.update_progress_bar = MagicMock()
        download_window.destroy = MagicMock()

        parameter_editor_window.ui.create_progress_window = MagicMock(
            side_effect=[upload_window, reset_reconnect_window, download_window]
        )
        param_editor_mock = cast("MagicMock", parameter_editor_window.parameter_editor)

        def failing_workflow(  # pylint: disable=too-many-arguments
            selected_params: dict,
            *,
            ask_confirmation: Callable[[str, str], bool],
            ask_retry_cancel: Callable[[str, str], bool],
            show_error: Callable[[str, str], None],
            get_upload_progress_callback: Callable[[], Callable | None],
            get_connection_progress_callback: Callable[[], Callable | None],
            get_download_progress_callback: Callable[[], Callable | None],
        ) -> None:
            assert selected_params == {}
            assert callable(ask_confirmation)
            assert callable(ask_retry_cancel)
            assert callable(show_error)
            upload_cb = get_upload_progress_callback()
            connection_cb = get_connection_progress_callback()
            download_cb = get_download_progress_callback()
            assert upload_cb is not None
            assert connection_cb is not None
            assert download_cb is not None
            upload_cb(0, 0)
            connection_cb(10, 100)
            connection_cb(30, 100)
            download_cb(3, 3)
            msg = "boom"
            raise RuntimeError(msg)

        param_editor_mock.upload_selected_params_workflow.side_effect = failing_workflow

        assert parameter_editor_window.upload_selected_params({}) is False

        parameter_editor_window.ui.show_error.assert_called_once()
        upload_window.destroy.assert_called_once()
        reset_reconnect_window.destroy.assert_called_once()
        download_window.destroy.assert_called_once()
        assert parameter_editor_window._reset_progress_window is None
        assert parameter_editor_window._param_download_progress_window_upload is None


class TestPluginLayoutLifecycle:
    """Exercise plugin layout decisions and cleanup flows."""

    @pytest.mark.parametrize("dialog", ["step_info", "copy_fc_values", "upload_confirmation"])
    @pytest.mark.parametrize("fail", [False, True])
    def test_step_dialog_component_sync_defers_plugin_until_workflow_finishes(
        self,
        parameter_editor_window: ParameterEditorWindow,
        parameter_editor: MagicMock,
        dialog: str,
        fail: bool,
    ) -> None:
        """
        Inline editor callbacks cannot restore a plugin during step dialogs or upload.

        GIVEN: A new step has a different plugin and an outgoing component editor still exists.
        WHEN: A workflow dialog syncs that editor before the configured upload starts.
        THEN: Component changes are synced but the plugin loads only after completion or failure.
        """
        editor = parameter_editor_window
        editor.current_plugin = {"name": "old_plugin", "placement": "left"}
        editor.current_plugin_view = MagicMock()
        new_plugin = {"name": "new_plugin", "placement": "left"}
        parameter_editor.get_plugin.return_value = new_plugin
        parameter_editor.get_instructions_popup.return_value = None
        parameter_editor._handle_file_jump_workflow.return_value = "01_initial.param"
        parameter_editor._repopulate_configuration_step_parameters.return_value = ([], [("Step", "Information")])
        parameter_editor.handle_param_file_change_workflow.side_effect = partial(
            ParameterEditor.handle_param_file_change_workflow, parameter_editor
        )
        components = {"Battery": {"Specifications": {"Volt per cell max": 4.2}}}
        editor.inline_component_editor = MagicMock()
        editor.inline_component_editor.get_component_data.return_value = {"Components": components}

        with (
            patch.object(editor, "_update_plugin_layout") as load_plugin,
            patch.object(editor, "_do_tempcal_imu"),
            patch.object(editor, "_should_copy_fc_values_to_file", return_value=False) as copy_values,
            patch.object(editor, "_should_upload_file_to_fc", return_value=True) as upload,
        ):

            def sync_during_dialog(*_args: object) -> bool:
                assert parameter_editor.current_file == "01_initial.param"
                assert not editor._configured_upload_active
                editor._on_component_data_changed()
                parameter_editor.update_vehicle_components.assert_called_once_with(components)
                parameter_editor.refresh_current_step_computed_parameters.assert_called_once_with()
                load_plugin.assert_not_called()
                assert editor.current_plugin_view is None
                if fail:
                    message = "dialog failed"
                    raise RuntimeError(message)
                return False

            callbacks = {"step_info": editor.ui.show_info, "copy_fc_values": copy_values, "upload_confirmation": upload}
            cast("MagicMock", callbacks[dialog]).side_effect = sync_during_dialog
            if fail:
                with pytest.raises(RuntimeError, match="dialog failed"):
                    editor.on_param_file_combobox_change(None)
            else:
                editor.on_param_file_combobox_change(None)
                upload.assert_called_once_with("01_initial.param")

        load_plugin.assert_called_once_with(new_plugin, force_reload=True)
        assert not editor._param_file_change_active
        assert not editor._configured_upload_active

    def test_user_refreshes_same_plugin_without_layout_changes(self, parameter_editor_window: ParameterEditorWindow) -> None:
        parameter_editor_window.current_plugin = {"name": "alpha", "placement": "left"}
        parameter_editor_window.current_plugin_view = MagicMock()

        with (
            patch.object(parameter_editor_window, "_swap_plugin_in_place") as mock_swap,
            patch.object(parameter_editor_window, "_rebuild_plugin_layout") as mock_rebuild,
        ):
            parameter_editor_window._update_plugin_layout(parameter_editor_window.current_plugin)

        mock_swap.assert_not_called()
        mock_rebuild.assert_not_called()

    @pytest.mark.parametrize("forced", [False, True])
    @pytest.mark.parametrize("final_file", ["00_previous.param", "01_initial.param"])
    def test_step_workflow_removes_outgoing_plugin_before_any_dialog(
        self,
        parameter_editor_window: ParameterEditorWindow,
        parameter_editor: MagicMock,
        forced: bool,
        final_file: str,
    ) -> None:
        """
        Step changes and forced refreshes release all outgoing plugin functionality.

        GIVEN: A plugin with controls and polling is active in the current step.
        WHEN: A transition runs, possibly returning to the original step.
        THEN: Its safety cleanup finishes before workflow dialogs and the final plugin is loaded.
        """
        editor = parameter_editor_window
        plugin = MagicMock()
        editor.current_plugin_view = plugin
        parameter_editor.current_file = "01_initial.param" if forced else "00_previous.param"

        def destroy() -> None:
            plugin.on_deactivate.assert_called_once_with()

        plugin.destroy.side_effect = destroy

        def workflow(*_args, **_kwargs) -> tuple[str, bool]:
            plugin.destroy.assert_called_once_with()
            assert editor.current_plugin_view is None
            parameter_editor.current_file = final_file
            return final_file, True

        parameter_editor.handle_param_file_change_workflow.side_effect = workflow
        with patch.object(editor, "_update_plugin_layout") as refresh:
            editor.on_param_file_combobox_change(None, forced=forced)

        parameter_editor.get_plugin.assert_called_once_with(final_file)
        refresh.assert_called_once_with(parameter_editor.get_plugin.return_value, force_reload=True)
        plugin.on_activate.assert_not_called()
        plugin.on_suspend.assert_not_called()

    def test_failed_plugin_safety_cleanup_prevents_step_workflow(
        self, parameter_editor_window: ParameterEditorWindow, parameter_editor: MagicMock
    ) -> None:
        """
        A failed safety stop prevents a configuration step transition.

        GIVEN: An outgoing plugin cannot complete its safety stop.
        WHEN: The user attempts to leave the step.
        THEN: No transfer or other step workflow starts and the error propagates.
        """
        editor = parameter_editor_window
        plugin = MagicMock()
        editor.current_plugin_view = plugin
        plugin.on_deactivate.side_effect = RuntimeError("motor stop failed")
        parameter_editor.current_file = "00_previous.param"

        with pytest.raises(RuntimeError, match="motor stop failed"):
            editor.on_param_file_combobox_change(None)

        parameter_editor.handle_param_file_change_workflow.assert_not_called()
        plugin.destroy.assert_not_called()
        assert editor.current_plugin_view is plugin

    def test_user_swaps_plugin_with_matching_placement(self, parameter_editor_window: ParameterEditorWindow) -> None:
        parameter_editor_window.current_plugin = {"name": "alpha", "placement": "left"}
        new_plugin = {"name": "beta", "placement": "left"}

        with (
            patch.object(parameter_editor_window, "_swap_plugin_in_place") as mock_swap,
            patch.object(parameter_editor_window, "_rebuild_plugin_layout") as mock_rebuild,
        ):
            parameter_editor_window._update_plugin_layout(new_plugin)

        mock_swap.assert_called_once_with(new_plugin)
        mock_rebuild.assert_not_called()

    def test_user_rebuilds_layout_when_plugin_placement_changes(self, parameter_editor_window: ParameterEditorWindow) -> None:
        parameter_editor_window.current_plugin = None
        plugin = {"name": "gamma", "placement": "top"}

        with (
            patch.object(parameter_editor_window, "_swap_plugin_in_place") as mock_swap,
            patch.object(parameter_editor_window, "_rebuild_plugin_layout") as mock_rebuild,
        ):
            parameter_editor_window._update_plugin_layout(plugin)

        mock_swap.assert_not_called()
        mock_rebuild.assert_called_once_with(plugin)

    def test_user_cleans_up_plugin_views_before_loading_new_layout(
        self, parameter_editor_window: ParameterEditorWindow
    ) -> None:
        plugin_view = MagicMock()
        plugin_view.on_deactivate = MagicMock()
        plugin_view.destroy = MagicMock()
        parameter_editor_window.current_plugin_view = plugin_view
        paned = MagicMock()
        parameter_editor_window.parameter_area_paned = paned

        parameter_editor_window._cleanup_plugin_views()

        plugin_view.on_deactivate.assert_called_once()
        plugin_view.destroy.assert_called_once()
        paned.destroy.assert_called_once()
        assert parameter_editor_window.current_plugin_view is None
        assert parameter_editor_window.parameter_area_paned is None

    def test_user_gets_warning_when_plugin_cleanup_hooks_fail(self, parameter_editor_window: ParameterEditorWindow) -> None:
        plugin_view = MagicMock()
        plugin_view.on_deactivate.side_effect = AttributeError("missing")
        plugin_view.destroy.side_effect = tk.TclError("boom")
        parameter_editor_window.current_plugin_view = plugin_view
        paned = MagicMock()
        paned.destroy.side_effect = AttributeError("gone")
        parameter_editor_window.parameter_area_paned = paned

        with patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.logging_warning") as mock_warn:
            parameter_editor_window._cleanup_plugin_views()

        assert mock_warn.call_count == 3
        assert parameter_editor_window.current_plugin_view is None
        assert parameter_editor_window.parameter_area_paned is None

    def test_user_swaps_left_plugin_updates_existing_container(self, parameter_editor_window: ParameterEditorWindow) -> None:
        plugin_view = MagicMock()
        parameter_editor_window.current_plugin_view = plugin_view
        parameter_editor_window.parameter_area_paned = MagicMock()
        parameter_editor_window.parameter_area_paned.panes.return_value = ("pane",)
        plugin_parent = MagicMock()
        existing_child = MagicMock()
        plugin_parent.winfo_children.return_value = [existing_child]
        parameter_editor_window.parameter_area_paned.nametowidget.return_value = plugin_parent
        plugin = {"name": "beta", "placement": "left"}

        with patch.object(parameter_editor_window, "_load_plugin") as mock_load:
            parameter_editor_window._swap_plugin_in_place(plugin)

        plugin_view.destroy.assert_called_once()
        existing_child.destroy.assert_called_once()
        mock_load.assert_called_once_with(plugin_parent, plugin)
        assert parameter_editor_window.current_plugin == plugin

    def test_user_swaps_top_plugin_updates_existing_container(self, parameter_editor_window: ParameterEditorWindow) -> None:
        class DummyFrame:  # pylint: disable=too-few-public-methods
            """Minimal container that mimics ttk.Frame for plugin layout tests."""

            def __init__(self, master: DummyFrame | None = None) -> None:
                self._children: list[object] = []
                self.master = master
                self.rowconfigure = MagicMock()

            def winfo_children(self) -> list[object]:
                return self._children

        top_container = DummyFrame()
        plugin_holder = DummyFrame(top_container)
        child = MagicMock()
        plugin_holder._children = [child]
        top_container._children = [plugin_holder]
        parameter_editor_window.parameter_area_container.winfo_children = MagicMock(return_value=[top_container])
        plugin = {"name": "gamma", "placement": "top"}

        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ttk.Frame", DummyFrame),
            patch.object(parameter_editor_window, "_load_plugin") as mock_load,
        ):
            parameter_editor_window._swap_plugin_in_place(plugin)

        child.destroy.assert_called_once()
        mock_load.assert_called_once_with(plugin_holder, plugin)
        assert parameter_editor_window.current_plugin == plugin


class TestPluginLayoutRebuild:
    """Cover the layout rebuild logic for each placement."""

    @pytest.mark.parametrize(
        "result_step",
        [("27_autotune_pitch_RatePD_results.param", "PIT"), ("36_autotune_roll_results.param", "RLL")],
        ids=["heli", "copter"],
    )
    @pytest.mark.parametrize(
        "window_size", [(990, 688), (990, 520), (1100, 500)], ids=["768-screen", "600-screen", "short-window"]
    )
    def test_user_can_apply_gain_backoff_and_read_feedback_on_short_screens(  # noqa: PLR0915 # pylint: disable=too-many-statements,too-many-locals
        self,
        parameter_editor_window: ParameterEditorWindow,
        layout_root: tk.Tk,
        window_size: tuple[int, int],
        result_step: tuple[str, str],
    ) -> None:
        """
        Non-scrollable top controls stay usable without sacrificing scrollable assistants.

        GIVEN: AutoTune results below a fixed header on a short screen
        WHEN: The user resizes, applies back-off and switches between top plugins in place
        THEN: All back-off controls and feedback remain visible, and orientation still scrolls
        """
        root = layout_root
        editor = parameter_editor_window
        parameter_editor = cast("MagicMock", editor.parameter_editor)
        width, height = window_size
        filename, axis = result_step
        window = tk.Toplevel(root)
        window.geometry(f"{width}x{height}+0+0")
        editor.root = window
        editor.main_frame = ttk.Frame(window)
        editor.main_frame.place(width=width, height=height)
        header = ttk.Frame(editor.main_frame, height=300)
        header.pack(side="top", fill="x")
        header.pack_propagate(flag=False)
        editor.parameter_area_container = ttk.Frame(editor.main_frame)
        editor.parameter_area_container.pack(side="top", fill="both", expand=True)
        buttons = ttk.Frame(editor.main_frame)
        buttons.pack(side="bottom", fill="x")
        ttk.Button(buttons, text="Upload parameters\nand advance").pack()
        parameter_editor.current_file = filename
        parameter_editor.current_step_parameters = {
            f"ATC_RAT_{axis}_{term}": ArduPilotParameter(f"ATC_RAT_{axis}_{term}", Par(0.2, "AutoTune result"))
            for term in ("P", "I", "D")
        }
        parameter_editor.should_display_bitmask_parameter_editor_usage.return_value = False
        backoff_model = AutotuneGainBackoffDataModel(parameter_editor)
        orientation_model = MagicMock(spec=AhrsOrientationDataModel)
        orientation_model.get_required_steps.return_value = ("LEVEL", "NOSE DOWN", "RIGHT")
        orientation_model.validate_detection_prerequisites.return_value = (True, "")
        parameter_editor.create_plugin_data_model.side_effect = lambda name: (
            orientation_model if name == PLUGIN_AHRS_ORIENTATION else backoff_model
        )
        registry = PluginFactory()
        registry.register(
            PLUGIN_AUTOTUNE_GAIN_BACKOFF,
            lambda parent, model, window: AutotuneGainBackoffView(
                parent, cast("AutotuneGainBackoffDataModel", model), cast("BaseWindow", window)
            ),
        )
        registry.register(
            PLUGIN_AHRS_ORIENTATION,
            lambda parent, model, window: AhrsOrientationView(
                parent, cast("AhrsOrientationDataModel", model), cast("BaseWindow", window)
            ),
        )

        try:
            root.update_idletasks()
            editor._bind_parameter_layout_events()
            with (
                patch.object(parameter_editor_module, "plugin_factory", registry),
                patch.object(AhrsOrientationView, "_start_imu_polling"),
            ):
                for name in (
                    PLUGIN_AUTOTUNE_GAIN_BACKOFF,
                    PLUGIN_AHRS_ORIENTATION,
                    PLUGIN_AUTOTUNE_GAIN_BACKOFF,
                    PLUGIN_AHRS_ORIENTATION,
                ):
                    previous_container = editor.parameter_area_container
                    previous_table = editor.parameter_editor_table
                    previous_plugin = editor.current_plugin
                    editor._update_plugin_layout({"name": name, "placement": "top"})
                    if previous_plugin is not None:
                        assert editor.parameter_area_container is previous_container
                        assert editor.parameter_editor_table is previous_table
                    editor.parameter_editor_table.repopulate_table(show_only_differences=False, gui_complexity="normal")
                    for client_height in (height, height - 40, height):
                        editor.main_frame.place_configure(height=client_height)
                        root.update_idletasks()
                        editor._resize_parameter_area_to_fit()
                        root.update_idletasks()

                        if name == PLUGIN_AUTOTUNE_GAIN_BACKOFF:
                            view = cast("AutotuneGainBackoffView", editor.current_plugin_view)
                            assert view.winfo_height() >= view.winfo_reqheight()
                            gain = parameter_editor.current_step_parameters[f"ATC_RAT_{axis}_P"]
                            previous_gain = gain.get_new_value()
                            view.apply_button.invoke()
                            root.update_idletasks()
                            assert gain.get_new_value() == pytest.approx(previous_gain * 0.75)
                            assert "Updated gains:" in view.status.get()
                            assert view.winfo_height() >= view.winfo_reqheight()
                            for widget in (*view.winfo_children(), view.entry, view.apply_button):
                                assert widget.winfo_ismapped()
                                assert view.winfo_rooty() <= widget.winfo_rooty()
                                assert widget.winfo_rooty() + widget.winfo_height() <= (
                                    view.winfo_rooty() + view.winfo_height()
                                )
                            assert editor.parameter_container.winfo_height() > 1
                        else:
                            assert editor.parameter_container.winfo_height() >= 120
                            orientation_view = cast("AhrsOrientationView", editor.current_plugin_view)
                            canvas = orientation_view._scroll_frame.canvas
                            canvas.yview_moveto(1)
                            root.update_idletasks()
                            assert canvas.yview()[0] > 0
                            assert canvas.yview()[1] == pytest.approx(1)
                        assert buttons.winfo_height() == buttons.winfo_reqheight()
                        assert buttons.winfo_y() + buttons.winfo_height() <= client_height
        finally:
            window.destroy()

    @pytest.mark.parametrize("queued_refit", [False, True], ids=["no-refit", "queued-refit"])
    def test_user_can_read_parameters_after_a_plugin_activation_dialog(  # noqa: PLR0915
        self, parameter_editor_window: ParameterEditorWindow, layout_root: tk.Tk, queued_refit: bool
    ) -> None:
        """
        A modal prerequisite warning must not collapse the adjacent parameter pane.

        GIVEN: A left AHRS assistant whose prerequisites fail during activation
        WHEN: Its real modal Tk warning runs a nested event loop while layout is rebuilt
        THEN: Both panes and the navigation remain usable, including on a revisit
        """
        root = layout_root
        editor = parameter_editor_window
        window = tk.Toplevel(root)
        window.geometry("990x600+0+0")
        editor.root = window
        editor.main_frame = ttk.Frame(window)
        editor.main_frame.place(width=990, height=600)
        editor.parameter_area_container = ttk.Frame(editor.main_frame)
        editor.parameter_area_container.pack(fill="both", expand=True)
        buttons = ttk.Frame(editor.main_frame)
        buttons.pack(side="bottom", fill="x")
        ttk.Button(buttons, text="Skip").pack()
        cast("MagicMock", editor.parameter_editor).current_step_parameters = {}
        model = MagicMock(spec=AhrsOrientationDataModel)
        model.get_required_steps.return_value = ("LEVEL", "NOSE DOWN", "RIGHT")
        model.is_connected.return_value = True
        model.validate_detection_prerequisites.return_value = (False, "IMU data unavailable")
        cast("MagicMock", editor.parameter_editor).create_plugin_data_model.return_value = model
        registry = PluginFactory()
        registry.register(
            PLUGIN_AHRS_ORIENTATION,
            lambda parent, model, window: AhrsOrientationView(
                parent, cast("AhrsOrientationDataModel", model), cast("BaseWindow", window)
            ),
        )

        def show_modal_warning(title: str, message: str) -> None:
            # A Tk modal dialog is portable; Windows' native messagebox cannot
            # be dismissed through Tk. This still runs a real nested wait loop.
            dialog = tk.Toplevel(window)
            dialog.title(title)
            dialog.transient(window)
            ttk.Label(dialog, text=message).pack()
            ttk.Button(dialog, text="OK", command=dialog.destroy).pack()
            dialog.grab_set()
            dialog.after(20, dialog.destroy)
            dialog.wait_window()

        try:
            root.update_idletasks()
            editor._bind_parameter_layout_events()
            with (
                patch.object(parameter_editor_module, "plugin_factory", registry),
                patch.object(AhrsOrientationView, "_start_imu_polling"),
                patch(
                    "ardupilot_methodic_configurator.plugins.frontend_tkinter_ahrs_orientation.showerror",
                    side_effect=show_modal_warning,
                ) as warning,
            ):
                for _ in range(2):
                    if queued_refit:
                        editor._on_main_frame_resize(tk.Event())
                    editor._rebuild_plugin_layout({"name": PLUGIN_AHRS_ORIENTATION, "placement": "left"})
                    editor.parameter_editor_table.repopulate_table(show_only_differences=False, gui_complexity="normal")
                    editor._resize_parameter_area_to_fit()
                    root.update_idletasks()

                    assert editor.parameter_container.winfo_width() > 100
                    assert editor.parameter_editor_table.winfo_width() > 100
                    assert editor.current_plugin_view is not None
                    assert cast("tk.Widget", editor.current_plugin_view).winfo_width() >= 500
                    assert buttons.winfo_height() == buttons.winfo_reqheight()
                    assert buttons.winfo_y() + buttons.winfo_height() <= 600
                    editor._rebuild_plugin_layout(None)
                    root.update_idletasks()
                assert warning.call_count == 2
                assert "Not Ready" in warning.call_args.args[0]
        finally:
            window.destroy()

    @pytest.mark.parametrize("component_visible", [True, False], ids=["with-component", "without-component"])
    @pytest.mark.parametrize("height", [688, 820], ids=["768-screen", "1080-screen"])
    def test_user_can_edit_parameters_below_the_top_orientation_assistant(  # noqa: PLR0915 # pylint: disable=too-many-statements,too-many-locals
        self, parameter_editor_window: ParameterEditorWindow, layout_root: tk.Tk, height: int, component_visible: bool
    ) -> None:
        """
        Manual orientation remains usable alongside the scrollable assistant.

        GIVEN: A top orientation assistant and optionally a tall Frame component editor
        WHEN: The user opens, resizes and revisits the board-orientation step
        THEN: Parameter rows and navigation stay visible and the assistant can scroll
        """
        root = layout_root
        editor = parameter_editor_window
        window = tk.Toplevel(root)
        window.geometry(f"990x{height}+0+0")
        editor.root = window
        editor.main_frame = ttk.Frame(window)
        editor.main_frame.place(width=990, height=height)
        header = ttk.Frame(editor.main_frame, height=300)
        header.pack(side="top", fill="x")
        header.pack_propagate(flag=False)
        editor.inline_component_container = ttk.LabelFrame(editor.main_frame)
        editor.parameter_area_container = ttk.Frame(editor.main_frame)
        editor.parameter_area_container.pack(side="top", fill="both", expand=True)
        if component_visible:
            editor.inline_component_container.pack(side="top", before=editor.parameter_area_container, fill="x")
            scroll_frame = ScrollFrame(editor.inline_component_container)
            scroll_frame.pack(fill="both", expand=True)
            for _ in range(20):
                ttk.Entry(scroll_frame.view_port).pack(fill="x")
            editor.inline_component_scroll_frame = scroll_frame
        buttons = ttk.Frame(editor.main_frame)
        buttons.pack(side="bottom", fill="x")
        ttk.Button(buttons, text="Upload parameters\nand advance").pack()
        cast("MagicMock", editor.parameter_editor).current_step_parameters = {
            "AHRS_ORIENTATION": ArduPilotParameter("AHRS_ORIENTATION", Par(0, "Board orientation"))
        }
        cast("MagicMock", editor.parameter_editor).should_display_bitmask_parameter_editor_usage.return_value = False
        model = MagicMock(spec=AhrsOrientationDataModel)
        model.get_required_steps.return_value = ("LEVEL", "NOSE DOWN", "RIGHT")
        model.validate_detection_prerequisites.return_value = (True, "")
        cast("MagicMock", editor.parameter_editor).create_plugin_data_model.return_value = model
        registry = PluginFactory()
        registry.register(
            PLUGIN_AHRS_ORIENTATION,
            lambda parent, model, window: AhrsOrientationView(
                parent, cast("AhrsOrientationDataModel", model), cast("BaseWindow", window)
            ),
        )

        try:
            root.update_idletasks()
            if editor.inline_component_scroll_frame is not None:
                editor._inline_component_chrome_height = (
                    editor.inline_component_container.winfo_reqheight()
                    - editor.inline_component_scroll_frame.winfo_reqheight()
                )
            editor._bind_parameter_layout_events()
            with (
                patch.object(parameter_editor_module, "plugin_factory", registry),
                patch.object(AhrsOrientationView, "_start_imu_polling"),
            ):
                for _ in range(2):
                    editor._rebuild_plugin_layout({"name": PLUGIN_AHRS_ORIENTATION, "placement": "top"})
                    editor.parameter_editor_table.repopulate_table(show_only_differences=False, gui_complexity="normal")
                    for client_height in (height, height - 40, height):
                        editor.main_frame.place_configure(height=client_height)
                        root.update_idletasks()
                        editor._resize_parameter_area_to_fit()
                        root.update_idletasks()

                        assert editor.parameter_container.winfo_height() >= 120
                        table = editor.parameter_editor_table
                        value_widget = table._new_value_widgets["AHRS_ORIENTATION"]
                        assert not value_widget.instate(["disabled"])
                        assert table.canvas.winfo_rooty() <= value_widget.winfo_rooty()
                        assert value_widget.winfo_rooty() + value_widget.winfo_height() <= (
                            table.canvas.winfo_rooty() + table.canvas.winfo_height()
                        )
                        assert buttons.winfo_height() == buttons.winfo_reqheight()
                        assert buttons.winfo_y() + buttons.winfo_height() <= client_height
                        view = cast("AhrsOrientationView", editor.current_plugin_view)
                        canvas = view._scroll_frame.canvas
                        assert canvas.winfo_height() >= view._continue_btn.winfo_reqheight() + 8
                        canvas.yview_moveto(1)
                        root.update_idletasks()
                        assert canvas.winfo_rooty() <= view._continue_btn.winfo_rooty()
                        assert view._continue_btn.winfo_rooty() + view._continue_btn.winfo_height() <= (
                            canvas.winfo_rooty() + canvas.winfo_height()
                        )
                    editor._rebuild_plugin_layout(None)
                    root.update_idletasks()
        finally:
            window.destroy()

    def test_user_rebuilds_left_layout_with_split_view(self, parameter_editor_window: ParameterEditorWindow) -> None:
        parameter_editor_window.parameter_area_container = _build_parameter_area_container()
        parameter_editor_window.main_frame = MagicMock()
        created_frames: list[MagicMock] = []

        def frame_side_effect(*_args: object, **_kwargs: object) -> MagicMock:
            frame = MagicMock()
            frame.pack = MagicMock()
            frame.winfo_children = MagicMock(return_value=[])
            created_frames.append(frame)
            return frame

        paned = MagicMock()
        paned.add = MagicMock()
        paned.pack = MagicMock()
        paned.paneconfigure = MagicMock()
        table = MagicMock()
        table.pack = MagicMock()
        plugin = {"name": "alpha", "placement": "left"}

        with (
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ttk.Frame",
                side_effect=frame_side_effect,
            ),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.tk.PanedWindow",
                return_value=paned,
            ),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ParameterEditorTable",
                return_value=table,
            ),
            patch.object(parameter_editor_window, "_load_plugin") as mock_load,
        ):
            parameter_editor_window._rebuild_plugin_layout(plugin)

        assert parameter_editor_window.parameter_container is created_frames[2]
        mock_load.assert_called_once_with(created_frames[1], plugin)
        table.pack.assert_called_once_with(side="top", fill="both", expand=True)

    @pytest.mark.parametrize("defer_geometry", [False, True], ids=["immediate", "sequoia"])
    @pytest.mark.parametrize(("width", "height"), [(990, 600), (1100, 500), (990, 440)])
    def test_user_can_read_parameters_after_revisiting_a_left_plugin_step(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        parameter_editor_window: ParameterEditorWindow,
        parameter_editor: MagicMock,
        root: tk.Tk,
        width: int,
        height: int,
        defer_geometry: bool,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        Left plugin steps preserve usable parameter table width and visible buttons.

        GIVEN: A registered plugin requires a flight controller that is disconnected
        WHEN: The user revisits its step with a refit queued before the layout rebuild
        THEN: The real parameter table remains readable and the Skip button stays visible
        """
        editor = parameter_editor_window
        monkeypatch.setattr(parameter_editor_module, "is_macos_sequoia_or_older", lambda: defer_geometry)
        window = tk.Toplevel(root)
        window.geometry(f"{width}x{height}+0+0")
        editor.root = window
        editor.main_frame = ttk.Frame(window)
        editor.main_frame.place(width=width, height=height)
        editor.parameter_area_container = ttk.Frame(editor.main_frame, height=300)
        editor.parameter_area_container.pack(side="top", fill="both", expand=True)
        buttons = ttk.Frame(editor.main_frame)
        buttons.pack(side="bottom", fill="x")
        ttk.Button(buttons, text="Skip").pack()
        parameter_editor.is_fc_connected = False
        parameter_editor.create_plugin_data_model.return_value = None
        parameter_editor.current_step_parameters = {}
        plugin_creator = MagicMock()
        registry = PluginFactory()
        registry.register(PLUGIN_RC_CALIBRATION, plugin_creator)

        try:
            if sys_platform == "win32":
                window.wait_visibility()
                _wait_for_layout(
                    window,
                    lambda: editor.main_frame.winfo_width() == width,
                )
            root.update_idletasks()
            editor._bind_parameter_layout_events()
            with patch.object(parameter_editor_module, "plugin_factory", registry):
                for _ in range(2):
                    editor._on_main_frame_resize(tk.Event())
                    editor._rebuild_plugin_layout({"name": PLUGIN_RC_CALIBRATION, "placement": "left"})
                    editor.parameter_editor_table.repopulate_table(show_only_differences=False, gui_complexity="normal")
                    root.update_idletasks()

                    if sys_platform == "win32":
                        _wait_for_layout(
                            window,
                            lambda: (
                                editor.parameter_container.winfo_width() > 1
                                and editor.parameter_editor_table.winfo_width() > 1
                            ),
                        )
                    assert editor.parameter_container.winfo_width() > 100
                    assert editor.parameter_editor_table.winfo_width() > 100
                    assert buttons.winfo_height() == buttons.winfo_reqheight()
                    assert buttons.winfo_y() + buttons.winfo_height() <= height

                    editor._rebuild_plugin_layout(None)
                    root.update_idletasks()
            plugin_creator.assert_not_called()
        finally:
            window.destroy()

    def test_user_rebuilds_top_layout_with_separator(self, parameter_editor_window: ParameterEditorWindow) -> None:
        parameter_editor_window.parameter_area_container = _build_parameter_area_container()
        parameter_editor_window.main_frame = MagicMock()
        created_frames: list[MagicMock] = []

        def frame_side_effect(*_args: object, **_kwargs: object) -> MagicMock:
            frame = MagicMock()
            frame.pack = MagicMock()
            frame.winfo_children = MagicMock(return_value=[])
            created_frames.append(frame)
            return frame

        table = MagicMock()
        table.pack = MagicMock()
        plugin = {"name": "beta", "placement": "top"}
        separator = MagicMock()

        with (
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ttk.Frame",
                side_effect=frame_side_effect,
            ),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ttk.Separator",
                return_value=separator,
            ),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ParameterEditorTable",
                return_value=table,
            ),
            patch.object(parameter_editor_window, "_load_plugin") as mock_load,
        ):
            parameter_editor_window._rebuild_plugin_layout(plugin)

        assert parameter_editor_window.parameter_container is created_frames[3]
        mock_load.assert_called_once_with(created_frames[2], plugin)
        separator.grid.assert_called_once_with(row=1, column=0, sticky="ew", pady=2)

    def test_user_rebuilds_simple_layout_when_no_plugin(self, parameter_editor_window: ParameterEditorWindow) -> None:
        parameter_editor_window.parameter_area_container = _build_parameter_area_container()
        parameter_editor_window.main_frame = MagicMock()
        table = MagicMock()
        table.pack = MagicMock()

        with (
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ttk.Frame",
                return_value=_build_parameter_area_container(),
            ),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ParameterEditorTable",
                return_value=table,
            ),
        ):
            parameter_editor_window._rebuild_plugin_layout(None)

        assert parameter_editor_window.parameter_container is parameter_editor_window.parameter_area_container
        table.pack.assert_called_once_with(side="top", fill="both", expand=True)


class TestPluginLoading:
    """Validate plugin factory edge cases."""

    def test_user_sees_message_when_plugin_name_missing(self, parameter_editor_window: ParameterEditorWindow) -> None:
        parent_frame = MagicMock()

        with patch(
            "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ttk.Label",
            return_value=MagicMock(pack=MagicMock()),
        ) as mock_label:
            parameter_editor_window._load_plugin(parent_frame, {})

        assert "Plugin configuration missing name" in mock_label.call_args.kwargs.get("text", "")

    def test_user_is_warned_when_plugin_is_unknown(self, parameter_editor_window: ParameterEditorWindow) -> None:
        parent_frame = MagicMock()
        plugin = {"name": "mystery"}

        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.plugin_factory") as mock_factory,
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ttk.Label",
                return_value=MagicMock(pack=MagicMock()),
            ) as mock_label,
        ):
            mock_factory.is_registered.return_value = False
            parameter_editor_window._load_plugin(parent_frame, plugin)

        mock_factory.is_registered.assert_called_once_with("mystery")
        assert "Unknown plugin" in mock_label.call_args.kwargs.get("text", "")

    def test_user_is_informed_when_plugin_needs_fc_connection(self, parameter_editor_window: ParameterEditorWindow) -> None:
        parent_frame = MagicMock()
        plugin = {"name": "needs-fc"}
        param_editor_mock = cast("MagicMock", parameter_editor_window.parameter_editor)
        param_editor_mock.create_plugin_data_model = MagicMock(return_value=None)

        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.plugin_factory") as mock_factory,
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ttk.Label",
                return_value=MagicMock(pack=MagicMock()),
            ) as mock_label,
        ):
            mock_factory.is_registered.return_value = True
            parameter_editor_window._load_plugin(parent_frame, plugin)

        assert "requires flight controller" in mock_label.call_args.kwargs.get("text", "")

    def test_user_gets_error_label_when_plugin_data_model_raises(self, parameter_editor_window: ParameterEditorWindow) -> None:
        parent_frame = MagicMock()
        plugin = {"name": "explosive"}
        param_editor_mock = cast("MagicMock", parameter_editor_window.parameter_editor)
        param_editor_mock.create_plugin_data_model = MagicMock(side_effect=ValueError("boom"))

        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.plugin_factory") as mock_factory,
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ttk.Label",
                return_value=MagicMock(pack=MagicMock()),
            ) as mock_label,
        ):
            mock_factory.is_registered.return_value = True
            parameter_editor_window._load_plugin(parent_frame, plugin)

        assert "boom" in mock_label.call_args.kwargs.get("text", "")

    def test_user_sees_message_when_plugin_creation_returns_none(self, parameter_editor_window: ParameterEditorWindow) -> None:
        _ = self
        parent_frame = MagicMock()
        plugin = {"name": "ghost"}
        param_editor_mock = cast("MagicMock", parameter_editor_window.parameter_editor)
        param_editor_mock.create_plugin_data_model = MagicMock(return_value=MagicMock())

        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.plugin_factory") as mock_factory,
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ttk.Label",
                return_value=MagicMock(pack=MagicMock()),
            ) as mock_label,
        ):
            mock_factory.is_registered.return_value = True
            mock_factory.create.return_value = None
            parameter_editor_window._load_plugin(parent_frame, plugin)

        assert "Failed to create plugin" in mock_label.call_args.kwargs.get("text", "")

    def test_user_gets_error_label_when_plugin_factory_raises(self, parameter_editor_window: ParameterEditorWindow) -> None:
        _ = self
        parent_frame = MagicMock()
        plugin = {"name": "explosive"}
        param_editor_mock = cast("MagicMock", parameter_editor_window.parameter_editor)
        param_editor_mock.create_plugin_data_model = MagicMock(return_value=MagicMock())

        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.plugin_factory") as mock_factory,
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ttk.Label",
                return_value=MagicMock(pack=MagicMock()),
            ) as mock_label,
        ):
            mock_factory.is_registered.return_value = True
            mock_factory.create.side_effect = ValueError("kaboom")
            parameter_editor_window._load_plugin(parent_frame, plugin)

        assert "Error loading plugin" in mock_label.call_args.kwargs.get("text", "")

    def test_user_recovers_when_plugin_activation_fails(self, parameter_editor_window: ParameterEditorWindow) -> None:
        parent_frame = MagicMock()
        plugin = {"name": "stubborn"}
        param_editor_mock = cast("MagicMock", parameter_editor_window.parameter_editor)
        param_editor_mock.create_plugin_data_model = MagicMock(return_value=MagicMock())
        plugin_view = MagicMock()
        plugin_view.pack = MagicMock()
        plugin_view.destroy = MagicMock()
        plugin_view.on_activate.side_effect = TypeError("boom")

        with patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.plugin_factory") as mock_factory:
            mock_factory.is_registered.return_value = True
            mock_factory.create.return_value = plugin_view
            parameter_editor_window._load_plugin(parent_frame, plugin)

        plugin_view.on_activate.assert_called_once()
        plugin_view.destroy.assert_called_once()
        assert parameter_editor_window.current_plugin_view is None

    def test_user_confirms_parameter_file_change_refreshes_ui(
        self, parameter_editor_window: ParameterEditorWindow, parameter_editor: MagicMock
    ) -> None:
        """
        User confirms switching to the next parameter file to continue configuration.

        GIVEN: A different parameter file is available in the combobox
        WHEN: The user accepts the workflow prompt
        THEN: Pending edits are saved and the UI refreshes with the new file
        """
        parameter_editor.current_file = "00_previous.param"
        parameter_editor.handle_param_file_change_workflow.return_value = ("01_initial.param", True)

        with (
            patch.object(parameter_editor_window, "write_changes_to_intermediate_parameter_file") as mock_write,
            patch.object(parameter_editor_window, "repopulate_parameter_table") as mock_repopulate,
            patch.object(parameter_editor_window, "_update_plugin_layout") as mock_plugin_layout,
            patch.object(parameter_editor_window, "_update_skip_button_state") as mock_skip_state,
        ):
            parameter_editor_window.on_param_file_combobox_change(None)

        mock_write.assert_called_once()
        parameter_editor.handle_param_file_change_workflow.assert_called_once()
        doc_frame = cast("MagicMock", parameter_editor_window.documentation_frame)
        doc_frame.refresh_documentation_labels.assert_called_once()
        doc_frame.update_why_why_now_tooltip.assert_called_once()
        mock_plugin_layout.assert_called_once_with(parameter_editor.get_plugin.return_value, force_reload=True)
        mock_repopulate.assert_called_once_with()
        mock_skip_state.assert_called_once()

    def test_user_cancels_parameter_file_change_closes_application(
        self, parameter_editor_window: ParameterEditorWindow, parameter_editor: MagicMock
    ) -> None:
        """
        User can cancel the workflow when switching files.

        GIVEN: The workflow indicates the user chose to close the window
        WHEN: The combobox change handler runs
        THEN: The application quits without refreshing the table
        """
        parameter_editor.current_file = "00_previous.param"
        parameter_editor.handle_param_file_change_workflow.return_value = ("01_initial.param", False)

        with patch.object(parameter_editor_window, "repopulate_parameter_table") as mock_repopulate:
            ui_sys_exit = cast("MagicMock", parameter_editor_window.ui.sys_exit)
            ui_sys_exit.side_effect = SystemExit
            with pytest.raises(SystemExit):
                parameter_editor_window.on_param_file_combobox_change(None)

        root_mock = cast("MagicMock", parameter_editor_window.root)
        root_mock.quit.assert_called_once()
        ui_sys_exit.assert_called_once_with(0)
        mock_repopulate.assert_not_called()


class TestCopyFlightControllerValues:
    """Cover the copy-from-flight-controller workflows and dialog helpers."""

    def test_user_handles_dialog_choice_helper(self, parameter_editor_window: ParameterEditorWindow) -> None:
        result: list[str | bool] = []
        dialog = MagicMock()

        parameter_editor_window._handle_dialog_choice(result, dialog, choice=True)

        assert result == [True]
        dialog.destroy.assert_called_once()

    def test_user_opens_copy_dialog_and_runs_workflow(self, parameter_editor_window: ParameterEditorWindow) -> None:
        parameter_editor = cast("MagicMock", parameter_editor_window.parameter_editor)

        def fake_workflow(
            selected_file: str,
            ask_user_choice: Callable[[str, str, list[str]], str | bool],
            show_info: Callable[[str, str], None],
        ) -> str | bool:
            assert selected_file == "01_initial.param"
            assert show_info is parameter_editor_window.ui.show_info
            return ask_user_choice("Title", "Message", ["Close", "Yes", "No"])

        parameter_editor.handle_copy_fc_values_workflow.side_effect = fake_workflow
        dialog = MagicMock()
        dialog.withdraw = MagicMock()
        dialog.transient = MagicMock()
        dialog.title = MagicMock()
        dialog.resizable = MagicMock()
        dialog.protocol = MagicMock()
        dialog.pack = MagicMock()
        dialog.grab_set = MagicMock()
        dialog.deiconify = MagicMock()
        dialog.update_idletasks = MagicMock()
        dialog.winfo_width.return_value = 200
        dialog.winfo_height.return_value = 100
        dialog.bind = MagicMock()

        message_label = MagicMock()
        message_label.pack = MagicMock()
        link_label = MagicMock()
        link_label.pack = MagicMock()
        link_label.bind = MagicMock()
        button_frame = MagicMock()
        button_frame.pack = MagicMock()
        close_button = MagicMock()
        close_button.pack = MagicMock()
        close_button.focus_set = MagicMock()
        yes_button = MagicMock()
        yes_button.pack = MagicMock()
        no_button = MagicMock()
        no_button.pack = MagicMock()

        parameter_editor_window.root.winfo_rootx = MagicMock(return_value=10)
        parameter_editor_window.root.winfo_rooty = MagicMock(return_value=20)
        parameter_editor_window.root.winfo_width = MagicMock(return_value=800)
        parameter_editor_window.root.winfo_height = MagicMock(return_value=600)
        wait_window_mock = MagicMock()
        parameter_editor_window.root.wait_window = wait_window_mock

        with (
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.tk.Toplevel",
                return_value=dialog,
            ),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.tk.Label",
                side_effect=[message_label, link_label],
            ),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.tk.Frame",
                return_value=button_frame,
            ),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.tk.Button",
                side_effect=[close_button, yes_button, no_button],
            ),
        ):
            result = parameter_editor_window._should_copy_fc_values_to_file("01_initial.param")

        assert result == "close"
        parameter_editor.handle_copy_fc_values_workflow.assert_called_once()
        wait_window_mock.assert_called_once_with(dialog)


# ============================== PROGRESS AND DOWNLOADS ==============================


class TestProgressIndicators:
    """Validate progress reporting behaviours for downloads and stage tracking."""

    def test_user_updates_stage_progress_bar_from_filename(self, editor_factory, parameter_editor) -> None:
        """
        User sees the stage progress bar advance when selecting numbered files.

        GIVEN: Configuration phases are enabled
        WHEN: A file prefixed with a step number is selected
        THEN: The progress bar receives the extracted step number
        """
        parameter_editor.configuration_phases.return_value = True
        editor = editor_factory()

        editor._update_progress_bar_from_file("05_stage.param")

        editor.stage_progress_bar.update_progress.assert_called_once_with(5)

    def test_user_gets_feedback_when_filename_prefix_is_invalid(self, editor_factory, parameter_editor) -> None:
        """
        User receives logging feedback when filenames lack numeric prefixes.

        GIVEN: Stage progress tracking is enabled
        WHEN: The selected filename does not start with digits
        THEN: No update occurs and an error is logged
        """
        parameter_editor.configuration_phases.return_value = True
        editor = editor_factory()

        with patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.logging_error") as mock_log:
            editor._update_progress_bar_from_file("invalid_name.param")

        editor.stage_progress_bar.update_progress.assert_not_called()
        mock_log.assert_called_once()

    def test_user_downloads_fc_parameters_with_progress_feedback(self, editor_factory, parameter_editor) -> None:
        """
        User sees a progress window while downloading flight controller parameters.

        GIVEN: The download workflow accepts a progress callback factory
        WHEN: The user initiates the download
        THEN: A progress window is created, passed to the workflow, and cleaned up
        """
        editor = editor_factory()
        editor.on_param_file_combobox_change = MagicMock()

        progress_instance = MagicMock()
        progress_instance.update_progress_bar = MagicMock()
        editor.ui.create_progress_window = MagicMock(return_value=progress_instance)

        editor.download_flight_controller_parameters(redownload=False)

        parameter_editor.download_flight_controller_parameters.assert_called_once_with(ANY, response_timeout=None)
        progress_instance.destroy.assert_called_once()
        editor.on_param_file_combobox_change.assert_called_once_with(None, forced=True)

    def test_user_skips_table_refresh_when_redownloading(self, editor_factory, parameter_editor) -> None:
        """
        User can re-download parameters without forcing a table refresh.

        GIVEN: The user re-downloads parameters for troubleshooting
        WHEN: The redownload flag is enabled
        THEN: The parameter table refresh is skipped
        """
        editor = editor_factory()
        editor.on_param_file_combobox_change = MagicMock()

        progress_instance = MagicMock()
        progress_instance.update_progress_bar = MagicMock()
        editor.ui.create_progress_window = MagicMock(return_value=progress_instance)

        editor.download_flight_controller_parameters(redownload=True)

        parameter_editor.download_flight_controller_parameters.assert_called_once_with(ANY, response_timeout=None)
        editor.on_param_file_combobox_change.assert_not_called()
        progress_instance.destroy.assert_called_once()


# ============================== TABLE REFRESH ==============================


class TestTableRefresh:
    """Cover interactions that rebuild the parameter table."""

    def test_user_toggles_show_only_changes_checkbox(self, parameter_editor_window: ParameterEditorWindow) -> None:
        """
        User refreshes the table when the "show only changed" checkbox toggles.

        GIVEN: The checkbox is interacted with
        WHEN: The handler executes
        THEN: The table is repopulated without forcing a disk read
        """
        with patch.object(parameter_editor_window, "repopulate_parameter_table") as mock_repopulate:
            parameter_editor_window.on_show_only_changed_checkbox_change()

        mock_repopulate.assert_called_once_with()

    def test_user_repopulates_table_for_selected_file(self, editor_factory, parameter_editor) -> None:
        """
        User can repopulate the table for the active file.

        GIVEN: A parameter file is already selected
        WHEN: The repopulate helper runs
        THEN: The table receives the expected arguments
        """
        editor = editor_factory()
        parameter_editor.current_file = "06_table.param"

        editor.repopulate_parameter_table()

        show_only_flag = editor.show_only_differences.get()
        editor.parameter_editor_table.repopulate_table.assert_called_once_with(
            show_only_flag,
            editor.gui_complexity,
        )


# ============================== UPLOAD WORKFLOWS ==============================


class TestParameterUploads:
    """Validate user-facing behaviours while uploading parameters."""

    def test_user_selects_external_parameter_file_for_preview(self, parameter_editor_window: ParameterEditorWindow) -> None:
        """A selected external file is loaded and shown without changing the current AMC step."""
        parameters = {"ROLL_P": MagicMock()}
        parameter_editor_window.ui.askopenfilename = MagicMock(return_value="C:/tmp/tune.parm")
        parameter_editor_window.parameter_editor.load_external_parameter_file.return_value = parameters

        with patch(
            "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ParameterFileUploadWindow"
        ) as upload_window:
            parameter_editor_window.on_compare_and_upload_parameter_file_click()

        parameter_editor_window.ui.askopenfilename.assert_called_once_with(
            title="Select an ArduPilot parameter file",
            filetypes=[("ArduPilot parameter files", "*.parm *.param"), ("All files", "*.*")],
        )
        parameter_editor_window.parameter_editor.load_external_parameter_file.assert_called_once_with("C:/tmp/tune.parm")
        upload_window.assert_called_once_with(parameter_editor_window, "C:/tmp/tune.parm", parameters)

    def test_external_parameter_file_parse_error_is_reported(self, parameter_editor_window: ParameterEditorWindow) -> None:
        """Invalid external files produce an error and do not open the preview."""
        parameter_editor_window.ui.askopenfilename = MagicMock(return_value="C:/tmp/bad.param")
        parameter_editor_window.parameter_editor.load_external_parameter_file.side_effect = ValueError("bad value")

        with patch(
            "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ParameterFileUploadWindow"
        ) as upload_window:
            parameter_editor_window.on_compare_and_upload_parameter_file_click()

        parameter_editor_window.ui.show_error.assert_called_once_with("Parameter file error", "bad value")
        upload_window.assert_not_called()

    def test_user_uploads_selected_parameters_when_fc_ready(self, parameter_editor_window: ParameterEditorWindow) -> None:
        """
        User uploads selected parameters when a flight controller connection is available.

        GIVEN: Parameters are selected and FC parameters were downloaded
        WHEN: The upload button is pressed
        THEN: The selected values are uploaded and the workflow advances
        """
        selected_params = {"ROLL_P": 0.2}
        parameter_editor_window.parameter_editor.fc_parameters.clear()
        parameter_editor_window.parameter_editor.fc_parameters.update({"ROLL_P": 0.1})

        with (
            patch.object(
                parameter_editor_window.parameter_editor_table,
                "get_upload_selected_params",
                return_value=selected_params,
            ),
            patch.object(parameter_editor_window, "write_changes_to_intermediate_parameter_file") as mock_write,
            patch.object(parameter_editor_window, "upload_selected_params") as mock_upload,
            patch.object(parameter_editor_window, "on_skip_click") as mock_skip,
            patch.object(
                parameter_editor_window.parameter_editor,
                "ensure_upload_preconditions",
                return_value=True,
            ) as mock_preconditions,
        ):
            parameter_editor_window.on_upload_selected_click()

        mock_preconditions.assert_called_once_with(
            selected_params,
            parameter_editor_window.ui.show_warning,
        )
        mock_write.assert_called_once()
        mock_upload.assert_called_once_with(selected_params)
        mock_skip.assert_called_once()

    def test_user_uploads_selected_parameters_and_stays_on_current_file(
        self, parameter_editor_window: ParameterEditorWindow
    ) -> None:
        """The stay variant uploads selected values without advancing to another parameter file."""
        selected_params = {"ROLL_P": 0.2}

        with (
            patch.object(
                parameter_editor_window.parameter_editor_table,
                "get_upload_selected_params",
                return_value=selected_params,
            ),
            patch.object(parameter_editor_window, "write_changes_to_intermediate_parameter_file") as mock_write,
            patch.object(parameter_editor_window, "upload_selected_params", return_value=True) as mock_upload,
            patch.object(parameter_editor_window, "_continue_to_analyse") as mock_continue,
            patch.object(parameter_editor_window, "repopulate_parameter_table") as mock_repopulate,
            patch.object(
                parameter_editor_window.parameter_editor,
                "ensure_upload_preconditions",
                return_value=True,
            ) as mock_preconditions,
            patch.object(parameter_editor_window, "on_skip_click") as mock_skip,
        ):
            parameter_editor_window.on_upload_selected_and_stay_click()

        mock_preconditions.assert_called_once_with(
            selected_params,
            parameter_editor_window.ui.show_warning,
        )
        mock_write.assert_called_once()
        mock_upload.assert_called_once_with(selected_params)
        mock_continue.assert_called_once()
        mock_repopulate.assert_called_once()
        mock_skip.assert_not_called()

    def test_user_receives_warning_when_no_fc_connection(self, parameter_editor_window: ParameterEditorWindow) -> None:
        """
        User receives feedback when attempting an upload without FC data.

        GIVEN: Parameters are selected but no FC parameters were downloaded
        WHEN: The upload button is pressed
        THEN: A warning dialog is shown and no upload occurs
        """
        selected_params = {"ROLL_P": 0.2}
        with (
            patch.object(
                parameter_editor_window.parameter_editor_table,
                "get_upload_selected_params",
                return_value=selected_params,
            ),
            patch.object(parameter_editor_window, "upload_selected_params") as mock_upload,
            patch.object(parameter_editor_window, "on_skip_click") as mock_skip,
            patch.object(
                parameter_editor_window.parameter_editor,
                "ensure_upload_preconditions",
                return_value=False,
            ) as mock_preconditions,
        ):
            parameter_editor_window.on_upload_selected_click()

        mock_preconditions.assert_called_once_with(
            selected_params,
            parameter_editor_window.ui.show_warning,
        )
        mock_upload.assert_not_called()
        mock_skip.assert_called_once()

    def test_user_receives_warning_when_no_parameters_selected(self, parameter_editor_window: ParameterEditorWindow) -> None:
        """
        User is notified when attempting to upload without selecting parameters.

        GIVEN: No parameters are marked for upload
        WHEN: The upload button is pressed
        THEN: A warning dialog appears and the workflow is not executed
        """
        with (
            patch.object(
                parameter_editor_window.parameter_editor_table,
                "get_upload_selected_params",
                return_value={},
            ),
            patch.object(parameter_editor_window, "upload_selected_params") as mock_upload,
            patch.object(parameter_editor_window, "on_skip_click") as mock_skip,
            patch.object(
                parameter_editor_window.parameter_editor,
                "ensure_upload_preconditions",
                return_value=False,
            ) as mock_preconditions,
        ):
            parameter_editor_window.on_upload_selected_click()

        mock_preconditions.assert_called_once_with(
            {},
            parameter_editor_window.ui.show_warning,
        )
        mock_upload.assert_not_called()
        mock_skip.assert_called_once()

    def test_user_runs_upload_workflow_with_progress_cleanup(self, editor_factory, parameter_editor: MagicMock) -> None:
        """
        User sees progress feedback during parameter uploads and windows are cleaned up.

        GIVEN: The upload workflow requests restart/reconnect and download callbacks
        WHEN: The callbacks are invoked by the workflow
        THEN: Progress windows expose update callables and are destroyed afterwards
        """
        editor = editor_factory()
        selected_params = {"ROLL_P": 0.2}

        created_windows: list[MagicMock] = []

        def _progress_window_factory(*_args, **_kwargs) -> MagicMock:
            window = MagicMock()
            window.update_progress_bar = MagicMock()
            created_windows.append(window)
            return window

        def _workflow(
            _selected: dict[str, float],
            *,
            get_upload_progress_callback: Callable[[], Callable],
            get_connection_progress_callback: Callable[[], Callable],
            get_download_progress_callback: Callable[[], Callable],
            **_ignored: object,
        ) -> None:
            upload_cb = get_upload_progress_callback()
            connection_cb = get_connection_progress_callback()
            download_cb = get_download_progress_callback()
            upload_cb(0, 1)
            connection_cb(10, 100)
            connection_cb(30, 100)
            download_cb(3, 4)

        parameter_editor.upload_selected_params_workflow.side_effect = _workflow

        editor.ui.create_progress_window = MagicMock(side_effect=_progress_window_factory)

        editor.upload_selected_params(selected_params)

        parameter_editor.upload_selected_params_workflow.assert_called_once_with(
            selected_params,
            ask_confirmation=ANY,
            ask_retry_cancel=ANY,
            show_error=ANY,
            get_upload_progress_callback=ANY,
            get_connection_progress_callback=ANY,
            get_download_progress_callback=ANY,
        )
        assert all(window.destroy.called for window in created_windows)

    def test_ui_services_upload_params_with_progress_handles_exceptions(
        self, editor_factory, parameter_editor: MagicMock
    ) -> None:
        """
        UI services properly handle exceptions during parameter upload.

        GIVEN: The upload workflow raises an exception
        WHEN: upload_params_with_progress is called
        THEN: Progress windows should still be cleaned up
        AND: Exception should propagate to caller
        """
        editor = editor_factory()

        # Mock progress windows
        reset_window = MagicMock()
        download_window = MagicMock()

        def fake_progress_window(_parent, title: str, *_args, **_kwargs) -> MagicMock:
            if "Reset" in title:
                return reset_window
            return download_window

        editor.ui.create_progress_window = MagicMock(side_effect=fake_progress_window)

        # Mock workflow that raises exception
        def failing_workflow(*_args, **_kwargs) -> None:
            msg = "Upload failed"
            raise RuntimeError(msg)

        parameter_editor.upload_selected_params_workflow = MagicMock(side_effect=failing_workflow)

        # Act & Assert: Exception is raised but cleanup happens
        with pytest.raises(RuntimeError, match="Upload failed"):
            editor.ui.upload_params_with_progress(
                editor.root,
                parameter_editor.upload_selected_params_workflow,
                {"PARAM1": 1.0},
            )

        # Verify cleanup happened - windows are only created if callbacks are invoked
        # Since workflow fails immediately, no callbacks are invoked, so no windows created
        assert len([w for w in [reset_window, download_window] if w.destroy.called]) == 0

    def test_upload_params_with_progress_only_creates_windows_when_callbacks_invoked(
        self, editor_factory, parameter_editor: MagicMock
    ) -> None:
        """
        Progress windows are only created when workflow invokes the factory callbacks.

        GIVEN: An upload workflow that may or may not need reset/download
        WHEN: The workflow only calls one of the progress factory callbacks
        THEN: Only that progress window should be created
        """
        editor = editor_factory()

        created_windows = []

        def track_window_creation(*_args, **_kwargs) -> MagicMock:
            window = MagicMock()
            created_windows.append(window)
            return window

        editor.ui.create_progress_window = MagicMock(side_effect=track_window_creation)

        # Mock workflow that only uses download progress (no restart needed)
        def workflow_without_reset(_params, **kwargs) -> None:
            # Don't call get_connection_progress_callback
            download_cb = kwargs["get_download_progress_callback"]()
            download_cb(50, 100)

        parameter_editor.upload_selected_params_workflow = MagicMock(side_effect=workflow_without_reset)

        # Act: Upload without reset
        editor.ui.upload_params_with_progress(
            editor.root,
            parameter_editor.upload_selected_params_workflow,
            {"PARAM1": 1.0},
        )

        # Assert: Only one window created (download, not restart/reconnect)
        assert len(created_windows) == 1


# ============================== FILE DOWNLOADS ==============================


@pytest.mark.parametrize("operation", ["upload", "reset", "download"])
@pytest.mark.parametrize("fails", [False, True], ids=["success", "failure"])
def test_sequoia_parameter_workflows_keep_tk_callbacks_on_the_ui_thread(  # pylint: disable=too-many-locals,too-many-statements # noqa: PLR0915
    parameter_editor_window: ParameterEditorWindow,
    root: tk.Tk,
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
    fails: bool,
) -> None:
    """
    Blocking parameter workflows leave Tk free to deliver timers and dialogs.

    GIVEN: Sequoia rendering and a parameter upload, reset or download
    WHEN: A worker reports progress, opens dialogs, and succeeds or fails
    THEN: All UI callbacks stay on Tk, windows are cleaned up, and results propagate
    """
    editor = parameter_editor_window
    editor.root = root
    ui_thread = get_ident()
    heartbeat = Event()
    root.after(0, heartbeat.set)
    monkeypatch.setattr(parameter_editor_module, "is_macos_sequoia_or_older", lambda: True)
    monkeypatch.setattr(tk.Misc, "update", lambda _self: None)
    monkeypatch.setattr(tk.Misc, "update_idletasks", lambda _self: None)
    created: list[MagicMock] = []
    rendered: list[tuple[int, int]] = []

    def render(current: int, total: int, *_message: str) -> None:
        assert get_ident() == ui_thread
        rendered.append((current, total))

    def destroy() -> None:
        assert get_ident() == ui_thread

    def create_window(*_args: object, **_kwargs: object) -> MagicMock:
        assert get_ident() == ui_thread
        window = MagicMock()
        window.update_progress_bar.side_effect = render
        window.update_progress_bar_with_message.side_effect = render
        window.destroy.side_effect = destroy
        created.append(window)
        return window

    def show_dialog(*_args: str) -> bool:
        assert get_ident() == ui_thread
        assert rendered
        return True

    editor.ui.create_progress_window = create_window
    editor.ui.ask_yesno = show_dialog
    editor.ui.ask_retry_cancel = show_dialog
    editor.ui.show_error = show_dialog

    def workflow(*args: object, **kwargs: object) -> object:
        assert get_ident() != ui_thread
        assert heartbeat.wait(2)
        if operation == "upload":
            for name in ("get_upload_progress_callback", "get_connection_progress_callback", "get_download_progress_callback"):
                report = cast("Callable", kwargs[name])()
                report(50, 100)
            assert cast("Callable", kwargs["ask_confirmation"])("Confirm", "Continue?")
            assert cast("Callable", kwargs["ask_retry_cancel"])("Retry", "Continue?")
            cast("Callable", kwargs["show_error"])("Error", "Example")
        elif operation == "reset":
            cast("Callable", args[1])(50, 100)
            cast("Callable", args[2])()(50, 100)
            cast("Callable", args[0])("Error", "Example")
        else:
            cast("Callable", args[0])()(50, 100)
        if fails:
            message = "transport failed"
            raise RuntimeError(message)
        return ({"TEST": 1}, {}) if operation == "download" else True

    def run() -> object:
        if operation == "upload":
            return editor.ui.upload_params_with_progress(root, workflow, {"TEST": 1})
        if operation == "reset":
            return editor.ui.reset_all_parameters_to_default_with_progress(root, workflow)
        cast("MagicMock", editor.parameter_editor).download_flight_controller_parameters.side_effect = workflow
        return editor.download_flight_controller_parameters(redownload=True)

    if fails:
        with pytest.raises(RuntimeError, match="transport failed"):
            run()
    else:
        assert run() == (({"TEST": 1}, {}) if operation == "download" else True)
    assert len(rendered) == len(created)
    assert len(created) == {"upload": 3, "reset": 2, "download": 1}[operation]
    for window in created:
        window.destroy.assert_called_once()
    assert editor._param_download_progress_window is None


class TestFlightLogDownloads:  # pylint: disable=too-few-public-methods
    """Keep one file-browser entry point for flight-log downloads."""

    def test_old_synchronous_log_handler_is_retired(self) -> None:
        """The legacy handler must not compete with the browser's async action."""
        assert not hasattr(ParameterEditorWindow, "on_download_last_flight_log_click")


# ============================== PERSISTENCE AND EXIT ==============================


class TestPersistenceAndExit:
    """Cover persistence helpers and graceful shutdown."""

    def test_user_writes_changes_to_intermediate_file(self, editor_factory, parameter_editor: MagicMock) -> None:
        """
        User persists staged changes to the intermediate parameter file.

        GIVEN: The annotate checkbox state is available
        WHEN: The user saves pending changes
        THEN: The parameter editor data model workflow receives the annotate flag and confirmation callback
        """
        editor = editor_factory()
        editor.annotate_params_into_files.get.return_value = True

        editor.ui.ask_yesno = MagicMock()
        editor.write_changes_to_intermediate_parameter_file()

        annotate_flag = editor.annotate_params_into_files.get()
        parameter_editor.handle_write_changes_workflow.assert_called_once_with(
            annotate_flag,
            editor.ui.ask_yesno,
        )

    def test_user_closes_application_after_saving_changes(self, parameter_editor_window: ParameterEditorWindow) -> None:
        """
        User closes the window after ensuring changes are saved.

        GIVEN: Focus rests on the parameter table
        WHEN: The user requests to close the application
        THEN: The focus widget is notified, changes are written, and Tk quits
        """
        focus_widget = MagicMock()

        with (
            patch.object(parameter_editor_window.parameter_editor_table.view_port, "focus_get", return_value=focus_widget),
            patch.object(parameter_editor_window, "write_changes_to_intermediate_parameter_file") as mock_write,
            patch.object(parameter_editor_window.root, "quit") as mock_quit,
        ):
            parameter_editor_window.close_connection_and_quit()

        focus_widget.event_generate.assert_called_once_with("<FocusOut>", when="now")
        mock_write.assert_called_once()
        mock_quit.assert_called_once()

    def test_user_can_close_application_during_other_navigation_locks(
        self, parameter_editor_window: ParameterEditorWindow
    ) -> None:
        """Calibration and diagnostics locks still allow saving and closing the application."""
        editor = parameter_editor_window
        editor.navigation_lock.acquire(self)
        with patch.object(editor, "_commit_focused_edit_and_offer_save") as save:
            editor.close_connection_and_quit()
        save.assert_called_once_with()
        editor.root.quit.assert_called_once_with()

    @pytest.mark.parametrize("save_result", [True, False])
    def test_user_hands_off_after_being_offered_to_save_changes(
        self, parameter_editor_window: ParameterEditorWindow, save_result: bool
    ) -> None:
        """The handoff proceeds after the user accepts or declines the optional save prompt."""
        events: list[str] = []
        focus_widget = MagicMock()
        focus_widget.event_generate.side_effect = lambda *_args, **_kwargs: events.append("commit focused edit")
        with (
            patch.object(parameter_editor_window.parameter_editor_table.view_port, "focus_get", return_value=focus_widget),
            patch.object(
                parameter_editor_window.parameter_editor,
                "handle_write_changes_workflow",
                side_effect=lambda *_args: (events.append("offer save"), save_result)[1],
            ),
            patch.object(parameter_editor_window.root, "destroy", side_effect=lambda: events.append("destroy window")),
            patch.object(
                parameter_editor_window.root,
                "mainloop",
                side_effect=parameter_editor_window.on_edit_vehicle_components_click,
            ),
        ):
            assert parameter_editor_window.run() is ParameterEditorAction.EDIT_COMPONENTS

        assert events == ["commit focused edit", "offer save", "destroy window"]
        focus_widget.event_generate.assert_called_once_with("<FocusOut>", when="now")

    def test_component_editor_handoff_is_refused_while_file_browser_is_open(
        self, parameter_editor_window: ParameterEditorWindow
    ) -> None:
        """The parameter editor remains alive while its non-modal browser is displayed."""
        browser_window = MagicMock()
        browser_window.root.winfo_exists.return_value = True
        parameter_editor_window._file_browser_window = browser_window

        parameter_editor_window.on_edit_vehicle_components_click()

        assert parameter_editor_window._requested_action is ParameterEditorAction.FINISHED
        parameter_editor_window.root.destroy.assert_not_called()
        parameter_editor_window.ui.show_error.assert_called_once_with(
            "File browser is open",
            "Close the flight-controller file browser before editing vehicle components.",
        )
        browser_window.root.destroy.assert_not_called()

    def test_component_editor_handoff_is_refused_while_log_analysis_is_running(
        self, parameter_editor_window: ParameterEditorWindow
    ) -> None:
        """Keep the editor open until the pending log analysis can deliver its result."""
        worker = MagicMock()
        worker.is_alive.return_value = True

        with patch(
            "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.threading.Thread",
            return_value=worker,
        ):
            parameter_editor_window._analyse_log_file("/fake/log.bin")

        parameter_editor_window.on_edit_vehicle_components_click()

        assert parameter_editor_window._requested_action is ParameterEditorAction.FINISHED
        parameter_editor_window.root.destroy.assert_not_called()
        parameter_editor_window._test_progress_windows[0].destroy.assert_not_called()  # type: ignore[attr-defined]
        parameter_editor_window.ui.show_error.assert_called_once_with(
            "Log analysis is running",
            "Wait for the flight log analysis to finish before editing vehicle components.",
        )

        worker.is_alive.return_value = False
        check_done = parameter_editor_window.root.after.call_args_list[-1].args[1]
        check_done()
        parameter_editor_window.on_edit_vehicle_components_click()

        parameter_editor_window._test_progress_windows[0].destroy.assert_called_once()  # type: ignore[attr-defined]
        assert parameter_editor_window._requested_action is ParameterEditorAction.EDIT_COMPONENTS
        parameter_editor_window.root.destroy.assert_called_once()

    def test_user_triggers_file_upload_helper_with_progress(self, editor_factory, parameter_editor: MagicMock) -> None:
        """
        User can upload the active parameter file directly to the flight controller.

        GIVEN: The upload workflow accepts confirmation, warning, and progress callbacks
        WHEN: The helper runs for the selected file
        THEN: The workflow receives the callbacks and any progress window is cleaned up
        """
        editor = editor_factory()

        progress_instance = MagicMock()
        progress_instance.update_progress_bar = MagicMock()
        editor.ui.create_progress_window = MagicMock(return_value=progress_instance)

        assert editor._should_upload_file_to_fc("01_initial.param") is True
        parameter_editor.should_upload_file_to_fc_workflow.assert_called_once()
        kwargs = parameter_editor.should_upload_file_to_fc_workflow.call_args.kwargs
        assert callable(kwargs["ask_confirmation"])
        assert callable(kwargs["show_error"])
        assert callable(kwargs["show_warning"])

        progress_instance.enable_transfer_progress.assert_called_once()
        snapshot = progress_instance.update_transfer_progress.call_args.args[0]
        assert snapshot.transferred_bytes == 10
        assert snapshot.total_bytes == 20
        assert snapshot.direction.name == "UPLOAD"
        progress_instance.destroy.assert_called_once()


class TestSkipButtonWorkflows:
    """Cover skip button behaviours and related helpers."""

    def test_user_completes_workflow_when_no_next_file(self, parameter_editor_window: ParameterEditorWindow) -> None:
        """When no next file exists, summary workflow runs and window closes."""
        param_editor_mock = cast("MagicMock", parameter_editor_window.parameter_editor)
        param_editor_mock.get_next_non_optional_file.return_value = None

        with (
            patch.object(parameter_editor_window, "write_changes_to_intermediate_parameter_file") as mock_write,
            patch.object(param_editor_mock, "write_summary_files_workflow") as mock_summary,
            patch.object(parameter_editor_window, "close_connection_and_quit") as mock_quit,
        ):
            parameter_editor_window.on_skip_click()

        mock_write.assert_called_once()
        mock_summary.assert_called_once()
        mock_quit.assert_called_once()

    def test_user_advances_to_next_file_when_available(self, parameter_editor_window: ParameterEditorWindow) -> None:
        """Skip button selects the next file when workflow returns one."""
        param_editor_mock = cast("MagicMock", parameter_editor_window.parameter_editor)
        param_editor_mock.get_next_non_optional_file.return_value = "02_next.param"

        with (
            patch.object(parameter_editor_window, "write_changes_to_intermediate_parameter_file") as mock_write,
            patch.object(parameter_editor_window, "on_param_file_combobox_change") as mock_change,
        ):
            parameter_editor_window.on_skip_click()

        mock_write.assert_called_once()
        combobox_mock = cast("MagicMock", parameter_editor_window.file_selection_combobox)
        combobox_mock.set.assert_called_once_with("02_next.param")
        mock_change.assert_called_once_with(None)

    def test_skip_button_disabled_in_simple_mode(self, parameter_editor_window: ParameterEditorWindow) -> None:
        """Simple mode with required step keeps skip button disabled when FC connected."""
        parameter_editor_window.gui_complexity = "simple"
        param_editor_mock = cast("MagicMock", parameter_editor_window.parameter_editor)
        param_editor_mock.is_configuration_step_optional.return_value = False
        param_editor_mock.is_fc_connected = True

        parameter_editor_window._update_skip_button_state()

        skip_button_mock = cast("MagicMock", parameter_editor_window.skip_button)
        skip_button_mock.configure.assert_called_once_with(state="disabled")

    def test_skip_button_enabled_for_optional_step(self, parameter_editor_window: ParameterEditorWindow) -> None:
        """Optional steps keep skip button enabled even in simple mode."""
        parameter_editor_window.gui_complexity = "simple"
        param_editor_mock = cast("MagicMock", parameter_editor_window.parameter_editor)
        param_editor_mock.is_configuration_step_optional.return_value = True
        param_editor_mock.is_fc_connected = True

        parameter_editor_window._update_skip_button_state()

        skip_button_mock = cast("MagicMock", parameter_editor_window.skip_button)
        skip_button_mock.configure.assert_called_once_with(state="normal")

    def test_user_returns_to_previous_file_when_available(self, parameter_editor_window: ParameterEditorWindow) -> None:
        """
        User can return to the preceding configuration step.

        GIVEN: The current file is not the first configuration step
        WHEN: The user clicks the previous button
        THEN: Pending edits are saved and the preceding file is selected
        """
        # Arrange
        parameter_editor_window.previous_button = MagicMock()
        combobox_mock = cast("MagicMock", parameter_editor_window.file_selection_combobox)
        combobox_mock.get.return_value = "02_current.param"
        parameter_editor_window.parameter_editor.get_previous_non_optional_file.return_value = "01_first.param"

        # Act
        with (
            patch.object(parameter_editor_window, "write_changes_to_intermediate_parameter_file") as mock_write,
            patch.object(parameter_editor_window, "on_param_file_combobox_change") as mock_change,
        ):
            parameter_editor_window.on_previous_click()

        # Assert
        mock_write.assert_called_once()
        parameter_editor_window.parameter_editor.get_previous_non_optional_file.assert_called_once_with(
            current_file="02_current.param", gui_complexity=parameter_editor_window.gui_complexity
        )
        combobox_mock.set.assert_called_once_with("01_first.param")
        mock_change.assert_called_once_with(None)

    def test_previous_button_disabled_for_first_file(self, parameter_editor_window: ParameterEditorWindow) -> None:
        """
        User cannot navigate before the first configuration step.

        GIVEN: The first parameter file is selected
        WHEN: The navigation controls refresh
        THEN: The previous button is disabled
        """
        # Arrange
        parameter_editor_window.previous_button = MagicMock()
        combobox_mock = cast("MagicMock", parameter_editor_window.file_selection_combobox)
        combobox_mock.get.return_value = "01_first.param"
        parameter_editor_window.parameter_editor.get_previous_non_optional_file.return_value = None

        # Act
        parameter_editor_window._update_previous_button_state()

        # Assert
        previous_button_mock = parameter_editor_window.previous_button
        previous_button_mock.configure.assert_called_once_with(state="disabled")

    def test_previous_navigation_skips_optional_steps_in_simple_mode(
        self, parameter_editor_window: ParameterEditorWindow
    ) -> None:
        """
        User returns to the preceding required configuration step in simple mode.

        GIVEN: The current step follows an optional configuration step
        WHEN: The user clicks the Previous button
        THEN: The editor selects the preceding required step
        """
        # Arrange (Given): Model the required step returned by simple-mode navigation.
        parameter_editor_window.gui_complexity = "simple"
        combobox_mock = cast("MagicMock", parameter_editor_window.file_selection_combobox)
        combobox_mock.get.return_value = "03_current.param"
        parameter_editor_window.parameter_editor.get_previous_non_optional_file.return_value = "01_required.param"

        # Act (When): Navigate to the preceding configuration step.
        with (
            patch.object(parameter_editor_window, "write_changes_to_intermediate_parameter_file") as mock_write,
            patch.object(parameter_editor_window, "on_param_file_combobox_change") as mock_change,
        ):
            parameter_editor_window.on_previous_click()

        # Assert (Then): The optional step is not selected or shown.
        parameter_editor_window.parameter_editor.get_previous_non_optional_file.assert_called_once_with(
            current_file="03_current.param", gui_complexity="simple"
        )
        mock_write.assert_called_once()
        combobox_mock.set.assert_called_once_with("01_required.param")
        mock_change.assert_called_once_with(None)


class TestZipVehicleForForumHelpButton:
    """Test the 'Zip Vehicle for Forum Help' button functionality."""

    def test_user_clicks_button_and_workflow_succeeds(self, parameter_editor_window: ParameterEditorWindow) -> None:
        """Given parameter files exist, when user clicks button, then workflow executes and shows success message."""
        # Arrange
        param_editor_mock = cast("MagicMock", parameter_editor_window.parameter_editor)
        param_editor_mock.create_forum_help_zip_workflow.return_value = True

        # Act
        parameter_editor_window.on_zip_vehicle_for_forum_help_click()

        # Assert
        param_editor_mock.create_forum_help_zip_workflow.assert_called_once_with(
            show_error=parameter_editor_window.ui.show_error,
            show_info=parameter_editor_window.ui.show_info,
        )

    def test_user_clicks_button_and_workflow_fails(self, parameter_editor_window: ParameterEditorWindow) -> None:
        """Given workflow fails, when user clicks button, then error is shown to user."""
        # Arrange
        param_editor_mock = cast("MagicMock", parameter_editor_window.parameter_editor)
        param_editor_mock.create_forum_help_zip_workflow.return_value = False

        # Act
        parameter_editor_window.on_zip_vehicle_for_forum_help_click()

        # Assert - workflow was called even though it failed
        param_editor_mock.create_forum_help_zip_workflow.assert_called_once()

    def test_workflow_receives_correct_ui_callbacks(self, parameter_editor_window: ParameterEditorWindow) -> None:
        """Given button is clicked, when workflow is invoked, then correct UI callbacks are injected."""
        # Arrange
        param_editor_mock = cast("MagicMock", parameter_editor_window.parameter_editor)
        param_editor_mock.create_forum_help_zip_workflow.return_value = True

        # Act
        parameter_editor_window.on_zip_vehicle_for_forum_help_click()

        # Assert - verify the exact callbacks passed
        call_args = param_editor_mock.create_forum_help_zip_workflow.call_args
        assert call_args is not None
        assert call_args.kwargs["show_error"] == parameter_editor_window.ui.show_error
        assert call_args.kwargs["show_info"] == parameter_editor_window.ui.show_info

    def test_button_callback_is_properly_bound(self, parameter_editor_window: ParameterEditorWindow) -> None:
        """Given ParameterEditorWindow is created, when checking button, then callback is correctly bound."""
        # This tests the integration between button creation and the handler method
        # We verify the method exists and is callable
        assert hasattr(parameter_editor_window, "on_zip_vehicle_for_forum_help_click")
        assert callable(parameter_editor_window.on_zip_vehicle_for_forum_help_click)

    def test_workflow_error_handling_with_show_error(self, parameter_editor_window: ParameterEditorWindow) -> None:
        """Given workflow encounters error, when executed, then error callback is available for use."""
        # Arrange - simulate workflow calling show_error callback
        param_editor_mock = cast("MagicMock", parameter_editor_window.parameter_editor)

        def workflow_with_error(**kwargs: Callable) -> bool:
            # Simulate the workflow calling show_error
            kwargs["show_error"]("Test Error", "Error details")
            return False

        param_editor_mock.create_forum_help_zip_workflow.side_effect = workflow_with_error

        # Act
        parameter_editor_window.on_zip_vehicle_for_forum_help_click()

        # Assert - show_error was called by the workflow
        ui_mock = cast("MagicMock", parameter_editor_window.ui.show_error)
        ui_mock.assert_called_once_with("Test Error", "Error details")

    def test_workflow_success_handling_with_show_info(self, parameter_editor_window: ParameterEditorWindow) -> None:
        """Given workflow succeeds, when executed, then info callback is available for notification."""
        # Arrange - simulate workflow calling show_info callback
        param_editor_mock = cast("MagicMock", parameter_editor_window.parameter_editor)

        def workflow_with_success(**kwargs: Callable) -> bool:
            # Simulate the workflow calling show_info
            kwargs["show_info"]("Success", "Zip created successfully")
            return True

        param_editor_mock.create_forum_help_zip_workflow.side_effect = workflow_with_success

        # Act
        parameter_editor_window.on_zip_vehicle_for_forum_help_click()

        # Assert - show_info was called by the workflow
        ui_mock = cast("MagicMock", parameter_editor_window.ui.show_info)
        ui_mock.assert_called_once_with("Success", "Zip created successfully")

    def test_multiple_button_clicks_invoke_workflow_each_time(self, parameter_editor_window: ParameterEditorWindow) -> None:
        """Given button is clicked multiple times, when each click occurs, then workflow executes each time."""
        # Arrange
        param_editor_mock = cast("MagicMock", parameter_editor_window.parameter_editor)
        param_editor_mock.create_forum_help_zip_workflow.return_value = True

        # Act - click button three times
        parameter_editor_window.on_zip_vehicle_for_forum_help_click()
        parameter_editor_window.on_zip_vehicle_for_forum_help_click()
        parameter_editor_window.on_zip_vehicle_for_forum_help_click()

        # Assert - workflow was called three times
        assert param_editor_mock.create_forum_help_zip_workflow.call_count == 3


class TestStepInstructionsPopupWorkflows:
    """Cover the step instructions popup behaviors when navigating files."""

    def test_user_sees_info_popup_when_instructions_exist(self, parameter_editor_window: ParameterEditorWindow) -> None:
        """
        User receives an informational popup for steps with info instructions.

        GIVEN: Instructions exist with type 'info'
        WHEN: The parameter file changes to that step
        THEN: An info popup is displayed to the user
        """
        param_editor_mock = cast("MagicMock", parameter_editor_window.parameter_editor)
        param_editor_mock.get_instructions_popup.return_value = {"type": "info", "msg": "Test info message"}

        parameter_editor_window.on_param_file_combobox_change(None)

        ui_mock = cast("MagicMock", parameter_editor_window.ui)
        ui_mock.show_info.assert_called_once_with("Step Instructions", "Test info message")
        ui_mock.show_warning.assert_not_called()

    def test_user_sees_warning_popup_when_instructions_exist(self, parameter_editor_window: ParameterEditorWindow) -> None:
        """
        User receives a warning popup for steps with warning instructions.

        GIVEN: Instructions exist with type 'warning'
        WHEN: The parameter file changes to that step
        THEN: A warning popup is displayed to the user
        """
        param_editor_mock = cast("MagicMock", parameter_editor_window.parameter_editor)
        param_editor_mock.get_instructions_popup.return_value = {"type": "warning", "msg": "Test warning message"}

        parameter_editor_window.on_param_file_combobox_change(None)

        ui_mock = cast("MagicMock", parameter_editor_window.ui)
        ui_mock.show_warning.assert_called_once_with("Step Instructions", "Test warning message")
        ui_mock.show_info.assert_not_called()


class TestInlineComponentEditorCallbacks:
    """Tests for the inline component editor data-sync and table-refresh callback."""

    @pytest.mark.parametrize("plugin_name", ["rc_calibration", "battery_monitor"])
    def test_offline_component_edits_preserve_plugin_placeholder(
        self,
        parameter_editor_window: ParameterEditorWindow,
        parameter_editor: MagicMock,
        root: tk.Tk,
        caplog: pytest.LogCaptureFixture,
        plugin_name: str,
    ) -> None:
        """
        Editing components offline keeps the unavailable plugin's existing explanation.

        GIVEN: A plugin cannot load without a flight controller connection.
        WHEN: The user edits five inline component fields.
        THEN: The placeholder survives and the connection warning is logged only once.
        """
        editor = parameter_editor_window
        plugin = {"name": plugin_name, "placement": "left"}
        editor.current_plugin = plugin
        editor.current_plugin_view = None
        parameter_editor.get_plugin.return_value = plugin
        parameter_editor.create_plugin_data_model.return_value = None
        inline_editor = MagicMock()
        inline_editor.get_component_data.return_value = {"Components": {"Battery": {}}}
        editor.inline_component_editor = inline_editor
        parent = ttk.Frame(root)
        paned = MagicMock()
        paned.panes.return_value = ("plugin",)
        paned.nametowidget.return_value = parent
        editor.parameter_area_paned = paned
        try:
            with patch.object(parameter_editor_module.plugin_factory, "is_registered", return_value=True):
                editor._load_plugin(parent, plugin)
                placeholder = parent.winfo_children()[0]
                for _ in range(5):
                    editor._on_component_data_changed()

            assert parent.winfo_children() == [placeholder]
            assert editor.current_plugin_view is None
            assert sum("Plugin requires flight controller connection" in record.message for record in caplog.records) == 1
            assert parameter_editor.update_vehicle_components.call_count == 5
        finally:
            parent.destroy()

    def test_component_data_change_calls_update_and_refresh(self, parameter_editor: MagicMock) -> None:
        """
        Callback delegates sync to update_vehicle_components() and triggers a refresh.

        GIVEN: An inline component editor whose data_model contains updated component data
        WHEN: _on_component_data_changed() is called
        THEN: update_vehicle_components() is called with the editor's component dict
        AND: refresh_current_step_computed_parameters() is called on the data model
        AND: The parameter table is repopulated
        """
        editor = _create_editor(parameter_editor)
        editor.repopulate_parameter_table = MagicMock()
        editor._update_plugin_layout = MagicMock()
        parameter_editor.current_file = "09_esc_telemetry.param"
        parameter_editor.get_plugin.return_value = {"name": "esc_rpm_scale", "placement": "left"}

        updated_components = {"Battery": {"Specifications": {"Volt per cell max": 4.2}}}
        mock_inline_editor = MagicMock()
        mock_inline_editor.get_component_data.return_value = {"Components": updated_components}
        editor.inline_component_editor = mock_inline_editor

        editor._on_component_data_changed()

        parameter_editor.update_vehicle_components.assert_called_once_with(updated_components)
        parameter_editor.refresh_current_step_computed_parameters.assert_called_once()
        parameter_editor.get_plugin.assert_called_once_with("09_esc_telemetry.param")
        editor._update_plugin_layout.assert_called_once_with({"name": "esc_rpm_scale", "placement": "left"})
        editor.repopulate_parameter_table.assert_called_once()

    def test_component_data_change_returns_early_when_no_inline_editor(self, parameter_editor: MagicMock) -> None:
        """
        Callback returns immediately when the inline editor is absent.

        GIVEN: inline_component_editor is None (no inline editor active for this step)
        WHEN: _on_component_data_changed() is called
        THEN: No AttributeError is raised
        AND: refresh_current_step_computed_parameters() is NOT called (no data to sync)
        AND: The parameter table is NOT repopulated
        """
        editor = _create_editor(parameter_editor)
        editor.repopulate_parameter_table = MagicMock()
        editor.inline_component_editor = None

        editor._on_component_data_changed()

        parameter_editor.refresh_current_step_computed_parameters.assert_not_called()
        editor.repopulate_parameter_table.assert_not_called()

    def test_component_data_change_delegates_none_fs_data_to_update_method(self, parameter_editor: MagicMock) -> None:
        """
        Callback delegates the None-data guard to update_vehicle_components(), then refreshes.

        GIVEN: vehicle_components_fs.data is None (file was never loaded)
        WHEN: _on_component_data_changed() is called
        THEN: No AttributeError is raised
        AND: update_vehicle_components() is called (it handles None internally)
        AND: refresh_current_step_computed_parameters() is called
        """
        editor = _create_editor(parameter_editor)
        editor.repopulate_parameter_table = MagicMock()

        mock_inline_editor = MagicMock()
        mock_inline_editor.get_component_data.return_value = {"Components": {"Battery": {}}}
        editor.inline_component_editor = mock_inline_editor

        editor._on_component_data_changed()

        parameter_editor.update_vehicle_components.assert_called_once()
        parameter_editor.refresh_current_step_computed_parameters.assert_called_once()

    def test_component_data_change_is_skipped_when_already_updating(self, parameter_editor: MagicMock) -> None:
        """
        Callback exits immediately when re-entered (e.g. widget event during repopulate).

        GIVEN: _updating_inline_editor is True (callback is already executing)
        WHEN: _on_component_data_changed() is called again
        THEN: update_vehicle_components() is NOT called a second time
        AND: refresh_current_step_computed_parameters() is NOT called a second time
        """
        editor = _create_editor(parameter_editor)
        editor.repopulate_parameter_table = MagicMock()

        mock_inline_editor = MagicMock()
        mock_inline_editor.get_component_data.return_value = {"Components": {"Battery": {}}}
        editor.inline_component_editor = mock_inline_editor
        editor._updating_inline_editor = True  # simulate re-entry

        editor._on_component_data_changed()

        parameter_editor.update_vehicle_components.assert_not_called()
        parameter_editor.refresh_current_step_computed_parameters.assert_not_called()
        editor.repopulate_parameter_table.assert_not_called()


@pytest.fixture
def monitored_editor(parameter_editor_window: ParameterEditorWindow) -> ParameterEditorWindow:
    """Supply an editor with a controllable connection monitor and no live transport."""
    editor = parameter_editor_window
    monitor = MagicMock(spec=FlightControllerReconnect)
    monitor.cancelled = Event()
    monitor.poll.return_value = True
    monitor.reconnect.return_value = ""
    editor._connection_recovery = ConnectionRecovery(
        editor.root,
        monitor,
        RecoveryCallbacks(
            reader_busy=editor._connection_reader_busy,
            can_read=lambda: editor.current_plugin_view is None,
            pause_receiver=editor._pause_connection_plugin,
            lock_controls=editor._lock_connection_plugin,
            show_status=editor._show_connection_status,
            on_recovered=editor._finish_connection_recovery,
            can_refresh=lambda: not editor.parameter_editor_table.bitmask_editor_open,
        ),
    )
    editor._connection_status = MagicMock()
    editor._file_browser_window = None
    editor.root.winfo_children.return_value = []
    editor.root.tk.call.return_value = ""
    return editor


def test_active_plugin_keeps_sole_receive_ownership(monitored_editor: ParameterEditorWindow) -> None:
    """GIVEN an active plugin, WHEN the timer runs, THEN the monitor observes without reading."""
    editor = monitored_editor
    editor.current_plugin_view = MagicMock()
    editor._connection_recovery.check()
    editor._connection_recovery._monitor.poll.assert_called_once_with(read=False)
    editor.current_plugin_view.on_suspend.assert_not_called()


@pytest.mark.parametrize("owner", ["upload", "navigation", "browser", "native_dialog", "bitmask_dialog"])
def test_other_owners_defer_connection_checks(monitored_editor: ParameterEditorWindow, owner: str) -> None:
    """GIVEN another receive owner, WHEN the timer fires, THEN no receive or reconnect operation starts."""
    editor = monitored_editor
    if owner == "upload":
        editor._connection_recovery.acquire_operation()
    elif owner == "navigation":
        editor.navigation_lock.acquire(object())
    elif owner == "browser":
        editor._file_browser_window = MagicMock()
    elif owner == "bitmask_dialog":
        cast("MagicMock", editor.parameter_editor_table).bitmask_editor_open = True
    elif owner == "native_dialog":
        editor.root.tk.call.return_value = ".__tk__messagebox"
    editor._connection_recovery.check()
    editor._connection_recovery._monitor.poll.assert_not_called()
    editor._connection_recovery._monitor.reconnect.assert_not_called()
    editor._connection_recovery._monitor.defer.assert_called_once()


def test_nested_upload_event_loop_cannot_start_monitor_reads(monitored_editor: ParameterEditorWindow) -> None:
    """GIVEN an upload pumps Tk events, WHEN its timer fires, THEN upload replies remain exclusively owned."""
    editor = monitored_editor

    def upload(*_args: object) -> bool:
        editor._connection_recovery.check()
        return True

    editor.ui.upload_params_with_progress = upload
    assert editor.upload_selected_params({})
    editor._connection_recovery._monitor.poll.assert_not_called()
    assert not editor._connection_recovery.operation_active


@pytest.mark.parametrize("fails", [False, True], ids=["success", "failure"])
def test_reset_prevents_reentry_and_restores_plugin_and_navigation(
    monitored_editor: ParameterEditorWindow, fails: bool
) -> None:
    """
    Parameter reset retains exclusive ownership while its event loop is running.

    GIVEN: An active plugin and a parameter reset that services Tk events
    WHEN: Another reset is requested during the reset, which then succeeds or raises
    THEN: Only one reset runs, and plugin reception and navigation resume afterward.
    """
    editor = monitored_editor
    plugin = MagicMock(spec=["on_suspend", "on_resume"])
    editor.current_plugin_view = plugin

    def reset(*_args: object) -> bool:
        assert editor.navigation_lock.locked
        assert editor._connection_recovery.operation_active
        plugin.on_suspend.assert_called_once()
        assert not editor.reset_all_parameters_to_default()
        editor._connection_recovery.check()
        if fails:
            message = "reset failed"
            raise RuntimeError(message)
        return True

    editor.ui.reset_all_parameters_to_default_with_progress = MagicMock(side_effect=reset)
    if fails:
        with pytest.raises(RuntimeError, match="reset failed"):
            editor.reset_all_parameters_to_default()
    else:
        assert editor.reset_all_parameters_to_default()
    editor.ui.reset_all_parameters_to_default_with_progress.assert_called_once()
    editor._connection_recovery._monitor.poll.assert_not_called()
    assert not editor.navigation_lock.locked
    assert not editor._connection_recovery.operation_active
    plugin.on_resume.assert_called_once()


def test_paused_plugin_with_buffered_heartbeat_resumes_without_reconnection(monitored_editor: ParameterEditorWindow) -> None:
    """GIVEN a plugin stopped reading, WHEN a buffered heartbeat proves liveness, THEN its state resumes unchanged."""
    editor = monitored_editor
    plugin = MagicMock(spec=["on_suspend", "on_resume"])
    editor.current_plugin_view = plugin
    editor._connection_recovery._monitor.poll.side_effect = [False, True]
    editor._connection_recovery.check()
    plugin.on_suspend.assert_called_once()
    plugin.on_resume.assert_called_once()
    editor._connection_recovery._monitor.reconnect.assert_not_called()
    assert not editor.navigation_lock.locked


@pytest.mark.parametrize("operation", ["inspector", "upload", "banner", "logs"])
def test_fc_tools_use_safety_pause_before_taking_reception(monitored_editor: ParameterEditorWindow, operation: str) -> None:
    """GIVEN an actuator plugin, WHEN an FC tool opens, THEN safety cleanup precedes the exclusive operation."""
    editor = monitored_editor
    plugin = MagicMock(spec=["on_suspend", "on_resume"])
    editor.current_plugin_view = plugin
    popup = MagicMock()

    def open_tool(*_args: object, **_kwargs: object) -> MagicMock:
        plugin.on_suspend.assert_called_once_with(PluginPauseReason.EXCLUSIVE_OPERATION)
        plugin.on_resume.assert_not_called()
        return popup

    with (
        patch.object(parameter_editor_module, "open_mavlink_inspector_window", side_effect=open_tool),
        patch.object(parameter_editor_module, "FlightControllerBannerWindow", side_effect=open_tool),
        patch.object(parameter_editor_module, "FileBrowserWindow", side_effect=open_tool),
    ):
        if operation == "inspector":
            editor.on_mavlink_inspector_click()
        elif operation == "upload":
            editor.ui.upload_params_with_progress = open_tool
            editor.upload_selected_params({})
        elif operation == "banner":
            editor.on_fc_banner_click()
        else:
            editor.on_download_bin_logs_click()
            popup.set_closed_callback.call_args.args[0]()

    plugin.on_suspend.assert_called_once_with(PluginPauseReason.EXCLUSIVE_OPERATION)
    plugin.on_resume.assert_called_once_with()


def test_connection_check_uses_passive_pause_when_available(monitored_editor: ParameterEditorWindow) -> None:
    """GIVEN an actuator plugin, WHEN checking buffered heartbeats, THEN no safety-stop command is requested."""
    editor = monitored_editor
    plugin = MagicMock(spec=["on_suspend", "on_resume"])
    editor.current_plugin_view = plugin
    editor._connection_recovery._monitor.poll.side_effect = [False, True]

    editor._connection_recovery.check()

    plugin.on_suspend.assert_called_once_with(PluginPauseReason.CONNECTION_RECOVERY)
    plugin.on_resume.assert_called_once_with()


@pytest.mark.parametrize("creation_fails", [False, True])
def test_log_browser_retains_an_explicit_lease_until_close(
    monitored_editor: ParameterEditorWindow, creation_fails: bool
) -> None:
    """GIVEN asynchronous browsing, WHEN opening returns or fails, THEN ownership follows the tool's actual lifetime."""
    editor = monitored_editor
    recovery = editor._connection_recovery
    popup = MagicMock()
    error = OSError("Browser unavailable")
    with patch.object(
        parameter_editor_module, "FileBrowserWindow", side_effect=error if creation_fails else None, return_value=popup
    ):
        if creation_fails:
            with pytest.raises(OSError, match="Browser unavailable"):
                editor.on_download_bin_logs_click()
        else:
            editor.on_download_bin_logs_click()
            assert recovery.operation_active
            popup.set_closed_callback.call_args.args[0]()
    assert not recovery.operation_active


@pytest.mark.parametrize("tool", ["preview", "export"])
def test_parameter_tool_retains_reception_until_its_root_is_destroyed(
    monitored_editor: ParameterEditorWindow, root: tk.Tk, tool: str
) -> None:
    """
    Keep asynchronous parameter tools protected independently of window visibility.

    GIVEN: A preview or export tool that does not use a modal grab
    WHEN: Its opening callback returns, a child closes, and its root is withdrawn
    THEN: It retains reception until its root closes, after which monitoring resumes
    """
    editor = monitored_editor
    recovery = editor._connection_recovery
    popup_root = tk.Toplevel(root)
    popup = SimpleNamespace(root=popup_root)
    child = ttk.Label(popup_root)
    editor.ui.askopenfilename = MagicMock(return_value="tune.param")
    try:
        with (
            patch.object(parameter_editor_module, "ParameterFileUploadWindow", return_value=popup),
            patch.object(parameter_editor_module, "ParameterExportWindow", return_value=popup),
        ):
            if tool == "preview":
                editor.on_compare_and_upload_parameter_file_click()
            else:
                editor.on_export_parameters_click()
        assert recovery.operation_active
        child.destroy()
        popup_root.withdraw()
        recovery.check()
        assert recovery.operation_active
        recovery._monitor.poll.assert_not_called()
    finally:
        popup_root.destroy()
    assert not recovery.operation_active
    recovery.check()
    recovery._monitor.poll.assert_called_once_with(read=True)


def test_overlapping_parameter_tools_release_only_their_own_lease(
    monitored_editor: ParameterEditorWindow, root: tk.Tk
) -> None:
    """GIVEN two tool windows, WHEN one closes twice, THEN the other keeps ownership until it closes."""
    editor = monitored_editor
    first, second = tk.Toplevel(root), tk.Toplevel(root)
    try:
        editor._retain_fc_operation_until_closed(first)
        editor._retain_fc_operation_until_closed(second)
        first.destroy()
        first.destroy()
        assert editor._connection_recovery.operation_active
    finally:
        if first.winfo_exists():
            first.destroy()
        second.destroy()
    assert not editor._connection_recovery.operation_active


def test_parameter_tool_bind_failure_does_not_leak_receive_ownership(monitored_editor: ParameterEditorWindow) -> None:
    """GIVEN a tool that cannot bind cleanup, WHEN ownership setup fails, THEN the lease is released."""
    root = MagicMock(spec=tk.Toplevel)
    root.bind.side_effect = tk.TclError("window destroyed")
    with pytest.raises(tk.TclError, match="window destroyed"):
        monitored_editor._retain_fc_operation_until_closed(root)
    assert not monitored_editor._connection_recovery.operation_active


def test_reconnection_retries_off_gui_thread_and_preserves_local_edits(monitored_editor: ParameterEditorWindow) -> None:
    """GIVEN an outage, WHEN retries eventually succeed, THEN the plugin resumes and pending widget edits are committed."""
    editor = monitored_editor
    plugin = MagicMock(spec=["on_suspend", "on_resume"])
    editor.current_plugin_view = plugin
    monitor = editor._connection_recovery._monitor
    monitor.poll.return_value = False
    attempts = iter(["Unavailable", "Different hardware ID", ""])
    worker_threads: list[int] = []

    def reconnect() -> str:
        worker_threads.append(threading.get_ident())
        return next(attempts)

    monitor.reconnect.side_effect = reconnect
    editor._connection_recovery.check()
    for _attempt in range(3):
        assert editor.navigation_lock.locked
        assert editor._connection_recovery._worker is not None
        editor._connection_recovery._worker.join(timeout=1)
        assert not editor._connection_recovery._worker.is_alive()
        editor._connection_recovery.check()

    assert len(worker_threads) == 3
    assert all(thread != threading.get_ident() for thread in worker_threads)
    assert not editor.navigation_lock.locked
    plugin.on_suspend.assert_called_once()
    plugin.on_resume.assert_called_once()
    editor.parameter_editor_table.view_port.focus_get().event_generate.assert_called_once_with("<FocusOut>", when="now")
    editor.parameter_editor.handle_write_changes_workflow.assert_not_called()
    editor.parameter_editor_table.repopulate_table.assert_called_once()


def test_editor_shutdown_retains_ownership_until_worker_finishes(monitored_editor: ParameterEditorWindow) -> None:
    """GIVEN a running reconnect, WHEN the editor closes, THEN the connection cannot leak into the next sub-application."""
    editor = monitored_editor
    monitor = editor._connection_recovery._monitor
    worker = MagicMock()
    editor._connection_recovery._worker = worker
    editor._connection_recovery._unlock = editor._lock_connection_plugin(editor._connection_recovery)
    assert not editor._stop_connection_monitor()
    assert monitor.cancelled.is_set()
    worker.join.assert_not_called()
    monitor.close.assert_not_called()
    assert editor.navigation_lock.locked

    worker.is_alive.return_value = False
    assert editor._stop_connection_monitor()
    monitor.close.assert_called_once()
    assert editor._connection_recovery is None
    assert not editor.navigation_lock.locked


def test_closing_during_recovery_keeps_tk_responsive_until_worker_yields(monitored_editor: ParameterEditorWindow) -> None:
    """
    Close safely while a slow telemetry recovery still owns the connection.

    GIVEN: A recovery worker is waiting for a parameter download
    WHEN: The user closes the editor and the worker later finishes
    THEN: Tk schedules another close attempt without joining and quits only after ownership is released
    """
    editor = monitored_editor
    worker = MagicMock()
    editor._connection_recovery._worker = worker
    with (
        patch.object(editor, "_commit_focused_edit_and_offer_save") as save,
        patch.object(editor, "_show_connection_status") as status,
    ):
        editor.close_connection_and_quit()
        worker.join.assert_not_called()
        editor.root.after.assert_called_once_with(50, editor._finish_pending_close)
        status.assert_called_once_with("Closing… Waiting for flight-controller recovery to stop.")
        editor.root.quit.assert_not_called()
        save.assert_not_called()

        worker.is_alive.return_value = False
        editor.root.after.call_args.args[1]()
        save.assert_called_once()
        editor.root.quit.assert_called_once()
        assert editor._connection_recovery is None


def test_recovery_locks_plugin_buttons_until_the_connection_owner_releases_them(
    monitored_editor: ParameterEditorWindow, root: tk.Tk
) -> None:
    """GIVEN a paused plugin with clickable controls, WHEN recovery owns reception, THEN the user cannot send commands."""
    editor = monitored_editor
    plugin = ttk.Frame(root)
    button = ttk.Button(plugin, text="Start calibration")
    disabled_button = ttk.Button(plugin, text="Unavailable", state="disabled")
    editor.current_plugin_view = cast("PluginView", plugin)
    try:
        unlock = editor._lock_connection_plugin(editor._connection_recovery._monitor)
        assert button.instate(("disabled",))
        unlock()
        assert not button.instate(("disabled",))
        assert disabled_button.instate(("disabled",))
        editor.navigation_lock.acquire(object())
        assert not button.instate(("disabled",))
    finally:
        plugin.destroy()


@pytest.mark.parametrize("visible", [False, True])
def test_report_visibility_does_not_prevent_idle_connection_monitoring(
    monitored_editor: ParameterEditorWindow, visible: bool
) -> None:
    """GIVEN a report without FC access, WHEN monitoring, THEN visibility does not imply receive ownership."""
    editor = monitored_editor
    report = MagicMock(spec=tk.Toplevel)
    report.winfo_viewable.return_value = visible
    editor.root.winfo_children.return_value = [report]
    editor._connection_recovery.check()
    editor._connection_recovery._monitor.poll.assert_called_once_with(read=True)


def test_close_during_configured_upload_keeps_monitor_until_upload_finishes(
    parameter_editor_window: ParameterEditorWindow,
) -> None:
    """GIVEN an active configured upload, WHEN closing, THEN defer shutdown until the upload yields the connection."""
    editor = parameter_editor_window
    editor._configured_upload_active = True
    with (
        patch.object(editor, "_stop_connection_monitor", return_value=True) as stop_monitor,
        patch.object(editor, "_commit_focused_edit_and_offer_save") as save,
    ):
        editor.close_connection_and_quit()
        assert editor._close_after_configured_upload
        stop_monitor.assert_not_called()
        save.assert_not_called()
        editor.root.quit.assert_not_called()

        editor._configured_upload_active = False
        editor.close_connection_and_quit()
        stop_monitor.assert_called_once()
        save.assert_called_once()
        editor.root.quit.assert_called_once()


@pytest.mark.parametrize("error", [KeyError("__tk__messagebox"), tk.TclError("bad window path name")])
def test_closing_still_saves_when_tk_focus_has_no_python_widget(
    parameter_editor_window: ParameterEditorWindow, error: Exception
) -> None:
    """GIVEN a native or destroyed popup owns focus, WHEN closing, THEN saving and quitting still complete."""
    editor = parameter_editor_window
    editor.parameter_editor_table.view_port.focus_get.side_effect = error
    editor.close_connection_and_quit()
    editor.parameter_editor.handle_write_changes_workflow.assert_called_once()
    editor.root.quit.assert_called_once()


def test_recovery_waits_for_bitmask_edits_before_repainting(monitored_editor: ParameterEditorWindow) -> None:
    """
    Recovery preserves rows referenced by an open bitmask dialog without a grab.

    GIVEN: A bitmask editor is open while a reconnect worker succeeds
    WHEN: The connection timer checks completion before and after the dialog closes
    THEN: The table is repainted once, only after the dialog releases its rows
    """
    editor = monitored_editor
    recovery = editor._connection_recovery
    assert recovery is not None
    table = cast("MagicMock", editor.parameter_editor_table)
    worker = MagicMock()
    worker.is_alive.return_value = False
    recovery._worker = worker
    recovery._state = RecoveryState.RECOVERING
    recovery._unlock = editor._lock_connection_plugin(recovery)
    resume = MagicMock()
    recovery._resume = resume
    table.bitmask_editor_open = True

    for _ in range(2):
        recovery.check()
        assert recovery.state is RecoveryState.RECOVERING
        assert editor.navigation_lock.locked
        table.repopulate_table.assert_not_called()
        resume.assert_not_called()

    table.bitmask_editor_open = False
    recovery.check()

    assert recovery.state is RecoveryState.MONITORING
    assert not editor.navigation_lock.locked
    table.repopulate_table.assert_called_once()
    resume.assert_called_once()


def test_recovery_resumes_plugin_when_tk_focus_points_to_a_destroyed_popup(monitored_editor: ParameterEditorWindow) -> None:
    """GIVEN stale focus after recovery, WHEN completion renders, THEN the plugin resumes and navigation unlocks."""
    editor = monitored_editor
    editor._connection_recovery._worker = MagicMock()
    editor._connection_recovery._worker.is_alive.return_value = False
    editor._connection_recovery._state = RecoveryState.RECOVERING
    resume_plugin = MagicMock()
    editor._connection_recovery._resume = resume_plugin
    editor._connection_recovery._unlock = editor._lock_connection_plugin(editor._connection_recovery)
    editor.parameter_editor_table.view_port.focus_get.side_effect = KeyError("missing-popup")
    editor._connection_recovery.check()
    resume_plugin.assert_called_once()
    assert not editor.navigation_lock.locked
    editor.parameter_editor_table.repopulate_table.assert_called_once()


@pytest.mark.parametrize("new_value", [1.0, 2.0, 3.0])
@pytest.mark.parametrize("refreshed_value", [2.0, None])
def test_recovery_refreshes_fc_cells_without_advancing_or_overwriting_edits(
    monitored_editor: ParameterEditorWindow, root: tk.Tk, new_value: float, refreshed_value: float | None
) -> None:
    """GIVEN edited parameters, WHEN recovery downloads new FC values, THEN repaint preserves the step and local edits."""
    editor = monitored_editor
    parameter = ArduPilotParameter("TEST_GAIN", Par(new_value, "Keep this reason"), fc_value=1.0)
    parameters = {parameter.name: parameter}
    editor.parameter_editor.current_step_parameters = parameters
    editor.parameter_editor.flight_controller.fc_parameters = (
        {parameter.name: refreshed_value} if refreshed_value is not None else {"OTHER_GAIN": 4.0}
    )
    editor.show_only_differences.get.return_value = True
    table = ParameterEditorTable(root, editor.parameter_editor, editor, parameters=parameters)
    editor.parameter_editor_table = table
    editor._connection_recovery._worker = MagicMock()
    editor._connection_recovery._worker.is_alive.return_value = False
    editor._connection_recovery._state = RecoveryState.RECOVERING
    with patch.object(editor, "on_skip_click") as skip:
        try:
            editor._connection_recovery.check()
            assert parameter.has_fc_value is (refreshed_value is not None)
            assert parameter.fc_value_as_string == ("2" if refreshed_value is not None else "N/A")
            assert parameter.value_as_string == str(int(new_value))
            assert parameter.change_reason == "Keep this reason"
            assert table.options.skip_when_no_differences
            skip.assert_not_called()
            if new_value != refreshed_value:
                expected_text = "2" if refreshed_value is not None else "N/A"
                assert str(table.view_port.grid_slaves(row=1, column=2)[0].cget("text")) == expected_text
        finally:
            table.destroy()


@pytest.mark.parametrize("platform", ["linux", "darwin"])
def test_user_can_close_bitmask_editor_after_recovery_repaints_rows(
    monitored_editor: ParameterEditorWindow, root: tk.Tk, platform: str
) -> None:
    """
    Checkbox edits remain usable after a recovery repaint.

    GIVEN a bitmask dialog opened during recovery with unsaved checkbox edits
    WHEN recovery repaints the table before the user closes the dialog
    THEN the dialog closes and its saved value appears in the replacement row.
    """
    editor = monitored_editor
    parameter = ArduPilotParameter(
        "TEST_OPTIONS", Par(1, "Keep this reason"), metadata={"Bitmask": {0: "First", 1: "Second"}}, fc_value=1
    )
    parameters = {parameter.name: parameter}
    editor.parameter_editor.current_step_parameters = parameters
    editor.parameter_editor.flight_controller.fc_parameters = {parameter.name: 3}
    editor.parameter_editor.update_parameter_object.side_effect = ParameterEditor.update_parameter_object
    with patch(
        "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.UsagePopupWindow.should_display",
        return_value=False,
    ):
        table = ParameterEditorTable(root, editor.parameter_editor, editor, parameters=parameters)
        editor.parameter_editor_table = table
        table.repopulate_table(show_only_differences=False, gui_complexity=editor.gui_complexity)
        entry = table._new_value_widgets[parameter.name]
        difference_label = table._value_is_different_labels[parameter.name]
        reason_entry = cast("ttk.Entry", table.view_port.grid_slaves(row=1, column=7)[0])
        event = tk.Event()
        event.widget = entry

        def recover_and_close(window: tk.Toplevel) -> None:
            checkbox = cast("ttk.Checkbutton", window.winfo_children()[0].winfo_children()[1])
            checkbox.invoke()
            # Exercise stale-row cleanup directly: real recovery defers while this dialog is open.
            editor._finish_connection_recovery()
            assert not entry.winfo_exists()
            assert not reason_entry.winfo_exists()
            window.tk.call(window.protocol("WM_DELETE_WINDOW"))
            assert not window.winfo_exists()

        try:
            with (
                patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.sys_platform", platform),
                patch.object(table, "_center_and_focus_window"),
                patch.object(tk.Misc, "update_idletasks"),
                patch.object(tk.Misc, "wait_window", autospec=True, side_effect=recover_and_close),
            ):
                table._open_bitmask_selection_window(event, parameter, reason_entry, difference_label)
            assert parameter.value_as_string == "3"
            assert parameter.change_reason == "Keep this reason"
            assert table._new_value_widgets[parameter.name].get() == "3"
            assert table._value_is_different_labels[parameter.name].cget("text") == " "
        finally:
            table.destroy()


def test_recovery_retries_plugin_enabled_by_component_edit(monitored_editor: ParameterEditorWindow, root: tk.Tk) -> None:
    """
    Recovery replaces a connection placeholder with the newly enabled plugin.

    GIVEN a component edit enables a plugin while recovery has no FC parameter cache
    WHEN the connection recovers and its parameter cache is available again
    THEN the placeholder is replaced by the plugin without navigating to another step.
    """
    editor = monitored_editor
    plugin = {"name": "esc_rpm_scale", "placement": "left"}
    editor.inline_component_editor = MagicMock()
    editor.inline_component_editor.get_component_data.return_value = {"Components": {"ESC": {}}}
    editor.parameter_editor.get_plugin.return_value = plugin
    editor.parameter_editor.create_plugin_data_model.return_value = None
    editor.parameter_editor.current_step_parameters = {}
    editor.parameter_editor.flight_controller.fc_parameters = {}
    editor.main_frame = ttk.Frame(root)
    editor.parameter_area_container = ttk.Frame(editor.main_frame)
    plugin_view = MagicMock()
    try:
        with (
            patch.object(parameter_editor_module.plugin_factory, "is_registered", return_value=True),
            patch.object(parameter_editor_module.plugin_factory, "create", return_value=plugin_view),
        ):
            editor._on_component_data_changed()
            parent = editor.parameter_area_paned.nametowidget(editor.parameter_area_paned.panes()[0])
            placeholder = parent.winfo_children()[0]
            assert editor.current_plugin == plugin
            assert editor.current_plugin_view is None
            editor.parameter_editor.create_plugin_data_model.return_value = object()
            editor.parameter_editor.flight_controller.fc_parameters = {"TEST_OPTIONS": 3}
            editor._connection_recovery._state = RecoveryState.RECOVERING
            editor._connection_recovery._worker = MagicMock()
            editor._connection_recovery._worker.is_alive.return_value = False
            editor._connection_recovery.check()

        assert not placeholder.winfo_exists()
        assert editor.current_plugin_view is plugin_view
        plugin_view.on_activate.assert_called_once()
    finally:
        editor.main_frame.destroy()


@pytest.mark.parametrize("owner_gone", ["plugin", "window"])
def test_recovery_does_not_resume_a_replaced_plugin(monitored_editor: ParameterEditorWindow, owner_gone: str) -> None:
    """GIVEN a paused plugin, WHEN its owner is replaced or destroyed before recovery finishes, THEN it stays stopped."""
    editor = monitored_editor
    plugin = MagicMock()
    editor.current_plugin_view = plugin
    resume = editor._pause_connection_plugin()
    assert resume is not None
    if owner_gone == "plugin":
        editor.current_plugin_view = MagicMock()
    else:
        editor.root.winfo_exists.return_value = False
    resume()
    plugin.on_resume.assert_not_called()


def test_close_during_recovery_keeps_tk_responsive_until_worker_yields(monitored_editor: ParameterEditorWindow) -> None:
    """GIVEN a blocked connection attempt, WHEN closing, THEN Tk schedules completion and keeps the FC locked meanwhile."""
    editor = monitored_editor
    worker = MagicMock()
    editor._connection_recovery._worker = worker
    editor._connection_recovery._unlock = editor._lock_connection_plugin(editor._connection_recovery)
    editor.close_connection_and_quit()
    editor.close_connection_and_quit()
    editor.close_connection_and_quit()
    editor.root.after.assert_called_once_with(50, editor._finish_pending_close)
    worker.join.assert_not_called()
    assert editor.navigation_lock.locked
    editor.root.quit.assert_not_called()
    worker.is_alive.return_value = False
    retry = editor.root.after.call_args.args[1]
    retry()
    editor.close_connection_and_quit()
    assert not editor.navigation_lock.locked
    editor.root.quit.assert_called_once()
    editor.parameter_editor.handle_write_changes_workflow.assert_called_once()


def test_inspector_disables_plugin_controls_without_a_modal_grab(monitored_editor: ParameterEditorWindow, root: tk.Tk) -> None:
    """GIVEN macOS permits input outside the inspector, WHEN it opens, THEN plugin controls stay disabled until it closes."""
    editor = monitored_editor
    plugin = ttk.Frame(root)
    button = ttk.Button(plugin, text="Start motor")
    editor.current_plugin_view = cast("PluginView", plugin)

    def wait(_window: object) -> None:
        assert button.instate(("disabled",))
        assert editor.navigation_lock.locked

    editor.root.wait_window.side_effect = wait
    with patch.object(parameter_editor_module, "open_mavlink_inspector_window"):
        try:
            editor.on_mavlink_inspector_click()
            assert not button.instate(("disabled",))
            assert not editor.navigation_lock.locked
        finally:
            plugin.destroy()
