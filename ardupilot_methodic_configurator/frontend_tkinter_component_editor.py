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
from typing import Optional, Union

from ardupilot_methodic_configurator import _, __version__
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.common_arguments import add_common_arguments
from ardupilot_methodic_configurator.data_model_vehicle_components_base import ComponentPath
from ardupilot_methodic_configurator.data_model_vehicle_components_validation import (
    BATTERY_CELL_VOLTAGE_PATHS,
    FC_CONNECTION_TYPE_PATHS,
)
from ardupilot_methodic_configurator.frontend_tkinter_component_editor_base import ComponentEditorWindowBase

# from ardupilot_methodic_configurator.frontend_tkinter_show import show_tooltip
from ardupilot_methodic_configurator.frontend_tkinter_show import show_error_message, show_warning_message


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


class ComponentEditorWindow(ComponentEditorWindowBase):
    """Validates the user input and handles user interactions for editing component configurations."""

    def __init__(self, version: str, local_filesystem: LocalFilesystem) -> None:
        ComponentEditorWindowBase.__init__(self, version, local_filesystem)
        # when only read from file and no FC is connected
        mcu = self.data_model.get_component_value(("Flight Controller", "Specifications", "MCU Series"))
        if mcu and isinstance(mcu, str):
            self.set_mcu_series(mcu)

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
            if mcu.upper() in ("STM32F4XX", "STM32F7XX", "STM32H7XX"):
                self.data_model.schema.modify_schema_for_mcu_series(is_optional=True)

    def update_component_protocol_combobox_entries(self, component_path: ComponentPath, connection_type: str) -> str:
        """Updates the Protocol combobox entries based on the selected component connection Type."""
        self.data_model.set_component_value(component_path, connection_type)

        # when the connection Type changes, we need to update the Protocol combobox entries
        protocol_path: ComponentPath = (component_path[0], component_path[1], "Protocol")
        return self.update_protocol_combobox_entries(
            self.data_model.get_combobox_values_for_path(protocol_path), protocol_path
        )

    def update_protocol_combobox_entries(self, protocols: tuple[str, ...], protocol_path: ComponentPath) -> str:
        err_msg = ""
        if protocol_path in self.entry_widgets:
            protocol_combobox = self.entry_widgets[protocol_path]
            protocol_combobox["values"] = protocols  # Update the combobox entries
            selected_protocol = protocol_combobox.get()
            if selected_protocol not in protocols and isinstance(protocol_combobox, ttk.Combobox):
                protocol_combobox.set("")
                _component: str = " > ".join(protocol_path)
                err_msg = _(
                    "On {_component} the selected\nprotocol '{selected_protocol}' "
                    "is not available for the selected connection Type."
                )
                err_msg = err_msg.format(**locals())
            if err_msg:
                show_error_message(_("Error"), err_msg)
                protocol_combobox.configure(style="comb_input_invalid.TCombobox")
            protocol_combobox.update_idletasks()  # re-draw the combobox ASAP
        return err_msg

    def update_cell_voltage_limits_entries(self, component_path: ComponentPath, chemistry: str) -> str:
        """
        Updates the cell voltage limits entries based on the selected battery chemistry.

        This method updates the max, low, and crit voltages for the battery based on the selected chemistry.
        """
        if self.data_model.get_component_value(component_path) == chemistry:
            return ""

        show_warning_message(
            _("Warning"),
            _(
                "Will update the cell voltage limits to the recommended\n"
                "values for {chemistry} chemistry.\n"
                "This will overwrite any custom values you may have set."
            ).format(chemistry=chemistry),
        )

        # this will trigger the data_model to update the voltages for the selected chemistry
        self.data_model.set_component_value(component_path, chemistry)

        err_msg = ""
        if component_path in self.entry_widgets:
            for voltage_path in BATTERY_CELL_VOLTAGE_PATHS:
                voltage_entry = self.entry_widgets[voltage_path]
                value = self.data_model.get_component_value(voltage_path)
                if value is not None:
                    voltage_entry.delete(0, tk.END)
                    voltage_entry.insert(0, str(value))
                    voltage_entry.configure(style="entry_input_valid.TEntry")
                else:
                    err_msg += _("No valid value found for {voltage_path} with chemistry {chemistry}.\n").format(
                        voltage_path=voltage_path, chemistry=chemistry
                    )
        return err_msg

    def add_entry_or_combobox(
        self, value: Union[str, float], entry_frame: ttk.Frame, path: ComponentPath, is_optional: bool = False
    ) -> Union[ttk.Entry, ttk.Combobox]:
        # Get combobox values from data model
        combobox_values = self.data_model.get_combobox_values_for_path(path)

        # Determine foreground color based on is_optional flag
        fg_color = "gray" if is_optional else "black"

        def on_validate_combobox(event: tk.Event) -> bool:
            return self._validate_combobox(event, path)

        if combobox_values:
            cb = ttk.Combobox(entry_frame, values=combobox_values, foreground=fg_color)
            cb.bind("<FocusOut>", on_validate_combobox)
            cb.bind("<KeyRelease>", on_validate_combobox)
            cb.bind("<Return>", on_validate_combobox)
            cb.bind("<ButtonRelease>", on_validate_combobox)

            # Prevent mouse wheel from changing value when dropdown is not open
            def handle_mousewheel(_event: tk.Event, widget: tk.Widget = cb) -> Optional[str]:
                # Check if dropdown is open by examining the combobox's state
                dropdown_is_open = getattr(widget, "dropdown_is_open", False)
                if not dropdown_is_open:
                    return "break"  # Prevent default behavior
                return None  # Allow default behavior when dropdown is open

            # Set flag when dropdown opens or closes
            def dropdown_opened(_event: tk.Event, widget: tk.Widget = cb) -> None:
                widget.dropdown_is_open = True  # type: ignore[attr-defined]

            def dropdown_closed(_event: tk.Event, widget: tk.Widget = cb) -> None:
                widget.dropdown_is_open = False  # type: ignore[attr-defined]

            # Initialize the flag
            cb.dropdown_is_open = False  # type: ignore[attr-defined]

            # Bind to events for dropdown opening and closing
            cb.bind("<<ComboboxDropdown>>", dropdown_opened)
            cb.bind(
                "<FocusOut>",
                lambda e, p=path: (dropdown_closed(e), self._validate_combobox(e, p)),  # type: ignore[misc,func-returns-value]
            )
            # Bind mouse wheel events
            cb.bind("<MouseWheel>", handle_mousewheel)  # Windows mouse wheel
            cb.bind("<Button-4>", handle_mousewheel)  # Linux mouse wheel up
            cb.bind("<Button-5>", handle_mousewheel)  # Linux mouse wheel down

            if path in FC_CONNECTION_TYPE_PATHS:
                cb.bind(  # immediate update of Protocol combobox choices after changing connection Type selection
                    "<<ComboboxSelected>>",
                    lambda event: self.update_component_protocol_combobox_entries(path, cb.get()),  # noqa: ARG005
                )

            # When battery chemistry changes, the max, low and crit voltages will change to the
            # recommended values for the new chemistry, so we need to update the UI
            if path == ("Battery", "Specifications", "Chemistry"):
                cb.bind(
                    "<<ComboboxSelected>>",
                    lambda event: self.update_cell_voltage_limits_entries(path, cb.get()),  # noqa: ARG005
                )

            cb.set(value)
            return cb

        entry = ttk.Entry(entry_frame, foreground=fg_color)

        def on_validate_entry_limits_ui(event: tk.Event) -> bool:
            return self._validate_entry_limits_ui(event, entry, path)

        entry.bind("<FocusOut>", on_validate_entry_limits_ui)
        entry.bind("<KeyRelease>", on_validate_entry_limits_ui)
        entry.bind("<Return>", on_validate_entry_limits_ui)
        entry.insert(0, str(value))
        return entry

    def _validate_combobox(self, event: tk.Event, path: ComponentPath) -> bool:
        """Validates the value of a combobox."""
        combobox = event.widget  # Get the combobox widget that triggered the event
        if not isinstance(combobox, ttk.Combobox):
            return False
        value = combobox.get()  # Get the current value of the combobox
        allowed_values = combobox.cget("values")  # Get the list of allowed values

        # Events that should trigger data model update (when value is valid)
        should_update_data_model = event.type in {
            tk.EventType.FocusOut,
            tk.EventType.KeyPress,  # Return key
            tk.EventType.KeyRelease,  # Key release events
            tk.EventType.ButtonRelease,  # Mouse click on dropdown item
        }

        if should_update_data_model and value in allowed_values:
            self.data_model.set_component_value(path, value)

        if value not in allowed_values:
            if (  # this is complicated because we only want to issue error messages in particular cases
                (event.type == tk.EventType.FocusOut and getattr(combobox, "dropdown_is_open", False))  # FocusOut events
                or event.type == tk.EventType.KeyPress  # KeyPress event (Return key)
            ):
                paths_str = ">".join(list(path))
                allowed_str = ", ".join(allowed_values)
                error_msg = _("Invalid value '{value}' for {paths_str}\nAllowed values are: {allowed_str}")
                show_error_message(_("Error"), error_msg.format(value=value, paths_str=paths_str, allowed_str=allowed_str))

            combobox.configure(style="comb_input_invalid.TCombobox")
            return False

        combobox.configure(style="comb_input_valid.TCombobox")
        return True

    def _validate_entry_limits_ui(self, event: Union[None, tk.Event], entry: ttk.Entry, path: ComponentPath) -> bool:
        """UI wrapper for entry limits validation."""
        is_focusout_event = event and event.type in {
            tk.EventType.FocusOut,
            tk.EventType.KeyPress,  # Return key generates KeyPress event
        }
        value = entry.get()

        error_msg, corrected_value = self.data_model.validate_entry_limits(value, path)

        if error_msg:
            if is_focusout_event:
                if corrected_value is not None:
                    entry.delete(0, tk.END)
                    entry.insert(0, str(corrected_value))
                paths_str = ">".join(list(path))
                error_msg = _("Invalid value '{value}' for {paths_str}\n{error_msg}").format(
                    value=value, paths_str=paths_str, error_msg=error_msg
                )
                show_error_message(_("Error"), error_msg)
            entry.configure(style="entry_input_invalid.TEntry")
            return False

        if is_focusout_event:
            self.data_model.set_component_value(path, value)
        entry.configure(style="entry_input_valid.TEntry")
        return True


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

    component_editor_window.validate_data_and_highlight_errors_in_red()

    component_editor_window.root.mainloop()
# pylint: enable=duplicate-code
