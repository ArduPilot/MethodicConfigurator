#!/usr/bin/env python3

'''
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

(C) 2024 Amilcar do Carmo Lucas, IAV GmbH

SPDX-License-Identifier:    GPL-3
'''

import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
# from logging import debug as logging_debug
# from logging import info as logging_info
from logging import warning as logging_warning
from logging import error as logging_error
from platform import system as platform_system

from backend_filesystem import LocalFilesystem


def show_error_message(title: str, message: str):
    root = tk.Tk()
    # Set the theme to 'alt'
    style = ttk.Style()
    style.theme_use('alt')
    root.withdraw() # Hide the main window
    messagebox.showwarning(title, message)
    root.destroy()


def show_no_param_files_error(dirname: str):
    error_message = f"No intermediate parameter files found in the selected '{dirname}' vehicle directory.\n" \
        "Please select a vehicle directory containing valid ArduPilot intermediate parameter files."
    show_error_message("No Parameter Files Found", error_message)


def show_no_connection_error(error_string: str):
    error_message = f"{error_string}\n\nPlease connect a flight controller to the PC,\n" \
        "wait at least 7 seconds and retry."
    show_error_message("No Connection to the Flight Controller", error_message)


def show_tooltip(widget, text):
    def enter(_event):
        # Calculate the position of the tooltip based on the widget's position
        x = widget.winfo_rootx() + widget.winfo_width() // 2
        y = widget.winfo_rooty() + widget.winfo_height()
        tooltip.geometry(f"+{x}+{y}")
        tooltip.deiconify()

    def leave(_event):
        tooltip.withdraw()

    tooltip = tk.Toplevel(widget)
    tooltip.wm_overrideredirect(True)
    tooltip_label = tk.Label(tooltip, text=text, bg="#ffffe0", relief="solid", borderwidth=1, justify=tk.LEFT)
    tooltip_label.pack()
    tooltip.withdraw() # Initially hide the tooltip

    # Bind the <Enter> and <Leave> events to show and hide the tooltip
    widget.bind("<Enter>", enter)
    widget.bind("<Leave>", leave)


def update_combobox_width(combobox):
    # Calculate the maximum width needed for the content
    max_width = max(len(value) for value in combobox['values'])
    # Set a minimum width for the combobox
    min_width = 4 # Adjust this value as needed
    # Set the width of the combobox to the maximum width, but not less than the minimum width
    combobox.config(width=max(min_width, max_width))


