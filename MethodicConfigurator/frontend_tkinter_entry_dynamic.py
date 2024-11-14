#!/usr/bin/env python3

"""
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

https://code.activestate.com/recipes/580770-combobox-autocomplete/

SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from tkinter import Entry, Listbox, StringVar, ttk
from tkinter.constants import END, HORIZONTAL, SINGLE, VERTICAL, E, N, S, W

from MethodicConfigurator import _


def autoscroll(sbar, first, last):
    """Hide and show scrollbar as needed."""
    first, last = float(first), float(last)
    if first <= 0 and last >= 1:
        sbar.grid_remove()
    else:
        sbar.grid()
    sbar.set(first, last)


class EntryWithDynamicalyFilteredListbox(Entry):  # pylint: disable=too-many-ancestors, too-many-instance-attributes
    """
    Entry with dynamicaly filtered ListBox to emulate an inteligent combobox widget
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        master,
        list_of_items=None,
        custom_filter_function=None,
        listbox_width=None,
        listbox_height=12,
        ignorecase_match=False,
        startswith_match=True,
        vscrollbar=True,
        hscrollbar=True,
        **kwargs,
    ):
        if list_of_items is None:
            raise ValueError(_("List_of_items can't be 'None'"))
        self._list_of_items = list_of_items

        self.filter_function = custom_filter_function or self.default_filter_function

        self._listbox_width = listbox_width
        self._listbox_height = int(listbox_height)
        self._ignorecase_match = ignorecase_match
        self._startswith_match = startswith_match
        self._use_vscrollbar = vscrollbar
        self._use_hscrollbar = hscrollbar

        kwargs.setdefault("background", "white")

        if "textvariable" in kwargs:
            self._entry_var = kwargs["textvariable"]
        else:
            self._entry_var = kwargs["textvariable"] = StringVar()

        Entry.__init__(self, master, **kwargs)

        self._trace_id = self._entry_var.trace_add("write", self._on_change_entry_var)

        self._listbox = None

        self.bind("<Up>", self._previous)
        self.bind("<Down>", self._next)
        self.bind("<Control-n>", self._next)
        self.bind("<Control-p>", self._previous)

        self.bind("<Return>", self.update_entry_from_listbox)
        self.bind("<Escape>", lambda event: self.unpost_listbox())

    def default_filter_function(self, entry_data):
        if self._ignorecase_match:
            if self._startswith_match:
                return [item for item in self._list_of_items if item.lower().startswith(entry_data.lower())]
            return [item for item in self._list_of_items if entry_data.lower() in item.lower()]
        if self._startswith_match:
            return [item for item in self._list_of_items if item.startswith(entry_data)]
        return [item for item in self._list_of_items if entry_data in item]

    def _on_change_entry_var(self, _name, _index, _mode):
        entry_data = self._entry_var.get()

        if entry_data == "":
            self.unpost_listbox()
            self.focus()
        else:
            values = self.filter_function(entry_data)
            if values:
                if self._listbox is None:
                    self._build_listbox(values)
                else:
                    self._listbox.delete(0, END)

                    height = min(self._listbox_height, len(values))
                    self._listbox.configure(height=height)

                    for item in values:
                        self._listbox.insert(END, item)

            else:
                self.unpost_listbox()
                self.focus()

    def _build_listbox(self, values):
        listbox_frame = ttk.Frame(self.master)

        self._listbox = Listbox(
            listbox_frame, background="white", selectmode=SINGLE, activestyle="none", exportselection=False
        )
        self._listbox.grid(row=0, column=0, sticky=N + E + W + S)

        self._listbox.bind("<ButtonRelease-1>", self.update_entry_from_listbox)
        self._listbox.bind("<Return>", self.update_entry_from_listbox)
        self._listbox.bind("<Escape>", lambda event: self.unpost_listbox())

        self._listbox.bind("<Control-n>", self._next)
        self._listbox.bind("<Control-p>", self._previous)

        if self._use_vscrollbar:
            vbar = ttk.Scrollbar(listbox_frame, orient=VERTICAL, command=self._listbox.yview)
            vbar.grid(row=0, column=1, sticky=N + S)

            self._listbox.configure(yscrollcommand=lambda first, last: autoscroll(vbar, first, last))

        if self._use_hscrollbar:
            hbar = ttk.Scrollbar(listbox_frame, orient=HORIZONTAL, command=self._listbox.xview)
            hbar.grid(row=1, column=0, sticky=E + W)

            self._listbox.configure(xscrollcommand=lambda first, last: autoscroll(hbar, first, last))

        listbox_frame.grid_columnconfigure(0, weight=1)
        listbox_frame.grid_rowconfigure(0, weight=1)

        x = -self.cget("borderwidth") - self.cget("highlightthickness")
        y = self.winfo_height() - self.cget("borderwidth") - self.cget("highlightthickness")

        width = self._listbox_width or self.winfo_width()

        listbox_frame.place(in_=self, x=x, y=y, width=width)

        height = min(self._listbox_height, len(values))
        self._listbox.configure(height=height)

        for item in values:
            self._listbox.insert(END, item)

    def post_listbox(self):
        if self._listbox is not None:
            return

        entry_data = self._entry_var.get()
        if entry_data == "":
            return

        values = self.filter_function(entry_data)
        if values:
            self._build_listbox(values)

    def unpost_listbox(self):
        if self._listbox is not None:
            self._listbox.master.destroy()
            self._listbox = None

    def get_value(self):
        return self._entry_var.get()

    def set_value(self, text, close_dialog=False):
        self._set_var(text)

        if close_dialog:
            self.unpost_listbox()

        self.icursor(END)
        self.xview_moveto(1.0)

    def _set_var(self, text):
        self._entry_var.trace_remove("write", self._trace_id)
        self._entry_var.set(text)
        self._trace_id = self._entry_var.trace_add("write", self._on_change_entry_var)

    def update_entry_from_listbox(self, _event):
        if self._listbox is not None:
            current_selection = self._listbox.curselection()

            if current_selection:
                text = self._listbox.get(current_selection)
                self._set_var(text)

            self._listbox.master.destroy()
            self._listbox = None

            self.focus()
            self.icursor(END)
            self.xview_moveto(1.0)

        return "break"

    def _previous(self, _event):
        if self._listbox is not None:
            current_selection = self._listbox.curselection()

            if len(current_selection) == 0:
                self._listbox.selection_set(0)
                self._listbox.activate(0)
            else:
                index: int = int(current_selection[0])
                self._listbox.selection_clear(index)

                if index == 0:
                    index = END  # type: ignore
                else:
                    index -= 1

                self._listbox.see(index)
                self._listbox.selection_set(first=index)
                self._listbox.activate(index)

        return "break"

    def _next(self, _event):
        if self._listbox is not None:
            current_selection = self._listbox.curselection()
            if len(current_selection) == 0:
                self._listbox.selection_set(0)
                self._listbox.activate(0)
            else:
                index = int(current_selection[0])
                self._listbox.selection_clear(index)

                if index == self._listbox.size() - 1:
                    index = 0
                else:
                    index += 1

                self._listbox.see(index)
                self._listbox.selection_set(index)
                self._listbox.activate(index)
        return "break"


