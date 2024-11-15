#!/usr/bin/env python3

"""
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

# https://wiki.tcl-lang.org/page/Changing+Widget+Colors

import tkinter as tk
from logging import error as logging_error

# from logging import debug as logging_debug
# from logging import info as logging_info
from logging import warning as logging_warning
from platform import system as platform_system
from tkinter import BooleanVar, messagebox, ttk
from tkinter import font as tkFont
from typing import Optional

from PIL import Image, ImageTk

from MethodicConfigurator import _
from MethodicConfigurator.backend_filesystem import LocalFilesystem
from MethodicConfigurator.backend_filesystem_program_settings import ProgramSettings


def show_error_message(title: str, message: str):
    root = tk.Tk()
    # Set the theme to 'alt'
    style = ttk.Style()
    style.theme_use("alt")
    root.withdraw()  # Hide the main window
    messagebox.showerror(title, message)
    root.destroy()


def show_no_param_files_error(_dirname: str):
    error_message = _(
        "No intermediate parameter files found in the selected '{_dirname}' vehicle directory.\n"
        "Please select and step inside a vehicle directory containing valid ArduPilot intermediate parameter files.\n\n"
        "Make sure to step inside the directory (double-click) and not just select it."
    )
    show_error_message(_("No Parameter Files Found"), error_message.format(**locals()))


def show_no_connection_error(_error_string: str):
    error_message = _("{_error_string}\n\nPlease connect a flight controller to the PC,\nwait at least 7 seconds and retry.")
    show_error_message(_("No Connection to the Flight Controller"), error_message.format(**locals()))


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
    tooltip_label = ttk.Label(tooltip, text=text, background="#ffffe0", relief="solid", borderwidth=1, justify=tk.LEFT)
    tooltip_label.pack()
    tooltip.withdraw()  # Initially hide the tooltip

    # Bind the <Enter> and <Leave> events to show and hide the tooltip
    widget.bind("<Enter>", enter)
    widget.bind("<Leave>", leave)


def update_combobox_width(combobox):
    # Calculate the maximum width needed for the content
    max_width = max(len(value) for value in combobox["values"])
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
        container: The parent container in which the Combobox is placed.
        values: A tuple of strings representing the entries in the Combobox.
        selected_element: The initially selected element in the Combobox.
        tooltip: A string representing the tooltip text to display when hovering over the widget.
    """

    def __init__(self, container, values, selected_element, tooltip, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        self.set_entries_tupple(values, selected_element, tooltip)

    def set_entries_tupple(self, values, selected_element, tooltip=None):
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


class ScrollFrame(ttk.Frame):  # pylint: disable=too-many-ancestors
    """
    A custom Frame widget that supports scrolling.

    This class extends the ttk.Frame widget to include a canvas and a scrollbar,
    allowing for scrolling content within the frame. It's useful for creating
    scrollable areas within your application's GUI.
    """

    def __init__(self, parent):
        super().__init__(parent)  # create a frame (self)

        # place canvas on self, copy ttk.background to tk.background
        self.canvas = tk.Canvas(self, borderwidth=0, background=ttk.Style(parent).lookup("TFrame", "background"))

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

    def on_frame_configure(self, _event):
        """Reset the scroll region to encompass the inner frame"""
        # Whenever the size of the frame changes, alter the scroll region respectively.
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        # Calculate the bounding box for the scroll region, starting from the second row
        # bbox = self.canvas.bbox("all")
        # if bbox:
        #     # Adjust the bounding box to start from the second row
        #     bbox = (bbox[0], bbox[1] + self.canvas.winfo_reqheight(), bbox[2], bbox[3])
        #     self.canvas.configure(scrollregion=bbox)

    def on_canvas_configure(self, event):
        """Reset the canvas window to encompass inner frame when required"""
        canvas_width = event.width
        # Whenever the size of the canvas changes alter the window region respectively.
        self.canvas.itemconfig(self.canvas_window, width=canvas_width)

    def on_mouse_wheel(self, event):  # cross platform scroll wheel event
        canvas_height = self.canvas.winfo_height()
        rows_height = self.canvas.bbox("all")[3]

        if rows_height > canvas_height:  # only scroll if the rows overflow the frame
            if platform_system() == "Windows":
                self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            elif platform_system() == "Darwin":
                self.canvas.yview_scroll(int(-1 * event.delta), "units")
            elif event.num == 4:
                self.canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                self.canvas.yview_scroll(1, "units")

    def on_enter(self, _event):  # bind wheel events when the cursor enters the control
        if platform_system() == "Linux":
            self.canvas.bind_all("<Button-4>", self.on_mouse_wheel)
            self.canvas.bind_all("<Button-5>", self.on_mouse_wheel)
        else:
            self.canvas.bind_all("<MouseWheel>", self.on_mouse_wheel)

    def on_leave(self, _event):  # unbind wheel events when the cursor leaves the control
        if platform_system() == "Linux":
            self.canvas.unbind_all("<Button-4>")
            self.canvas.unbind_all("<Button-5>")
        else:
            self.canvas.unbind_all("<MouseWheel>")


class ProgressWindow:
    """
    A class for creating and managing a progress window in the application.

    This class is responsible for creating a progress window that displays the progress of
    a task. It includes a progress bar and a label to display the progress message.
    """

    def __init__(self, parent, title: str, message: str = "", width: int = 300, height: int = 80):  # pylint: disable=too-many-arguments
        self.parent = parent
        self.message = message
        self.progress_window = tk.Toplevel(self.parent)
        self.progress_window.title(title)
        self.progress_window.geometry(f"{width}x{height}")

        main_frame = ttk.Frame(self.progress_window)
        main_frame.pack(expand=True, fill=tk.BOTH)

        # Create a progress bar
        self.progress_bar = ttk.Progressbar(main_frame, length=100, mode="determinate")
        self.progress_bar.pack(side=tk.TOP, fill=tk.X, expand=False, padx=(5, 5), pady=(10, 10))

        # Create a label to display the progress message
        self.progress_label = ttk.Label(main_frame, text=message.format(0, 0))
        self.progress_label.pack(side=tk.TOP, fill=tk.X, expand=False, pady=(10, 10))

        self.progress_window.lift()

        # Center the progress window on the parent window
        BaseWindow.center_window(self.progress_window, self.parent)

        self.progress_bar.update()

    def update_progress_bar_300_pct(self, percent: int):
        self.message = _("Please be patient, {:.1f}% of {}% complete")
        self.update_progress_bar(int(percent / 3), max_value=100)

    def update_progress_bar(self, current_value: int, max_value: int):
        """
        Update the progress bar and the progress message with the current progress.

        Args:
            current_value (int): The current progress value.
            max_value (int): The maximum progress value, if 0 uses percentage.
        """
        try:
            self.progress_window.lift()
        except tk.TclError as _e:
            msg = _("Lifting window: {_e} on file {__file__}")
            logging_error(msg.format(**locals()))
            return

        self.progress_bar["value"] = current_value
        self.progress_bar["maximum"] = max_value

        # Update the progress message
        self.progress_label.config(text=self.message.format(current_value, max_value))

        self.progress_bar.update()

        # Close the progress window when the process is complete
        if current_value == max_value:
            self.progress_window.destroy()

    def destroy(self):
        self.progress_window.destroy()


class RichText(tk.Text):  # pylint: disable=too-many-ancestors
    """
    Extends the standard Tkinter Text widget to support rich text formatting.

    This class allows for the customization of text appearance through tags, enabling
    bold, italic, and heading styles directly within the text widget. It leverages the
    Tkinter font module to dynamically adjust font properties based on predefined tags.

    Methods:
        __init__(self, *args, **kwargs): Initializes the RichText widget with optional arguments
            passed to the superclass constructor. Custom fonts for bold, italic, and heading styles
            are configured during initialization.

    Tags:
        bold: Applies a bold font style.
        italic: Applies an italic font style.
        h1: Doubles the font size and applies bold styling, suitable for headings.

    Usage:
        To use this widget, simply replace instances of the standard Tkinter Text widget with
        RichText in your UI definitions. Apply tags to text segments using the tag_add method
        and configure the appearance accordingly.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        default_font = tkFont.nametofont(self.cget("font"))
        default_size = default_font.cget("size")

        bold_font = tkFont.Font(**default_font.configure())  # type: ignore[arg-type]
        italic_font = tkFont.Font(**default_font.configure())  # type: ignore[arg-type]
        h1_font = tkFont.Font(**default_font.configure())  # type: ignore[arg-type]

        bold_font.configure(weight="bold")
        italic_font.configure(slant="italic")
        h1_font.configure(size=int(default_size * 2), weight="bold")

        self.tag_configure("bold", font=bold_font)
        self.tag_configure("italic", font=italic_font)
        self.tag_configure("h1", font=h1_font, spacing3=default_size)


def get_widget_font(widget: tk.Widget):
    style = ttk.Style()
    widget_style = widget.cget("style")  # Get the style used by the widget
    font_name = style.lookup(widget_style, "font")
    return tkFont.nametofont(font_name).config()


class BaseWindow:
    """
    A base class for creating windows in the ArduPilot Methodic Configurator application.

    This class provides a foundation for creating windows in the application, including setting up the
    root window, applying a theme, and configuring the application icon. It also includes methods for
    creating a progress window and centering a window on its parent.
    """

    def __init__(self, root_tk: Optional[tk.Toplevel] = None):
        if root_tk:
            self.root = tk.Toplevel(root_tk)
        else:
            self.root = tk.Tk()  # type: ignore[assignment]
            # Set the application icon for the window and all child windows
            # https://pythonassets.com/posts/window-icon-in-tk-tkinter/
            self.root.iconphoto(True, tk.PhotoImage(file=LocalFilesystem.application_icon_filepath()))

        # Set the theme to 'alt'
        style = ttk.Style()
        style.theme_use("alt")
        style.configure("Bold.TLabel", font=("TkDefaultFont", 10, "bold"))

        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(expand=True, fill=tk.BOTH)

    @staticmethod
    def center_window(window: tk.Toplevel, parent: tk.Toplevel):
        """
        Center a window on its parent window.

        Args:
            window (tk.Toplevel): The window to center.
            parent (tk.Toplevel): The parent window.
        """
        window.update_idletasks()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        window_width = window.winfo_width()
        window_height = window.winfo_height()
        x = parent.winfo_x() + (parent_width // 2) - (window_width // 2)
        y = parent.winfo_y() + (parent_height // 2) - (window_height // 2)
        window.geometry(f"+{x}+{y}")

    @staticmethod
    def put_image_in_label(parent: ttk.Frame, filepath: str, image_height: int = 40) -> ttk.Label:
        # Load the image and scale it down to image_height pixels in height
        image = Image.open(filepath)
        width, height = image.size
        aspect_ratio = width / height
        new_width = int(image_height * aspect_ratio)
        resized_image = image.resize((new_width, image_height))

        # Convert the image to a format that can be used by Tkinter
        photo = ImageTk.PhotoImage(resized_image)

        # Create a label with the resized image
        image_label = ttk.Label(parent, image=photo)
        # Keep a reference to the image to prevent it from being garbage collected
        image_label.image = photo  # type: ignore
        return image_label


class UsagePopupWindow:
    """
    A class for creating and managing usage popup windows in the application.

    This class extends the BaseWindow class to provide functionality for displaying
    usage popups with instructions and options to show them again or dismiss.
    """

    def __init__(self):
        pass

    @staticmethod
    def should_display(ptype: str) -> bool:
        return ProgramSettings.display_usage_popup(ptype)

    @staticmethod
    def display(  # pylint: disable=too-many-arguments
        parent: tk.Toplevel,
        usage_popup_window: BaseWindow,
        title: str,
        ptype: str,
        geometry: str,
        instructions_text: RichText,
    ):
        usage_popup_window.root.title(title)
        usage_popup_window.root.geometry(geometry)

        instructions_text.pack(padx=6, pady=10)

        show_again_var = BooleanVar()
        show_again_var.set(True)

        def update_show_again():
            ProgramSettings.set_display_usage_popup(ptype, show_again_var.get())

        show_again_checkbox = ttk.Checkbutton(
            usage_popup_window.main_frame,
            text=_("Show this usage popup again"),
            variable=show_again_var,
            command=update_show_again,
        )
        show_again_checkbox.pack(pady=(10, 5))

        dismiss_button = ttk.Button(
            usage_popup_window.main_frame,
            text=_("Dismiss"),
            command=lambda: UsagePopupWindow.close(usage_popup_window, parent),
        )
        dismiss_button.pack(pady=10)

        BaseWindow.center_window(usage_popup_window.root, parent)
        usage_popup_window.root.attributes("-topmost", True)

        if platform_system() == "Windows":
            parent.attributes("-disabled", True)  # Disable parent window input

        usage_popup_window.root.protocol("WM_DELETE_WINDOW", lambda: UsagePopupWindow.close(usage_popup_window, parent))

    @staticmethod
    def close(usage_popup_window: BaseWindow, parent: tk.Toplevel):
        usage_popup_window.root.destroy()
        if platform_system() == "Windows":
            parent.attributes("-disabled", False)  # Re-enable the parent window
        parent.focus_set()