class AutoResizeCombobox(ttk.Combobox):  # pylint: disable=too-many-ancestors
    """
    A custom Combobox widget that automatically resizes based on its content.

    This class extends the ttk.Combobox widget to include functionality for
    automatically adjusting its width based on the longest entry in its list of
    values. It also supports displaying a tooltip when hovering over the widget.

    Attributes:
        container: The parent container in which the Combobox is placed.
        values: A tuple of strings representing the entries in the Combobox.
        selected_element: The initially selected element in the Combobox.
        tooltip: A string representing the tooltip text to display when hovering over the widget.
    """
    def __init__(self, container, values, selected_element, tooltip, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        self.set_entries_tupple(values, selected_element, tooltip)

    def set_entries_tupple(self, values, selected_element, tooltip=None):
        self['values'] = tuple(values)
        if selected_element:
            if selected_element in values:
                self.set(selected_element)
            else:
                logging_error("param_file combobox selected string '%s' not in list %s", selected_element, values)
        else:
            if values:
                logging_warning("No param_file combobox element selected")
        if values:
            update_combobox_width(self)
        if tooltip:
            show_tooltip(self, tooltip)


class ScrollFrame(tk.Frame):
    """
    A custom Frame widget that supports scrolling.

    This class extends the tk.Frame widget to include a canvas and a scrollbar,
    allowing for scrolling content within the frame. It's useful for creating
    scrollable areas within your application's GUI.
    """
    def __init__(self, parent):
        super().__init__(parent) # create a frame (self)

        self.canvas = tk.Canvas(self, borderwidth=0)                                 # place canvas on self

        # place a frame on the canvas, this frame will hold the child widgets
        self.view_port = tk.Frame(self.canvas)

        self.vsb = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)  # place a scrollbar on self
        # attach scrollbar action to scroll of canvas
        self.canvas.configure(yscrollcommand=self.vsb.set)

        self.vsb.pack(side="right", fill="y")                                        # pack scrollbar to right of self
        # pack canvas to left of self and expand to fill
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas_window = self.canvas.create_window((4, 4), window=self.view_port, # add view port frame to canvas
                                                       anchor="nw", tags="self.view_port")

        # bind an event whenever the size of the view_port frame changes.
        self.view_port.bind("<Configure>", self.on_frame_configure)
        # bind an event whenever the size of the canvas frame changes.
        self.canvas.bind("<Configure>", self.on_canvas_configure)

        # bind wheel events when the cursor enters the control
        self.view_port.bind('<Enter>', self.on_enter)
        # unbind wheel events when the cursor leaves the control
        self.view_port.bind('<Leave>', self.on_leave)

        # perform an initial stretch on render, otherwise the scroll region has a tiny border until the first resize
        self.on_frame_configure(None)

    def on_frame_configure(self, _event):
        '''Reset the scroll region to encompass the inner frame'''
        # whenever the size of the frame changes, alter the scroll region respectively.
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        # Calculate the bounding box for the scroll region, starting from the second row
        # bbox = self.canvas.bbox("all")
        # if bbox:
        #     # Adjust the bounding box to start from the second row
        #     bbox = (bbox[0], bbox[1] + self.canvas.winfo_reqheight(), bbox[2], bbox[3])
        #     self.canvas.configure(scrollregion=bbox)

    def on_canvas_configure(self, event):
        '''Reset the canvas window to encompass inner frame when required'''
        canvas_width = event.width
        # whenever the size of the canvas changes alter the window region respectively.
        self.canvas.itemconfig(self.canvas_window, width=canvas_width)

    def on_mouse_wheel(self, event):                       # cross platform scroll wheel event
        canvas_height = self.canvas.winfo_height()
        rows_height = self.canvas.bbox("all")[3]

        if rows_height > canvas_height: # only scroll if the rows overflow the frame
            if platform_system() == 'Windows':
                self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            elif platform_system() == 'Darwin':
                self.canvas.yview_scroll(int(-1 * event.delta), "units")
            else:
                if event.num == 4:
                    self.canvas.yview_scroll(-1, "units")
                elif event.num == 5:
                    self.canvas.yview_scroll(1, "units")

    def on_enter(self, _event):                             # bind wheel events when the cursor enters the control
        if platform_system() == 'Linux':
            self.canvas.bind_all("<Button-4>", self.on_mouse_wheel)
            self.canvas.bind_all("<Button-5>", self.on_mouse_wheel)
        else:
            self.canvas.bind_all("<MouseWheel>", self.on_mouse_wheel)

    def on_leave(self, _event):                             # unbind wheel events when the cursor leaves the control
        if platform_system() == 'Linux':
            self.canvas.unbind_all("<Button-4>")
            self.canvas.unbind_all("<Button-5>")
        else:
            self.canvas.unbind_all("<MouseWheel>")


class BaseWindow:
    """
    A base class for creating windows in the ArduPilot Methodic Configurator application.

    This class provides a foundation for creating windows in the application, including setting up the
    root window, applying a theme, and configuring the application icon. It also includes methods for
    creating a progress window and centering a window on its parent.
    """
    def __init__(self, root_tk: tk.Tk=None):
        if root_tk:
            self.root = root_tk
        else:
            self.root = tk.Tk()

        # Set the theme to 'alt'
        style = ttk.Style()
        style.theme_use('alt')

        # Set the application icon for the window and all child windows
        # https://pythonassets.com/posts/window-icon-in-tk-tkinter/
        self.root.iconphoto(True, tk.PhotoImage(file=LocalFilesystem.application_icon_filepath()))

        # Get the background color for the 'TFrame' widget
        self.default_background_color = '#f0f0f0' # style.lookup('TFrame', 'background')

        # Configure the background color for the checkbutton
        style.configure('TCheckbutton', background=self.default_background_color)
        style.configure('TCombobox', background=self.default_background_color)

    def create_progress_window(self, title: str):
        # Create a new window for the param_read progress bar
        progress_window = tk.Toplevel(self.root)
        progress_window.title(title)
        progress_window.geometry("300x80")

        # Center the param_read progress window on the main window
        BaseWindow.center_window(progress_window, self.root)

        # Create a param_read progress bar
        progress_bar = ttk.Progressbar(progress_window, length=100, mode='determinate')
        progress_bar.pack(side=tk.TOP, fill=tk.X, expand=False, padx=(5, 5), pady=(10, 10))

        # Create a param_read label to display the progress message
        progress_label = tk.Label(progress_window, text="")
        progress_label.pack(side=tk.TOP, fill=tk.X, expand=False, pady=(10, 10))

        return progress_window, progress_bar, progress_label

    @staticmethod
    def center_window(window, parent):
        """
        Center a window on its parent window.

        Args:
            window (tk.Toplevel): The window to center.
            parent (tk.Tk): The parent window.
        """
        window.update_idletasks()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        window_width = window.winfo_width()
        window_height = window.winfo_height()
        x = parent.winfo_x() + (parent_width // 2) - (window_width // 2)
        y = parent.winfo_y() + (parent_height // 2) - (window_height // 2)
        window.geometry(f"+{x}+{y}")
