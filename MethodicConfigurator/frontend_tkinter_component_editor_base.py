#!/usr/bin/env python3

"""
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from argparse import ArgumentParser
from logging import basicConfig as logging_basicConfig
from logging import getLevelName as logging_getLevelName

# from logging import debug as logging_debug
from logging import info as logging_info
from tkinter import messagebox, ttk
from typing import Union

from MethodicConfigurator import _, __version__
from MethodicConfigurator.backend_filesystem import LocalFilesystem
from MethodicConfigurator.common_arguments import add_common_arguments_and_parse
from MethodicConfigurator.frontend_tkinter_base import (
    BaseWindow,
    RichText,
    ScrollFrame,
    UsagePopupWindow,
    show_error_message,
    show_tooltip,
)


def argument_parser():
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
    return add_common_arguments_and_parse(parser)
    # pylint: enable=duplicate-code


class ComponentEditorWindowBase(BaseWindow):
    """
    A class for editing JSON files in the ArduPilot methodic configurator.

    This class provides a graphical user interface for editing JSON files that
    contain vehicle component configurations. It inherits from the BaseWindow
    class, which provides basic window functionality.
    """

    def __init__(self, version, local_filesystem: LocalFilesystem):
        super().__init__()
        self.local_filesystem = local_filesystem

        self.root.title(_("Amilcar Lucas's - ArduPilot methodic configurator ") + version + _(" - Vehicle Component Editor"))
        self.root.geometry("880x600")  # Set the window width

        self.data = local_filesystem.load_vehicle_components_json_data(local_filesystem.vehicle_dir)
        if len(self.data) < 1:
            # Schedule the window to be destroyed after the mainloop has started
            self.root.after(100, self.root.destroy)  # Adjust the delay as needed
            return

        self.entry_widgets: dict[tuple, Union[ttk.Entry, ttk.Combobox]] = {}

        intro_frame = ttk.Frame(self.main_frame)
        intro_frame.pack(side=tk.TOP, fill="x", expand=False)

        style = ttk.Style()
        style.configure("bigger.TLabel", font=("TkDefaultFont", 14))
        style.configure("comb_input_invalid.TCombobox", fieldbackground="red")
        style.configure("comb_input_valid.TCombobox", fieldbackground="white")
        style.configure("entry_input_invalid.TEntry", fieldbackground="red")
        style.configure("entry_input_valid.TEntry", fieldbackground="white")

        explanation_text = _("Please configure all vehicle component properties in this window.\n")
        explanation_text += _("Scroll down and make sure you do not miss a property.\n")
        explanation_text += _("Saving the result will write to the vehicle_components.json file.")
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
        self.save_button = ttk.Button(save_frame, text=_("Save data and start configuration"), command=self.save_data)
        show_tooltip(self.save_button, _("Save component data and start parameter value configuration and tuning."))
        self.save_button.pack(pady=7)
        if UsagePopupWindow.should_display("component_editor"):
            self.root.after(10, self.__display_component_editor_usage_instructions(self.root))

    @staticmethod
    def __display_component_editor_usage_instructions(parent: tk.Toplevel):
        usage_popup_window = BaseWindow(parent)
        style = ttk.Style()

        instructions_text = RichText(
            usage_popup_window.main_frame, wrap=tk.WORD, height=5, bd=0, background=style.lookup("TLabel", "background")
        )
        instructions_text.insert(tk.END, _("1. Describe all vehicle component properties in the window below\n"))
        instructions_text.insert(tk.END, _("2. Scroll all the way down and make sure to edit all properties\n"))
        instructions_text.insert(tk.END, _("3. Do not be lazy, collect the required information and enter it\n"))
        instructions_text.insert(tk.END, _("4. Press the "))
        instructions_text.insert(tk.END, _("Save data and start configuration"), "italic")
        instructions_text.insert(tk.END, _(" only after all information is correct"))
        instructions_text.config(state=tk.DISABLED)

        UsagePopupWindow.display(
            parent,
            usage_popup_window,
            _("How to use the component editor window"),
            "component_editor",
            "690x200",
            instructions_text,
        )

    def update_json_data(self):  # should be overwritten in child classes
        if "Format version" not in self.data:
            self.data["Format version"] = 1

    def _set_component_value_and_update_ui(self, path: tuple, value: str):
        data_path = self.data["Components"]
        for key in path[:-1]:
            data_path = data_path[key]
        data_path[path[-1]] = value
        entry = self.entry_widgets[path]
        entry.delete(0, tk.END)
        entry.insert(0, value)
        entry.config(state="disabled")

    def populate_frames(self):
        """
        Populates the ScrollFrame with widgets based on the JSON data.
        """
        if "Components" in self.data:
            for key, value in self.data["Components"].items():
                self.__add_widget(self.scroll_frame.view_port, key, value, [])

    def __add_widget(self, parent, key, value, path):
        """
        Adds a widget to the parent widget with the given key and value.

        Parameters:
        parent (tkinter.Widget): The parent widget to which the LabelFrame/Entry will be added.
        key (str): The key for the LabelFrame/Entry.
        value (dict): The value associated with the key.
        path (list): The path to the current key in the JSON data.
        """
        if isinstance(value, dict):  # JSON non-leaf elements, add LabelFrame widget
            frame = ttk.LabelFrame(parent, text=_(key))
            is_toplevel = parent == self.scroll_frame.view_port
            pady = 5 if is_toplevel else 3
            frame.pack(
                fill=tk.X, side=tk.TOP if is_toplevel else tk.LEFT, pady=pady, padx=5, anchor=tk.NW if is_toplevel else tk.N
            )
            for sub_key, sub_value in value.items():
                # recursively add child elements
                self.__add_widget(frame, sub_key, sub_value, [*path, key])
        else:  # JSON leaf elements, add Entry widget
            entry_frame = ttk.Frame(parent)
            entry_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 5))

            label = ttk.Label(entry_frame, text=_(key))
            label.pack(side=tk.LEFT)

            entry = self.add_entry_or_combobox(value, entry_frame, tuple([*path, key]))
            entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))

            # Store the entry widget in the entry_widgets dictionary for later retrieval
            self.entry_widgets[tuple([*path, key])] = entry

    def save_data(self):
        """
        Saves the edited JSON data back to the file.
        """
        confirm_message = _(
            "ArduPilot Methodic Configurator only operates correctly if all component properties are correct."
            " ArduPilot parameter values depend on the components used and their connections."
            " Have you used the scrollbar on the right side of the window and "
            "entered the correct values for all components?"
        )
        user_confirmation = messagebox.askyesno(_("Confirm that all component properties are correct"), confirm_message)

        if not user_confirmation:
            # User chose 'No', so return and do not save data
            return

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
                        value = str(value)

            # Update the value in the data dictionary
            current_data[path[-1]] = value

        # Save the updated data back to the JSON file
        if self.local_filesystem.save_vehicle_components_json_data(self.data, self.local_filesystem.vehicle_dir):
            show_error_message(_("Error"), _("Failed to save data to file. Is the destination write protected?"))
        else:
            logging_info(_("Vehicle component data saved successfully."))
        self.root.destroy()

    # This function will be overwritten in child classes
    def add_entry_or_combobox(self, value, entry_frame, _path) -> Union[ttk.Entry, ttk.Combobox]:
        entry = ttk.Entry(entry_frame)
        entry.insert(0, str(value))
        return entry

    @staticmethod
    def add_argparse_arguments(parser):
        parser.add_argument(
            "--skip-component-editor",
            action="store_true",
            help=_(
                "Skip the component editor window. Only use this if all components have been configured. "
                "Defaults to %(default)s"
            ),
        )
        return parser


if __name__ == "__main__":
    args = argument_parser()

    logging_basicConfig(level=logging_getLevelName(args.loglevel), format="%(asctime)s - %(levelname)s - %(message)s")

    filesystem = LocalFilesystem(args.vehicle_dir, args.vehicle_type, "", args.allow_editing_template_files)
    app = ComponentEditorWindowBase(__version__, filesystem)
    app.root.mainloop()
