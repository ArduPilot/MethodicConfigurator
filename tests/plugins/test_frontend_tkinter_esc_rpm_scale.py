#!/usr/bin/env python3

"""
Behavior-driven tests for the ESC RPM scale upload workflow.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

from tkinter import Misc, Tk, ttk
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from ardupilot_methodic_configurator.plugins import frontend_tkinter_esc_rpm_scale as frontend
from ardupilot_methodic_configurator.plugins.data_model_esc_rpm_scale import (
    SCRIPT_FILENAME,
    SCRIPT_REMOTE_PATH,
    EscRpmScaleDataModel,
)
from ardupilot_methodic_configurator.plugins.plugin_constants import PLUGIN_ESC_RPM_SCALE
from ardupilot_methodic_configurator.plugins.plugin_factory import PluginFactory, PluginModelContext

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

    from pytest_mock import MockerFixture

# pylint: disable=redefined-outer-name, protected-access


def _descendants(widget: Misc) -> list[Misc]:
    """Return the widgets available to the user, including nested controls."""
    children = widget.winfo_children()
    return children + [descendant for child in children for descendant in _descendants(child)]


@pytest.fixture
def esc_view_factory(tk_root: Tk, tmp_path: Path) -> Generator[SimpleNamespace, None, None]:
    """Use a real model, widgets and temporary script directory; mock controller I/O."""
    controller = MagicMock(fc_parameters={})
    controller.upload_file.return_value = True
    filesystem = MagicMock(vehicle_dir=str(tmp_path))
    parent = ttk.Frame(tk_root)
    views = []

    def create(protocol: str = "Scripting", *, hobbywing: bool = True) -> frontend.EscRpmScaleView:
        filesystem.vehicle_components_fs.data = {
            "Components": {
                "ESC": {
                    "Product": {"Manufacturer": "Hobbywing" if hobbywing else "Other", "Model": "6X SE"},
                    "ESC->FC Telemetry": {"Protocol": protocol},
                }
            }
        }
        view = frontend.EscRpmScaleView(parent, EscRpmScaleDataModel(controller, filesystem), MagicMock())
        views.append(view)
        return view

    try:
        yield SimpleNamespace(create=create, controller=controller, filesystem=filesystem, parent=parent)
    finally:
        for view in views:
            view.destroy()
        parent.destroy()


@pytest.fixture
def upload_dialogs(mocker: MockerFixture) -> SimpleNamespace:
    """Replace modal dialogs so workflows run without waiting for user input."""
    return SimpleNamespace(
        ask=mocker.patch.object(frontend, "askfloat", return_value=0.714),
        info=mocker.patch.object(frontend, "showinfo"),
        error=mocker.patch.object(frontend, "showerror"),
    )


@pytest.mark.parametrize("hobbywing", [True, False])
def test_user_sees_scale_guidance_for_the_selected_esc(esc_view_factory: SimpleNamespace, hobbywing: bool) -> None:
    """
    Explain the correction appropriate to the selected product.

    GIVEN: Scripting telemetry and a known or generic ESC
    WHEN: The user opens the plugin
    THEN: Product guidance and the script upload action are visible
    """
    # Given / When: Open the plugin with the selected product.
    view = esc_view_factory.create(hobbywing=hobbywing)

    # Then: The explanation distinguishes the known correction from a generic scale.
    widgets = _descendants(view)
    labels = [str(widget.cget("text")) for widget in widgets if isinstance(widget, ttk.Label)]
    assert any("0.714" in text for text in labels) is hobbywing
    assert any("Lua script" in text or "Lua correction script" in text for text in labels)
    assert [str(widget.cget("text")) for widget in widgets if isinstance(widget, ttk.Button)] == [
        "Generate and upload RPM scale script"
    ]


def test_user_has_no_script_upload_action_for_non_scripting_telemetry(esc_view_factory: SimpleNamespace) -> None:
    """
    Hide an inapplicable Lua correction workflow.

    GIVEN: The ESC uses ordinary ESC telemetry
    WHEN: The user opens the plugin
    THEN: No script upload controls are offered
    """
    # Given / When: Open with a protocol that does not use scripting.
    view = esc_view_factory.create("ESC Telemetry")

    # Then: The plugin has no upload controls.
    assert not view.winfo_children()


def test_user_can_upload_the_requested_rpm_correction_script(
    esc_view_factory: SimpleNamespace, upload_dialogs: SimpleNamespace, tmp_path: Path
) -> None:
    """
    Generate the requested correction before uploading it.

    GIVEN: A connected Hobbywing ESC configuration
    WHEN: The user accepts a scale factor through the upload button
    THEN: The script contains that scale and the user sees successful upload feedback
    """
    # Given: A real view and data model backed by a temporary vehicle directory.
    view = esc_view_factory.create()
    upload_dialogs.ask.return_value = 0.625
    button = next(widget for widget in _descendants(view) if isinstance(widget, ttk.Button))

    # When: Activate the action through its real Tk command.
    button.invoke()

    # Then: The actual generated file and controller upload agree.
    script = tmp_path / SCRIPT_FILENAME
    assert script.read_text(encoding="utf-8") == EscRpmScaleDataModel.generate_script(0.625, 4)
    esc_view_factory.controller.upload_file.assert_called_once_with(str(script), SCRIPT_REMOTE_PATH, None)
    assert upload_dialogs.ask.call_args.kwargs == {"initialvalue": 0.714, "minvalue": 0.001, "maxvalue": 100.0, "parent": view}
    upload_dialogs.info.assert_called_once_with(
        "ESC RPM script uploaded", "The Lua script was uploaded to /APM/Scripts/esc_rpm_scale.lua.", parent=view
    )
    upload_dialogs.error.assert_not_called()


def test_user_can_cancel_without_creating_or_uploading_a_script(
    esc_view_factory: SimpleNamespace, upload_dialogs: SimpleNamespace, tmp_path: Path
) -> None:
    """
    Cancel the scale prompt without side effects.

    GIVEN: The script upload prompt
    WHEN: The user cancels it
    THEN: No script is created and no upload or result dialog occurs
    """
    # Given: The user dismisses the scale prompt.
    view = esc_view_factory.create()
    upload_dialogs.ask.return_value = None

    # When: Attempt the upload workflow.
    view._generate_and_upload()

    # Then: Cancellation leaves the vehicle directory untouched.
    assert not (tmp_path / SCRIPT_FILENAME).exists()
    esc_view_factory.controller.upload_file.assert_not_called()
    upload_dialogs.info.assert_not_called()
    upload_dialogs.error.assert_not_called()


@pytest.mark.parametrize("disconnected", [True, False])
def test_user_sees_failure_when_the_controller_cannot_receive_the_script(
    esc_view_factory: SimpleNamespace, upload_dialogs: SimpleNamespace, disconnected: bool
) -> None:
    """
    Report an unavailable upload rather than claiming success.

    GIVEN: A disconnected controller or an unsuccessful MAVFTP upload
    WHEN: The user requests the correction script
    THEN: The user sees the connection/MAVFTP requirement
    """
    # Given: Controller I/O cannot deliver the script.
    view = esc_view_factory.create()
    if disconnected:
        esc_view_factory.controller.master = None
    esc_view_factory.controller.upload_file.return_value = False

    # When: Request upload.
    view._generate_and_upload()

    # Then: No success is reported.
    upload_dialogs.error.assert_called_once_with(
        "ESC RPM script upload failed", "A flight controller connection with MAVFTP support is required.", parent=view
    )
    upload_dialogs.info.assert_not_called()
    assert esc_view_factory.controller.upload_file.called is not disconnected


@pytest.mark.parametrize("exception_type", [OSError, RuntimeError, ValueError])
def test_user_sees_the_upload_error_and_can_retry(
    esc_view_factory: SimpleNamespace, upload_dialogs: SimpleNamespace, exception_type: type[Exception]
) -> None:
    """
    Recover from expected upload errors.

    GIVEN: Controller upload raises an expected operational error
    WHEN: The user requests upload and then retries after recovery
    THEN: The error is shown and the subsequent upload succeeds
    """
    # Given: An I/O boundary fails on its first call.
    view = esc_view_factory.create()
    esc_view_factory.controller.upload_file.side_effect = [exception_type("Upload unavailable"), True]

    # When: Upload once, then retry.
    view._generate_and_upload()
    view._generate_and_upload()

    # Then: Both failure feedback and recovery are observable.
    upload_dialogs.error.assert_called_once_with("ESC RPM script upload failed", "Upload unavailable", parent=view)
    upload_dialogs.info.assert_called_once()


def test_registered_plugin_creates_a_working_scale_view(
    esc_view_factory: SimpleNamespace, mocker: MockerFixture, upload_dialogs: SimpleNamespace
) -> None:
    """
    Open the correction workflow through registered application dependencies.

    GIVEN: An isolated plugin registry and application dependencies
    WHEN: The application registers and creates the ESC RPM plugin
    THEN: Its real model and view can perform the upload workflow
    """
    # Given: Keep registration isolated from the global application registry.
    factory = PluginFactory()
    mocker.patch.object(frontend, "plugin_factory", factory)
    esc_view_factory.create()
    context = PluginModelContext(esc_view_factory.controller, esc_view_factory.filesystem, MagicMock())

    # When: Register and instantiate through the public factory API.
    frontend.register_esc_rpm_scale_plugin()
    model = factory.create_model(PLUGIN_ESC_RPM_SCALE, context)
    view = factory.create(PLUGIN_ESC_RPM_SCALE, esc_view_factory.parent, model, MagicMock())

    # Then: The generated view uses the model and supports its lifecycle and upload action.
    assert isinstance(view, frontend.EscRpmScaleView)
    assert isinstance(model, EscRpmScaleDataModel)
    try:
        view.on_activate()
        view._generate_and_upload()
        view.on_deactivate()
        upload_dialogs.info.assert_called_once()
    finally:
        view.destroy()
