#!/usr/bin/env python3

"""
A combobox GUI with support for complex lists.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

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
from typing import Optional, Union

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.common_arguments import add_common_arguments
from ardupilot_methodic_configurator.frontend_tkinter_autoresize_combobox import update_combobox_width


def setup_combobox_mousewheel_handling(combobox: ttk.Combobox) -> None:
    """
    Set up mouse wheel handling for a combobox to prevent value changes when scrolling.

    This function adds event bindings to prevent the combobox value from changing
    when the user scrolls the mouse wheel over it while the dropdown is closed.
    When the dropdown is closed, the mouse wheel event is propagated to the parent
    widget to allow normal scrolling behavior in the containing widget.

    Args:
        combobox: The ttk.Combobox widget to configure

    """
    # Track dropdown state to control mouse wheel behavior
    combobox.dropdown_is_open = False  # type: ignore[attr-defined]

    def handle_mousewheel(event: tk.Event) -> Optional[str]:
        """Handle mouse wheel events - propagate to parent when dropdown is closed."""
        if not combobox.dropdown_is_open:  # type: ignore[attr-defined]
            # Propagate the wheel event to the parent widget
            combobox.master.event_generate("<MouseWheel>", delta=event.delta)
            return "break"  # Prevent default combobox behavior
        return None  # Allow default behavior when dropdown is open

    def dropdown_opened(_event: Optional[tk.Event] = None) -> None:
        """Mark dropdown as open."""
        combobox.dropdown_is_open = True  # type: ignore[attr-defined]

    def dropdown_closed(_event: Optional[tk.Event] = None) -> None:
        """Mark dropdown as closed."""
        combobox.dropdown_is_open = False  # type: ignore[attr-defined]    # Bind mouse wheel events (Windows and Linux)

    combobox.bind("<MouseWheel>", handle_mousewheel, add="+")
    combobox.bind("<Button-4>", handle_mousewheel, add="+")
    combobox.bind("<Button-5>", handle_mousewheel, add="+")

    # Track dropdown open/close events
    combobox.bind("<<ComboboxDropdown>>", dropdown_opened, add="+")
    combobox.bind("<FocusOut>", dropdown_closed, add="+")


# SPDX-SnippetBegin
# SPDX-License-Identifier: MPL-2.0
# SPDX-SnippetCopyrightText: 2022 geraldew


# https://dev.to/geraldew/python-tkinter-an-exercise-in-wrapping-the-combobox-ndb
class PairTupleCombobox(ttk.Combobox):  # pylint: disable=too-many-ancestors
    """
    A custom Combobox widget that displays a list of key-value tuples.

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
        self.set_entries_tuple(list_pair_tuple, selected_element)
        self.bind("<Configure>", self.on_combo_configure, add="+")

        # Add keyboard navigation for up/down arrow keys
        self.bind("<Up>", self._on_key_up, add="+")
        self.bind("<Down>", self._on_key_down, add="+")

        # Add focus handling for keyboard events (enable focus reception)
        self.bind("<FocusIn>", lambda _: None, add="+")

        # Apply mouse wheel handling to this combobox instance
        setup_combobox_mousewheel_handling(self)

    def set_entries_tuple(self, list_pair_tuple: list[tuple[str, str]], selected_element: Union[None, str]) -> None:
        # Clear existing entries before setting new ones
        self.list_keys.clear()
        self.list_shows.clear()
        self.append_entries_tuple(list_pair_tuple, selected_element)

    def append_entries_tuple(self, list_pair_tuple: list[tuple[str, str]], selected_element: Union[None, str]) -> None:
        if isinstance(list_pair_tuple, list):
            for tpl in list_pair_tuple:
                self.list_keys.append(tpl[0])
                self.list_shows.append(tpl[1])
        elif isinstance(list_pair_tuple, dict):
            for key, value in list_pair_tuple.items():
                self.list_keys.append(key)
                self.list_shows.append(value)
        else:
            logging_critical(_("list_pair_tuple must be a list of tuples or a dictionary, not %s"), type(list_pair_tuple))
            sys_exit(1)
        self["values"] = tuple(self.list_shows)

        if selected_element:
            default_key_index = self._find_and_validate_selected_element(selected_element)
            if default_key_index is not None:
                self.current(default_key_index)
                update_combobox_width(self)
        else:
            logging_debug(_("No %s combobox element selected"), self.cb_name)

    def _find_and_validate_selected_element(self, selected_element: str) -> Union[int, None]:
        """
        Find the index of the selected element in list_keys.

        Args:
            selected_element: The element to find (should be a list_key)

        Returns:
            The index of the element in list_keys, or None if not found

        """
        try:
            # Find the element in list_keys
            return self.list_keys.index(selected_element)
        except ValueError:
            # Element not found - this should not happen if data model is clean
            logging_critical(
                _("%s combobox selected string '%s' not found in keys %s"),
                self.cb_name,
                selected_element,
                self.list_keys,
            )
            return None

    def get_selected_key(self) -> Union[str, None]:
        try:
            i_index = self.current()
            # self.current() returns -1 if no item is selected
            if i_index < 0:
                return None
            return self.list_keys[i_index]
        except IndexError:
            return None

    # SPDX-SnippetEnd

    def _on_key_up(self, _event: tk.Event) -> str:
        """Handle up arrow key navigation."""
        if not self.list_keys:
            return "break"

        try:
            current_index = self.current()
            # Move up (decrease index), stop at the beginning
            if current_index > 0:
                new_index = current_index - 1
                self.current(new_index)
                # Highlight the text to show selection
                self.selection_range(0, tk.END)
                # Force the combobox to update visually
                self.update_idletasks()
                # Generate a virtual ComboboxSelected event to trigger callbacks
                self.event_generate("<<ComboboxSelected>>")

        except (ValueError, IndexError):
            # Current selection not found or invalid, select first item
            if self.list_keys:
                self.current(0)
                self.update_idletasks()
                self.event_generate("<<ComboboxSelected>>")

        # Prevent the default behavior
        return "break"

    def _on_key_down(self, _event: tk.Event) -> str:
        """Handle down arrow key navigation."""
        if not self.list_keys:
            return "break"

        try:
            current_index = self.current()
            # Move down (increase index), stop at the end
            if current_index < len(self.list_keys) - 1:
                new_index = current_index + 1
                self.current(new_index)
                # Highlight the text to show selection
                self.selection_range(0, tk.END)
                # Force the combobox to update visually
                self.update_idletasks()
                # Generate a virtual ComboboxSelected event to trigger callbacks
                self.event_generate("<<ComboboxSelected>>")

        except (ValueError, IndexError):
            # Current selection not found or invalid, select first item
            if self.list_keys:
                self.current(0)
                # Highlight the text to show selection
                self.selection_range(0, tk.END)
                self.update_idletasks()
                self.event_generate("<<ComboboxSelected>>")

        # Prevent the default behavior
        return "break"

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
        font = tkfont.nametofont("TkDefaultFont")
        width = font.measure(longest_value + "0000") - event.width
        if width < 0:
            # no need to make the popdown smaller
            return
        # create an unique style name using widget's id
        unique_name = f"Combobox{combo.winfo_id()}"
        # the new style must inherit from current widget style (unless it's our custom style!)
        style_name = current_combo_style if unique_name in current_combo_style else f"{unique_name}.{current_combo_style}"

        if isinstance(combo, ttk.Combobox):
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
    return add_common_arguments(parser).parse_args()


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
    import random  # pylint: disable=import-outside-toplevel # noqa: PLC0415
    import string  # pylint: disable=import-outside-toplevel # noqa: PLC0415

    random_strings = [
        "".join(random.choices(string.ascii_letters + string.digits, k=random.randint(4, 70)))  # noqa: S311
        for _ in range(20)
    ]

    # Create the PairTupleCombobox2 instance
    tuple_pairs = [(str(i), random_string) for i, random_string in enumerate(random_strings)]
    combobox = PairTupleCombobox(root, tuple_pairs, None, "Random Strings")

    style = ttk.Style()
    style.theme_use("alt")  # Use an alternative theme for better appearance

    font_size = tkfont.nametofont("TkDefaultFont").cget("size")
    font_size -= 2 if platform_system() == "Windows" else -1
    combobox.config(state="readonly", width=9, font=("TkDefaultFont", font_size))

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
