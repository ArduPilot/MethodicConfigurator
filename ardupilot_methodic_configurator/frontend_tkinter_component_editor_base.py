#!/usr/bin/env python3

"""
Component editor GUI that is not data dependent.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from argparse import ArgumentParser, Namespace

# from logging import debug as logging_debug
from logging import basicConfig as logging_basicConfig
from logging import getLevelName as logging_getLevelName
from logging import info as logging_info
from sys import exit as sys_exit
from tkinter import messagebox, ttk
from typing import Any, Union

from ardupilot_methodic_configurator import _, __version__
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.common_arguments import add_common_arguments
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_component_template_manager import ComponentTemplateManager
from ardupilot_methodic_configurator.frontend_tkinter_rich_text import RichText
from ardupilot_methodic_configurator.frontend_tkinter_scroll_frame import ScrollFrame
from ardupilot_methodic_configurator.frontend_tkinter_show import show_error_message, show_tooltip
from ardupilot_methodic_configurator.frontend_tkinter_usage_popup_window import UsagePopupWindow


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
    parser = ComponentEditorWindowBase.add_argparse_arguments(parser)
    return add_common_arguments(parser).parse_args()
    # pylint: enable=duplicate-code


class ComponentEditorWindowBase(BaseWindow):
    """
    A class for editing JSON files in the ArduPilot methodic configurator.

    This class provides a graphical user interface for editing JSON files that
    contain vehicle component configurations. It inherits from the BaseWindow
    class, which provides basic window functionality.
    """

    def __init__(self, version: str, local_filesystem: LocalFilesystem) -> None:
        super().__init__()
        self.local_filesystem = local_filesystem

        self.root.title(_("Amilcar Lucas's - ArduPilot methodic configurator ") + version + _(" - Vehicle Component Editor"))
        self.root.geometry("880x600")  # Set the window width

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.data = local_filesystem.load_vehicle_components_json_data(local_filesystem.vehicle_dir)
        if len(self.data) < 1:
            # Schedule the window to be destroyed after the mainloop has started
            self.root.after(100, self.root.destroy)  # Adjust the delay as needed
            return

        self.entry_widgets: dict[tuple, Union[ttk.Entry, ttk.Combobox]] = {}

        intro_frame = ttk.Frame(self.main_frame)
        intro_frame.pack(side=tk.TOP, fill="x", expand=False)

        style = ttk.Style()
        style.configure("bigger.TLabel", font=("TkDefaultFont", 13))
        style.configure("comb_input_invalid.TCombobox", fieldbackground="red")
        style.configure("comb_input_valid.TCombobox", fieldbackground="white")
        style.configure("entry_input_invalid.TEntry", fieldbackground="red")
        style.configure("entry_input_valid.TEntry", fieldbackground="white")
        style.configure("Optional.TLabelframe", borderwidth=2)
        style.configure("Optional.TLabelframe.Label", foreground="gray")

        explanation_text = _("Please configure properties of the vehicle components.\n")
        explanation_text += _("Labels for optional properties are displayed in gray text.\n")
        explanation_text += _("Scroll down to ensure that you do not overlook any properties.\n")
        explanation_label = ttk.Label(intro_frame, text=explanation_text, wraplength=800, justify=tk.LEFT)
        explanation_label.configure(style="bigger.TLabel")
        explanation_label.pack(side=tk.LEFT, padx=(10, 10), pady=(10, 0), anchor=tk.NW)

        # Load the vehicle image and scale it down to image_height pixels in height
        if local_filesystem.vehicle_image_exists():
            image_label = self.put_image_in_label(intro_frame, local_filesystem.vehicle_image_filepath(), 100)
            image_label.pack(side=tk.RIGHT, anchor=tk.NE, padx=(4, 4), pady=(4, 0))
            show_tooltip(image_label, _("Replace the vehicle.jpg file in the vehicle directory to change the vehicle image."))
        else:
            image_label = ttk.Label(intro_frame, text=_("Add a 'vehicle.jpg' image file to the vehicle directory."))
            image_label.pack(side=tk.RIGHT, anchor=tk.NE, padx=(4, 4), pady=(4, 0))

        self.scroll_frame = ScrollFrame(self.main_frame)
        self.scroll_frame.pack(side="top", fill="both", expand=True)

        self.update_json_data()

        save_frame = ttk.Frame(self.main_frame)
        save_frame.pack(side=tk.TOP, fill="x", expand=False)
        self.save_button = ttk.Button(
            save_frame, text=_("Save data and start configuration"), command=self.validate_and_save_component_json
        )
        show_tooltip(
            self.save_button,
            _("Save component data to the vehicle_components.json file\nand start parameter value configuration and tuning."),
        )
        self.save_button.pack(pady=7)
        if UsagePopupWindow.should_display("component_editor"):
            self.root.after(10, self.__display_component_editor_usage_instructions(self.root))  # type: ignore[arg-type]

        def update_data_callback(comp_name: str, template_data: dict) -> None:
            self.data["Components"][comp_name] = template_data

        self.template_manager = ComponentTemplateManager(
            self.root,
            self.entry_widgets,
            self.get_component_data_from_gui,
            update_data_callback,
            self.derive_initial_template_name,
            local_filesystem.save_component_to_system_templates,
        )

    @staticmethod
    def __display_component_editor_usage_instructions(parent: tk.Tk) -> None:
        usage_popup_window = BaseWindow(parent)
        style = ttk.Style()

        instructions_text = RichText(
            usage_popup_window.main_frame, wrap=tk.WORD, height=5, bd=0, background=style.lookup("TLabel", "background")
        )
        instructions_text.insert(tk.END, _("1. Describe the properties of the vehicle components in the window below.\n"))
        instructions_text.insert(tk.END, _("2. Each field has mouse-over tooltips for additional guidance.\n"))
        instructions_text.insert(tk.END, _("3. Optional fields are marked with gray text and can be left blank.\n"))
        instructions_text.insert(tk.END, _("4. Scroll to the bottom of the window to ensure all properties are edited.\n"))
        instructions_text.insert(tk.END, _("5. Press the "))
        instructions_text.insert(tk.END, _("Save data and start configuration"), "italic")
        instructions_text.insert(tk.END, _(" button only after verifying that all information is correct.\n"))
        instructions_text.config(state=tk.DISABLED)

        UsagePopupWindow.display(
            parent,
            usage_popup_window,
            _("How to use the component editor window"),
            "component_editor",
            "690x200",
            instructions_text,
        )

    def update_json_data(self) -> None:  # should be overwritten in child classes
        if "Format version" not in self.data:
            self.data["Format version"] = 1

    def _set_component_value_and_update_ui(self, path: tuple, value: str) -> None:
        data_path = self.data["Components"]
        for key in path[:-1]:
            data_path = data_path[key]
        data_path[path[-1]] = value
        entry = self.entry_widgets[path]
        entry.delete(0, tk.END)
        entry.insert(0, value)
        entry.config(state="disabled")

    def populate_frames(self) -> None:
        """Populates the ScrollFrame with widgets based on the JSON data."""
        if "Components" in self.data:
            for key, value in self.data["Components"].items():
                self._add_widget(self.scroll_frame.view_port, key, value, [])

    def _add_widget(self, parent: tk.Widget, key: str, value: Union[dict, float], path: list) -> None:
        """
        Adds a widget to the parent widget with the given key and value.

        Args:
            parent (tkinter.Widget): The parent widget to which the LabelFrame/Entry will be added.
            key (str): The key for the LabelFrame/Entry.
            value (dict|float): The value associated with the key.
            path (list): The path to the current key in the JSON data.

        """
        if isinstance(value, dict):  # JSON non-leaf elements, add LabelFrame widget
            self.__add_non_leaf_widget(parent, key, value, path)
        else:  # JSON leaf elements, add Entry widget
            self.__add_leaf_widget(parent, key, value, path)

    def __add_non_leaf_widget(self, parent: tk.Widget, key: str, value: dict, path: list) -> None:
        is_toplevel = parent == self.scroll_frame.view_port
        pady = 5 if is_toplevel else 3

        current_path = (*path, key)
        description, is_optional = self.local_filesystem.get_component_property_description(current_path)
        description = _(description) if description else ""

        if is_optional:
            frame = ttk.LabelFrame(parent, text=_(key), style="Optional.TLabelframe")
        else:
            frame = ttk.LabelFrame(parent, text=_(key))

        frame.pack(
            fill=tk.X, side=tk.TOP if is_toplevel else tk.LEFT, pady=pady, padx=5, anchor=tk.NW if is_toplevel else tk.N
        )

        # Enhance tooltip for optional fields
        if is_optional and description:
            description += _("\nThis is optional and can be left blank")

        # Add tooltip based on schema description
        if description:
            show_tooltip(frame, description, position_below=False)

        if is_toplevel and key in self.data.get("Components", {}):
            self._add_template_controls(frame, key)

        for sub_key, sub_value in value.items():
            # recursively add child elements
            self._add_widget(frame, sub_key, sub_value, [*path, key])

    def __add_leaf_widget(self, parent: tk.Widget, key: str, value: float, path: list) -> None:
        entry_frame = ttk.Frame(parent)
        entry_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 5))

        description, is_optional = self.local_filesystem.get_component_property_description((*path, key))
        description = _(description) if description else ""

        label = ttk.Label(entry_frame, text=_(key), foreground="gray" if is_optional else "black")

        label.pack(side=tk.LEFT)

        entry = self.add_entry_or_combobox(value, entry_frame, (*path, key), is_optional)
        entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))

        # Store the entry widget in the entry_widgets dictionary for later retrieval
        self.entry_widgets[(*path, key)] = entry

        # Enhance tooltip for optional fields
        if is_optional and description:
            description += _("\nThis is optional and can be left blank")

        # Add tooltip based on schema description
        if description:
            show_tooltip(label, description)
            show_tooltip(entry, description)

    def _add_template_controls(self, parent_frame: ttk.LabelFrame, component_name: str) -> None:
        """Add template controls for a component."""
        self.template_manager.add_template_controls(parent_frame, component_name)

    def derive_initial_template_name(self, component_data: dict[str, Any]) -> str:  # pylint: disable=unused-argument # noqa: ARG002
        """
        Derive an initial template name from the component data.

        This is a basic implementation that can be overridden in derived classes
        to provide more specific template naming logic.
        """
        return ""

    def get_component_data_from_gui(self, component_name: str) -> dict[str, Any]:
        """Save the current component configuration as a template."""
        # Get fresh component data from the GUI elements instead of stored data
        component_data: dict[str, Any] = {}

        # Find all entry widgets belonging to this component and extract their values
        for path, entry in self.entry_widgets.items():
            if len(path) >= 1 and path[0] == component_name:
                # Get the current value from the entry widget
                value: Union[str, int, float] = entry.get()

                # Try to convert to appropriate type (int, float, or string)
                if path[-1] != "Version":
                    try:
                        value = int(value)
                    except ValueError:
                        try:
                            value = float(value)
                        except ValueError:
                            value = str(value).strip()

                # Create nested structure by navigating through the path
                current_level = component_data
                for key in path[1:-1]:  # Skip component_name and the last key
                    if key not in current_level:
                        current_level[key] = {}
                    current_level = current_level[key]

                # Set the value at the final level
                current_level[path[-1]] = value
        return component_data

    def validate_and_save_component_json(self) -> None:
        """Saves the edited JSON data back to the file."""
        confirm_message = _(
            "ArduPilot Methodic Configurator only operates correctly if all component properties are correct."
            " ArduPilot parameter values depend on the components used and their connections.\n\n"
            " Have you used the scrollbar on the right side of the window and "
            "entered the correct values for all components?"
        )
        user_confirmation = messagebox.askyesno(_("Confirm that all component properties are correct"), confirm_message)

        if not user_confirmation:
            # User chose 'No', so return and do not save data
            return

        self.save_component_json()

    def save_component_json(self) -> None:
        # User confirmed, proceed with saving the data
        for path, entry in self.entry_widgets.items():
            value: Union[str, int, float] = entry.get()
            # Navigate through the nested dictionaries using the elements of the path
            current_data = self.data["Components"]
            for key in path[:-1]:
                current_data = current_data[key]

            if path[-1] != "Version":
                try:
                    value = int(value)
                except ValueError:
                    try:
                        value = float(value)
                    except ValueError:
                        value = str(value).strip()

            # Update the value in the data dictionary
            current_data[path[-1]] = value

        # Save the updated data back to the JSON file
        failed, msg = self.local_filesystem.save_vehicle_components_json_data(self.data, self.local_filesystem.vehicle_dir)
        if failed:
            show_error_message(_("Error"), _("Failed to save data to file.") + "\n" + msg)
        else:
            logging_info(_("Vehicle component data saved successfully."))
        self.root.destroy()

    def on_closing(self) -> None:
        """Handle window closing event."""
        answer = messagebox.askyesnocancel(_("Save Changes?"), _("Do you want to save the changes before closing?"))

        if answer is None:  # Cancel was clicked
            return

        if answer:
            self.save_component_json()
        else:
            self.root.destroy()
        sys_exit(0)

    # This function will be overwritten in child classes
    def add_entry_or_combobox(
        self,
        value: float,
        entry_frame: ttk.Frame,
        _path: tuple[str, str, str],
        is_optional: bool = False,  # pylint: disable=unused-argument # noqa: ARG002
    ) -> Union[ttk.Entry, ttk.Combobox]:
        entry = ttk.Entry(entry_frame)
        entry.insert(0, str(value))
        return entry

    @staticmethod
    def add_argparse_arguments(parser: ArgumentParser) -> ArgumentParser:
        parser.add_argument(
            "--skip-component-editor",
            action="store_true",
            help=_(
                "Skip the component editor window. Only use this if all components have been configured. "
                "Default is %(default)s"
            ),
        )
        return parser


if __name__ == "__main__":
    args = argument_parser()

    logging_basicConfig(level=logging_getLevelName(args.loglevel), format="%(asctime)s - %(levelname)s - %(message)s")

    filesystem = LocalFilesystem(
        args.vehicle_dir, args.vehicle_type, "", args.allow_editing_template_files, args.save_component_to_system_templates
    )
    app = ComponentEditorWindowBase(__version__, filesystem)
    app.root.mainloop()
