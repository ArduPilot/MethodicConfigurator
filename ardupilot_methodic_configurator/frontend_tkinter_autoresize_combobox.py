"""
TKinter base classes reused in multiple parts of the code.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

# https://wiki.tcl-lang.org/page/Changing+Widget+Colors

from logging import error as logging_error
from logging import warning as logging_warning
from tkinter import ttk
from typing import Union

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.frontend_tkinter_show import show_tooltip


def update_combobox_width(combobox: ttk.Combobox) -> None:
    # Calculate the maximum width needed for the content
    values = combobox["values"]
    max_width = max(len(value) for value in values) if values else 0
    # Set a minimum width for the combobox
    min_width = 4  # Adjust this value as needed
    # Set the width of the combobox to the maximum width, but not less than the minimum width
    combobox.config(width=max(min_width, max_width))


class AutoResizeCombobox(ttk.Combobox):  # pylint: disable=too-many-ancestors
    """
    A custom Combobox widget that automatically resizes based on its content.

    This class extends the ttk.Combobox widget to include functionality for
    automatically adjusting its width based on the longest entry in its list of
    values. It also supports displaying a tooltip when hovering over the widget.

    Attributes:
        master: The parent container in which the Combobox is placed.
        values: A tuple of strings representing the entries in the Combobox.
        selected_element: The initially selected element in the Combobox.
        tooltip: A string representing the tooltip text to display when hovering over the widget.

    """

    def __init__(
        self, master: ttk.Frame, values: list[str], selected_element: str, tooltip: Union[None, str], *args, **kwargs
    ) -> None:
        super().__init__(master, *args, **kwargs)
        self.set_entries_tuple(values, selected_element, tooltip)

    def set_entries_tuple(self, values: list[str], selected_element: str, tooltip: Union[None, str] = None) -> None:
        self["values"] = tuple(values)
        if selected_element:
            if selected_element in values:
                self.set(selected_element)
            else:
                logging_error(_("param_file combobox selected string '%s' not in list %s"), selected_element, values)
        elif values:
            logging_warning(_("No param_file combobox element selected"))
        if values:
            update_combobox_width(self)
        if tooltip:
            show_tooltip(self, tooltip)
