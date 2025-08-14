"""
TKinter base classes reused in multiple parts of the code.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from platform import system as platform_system
from tkinter import ttk

# SPDX-SnippetBegin
# SPDX-License-Identifier: MPL-2.0
# SPDX-SnippetCopyrightText: 2019 Mark Pointing


class ScrollFrame(ttk.Frame):  # pylint: disable=too-many-ancestors
    """
    A custom Frame widget that supports scrolling.

    This class extends the ttk.Frame widget to include a canvas and a scrollbar,
    allowing for scrolling content within the frame. It's useful for creating
    scrollable areas within your application's GUI.
    """

    def __init__(self, master) -> None:  # noqa: ANN001
        super().__init__(master)  # create a frame (self)

        # place canvas on self, copy ttk.background to tk.background
        self.canvas = tk.Canvas(
            self,
            borderwidth=0,
            background=ttk.Style(master).lookup("TFrame", "background"),  # type: ignore[no-untyped-call]
        )

        # place a frame on the canvas, this frame will hold the child widgets
        self.view_port = ttk.Frame(self.canvas)

        # place a tk.scrollbar on self. ttk.scrollbar will not work here
        self.vsb = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        # attach scrollbar action to scroll of canvas
        self.canvas.configure(yscrollcommand=self.vsb.set)

        self.vsb.pack(side="right", fill="y")  # pack scrollbar to right of self
        # pack canvas to left of self and expand to fill
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas_window = self.canvas.create_window(
            (4, 4),
            window=self.view_port,  # add view port frame to canvas
            anchor="nw",
            tags="self.view_port",
        )

        # bind an event whenever the size of the view_port frame changes.
        self.view_port.bind("<Configure>", self.on_frame_configure)
        # bind an event whenever the size of the canvas frame changes.
        self.canvas.bind("<Configure>", self.on_canvas_configure)

        # bind wheel events when the cursor enters the control
        self.view_port.bind("<Enter>", self.on_enter)
        # unbind wheel events when the cursor leaves the control
        self.view_port.bind("<Leave>", self.on_leave)

        # perform an initial stretch on render, otherwise the scroll region has a tiny border until the first resize
        self.on_frame_configure(None)

    def on_frame_configure(self, _event) -> None:  # noqa: ANN001
        """Reset the scroll region to encompass the inner frame."""
        # Whenever the size of the frame changes, alter the scroll region respectively.
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        # Calculate the bounding box for the scroll region, starting from the second row
        # bbox = self.canvas.bbox("all")
        # if bbox:
        #     # Adjust the bounding box to start from the second row
        #     bbox = (bbox[0], bbox[1] + self.canvas.winfo_reqheight(), bbox[2], bbox[3])
        #     self.canvas.configure(scrollregion=bbox)

    def on_canvas_configure(self, event: tk.Event) -> None:
        """Reset the canvas window to encompass inner frame when required."""
        canvas_width = event.width
        # Whenever the size of the canvas changes alter the window region respectively.
        self.canvas.itemconfig(self.canvas_window, width=canvas_width)

    def on_mouse_wheel(self, event: tk.Event) -> None:  # cross platform scroll wheel event
        canvas_height = self.canvas.winfo_height()
        rows_height = self.canvas.bbox("all")[3]

        if rows_height > canvas_height:  # only scroll if the rows overflow the frame
            if platform_system() == "Windows":
                # Windows: positive delta means scroll up, negative means scroll down
                self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            elif platform_system() == "Darwin":
                # macOS: similar to Windows but different scaling
                self.canvas.yview_scroll(int(-1 * event.delta), "units")
            elif event.num == 4:
                # Linux: Button-4 means scroll up
                self.canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                # Linux: Button-5 means scroll down
                self.canvas.yview_scroll(1, "units")

    def on_enter(self, _event: tk.Event) -> None:  # bind wheel events when the cursor enters the control
        if platform_system() == "Linux":
            self.canvas.bind_all("<Button-4>", self.on_mouse_wheel)
            self.canvas.bind_all("<Button-5>", self.on_mouse_wheel)
        else:
            self.canvas.bind_all("<MouseWheel>", self.on_mouse_wheel)

    def on_leave(self, _event: tk.Event) -> None:  # unbind wheel events when the cursor leaves the control
        if platform_system() == "Linux":
            self.canvas.unbind_all("<Button-4>")
            self.canvas.unbind_all("<Button-5>")
        else:
            self.canvas.unbind_all("<MouseWheel>")


# SPDX-SnippetEnd
