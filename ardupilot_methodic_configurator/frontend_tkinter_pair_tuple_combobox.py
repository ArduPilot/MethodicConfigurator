#!/usr/bin/env python3

"""
A combobox GUI with support for complex lists.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import contextlib
import tkinter as tk
import tkinter.font as tkfont
from argparse import ArgumentParser, Namespace
from logging import basicConfig as logging_basicConfig
from logging import critical as logging_critical
from logging import debug as logging_debug
from logging import getLevelName as logging_getLevelName
from logging import warning as logging_warning
from platform import system as platform_system
from sys import exit as sys_exit
from tkinter import Label, Toplevel, ttk
from typing import Union

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.common_arguments import add_common_arguments_and_parse
from ardupilot_methodic_configurator.frontend_tkinter_base import get_widget_font_family_and_size, update_combobox_width


# https://dev.to/geraldew/python-tkinter-an-exercise-in-wrapping-the-combobox-ndb
class PairTupleCombobox(ttk.Combobox):  # pylint: disable=too-many-ancestors
    """
    A custom Combobox widget that allows for the display of a list of tuples, where each tuple contains a key and a value.
    This widget processes the list of tuples to separate keys and values for display purposes and allows for the selection
    of a tuple based on its key.
    """

    def __init__(
        self,
        master,  # noqa: ANN001
        list_pair_tuple: list[tuple[str, str]],
        selected_element: Union[None, str],
        cb_name: str,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(master, *args, **kwargs)
        self.cb_name = cb_name
        self.list_keys: list[str] = []
        self.list_shows: list[str] = []
        self.set_entries_tupple(list_pair_tuple, selected_element)
        self.bind("<Configure>", self.on_combo_configure, add="+")

    def set_entries_tupple(self, list_pair_tuple: list[tuple[str, str]], selected_element: Union[None, str]) -> None:
        if isinstance(list_pair_tuple, list):
            for tpl in list_pair_tuple:
                self.list_keys.append(tpl[0])
                self.list_shows.append(tpl[1])
        elif isinstance(list_pair_tuple, dict):
            for key, value in list_pair_tuple.items():
                self.list_keys.append(key)
                self.list_shows.append(value)
        else:
            logging_critical(_("list_pair_tuple must be a tuple or a dictionary, not %s"), type(list_pair_tuple))
            sys_exit(1)
        self["values"] = tuple(self.list_shows)

        if selected_element:
            try:
                default_key_index = self.list_keys.index(selected_element)
                self.current(default_key_index)
            except IndexError:
                logging_critical(
                    _("%s combobox selected string '%s' not in list %s"), self.cb_name, selected_element, self.list_keys
                )
                sys_exit(1)
            except ValueError:
                logging_critical(
                    _("%s combobox selected string '%s' not in list %s"), self.cb_name, selected_element, self.list_keys
                )
                sys_exit(1)
            update_combobox_width(self)
        else:
            logging_debug(_("No %s combobox element selected"), self.cb_name)

    def get_selected_key(self) -> Union[str, None]:
        try:
            i_index = self.current()
            return self.list_keys[i_index]
        except IndexError:
            return None

    # https://stackoverflow.com/questions/39915275/change-width-of-dropdown-listbox-of-a-ttk-combobox
    def on_combo_configure(self, event: tk.Event) -> None:
        combo = event.widget
        style = ttk.Style()
        # check if the combobox already has the "postoffset" property
        current_combo_style = combo.cget("style") or "TCombobox"
        if len(style.lookup(current_combo_style, "postoffset")) > 0:
            return
        combo_values = combo.cget("values")
        if len(combo_values) == 0:
            return
        longest_value = max(combo_values, key=len)
        # font = tkfont.nametofont(combo.cget('font'))
        font = tkfont.nametofont("TkDefaultFont")
        width = font.measure(longest_value + "0000") - event.width
        if width < 0:
            # no need to make the popdown smaller
            return
        # create an unique style name using widget's id
        unique_name = f"Combobox{combo.winfo_id()}"
        # the new style must inherit from current widget style (unless it's our custom style!)
        style_name = current_combo_style if unique_name in current_combo_style else f"{unique_name}.{current_combo_style}"

        style.configure(style_name, postoffset=(0, 0, width, 0))
        combo.configure(style=style_name)


class PairTupleComboboxTooltip(PairTupleCombobox):  # pylint: disable=too-many-ancestors
    """
    A subclass of PairTupleCombobox that enhances the dropdown experience by displaying tooltips for the highlighted entry.

    This class extends the functionality of PairTupleCombobox by adding tooltips to the items displayed in the dropdown menu.
    When an item is selected or hovered over, a tooltip appears on the right side of the combobox, showing the full value and
      descriptive text of the currently highlighted, potentially truncated, combobox entry.

    The tooltip updates dynamically in real-time based on:
    1. Cursor movement within the dropdown list
    2. Mouse hover over the dropdown items

    Key features:
    - Provides immediate feedback on long entries without scrolling
    - Improves usability by offering more information at a glance
    - Maintains focus on the selected item while providing additional details

    Behavior:
    - Tooltip disappears automatically when:
      a) An item is selected from the dropdown
      b) The dropdown is closed (either by selection or pressing Esc)
    """

    def __init__(
        self,
        master,  # noqa: ANN001
        list_pair_tuple: list[tuple[str, str]],
        selected_element: Union[None, str],
        cb_name: str,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(master, list_pair_tuple, selected_element, cb_name, *args, **kwargs)
        self.tooltip: Union[None, Toplevel] = None

        # Bind events related to the dropdown
        pd = self.tk.call("ttk::combobox::PopdownWindow", self)
        lb = pd + ".f.l"
        self._bind(("bind", lb), "<KeyRelease>", self.on_key_release, None)  # type: ignore[attr-defined]
        self._bind(("bind", lb), "<Motion>", self.on_motion, None)  # type: ignore[attr-defined]
        self._bind(("bind", lb), "<Escape>", self.on_escape_press, None)  # type: ignore[attr-defined]
        self.bind("<<ComboboxSelected>>", self.on_combobox_selected, None)

    def on_key_release(self, _event: Union[None, tk.Event]) -> None:
        """Get the keyboard highlighted index and create a tooltip for it."""
        pd = self.tk.call("ttk::combobox::PopdownWindow", self)
        lb = pd + ".f.l"
        if self.tk.call(lb, "curselection"):
            highlighted_index = int(self.tk.call(lb, "curselection")[0])
            self.create_tooltip_from_index(highlighted_index)

    def on_motion(self, event: tk.Event) -> None:
        """Get the mouse highlighted index and create a tooltip for it."""
        pd = self.tk.call("ttk::combobox::PopdownWindow", self)
        lb = pd + ".f.l"
        index = self.tk.call(lb, "index", f"@{event.x},{event.y}")
        self.create_tooltip_from_index(int(index))

    def create_tooltip_from_index(self, index: int) -> None:
        with contextlib.suppress(IndexError):
            self.create_tooltip(f"{self.list_keys[index]}: {self.list_shows[index]}")

    def create_tooltip(self, text: str) -> None:
        self.destroy_tooltip()
        try:
            if self.tooltip is None or self.tooltip.winfo_exists():
                self.tooltip = Toplevel(self.master)
                self.tooltip.wm_overrideredirect(boolean=True)
                x = self.winfo_rootx() + 150  # Adjust width as needed
                y = self.winfo_rooty()
                self.tooltip.wm_geometry(f"+{x}+{y}")
                label = Label(self.tooltip, text=text, background="#ffffe0", relief="solid", borderwidth=1, justify=tk.LEFT)
                label.pack(fill="both", expand=True)
        except tk.TclError:
            # If there's no active item, we don't need to update the tooltip
            pass

    def on_combobox_selected(self, _event: Union[None, tk.Event]) -> None:
        self.destroy_tooltip()

    def on_escape_press(self, _event: Union[None, tk.Event]) -> None:
        self.destroy_tooltip()

    def destroy_tooltip(self) -> None:
        if hasattr(self, "tooltip") and self.tooltip and self.tooltip.winfo_exists():
            self.tooltip.destroy()
            self.tooltip = None


def argument_parser() -> Namespace:
    """
    Parses command-line arguments for the script.

    This function sets up an argument parser to handle the command-line arguments for the script.

    Returns:
    argparse.Namespace: An object containing the parsed arguments.

    """
    parser = ArgumentParser(
        description=_(
            "A GUI for testing the PairTupleCombobox. "
            "Not to be used directly, but through the main ArduPilot methodic configurator script."
        )
    )
    return add_common_arguments_and_parse(parser)


def main() -> None:
    argsp = argument_parser()

    logging_basicConfig(level=logging_getLevelName(argsp.loglevel), format="%(asctime)s - %(levelname)s - %(message)s")

    logging_warning(
        _("This main is for testing and development only, usually the PairTupleCombobox is called from another script")
    )

    root = tk.Tk()
    root.title("Random String Selector")
    root.geometry("400x100")  # Set a size for the window

    # Generate 20 random strings between 4 and 70 characters
    import random  # pylint: disable=import-outside-toplevel
    import string  # pylint: disable=import-outside-toplevel

    random_strings = [
        "".join(random.choices(string.ascii_letters + string.digits, k=random.randint(4, 70)))  # noqa: S311
        for _ in range(20)
    ]

    # Create the PairTupleCombobox2 instance
    tuple_pairs = [(str(i), random_string) for i, random_string in enumerate(random_strings)]
    combobox = PairTupleCombobox(root, tuple_pairs, None, "Random Strings")

    font_family, font_size = get_widget_font_family_and_size(combobox)
    font_size -= 2 if platform_system() == "Windows" else 1
    combobox.config(state="readonly", width=9, font=(font_family, font_size))

    # Pack the combobox into the main window
    combobox.pack(pady=10, padx=10)

    # Set the initial value
    combobox.set(str(1))

    tuple_pairs = [("1", "One"), ("2", "Two"), ("3", "Test")]
    # Create a PairTupleComboboxTooltip instance
    tooltip_combobox = PairTupleComboboxTooltip(root, tuple_pairs, None, "Tooltip Items")

    # Place the tooltip below the combobox
    tooltip_combobox.place(relx=0.5, rely=0.7, anchor=tk.CENTER)

    # Start the Tkinter event loop
    root.mainloop()


if __name__ == "__main__":
    main()
