"""
Component template manager for the ArduPilot methodic configurator.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>, 2025 Francisco Fonseca

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from collections.abc import Callable as CollectionsCallable
from tkinter import Menu, messagebox, simpledialog, ttk
from typing import Any, TypeVar, Union

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_filesystem_vehicle_components import VehicleComponents
from ardupilot_methodic_configurator.frontend_tkinter_show import show_tooltip

T = TypeVar("T")


class ComponentTemplateManager:  # pylint: disable=too-many-instance-attributes
    """Manages component templates for the ArduPilot methodic configurator."""

    def __init__(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        root: Union[tk.Tk, tk.Toplevel],
        entry_widgets: dict[tuple, Union[ttk.Entry, ttk.Combobox]],
        get_component_data_callback: CollectionsCallable[[str], dict[str, Any]],
        update_data_callback: CollectionsCallable[[str, dict[str, Any]], None],
        derive_template_name_callback: CollectionsCallable[[dict[str, Any]], str],
        save_component_to_system_templates: bool = False,
    ) -> None:
        """
        Initialize the ComponentTemplateManager.

        Args:
            root: The root Tkinter window or toplevel widget
            entry_widgets: Dictionary mapping component paths to entry widgets
            get_component_data_callback: Callback to get component data
            update_data_callback: Callback to update data when applying template
            derive_template_name_callback: Callback to derive an initial template name from component
            save_component_to_system_templates: Boolean save the component to the system file instead of the user file

        """
        self.root = root
        self.entry_widgets = entry_widgets
        self.buttons: dict[str, ttk.Button] = {}
        self.current_menu: Union[Menu, None] = None
        self.template_manager = VehicleComponents(save_component_to_system_templates)
        self.get_component_data_callback = get_component_data_callback
        self.update_data_callback = update_data_callback
        self.derive_template_name_callback = derive_template_name_callback

    def add_template_controls(self, parent_frame: ttk.LabelFrame, component_name: str) -> None:
        """Add "template dropdown" and "save" buttons for a component."""
        label_frame = ttk.Frame(parent_frame)
        label_frame.pack(side=tk.TOP, fill=tk.X)

        label = ttk.Label(label_frame, text=_("Template:"))
        label.pack(side=tk.LEFT, padx=(5, 5))

        # Create and add the template dropdown button
        def show_template_for_component() -> None:
            self.show_template_options(component_name)

        dropdown_button = ttk.Button(label_frame, text="▼", width=2, command=show_template_for_component)
        show_tooltip(dropdown_button, _("Select a template for this component"))
        dropdown_button.pack(side=tk.LEFT)

        # Create and add the save template button
        def save_as_template() -> None:
            self.save_component_as_template(component_name)

        save_button = ttk.Button(label_frame, text="+", width=2, command=save_as_template)
        show_tooltip(save_button, _("Save current configuration as template"))
        save_button.pack(side=tk.LEFT, padx=(5, 0))

        # Store the dropdown button reference
        self.buttons[component_name] = dropdown_button

    def save_component_as_template(self, component_name: str) -> None:
        """Save the current component configuration as a template."""
        component_data = self.get_component_data_callback(component_name)
        if not component_data:
            messagebox.showerror(_("Error"), _("No data for component: ") + component_name)
            return

        initial_template_name = self.derive_initial_template_name(component_data)
        template_name = simpledialog.askstring(
            _("Save Template"), _("Enter a name for this template:"), parent=self.root, initialvalue=initial_template_name
        )
        if not template_name:
            return

        templates = self.template_manager.load_component_templates()
        if component_name not in templates:
            templates[component_name] = []

        new_template = {"name": template_name, "data": component_data, "is_user_modified": True}

        for i, template in enumerate(templates[component_name]):
            if template.get("name") == template_name:
                confirm = messagebox.askyesno(_("Template exists"), _("A template with this name already exists. Overwrite?"))
                if confirm:
                    templates[component_name][i] = new_template
                    self.template_manager.save_component_templates(templates)
                    messagebox.showinfo(_("Template Saved"), _("Template has been updated"))
                return

        templates[component_name].append(new_template)
        self.template_manager.save_component_templates(templates)
        messagebox.showinfo(_("Template Saved"), _("Template has been saved"))

    def derive_initial_template_name(self, component_data: dict[str, Any]) -> str:
        """Derive an initial template name from the component data."""
        return self.derive_template_name_callback(component_data)

    def create_template_dropdown_button(self, parent: ttk.Frame, component_name: str) -> ttk.Button:
        """Creates a dropdown button for component templates."""
        button = ttk.Button(parent, text="▼", width=2, command=lambda: self.show_template_options(component_name))
        show_tooltip(button, _("Select a template for this component"))
        return button

    def show_template_options(self, component_name: str) -> None:
        """Shows a dropdown menu with template options for the component."""
        if isinstance(self.current_menu, Menu):
            self.current_menu.unpost()

        button = self.buttons.get(component_name)
        if not button:
            return

        templates = self.template_manager.load_component_templates()
        component_templates = templates.get(component_name, [])
        component_templates = sorted(component_templates, key=lambda x: x.get("name", "").lower())

        menu = Menu(self.root, tearoff=0)

        if component_templates:
            for template in component_templates:
                template_name = template.get("name", "Template")

                # Create a command function with proper closure
                command_function = self._create_template_apply_function(component_name, template)

                menu.add_command(label=template_name, command=command_function)
        else:
            menu.add_command(label=_("No component templates available"), state="disabled")

        x = button.winfo_rootx()
        y = button.winfo_rooty() + button.winfo_height()
        menu.post(x, y)

        self.current_menu = menu

        def close_menu(_: tk.Event) -> None:
            if isinstance(self.current_menu, Menu):
                self.current_menu.unpost()
                self.current_menu = None
                self.root.unbind("<Button-1>", close_handler_id)

        close_handler_id = self.root.bind("<Button-1>", close_menu, add="+")

    def _create_template_apply_function(self, component_name: str, template: dict) -> CollectionsCallable[[], None]:
        """Create a function that will apply a template to a component when called."""

        def apply_function() -> None:
            self.apply_component_template(component_name, template)

        return apply_function

    def apply_component_template(self, component_name: str, template: dict) -> None:
        """Apply a template to a component."""
        if "data" not in template:
            return

        template_data = template["data"]

        # Call the callback to update the main data structure
        self.update_data_callback(component_name, template_data)

        for path, entry in self.entry_widgets.items():
            if len(path) >= 1 and path[0] == component_name:
                value = template_data
                try:
                    for key in path[1:]:
                        value = value[key]
                    entry.delete(0, tk.END)
                    entry.insert(0, str(value))
                except (KeyError, TypeError):
                    pass

        template_name = template.get("name", "Template")
        messagebox.showinfo(_("Template Applied"), _("{} has been applied to {}").format(template_name, component_name))