if __name__ == "__main__":

    def main():
        list_of_items = [
            "Cordell Cannata",
            "Lacey Naples",
            "Zachery Manigault",
            "Regan Brunt",
            "Mario Hilgefort",
            "Austin Phong",
            "Moises Saum",
            "Willy Neill",
            "Rosendo Sokoloff",
            "Salley Christenberry",
            "Toby Schneller",
            "Angel Buchwald",
            "Nestor Criger",
            "Arie Jozwiak",
            "Nita Montelongo",
            "Clemencia Okane",
            "Alison Scaggs",
            "Von Petrella",
            "Glennie Gurley",
            "Jamar Callender",
            "Titus Wenrich",
            "Chadwick Liedtke",
            "Sharlene Yochum",
            "Leonida Mutchler",
            "Duane Pickett",
            "Morton Brackins",
            "Ervin Trundy",
            "Antony Orwig",
            "Audrea Yutzy",
            "Michal Hepp",
            "Annelle Hoadley",
            "Hank Wyman",
            "Mika Fernandez",
            "Elisa Legendre",
            "Sade Nicolson",
            "Jessie Yi",
            "Forrest Mooneyhan",
            "Alvin Widell",
            "Lizette Ruppe",
            "Marguerita Pilarski",
            "Merna Argento",
            "Jess Daquila",
            "Breann Bevans",
            "Melvin Guidry",
            "Jacelyn Vanleer",
            "Jerome Riendeau",
            "Iraida Nyquist",
            "Micah Glantz",
            "Dorene Waldrip",
            "Fidel Garey",
            "Vertie Deady",
            "Rosalinda Odegaard",
            "Chong Hayner",
            "Candida Palazzolo",
            "Bennie Faison",
            "Nova Bunkley",
            "Francis Buckwalter",
            "Georgianne Espinal",
            "Karleen Dockins",
            "Hertha Lucus",
            "Ike Alberty",
            "Deangelo Revelle",
            "Juli Gallup",
            "Wendie Eisner",
            "Khalilah Travers",
            "Rex Outman",
            "Anabel King",
            "Lorelei Tardiff",
            "Pablo Berkey",
            "Mariel Tutino",
            "Leigh Marciano",
            "Ok Nadeau",
            "Zachary Antrim",
            "Chun Matthew",
            "Golden Keniston",
            "Anthony Johson",
            "Rossana Ahlstrom",
            "Amado Schluter",
            "Delila Lovelady",
            "Josef Belle",
            "Leif Negrete",
            "Alec Doss",
            "Darryl Stryker",
            "Michael Cagley",
            "Sabina Alejo",
            "Delana Mewborn",
            "Aurelio Crouch",
            "Ashlie Shulman",
            "Danielle Conlan",
            "Randal Donnell",
            "Rheba Anzalone",
            "Lilian Truax",
            "Weston Quarterman",
            "Britt Brunt",
            "Leonie Corbett",
            "Monika Gamet",
            "Ingeborg Bello",
            "Angelique Zhang",
            "Santiago Thibeau",
            "Eliseo Helmuth",
        ]

        root = tk.Tk()
        root.geometry("300x300")

        combobox_autocomplete = EntryWithDynamicalyFilteredListbox(
            root, list_of_items=list_of_items, ignorecase_match=True, startswith_match=False
        )

        combobox_autocomplete.pack()

        combobox_autocomplete.focus()

        root.mainloop()

    main()
