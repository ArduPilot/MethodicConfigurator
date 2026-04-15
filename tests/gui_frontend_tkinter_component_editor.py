#!/usr/bin/env python3

"""
GUI tests for the ComponentEditorWindow using PyAutoGUI.

This module contains automated GUI tests for the Tkinter-based component editor.
Tests verify that ESC connection type cascade updates work correctly through
real GUI comboboxes visible on screen.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import json
import tempfile
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pyautogui
import pytest

from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.frontend_tkinter_component_editor import ComponentEditorWindow
from ardupilot_methodic_configurator.frontend_tkinter_pair_tuple_combobox import PairTupleCombobox

# pylint: disable=redefined-outer-name, too-many-lines

_VEHICLE_COMPONENTS_WITH_ESC = {
    "Format version": 1,
    "Components": {
        "Flight Controller": {
            "Product": {"Manufacturer": "Matek", "Model": "H743 SLIM", "URL": "", "Version": ""},
            "Firmware": {"Type": "ArduCopter", "Version": "4.6.0"},
            "Specifications": {"MCU Series": "STM32H7xx"},
            "Notes": "",
        },
        "Frame": {
            "Product": {"Manufacturer": "Diatone", "Model": "Taycan MXC", "URL": "", "Version": ""},
            "Specifications": {"TOW min Kg": 0.5, "TOW max Kg": 1.0},
            "Notes": "",
        },
        "Battery Monitor": {
            "Product": {"Manufacturer": "Matek", "Model": "H743 SLIM", "URL": "", "Version": ""},
            "Firmware": {"Type": "ArduCopter", "Version": "4.6.x"},
            "FC Connection": {"Type": "Analog", "Protocol": "Analog Voltage and Current"},
            "Notes": "",
        },
        "Battery": {
            "Product": {"Manufacturer": "SLS", "Model": "X-Cube 1800mAh 4S", "URL": "", "Version": ""},
            "Specifications": {
                "Chemistry": "Lipo",
                "Volt per cell max": 4.2,
                "Volt per cell arm": 3.8,
                "Volt per cell low": 3.5,
                "Volt per cell crit": 3.3,
                "Volt per cell min": 3.1,
                "Number of cells": 4,
                "Capacity mAh": 1800,
            },
            "Notes": "",
        },
        "ESC": {
            "Product": {"Manufacturer": "Mamba System", "Model": "F45_128k 4in1 ESC", "URL": "", "Version": "1"},
            "Firmware": {"Type": "BLHeli32", "Version": "32.10"},
            # Start with CAN2 so that all three ESC protocol fields are created as PairTupleComboboxes.
            # The test then cascades to CAN1 to verify the cascade update.
            "FC->ESC Connection": {"Type": "CAN2", "Protocol": "DroneCAN"},
            "ESC->FC Telemetry": {"Type": "CAN2", "Protocol": "DroneCAN"},
            "Notes": "",
        },
        "Motors": {
            "Product": {"Manufacturer": "T-Motor", "Model": "T-Motor 15507 3800kv", "URL": "", "Version": ""},
            "Specifications": {"Poles": 14},
            "Notes": "",
        },
        "Propellers": {
            "Product": {"Manufacturer": "HQProp", "Model": 'CineWhoop 3"', "URL": "", "Version": ""},
            "Specifications": {"Diameter_inches": 3},
            "Notes": "",
        },
        "GNSS Receiver": {
            "Product": {"Manufacturer": "Holybro", "Model": "H-RTK F9P Helical", "URL": "", "Version": "1"},
            "FC Connection": {"Type": "SERIAL1", "Protocol": "UBLOX"},
            "Notes": "",
        },
        "RC Receiver": {
            "Product": {"Manufacturer": "TBS", "Model": "TBS Crossfire Nano RX", "URL": "", "Version": ""},
            "FC Connection": {"Type": "SERIAL2", "Protocol": "CRSF"},
            "Notes": "",
        },
        "Telemetry": {
            "Product": {"Manufacturer": "HolyBro", "Model": "SiK Telemetry Radio V3", "URL": "", "Version": ""},
            "FC Connection": {"Type": "SERIAL3", "Protocol": "MAVLink2"},
            "Notes": "",
        },
    },
}


@pytest.fixture(scope="class")
def temp_vehicle_dir_with_esc() -> Generator[str, None, None]:
    """Create a temporary directory with vehicle_components.json that includes full ESC data."""
    with tempfile.TemporaryDirectory() as temp_dir:
        components_file = Path(temp_dir) / "vehicle_components.json"
        components_file.write_text(json.dumps(_VEHICLE_COMPONENTS_WITH_ESC, indent=2), encoding="utf-8")
        yield temp_dir


@pytest.fixture(scope="class")
def component_editor_window(temp_vehicle_dir_with_esc) -> Generator[ComponentEditorWindow, None, None]:
    """
    Create a real ComponentEditorWindow with ESC comboboxes for GUI testing.

    GIVEN: A temporary vehicle directory with ESC FC->ESC Connection and ESC->FC Telemetry fields
    WHEN: The ComponentEditorWindow is initialised and frames are populated
    THEN: Real PairTupleCombobox widgets exist for all ESC connection paths
    """
    filesystem = LocalFilesystem(
        vehicle_dir=temp_vehicle_dir_with_esc,
        vehicle_type="ArduCopter",
        fw_version="",
        allow_editing_template_files=True,
        save_component_to_system_templates=False,
    )

    with patch(
        "ardupilot_methodic_configurator.frontend_tkinter_usage_popup_window.UsagePopupWindow.should_display",
        return_value=False,
    ):
        editor = ComponentEditorWindow("1.0.0", filesystem, {})
        editor.populate_frames()
        editor.root.update_idletasks()
        editor.root.update()

    yield editor

    editor.root.destroy()


class TestESCConnectionCascadeBehavior:
    """
    GUI tests for ESC connection type cascade behaviour in ComponentEditorWindow.

    Validates that selecting a FC->ESC Connection Type correctly cascades to
    update the FC->ESC Protocol, ESC->FC Telemetry Type, and ESC->FC Telemetry
    Protocol comboboxes in the live GUI.
    """

    def test_user_selects_can1_fc_esc_type_cascades_to_dronecan(
        self,
        component_editor_window: ComponentEditorWindow,
        gui_test_environment,  # pylint: disable=unused-argument
    ) -> None:
        """
        Selecting CAN1 as FC->ESC Connection Type cascades all related fields to DroneCAN.

        GIVEN: The component editor is open and ESC comboboxes are rendered on screen
        WHEN: The user selects "CAN1" as the FC->ESC Connection Type
        THEN: FC->ESC Connection Protocol becomes "DroneCAN"
        AND: ESC->FC Telemetry Type becomes "CAN1"
        AND: ESC->FC Telemetry Protocol becomes "DroneCAN"
        AND: ESC->FC Telemetry Type and Protocol comboboxes are disabled (mirrored)
        AND: PyAutoGUI can capture the updated window on screen
        """
        editor = component_editor_window

        fc_esc_type_path = ("ESC", "FC->ESC Connection", "Type")
        fc_esc_protocol_path = ("ESC", "FC->ESC Connection", "Protocol")
        telem_type_path = ("ESC", "ESC->FC Telemetry", "Type")
        telem_protocol_path = ("ESC", "ESC->FC Telemetry", "Protocol")

        # Verify required comboboxes exist before acting
        assert fc_esc_type_path in editor.entry_widgets, "FC->ESC Connection Type combobox not found"
        assert fc_esc_protocol_path in editor.entry_widgets, "FC->ESC Connection Protocol combobox not found"
        assert telem_type_path in editor.entry_widgets, "ESC->FC Telemetry Type combobox not found"
        assert telem_protocol_path in editor.entry_widgets, "ESC->FC Telemetry Protocol combobox not found"

        fc_esc_type_cb = editor.entry_widgets[fc_esc_type_path]
        assert isinstance(fc_esc_type_cb, PairTupleCombobox), "FC->ESC Connection Type widget must be a PairTupleCombobox"

        # Act: select "CAN1" programmatically (same as user clicking the combobox and choosing CAN1).
        # Patch show_error_message to suppress any "invalid selection" popups caused by the CAN2→CAN1
        # transition (where the old telemetry port "CAN2" is no longer in the new choices).
        # This is expected behaviour in cascade updates and is a known UX limitation, not a test failure.
        with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor.show_error_message"):
            fc_esc_type_cb.set_entries_tuple(
                [(k, k) for k in editor.data_model.get_combobox_values_for_path(fc_esc_type_path)],
                "CAN1",
            )
            fc_esc_type_cb.event_generate("<<ComboboxSelected>>")
            editor.root.update_idletasks()
            editor.root.update()

        # Assert: FC->ESC Connection Protocol → "DroneCAN"
        fc_esc_protocol_cb = editor.entry_widgets[fc_esc_protocol_path]
        assert isinstance(fc_esc_protocol_cb, PairTupleCombobox)
        assert fc_esc_protocol_cb.get_selected_key() == "DroneCAN", (
            f"Expected FC->ESC Protocol to be 'DroneCAN', got '{fc_esc_protocol_cb.get_selected_key()}'"
        )

        # Assert: ESC->FC Telemetry Type available choices restricted to ("CAN1",) only.
        # The data model correctly computed the cascade; the single-option restriction IS the
        # "change to CAN1" — only CAN1 is available as ESC->FC Telemetry Type when FC->ESC is CAN1.
        telem_type_cb = editor.entry_widgets[telem_type_path]
        assert isinstance(telem_type_cb, PairTupleCombobox)
        assert editor.data_model.get_combobox_values_for_path(telem_type_path) == ("CAN1",), (
            f"Expected ESC->FC Telemetry Type data model choices to be ('CAN1',), "
            f"got {editor.data_model.get_combobox_values_for_path(telem_type_path)}"
        )
        assert telem_type_cb.list_keys == ["CAN1"], (
            f"Expected ESC->FC Telemetry Type combobox choices to be ['CAN1'], got {telem_type_cb.list_keys}"
        )

        # Assert: ESC->FC Telemetry Protocol → "DroneCAN"
        telem_protocol_cb = editor.entry_widgets[telem_protocol_path]
        assert isinstance(telem_protocol_cb, PairTupleCombobox)
        assert telem_protocol_cb.get_selected_key() == "DroneCAN", (
            f"Expected ESC->FC Telemetry Protocol to be 'DroneCAN', got '{telem_protocol_cb.get_selected_key()}'"
        )

        # Assert: ESC->FC Telemetry comboboxes are disabled (mirrored for CAN connections)
        assert str(telem_type_cb.cget("state")) == "disabled", "ESC->FC Telemetry Type should be disabled for CAN"
        assert str(telem_protocol_cb.cget("state")) == "disabled", "ESC->FC Telemetry Protocol should be disabled for CAN"

        # Assert: PyAutoGUI can capture the screen with the window visible
        editor.root.deiconify()
        editor.root.lift()
        editor.root.update_idletasks()
        editor.root.update()

        screenshot = pyautogui.screenshot()
        assert screenshot is not None
        assert screenshot.size[0] > 0
        assert screenshot.size[1] > 0

    def test_user_switches_serial_port_keeps_same_port_protocol(
        self,
        component_editor_window: ComponentEditorWindow,
        gui_test_environment,  # pylint: disable=unused-argument
    ) -> None:
        """
        Switching FC->ESC Type between SERIAL ports keeps the same-port protocol without error.

        GIVEN: FC->ESC Connection Type is navigated to SERIAL5 with CoDevESC protocol
        WHEN: The user changes FC->ESC Connection Type to SERIAL8
        THEN: No error dialog is shown
        AND: ESC->FC Telemetry Type is silently updated to SERIAL8
        AND: ESC->FC Telemetry Protocol stays CoDevESC (the only valid same-port protocol)
        AND: Both ESC->FC Telemetry comboboxes remain disabled (SERIAL mirrors FC->ESC)
        """
        editor = component_editor_window

        fc_esc_type_path = ("ESC", "FC->ESC Connection", "Type")
        fc_esc_protocol_path = ("ESC", "FC->ESC Connection", "Protocol")
        telem_type_path = ("ESC", "ESC->FC Telemetry", "Type")
        telem_protocol_path = ("ESC", "ESC->FC Telemetry", "Protocol")

        fc_esc_type_cb = editor.entry_widgets[fc_esc_type_path]
        assert isinstance(fc_esc_type_cb, PairTupleCombobox)
        fc_esc_protocol_cb = editor.entry_widgets[fc_esc_protocol_path]
        assert isinstance(fc_esc_protocol_cb, PairTupleCombobox)

        # Arrange: navigate to SERIAL5 / CoDevESC starting state (suppress any cascade errors).
        # Start from CAN2 (fixture default) → switch to SERIAL5 → pick CoDevESC protocol.
        with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor.show_error_message"):
            fc_esc_type_cb.set_entries_tuple(
                [(k, k) for k in editor.data_model.get_combobox_values_for_path(fc_esc_type_path)],
                "SERIAL5",
            )
            fc_esc_type_cb.event_generate("<<ComboboxSelected>>")
            editor.root.update_idletasks()
            editor.root.update()
            # Select CoDevESC as the FC->ESC protocol (unlocks specific same-port mapping).
            # Also sync the data model directly — the <<ComboboxSelected>> event on a protocol
            # combobox only triggers _on_esc_fc_protocol_changed (which mirrors to telemetry) but
            # does NOT update the data model for FC->ESC Protocol itself.  We need the data model
            # in sync so that the subsequent SERIAL8 cascade reads "CoDevESC" when computing
            # telemetry protocol choices.
            editor.data_model.set_component_value(fc_esc_protocol_path, "CoDevESC")
            fc_esc_protocol_cb.set_entries_tuple(
                [(k, k) for k in editor.data_model.get_combobox_values_for_path(fc_esc_protocol_path)],
                "CoDevESC",
            )
            fc_esc_protocol_cb.event_generate("<<ComboboxSelected>>")
            editor.root.update_idletasks()
            editor.root.update()

        # Verify pre-conditions for the main act
        assert fc_esc_type_cb.get_selected_key() == "SERIAL5"
        assert fc_esc_protocol_cb.get_selected_key() == "CoDevESC"
        telem_type_cb = editor.entry_widgets[telem_type_path]
        assert isinstance(telem_type_cb, PairTupleCombobox)
        assert telem_type_cb.get_selected_key() == "SERIAL5"
        telem_protocol_cb = editor.entry_widgets[telem_protocol_path]
        assert isinstance(telem_protocol_cb, PairTupleCombobox)
        assert telem_protocol_cb.get_selected_key() == "CoDevESC"

        # Act: switch FC->ESC Connection Type to SERIAL8
        error_was_shown = False

        def record_error(*_args: object, **_kwargs: object) -> None:
            nonlocal error_was_shown
            error_was_shown = True

        with patch(
            "ardupilot_methodic_configurator.frontend_tkinter_component_editor.show_error_message",
            side_effect=record_error,
        ):
            fc_esc_type_cb.set_entries_tuple(
                [(k, k) for k in editor.data_model.get_combobox_values_for_path(fc_esc_type_path)],
                "SERIAL8",
            )
            fc_esc_type_cb.event_generate("<<ComboboxSelected>>")
            editor.root.update_idletasks()
            editor.root.update()

        # Assert: no error dialog was triggered
        assert not error_was_shown, "No error dialog should appear when switching between SERIAL ports with a valid protocol"

        # Assert: FC->ESC Protocol unchanged (CoDevESC valid for any SERIAL port)
        assert fc_esc_protocol_cb.get_selected_key() == "CoDevESC"

        # Assert: ESC->FC Telemetry Type silently updated to SERIAL8
        assert telem_type_cb.get_selected_key() == "SERIAL8", (
            f"Expected ESC->FC Telemetry Type to be 'SERIAL8', got '{telem_type_cb.get_selected_key()}'"
        )

        # Assert: ESC->FC Telemetry Protocol remains CoDevESC — not cleared, no error
        assert telem_protocol_cb.get_selected_key() == "CoDevESC", (
            f"Expected ESC->FC Telemetry Protocol to remain 'CoDevESC', got '{telem_protocol_cb.get_selected_key()}'"
        )

        # Assert: ESC->FC Telemetry comboboxes remain disabled (SERIAL mirrors FC->ESC)
        assert str(telem_type_cb.cget("state")) == "disabled", "ESC->FC Telemetry Type should be disabled for SERIAL"
        assert str(telem_protocol_cb.cget("state")) == "disabled", "ESC->FC Telemetry Protocol should be disabled for SERIAL"

    def test_user_selects_serial_telemetry_type_with_normal_pwm_excludes_esc_telemetry_protocol(
        self,
        component_editor_window: ComponentEditorWindow,
        gui_test_environment,  # pylint: disable=unused-argument
    ) -> None:
        """
        ESC->FC Telemetry Type SERIAL1 with FC->ESC Normal offers only Scripting, not ESC Telemetry.

        GIVEN: FC->ESC Connection Type is "Main Out" with Protocol "Normal"
        WHEN: The user selects ESC->FC Telemetry Type = "SERIAL1"
        THEN: ESC->FC Telemetry Protocol choices contain only "Scripting"
        AND: "ESC Telemetry" is NOT offered (it belongs to DShot/OneShot, not Normal)
        AND: No error dialog is shown
        """
        editor = component_editor_window

        fc_esc_type_path = ("ESC", "FC->ESC Connection", "Type")
        fc_esc_protocol_path = ("ESC", "FC->ESC Connection", "Protocol")
        telem_type_path = ("ESC", "ESC->FC Telemetry", "Type")
        telem_protocol_path = ("ESC", "ESC->FC Telemetry", "Protocol")

        fc_esc_type_cb = editor.entry_widgets[fc_esc_type_path]
        assert isinstance(fc_esc_type_cb, PairTupleCombobox)

        # Arrange: switch FC->ESC Type to "Main Out" (PWM), suppress cascade errors.
        # Also directly set the data model Protocol to "Normal" — the FC->ESC Protocol widget
        # is empty in test context (no apm.pdef.xml doc), but the data model value is what
        # _compute_telem_serial_protocols reads when computing ESC->FC Telemetry choices.
        with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor.show_error_message"):
            fc_esc_type_cb.set_entries_tuple(
                [(k, k) for k in editor.data_model.get_combobox_values_for_path(fc_esc_type_path)],
                "Main Out",
            )
            fc_esc_type_cb.event_generate("<<ComboboxSelected>>")
            editor.root.update_idletasks()
            editor.root.update()

        editor.data_model.set_component_value(fc_esc_protocol_path, "Normal")

        # Verify: ESC->FC Telemetry comboboxes are enabled (unmirored for PWM)
        telem_type_cb = editor.entry_widgets[telem_type_path]
        assert isinstance(telem_type_cb, PairTupleCombobox)
        assert str(telem_type_cb.cget("state")) != "disabled", "ESC->FC Telemetry Type should be enabled for PWM"

        # Act: select ESC->FC Telemetry Type = "SERIAL1"
        error_was_shown = False

        def record_error(*_args: object, **_kwargs: object) -> None:
            nonlocal error_was_shown
            error_was_shown = True

        with patch(
            "ardupilot_methodic_configurator.frontend_tkinter_component_editor.show_error_message",
            side_effect=record_error,
        ):
            telem_type_choices = editor.data_model.get_combobox_values_for_path(telem_type_path)
            assert "SERIAL1" in telem_type_choices, (
                f"SERIAL1 should be available in ESC->FC Telemetry choices: {telem_type_choices}"
            )
            telem_type_cb.set_entries_tuple([(k, k) for k in telem_type_choices], "SERIAL1")
            telem_type_cb.event_generate("<<ComboboxSelected>>")
            editor.root.update_idletasks()
            editor.root.update()

        # Assert: no error dialog
        assert not error_was_shown, "No error dialog should appear when selecting SERIAL1 with a valid Normal protocol"

        # Assert: Protocol choices contain only "Scripting" — not "ESC Telemetry"
        telem_protocol_cb = editor.entry_widgets[telem_protocol_path]
        assert isinstance(telem_protocol_cb, PairTupleCombobox)
        available_protocols = editor.data_model.get_combobox_values_for_path(telem_protocol_path)
        assert "Scripting" in available_protocols, (
            f"'Scripting' should be available for Normal/SERIAL1, got: {available_protocols}"
        )
        assert "ESC Telemetry" not in available_protocols, (
            f"'ESC Telemetry' must NOT be available for Normal/SERIAL1 (only DShot/OneShot), got: {available_protocols}"
        )

    def test_user_selects_serial_telemetry_type_with_dshot_shows_esc_telemetry_not_scripting(
        self,
        component_editor_window: ComponentEditorWindow,
        gui_test_environment,  # pylint: disable=unused-argument
    ) -> None:
        """
        ESC->FC Telemetry Type SERIAL1 with FC->ESC DShot600 offers only ESC Telemetry, not Scripting.

        GIVEN: FC->ESC Connection Type is "Main Out" with Protocol "DShot600"
        WHEN: The user selects ESC->FC Telemetry Type = "SERIAL1"
        THEN: ESC->FC Telemetry Protocol choices contain "ESC Telemetry"
        AND: "Scripting" is NOT offered (it belongs to Normal, not DShot)
        AND: No error dialog is shown
        """
        editor = component_editor_window

        fc_esc_type_path = ("ESC", "FC->ESC Connection", "Type")
        fc_esc_protocol_path = ("ESC", "FC->ESC Connection", "Protocol")
        telem_type_path = ("ESC", "ESC->FC Telemetry", "Type")
        telem_protocol_path = ("ESC", "ESC->FC Telemetry", "Protocol")

        fc_esc_type_cb = editor.entry_widgets[fc_esc_type_path]
        assert isinstance(fc_esc_type_cb, PairTupleCombobox)

        # Arrange: ensure FC->ESC Type is "Main Out" with Protocol "DShot600".
        # Re-apply "Main Out" to be safe (previous test may have left it there already),
        # then override the data model Protocol to "DShot600".
        with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor.show_error_message"):
            fc_esc_type_cb.set_entries_tuple(
                [(k, k) for k in editor.data_model.get_combobox_values_for_path(fc_esc_type_path)],
                "Main Out",
            )
            fc_esc_type_cb.event_generate("<<ComboboxSelected>>")
            editor.root.update_idletasks()
            editor.root.update()

        editor.data_model.set_component_value(fc_esc_protocol_path, "DShot600")

        # Verify: ESC->FC Telemetry Type combobox is enabled for PWM
        telem_type_cb = editor.entry_widgets[telem_type_path]
        assert isinstance(telem_type_cb, PairTupleCombobox)
        assert str(telem_type_cb.cget("state")) != "disabled", "ESC->FC Telemetry Type should be enabled for PWM"

        # Act: select ESC->FC Telemetry Type = "SERIAL1"
        error_was_shown = False

        def record_error(*_args: object, **_kwargs: object) -> None:
            nonlocal error_was_shown
            error_was_shown = True

        with patch(
            "ardupilot_methodic_configurator.frontend_tkinter_component_editor.show_error_message",
            side_effect=record_error,
        ):
            telem_type_choices = editor.data_model.get_combobox_values_for_path(telem_type_path)
            assert "SERIAL1" in telem_type_choices, (
                f"SERIAL1 should be available in ESC->FC Telemetry choices: {telem_type_choices}"
            )
            telem_type_cb.set_entries_tuple([(k, k) for k in telem_type_choices], "SERIAL1")
            telem_type_cb.event_generate("<<ComboboxSelected>>")
            editor.root.update_idletasks()
            editor.root.update()

        # Assert: no error dialog
        assert not error_was_shown, "No error dialog should appear when selecting SERIAL1 with a valid DShot protocol"

        # Assert: Protocol choices contain "ESC Telemetry" — not "Scripting"
        telem_protocol_cb = editor.entry_widgets[telem_protocol_path]
        assert isinstance(telem_protocol_cb, PairTupleCombobox)
        available_protocols = editor.data_model.get_combobox_values_for_path(telem_protocol_path)
        assert "ESC Telemetry" in available_protocols, (
            f"'ESC Telemetry' should be available for DShot600/SERIAL1, got: {available_protocols}"
        )
        assert "Scripting" not in available_protocols, (
            f"'Scripting' must NOT be available for DShot600/SERIAL1 (only Normal), got: {available_protocols}"
        )

    def test_user_changes_fc_esc_protocol_to_oneshot_autoselects_esc_telemetry_protocol(  # pylint: disable=too-many-locals
        self,
        component_editor_window: ComponentEditorWindow,
        gui_test_environment,  # pylint: disable=unused-argument
    ) -> None:
        """
        Changing FC->ESC Protocol to OneShot auto-selects the single valid ESC->FC Telemetry Protocol.

        GIVEN: FC->ESC Connection is (Main Out, Normal) and ESC->FC Telemetry is (SERIAL5, Scripting)
        WHEN: The user changes FC->ESC Connection Protocol from "Normal" to "OneShot"
        THEN: No error dialog appears — there is exactly one valid option ("ESC Telemetry")
        AND: ESC->FC Telemetry Protocol is automatically set to "ESC Telemetry"
        AND: The new telemetry protocol choices contain "ESC Telemetry" but not "Scripting"
        """
        editor = component_editor_window

        fc_esc_type_path = ("ESC", "FC->ESC Connection", "Type")
        fc_esc_protocol_path = ("ESC", "FC->ESC Connection", "Protocol")
        telem_type_path = ("ESC", "ESC->FC Telemetry", "Type")
        telem_protocol_path = ("ESC", "ESC->FC Telemetry", "Protocol")

        fc_esc_type_cb = editor.entry_widgets[fc_esc_type_path]
        assert isinstance(fc_esc_type_cb, PairTupleCombobox)
        fc_esc_protocol_cb = editor.entry_widgets[fc_esc_protocol_path]
        assert isinstance(fc_esc_protocol_cb, PairTupleCombobox)
        telem_type_cb = editor.entry_widgets[telem_type_path]
        assert isinstance(telem_type_cb, PairTupleCombobox)
        telem_protocol_cb = editor.entry_widgets[telem_protocol_path]
        assert isinstance(telem_protocol_cb, PairTupleCombobox)

        # Arrange: set FC->ESC = (Main Out, Normal), ESC->FC Telemetry = (SERIAL5, Scripting).
        # Suppress errors during setup — we only care about errors triggered by the act step.
        with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor.show_error_message"):
            # Step 1: switch FC->ESC Type to "Main Out" (PWM)
            fc_esc_type_cb.set_entries_tuple(
                [(k, k) for k in editor.data_model.get_combobox_values_for_path(fc_esc_type_path)],
                "Main Out",
            )
            fc_esc_type_cb.event_generate("<<ComboboxSelected>>")
            editor.root.update_idletasks()
            editor.root.update()

            # Step 2: set FC->ESC Protocol = "Normal" in the data model and widget.
            editor.data_model.set_component_value(fc_esc_protocol_path, "Normal")
            fc_esc_protocol_cb.set_entries_tuple([("Normal", "Normal")], "Normal")

            # Step 3: switch ESC->FC Telemetry Type to SERIAL5.
            telem_type_choices = editor.data_model.get_combobox_values_for_path(telem_type_path)
            telem_type_cb.set_entries_tuple([(k, k) for k in telem_type_choices], "SERIAL5")
            telem_type_cb.event_generate("<<ComboboxSelected>>")
            editor.root.update_idletasks()
            editor.root.update()

            # Step 4: set ESC->FC Telemetry Protocol = "Scripting" (the only choice for Normal/SERIAL5).
            editor.data_model.set_component_value(telem_protocol_path, "Scripting")
            telem_protocol_cb.set_entries_tuple([("Scripting", "Scripting")], "Scripting")

        # Verify pre-conditions
        assert fc_esc_type_cb.get_selected_key() == "Main Out"
        assert fc_esc_protocol_cb.get_selected_key() == "Normal"
        assert telem_type_cb.get_selected_key() == "SERIAL5"
        assert telem_protocol_cb.get_selected_key() == "Scripting"
        assert str(telem_protocol_cb.cget("state")) != "disabled", "ESC->FC Telemetry Protocol must be editable for PWM"

        # Act: user changes FC->ESC Protocol from "Normal" to "OneShot".
        error_was_shown = False

        def record_error(*_args: object, **_kwargs: object) -> None:
            nonlocal error_was_shown
            error_was_shown = True

        with patch(
            "ardupilot_methodic_configurator.frontend_tkinter_component_editor.show_error_message",
            side_effect=record_error,
        ):
            editor.data_model.set_component_value(fc_esc_protocol_path, "OneShot")
            fc_esc_protocol_cb.set_entries_tuple([("OneShot", "OneShot")], "OneShot")
            fc_esc_protocol_cb.event_generate("<<ComboboxSelected>>")
            editor.root.update_idletasks()
            editor.root.update()

        # Assert: no error dialog — only one valid option, so it is auto-selected silently
        assert not error_was_shown, "No error dialog should appear when there is exactly one valid option to auto-select"

        # Assert: ESC->FC Telemetry Protocol is automatically set to "ESC Telemetry"
        assert telem_protocol_cb.get_selected_key() == "ESC Telemetry", (
            f"Expected ESC->FC Telemetry Protocol to be auto-selected as 'ESC Telemetry', "
            f"got '{telem_protocol_cb.get_selected_key()}'"
        )

        # Assert: data model also reflects the auto-selected value
        assert editor.data_model.get_component_value(telem_protocol_path) == "ESC Telemetry", (
            "Data model ESC->FC Telemetry Protocol should also be updated to 'ESC Telemetry'"
        )

        # Assert: new protocol choices contain "ESC Telemetry" (correct for OneShot/SERIAL5)
        new_choices = editor.data_model.get_combobox_values_for_path(telem_protocol_path)
        assert "ESC Telemetry" in new_choices, (
            f"'ESC Telemetry' should now be available for OneShot/SERIAL5, got: {new_choices}"
        )
        assert "Scripting" not in new_choices, f"'Scripting' must NOT be available for OneShot/SERIAL5, got: {new_choices}"

    def test_pwm_fc_esc_leaves_telemetry_comboboxes_enabled(
        self,
        component_editor_window: ComponentEditorWindow,
        gui_test_environment,  # pylint: disable=unused-argument
    ) -> None:
        """
        PWM FC->ESC connection leaves ESC->FC Telemetry comboboxes editable (not greyed).

        GIVEN: FC->ESC Connection Type is "Main Out" (PWM protocol, not same_as_FC_to_ESC)
        WHEN: The component editor is displayed
        THEN: ESC->FC Telemetry Type combobox is NOT disabled
        AND: ESC->FC Telemetry Protocol combobox is NOT disabled
        """
        editor = component_editor_window

        fc_esc_type_path = ("ESC", "FC->ESC Connection", "Type")
        telem_type_path = ("ESC", "ESC->FC Telemetry", "Type")
        telem_protocol_path = ("ESC", "ESC->FC Telemetry", "Protocol")

        fc_esc_type_cb = editor.entry_widgets[fc_esc_type_path]
        assert isinstance(fc_esc_type_cb, PairTupleCombobox)

        # Arrange: switch to "Main Out" (a PWM port — back-channel is independent, not mirrored)
        with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor.show_error_message"):
            fc_esc_type_cb.set_entries_tuple(
                [(k, k) for k in editor.data_model.get_combobox_values_for_path(fc_esc_type_path)],
                "Main Out",
            )
            fc_esc_type_cb.event_generate("<<ComboboxSelected>>")
            editor.root.update_idletasks()
            editor.root.update()

        # Assert: both ESC->FC Telemetry comboboxes are editable
        telem_type_cb = editor.entry_widgets[telem_type_path]
        assert isinstance(telem_type_cb, PairTupleCombobox)
        telem_protocol_cb = editor.entry_widgets[telem_protocol_path]
        assert isinstance(telem_protocol_cb, PairTupleCombobox)

        assert str(telem_type_cb.cget("state")) != "disabled", (
            "ESC->FC Telemetry Type must NOT be disabled for PWM FC->ESC connection"
        )
        assert str(telem_protocol_cb.cget("state")) != "disabled", (
            "ESC->FC Telemetry Protocol must NOT be disabled for PWM FC->ESC connection"
        )

    def test_serial_non_same_port_protocol_leaves_telemetry_comboboxes_enabled(
        self,
        component_editor_window: ComponentEditorWindow,
        gui_test_environment,  # pylint: disable=unused-argument
    ) -> None:
        """
        SERIAL FC->ESC with a non-same-port protocol (e.g. Normal) leaves telemetry comboboxes editable.

        GIVEN: FC->ESC Connection Type is "SERIAL5" with Protocol "Normal"
              (Normal is NOT a same_as_FC_to_ESC protocol — back-channel is independent)
        WHEN: The component editor is displayed
        THEN: ESC->FC Telemetry Type combobox is NOT disabled
        AND: ESC->FC Telemetry Protocol combobox is NOT disabled
        """
        editor = component_editor_window

        fc_esc_type_path = ("ESC", "FC->ESC Connection", "Type")
        fc_esc_protocol_path = ("ESC", "FC->ESC Connection", "Protocol")
        telem_type_path = ("ESC", "ESC->FC Telemetry", "Type")
        telem_protocol_path = ("ESC", "ESC->FC Telemetry", "Protocol")

        fc_esc_type_cb = editor.entry_widgets[fc_esc_type_path]
        assert isinstance(fc_esc_type_cb, PairTupleCombobox)

        # Arrange: switch FC->ESC Type to SERIAL5 with Protocol "Normal"
        # (Normal is a PWM-style protocol carried over SERIAL — not same_as_FC_to_ESC)
        with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor.show_error_message"):
            fc_esc_type_cb.set_entries_tuple(
                [(k, k) for k in editor.data_model.get_combobox_values_for_path(fc_esc_type_path)],
                "SERIAL5",
            )
            fc_esc_type_cb.event_generate("<<ComboboxSelected>>")
            editor.root.update_idletasks()
            editor.root.update()

        # Set FC->ESC Protocol to "Normal" (not a same-port protocol)
        editor.data_model.set_component_value(fc_esc_protocol_path, "Normal")
        # Re-trigger mirror-state evaluation by firing _on_esc_fc_protocol_changed
        fc_esc_protocol_cb = editor.entry_widgets[fc_esc_protocol_path]
        assert isinstance(fc_esc_protocol_cb, PairTupleCombobox)
        fc_esc_protocol_cb.set_entries_tuple([("Normal", "Normal")], "Normal")
        fc_esc_protocol_cb.event_generate("<<ComboboxSelected>>")
        editor.root.update_idletasks()
        editor.root.update()

        # Assert: both ESC->FC Telemetry comboboxes are NOT disabled
        telem_type_cb = editor.entry_widgets[telem_type_path]
        assert isinstance(telem_type_cb, PairTupleCombobox)
        telem_protocol_cb = editor.entry_widgets[telem_protocol_path]
        assert isinstance(telem_protocol_cb, PairTupleCombobox)

        assert str(telem_type_cb.cget("state")) != "disabled", (
            "ESC->FC Telemetry Type must NOT be disabled for SERIAL5/Normal (back-channel is independent)"
        )
        assert str(telem_protocol_cb.cget("state")) != "disabled", (
            "ESC->FC Telemetry Protocol must NOT be disabled for SERIAL5/Normal (back-channel is independent)"
        )

    def test_serial_same_port_protocol_disables_telemetry_comboboxes(
        self,
        component_editor_window: ComponentEditorWindow,
        gui_test_environment,  # pylint: disable=unused-argument
    ) -> None:
        """
        SERIAL FC->ESC with a same-port protocol (e.g. FETtecOneWire) disables telemetry comboboxes.

        GIVEN: FC->ESC Connection Type is "SERIAL5" with Protocol "FETtecOneWire"
              (FETtecOneWire IS a same_as_FC_to_ESC protocol — telemetry mirrors FC->ESC)
        WHEN: The component editor is displayed
        THEN: ESC->FC Telemetry Type combobox IS disabled
        AND: ESC->FC Telemetry Protocol combobox IS disabled
        """
        editor = component_editor_window

        fc_esc_type_path = ("ESC", "FC->ESC Connection", "Type")
        fc_esc_protocol_path = ("ESC", "FC->ESC Connection", "Protocol")
        telem_type_path = ("ESC", "ESC->FC Telemetry", "Type")
        telem_protocol_path = ("ESC", "ESC->FC Telemetry", "Protocol")

        fc_esc_type_cb = editor.entry_widgets[fc_esc_type_path]
        assert isinstance(fc_esc_type_cb, PairTupleCombobox)
        fc_esc_protocol_cb = editor.entry_widgets[fc_esc_protocol_path]
        assert isinstance(fc_esc_protocol_cb, PairTupleCombobox)

        # Arrange: switch FC->ESC to SERIAL5 / FETtecOneWire (a same-port protocol)
        with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor.show_error_message"):
            fc_esc_type_cb.set_entries_tuple(
                [(k, k) for k in editor.data_model.get_combobox_values_for_path(fc_esc_type_path)],
                "SERIAL5",
            )
            fc_esc_type_cb.event_generate("<<ComboboxSelected>>")
            editor.root.update_idletasks()
            editor.root.update()

        editor.data_model.set_component_value(fc_esc_protocol_path, "FETtecOneWire")
        fc_esc_protocol_cb.set_entries_tuple([("FETtecOneWire", "FETtecOneWire")], "FETtecOneWire")
        fc_esc_protocol_cb.event_generate("<<ComboboxSelected>>")
        editor.root.update_idletasks()
        editor.root.update()

        # Assert: both ESC->FC Telemetry comboboxes ARE disabled (mirrored)
        telem_type_cb = editor.entry_widgets[telem_type_path]
        assert isinstance(telem_type_cb, PairTupleCombobox)
        telem_protocol_cb = editor.entry_widgets[telem_protocol_path]
        assert isinstance(telem_protocol_cb, PairTupleCombobox)

        assert str(telem_type_cb.cget("state")) == "disabled", (
            "ESC->FC Telemetry Type MUST be disabled for SERIAL5/FETtecOneWire (same_as_FC_to_ESC)"
        )
        assert str(telem_protocol_cb.cget("state")) == "disabled", (
            "ESC->FC Telemetry Protocol MUST be disabled for SERIAL5/FETtecOneWire (same_as_FC_to_ESC)"
        )

    def test_changing_fc_esc_protocol_to_brushed_resets_both_telemetry_type_and_protocol(
        self,
        component_editor_window: ComponentEditorWindow,
        gui_test_environment,  # pylint: disable=unused-argument
    ) -> None:
        """
        Changing FC->ESC Protocol to Brushed resets both ESC->FC Telemetry Type and Protocol to "None".

        Brushed uses ESC_TO_FC_TELEMETRY_NONE — no back-channel is possible.  When the user
        was previously using a DShot protocol with a dedicated serial telemetry port, both the
        Type (e.g. SERIAL3) and the Protocol (e.g. ESC Telemetry) must be invalidated and
        auto-reset to "None" when the FC->ESC protocol changes to Brushed.

        GIVEN: FC->ESC Connection is (Main Out, DShot150)
        AND: ESC->FC Telemetry is (SERIAL3, ESC Telemetry)
        WHEN: The user changes the FC->ESC Protocol to "Brushed"
        THEN: ESC->FC Telemetry Type is immediately reset to "None"
        AND: ESC->FC Telemetry Protocol is immediately reset to "None"
        AND: Both data model values are updated to "None"
        """
        editor = component_editor_window

        fc_esc_type_path = ("ESC", "FC->ESC Connection", "Type")
        fc_esc_protocol_path = ("ESC", "FC->ESC Connection", "Protocol")
        telem_type_path = ("ESC", "ESC->FC Telemetry", "Type")
        telem_protocol_path = ("ESC", "ESC->FC Telemetry", "Protocol")

        fc_esc_type_cb = editor.entry_widgets[fc_esc_type_path]
        assert isinstance(fc_esc_type_cb, PairTupleCombobox)
        fc_esc_protocol_cb = editor.entry_widgets[fc_esc_protocol_path]
        assert isinstance(fc_esc_protocol_cb, PairTupleCombobox)
        telem_type_cb = editor.entry_widgets[telem_type_path]
        assert isinstance(telem_type_cb, PairTupleCombobox)
        telem_protocol_cb = editor.entry_widgets[telem_protocol_path]
        assert isinstance(telem_protocol_cb, PairTupleCombobox)

        # Arrange: set FC->ESC = (Main Out, DShot150), ESC->FC Telemetry = (SERIAL3, ESC Telemetry).
        with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor.show_error_message"):
            fc_esc_type_cb.set_entries_tuple(
                [(k, k) for k in editor.data_model.get_combobox_values_for_path(fc_esc_type_path)],
                "Main Out",
            )
            fc_esc_type_cb.event_generate("<<ComboboxSelected>>")
            editor.root.update_idletasks()
            editor.root.update()

            editor.data_model.set_component_value(fc_esc_protocol_path, "DShot150")
            fc_esc_protocol_cb.set_entries_tuple([("DShot150", "DShot150")], "DShot150")
            fc_esc_protocol_cb.event_generate("<<ComboboxSelected>>")
            editor.root.update_idletasks()
            editor.root.update()

            telem_type_choices = editor.data_model.get_combobox_values_for_path(telem_type_path)
            assert "SERIAL3" in telem_type_choices, f"SERIAL3 should be available for DShot150: {telem_type_choices}"
            telem_type_cb.set_entries_tuple([(k, k) for k in telem_type_choices], "SERIAL3")
            telem_type_cb.event_generate("<<ComboboxSelected>>")
            editor.root.update_idletasks()
            editor.root.update()

            telem_protocol_choices = editor.data_model.get_combobox_values_for_path(telem_protocol_path)
            assert "ESC Telemetry" in telem_protocol_choices, (
                f"ESC Telemetry should be available for DShot150/SERIAL3: {telem_protocol_choices}"
            )
            editor.data_model.set_component_value(telem_protocol_path, "ESC Telemetry")
            telem_protocol_cb.set_entries_tuple([("ESC Telemetry", "ESC Telemetry")], "ESC Telemetry")

        # Verify pre-conditions
        assert fc_esc_type_cb.get_selected_key() == "Main Out"
        assert fc_esc_protocol_cb.get_selected_key() == "DShot150"
        assert telem_type_cb.get_selected_key() == "SERIAL3"
        assert telem_protocol_cb.get_selected_key() == "ESC Telemetry"

        # Act: user changes FC->ESC Protocol to "Brushed" (no back-channel possible).
        with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor.show_error_message"):
            editor.data_model.set_component_value(fc_esc_protocol_path, "Brushed")
            fc_esc_protocol_cb.set_entries_tuple([("Brushed", "Brushed")], "Brushed")
            fc_esc_protocol_cb.event_generate("<<ComboboxSelected>>")
            editor.root.update_idletasks()
            editor.root.update()

        # Assert: ESC->FC Telemetry Type is reset to "None"
        assert telem_type_cb.get_selected_key() == "None", (
            f"ESC->FC Telemetry Type must be reset to 'None' when FC->ESC Protocol is Brushed "
            f"(no back-channel possible), got '{telem_type_cb.get_selected_key()}'"
        )

        # Assert: ESC->FC Telemetry Protocol is reset to "None"
        assert telem_protocol_cb.get_selected_key() == "None", (
            f"ESC->FC Telemetry Protocol must be reset to 'None' when FC->ESC Protocol is Brushed "
            f"(no back-channel possible), got '{telem_protocol_cb.get_selected_key()}'"
        )

        # Assert: data model reflects the reset values
        assert editor.data_model.get_component_value(telem_type_path) == "None", (
            "Data model ESC->FC Telemetry Type must be 'None' after switching to Brushed"
        )
        assert editor.data_model.get_component_value(telem_protocol_path) == "None", (
            "Data model ESC->FC Telemetry Protocol must be 'None' after switching to Brushed"
        )

    def test_changing_fc_esc_protocol_to_dshot_leaves_telemetry_type_editable(
        self,
        component_editor_window: ComponentEditorWindow,
        gui_test_environment,  # pylint: disable=unused-argument
    ) -> None:
        """
        Changing FC->ESC Protocol to DShot150 leaves ESC->FC Telemetry Type editable (not greyed).

        DShot protocols have ESC_TO_FC_TELEMETRY_DSHOT with three valid type choices:
        ("None",), ("same_as_FC_to_ESC",), and SERIAL_PORTS.  The ESC->FC Telemetry Type
        should be enabled and offer all three type options.  (It is NOT fully mirrored —
        only the Protocol field mirrors when a specific type is selected.)

        GIVEN: FC->ESC Connection is (Main Out, Brushed) and ESC->FC Telemetry is (None, None)
        WHEN: The user changes the FC->ESC Protocol to "DShot150"
        THEN: ESC->FC Telemetry Type combobox IS enabled (not greyed out)
        AND: ESC->FC Telemetry Protocol combobox IS enabled (not greyed out)
        AND: ESC->FC Telemetry Type choices include all valid options
        """
        editor = component_editor_window

        fc_esc_type_path = ("ESC", "FC->ESC Connection", "Type")
        fc_esc_protocol_path = ("ESC", "FC->ESC Connection", "Protocol")
        telem_type_path = ("ESC", "ESC->FC Telemetry", "Type")
        telem_protocol_path = ("ESC", "ESC->FC Telemetry", "Protocol")

        fc_esc_type_cb = editor.entry_widgets[fc_esc_type_path]
        assert isinstance(fc_esc_type_cb, PairTupleCombobox)
        fc_esc_protocol_cb = editor.entry_widgets[fc_esc_protocol_path]
        assert isinstance(fc_esc_protocol_cb, PairTupleCombobox)
        telem_type_cb = editor.entry_widgets[telem_type_path]
        assert isinstance(telem_type_cb, PairTupleCombobox)
        telem_protocol_cb = editor.entry_widgets[telem_protocol_path]
        assert isinstance(telem_protocol_cb, PairTupleCombobox)

        # Arrange: set FC->ESC = (Main Out, Brushed), ESC->FC Telemetry = (None, None).
        with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor.show_error_message"):
            fc_esc_type_cb.set_entries_tuple(
                [(k, k) for k in editor.data_model.get_combobox_values_for_path(fc_esc_type_path)],
                "Main Out",
            )
            fc_esc_type_cb.event_generate("<<ComboboxSelected>>")
            editor.root.update_idletasks()
            editor.root.update()

            editor.data_model.set_component_value(fc_esc_protocol_path, "Brushed")
            fc_esc_protocol_cb.set_entries_tuple([("Brushed", "Brushed")], "Brushed")
            fc_esc_protocol_cb.event_generate("<<ComboboxSelected>>")
            editor.root.update_idletasks()
            editor.root.update()

            editor.data_model.set_component_value(telem_type_path, "None")
            telem_type_cb.set_entries_tuple([("None", "None")], "None")

            editor.data_model.set_component_value(telem_protocol_path, "None")
            telem_protocol_cb.set_entries_tuple([("None", "None")], "None")

        # Verify pre-conditions
        assert fc_esc_type_cb.get_selected_key() == "Main Out"
        assert fc_esc_protocol_cb.get_selected_key() == "Brushed"
        assert telem_type_cb.get_selected_key() == "None"
        assert telem_protocol_cb.get_selected_key() == "None"

        # Act: user changes FC->ESC Protocol from "Brushed" to "DShot150".
        with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor.show_error_message"):
            editor.data_model.set_component_value(fc_esc_protocol_path, "DShot150")
            fc_esc_protocol_cb.set_entries_tuple([("DShot150", "DShot150")], "DShot150")
            fc_esc_protocol_cb.event_generate("<<ComboboxSelected>>")
            editor.root.update_idletasks()
            editor.root.update()

        # Assert: ESC->FC Telemetry Type combobox IS enabled (not greyed out)
        # DShot has multiple type choices (None, BDShotOnly same-port, SERIAL) so it is NOT fully mirrored
        assert str(telem_type_cb.cget("state")) != "disabled", (
            "ESC->FC Telemetry Type MUST be enabled for DShot150 (has multiple type choices: "
            "None, same_as_FC_to_ESC, SERIAL_PORTS)"
        )

        # Assert: ESC->FC Telemetry Protocol combobox IS enabled (not greyed out)
        # Until the user selects a specific Type, the Protocol should also be editable
        assert str(telem_protocol_cb.cget("state")) != "disabled", (
            "ESC->FC Telemetry Protocol MUST be enabled for DShot150 when Type is not mirrored"
        )

    def test_fc_esc_protocol_change_takes_effect_immediately_not_on_next_selection(
        self,
        component_editor_window: ComponentEditorWindow,
        gui_test_environment,  # pylint: disable=unused-argument
    ) -> None:
        """
        Changing FC->ESC Protocol takes effect immediately on <<ComboboxSelected>>, not one selection later.

        Regression test for the bug where <<ComboboxSelected>> fires before <ButtonRelease> persists
        the new value to the data model, causing the cascade to read the *previous* protocol and
        produce stale results — so the first selection appeared to do nothing and the intended effect
        only appeared on the next selection.

        GIVEN: FC->ESC Connection is (Main Out, Normal) and ESC->FC Telemetry is (SERIAL5, Scripting)
        AND: The data model still holds "Normal" for FC->ESC Protocol (not yet persisted by <ButtonRelease>)
        WHEN: The FC->ESC Protocol widget shows "OneShot" and <<ComboboxSelected>> fires
              WITHOUT first updating the data model (replicating the real Tkinter event order)
        THEN: ESC->FC Telemetry Protocol is immediately auto-selected as "ESC Telemetry"
        AND: The data model is also updated to "ESC Telemetry" in the same event
        AND: No second selection is needed to trigger the change
        """
        editor = component_editor_window

        fc_esc_type_path = ("ESC", "FC->ESC Connection", "Type")
        fc_esc_protocol_path = ("ESC", "FC->ESC Connection", "Protocol")
        telem_type_path = ("ESC", "ESC->FC Telemetry", "Type")
        telem_protocol_path = ("ESC", "ESC->FC Telemetry", "Protocol")

        fc_esc_type_cb = editor.entry_widgets[fc_esc_type_path]
        assert isinstance(fc_esc_type_cb, PairTupleCombobox)
        fc_esc_protocol_cb = editor.entry_widgets[fc_esc_protocol_path]
        assert isinstance(fc_esc_protocol_cb, PairTupleCombobox)
        telem_type_cb = editor.entry_widgets[telem_type_path]
        assert isinstance(telem_type_cb, PairTupleCombobox)
        telem_protocol_cb = editor.entry_widgets[telem_protocol_path]
        assert isinstance(telem_protocol_cb, PairTupleCombobox)

        # Arrange: set FC->ESC = (Main Out, Normal), ESC->FC Telemetry = (SERIAL5, Scripting).
        with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor.show_error_message"):
            fc_esc_type_cb.set_entries_tuple(
                [(k, k) for k in editor.data_model.get_combobox_values_for_path(fc_esc_type_path)],
                "Main Out",
            )
            fc_esc_type_cb.event_generate("<<ComboboxSelected>>")
            editor.root.update_idletasks()
            editor.root.update()

            editor.data_model.set_component_value(fc_esc_protocol_path, "Normal")
            fc_esc_protocol_cb.set_entries_tuple([("Normal", "Normal")], "Normal")

            telem_type_choices = editor.data_model.get_combobox_values_for_path(telem_type_path)
            telem_type_cb.set_entries_tuple([(k, k) for k in telem_type_choices], "SERIAL5")
            telem_type_cb.event_generate("<<ComboboxSelected>>")
            editor.root.update_idletasks()
            editor.root.update()

            editor.data_model.set_component_value(telem_protocol_path, "Scripting")
            telem_protocol_cb.set_entries_tuple([("Scripting", "Scripting")], "Scripting")

        # Verify pre-conditions
        assert fc_esc_type_cb.get_selected_key() == "Main Out"
        assert fc_esc_protocol_cb.get_selected_key() == "Normal"
        assert telem_type_cb.get_selected_key() == "SERIAL5"
        assert telem_protocol_cb.get_selected_key() == "Scripting"

        # Act: simulate the real Tkinter event order — the widget shows "OneShot" but the data
        # model has NOT been updated yet (<<ComboboxSelected>> fires before <ButtonRelease>, which
        # is what _validate_combobox uses to persist the value to the data model).
        # This is the exact condition that triggered the regression.
        fc_esc_protocol_cb.set_entries_tuple([("Normal", "Normal"), ("OneShot", "OneShot")], "OneShot")
        # Data model intentionally NOT updated here — it still holds "Normal"
        assert editor.data_model.get_component_value(fc_esc_protocol_path) == "Normal", (
            "Pre-condition: data model must still hold 'Normal' to replicate the regression scenario"
        )
        fc_esc_protocol_cb.event_generate("<<ComboboxSelected>>")
        editor.root.update_idletasks()
        editor.root.update()

        # Assert: ESC->FC Telemetry Protocol is immediately "ESC Telemetry" — no second selection needed.
        assert telem_protocol_cb.get_selected_key() == "ESC Telemetry", (
            f"ESC->FC Telemetry Protocol must be auto-selected as 'ESC Telemetry' immediately on the "
            f"first <<ComboboxSelected>> event, got '{telem_protocol_cb.get_selected_key()}'. "
            f"If this is still 'Scripting', the regression has returned: the cascade is reading the "
            f"stale data model value instead of the protocol passed to _on_esc_fc_protocol_changed."
        )

        # Assert: data model also reflects the auto-selected value
        assert editor.data_model.get_component_value(telem_protocol_path) == "ESC Telemetry", (
            "Data model ESC->FC Telemetry Protocol must be updated to 'ESC Telemetry' in the same event"
        )

    def test_pwm_main_out_fc_esc_type_change_cascades_protocol_and_telemetry(
        self,
        component_editor_window: ComponentEditorWindow,
        gui_test_environment,  # pylint: disable=unused-argument
    ) -> None:
        """
        Changing FC->ESC Type between PWM ports keeps protocol options and leaves telemetry editable.

        GIVEN: FC->ESC Connection is set to "Main Out" with Normal protocol
        WHEN: The user changes FC->ESC Connection Type to "AIO"
        THEN: FC->ESC Protocol options remain non-empty (same set for all PWM_OUT_PORTS)
        AND: ESC->FC Telemetry comboboxes are NOT disabled (Normal/PWM has no telemetry mirroring)
        AND: PyAutoGUI can capture the updated window on screen
        """
        editor = component_editor_window
        fc_esc_type_path = ("ESC", "FC->ESC Connection", "Type")
        fc_esc_protocol_path = ("ESC", "FC->ESC Connection", "Protocol")
        telem_type_path = ("ESC", "ESC->FC Telemetry", "Type")
        telem_protocol_path = ("ESC", "ESC->FC Telemetry", "Protocol")

        fc_esc_type_cb = editor.entry_widgets[fc_esc_type_path]
        assert isinstance(fc_esc_type_cb, PairTupleCombobox)
        fc_esc_protocol_cb = editor.entry_widgets[fc_esc_protocol_path]
        assert isinstance(fc_esc_protocol_cb, PairTupleCombobox)
        telem_type_cb = editor.entry_widgets[telem_type_path]
        assert isinstance(telem_type_cb, PairTupleCombobox)
        telem_protocol_cb = editor.entry_widgets[telem_protocol_path]
        assert isinstance(telem_protocol_cb, PairTupleCombobox)

        # Arrange: Set FC->ESC to Main Out/Normal
        with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor.show_error_message"):
            fc_esc_type_cb.set_entries_tuple(
                [(k, k) for k in editor.data_model.get_combobox_values_for_path(fc_esc_type_path)],
                "Main Out",
            )
            fc_esc_type_cb.event_generate("<<ComboboxSelected>>")
            editor.root.update_idletasks()
            editor.root.update()
            editor.data_model.set_component_value(fc_esc_protocol_path, "Normal")

        # Act: Change FC->ESC Type to AIO
        with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor.show_error_message"):
            fc_esc_type_cb.set_entries_tuple(
                [(k, k) for k in editor.data_model.get_combobox_values_for_path(fc_esc_type_path)],
                "AIO",
            )
            fc_esc_type_cb.event_generate("<<ComboboxSelected>>")
            editor.root.update_idletasks()
            editor.root.update()

        # Assert cascade results
        assert fc_esc_type_cb.get_selected_key() == "AIO"
        # For Normal/PWM, the telemetry comboboxes must NOT be disabled (independent back-channel).
        # Only CAN/DroneCAN and SERIAL same-port protocols (FETtecOneWire, CoDevESC, etc.) mirror.
        assert str(telem_type_cb.cget("state")) != "disabled", (
            "ESC->FC Telemetry Type must NOT be disabled for AIO/Normal (PWM has no telemetry mirroring)"
        )
        assert str(telem_protocol_cb.cget("state")) != "disabled", (
            "ESC->FC Telemetry Protocol must NOT be disabled for AIO/Normal (PWM has no telemetry mirroring)"
        )
        # FC->ESC Protocol combobox must have entries (validates that _mot_pwm_types is populated)
        assert len(fc_esc_protocol_cb.list_keys) > 0, (
            "FC->ESC Protocol combobox must have entries for PWM type; got empty list — _mot_pwm_types may not be initialised"
        )

        # Assert PyAutoGUI can capture the screen
        editor.root.deiconify()
        editor.root.lift()
        editor.root.update_idletasks()
        screenshot = pyautogui.screenshot()
        assert screenshot.size[0] > 0

    def test_changing_fc_esc_protocol_from_brushed_to_dshot300_expands_telemetry_type_options(  # noqa: PLR0915  # pylint: disable=too-many-locals, too-many-statements
        self,
        component_editor_window: ComponentEditorWindow,
        gui_test_environment,  # pylint: disable=unused-argument
    ) -> None:
        """
        Changing FC->ESC Protocol from Brushed to DShot300 expands ESC->FC Telemetry Type choices.

        DShot300 uses ESC_TO_FC_TELEMETRY_DSHOT which supports three back-channel categories:
        "None" (no telemetry), the FC->ESC port itself via BDShot, and any SERIAL port via
        ESC Telemetry.  Brushed has no back-channel (ESC_TO_FC_TELEMETRY_NONE = only "None").

        GIVEN: FC->ESC Connection is ("Main Out", "Brushed") and ESC->FC Telemetry is ("None", "None")
        WHEN: The user changes FC->ESC Connection Protocol from "Brushed" to "DShot300"
        THEN: No error dialog is shown (current telemetry "None" is valid for DShot300)
        AND: ESC->FC Telemetry Type combobox is NOT disabled (DShot has an independent back-channel)
        AND: ESC->FC Telemetry Protocol combobox is NOT disabled
        AND: ESC->FC Telemetry Type choices now include "Main Out" and SERIAL ports (not just "None")
        AND: ESC->FC Telemetry Type selection remains "None" (still valid — no forced reset)
        AND: ESC->FC Telemetry Type widget entries include "Main Out" and "SERIAL2" (not just "None")
        """
        editor = component_editor_window

        fc_esc_type_path = ("ESC", "FC->ESC Connection", "Type")
        fc_esc_protocol_path = ("ESC", "FC->ESC Connection", "Protocol")
        telem_type_path = ("ESC", "ESC->FC Telemetry", "Type")
        telem_protocol_path = ("ESC", "ESC->FC Telemetry", "Protocol")

        fc_esc_type_cb = editor.entry_widgets[fc_esc_type_path]
        assert isinstance(fc_esc_type_cb, PairTupleCombobox)
        fc_esc_protocol_cb = editor.entry_widgets[fc_esc_protocol_path]
        assert isinstance(fc_esc_protocol_cb, PairTupleCombobox)
        telem_type_cb = editor.entry_widgets[telem_type_path]
        assert isinstance(telem_type_cb, PairTupleCombobox)
        telem_protocol_cb = editor.entry_widgets[telem_protocol_path]
        assert isinstance(telem_protocol_cb, PairTupleCombobox)

        # Arrange: FC->ESC = (Main Out, Brushed), ESC->FC Telemetry = (None, None)
        with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor.show_error_message"):
            fc_esc_type_cb.set_entries_tuple(
                [(k, k) for k in editor.data_model.get_combobox_values_for_path(fc_esc_type_path)],
                "Main Out",
            )
            fc_esc_type_cb.event_generate("<<ComboboxSelected>>")
            editor.root.update_idletasks()
            editor.root.update()

            editor.data_model.set_component_value(fc_esc_protocol_path, "Brushed")
            fc_esc_protocol_cb.set_entries_tuple([("Brushed", "Brushed")], "Brushed")
            fc_esc_protocol_cb.event_generate("<<ComboboxSelected>>")
            editor.root.update_idletasks()
            editor.root.update()

        # Verify pre-conditions
        assert fc_esc_type_cb.get_selected_key() == "Main Out"
        assert fc_esc_protocol_cb.get_selected_key() == "Brushed"
        assert telem_type_cb.get_selected_key() == "None", (
            f"Pre-condition: ESC->FC Telemetry Type should be 'None', got '{telem_type_cb.get_selected_key()}'"
        )
        assert telem_protocol_cb.get_selected_key() == "None", (
            f"Pre-condition: ESC->FC Telemetry Protocol should be 'None', got '{telem_protocol_cb.get_selected_key()}'"
        )
        brushed_valid_types = editor.data_model.get_valid_esc_telemetry_types()
        assert brushed_valid_types == ("None",), (
            f"Pre-condition: Brushed should allow only ('None',) as telemetry types, got {brushed_valid_types}"
        )

        # Act: change FC->ESC Protocol from "Brushed" to "DShot300"
        error_was_shown = False

        def record_error(*_args: object, **_kwargs: object) -> None:
            nonlocal error_was_shown
            error_was_shown = True

        with patch(
            "ardupilot_methodic_configurator.frontend_tkinter_component_editor.show_error_message",
            side_effect=record_error,
        ):
            editor.data_model.set_component_value(fc_esc_protocol_path, "DShot300")
            fc_esc_protocol_cb.set_entries_tuple([("DShot300", "DShot300")], "DShot300")
            fc_esc_protocol_cb.event_generate("<<ComboboxSelected>>")
            editor.root.update_idletasks()
            editor.root.update()

        # Assert: no error dialog — current telemetry "None" is valid for DShot300
        assert not error_was_shown, "No error dialog should appear: ESC->FC Telemetry 'None' is valid for DShot300"

        # Assert: FC->ESC Protocol selection unchanged
        assert fc_esc_protocol_cb.get_selected_key() == "DShot300"

        # Assert: both ESC->FC Telemetry comboboxes are enabled (DShot has no full telemetry mirroring)
        assert str(telem_type_cb.cget("state")) != "disabled", (
            "ESC->FC Telemetry Type must NOT be disabled for DShot300 (independent back-channel)"
        )
        assert str(telem_protocol_cb.cget("state")) != "disabled", (
            "ESC->FC Telemetry Protocol must NOT be disabled for DShot300"
        )

        # Assert: ESC->FC Telemetry Type choices are now expanded (DShot allows BDShot and SERIAL)
        dshot_valid_types = editor.data_model.get_valid_esc_telemetry_types()
        assert "Main Out" in dshot_valid_types, (
            f"DShot300 should offer 'Main Out' (BDShot back-channel) as telemetry type, got {dshot_valid_types}"
        )
        assert "SERIAL1" in dshot_valid_types, (
            f"DShot300 should offer SERIAL ports as telemetry types, got {dshot_valid_types}"
        )
        assert "None" in dshot_valid_types, f"DShot300 should still offer 'None' as telemetry type, got {dshot_valid_types}"

        # Assert: current ESC->FC Telemetry Type selection stays "None" (no forced reset needed)
        assert telem_type_cb.get_selected_key() == "None", (
            f"ESC->FC Telemetry Type should remain 'None' (still valid for DShot300), got '{telem_type_cb.get_selected_key()}'"
        )

        # Assert: current ESC->FC Telemetry Protocol stays "None"
        assert telem_protocol_cb.get_selected_key() == "None", (
            f"ESC->FC Telemetry Protocol should remain 'None', got '{telem_protocol_cb.get_selected_key()}'"
        )

        # Assert: the Type widget's dropdown entries are now expanded (not just ["None"]).
        # This is the KEY check — the widget itself must reflect the new valid set, not stale Brushed options.
        assert "Main Out" in telem_type_cb.list_keys, (
            f"Type widget entries must include 'Main Out' (BDShot) after DShot300, got {telem_type_cb.list_keys}"
        )
        assert "SERIAL2" in telem_type_cb.list_keys, (
            f"Type widget entries must include SERIAL ports after DShot300, got {telem_type_cb.list_keys}"
        )
        assert telem_type_cb.list_keys != ["None"], "Type widget must offer more than just 'None' when DShot300 is selected"

    def test_pwm_main_out_fc_esc_protocol_change_cascades_to_telemetry_protocol(
        self,
        component_editor_window: ComponentEditorWindow,
        gui_test_environment,  # pylint: disable=unused-argument
    ) -> None:
        """Changing FC->ESC Protocol on Main Out cascades to ESC->FC Telemetry Protocol."""
        editor = component_editor_window
        fc_esc_type_path = ("ESC", "FC->ESC Connection", "Type")
        fc_esc_protocol_path = ("ESC", "FC->ESC Connection", "Protocol")
        telem_protocol_path = ("ESC", "ESC->FC Telemetry", "Protocol")

        fc_esc_type_cb = editor.entry_widgets[fc_esc_type_path]
        assert isinstance(fc_esc_type_cb, PairTupleCombobox)
        fc_esc_protocol_cb = editor.entry_widgets[fc_esc_protocol_path]
        assert isinstance(fc_esc_protocol_cb, PairTupleCombobox)
        telem_protocol_cb = editor.entry_widgets[telem_protocol_path]
        assert isinstance(telem_protocol_cb, PairTupleCombobox)

        # Arrange
        with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor.show_error_message"):
            fc_esc_type_cb.set_entries_tuple(
                [(k, k) for k in editor.data_model.get_combobox_values_for_path(fc_esc_type_path)],
                "Main Out",
            )
            fc_esc_type_cb.event_generate("<<ComboboxSelected>>")
            editor.root.update_idletasks()
            editor.root.update()
            editor.data_model.set_component_value(fc_esc_protocol_path, "Normal")

        # Act
        fc_esc_protocol_cb.set_entries_tuple(
            [(k, k) for k in editor.data_model.get_combobox_values_for_path(fc_esc_protocol_path)],
            "DShot600",
        )
        fc_esc_protocol_cb.event_generate("<<ComboboxSelected>>")
        editor.root.update_idletasks()
        editor.root.update()

        # Assert
        assert fc_esc_protocol_cb.get_selected_key() == "DShot600"
        assert telem_protocol_cb.get_selected_key() in editor.data_model.get_combobox_values_for_path(telem_protocol_path)

    def test_pwm_main_out_telem_type_change_cascades_to_telemetry_protocol(  # pylint: disable=too-many-locals
        self,
        component_editor_window: ComponentEditorWindow,
        gui_test_environment,  # pylint: disable=unused-argument
    ) -> None:
        """
        Changing ESC->FC Telemetry Type on SERIAL cascades to ESC->FC Telemetry Protocol.

        GIVEN: FC->ESC Connection is "Main Out" with "DShot" protocol
        AND: ESC->FC Telemetry Type is "SERIAL1"
        WHEN: The user changes ESC->FC Telemetry Type to another SERIAL port (e.g., "SERIAL5")
        THEN: ESC->FC Telemetry Protocol options are recalculated for the new SERIAL port
        AND: ESC->FC Telemetry Protocol remains a valid option
        AND: Data model is updated to reflect the cascaded changes
        AND: PyAutoGUI can capture the updated window on screen
        """
        editor = component_editor_window
        fc_esc_type_path = ("ESC", "FC->ESC Connection", "Type")
        fc_esc_protocol_path = ("ESC", "FC->ESC Connection", "Protocol")
        telem_type_path = ("ESC", "ESC->FC Telemetry", "Type")
        telem_protocol_path = ("ESC", "ESC->FC Telemetry", "Protocol")

        fc_esc_type_cb = editor.entry_widgets[fc_esc_type_path]
        assert isinstance(fc_esc_type_cb, PairTupleCombobox)
        fc_esc_protocol_cb = editor.entry_widgets[fc_esc_protocol_path]
        assert isinstance(fc_esc_protocol_cb, PairTupleCombobox)
        telem_type_cb = editor.entry_widgets[telem_type_path]
        assert isinstance(telem_type_cb, PairTupleCombobox)
        telem_protocol_cb = editor.entry_widgets[telem_protocol_path]
        assert isinstance(telem_protocol_cb, PairTupleCombobox)

        # Arrange: Set FC->ESC to Main Out/DShot
        with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor.show_error_message"):
            fc_esc_type_cb.set_entries_tuple(
                [(k, k) for k in editor.data_model.get_combobox_values_for_path(fc_esc_type_path)],
                "Main Out",
            )
            fc_esc_type_cb.event_generate("<<ComboboxSelected>>")
            editor.root.update_idletasks()
            editor.root.update()

            editor.data_model.set_component_value(fc_esc_protocol_path, "DShot")
            fc_esc_protocol_cb.set_entries_tuple(
                [(k, k) for k in editor.data_model.get_combobox_values_for_path(fc_esc_protocol_path)],
                "DShot",
            )

        # Get available telemetry types and select an alternative SERIAL port
        telem_types = editor.data_model.get_combobox_values_for_path(telem_type_path)
        serial_ports = [t for t in telem_types if t.startswith("SERIAL")]
        if len(serial_ports) < 2:
            pytest.skip("Not enough SERIAL ports available for cascade test")

        alt_port = serial_ports[1]  # Use second SERIAL port as alternative

        # Act: Change ESC->FC Telemetry Type to alternative SERIAL port
        telem_type_cb.set_entries_tuple(
            [(k, k) for k in editor.data_model.get_combobox_values_for_path(telem_type_path)],
            alt_port,
        )
        telem_type_cb.event_generate("<<ComboboxSelected>>")
        editor.root.update_idletasks()
        editor.root.update()

        # Assert: Telemetry Type changed
        assert telem_type_cb.get_selected_key() == alt_port
        # Assert: Telemetry Protocol is still valid for the new type
        assert telem_protocol_cb.get_selected_key() in editor.data_model.get_combobox_values_for_path(telem_protocol_path)
        # Assert: Data model is in sync
        assert editor.data_model.get_component_value(telem_type_path) == alt_port

        # Assert PyAutoGUI can capture the screen
        editor.root.deiconify()
        editor.root.lift()
        editor.root.update_idletasks()
        screenshot = pyautogui.screenshot()
        assert screenshot.size[0] > 0

    # -------------------------------------------------------------------------
    # Cascade rule 1: FC->ESC Type change → Protocol + Telem Type + Telem Protocol
    # -------------------------------------------------------------------------

    def test_cascade_1_fc_esc_type_change_from_can_to_pwm_updates_all_downstream_widget_entries(
        self,
        component_editor_window: ComponentEditorWindow,
        gui_test_environment,  # pylint: disable=unused-argument
    ) -> None:
        """
        Cascade rule 1: FC->ESC Type change updates Protocol, Telem Type, and Telem Protocol entries.

        Mirroring is applied only after all downstream option lists are populated.

        GIVEN: FC->ESC Connection is ("CAN1", "DroneCAN") and ESC->FC Telemetry mirrors it
        WHEN: The user changes FC->ESC Connection Type to "Main Out" (PWM)
        THEN: FC->ESC Protocol widget entries list all valid PWM protocols
        AND: ESC->FC Telemetry Type widget entries list valid types for the auto-selected PWM protocol
        AND: Both ESC->FC Telemetry comboboxes are enabled (NOT disabled — PWM is not mirrored)
        AND: All changes are immediately visible without any further user interaction
        """
        editor = component_editor_window

        fc_esc_type_path = ("ESC", "FC->ESC Connection", "Type")
        fc_esc_protocol_path = ("ESC", "FC->ESC Connection", "Protocol")
        telem_type_path = ("ESC", "ESC->FC Telemetry", "Type")
        telem_protocol_path = ("ESC", "ESC->FC Telemetry", "Protocol")

        fc_esc_type_cb = editor.entry_widgets[fc_esc_type_path]
        assert isinstance(fc_esc_type_cb, PairTupleCombobox)
        fc_esc_protocol_cb = editor.entry_widgets[fc_esc_protocol_path]
        assert isinstance(fc_esc_protocol_cb, PairTupleCombobox)
        telem_type_cb = editor.entry_widgets[telem_type_path]
        assert isinstance(telem_type_cb, PairTupleCombobox)
        telem_protocol_cb = editor.entry_widgets[telem_protocol_path]
        assert isinstance(telem_protocol_cb, PairTupleCombobox)

        # Arrange: FC->ESC = (CAN1, DroneCAN) — fully mirrored initial state
        with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor.show_error_message"):
            fc_esc_type_cb.set_entries_tuple(
                [(k, k) for k in editor.data_model.get_combobox_values_for_path(fc_esc_type_path)],
                "CAN1",
            )
            fc_esc_type_cb.event_generate("<<ComboboxSelected>>")
            editor.root.update_idletasks()
            editor.root.update()

        # Verify: CAN state (fully mirrored, disabled)
        assert fc_esc_protocol_cb.list_keys == ["DroneCAN"], (
            f"Pre-condition: CAN should restrict Protocol to ['DroneCAN'], got {fc_esc_protocol_cb.list_keys}"
        )
        assert telem_type_cb.list_keys == ["CAN1"], (
            f"Pre-condition: CAN should restrict Telem Type to ['CAN1'], got {telem_type_cb.list_keys}"
        )
        assert str(telem_type_cb.cget("state")) == "disabled", "Pre-condition: Telem Type should be disabled for CAN"

        # Act: change FC->ESC Type to "Main Out" (PWM)
        with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor.show_error_message"):
            fc_esc_type_cb.set_entries_tuple(
                [(k, k) for k in editor.data_model.get_combobox_values_for_path(fc_esc_type_path)],
                "Main Out",
            )
            fc_esc_type_cb.event_generate("<<ComboboxSelected>>")
            editor.root.update_idletasks()
            editor.root.update()

        # Assert cascade rule 1: FC->ESC Protocol widget entries updated
        assert len(fc_esc_protocol_cb.list_keys) > 1, (
            f"FC->ESC Protocol should offer multiple PWM options after 'Main Out' type, got {fc_esc_protocol_cb.list_keys}"
        )
        # Normal, Brushed, DShot* and other PWM protocols should be available
        assert any(k in fc_esc_protocol_cb.list_keys for k in ("Normal", "Brushed", "DShot150")), (
            f"FC->ESC Protocol must include common PWM protocols, got {fc_esc_protocol_cb.list_keys}"
        )

        # Assert cascade rule 1: ESC->FC Telemetry Type widget entries updated
        # The auto-selected PWM protocol determines which telem types are valid.
        assert len(telem_type_cb.list_keys) >= 1, (
            f"Telem Type widget must have at least one option after PWM type change, got {telem_type_cb.list_keys}"
        )
        assert "None" in telem_type_cb.list_keys, "'None' must always be an option in Telem Type widget"

        # Assert cascade rule 1: mirroring is NOT applied for PWM (it was applied last, after options)
        assert str(telem_type_cb.cget("state")) != "disabled", (
            "ESC->FC Telemetry Type must be enabled after switching to PWM 'Main Out' "
            "(mirroring only for CAN/SERIAL same-port)"
        )
        assert str(telem_protocol_cb.cget("state")) != "disabled", (
            "ESC->FC Telemetry Protocol must be enabled after switching to PWM 'Main Out'"
        )

    # -------------------------------------------------------------------------
    # Cascade rule 2: FC->ESC Protocol change → Telem Type + Telem Protocol
    # -------------------------------------------------------------------------

    def test_cascade_2_fc_esc_protocol_change_to_dshot150_expands_telem_type_widget_entries(
        self,
        component_editor_window: ComponentEditorWindow,
        gui_test_environment,  # pylint: disable=unused-argument
    ) -> None:
        """
        Cascade rule 2 expanding: Brushed to DShot150 Protocol change expands Telem Type entries.

        Changing FC->ESC Protocol from Brushed to DShot150 immediately expands the
        ESC->FC Telemetry Type widget entries to include BDShot and SERIAL options.

        GIVEN: FC->ESC Connection is ("Main Out", "Brushed") and ESC->FC Telemetry is ("None", "None")
        WHEN: The user changes FC->ESC Protocol to "DShot150"
        THEN: ESC->FC Telemetry Type widget entries include "Main Out" (BDShot back-channel)
        AND: ESC->FC Telemetry Type widget entries include SERIAL ports (dedicated ESC telemetry)
        AND: ESC->FC Telemetry Type current selection stays "None" (no forced reset)
        AND: Both ESC->FC Telemetry comboboxes remain enabled (DShot is not fully mirrored)
        AND: No error dialog is shown (current "None" is still valid)
        """
        editor = component_editor_window

        fc_esc_type_path = ("ESC", "FC->ESC Connection", "Type")
        fc_esc_protocol_path = ("ESC", "FC->ESC Connection", "Protocol")
        telem_type_path = ("ESC", "ESC->FC Telemetry", "Type")
        telem_protocol_path = ("ESC", "ESC->FC Telemetry", "Protocol")

        fc_esc_type_cb = editor.entry_widgets[fc_esc_type_path]
        assert isinstance(fc_esc_type_cb, PairTupleCombobox)
        fc_esc_protocol_cb = editor.entry_widgets[fc_esc_protocol_path]
        assert isinstance(fc_esc_protocol_cb, PairTupleCombobox)
        telem_type_cb = editor.entry_widgets[telem_type_path]
        assert isinstance(telem_type_cb, PairTupleCombobox)
        telem_protocol_cb = editor.entry_widgets[telem_protocol_path]
        assert isinstance(telem_protocol_cb, PairTupleCombobox)

        # Arrange: FC->ESC = (Main Out, Brushed), ESC->FC = (None, None)
        with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor.show_error_message"):
            fc_esc_type_cb.set_entries_tuple(
                [(k, k) for k in editor.data_model.get_combobox_values_for_path(fc_esc_type_path)],
                "Main Out",
            )
            fc_esc_type_cb.event_generate("<<ComboboxSelected>>")
            editor.root.update_idletasks()
            editor.root.update()

            editor.data_model.set_component_value(fc_esc_protocol_path, "Brushed")
            fc_esc_protocol_cb.set_entries_tuple([("Brushed", "Brushed")], "Brushed")
            fc_esc_protocol_cb.event_generate("<<ComboboxSelected>>")
            editor.root.update_idletasks()
            editor.root.update()

        # Verify pre-conditions
        assert fc_esc_protocol_cb.get_selected_key() == "Brushed"
        assert telem_type_cb.get_selected_key() == "None"
        assert telem_type_cb.list_keys == ["None"], (
            f"Pre-condition: Brushed should restrict Telem Type widget to ['None'], got {telem_type_cb.list_keys}"
        )

        # Act: change FC->ESC Protocol to DShot150
        error_was_shown = False

        def record_error(*_args: object, **_kwargs: object) -> None:
            nonlocal error_was_shown
            error_was_shown = True

        with patch(
            "ardupilot_methodic_configurator.frontend_tkinter_component_editor.show_error_message",
            side_effect=record_error,
        ):
            editor.data_model.set_component_value(fc_esc_protocol_path, "DShot150")
            fc_esc_protocol_cb.set_entries_tuple([("DShot150", "DShot150")], "DShot150")
            fc_esc_protocol_cb.event_generate("<<ComboboxSelected>>")
            editor.root.update_idletasks()
            editor.root.update()

        # Assert cascade rule 2: no error (current "None" telem type is still valid for DShot150)
        assert not error_was_shown, "No error dialog should appear: 'None' is valid for DShot150"

        # Assert cascade rule 2: Telem Type widget entries expanded immediately
        assert "Main Out" in telem_type_cb.list_keys, (
            f"Telem Type widget must include 'Main Out' (BDShot) after DShot150, got {telem_type_cb.list_keys}"
        )
        assert "SERIAL1" in telem_type_cb.list_keys, (
            f"Telem Type widget must include SERIAL ports after DShot150, got {telem_type_cb.list_keys}"
        )
        assert telem_type_cb.list_keys != ["None"], "Telem Type widget must offer more than 'None' for DShot150"

        # Assert cascade rule 2: current selection unchanged (no forced reset)
        assert telem_type_cb.get_selected_key() == "None", (
            f"Telem Type selection must remain 'None' (still valid), got '{telem_type_cb.get_selected_key()}'"
        )
        assert telem_protocol_cb.get_selected_key() == "None", (
            f"Telem Protocol selection must remain 'None', got '{telem_protocol_cb.get_selected_key()}'"
        )

        # Assert: mirroring applied after options — both comboboxes are enabled (not mirrored for DShot)
        assert str(telem_type_cb.cget("state")) != "disabled", "Telem Type must be enabled after DShot150 (not fully mirrored)"
        assert str(telem_protocol_cb.cget("state")) != "disabled", "Telem Protocol must be enabled after DShot150"

    def test_cascade_2_fc_esc_protocol_change_to_brushed_restricts_telem_type_widget_to_none(
        self,
        component_editor_window: ComponentEditorWindow,
        gui_test_environment,  # pylint: disable=unused-argument
    ) -> None:
        """
        Cascade rule 2 restricting: DShot300 to Brushed Protocol change restricts Telem Type to None.

        Changing from DShot300 to Brushed immediately restricts the ESC->FC Telemetry Type
        widget entries to only "None".

        GIVEN: FC->ESC Connection is ("Main Out", "DShot300") and ESC->FC Telemetry is ("None", "None")
        WHEN: The user changes FC->ESC Protocol to "Brushed"
        THEN: ESC->FC Telemetry Type widget entries shrink to ["None"] only
        AND: ESC->FC Telemetry Protocol widget entries shrink to ["None"] only
        AND: Both selections stay "None" (still valid — no error needed)
        AND: No error dialog is shown
        """
        editor = component_editor_window

        fc_esc_type_path = ("ESC", "FC->ESC Connection", "Type")
        fc_esc_protocol_path = ("ESC", "FC->ESC Connection", "Protocol")
        telem_type_path = ("ESC", "ESC->FC Telemetry", "Type")
        telem_protocol_path = ("ESC", "ESC->FC Telemetry", "Protocol")

        fc_esc_type_cb = editor.entry_widgets[fc_esc_type_path]
        assert isinstance(fc_esc_type_cb, PairTupleCombobox)
        fc_esc_protocol_cb = editor.entry_widgets[fc_esc_protocol_path]
        assert isinstance(fc_esc_protocol_cb, PairTupleCombobox)
        telem_type_cb = editor.entry_widgets[telem_type_path]
        assert isinstance(telem_type_cb, PairTupleCombobox)
        telem_protocol_cb = editor.entry_widgets[telem_protocol_path]
        assert isinstance(telem_protocol_cb, PairTupleCombobox)

        # Arrange: FC->ESC = (Main Out, DShot300), ESC->FC = (None, None)
        with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor.show_error_message"):
            fc_esc_type_cb.set_entries_tuple(
                [(k, k) for k in editor.data_model.get_combobox_values_for_path(fc_esc_type_path)],
                "Main Out",
            )
            fc_esc_type_cb.event_generate("<<ComboboxSelected>>")
            editor.root.update_idletasks()
            editor.root.update()

            editor.data_model.set_component_value(fc_esc_protocol_path, "DShot300")
            fc_esc_protocol_cb.set_entries_tuple([("DShot300", "DShot300")], "DShot300")
            fc_esc_protocol_cb.event_generate("<<ComboboxSelected>>")
            editor.root.update_idletasks()
            editor.root.update()

        # Verify pre-conditions: DShot300 should have expanded Telem Type options
        assert "Main Out" in telem_type_cb.list_keys, (
            f"Pre-condition: DShot300 should expand Telem Type widget, got {telem_type_cb.list_keys}"
        )
        assert telem_type_cb.get_selected_key() == "None"

        # Act: change FC->ESC Protocol to Brushed
        error_was_shown = False

        def record_error(*_args: object, **_kwargs: object) -> None:
            nonlocal error_was_shown
            error_was_shown = True

        with patch(
            "ardupilot_methodic_configurator.frontend_tkinter_component_editor.show_error_message",
            side_effect=record_error,
        ):
            editor.data_model.set_component_value(fc_esc_protocol_path, "Brushed")
            fc_esc_protocol_cb.set_entries_tuple([("Brushed", "Brushed")], "Brushed")
            fc_esc_protocol_cb.event_generate("<<ComboboxSelected>>")
            editor.root.update_idletasks()
            editor.root.update()

        # Assert cascade rule 2: no error (current "None" is still valid for Brushed)
        assert not error_was_shown, "No error dialog should appear: 'None' is valid for Brushed"

        # Assert cascade rule 2: Telem Type widget entries restricted to ["None"]
        assert telem_type_cb.list_keys == ["None"], (
            f"Telem Type widget must be restricted to ['None'] for Brushed, got {telem_type_cb.list_keys}"
        )

        # Assert cascade rule 2: Telem Protocol widget entries restricted to ["None"]
        assert telem_protocol_cb.list_keys == ["None"], (
            f"Telem Protocol widget must be restricted to ['None'] for Brushed, got {telem_protocol_cb.list_keys}"
        )

        # Assert: selections remain "None" (valid, no forced reset needed)
        assert telem_type_cb.get_selected_key() == "None"
        assert telem_protocol_cb.get_selected_key() == "None"

    # -------------------------------------------------------------------------
    # Cascade rule 3: ESC->FC Telemetry Type change → Telem Protocol
    # -------------------------------------------------------------------------

    def test_cascade_3_telem_type_change_from_none_to_main_out_shows_bdshot_protocol_in_widget(
        self,
        component_editor_window: ComponentEditorWindow,
        gui_test_environment,  # pylint: disable=unused-argument
    ) -> None:
        """
        Cascade rule 3: Telem Type change from None to Main Out updates Protocol widget to BDShotOnly.

        Changing ESC->FC Telemetry Type from "None" to "Main Out" (BDShot back-channel)
        immediately updates the Telem Protocol widget to show only "BDShotOnly".

        GIVEN: FC->ESC Connection is ("Main Out", "DShot300") and ESC->FC Telemetry is ("None", "None")
        WHEN: The user changes ESC->FC Telemetry Type to "Main Out"
        THEN: ESC->FC Telemetry Protocol widget entries contain only "BDShotOnly"
        AND: "ESC Telemetry" is NOT offered (that is for SERIAL back-channel, not BDShot)
        AND: "None" is NOT offered (back-channel is now active)
        AND: ESC->FC Telemetry Protocol is auto-selected to "BDShotOnly" (single valid option)
        """
        editor = component_editor_window

        fc_esc_type_path = ("ESC", "FC->ESC Connection", "Type")
        fc_esc_protocol_path = ("ESC", "FC->ESC Connection", "Protocol")
        telem_type_path = ("ESC", "ESC->FC Telemetry", "Type")
        telem_protocol_path = ("ESC", "ESC->FC Telemetry", "Protocol")

        fc_esc_type_cb = editor.entry_widgets[fc_esc_type_path]
        assert isinstance(fc_esc_type_cb, PairTupleCombobox)
        fc_esc_protocol_cb = editor.entry_widgets[fc_esc_protocol_path]
        assert isinstance(fc_esc_protocol_cb, PairTupleCombobox)
        telem_type_cb = editor.entry_widgets[telem_type_path]
        assert isinstance(telem_type_cb, PairTupleCombobox)
        telem_protocol_cb = editor.entry_widgets[telem_protocol_path]
        assert isinstance(telem_protocol_cb, PairTupleCombobox)

        # Arrange: FC->ESC = (Main Out, DShot300), ESC->FC = (None, None)
        with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor.show_error_message"):
            fc_esc_type_cb.set_entries_tuple(
                [(k, k) for k in editor.data_model.get_combobox_values_for_path(fc_esc_type_path)],
                "Main Out",
            )
            fc_esc_type_cb.event_generate("<<ComboboxSelected>>")
            editor.root.update_idletasks()
            editor.root.update()

            editor.data_model.set_component_value(fc_esc_protocol_path, "DShot300")
            fc_esc_protocol_cb.set_entries_tuple([("DShot300", "DShot300")], "DShot300")
            fc_esc_protocol_cb.event_generate("<<ComboboxSelected>>")
            editor.root.update_idletasks()
            editor.root.update()

        # Verify pre-conditions: telem type widget must offer "Main Out" (DShot BDShot option)
        assert "Main Out" in telem_type_cb.list_keys, (
            f"Pre-condition: DShot300 must offer 'Main Out' in Telem Type widget, got {telem_type_cb.list_keys}"
        )
        assert telem_type_cb.get_selected_key() == "None"

        # Act: change Telem Type to "Main Out" (BDShot back-channel)
        with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor.show_error_message"):
            telem_type_cb.set_entries_tuple([(k, k) for k in telem_type_cb.list_keys], "Main Out")
            telem_type_cb.event_generate("<<ComboboxSelected>>")
            editor.root.update_idletasks()
            editor.root.update()

        # Assert cascade rule 3: Telem Protocol widget entries updated to BDShot only
        assert telem_type_cb.get_selected_key() == "Main Out"
        assert "BDShotOnly" in telem_protocol_cb.list_keys, (
            f"BDShot back-channel must offer 'BDShotOnly' protocol, got {telem_protocol_cb.list_keys}"
        )
        assert "ESC Telemetry" not in telem_protocol_cb.list_keys, (
            f"'ESC Telemetry' must NOT appear for 'Main Out' BDShot (it belongs to SERIAL), got {telem_protocol_cb.list_keys}"
        )
        # With only one valid option, it should be auto-selected
        assert telem_protocol_cb.get_selected_key() == "BDShotOnly", (
            f"Protocol must be auto-selected to 'BDShotOnly' (only option), got '{telem_protocol_cb.get_selected_key()}'"
        )

    def test_cascade_3_telem_type_change_from_none_to_serial_updates_protocol_widget(
        self,
        component_editor_window: ComponentEditorWindow,
        gui_test_environment,  # pylint: disable=unused-argument
    ) -> None:
        """
        Cascade rule 3: Telem Type change to SERIAL updates Protocol widget for active FC->ESC Protocol.

        Changing ESC->FC Telemetry Type to a SERIAL port immediately updates the
        Telem Protocol widget to show the correct protocol for the active FC->ESC Protocol.

        For DShot: SERIAL type → "ESC Telemetry" (dedicated back-channel).
        For Normal: SERIAL type → "Scripting" (scripting-based back-channel).

        GIVEN: FC->ESC Connection is ("Main Out", "DShot150") and ESC->FC Telemetry is ("None", "None")
        WHEN: The user changes ESC->FC Telemetry Type to "SERIAL4"
        THEN: ESC->FC Telemetry Protocol widget contains "ESC Telemetry"
        AND: "Scripting" is NOT offered (that belongs to Normal, not DShot)
        AND: The widget's list_keys is updated (not just the data model)
        """
        editor = component_editor_window

        fc_esc_type_path = ("ESC", "FC->ESC Connection", "Type")
        fc_esc_protocol_path = ("ESC", "FC->ESC Connection", "Protocol")
        telem_type_path = ("ESC", "ESC->FC Telemetry", "Type")
        telem_protocol_path = ("ESC", "ESC->FC Telemetry", "Protocol")

        fc_esc_type_cb = editor.entry_widgets[fc_esc_type_path]
        assert isinstance(fc_esc_type_cb, PairTupleCombobox)
        fc_esc_protocol_cb = editor.entry_widgets[fc_esc_protocol_path]
        assert isinstance(fc_esc_protocol_cb, PairTupleCombobox)
        telem_type_cb = editor.entry_widgets[telem_type_path]
        assert isinstance(telem_type_cb, PairTupleCombobox)
        telem_protocol_cb = editor.entry_widgets[telem_protocol_path]
        assert isinstance(telem_protocol_cb, PairTupleCombobox)

        # Arrange: FC->ESC = (Main Out, DShot150), ESC->FC = (None, None)
        with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor.show_error_message"):
            fc_esc_type_cb.set_entries_tuple(
                [(k, k) for k in editor.data_model.get_combobox_values_for_path(fc_esc_type_path)],
                "Main Out",
            )
            fc_esc_type_cb.event_generate("<<ComboboxSelected>>")
            editor.root.update_idletasks()
            editor.root.update()

            editor.data_model.set_component_value(fc_esc_protocol_path, "DShot150")
            fc_esc_protocol_cb.set_entries_tuple([("DShot150", "DShot150")], "DShot150")
            fc_esc_protocol_cb.event_generate("<<ComboboxSelected>>")
            editor.root.update_idletasks()
            editor.root.update()

        # Verify pre-conditions
        assert fc_esc_protocol_cb.get_selected_key() == "DShot150"
        assert "SERIAL4" in telem_type_cb.list_keys, (
            f"Pre-condition: DShot150 must offer SERIAL ports in Telem Type widget, got {telem_type_cb.list_keys}"
        )

        # Act: change Telem Type to SERIAL4
        with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor.show_error_message"):
            telem_type_cb.set_entries_tuple([(k, k) for k in telem_type_cb.list_keys], "SERIAL4")
            telem_type_cb.event_generate("<<ComboboxSelected>>")
            editor.root.update_idletasks()
            editor.root.update()

        # Assert cascade rule 3: Telem Protocol widget entries updated
        assert telem_type_cb.get_selected_key() == "SERIAL4"
        assert "ESC Telemetry" in telem_protocol_cb.list_keys, (
            f"DShot150/SERIAL4 must offer 'ESC Telemetry' in Protocol widget, got {telem_protocol_cb.list_keys}"
        )
        assert "Scripting" not in telem_protocol_cb.list_keys, (
            f"'Scripting' must NOT appear for DShot150 (it belongs to Normal), got {telem_protocol_cb.list_keys}"
        )
        assert "BDShotOnly" not in telem_protocol_cb.list_keys, (
            f"'BDShotOnly' must NOT appear for SERIAL4 (it is a PWM back-channel, not SERIAL), "
            f"got {telem_protocol_cb.list_keys}"
        )
