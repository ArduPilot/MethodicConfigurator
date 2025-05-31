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
from typing import Any, Union, cast

from ardupilot_methodic_configurator import _, __version__
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.common_arguments import add_common_arguments
from ardupilot_methodic_configurator.data_model_vehicle_components import (
    ComponentDataModel,
    ComponentPath,
    ComponentValue,
    ValidationRulePath,
)
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


# Type aliases to improve code readability
EntryWidget = Union[ttk.Entry, ttk.Combobox]

WINDOW_WIDTH_PIX = 880
VEICLE_IMAGE_WIDTH_PIX = 100


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
        self.version = version

        # Initialize the data model
        raw_data = local_filesystem.load_vehicle_components_json_data(local_filesystem.vehicle_dir)
        self.data_model = ComponentDataModel(raw_data)

        # UI elements dictionary for easier access and testing
        self.entry_widgets: dict[ComponentPath, EntryWidget] = {}
        self.scroll_frame: ScrollFrame
        self.save_button: ttk.Button
        self.template_manager: ComponentTemplateManager

        # Initialize UI if there's data to work with
        if self._check_data():
            self._setup_window()
            self._setup_styles()
            self._create_intro_frame()
            self._create_scroll_frame()
            self._setup_template_manager()
            self._update_data_structure()
            self._create_save_frame()
            self._check_show_usage_instructions()
            # Populate the UI with data
            self.populate_frames()

    def _check_data(self) -> bool:
        """Check if we have data to work with and prepare for UI setup."""
        if not self.data_model.is_valid_component_data() or not self.data_model.has_components():
            # Schedule the window to be destroyed after the mainloop has started
            self.root.after(100, self.root.destroy)
            return False
        return True

    def _setup_window(self) -> None:
        """Setup the main window properties."""
        self.root.title(
            _("Amilcar Lucas's - ArduPilot methodic configurator ") + self.version + _(" - Vehicle Component Editor")
        )
        self.root.geometry(f"{WINDOW_WIDTH_PIX}x600")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _setup_styles(self) -> None:
        """Configure the styles for UI elements."""
        style = ttk.Style()
        style.configure("bigger.TLabel", font=("TkDefaultFont", 13))
        style.configure("comb_input_invalid.TCombobox", fieldbackground="red")
        style.configure("comb_input_valid.TCombobox", fieldbackground="white")
        style.configure("entry_input_invalid.TEntry", fieldbackground="red")
        style.configure("entry_input_valid.TEntry", fieldbackground="white")
        style.configure("Optional.TLabelframe", borderwidth=2)
        style.configure("Optional.TLabelframe.Label", foreground="gray")

    def _create_intro_frame(self) -> None:
        """Create the introduction frame with explanations and image."""
        intro_frame = ttk.Frame(self.main_frame)
        intro_frame.pack(side=tk.TOP, fill="x", expand=False)

        self._add_explanation_text(intro_frame)
        self._add_vehicle_image(intro_frame)

    def _add_explanation_text(self, parent: ttk.Frame) -> None:
        """Add explanation text to the parent frame."""
        explanation_text = _("Please configure properties of the vehicle components.\n")
        explanation_text += _("Labels for optional properties are displayed in gray text.\n")
        explanation_text += _("Scroll down to ensure that you do not overlook any properties.\n")

        explanation_label = ttk.Label(
            parent, text=explanation_text, wraplength=WINDOW_WIDTH_PIX - VEICLE_IMAGE_WIDTH_PIX, justify=tk.LEFT
        )
        explanation_label.configure(style="bigger.TLabel")
        explanation_label.pack(side=tk.LEFT, padx=(10, 10), pady=(10, 0), anchor=tk.NW)

    def _add_vehicle_image(self, parent: ttk.Frame) -> None:
        """Add the vehicle image to the parent frame."""
        if self.local_filesystem.vehicle_image_exists():
            image_label = self.put_image_in_label(
                parent, self.local_filesystem.vehicle_image_filepath(), VEICLE_IMAGE_WIDTH_PIX
            )
            image_label.pack(side=tk.RIGHT, anchor=tk.NE, padx=(4, 4), pady=(4, 0))
            show_tooltip(image_label, _("Replace the vehicle.jpg file in the vehicle directory to change the vehicle image."))
        else:
            image_label = ttk.Label(parent, text=_("Add a 'vehicle.jpg' image file to the vehicle directory."))
            image_label.pack(side=tk.RIGHT, anchor=tk.NE, padx=(4, 4), pady=(4, 0))

    def _create_scroll_frame(self) -> None:
        """Create the scrollable frame for component widgets."""
        self.scroll_frame = ScrollFrame(self.main_frame)
        self.scroll_frame.pack(side="top", fill="both", expand=True)

    def _create_save_frame(self) -> None:
        """Create the frame with save button."""
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

    def _setup_template_manager(self) -> None:
        """Set up the component template manager."""

        def update_data_callback(comp_name: str, template_data: dict) -> None:
            self.data_model.update_component(comp_name, template_data)

        self.template_manager = ComponentTemplateManager(
            self.root,
            self.entry_widgets,
            self.get_component_data_from_gui,
            update_data_callback,
            self.data_model.derive_initial_template_name,
            self.local_filesystem.save_component_to_system_templates,
        )

    def _check_show_usage_instructions(self) -> None:
        """Check if usage instructions should be displayed."""
        if UsagePopupWindow.should_display("component_editor"):
            # Cast to Tk since we know root is a Tk instance in this context
            self.root.after(10, lambda: self._display_component_editor_usage_instructions(cast("tk.Tk", self.root)))

    def _display_component_editor_usage_instructions(self, parent: tk.Tk) -> None:
        """Display usage instructions for the component editor."""
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

    def _update_data_structure(self) -> None:
        """Update the data structure to ensure all required fields are present."""
        # Ensure format version is set
        self.data_model.ensure_format_version()
        # Let the data model handle the structure update
        self.data_model.update_json_structure()

    def set_component_value_and_update_ui(self, path: ComponentPath, value: str) -> None:
        """Set a component value and update the UI to reflect it."""
        self.data_model.set_component_value(path, value)
        if path in self.entry_widgets:
            entry = self.entry_widgets[path]
            entry.delete(0, tk.END)
            entry.insert(0, value)
            entry.config(state="disabled")

    def populate_frames(self) -> None:
        """Populates the ScrollFrame with widgets based on the JSON data."""
        components = self.data_model.get_all_components()
        for key, value in components.items():
            self.add_widget(self.scroll_frame.view_port, key, value, [])

    def add_widget(self, parent: tk.Widget, key: str, value: ComponentValue, path: list[str]) -> None:
        """
        Adds a widget to the parent widget with the given key and value.

        Public version for better testability.
        """
        self._add_widget(parent, key, value, path)

    def _add_widget(self, parent: tk.Widget, key: str, value: ComponentValue, path: list[str]) -> None:
        """
        Adds a widget to the parent widget with the given key and value.

        Args:
            parent (tkinter.Widget): The parent widget to which the LabelFrame/Entry will be added.
            key (str): The key for the LabelFrame/Entry.
            value (dict|float): The value associated with the key.
            path (list): The path to the current key in the JSON data.

        """
        if isinstance(value, dict):  # JSON non-leaf elements, add LabelFrame widget
            self._add_non_leaf_widget(parent, key, value, path)
        else:  # JSON leaf elements, add Entry widget
            self._add_leaf_widget(parent, key, value, path)

    def _add_non_leaf_widget(self, parent: tk.Widget, key: str, value: dict, path: list[str]) -> None:
        """Add a non-leaf widget (frame containing other widgets) to the UI."""
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

        if is_toplevel and key in self.data_model.get_all_components():
            self._add_template_controls(frame, key)

        for sub_key, sub_value in value.items():
            # recursively add child elements
            self._add_widget(frame, sub_key, sub_value, [*path, key])

    def _add_leaf_widget(self, parent: tk.Widget, key: str, value: Union[str, float], path: list[str]) -> None:
        """Add a leaf widget (containing input controls) to the UI."""
        entry_frame = ttk.Frame(parent)
        entry_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 5))

        description, is_optional = self.local_filesystem.get_component_property_description((*path, key))
        description = _(description) if description else ""

        label = ttk.Label(entry_frame, text=_(key), foreground="gray" if is_optional else "black")
        label.pack(side=tk.LEFT)

        entry = self.add_entry_or_combobox(value, entry_frame, (*path, key), is_optional)  # type: ignore[arg-type]
        entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))

        # Store the entry widget in the entry_widgets Dictionary for later retrieval
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

    def get_component_data_from_gui(self, component_name: str) -> dict[str, Any]:
        """Extract component data from GUI elements."""
        # Get all entry widget values as a dictionary
        entry_values = {path: entry.get() for path, entry in self.entry_widgets.items()}

        # Use the data model to extract and process the component data
        return self.data_model.extract_component_data_from_entries(component_name, entry_values)

    def validate_and_save_component_json(self) -> None:
        """Validate and save the component JSON data."""
        if self._confirm_component_properties():
            self.save_component_json()

    def _confirm_component_properties(self) -> bool:
        """Show confirmation dialog for component properties."""
        confirm_message = _(
            "ArduPilot Methodic Configurator only operates correctly if all component properties are correct."
            " ArduPilot parameter values depend on the components used and their connections.\n\n"
            " Have you used the scrollbar on the right side of the window and "
            "entered the correct values for all components?"
        )
        return messagebox.askyesno(_("Confirm that all component properties are correct"), confirm_message)

    def save_component_json(self) -> None:
        """Save component JSON data to file."""
        # Collect all entry values
        entry_values = {path: entry.get() for path, entry in self.entry_widgets.items()}

        # Use data model to save (which handles validation and data processing)
        failed, msg = self.data_model.save_to_filesystem(self.local_filesystem, entry_values)

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
        value: Union[str, float],
        entry_frame: ttk.Frame,
        _path: ValidationRulePath,
        is_optional: bool = False,  # pylint: disable=unused-argument # noqa: ARG002
    ) -> EntryWidget:
        """Create an entry widget for input values."""
        entry = ttk.Entry(entry_frame)
        entry.insert(0, str(value))
        return entry

    @staticmethod
    def add_argparse_arguments(parser: ArgumentParser) -> ArgumentParser:
        """Add component editor specific arguments to the parser."""
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
