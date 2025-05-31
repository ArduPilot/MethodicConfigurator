#!/usr/bin/env python3

"""
Data-dependent part of the component editor GUI.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from argparse import ArgumentParser, Namespace

# from logging import debug as logging_debug
# from logging import info as logging_info
from logging import basicConfig as logging_basicConfig
from logging import getLevelName as logging_getLevelName
from tkinter import ttk
from typing import Callable, Optional, Union

from ardupilot_methodic_configurator import _, __version__
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.common_arguments import add_common_arguments
from ardupilot_methodic_configurator.data_model_vehicle_components import ComponentPath, ValidationRulePath
from ardupilot_methodic_configurator.frontend_tkinter_component_editor_base import ComponentEditorWindowBase

# from ardupilot_methodic_configurator.frontend_tkinter_show import show_tooltip
from ardupilot_methodic_configurator.frontend_tkinter_show import show_error_message


def argument_parser() -> Namespace:
    """
    Parses command-line arguments for the script.

    This function sets up an argument parser to handle the command-line arguments for the script.

    Returns:
    argparse.Namespace: An object containing the parsed arguments.

    """
    # pylint: disable=duplicate-code
    parser = ArgumentParser(
        description=_(
            "A GUI for editing JSON files that contain vehicle component configurations. "
            "Not to be used directly, but through the main ArduPilot methodic configurator script."
        )
    )
    parser = LocalFilesystem.add_argparse_arguments(parser)
    parser = ComponentEditorWindow.add_argparse_arguments(parser)
    return add_common_arguments(parser).parse_args()
    # pylint: enable=duplicate-code


class VoltageTooLowError(Exception):
    """Raised when the voltage is below the minimum limit."""


class VoltageTooHighError(Exception):
    """Raised when the voltage is above the maximum limit."""


class MockEvent(tk.Event):  # pylint: disable=too-few-public-methods
    """A mock event object that mirrors the structure of a real tkinter event."""

    def __init__(self, event_type: tk.EventType) -> None:
        self.type = event_type


class ComponentEditorWindow(ComponentEditorWindowBase):
    """Validates the user input and handles user interactions for editing component configurations."""

    def __init__(self, version: str, local_filesystem: LocalFilesystem) -> None:
        ComponentEditorWindowBase.__init__(self, version, local_filesystem)

    def set_vehicle_type_and_version(self, vehicle_type: str, version: str) -> None:
        """Set the vehicle type and version in the data model."""
        # Update UI if widgets exist
        self.set_component_value_and_update_ui(("Flight Controller", "Firmware", "Type"), vehicle_type)
        if version:
            self.set_component_value_and_update_ui(("Flight Controller", "Firmware", "Version"), version)

    def set_fc_manufacturer(self, manufacturer: str) -> None:
        """Set the flight controller manufacturer if it's valid."""
        # Update UI if widget exists
        if self.data_model.is_fc_manufacturer_valid(manufacturer):
            self.set_component_value_and_update_ui(("Flight Controller", "Product", "Manufacturer"), manufacturer)

    def set_fc_model(self, model: str) -> None:
        """Set the flight controller model if it's valid."""
        # Update UI if widget exists
        if self.data_model.is_fc_model_valid(model):
            self.set_component_value_and_update_ui(("Flight Controller", "Product", "Model"), model)

    def set_mcu_series(self, mcu: str) -> None:
        """Set the MCU series in the data model."""
        # Update UI if widget exists
        if mcu:
            self.set_component_value_and_update_ui(("Flight Controller", "Specifications", "MCU Series"), mcu)

    def set_vehicle_configuration_template(self, configuration_template: str) -> None:
        """Set the configuration template name in the data."""
        self.data_model.set_configuration_template(configuration_template)

    def set_values_from_fc_parameters(self, fc_parameters: dict, doc: dict) -> None:
        """
        Process flight controller parameters and update the data model.

        This delegates to the data model's process_fc_parameters method to handle
        all the business logic of processing parameters.
        """
        # Delegate to the data model for parameter processing
        self.data_model.process_fc_parameters(fc_parameters, doc)

    def update_rc_protocol_combobox_entries(self, rc_connection_type: str) -> str:
        """Updates the RC Protocol combobox entries based on the selected RC connection Type."""
        protocols = self.data_model.get_rc_protocol_values(rc_connection_type, self.local_filesystem.doc_dict)
        protocol_path = ("RC Receiver", "FC Connection", "Protocol")
        return self.update_protocol_combobox_entries(protocols, protocol_path)

    def update_telem_protocol_combobox_entries(self, telem_connection_type: str) -> str:
        """Updates the Telemetry Protocol combobox entries based on the selected Telemetry connection Type."""
        protocols = self.data_model.get_telem_protocol_values(telem_connection_type, self.local_filesystem.doc_dict)
        protocol_path = ("Telemetry", "FC Connection", "Protocol")
        return self.update_protocol_combobox_entries(protocols, protocol_path)

    def update_battery_protocol_combobox_entries(self, battery_connection_type: str) -> str:
        """Updates the Battery Monitor Protocol combobox entries based on the selected Battery Monitor connection Type."""
        protocols = self.data_model.get_battery_protocol_values(battery_connection_type, self.local_filesystem.doc_dict)
        protocol_path = ("Battery Monitor", "FC Connection", "Protocol")
        return self.update_protocol_combobox_entries(protocols, protocol_path)

    def update_esc_protocol_combobox_entries(self, esc_connection_type: str) -> str:
        """Updates the ESC Protocol combobox entries based on the selected ESC connection Type."""
        protocols = self.data_model.get_esc_protocol_values(esc_connection_type, self.local_filesystem.doc_dict)
        protocol_path = ("ESC", "FC Connection", "Protocol")
        return self.update_protocol_combobox_entries(protocols, protocol_path)

    def update_gnss_protocol_combobox_entries(self, gnss_connection_type: str) -> str:
        """Updates the GNSS Protocol combobox entries based on the selected GNSS connection Type."""
        protocols = self.data_model.get_gnss_protocol_values(gnss_connection_type, self.local_filesystem.doc_dict)
        protocol_path = ("GNSS Receiver", "FC Connection", "Protocol")
        return self.update_protocol_combobox_entries(protocols, protocol_path)

    def update_protocol_combobox_entries(self, protocols: list[str], protocol_path: ValidationRulePath) -> str:
        err_msg = ""
        if protocol_path in self.entry_widgets:
            protocol_combobox = self.entry_widgets[protocol_path]
            protocol_combobox["values"] = protocols  # Update the combobox entries
            selected_protocol = protocol_combobox.get()
            if selected_protocol not in protocols and isinstance(protocol_combobox, ttk.Combobox):
                protocol_combobox.set(protocols[0] if protocols else "")
                err_msg = f"On {' > '.join(protocol_path)} the selected\nprotocol '{selected_protocol}' is not available for the currently selected connection Type."
                err_msg += f" Defaulting to '{protocols[0]}'." if protocols else " No protocols available."
                err_msg = _(err_msg)
            protocol_combobox.update_idletasks()  # re-draw the combobox ASAP
        return err_msg

    def add_entry_or_combobox(
        self, value: Union[str, float], entry_frame: ttk.Frame, path: ValidationRulePath, is_optional: bool = False
    ) -> Union[ttk.Entry, ttk.Combobox]:
        # Get combobox values from data model
        combobox_values = self.data_model.get_combobox_values_for_path(path, self.local_filesystem.doc_dict)

        # Determine foreground color based on is_optional flag
        fg_color = "gray" if is_optional else "black"

        if combobox_values:
            cb = ttk.Combobox(entry_frame, values=combobox_values, foreground=fg_color)
            cb.bind("<FocusOut>", lambda event, path=path: self._validate_combobox(event, path))  # type: ignore[misc]
            cb.bind("<KeyRelease>", lambda event, path=path: self._validate_combobox(event, path))  # type: ignore[misc]

            # Prevent mouse wheel from changing value when dropdown is not open
            def handle_mousewheel(_event: tk.Event, widget: tk.Widget = cb) -> Optional[str]:
                # Check if dropdown is open by examining the combobox's state
                if not hasattr(widget, "_dropdown_open") or not widget._dropdown_open:  # pylint: disable=protected-access,line-too-long # noqa: SLF001 # pyright: ignore[reportAttributeAccessIssue]
                    return "break"  # Prevent default behavior
                return None  # Allow default behavior when dropdown is open

            # Set flag when dropdown opens or closes
            def dropdown_opened(_event: tk.Event, widget: tk.Widget = cb) -> None:
                widget._dropdown_open = True  # type: ignore[attr-defined] # pylint: disable=protected-access # noqa: SLF001

            def dropdown_closed(_event: tk.Event, widget: tk.Widget = cb) -> None:
                widget._dropdown_open = False  # type: ignore[attr-defined] # pylint: disable=protected-access # noqa: SLF001

            # Initialize the flag
            cb._dropdown_open = False  # type: ignore[attr-defined] # pylint: disable=protected-access # noqa: SLF001

            # Bind to events for dropdown opening and closing
            cb.bind("<<ComboboxDropdown>>", dropdown_opened)
            cb.bind(
                "<FocusOut>",
                lambda e, p=path: (dropdown_closed(e), self._validate_combobox(e, p)),  # type: ignore[misc, func-returns-value]
            )
            # Bind mouse wheel events
            cb.bind("<MouseWheel>", handle_mousewheel)  # Windows mouse wheel
            cb.bind("<Button-4>", handle_mousewheel)  # Linux mouse wheel up
            cb.bind("<Button-5>", handle_mousewheel)  # Linux mouse wheel down

            if path == ("RC Receiver", "FC Connection", "Type"):
                cb.bind(  # immediate update of RC Receiver Protocol upon RC connection Type selection
                    "<<ComboboxSelected>>",
                    lambda event: self.update_rc_protocol_combobox_entries(cb.get()),  # noqa: ARG005
                )

            if path == ("Telemetry", "FC Connection", "Type"):
                cb.bind(  # immediate update of Telemetry Protocol upon Telemetry connection Type selection
                    "<<ComboboxSelected>>",
                    lambda event: self.update_telem_protocol_combobox_entries(cb.get()),  # noqa: ARG005
                )

            if path == ("Battery Monitor", "FC Connection", "Type"):
                cb.bind(  # immediate update of Battery Monitor Protocol upon Battery Monitor connection Type selection
                    "<<ComboboxSelected>>",
                    lambda event: self.update_battery_protocol_combobox_entries(cb.get()),  # noqa: ARG005
                )

            if path == ("ESC", "FC Connection", "Type"):
                cb.bind(  # immediate update of ESC Protocol upon ESC connection Type selection
                    "<<ComboboxSelected>>",
                    lambda event: self.update_esc_protocol_combobox_entries(cb.get()),  # noqa: ARG005
                )

            if path == ("GNSS Receiver", "FC Connection", "Type"):
                cb.bind(  # immediate update of GNSS Protocol upon GNSS connection Type selection
                    "<<ComboboxSelected>>",
                    lambda event: self.update_gnss_protocol_combobox_entries(cb.get()),  # noqa: ARG005
                )

            cb.set(value)
            return cb

        entry = ttk.Entry(entry_frame, foreground=fg_color)
        validate_function = self.get_validate_function(entry, path)
        if validate_function:
            entry.bind("<FocusOut>", validate_function)
            entry.bind("<KeyRelease>", validate_function)
        entry.insert(0, str(value))
        return entry

    def get_validate_function(self, entry: ttk.Entry, path: ValidationRulePath) -> Union[Callable[[tk.Event], object], None]:
        # Only return validation functions for specific paths that need real-time validation
        voltage_paths = {
            ("Battery", "Specifications", "Volt per cell max"),
            ("Battery", "Specifications", "Volt per cell low"),
            ("Battery", "Specifications", "Volt per cell crit"),
        }

        if path in voltage_paths:

            def validate_voltage(event: tk.Event) -> bool:
                return self.validate_cell_voltage_ui(event, entry, path)

            return validate_voltage

        # For other paths that have validation rules, use generic validation
        if self.data_model.has_validation_rules(path):

            def validate_limits(event: tk.Event) -> bool:
                return self.validate_entry_limits_ui(event, entry, path)

            return validate_limits

        return None

    def _validate_combobox(self, event: tk.Event, path: ComponentPath) -> bool:
        """Validates the value of a combobox."""
        combobox = event.widget  # Get the combobox widget that triggered the event
        value = combobox.get()  # Get the current value of the combobox
        allowed_values = combobox.cget("values")  # Get the list of allowed values

        if value not in allowed_values:
            if event.type == "10":  # FocusOut events
                _paths_str = ">".join(list(path))
                _allowed_str = ", ".join(allowed_values)
                error_msg = _("Invalid value '{value}' for {_paths_str}\nAllowed values are: {_allowed_str}")
                show_error_message(_("Error"), error_msg.format(value=value, _paths_str=_paths_str, _allowed_str=_allowed_str))
            combobox.configure(style="comb_input_invalid.TCombobox")
            return False

        if path == ("RC Receiver", "FC Connection", "Type"):
            self.update_rc_protocol_combobox_entries(value)

        if path == ("Telemetry", "FC Connection", "Type"):
            self.update_telem_protocol_combobox_entries(value)

        if path == ("Battery Monitor", "FC Connection", "Type"):
            self.update_battery_protocol_combobox_entries(value)

        if path == ("ESC", "FC Connection", "Type"):
            self.update_esc_protocol_combobox_entries(value)

        if path == ("GNSS Receiver", "FC Connection", "Type"):
            self.update_gnss_protocol_combobox_entries(value)

        combobox.configure(style="comb_input_valid.TCombobox")
        return True

    def validate_entry_limits_ui(self, event: Union[None, tk.Event], entry: ttk.Entry, path: ValidationRulePath) -> bool:
        """UI wrapper for entry limits validation."""
        is_focusout_event = event and event.type == "10"
        value = entry.get()

        is_valid, error_msg = self.data_model.validate_entry_limits(value, path)

        if not is_valid:
            if is_focusout_event:
                _paths_str = ">".join(list(path))
                error_msg = _("Invalid value '{value}' for {_paths_str}\n{error_msg}")
                show_error_message(_("Error"), error_msg.format(value=value, _paths_str=_paths_str, error_msg=error_msg))
            entry.configure(style="entry_input_invalid.TEntry")
            return False

        entry.configure(style="entry_input_valid.TEntry")
        return True

    def validate_cell_voltage_ui(self, event: Union[None, tk.Event], entry: ttk.Entry, path: ValidationRulePath) -> bool:
        """UI wrapper for battery cell voltage validation."""
        chemistry_path = ("Battery", "Specifications", "Chemistry")
        if chemistry_path not in self.entry_widgets:
            show_error_message(_("Error"), _("Battery Chemistry not set. Will default to Lipo."))
            chemistry = "Lipo"
        else:
            chemistry = self.entry_widgets[chemistry_path].get()

        value = entry.get()
        is_focusout_event = event and event.type == "10"

        is_valid, error_msg, corrected_value = self.data_model.validate_cell_voltage(value, path, chemistry)

        if not is_valid:
            if is_focusout_event:
                entry.delete(0, tk.END)
                entry.insert(0, corrected_value)
                _path_str = ">".join(list(path))
                error_msg = _("Invalid value '{value}' for {_path_str}\n{error_msg}")
                show_error_message(_("Error"), error_msg.format(value=value, _path_str=_path_str, error_msg=error_msg))
            else:
                entry.configure(style="entry_input_invalid.TEntry")
                return False

        entry.configure(style="entry_input_valid.TEntry")
        return True

    def validate_data(self) -> bool:
        """Validate all data using the data model."""
        # Collect all entry values
        entry_values = {path: entry.get() for path, entry in self.entry_widgets.items() if len(path) == 3}

        # Use data model for validation
        is_valid, errors = self.data_model.validate_all_data(entry_values, self.local_filesystem.doc_dict)

        if not is_valid:
            # Update UI to show invalid states and display errors
            for path, entry in self.entry_widgets.items():
                if len(path) != 3:
                    continue

                value = entry.get()

                # Check combobox validation
                if isinstance(entry, ttk.Combobox):
                    if path == ("RC Receiver", "FC Connection", "Type"):
                        self.update_rc_protocol_combobox_entries(value)
                    if path == ("Telemetry", "FC Connection", "Type"):
                        self.update_telem_protocol_combobox_entries(value)
                    if path == ("Battery Monitor ", "FC Connection", "Type"):
                        self.update_battery_protocol_combobox_entries(value)
                    if path == ("ESC", "FC Connection", "Type"):
                        self.update_esc_protocol_combobox_entries(value)
                    if path == ("GNSS Receiver", "FC Connection", "Type"):
                        self.update_gnss_protocol_combobox_entries(value)
                    combobox_values = self.data_model.get_combobox_values_for_path(path, self.local_filesystem.doc_dict)
                    if combobox_values and value not in combobox_values:
                        entry.configure(style="comb_input_invalid.TCombobox")
                    else:
                        entry.configure(style="comb_input_valid.TCombobox")
                else:
                    # Check entry validation
                    entry_valid, _error_message = self.data_model.validate_entry_limits(value, path)
                    if not entry_valid:
                        entry.configure(style="entry_input_invalid.TEntry")
                    else:
                        entry.configure(style="entry_input_valid.TEntry")

            # Show first few errors
            if errors:
                error_message = "\n".join(errors[:3])  # Show first 3 errors
                if len(errors) > 3:
                    error_message += f"\n... and {len(errors) - 3} more errors"
                show_error_message(_("Validation Errors"), error_message)

        return is_valid


# pylint: disable=duplicate-code
if __name__ == "__main__":
    args = argument_parser()

    logging_basicConfig(level=logging_getLevelName(args.loglevel), format="%(asctime)s - %(levelname)s - %(message)s")

    filesystem = LocalFilesystem(
        args.vehicle_dir, args.vehicle_type, "", args.allow_editing_template_files, args.save_component_to_system_templates
    )
    component_editor_window = ComponentEditorWindow(__version__, filesystem)

    component_editor_window.populate_frames()
    if args.skip_component_editor:
        component_editor_window.root.after(10, component_editor_window.root.destroy)

    component_editor_window.validate_data()

    component_editor_window.root.mainloop()
# pylint: enable=duplicate-code
