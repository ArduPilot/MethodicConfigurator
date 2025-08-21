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
from platform import system as platform_system
from sys import exit as sys_exit
from tkinter import messagebox, ttk
from typing import Any, Optional, Union, cast
from unittest.mock import patch

from ardupilot_methodic_configurator import _, __version__
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.backend_filesystem_program_settings import ProgramSettings
from ardupilot_methodic_configurator.common_arguments import add_common_arguments
from ardupilot_methodic_configurator.data_model_vehicle_components import ComponentDataModel
from ardupilot_methodic_configurator.data_model_vehicle_components_base import ComponentData, ComponentPath, ComponentValue
from ardupilot_methodic_configurator.data_model_vehicle_components_json_schema import VehicleComponentsJsonSchema
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
VEHICLE_IMAGE_WIDTH_PIX = 100
VEHICLE_IMAGE_HEIGHT_PIX = 100


class ComponentEditorWindowBase(BaseWindow):  # pylint: disable=too-many-instance-attributes
    """
    A class for editing JSON files in the ArduPilot methodic configurator.

    This class provides a graphical user interface for editing JSON files that
    contain vehicle component configurations. It inherits from the BaseWindow
    class, which provides basic window functionality.
    """

    def __init__(
        self,
        version: str,
        local_filesystem: LocalFilesystem,
        data_model: Optional[ComponentDataModel] = None,
        root_tk: Optional[tk.Tk] = None,
    ) -> None:
        """
        Initialize the ComponentEditorWindowBase.

        Args:
            version: Application version string
            local_filesystem: Filesystem interface for loading/saving data
            data_model: Optional pre-configured data model (for testing)
            root_tk: Optional parent Tk window (for testing)

        """
        super().__init__(root_tk)
        self.local_filesystem = local_filesystem
        self.version = version

        # Initialize the data model - allow injection for testing
        self.data_model = data_model or self._create_data_model()

        # UI elements dictionary for easier access and testing
        self.entry_widgets: dict[ComponentPath, EntryWidget] = {}
        self.scroll_frame: ScrollFrame
        self.save_button: ttk.Button
        self.template_manager: ComponentTemplateManager
        self.complexity_var = tk.StringVar()

        # Initialize UI if there's data to work with
        if self._check_data():
            self._initialize_ui()
            self._finalize_initialization()

    def _create_data_model(self) -> ComponentDataModel:
        """Create the data model. Extracted for better testability."""
        raw_data = self.local_filesystem.load_vehicle_components_json_data(self.local_filesystem.vehicle_dir)
        schema = VehicleComponentsJsonSchema(self.local_filesystem.load_schema())
        component_datatypes = schema.get_all_value_datatypes()
        return ComponentDataModel(raw_data, component_datatypes, schema)

    def _initialize_ui(self) -> None:
        """Initialize the complete UI. Extracted for better testability."""
        self._setup_window()
        self._setup_styles()
        self._create_intro_frame()
        self._create_scroll_frame()
        self._setup_template_manager()
        self._create_save_frame()
        self._check_show_usage_instructions()

    def _finalize_initialization(self) -> None:
        """Finalize initialization after UI setup. Extracted for better testability."""
        self.data_model.post_init(self.local_filesystem.doc_dict)

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
        style.configure(
            "bigger.TLabel",  # type: ignore[no-untyped-call]
            font=("TkDefaultFont", self.calculate_scaled_font_size(self.default_font_size)),
        )
        style.configure("comb_input_invalid.TCombobox", fieldbackground="red")  # type: ignore[no-untyped-call]
        style.configure("comb_input_valid.TCombobox", fieldbackground="white")  # type: ignore[no-untyped-call]
        style.configure("entry_input_invalid.TEntry", fieldbackground="red")  # type: ignore[no-untyped-call]
        style.configure("entry_input_valid.TEntry", fieldbackground="white")  # type: ignore[no-untyped-call]
        style.configure("Optional.TLabelframe", borderwidth=2)  # type: ignore[no-untyped-call]
        style.configure("Optional.TLabelframe.Label", foreground="gray")  # type: ignore[no-untyped-call]

    def _create_intro_frame(self) -> None:
        """Create the introduction frame with explanations and image."""
        intro_frame = ttk.Frame(self.main_frame)
        intro_frame.pack(side=tk.TOP, fill="x", expand=False)

        # Add vehicle image first to the right side
        self._add_vehicle_image(intro_frame)

        # Add explanation text to the left side
        self._add_explanation_text(intro_frame)

    def _add_explanation_text(self, parent: ttk.Frame) -> None:
        """Add explanation text to the parent frame."""
        explanation_frame = ttk.Frame(parent)
        explanation_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 10), pady=(10, 0))

        # Add UI complexity combobox
        complexity_frame = ttk.Frame(explanation_frame)
        complexity_frame.pack(side=tk.TOP, anchor=tk.NW, padx=(0, 10))

        complexity_label = ttk.Label(complexity_frame, text=_("GUI Complexity:"))
        complexity_label.pack(side=tk.LEFT, padx=(0, 5))

        complexity_setting = ProgramSettings.get_setting("gui_complexity")
        self.complexity_var.set(str(complexity_setting) if complexity_setting is not None else "simple")

        complexity_combobox = ttk.Combobox(
            complexity_frame, textvariable=self.complexity_var, values=["simple", "normal"], state="readonly", width=10
        )
        complexity_combobox.pack(side=tk.LEFT)
        complexity_combobox.bind("<<ComboboxSelected>>", self._on_complexity_changed)

        # Add tooltip
        show_tooltip(
            complexity_combobox,
            _(
                "Select the graphical user interface complexity level:\n"
                "simple for beginners, only minimal mandatory fields no optional params displayed\n"
                "normal for everybody else."
            ),
        )

        explanation_text = _("Please configure properties of the vehicle components.\n")
        explanation_text += _("Labels for optional properties are displayed in gray text.\n")
        explanation_text += _("Scroll down to ensure that you do not overlook any properties.\n")

        explanation_label = ttk.Label(
            explanation_frame, text=explanation_text, wraplength=WINDOW_WIDTH_PIX - VEHICLE_IMAGE_WIDTH_PIX, justify=tk.LEFT
        )
        explanation_label.configure(style="bigger.TLabel")
        explanation_label.pack(side=tk.TOP, anchor=tk.NW, pady=self.calculate_scaled_padding_tuple(10, 0))

    def _on_complexity_changed(self, _event: Optional[tk.Event] = None) -> None:
        """Handle complexity combobox change."""
        old_gui_complexity = ProgramSettings.get_setting("gui_complexity")
        new_gui_complexity = self.complexity_var.get()
        if new_gui_complexity != old_gui_complexity:
            ProgramSettings.set_setting("gui_complexity", new_gui_complexity)
            self._refresh_component_display()

    def _refresh_component_display(self) -> None:
        """Refresh the component display UI."""
        # Clear all widgets from the scroll frame
        for widget in self.scroll_frame.view_port.winfo_children():
            widget.destroy()

        # Clear the entry_widgets dictionary since all widgets have been destroyed
        self.entry_widgets.clear()

        # Repopulate the frame with widgets according to the new complexity setting
        self.populate_frames()

        # Update the UI
        self.scroll_frame.view_port.update_idletasks()

    def _add_vehicle_image(self, parent: ttk.Frame) -> None:
        """Add the vehicle image to the parent frame."""
        if self.local_filesystem.vehicle_image_exists():
            image_label = self.put_image_in_label(
                parent, self.local_filesystem.vehicle_image_filepath(), VEHICLE_IMAGE_HEIGHT_PIX
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

        self.save_button = ttk.Button(save_frame, text=_("Save data and start configuration"), command=self.on_save_pressed)
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
        # pylint: disable=duplicate-code
        usage_popup_window = BaseWindow(parent)
        style = ttk.Style()

        instructions_text = RichText(
            usage_popup_window.main_frame,
            wrap=tk.WORD,
            height=5,
            bd=0,
            background=style.lookup("TLabel", "background"),  # type: ignore[no-untyped-call]
        )
        # pylint: enable=duplicate-code
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

    def set_component_value_and_update_ui(self, path: ComponentPath, value: str) -> None:
        """Set a component value and update the UI to reflect it."""
        self._set_component_value(path, value)
        self._update_widget_value(path, value)

    def _set_component_value(self, path: ComponentPath, value: str) -> None:
        """Set component value in data model."""
        self.data_model.set_component_value(path, value)

    def set_vehicle_configuration_template(self, configuration_template: str) -> None:
        """Set the configuration template name in the data."""
        self.data_model.set_configuration_template(configuration_template)

    def set_values_from_fc_parameters(self, fc_parameters: dict[str, Any], doc: dict[str, Any]) -> None:
        """
        Process flight controller parameters and update the data model.

        This delegates to the data model's process_fc_parameters method to handle
        all the business logic of processing parameters.
        """
        # Delegate to the data model for parameter processing
        self.data_model.process_fc_parameters(fc_parameters, doc)

    def _update_widget_value(self, path: ComponentPath, value: str) -> None:
        """Update widget value in UI."""
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
        # Scroll to the top after (re-)populating
        self.scroll_frame.canvas.yview("moveto", 0)

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
        # Skip components that shouldn't be displayed in simple mode
        if isinstance(value, dict) and not self.data_model.should_display_in_simple_mode(
            key, value, path, self.complexity_var.get()
        ):
            return

        # For leaf nodes in simple mode, check if they are optional
        if not isinstance(value, dict) and not self.data_model.should_display_leaf_in_simple_mode(
            (*path, key), self.complexity_var.get()
        ):
            return

        if isinstance(value, dict):  # JSON non-leaf elements, add LabelFrame widget
            self._add_non_leaf_widget(parent, key, value, path)
        else:  # JSON leaf elements, add Entry widget
            self._add_leaf_widget(parent, key, value, path)

    def _prepare_non_leaf_widget_config(self, key: str, value: dict, path: list[str]) -> dict:
        """Prepare configuration for non-leaf widget creation. Delegates to display logic."""
        return self.data_model.prepare_non_leaf_widget_config(key, value, path)

    def _create_non_leaf_widget_ui(self, parent: tk.Widget, config: dict) -> ttk.LabelFrame:
        """Create the UI elements for a non-leaf widget. Separated for better testability."""
        if config["is_optional"]:
            frame = ttk.LabelFrame(parent, text=_(config["key"]), style="Optional.TLabelframe")
        else:
            frame = ttk.LabelFrame(parent, text=_(config["key"]))

        frame.pack(
            fill=tk.X,
            side=tk.TOP if config["is_toplevel"] else tk.LEFT,
            pady=5 if config["is_toplevel"] else 3,
            padx=5,
            anchor=tk.NW if config["is_toplevel"] else tk.N,
        )

        # Add tooltip based on schema description
        if config["description"]:
            show_tooltip(frame, config["description"], position_below=False)

        return frame

    def _add_non_leaf_widget(self, parent: tk.Widget, key: str, value: dict, path: list[str]) -> None:
        """Add a non-leaf widget (frame containing other widgets) to the UI."""
        # Extract business logic to separate method for better testability
        widget_config = self._prepare_non_leaf_widget_config(key, value, path)
        frame = self._create_non_leaf_widget_ui(parent, widget_config)

        if widget_config["is_toplevel"] and key in self.data_model.get_all_components():
            self._add_template_controls(frame, key)

        for sub_key, sub_value in value.items():
            # recursively add child elements
            self._add_widget(frame, sub_key, sub_value, [*path, key])

    def _add_leaf_widget(self, parent: tk.Widget, key: str, value: Union[str, float], path: list[str]) -> None:
        """Add a leaf widget (containing input controls) to the UI."""
        # Extract business logic to separate method for better testability
        widget_config = self._prepare_leaf_widget_config(key, value, path)
        self._create_leaf_widget_ui(parent, widget_config)

    def _prepare_leaf_widget_config(self, key: str, value: Union[str, float], path: list[str]) -> dict:
        """Prepare configuration for leaf widget creation. Delegates to display logic."""
        return self.data_model.prepare_leaf_widget_config(key, value, path)

    def _create_leaf_widget_ui(self, parent: tk.Widget, config: dict) -> None:
        """Create the UI elements for a leaf widget. Separated for better testability."""
        entry_frame = ttk.Frame(parent)
        entry_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 5))

        label = ttk.Label(entry_frame, text=_(config["key"]), foreground="gray" if config["is_optional"] else "black")
        label.pack(side=tk.LEFT)

        entry = self.add_entry_or_combobox(config["value"], entry_frame, config["path"], config["is_optional"])
        entry.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))

        # Store the entry widget in the entry_widgets Dictionary for later retrieval
        self.entry_widgets[config["path"]] = entry

        # Add tooltip based on schema description
        if config["description"]:
            show_tooltip(label, config["description"])
            show_tooltip(entry, config["description"])

    def _add_template_controls(self, parent_frame: ttk.LabelFrame, component_name: str) -> None:
        """Add template controls for a component."""
        if self.complexity_var.get() != "simple":
            self.template_manager.add_template_controls(parent_frame, component_name)

    def get_component_data_from_gui(self, component_name: str) -> ComponentData:
        """Extract component data from GUI elements."""
        # Get all entry widget values as a dictionary
        entry_values = {path: entry.get() for path, entry in self.entry_widgets.items()}

        # Use the data model to extract and process the component data
        return self.data_model.extract_component_data_from_entries(component_name, entry_values)

    def validate_data_and_highlight_errors_in_red(self) -> str:
        """Validate all data using the data model."""
        # Collect all entry values
        entry_values = {
            path: entry.get() for path, entry in self.entry_widgets.items() if isinstance(entry, (ttk.Entry, ttk.Combobox))
        }

        # Use data model for validation
        is_valid, errors = self.data_model.validate_all_data(entry_values)

        if not is_valid:
            # Update UI to show invalid states and display errors
            for path, entry in (
                (path, entry) for path, entry in self.entry_widgets.items() if isinstance(entry, (ttk.Entry, ttk.Combobox))
            ):
                value = entry.get()

                # Check combobox validation
                if isinstance(entry, ttk.Combobox):
                    combobox_values = self.data_model.get_combobox_values_for_path(path)
                    if combobox_values and value not in combobox_values:
                        entry.configure(style="comb_input_invalid.TCombobox")
                    else:
                        entry.configure(style="comb_input_valid.TCombobox")
                else:
                    # Check entry validation
                    error_message, _corr = self.data_model.validate_entry_limits(value, path)
                    if error_message:
                        entry.configure(style="entry_input_invalid.TEntry")
                    else:
                        entry.configure(style="entry_input_valid.TEntry")

            # Show first few errors
            error_message = "\n".join(errors[:3])  # Show first 3 errors
            if len(errors) > 3:
                error_message += f"\n... and {len(errors) - 3} more errors"
            show_error_message(_("Validation Errors"), error_message)
            return _("Validation failed. Please correct the errors before saving.")

        return ""

    def on_save_pressed(self) -> None:
        """Validate component data, save the component JSON file and close the window."""
        error_msg = self.validate_data_and_highlight_errors_in_red()
        if error_msg:
            show_error_message(_("Error"), error_msg)
            return
        if self._confirm_component_properties():
            self.save_component_json()
        self.root.destroy()

    def _confirm_component_properties(self) -> bool:
        """Show confirmation dialog for component properties."""
        confirm_message = _(
            "ArduPilot Methodic Configurator only operates correctly if all component properties are correct."
            " ArduPilot parameter values depend on the components used and their connections.\n\n"
            " Have you used the scrollbar on the right side of the window and "
            "entered the correct values for all components?"
        )
        return messagebox.askyesno(_("Confirm that all component properties are correct"), confirm_message)

    def save_component_json(self) -> bool:
        """Save component JSON data to file."""
        try:
            save_result = self._perform_file_save()
        except Exception as exc:  # pylint: disable=broad-except # Catch unexpected exceptions and present them as a save error
            # Convert exception into the expected save_result shape: (is_error: bool, message: str)
            save_result = (True, str(exc))
        return self._handle_save_result(save_result)

    def _perform_file_save(self) -> tuple[bool, str]:
        """Perform file save operation."""
        return self.data_model.save_to_filesystem(self.local_filesystem)

    def _handle_save_result(self, save_result: tuple[bool, str]) -> bool:
        """Handle save operation result."""
        if save_result[0]:
            show_error_message(_("Error"), _("Failed to save data to file.") + "\n" + save_result[1])
            ret = True
        else:
            logging_info(_("Vehicle component data saved successfully."))
            ret = False

        return ret

    def on_closing(self) -> None:
        """Handle window closing event."""
        answer = messagebox.askyesnocancel(_("Save Changes?"), _("Do you want to save the changes before closing?"))

        if answer is None:  # Cancel was clicked
            return

        ret = False
        if answer:
            ret = self.save_component_json()
        else:
            # If it just created the files from a new template and the user chooses not to save,
            # delete the created files
            if self.data_model.is_new_project():
                # remove the files created
                err_msg = self.local_filesystem.remove_created_files_and_vehicle_dir()
                if err_msg:
                    show_error_message(_("Error"), err_msg)
                ret = bool(err_msg)
            logging_info(_("Changes discarded. No data saved."))
        # Close the window and exit. ret indicates if there was an error earlier (e.g. cleanup failed).
        self.root.destroy()
        sys_exit(int(ret))

    # This function will be overwritten in child classes
    def add_entry_or_combobox(
        self,
        value: Union[str, float],
        entry_frame: ttk.Frame,
        _path: ComponentPath,
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

    @classmethod
    def create_for_testing(
        cls,
        version: str = "test",
        local_filesystem: Optional[LocalFilesystem] = None,
        data_model: Optional[ComponentDataModel] = None,
        root_tk: Optional[tk.Tk] = None,  # pylint: disable=unused-argument # noqa: ARG003
    ) -> "ComponentEditorWindowBase":
        """
        Factory method for creating instances suitable for testing.

        This method provides a convenient way to create instances with minimal
        dependencies for testing purposes.

        Args:
            version: Application version string
            local_filesystem: Optional filesystem interface
            data_model: Optional pre-configured data model
            root_tk: Optional parent Tk window

        Returns:
            ComponentEditorWindowBase instance configured for testing

        """
        # Import MagicMock at the method level to avoid import issues
        from unittest.mock import MagicMock  # pylint: disable=import-outside-toplevel # noqa: PLC0415

        if local_filesystem is None:
            # Create a minimal mock filesystem for testing
            local_filesystem = MagicMock(spec=LocalFilesystem)
            local_filesystem.vehicle_dir = "test_vehicle"
            local_filesystem.doc_dict = {}
            local_filesystem.load_vehicle_components_json_data.return_value = {}
            local_filesystem.load_schema.return_value = {}

        # Patch the BaseWindow initialization to avoid Tkinter dependencies
        with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor_base.BaseWindow.__init__"):
            instance = cls.__new__(cls)

            # Manually initialize the essential attributes without calling BaseWindow.__init__
            instance.local_filesystem = local_filesystem
            instance.version = version

            # Create mock UI elements to avoid Tkinter dependencies
            instance.root = MagicMock()
            instance.main_frame = MagicMock()

            # Initialize the data model - allow injection for testing
            instance.data_model = data_model or instance._create_data_model()  # noqa: SLF001

            # Initialize UI elements dictionary for easier access and testing
            instance.entry_widgets = {}
            instance.scroll_frame = MagicMock()
            instance.save_button = MagicMock()
            instance.template_manager = MagicMock()
            instance.complexity_var = MagicMock()
            instance.default_font_size = 9 if platform_system() == "Windows" else -12

            return instance


if __name__ == "__main__":
    args = argument_parser()

    logging_basicConfig(level=logging_getLevelName(args.loglevel), format="%(asctime)s - %(levelname)s - %(message)s")

    filesystem = LocalFilesystem(
        args.vehicle_dir, args.vehicle_type, "", args.allow_editing_template_files, args.save_component_to_system_templates
    )
    component_editor_window = ComponentEditorWindowBase(__version__, filesystem)

    component_editor_window.populate_frames()
    if args.skip_component_editor:
        component_editor_window.root.after(10, component_editor_window.root.destroy)

    # component_editor_window.validate_data()

    component_editor_window.root.mainloop()
