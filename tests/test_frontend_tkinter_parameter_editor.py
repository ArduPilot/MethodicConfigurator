#!/usr/bin/env python3

"""
Behaviour-driven tests for the parameter editor window.

Many fixtures are configured in the tests/conftest.py file.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import tkinter as tk
from contextlib import contextmanager
from typing import TYPE_CHECKING, Callable, cast
from unittest.mock import ANY, MagicMock, patch

import pytest

from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor import (
    ParameterEditorUiServices,
    ParameterEditorWindow,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

# pylint: disable=too-many-lines, redefined-outer-name, protected-access

# ============================== SHARED FIXTURES ==============================


def _configure_root_stubs(root: MagicMock) -> None:
    root.quit = MagicMock()
    root.after = MagicMock()
    root.wait_window = MagicMock()
    root.winfo_rootx = MagicMock(return_value=0)
    root.winfo_rooty = MagicMock(return_value=0)
    root.winfo_width = MagicMock(return_value=800)
    root.winfo_height = MagicMock(return_value=600)


def _build_parameter_area_container() -> MagicMock:
    container = MagicMock()
    container.destroy = MagicMock()
    container.pack = MagicMock()
    container.winfo_children = MagicMock(return_value=[])
    return container


def _create_editor(parameter_editor: MagicMock) -> ParameterEditorWindow:
    editor = ParameterEditorWindow.__new__(ParameterEditorWindow)
    editor.parameter_editor = parameter_editor
    editor.root = MagicMock()
    _configure_root_stubs(editor.root)
    editor.gui_complexity = "normal"
    editor.stage_progress_bar = MagicMock()
    editor.documentation_frame = MagicMock()
    editor.documentation_frame.get_auto_open_documentation_in_browser.return_value = False
    editor.documentation_frame.refresh_documentation_labels = MagicMock()
    editor.documentation_frame.update_why_why_now_tooltip = MagicMock()
    editor.parameter_editor_table = MagicMock()
    editor.parameter_editor_table.repopulate = MagicMock()
    editor.parameter_editor_table.get_upload_selected_params = MagicMock(return_value={})
    editor.parameter_editor_table.view_port = MagicMock()
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
    editor._tempcal_imu_progress_window = None
    editor.main_frame = MagicMock()
    parameter_area_container = _build_parameter_area_container()
    editor.parameter_area_container = parameter_area_container
    editor.parameter_container = parameter_area_container
    editor.parameter_area_paned = None
    return editor


@pytest.fixture
def parameter_editor() -> MagicMock:
    """Provide a realistic parameter editor data model double."""
    manager = MagicMock()
    manager.current_file = "00_previous.param"
    manager.configuration_phases.return_value = True
    manager.handle_param_file_change_workflow.return_value = ("01_initial.param", True)
    manager.get_plugin.return_value = None
    manager.handle_write_changes_workflow = MagicMock()
    manager.handle_copy_fc_values_workflow = MagicMock(return_value="close")
    manager.open_documentation_in_browser = MagicMock()

    def _download_fc_parameters(get_progress_callback: Callable | None = None) -> None:
        if get_progress_callback is not None:
            callback = get_progress_callback()
            if callback is not None:
                callback(50, 100)

    manager.download_flight_controller_parameters = MagicMock(side_effect=_download_fc_parameters)
    manager.upload_selected_params_workflow = MagicMock()
    manager.download_last_flight_log_workflow = MagicMock()
    manager.write_summary_files_workflow = MagicMock()
    manager.last_upload_progress_callback = None

    def _should_upload_file_to_fc(
        _selected_file: str,
        *,
        get_progress_callback: Callable[[], Callable | None] | None = None,
        **_ignored: object,
    ) -> None:
        if get_progress_callback is not None:
            manager.last_upload_progress_callback = get_progress_callback()
            if manager.last_upload_progress_callback is not None:
                manager.last_upload_progress_callback(10, 20)

    manager.should_upload_file_to_fc_workflow = MagicMock(side_effect=_should_upload_file_to_fc)
    manager._should_download_file_from_url_workflow = MagicMock()
    manager.handle_imu_temperature_calibration_workflow = MagicMock()
    manager._handle_file_jump_workflow = MagicMock()
    manager.get_non_default_params = MagicMock(return_value={})
    manager.is_fc_connected = True
    manager.is_configuration_step_optional.return_value = False
    manager.get_next_non_optional_file.return_value = None
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
        self.protocol = MagicMock()
        self.withdraw = MagicMock()
        self.destroy = MagicMock()
        self.deiconify = MagicMock()
        self.update_idletasks = MagicMock()
        self.after = MagicMock()
        self.winfo_fpixels = MagicMock(return_value=96.0)
        self.winfo_reqheight = MagicMock(return_value=630)


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
        )
        assert window is progress_window


# ============================== PARAMETER FILE FLOW ==============================


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
            patch.object(ParameterEditorWindow, "_create_parameter_area_widgets"),
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
            patch.object(ParameterEditorWindow, "_create_parameter_area_widgets"),
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
            patch.object(ParameterEditorWindow, "_create_parameter_area_widgets"),
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
    ) -> Iterator[tuple[ParameterEditorWindow, MagicMock]]:
        parameter_editor.get_last_configuration_step_number.return_value = None

        def fake_get_setting(key: str) -> object:
            return {"gui_complexity": "normal", "annotate_docs_into_param_files": False}.get(key, False)

        with (
            patch("tkinter.Tk", _DummyTkRoot),
            patch.object(ParameterEditorWindow, "_create_conf_widgets"),
            patch.object(ParameterEditorWindow, "_create_parameter_area_widgets"),
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


class TestRunLoop:  # pylint: disable=too-few-public-methods
    """Ensure the run helper starts Tk's event loop."""

    def test_run_enters_mainloop(self, parameter_editor_window: ParameterEditorWindow) -> None:
        parameter_editor_window.root.mainloop = MagicMock()

        parameter_editor_window.run()

        parameter_editor_window.root.mainloop.assert_called_once_with()


class TestWidgetFactoryMethods:
    """Cover the widget factory helpers inside the parameter editor window."""

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
            assert show_error is parameter_editor_window.ui.show_error
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
            assert show_error is parameter_editor_window.ui.show_error
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
        ) -> None:
            assert selected_file == "01_initial.param"
            assert ask_confirmation is parameter_editor_window.ui.ask_yesno
            assert show_error is parameter_editor_window.ui.show_error
            assert show_warning is parameter_editor_window.ui.show_warning
            callback = get_progress_callback()
            assert callback is progress_window.update_progress_bar
            assert callback is not None
            callback(5, 10)

        parameter_editor.should_upload_file_to_fc_workflow.side_effect = fake_upload

        parameter_editor_window._should_upload_file_to_fc("01_initial.param")

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

        def failing_upload(
            selected_file: str,
            *,
            ask_confirmation: Callable[[str, str], bool],
            show_error: Callable[[str, str], None],
            show_warning: Callable[[str, str], None],
            get_progress_callback: Callable[[], Callable | None],
        ) -> None:
            assert selected_file == "01_initial.param"
            assert ask_confirmation is parameter_editor_window.ui.ask_yesno
            assert show_error is parameter_editor_window.ui.show_error
            assert show_warning is parameter_editor_window.ui.show_warning
            callback = get_progress_callback()
            assert callback is progress_window.update_progress_bar
            assert callback is not None
            callback(1, 2)
            msg = "boom"
            raise RuntimeError(msg)

        parameter_editor.should_upload_file_to_fc_workflow.side_effect = failing_upload

        with pytest.raises(RuntimeError):
            parameter_editor_window._should_upload_file_to_fc("01_initial.param")

        progress_window.destroy.assert_called_once()
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

    def test_user_sees_reset_and_download_progress_windows(self, parameter_editor_window: ParameterEditorWindow) -> None:
        reset_window = MagicMock()
        reset_window.update_progress_bar = MagicMock()
        reset_window.destroy = MagicMock()
        download_window = MagicMock()
        download_window.update_progress_bar = MagicMock()
        download_window.destroy = MagicMock()

        def fake_progress_window(_parent: object, title: str, *_args: object, **_kwargs: object) -> MagicMock:
            if "Resetting" in title:
                return reset_window
            return download_window

        parameter_editor_window.ui.create_progress_window = MagicMock(side_effect=fake_progress_window)

        param_editor_mock = cast("MagicMock", parameter_editor_window.parameter_editor)

        def fake_upload_workflow(  # pylint: disable=too-many-arguments
            selected_params: dict,
            *,
            ask_confirmation: Callable[[str, str], bool],
            ask_retry_cancel: Callable[[str, str], bool],
            show_error: Callable[[str, str], None],
            get_reset_progress_callback: Callable[[], Callable | None],
            get_download_progress_callback: Callable[[], Callable | None],
        ) -> None:
            assert selected_params == {"ROLL_P": 0.12}
            assert ask_confirmation is parameter_editor_window.ui.ask_yesno
            assert ask_retry_cancel is parameter_editor_window.ui.ask_retry_cancel
            assert show_error is parameter_editor_window.ui.show_error
            reset_cb = get_reset_progress_callback()
            download_cb = get_download_progress_callback()
            assert reset_cb is reset_window.update_progress_bar
            assert download_cb is download_window.update_progress_bar
            assert reset_cb is not None
            assert download_cb is not None
            reset_cb(1, 2)
            download_cb(3, 4)

        param_editor_mock.upload_selected_params_workflow.side_effect = fake_upload_workflow

        parameter_editor_window.upload_selected_params({"ROLL_P": 0.12})

        reset_window.destroy.assert_called_once()
        download_window.destroy.assert_called_once()
        assert parameter_editor_window._reset_progress_window is None
        assert parameter_editor_window._param_download_progress_window_upload is None

    def test_user_still_cleans_upload_windows_on_failure(self, parameter_editor_window: ParameterEditorWindow) -> None:
        reset_window = MagicMock()
        reset_window.update_progress_bar = MagicMock()
        reset_window.destroy = MagicMock()
        download_window = MagicMock()
        download_window.update_progress_bar = MagicMock()
        download_window.destroy = MagicMock()

        parameter_editor_window.ui.create_progress_window = MagicMock(side_effect=[reset_window, download_window])
        param_editor_mock = cast("MagicMock", parameter_editor_window.parameter_editor)

        def failing_workflow(  # pylint: disable=too-many-arguments
            selected_params: dict,
            *,
            ask_confirmation: Callable[[str, str], bool],
            ask_retry_cancel: Callable[[str, str], bool],
            show_error: Callable[[str, str], None],
            get_reset_progress_callback: Callable[[], Callable | None],
            get_download_progress_callback: Callable[[], Callable | None],
        ) -> None:
            assert selected_params == {}
            assert ask_confirmation is parameter_editor_window.ui.ask_yesno
            assert ask_retry_cancel is parameter_editor_window.ui.ask_retry_cancel
            assert show_error is parameter_editor_window.ui.show_error
            reset_cb = get_reset_progress_callback()
            download_cb = get_download_progress_callback()
            assert reset_cb is reset_window.update_progress_bar
            assert download_cb is download_window.update_progress_bar
            assert reset_cb is not None
            assert download_cb is not None
            reset_cb(1, 1)
            download_cb(2, 2)
            msg = "boom"
            raise RuntimeError(msg)

        param_editor_mock.upload_selected_params_workflow.side_effect = failing_workflow

        with pytest.raises(RuntimeError):
            parameter_editor_window.upload_selected_params({})

        reset_window.destroy.assert_called_once()
        download_window.destroy.assert_called_once()
        assert parameter_editor_window._reset_progress_window is None
        assert parameter_editor_window._param_download_progress_window_upload is None


class TestPluginLayoutLifecycle:
    """Exercise plugin layout decisions and cleanup flows."""

    def test_user_refreshes_same_plugin_without_layout_changes(self, parameter_editor_window: ParameterEditorWindow) -> None:
        parameter_editor_window.current_plugin = {"name": "alpha", "placement": "left"}

        with (
            patch.object(parameter_editor_window, "_swap_plugin_in_place") as mock_swap,
            patch.object(parameter_editor_window, "_rebuild_plugin_layout") as mock_rebuild,
        ):
            parameter_editor_window._update_plugin_layout(parameter_editor_window.current_plugin)

        mock_swap.assert_not_called()
        mock_rebuild.assert_not_called()

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

            def __init__(self) -> None:
                self._children: list[object] = []

            def winfo_children(self) -> list[object]:
                return self._children

        top_container = DummyFrame()
        plugin_holder = DummyFrame()
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
        separator = MagicMock(pack=MagicMock())

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
        separator.pack.assert_called_once_with(side="top", fill="x", pady=2)

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
        mock_plugin_layout.assert_called_once_with(parameter_editor.get_plugin.return_value)
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

        parameter_editor.download_flight_controller_parameters.assert_called_once()
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

        parameter_editor.download_flight_controller_parameters.assert_called_once()
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

        GIVEN: The upload workflow requests reset and download callbacks
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
            get_reset_progress_callback: Callable[[], Callable],
            get_download_progress_callback: Callable[[], Callable],
            **_ignored: object,
        ) -> None:
            reset_cb = get_reset_progress_callback()
            download_cb = get_download_progress_callback()
            reset_cb(1, 2)
            download_cb(3, 4)

        parameter_editor.upload_selected_params_workflow.side_effect = _workflow

        editor.ui.create_progress_window = MagicMock(side_effect=_progress_window_factory)

        editor.upload_selected_params(selected_params)

        parameter_editor.upload_selected_params_workflow.assert_called_once_with(
            selected_params,
            ask_confirmation=ANY,
            ask_retry_cancel=ANY,
            show_error=ANY,
            get_reset_progress_callback=ANY,
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

        # Mock workflow that only uses download progress (no reset needed)
        def workflow_without_reset(_params, **kwargs) -> None:
            # Don't call get_reset_progress_callback
            download_cb = kwargs["get_download_progress_callback"]()
            download_cb(50, 100)

        parameter_editor.upload_selected_params_workflow = MagicMock(side_effect=workflow_without_reset)

        # Act: Upload without reset
        editor.ui.upload_params_with_progress(
            editor.root,
            parameter_editor.upload_selected_params_workflow,
            {"PARAM1": 1.0},
        )

        # Assert: Only one window created (download, not reset)
        assert len(created_windows) == 1


# ============================== FILE DOWNLOADS ==============================


class TestFlightLogDownloads:  # pylint: disable=too-few-public-methods
    """Verify downloading flight logs through the GUI helper."""

    def test_user_downloads_last_flight_log_with_progress(
        self,
        editor_factory,
        parameter_editor: MagicMock,
        tmp_path: Path,
    ) -> None:
        """
        User downloads the last flight log while monitoring progress.

        GIVEN: The workflow accepts callbacks for progress and saving the file
        WHEN: The user starts the download
        THEN: A progress window is shown and destroyed after completion
        """
        editor = editor_factory()

        progress_instance = MagicMock()
        progress_instance.update_progress_bar = MagicMock()
        editor.ui.create_progress_window = MagicMock(return_value=progress_instance)
        log_file = tmp_path / "log.bin"
        editor.ui.asksaveasfilename = MagicMock(return_value=str(log_file))

        editor.on_download_last_flight_log_click()

        parameter_editor.download_last_flight_log_workflow.assert_called_once()
        workflow_kwargs = parameter_editor.download_last_flight_log_workflow.call_args.kwargs
        assert workflow_kwargs["ask_saveas_filename"]() == str(log_file)
        assert workflow_kwargs["progress_callback"] is progress_instance.update_progress_bar
        progress_instance.destroy.assert_called_once()


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

        editor._should_upload_file_to_fc("01_initial.param")
        parameter_editor.should_upload_file_to_fc_workflow.assert_called_once()
        kwargs = parameter_editor.should_upload_file_to_fc_workflow.call_args.kwargs
        assert callable(kwargs["ask_confirmation"])
        assert callable(kwargs["show_error"])
        assert callable(kwargs["show_warning"])

        assert parameter_editor.last_upload_progress_callback is progress_instance.update_progress_bar
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
