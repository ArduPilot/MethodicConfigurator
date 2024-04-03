#!/usr/bin/env python3

'''
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

AP_FLAKE8_CLEAN

(C) 2024 Amilcar do Carmo Lucas, IAV GmbH

SPDX-License-Identifier:    GPL-3
'''

import tkinter as tk
from tkinter import filedialog
from tkinter import messagebox
from tkinter import simpledialog
from tkinter import ttk
from logging import debug as logging_debug
from logging import info as logging_info
from logging import warning as logging_warning
from logging import error as logging_error
from PIL import Image
from PIL import ImageTk
from platform import system as platform_system

from webbrowser import open as webbrowser_open  # to open the blog post documentation

from backend_filesystem import LocalFilesystem
from backend_filesystem import is_within_tolerance
from backend_flightcontroller import FlightController


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
        "Please select a vehicle directory containing valid ArduPilot methodic intermediate parameter files."
    show_error_message("No Parameter Files Found", error_message)


def show_no_connection_error(error_string: str):
    error_message = f"{error_string}\n\nPlease connect a flight controller, wait a few seconds,\n" \
        "restart the software and select its connection port."
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


# https://dev.to/geraldew/python-tkinter-an-exercise-in-wrapping-the-combobox-ndb
class PairTupleCombobox(ttk.Combobox):

    def _process_listPairTuple(self, ip_listPairTuple):
        r_list_keys = [] 
        r_list_shows = [] 
        for tpl in ip_listPairTuple:
            r_list_keys.append(tpl[0])
            r_list_shows.append(tpl[1])
        return r_list_keys, r_list_shows

    def __init__(self, container, p_listPairTuple, selected_element, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        self.set_entries_tupple(p_listPairTuple, selected_element)

    def set_entries_tupple(self, p_listPairTuple, selected_element):
        self.list_keys, self.list_shows = self._process_listPairTuple(p_listPairTuple)
        self['values'] = tuple(self.list_shows)
        # still need to set the default value from the nominated key
        if selected_element:
            try:
                default_key_index = self.list_keys.index(selected_element)
                self.current(default_key_index)
            except IndexError:
                logging_error("connection combobox selected string '%s' not in list %s", selected_element, self.list_keys)
                pass
            except ValueError:
                logging_error("connection combobox selected string '%s' not in list %s", selected_element, self.list_keys)
                exit(1)
            gui.update_combobox_width(self)
        else:
            logging_warning("No connection combobox element selected")

    def getSelectedKey(self):
        try:
            i_index = self.current()
            return self.list_keys[i_index]
        except IndexError:
            return None

class AutoResizeCombobox(ttk.Combobox):

    def __init__(self, container, values, selected_element, tooltip, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        self.set_entries_tupple(values, selected_element, tooltip)

    def set_entries_tupple(self, values, selected_element, tooltip = None):
        self['values'] = tuple(values)
        if selected_element:
            if selected_element in values:
                self.set(selected_element)
            else:
                logging_error("param_file combobox selected string '%s' not in list %s", selected_element, values)
        else:
            logging_warning("No param_file combobox element selected")
        if values:
            gui.update_combobox_width(self)
        if tooltip:
            show_tooltip(self, tooltip)


class ScrollFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent) # create a frame (self)

        self.canvas = tk.Canvas(self, borderwidth=0)                                # place canvas on self
        self.viewPort = tk.Frame(self.canvas)                                       # place a frame on the canvas, this frame will hold the child widgets
        self.vsb = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview) # place a scrollbar on self
        self.canvas.configure(yscrollcommand=self.vsb.set)                          # attach scrollbar action to scroll of canvas

        self.vsb.pack(side="right", fill="y")                                       # pack scrollbar to right of self
        self.canvas.pack(side="left", fill="both", expand=True)                     # pack canvas to left of self and expand to fil
        self.canvas_window = self.canvas.create_window((4,4), window=self.viewPort, # add view port frame to canvas
                                                       anchor="nw", tags="self.viewPort")

        self.viewPort.bind("<Configure>", self.onFrameConfigure)                    # bind an event whenever the size of the viewPort frame changes.
        self.canvas.bind("<Configure>", self.onCanvasConfigure)                     # bind an event whenever the size of the canvas frame changes.
            
        self.viewPort.bind('<Enter>', self.onEnter)                                 # bind wheel events when the cursor enters the control
        self.viewPort.bind('<Leave>', self.onLeave)                                 # unbind wheel events when the cursor leaves the control

        self.onFrameConfigure(None)                                                 # perform an initial stretch on render, otherwise the scroll region has a tiny border until the first resize

    def onFrameConfigure(self, event):
        '''Reset the scroll region to encompass the inner frame'''
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))                 # whenever the size of the frame changes, alter the scroll region respectively.
        # Calculate the bounding box for the scroll region, starting from the second row
       # bbox = self.canvas.bbox("all")
       # if bbox:
       #     # Adjust the bounding box to start from the second row
       #     bbox = (bbox[0], bbox[1] + self.canvas.winfo_reqheight(), bbox[2], bbox[3])
       #     self.canvas.configure(scrollregion=bbox)

    def onCanvasConfigure(self, event):
        '''Reset the canvas window to encompass inner frame when required'''
        canvas_width = event.width
        self.canvas.itemconfig(self.canvas_window, width = canvas_width)            # whenever the size of the canvas changes alter the window region respectively.

    def onMouseWheel(self, event):                                                  # cross platform scroll wheel event
        canvas_height = self.canvas.winfo_height()
        rows_height = self.canvas.bbox("all")[3]

        if rows_height > canvas_height: # only scroll if the rows overflow the frame
            if platform_system() == 'Windows':
                self.canvas.yview_scroll(int(-1* (event.delta/120)), "units")
            elif platform_system() == 'Darwin':
                self.canvas.yview_scroll(int(-1 * event.delta), "units")
            else:
                if event.num == 4:
                    self.canvas.yview_scroll( -1, "units" )
                elif event.num == 5:
                    self.canvas.yview_scroll( 1, "units" )
    
    def onEnter(self, event):                                                       # bind wheel events when the cursor enters the control
        if platform_system() == 'Linux':
            self.canvas.bind_all("<Button-4>", self.onMouseWheel)
            self.canvas.bind_all("<Button-5>", self.onMouseWheel)
        else:
            self.canvas.bind_all("<MouseWheel>", self.onMouseWheel)

    def onLeave(self, event):                                                       # unbind wheel events when the cursor leaves the control
        if platform_system() == 'Linux':
            self.canvas.unbind_all("<Button-4>")
            self.canvas.unbind_all("<Button-5>")
        else:
            self.canvas.unbind_all("<MouseWheel>")


class gui:
    def __init__(self, current_file: str, flight_controller: FlightController, local_filesystem: LocalFilesystem, version: str):
        self.current_file = current_file
        self.flight_controller = flight_controller
        self.local_filesystem = local_filesystem

        self.at_least_one_param_edited = False
        self.at_least_one_changed_parameter_written = False
        self.write_checkbutton_var = {}
        self.root = tk.Tk()
        self.root.title("Amilcar Lucas's - ArduPilot methodic configurator - " + version)
        self.root.geometry("880x500") # Set the window width

        # Set the theme to 'alt'
        style = ttk.Style()
        style.theme_use('alt')

        # Bind the close_connection_and_quit function to the window close event
        self.root.protocol("WM_DELETE_WINDOW", self.close_connection_and_quit)
        
        # Set the application icon for the window and all child windows
        # https://pythonassets.com/posts/window-icon-in-tk-tkinter/
        #self.root.iconbitmap(default='ArduPilot_32x32.ico')
        self.root.iconphoto(True, tk.PhotoImage(file='ArduPilot_32x32.png'))

        config_frame = tk.Frame(self.root)
        config_frame.pack(side=tk.TOP, fill="x", expand=False, pady=(4, 0)) # Pack the frame at the top of the window

        config_subframe = tk.Frame(config_frame)
        config_subframe.pack(side=tk.LEFT, fill="x", expand=True, anchor=tk.NW) # Pack the frame at the top of the window

        # Get the background color for the 'TFrame' widget
        self.default_background_color = '#f0f0f0' # style.lookup('TFrame', 'background')

        # Configure the background color for the checkbutton
        style.configure('TCheckbutton', background=self.default_background_color)
        style.configure('TCombobox', background=self.default_background_color)

        # Create a new frame inside the config_subframe for the intermediate parameter file directory selection labels and directory selection button
        directory_selection_frame = tk.Frame(config_subframe)
        directory_selection_frame.pack(side=tk.LEFT, fill="x", expand=False, padx=(4, 6))

        # Create a description label for the directory
        directory_selection_label = tk.Label(directory_selection_frame, text="Vehicle directory:")
        directory_selection_label.pack(side=tk.TOP, anchor=tk.NW) # Add the label to the top of the directory_selection_frame

        # Create a new subframe for the directory selection
        directory_selection_subframe = tk.Frame(directory_selection_frame)
        directory_selection_subframe.pack(side=tk.TOP, fill="x", expand=False, anchor=tk.NW)

        # Create a read-only entry for the directory
        vehicle_directory_name = self.local_filesystem.get_vehicle_directory_name()
        vehicle_dir_var = tk.StringVar(value=vehicle_directory_name)
        self.directory_entry = tk.Entry(directory_selection_subframe, textvariable=vehicle_dir_var,
                                        width=max(4, len(vehicle_directory_name)), state='readonly')
        self.directory_entry.pack(side=tk.LEFT, fill="x", expand=True, anchor=tk.NW, pady=(4, 0))
        show_tooltip(self.directory_entry,
                     "Vehicle-specific directory containing the intermediate\nparameter files to be written to the flight "
                     "controller")

        # Create a button for directory selection
        directory_selection_button = ttk.Button(directory_selection_subframe, text="...",
                                                command=self.on_select_vehicle_directory, width=2)
        directory_selection_button.pack(side=tk.RIGHT, anchor=tk.NW)
        show_tooltip(directory_selection_button, "Select the vehicle-specific directory containing the\nintermediate "
                     "parameter files to be written to the flight controller")

        # Create a new frame inside the config_subframe for the intermediate parameter file selection label and combobox
        file_selection_frame = tk.Frame(config_subframe)
        file_selection_frame.pack(side=tk.LEFT, fill="x", expand=False, padx=(6, 6))

        # Create a label for the combobox
        file_selection_label = tk.Label(file_selection_frame, text="Current intermediate parameter file:")
        file_selection_label.pack(side=tk.TOP, anchor=tk.NW) # Add the label to the top of the file_selection_frame

        # Create combobox for intermediate parameter file selection
        self.file_selection_combobox = AutoResizeCombobox(file_selection_frame,
                                                          list(local_filesystem.file_parameters.keys()),
                                                          current_file,
                                                          "Select the intermediate parameter file from the list of available "
                                                          "files in the selected vehicle directory\nIt will automatically "
                                                          "advance to the next file once the current file is written to the "
                                                          "fight controller",
                                                          state='readonly', width=45)
        self.file_selection_combobox.bind("<<ComboboxSelected>>", self.on_param_file_combobox_change)
        self.file_selection_combobox.pack(side=tk.TOP, anchor=tk.NW, pady=(4, 0)) # Add the combobox below the label in the file_selection_frame

        # Create a new frame inside the config_subframe for the flight controller connection selection label and combobox
        conn_selection_frame = tk.Frame(config_subframe)
        conn_selection_frame.pack(side=tk.RIGHT, fill="x", expand=False, padx=(6, 4))

        # Create a description label for the flight controller connection selection
        conn_selection_label = tk.Label(conn_selection_frame, text="flight controller connection:")
        conn_selection_label.pack(side=tk.TOP, anchor=tk.NW) # Add the label to the top of the conn_selection_frame

        # Create a read-only combobox for flight controller connection selection
        self.conn_selection_combobox = PairTupleCombobox(conn_selection_frame, self.flight_controller.get_connection_tuples(),
                                                         self.flight_controller.comport.device if \
                                                            hasattr(self.flight_controller.comport, "device") else None,
                                                            state='readonly')
        self.conn_selection_combobox.bind("<<ComboboxSelected>>", self.on_select_connection_combobox_change)
        self.conn_selection_combobox.pack(side=tk.TOP, anchor=tk.NW, pady=(4, 0)) # Add the combobox below the label in the conn_selection_frame
        show_tooltip(self.conn_selection_combobox, "Select the flight controller connection\nYou can add a custom connection "
                     "to the existing ones")

        # Load the ArduPilot logo and scale it down to image_height pixels in height
        image_height = 40
        image = Image.open('ArduPilot.png')
        width, height = image.size
        aspect_ratio = width / height
        new_width = int(image_height * aspect_ratio)
        resized_image = image.resize((new_width, image_height))

        # Convert the image to a format that can be used by Tkinter
        photo = ImageTk.PhotoImage(resized_image)

        # Create a label with the resized image
        image_label = tk.Label(config_frame, image=photo)
        image_label.image = photo # Keep a reference to the image to prevent it from being garbage collected
        image_label.pack(side=tk.RIGHT, anchor=tk.NE, padx=(4, 4), pady=(4, 0))

        # Create a Frame for the Documentation Content
        documentation_frame = tk.LabelFrame(self.root, text="Documentation")
        documentation_frame.pack(side=tk.TOP, fill="x", expand=False, pady=(4, 4), padx=(4, 4))

        # Create a grid structure within the documentation_frame
        documentation_grid = tk.Frame(documentation_frame)
        documentation_grid.pack(fill="both", expand=True)

        # Create labels for the first column with static descriptive text
        descriptive_texts = ["Forum Blog:", "Wiki:", "External tool:", "Mandatory:"]
        descriptive_tooltips = ["ArduPilot's forum Methodic configuration Blog post relevant for the current file",
                                "ArduPilot's wiki page relevant for the current file",
                                "External tool or documentation relevant for the current file",
                                "Mandatory level of the current file,\n 100% you MUST use this file to configure the "
                                "vehicle,\n 0% you can ignore this file if it does not apply to your vehicle"]
        for i, text in enumerate(descriptive_texts):
            label = tk.Label(documentation_grid, text=text)
            label.grid(row=i, column=0, sticky="w")
            show_tooltip(label, descriptive_tooltips[i])

        # Create labels for the second column with the documentation links
        self.documentation_label_blog = tk.Label(documentation_grid)
        self.documentation_label_wiki = tk.Label(documentation_grid)
        self.documentation_label_extra = tk.Label(documentation_grid)
        self.documentation_label_mandatory = tk.Label(documentation_grid)

        # Grid the documentation labels in the second column
        self.documentation_label_blog.grid(row=0, column=1, sticky="w")
        self.documentation_label_wiki.grid(row=1, column=1, sticky="w")
        self.documentation_label_extra.grid(row=2, column=1, sticky="w")
        self.documentation_label_mandatory.grid(row=3, column=1, sticky="w")

        # Dynamically update the documentation text and URL links
        self.update_documentation_labels()

        self.show_only_differences = tk.BooleanVar(value=False)

        # Create a Frame for the Scrollable Content
        self.scroll_frame = ScrollFrame(self.root)
        self.repopulate_parameter_table(current_file)
        self.scroll_frame.pack(side="top", fill="both", expand=True)

        # Create a frame for the buttons
        buttons_frame = tk.Frame(self.root)
        buttons_frame.pack(side="bottom", fill="x", expand= False, pady=(10, 10))

        # Create checkbox for toggling parameter display
        only_changed_checkbox = ttk.Checkbutton(buttons_frame, text="See only changed parameters",
                                                variable=self.show_only_differences,
                                                command=self.on_show_only_changed_checkbox_change)
        only_changed_checkbox.pack(side=tk.LEFT, padx=(8, 8))
        show_tooltip(only_changed_checkbox, "Toggle to show only parameters that will change if/when written to the flight "
                     "controller")

        # Create write button
        write_selected_button = tk.Button(buttons_frame, text="Write selected params to FC, and advance to next param file",
                                          command=self.on_write_selected_click)
        write_selected_button.pack(side=tk.LEFT, padx=(8, 8)) # Add padding on both sides of the write selected button
        show_tooltip(write_selected_button, "Write selected parameters to the flight controller and advance to the next "
                     "intermediate parameter file\nIf changes have been made to the current file it will ask if you want "
                     "to save them\nIt will reset the FC if necessary, re-read all parameters and validate their value")

        # Create skip button
        skip_button = tk.Button(buttons_frame, text="Skip parameter file", command=self.on_skip_click)
        skip_button.pack(side=tk.RIGHT, padx=(8, 8)) # Add right padding to the skip button
        show_tooltip(skip_button, "Skip to the next intermediate parameter file without writing any changes to the flight "
                     "controller\nIf changes have been made to the current file it will ask if you want to save them")

        self.root.after(50, self.read_flight_controller_parameters(reread=False)) # 50 milliseconds
        self.root.mainloop()


    @staticmethod
    def update_combobox_width(combobox):
        # Calculate the maximum width needed for the content
        max_width = max(len(value) for value in combobox['values'])
        # Set a minimum width for the combobox
        min_width = 4 # Adjust this value as needed
        # Set the width of the combobox to the maximum width, but not less than the minimum width
        combobox.config(width=max(min_width, max_width))


    def on_select_vehicle_directory(self):
        # Open the directory selection dialog
        selected_directory = filedialog.askdirectory(initialdir=self.local_filesystem.vehicle_dir)
        if selected_directory:
            self.local_filesystem.vehicle_dir = selected_directory
            displayed_directory = self.local_filesystem.get_vehicle_directory_name()
            # Set the width of the directory_entry to match the width of the displayed_directory text
            self.directory_entry.config(width=max(4, len(displayed_directory)), state='normal')
            self.directory_entry.delete(0, tk.END)
            self.directory_entry.insert(0, displayed_directory)
            self.directory_entry.config(state='readonly')
            self.root.update_idletasks()
            # Update the local_filesystem with the new directory
            self.local_filesystem.re_init(selected_directory, self.local_filesystem.vehicle_type)
            files = list(self.local_filesystem.file_parameters.keys())
            if files:
                self.file_selection_combobox.set_entries_tupple(files, files[0])
                # Trigger the combobox change event to update the table
                self.on_param_file_combobox_change(None, forced=True)
            else:
                # No files were found in the selected directory
                show_no_param_files_error(selected_directory)


    def on_param_file_combobox_change(self, _event, forced: bool = False):
        if not self.file_selection_combobox['values']:
            return
        self.param_edit_widgets_event_generate_focus_out()
        selected_file = self.file_selection_combobox.get()
        if self.current_file != selected_file or forced:
            self.write_changes_to_intermediate_parameter_file()
            # Update the current_file attribute to the selected file
            self.current_file = selected_file
            self.at_least_one_changed_parameter_written = False
            self.update_documentation_labels()
            self.repopulate_parameter_table(selected_file)


    def on_select_connection_combobox_change(self, _event):
        selected_connection = self.conn_selection_combobox.getSelectedKey()
        logging_debug(f"Connection combobox changed to: {selected_connection}")
        if self.flight_controller.master is None or selected_connection != self.flight_controller.comport.device:
            if selected_connection == 'Add another':
                self.on_add_connection(None)
                return
            self.reconnect(selected_connection)


    def on_add_connection(self, _event):
        # Open the connection selection dialog
        selected_connection = simpledialog.askstring("Flight Controller Connection",
                                                     "Enter the connection string to the flight controller. "
                                                     "Examples are:\n\nCOM4 (on windows)\n"
                                                     "/dev/serial/by-id/usb-xxx (on linux)\n"
                                                     "tcp:127.0.0.1:5761\n"
                                                     "udp:udp:127.0.0.1:14551")
        logging_debug(f"Will add new connection: {selected_connection} if not duplicated")
        self.flight_controller.add_connection(selected_connection)
        connection_tuples = self.flight_controller.get_connection_tuples()
        logging_debug(f"Updated connection tuples: {connection_tuples} with selected connection: {selected_connection}")
        self.conn_selection_combobox.set_entries_tupple(connection_tuples, selected_connection)
        self.reconnect(selected_connection)


    def reconnect(self, selected_connection: str = None):
        if selected_connection:
            [self.connection_progress_window,
            self.connection_progress_bar,
            self.connection_progress_label] = self.create_progress_window("Connecting with the FC")
            error_message = self.flight_controller.connect(selected_connection, self.update_connection_progress_bar)
            if error_message:
                show_no_connection_error(error_message)
                return
            self.connection_progress_window.destroy()


    def read_flight_controller_parameters(self, reread: bool = False):
        [self.param_read_progress_window,
        self.param_read_progress_bar,
        self.param_read_progress_label] = self.create_progress_window(("Re-r" if reread else "R") + "eading FC parameters")
        # Download all parameters from the flight controller
        self.flight_controller.fc_parameters = self.flight_controller.read_params(self.update_param_download_progress_bar)
        self.param_read_progress_window.destroy()  # for the case that we are doing test and there is no real FC connected
        if not reread:
            self.on_param_file_combobox_change(None, True) # the initial param read will trigger a table update


    def get_documentation_text_and_url(self, documentation, text_key, url_key):
        if documentation:
            text = documentation.get(text_key, f"No documentation available for {self.current_file} in the "
                                     f"{self.local_filesystem.file_documentation_filename} file")
            url = documentation.get(url_key, None)
        else:
            text = f"File '{self.local_filesystem.file_documentation_filename}' not found. No intermediate parameter " \
                "file documentation available"
            url = None
        return text, url


    def update_documentation_label(self, label, text, url, url_expected = True):
        if url:
            label.config(text=text, fg="blue", cursor="hand2", underline=True)
            label.bind("<Button-1>", lambda event, url=url: webbrowser_open(url))
            show_tooltip(label, url)
        else:
            label.config(text=text, fg="black", cursor="arrow", underline=False)
            label.bind("<Button-1>", lambda event: None)
            if url_expected:
                show_tooltip(label, "Documentation URL not available")


    def update_documentation_labels(self):
        documentation = self.local_filesystem.file_documentation.get(self.current_file, None) if \
            self.local_filesystem.file_documentation else None
        
        blog_text, blog_url = self.get_documentation_text_and_url(documentation, 'blog_text', 'blog_url')
        self.update_documentation_label(self.documentation_label_blog, blog_text, blog_url)
        wiki_text, wiki_url = self.get_documentation_text_and_url(documentation, 'wiki_text', 'wiki_url')
        self.update_documentation_label(self.documentation_label_wiki, wiki_text, wiki_url)
        external_tool_text, external_tool_url = self.get_documentation_text_and_url(documentation, 'external_tool_text',
                                                                                    'external_tool_url')
        self.update_documentation_label(self.documentation_label_extra, external_tool_text, external_tool_url)
        mandatory_text, mandatory_url = self.get_documentation_text_and_url(documentation, 'mandatory_text', 'mandatory_url')
        self.update_documentation_label(self.documentation_label_mandatory, mandatory_text, mandatory_url, False)


    def repopulate_parameter_table(self, selected_file):
        if not selected_file:
            return  # no file was yet selected, so skip it
        if not hasattr(self.flight_controller, 'fc_parameters'):
            return  # no file was yet selected, so skip it
        if not self.flight_controller.fc_parameters:
            return  # no file was yet selected, so skip it
        # Different parameters based on the threshold
        different_params = {param_name: file_value for param_name, file_value in
                            self.local_filesystem.file_parameters[selected_file].items()
                            if param_name in self.flight_controller.fc_parameters and \
                                not is_within_tolerance(self.flight_controller.fc_parameters[param_name],
                                                        float(file_value.value))}
        if not different_params and self.show_only_differences.get():
            logging_info("No different parameters found in %s. Skipping...", selected_file)
            messagebox.showinfo("ArduPilot methodic configurator",
                                f"No different parameters found in {selected_file}. Skipping...")
            self.on_skip_click(force_focus_out_event=False)
            return
        # Clear the current table
        for widget in self.scroll_frame.viewPort.winfo_children():
            widget.destroy()
        # Repopulate the table with the new parameters
        if self.show_only_differences.get():
            self.update_table(different_params)
        else:
            self.update_table(self.local_filesystem.file_parameters[selected_file])
        # Scroll to the top of the parameter table
        self.scroll_frame.canvas.yview("moveto", 0)


    def update_table(self, params):       
        # Create labels for table headers
        headers = ["Parameter", "Current Value", "New Value", "Unit", "Write", "Change Reason"]
        tooltips = ["Parameter name must be ^[A-Z][A-Z_0-9]* and most 16 characters long",
                    "Current value on the flight controller ",
                    "New value from the above selected intermediate parameter file",
                    "Parameter Unit",
                    "When selected, write new value to the flight controller",
                    "Reason why respective parameter changed"]
        for i, header in enumerate(headers):
            label = tk.Label(self.scroll_frame.viewPort, text=header)
            label.grid(row=0, column=i, sticky="ew") # Use sticky="ew" to make the label stretch horizontally
            show_tooltip(label, tooltips[i])

        self.write_checkbutton_var = {}
        try:
            # Create the new table
            for i, (param_name, param_value) in enumerate(params.items()):
                param_metadata = self.local_filesystem.doc_dict.get(param_name, None)

                is_calibration = param_metadata.get('Calibration', False) if param_metadata else False
                is_readonly = param_metadata.get('ReadOnly', False) if param_metadata else False
                parameter_label = tk.Label(self.scroll_frame.viewPort, text=param_name + (" " * (16 - len(param_name))),
                                           background="red" if is_readonly else "yellow" if is_calibration else \
                                            self.default_background_color)
                if param_name in self.flight_controller.fc_parameters:
                    flightcontroller_value = tk.Label(self.scroll_frame.viewPort, text=format(
                        self.flight_controller.fc_parameters[param_name], '.6f'))
                else:
                    flightcontroller_value = tk.Label(self.scroll_frame.viewPort, text="N/A", background="blue")
                
                new_value_entry = tk.Entry(self.scroll_frame.viewPort, width=10, justify=tk.RIGHT, background="white")
                new_value_entry.insert(0, param_value.value)
                new_value_entry.bind("<FocusOut>", lambda event, current_file=self.current_file, param_name=param_name:
                                     self.on_parameter_value_change(event, current_file, param_name))

                unit_label = tk.Label(self.scroll_frame.viewPort, text=param_metadata.get('unit') if param_metadata else "")

                self.write_checkbutton_var[param_name] = tk.BooleanVar(value=True) # Default to selected
                write_write_checkbutton = ttk.Checkbutton(self.scroll_frame.viewPort,
                                                          variable=self.write_checkbutton_var[param_name])

                change_reason_entry = tk.Entry(self.scroll_frame.viewPort, background="white")
                change_reason_entry.insert(0, "" if param_value.comment is None else param_value.comment)
                change_reason_entry.bind("<FocusOut>", lambda event, current_file=self.current_file, param_name=param_name:
                                         self.on_parameter_change_reason_change(event, current_file, param_name))

                doc_tooltip = param_metadata.get('doc_tooltip') if param_metadata else \
                    "No documentation available in apm.pdef.xml for this parameter"
                if doc_tooltip:
                    show_tooltip(parameter_label, doc_tooltip)
                    show_tooltip(flightcontroller_value, doc_tooltip)
                    show_tooltip(new_value_entry, doc_tooltip)
                unit_tooltip = param_metadata.get('unit_tooltip') if param_metadata else \
                    "No documentation available in apm.pdef.xml for this parameter"
                if unit_tooltip:
                    show_tooltip(unit_label, unit_tooltip)
                show_tooltip(write_write_checkbutton, f'When selected write {param_name} new value to the flight controller')
                show_tooltip(change_reason_entry, f'Reason why {param_name} should change to {new_value_entry.get()}')
                
                row = [
                    parameter_label,
                    flightcontroller_value,
                    new_value_entry,
                    unit_label,
                    write_write_checkbutton,
                    change_reason_entry,
                ]
                for j, widget in enumerate(row):
                    widget.grid(row=i+1, column=j, sticky="w" if j == 0 else "ew" if j == 5 else "e") # Use sticky="ew" to make the widget stretch horizontally
        except KeyError as e:
            logging_error("Parameter %s not found in the %s file: %s", param_name, self.current_file, e, exc_info=True)
            exit(1)

        # Configure the table_frame to stretch columns
        self.scroll_frame.viewPort.columnconfigure(0, weight=0, minsize=120) # Parameter name
        self.scroll_frame.viewPort.columnconfigure(1, weight=0) # Current Value
        self.scroll_frame.viewPort.columnconfigure(2, weight=0) # New Value
        self.scroll_frame.viewPort.columnconfigure(3, weight=0) # Units
        self.scroll_frame.viewPort.columnconfigure(4, weight=0) # write to FC
        self.scroll_frame.viewPort.columnconfigure(5, weight=1) # Change reason


    def on_parameter_value_change(self, event, current_file, param_name):
        # Get the new value from the Entry widget
        new_value = event.widget.get()
        try:
            old_value = self.local_filesystem.file_parameters[current_file][param_name].value
        except KeyError as e:
            logging_error("Parameter %s not found in the %s file: %s", param_name, current_file, e, exc_info=True)
            exit(1)
        valid = True
        # Check if the input is a valid float
        try:
            P = float(new_value)
            changed = not is_within_tolerance(old_value, P)
            param_metadata = self.local_filesystem.doc_dict.get(param_name, None)
            p_min = param_metadata.get('min', None) if param_metadata else None
            p_max = param_metadata.get('max', None) if param_metadata else None
            if changed:
                if p_min and P < p_min:
                    if not messagebox.askyesno("Out-of-bounds Value",
                                               f"The value for {param_name} {P} should be greater than {p_min}\n"
                                               "Use out-of-bounds value?", icon='warning'):
                        valid = False
                if p_max and P > p_max:
                    if not messagebox.askyesno("Out-of-bounds Value",
                                               f"The value for {param_name} {P} should be smaller than {p_max}\n"
                                               "Use out-of-bounds value?", icon='warning'):
                        valid = False
        except ValueError:
            # Optionally, you can handle the invalid value here, for example, by showing an error message
            messagebox.showerror("Invalid Value", f"The value for {param_name} must be a valid float.")
            valid = False
        if valid:
            if changed and not self.at_least_one_param_edited:
                logging_debug("Parameter %s changed, will later ask if change(s) should be saved to file.", param_name)
            self.at_least_one_param_edited = changed or self.at_least_one_param_edited
            # Update the params dictionary with the new value
            self.local_filesystem.file_parameters[current_file][param_name].value = P
        else:
            # Revert to the previous (valid) value
            event.widget.delete(0, tk.END)
            event.widget.insert(0, old_value)


    def on_parameter_change_reason_change(self, event, current_file, param_name):
        # Get the new value from the Entry widget
        new_value = event.widget.get()
        try:
            changed = new_value != self.local_filesystem.file_parameters[current_file][param_name].comment and \
                not (new_value == "" and self.local_filesystem.file_parameters[current_file][param_name].comment is None)
        except KeyError as e:
            logging_error("Parameter %s not found in the %s file %s: %s", param_name, self.current_file,
                          new_value, e, exc_info=True)
            exit(1)
        if changed and not self.at_least_one_param_edited:
            logging_debug("Parameter %s change reason changed from %s to %s, will later ask if change(s) should be saved to file.",
                          param_name, self.local_filesystem.file_parameters[current_file][param_name].comment, new_value)
        self.at_least_one_param_edited = changed or self.at_least_one_param_edited
        # Update the params dictionary with the new value
        self.local_filesystem.file_parameters[current_file][param_name].comment = new_value


    def get_write_selected_params(self):
        selected_params = {}
        for param_name, checkbutton_state in self.write_checkbutton_var.items():
            if checkbutton_state.get():
                selected_params[param_name] = self.local_filesystem.file_parameters[self.current_file][param_name]
        return selected_params


    def on_show_only_changed_checkbox_change(self):
        self.repopulate_parameter_table(self.current_file)


    def create_progress_window(self, title: str):
        # Create a new window for the param_read progress bar
        progress_window = tk.Toplevel(self.root)
        progress_window.title(title)
        progress_window.geometry("300x80")

        # Center the param_read progress window on the main window
        self.center_window(progress_window, self.root)

        # Create a param_read progress bar
        progress_bar = ttk.Progressbar(progress_window, length=100, mode='determinate')
        progress_bar.pack(side=tk.TOP, fill=tk.X, expand=False, padx=(5, 5), pady=(10, 10))

        # Create a param_read label to display the progress message
        progress_label = tk.Label(progress_window, text="")
        progress_label.pack(side=tk.TOP, fill=tk.X, expand=False, pady=(10, 10))

        return progress_window, progress_bar, progress_label


    def center_window(self, window, parent):
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


    def update_connection_progress_bar(self, current_value: int, max_value: int):
        """
        Update the FC connection progress bar and the progress message with the current progress.

        Args:
            current_value (int): The current progress value.
            max_value (int): The maximum progress value.
        """
        self.connection_progress_window.lift()

        self.connection_progress_bar['value'] = current_value
        self.connection_progress_bar['maximum'] = max_value
        self.connection_progress_bar.update()

        # Update the reset progress message
        self.connection_progress_label.config(text=f"waiting for {current_value} of {max_value} seconds")

        # Close the reset progress window when the process is complete
        if current_value == max_value:
            self.connection_progress_window.destroy()


    def update_reset_progress_bar(self, current_value: int, max_value: int):
        """
        Update the FC reset progress bar and the progress message with the current progress.

        Args:
            current_value (int): The current progress value.
            max_value (int): The maximum progress value.
        """
        self.reset_progress_window.lift()

        self.reset_progress_bar['value'] = current_value
        self.reset_progress_bar['maximum'] = max_value
        self.reset_progress_bar.update()

        # Update the reset progress message
        self.reset_progress_label.config(text=f"waiting for {current_value} of {max_value} seconds")

        # Close the reset progress window when the process is complete
        if current_value == max_value:
            self.reset_progress_window.destroy()


    def update_param_download_progress_bar(self, current_value: int, max_value: int):
        """
        Update the FC parameter read progress bar the progress message with the current progress.

        Args:
            current_value (int): The current progress value.
            max_value (int): The maximum progress value.
        """
        self.param_read_progress_window.lift()

        self.param_read_progress_bar['value'] = current_value
        self.param_read_progress_bar['maximum'] = max_value
        self.param_read_progress_bar.update()

        # Update the param read progress message
        self.param_read_progress_label.config(text=f"Reading parameter {current_value} of {max_value}")

        # Close the param read progress window when the process is complete
        if current_value == max_value:
            self.param_read_progress_window.destroy()


    def param_edit_widgets_event_generate_focus_out(self):
        # Trigger the <FocusOut> event for all entry widgets to ensure all changes are processed
        for widget in self.scroll_frame.viewPort.winfo_children():
            if isinstance(widget, tk.Entry):
                widget.event_generate("<FocusOut>", when="now")


    def write_params_that_require_reset(self, selected_params: dict):
        """
        Write the selected parameters to the flight controller that require a reset.

        After the reset, the other parameters that do not require a reset, must still be written to the flight controller.
        """
        fc_reset_required = False
        fc_reset_unsure = []

        # Write each selected parameter to the flight controller
        for param_name, param_value in selected_params.items():
            try:
                logging_info("Parameter %s set to %f", param_name, param_value.value)
                if param_name not in self.flight_controller.fc_parameters or \
                    not is_within_tolerance(self.flight_controller.fc_parameters[param_name], param_value.value):
                    param_metadata = self.local_filesystem.doc_dict.get(param_name, None)
                    if param_metadata and param_metadata.get('RebootRequired', False):
                        self.flight_controller.set_param(param_name, float(param_value.value))
                        self.at_least_one_changed_parameter_written = True
                        if param_name in self.flight_controller.fc_parameters:
                            logging_info("Parameter %s changed from %f to %f, reset required", param_name,
                                         self.flight_controller.fc_parameters[param_name], param_value.value)
                        else:
                            logging_info("Parameter %s changed to %f, reset required", param_name, param_value.value)
                        fc_reset_required = True
                    # Check if any of the selected parameters have a _TYPE, _EN, or _ENABLE suffix
                    elif param_name.endswith(('_TYPE', '_EN', '_ENABLE')):
                        self.flight_controller.set_param(param_name, float(param_value.value))
                        self.at_least_one_changed_parameter_written = True
                        if param_name in self.flight_controller.fc_parameters:
                            logging_info("Parameter %s changed from %f to %f, possible reset required", param_name,
                                         self.flight_controller.fc_parameters[param_name], param_value.value)
                        else:
                            logging_info("Parameter %s changed to %f, possible reset required", param_name, param_value.value)
                        fc_reset_unsure.append(param_name)
            except ValueError as e:
                logging_error("Failed to set parameter %s: %s", param_name, e)
                messagebox.showerror("ArduPilot methodic configurator", f"Failed to set parameter {param_name}: {e}")
        
        if not fc_reset_required:
            if fc_reset_unsure:
                # Ask the user if they want to reset the ArduPilot
                fc_reset_required = messagebox.askyesno("Possible reset required", f"{(', ').join(fc_reset_unsure)} parameter"
                                                        "(s) potentially require a reset\nDo you want to reset the ArduPilot?")

        if fc_reset_required:
            [self.reset_progress_window,
            self.reset_progress_bar,
            self.reset_progress_label] = self.create_progress_window("Resetting Flight Controller")
            # Call reset_and_reconnect with a callback to update the reset progress bar and the progress message
            self.flight_controller.reset_and_reconnect(self.update_reset_progress_bar)
            self.reset_progress_window.destroy()  # for the case that we are doing test and there is no real FC connected


    def on_write_selected_click(self):
        self.param_edit_widgets_event_generate_focus_out()

        self.write_changes_to_intermediate_parameter_file()
        selected_params = self.get_write_selected_params()
        self.write_selected_params(selected_params)
        # Delete the parameter table and create a new one with the next file if available
        self.on_skip_click(force_focus_out_event=False)

    # This function can recurse multiple time if there is a write error
    def write_selected_params(self, selected_params):
        if selected_params:
            logging_info("Writing %d selected %s parameters to flight controller...", len(selected_params), self.current_file)

            self.write_params_that_require_reset(selected_params)

            # Write each selected parameter to the flight controller
            for param_name, param_value in selected_params.items():
                try:
                    self.flight_controller.set_param(param_name, param_value.value)
                    logging_info("Parameter %s set to %f", param_name, param_value.value)
                    if param_name not in self.flight_controller.fc_parameters or \
                        not is_within_tolerance(self.flight_controller.fc_parameters[param_name], param_value.value):
                        self.at_least_one_changed_parameter_written = True
                except ValueError as e:
                    logging_error("Failed to set parameter %s: %s", param_name, e)
                    messagebox.showerror("ArduPilot methodic configurator", f"Failed to set parameter {param_name}: {e}")

        else:
            logging_warning("No parameter was selected for write, will not write any parameter")
            messagebox.showwarning("No parameter was selected for write", "Will not write any parameter")

        if self.at_least_one_changed_parameter_written:
            # Re-Download all parameters, in case one of them changed, and to validate that all writes where successful
            self.read_flight_controller_parameters(True)
            logging_info("Re-read all parameters from the flight controller")

            # Validate that the read parameters are the same as the ones in the current_file
            param_write_error = []
            for param_name, param_value in selected_params.items():
                if param_name in self.flight_controller.fc_parameters and \
                    not is_within_tolerance(self.flight_controller.fc_parameters[param_name], float(param_value.value)):
                    logging_error("Parameter %s write to the flight controller failed. Expected: %f, Actual: %f",
                                    param_name, param_value.value, self.flight_controller.fc_parameters[param_name])
                    param_write_error.append(param_name)
                if param_name not in self.flight_controller.fc_parameters:
                    logging_error("Parameter %s write to the flight controller failed. Expected: %f, Actual: N/A",
                                    param_name, param_value.value)
                    param_write_error.append(param_name)

            if param_write_error:
                if messagebox.askretrycancel("Parameter write error",
                                             "Failed to write the following parameters to the flight controller:\n"
                                             f"{(', ').join(param_write_error)}"):
                    self.write_selected_params(selected_params)
            else:
                logging_info("All parameters written to the flight controller successfully")



    def on_skip_click(self, _event=None, force_focus_out_event=True):
        if force_focus_out_event:
            self.param_edit_widgets_event_generate_focus_out()
        self.write_changes_to_intermediate_parameter_file()
        # Find the next filename in the file_parameters dictionary
        files = list(self.local_filesystem.file_parameters.keys())
        if not files:
            return
        try:
            next_file_index = files.index(self.current_file) + 1
            if next_file_index >= len(files):
                self.write_summary_files()
                # Close the application and the connection
                self.close_connection_and_quit()
                return
            next_file = files[next_file_index]
            # Update the combobox selection to the next file
            self.file_selection_combobox.set(next_file)
            # Trigger the combobox change event to update the table
            self.on_param_file_combobox_change(None)
        except ValueError:
            # If the current file is not found in the list, present a message box
            messagebox.showerror("ArduPilot methodic configurator", "Current file not found in the list of files")
            # Close the application and the connection
            self.close_connection_and_quit()


    def write_changes_to_intermediate_parameter_file(self):
        if self.at_least_one_param_edited:
            if messagebox.askyesno("One or more parameters have been edited",
                                   f"Do you want to write the changes to the {self.current_file} file?"):
                self.local_filesystem.export_to_param(self.local_filesystem.file_parameters[self.current_file],
                                                      self.current_file)
        self.at_least_one_param_edited = False


    def write_summary_files(self):
        annotated_fc_parameters = self.local_filesystem.annotate_intermediate_comments_to_param_dict(
            self.flight_controller.fc_parameters)
        non_default__read_only_params, non_default__writable_calibrations, non_default__writable_non_calibrations = \
            self.local_filesystem.categorize_parameters(annotated_fc_parameters)

        nr_unchanged_params = len(annotated_fc_parameters) - len(non_default__read_only_params) - \
            len(non_default__writable_calibrations) - len(non_default__writable_non_calibrations)
        # If there are no more files, present a summary message box
        _summary_message = messagebox.showinfo("Last parameter file processed",
                                               f"Methodic configuration of {len(annotated_fc_parameters)} parameters complete:\n\n"
                                               f"{nr_unchanged_params} kept their default value\n\n"
                                               f"{len(non_default__read_only_params)} non-default read-only parameters - "
                                               f"ignore these, you can not change them\n\n"
                                               f"{len(non_default__writable_calibrations)} non-default writable sensor-"
                                               f"calibrations - non-reusable between vehicles\n\n"
                                               f"{len(non_default__writable_non_calibrations)} non-default writable non-sensor"
                                               f"-calibrations - these can be reused between similar vehicles")
        wrote_complete = self.write_summary_file(annotated_fc_parameters,
                                                 "complete.param", False)
        wrote_read_only = self.write_summary_file(non_default__read_only_params,
                                                  "non-default_read-only.param", False)
        wrote_calibrations = self.write_summary_file(non_default__writable_calibrations,
                                                     "non-default_writable_calibrations.param", False)
        wrote_non_calibrations = self.write_summary_file(non_default__writable_non_calibrations,
                                                         "non-default_writable_non-calibrations.param", False)
        self.write_zip_file(wrote_complete, wrote_read_only, wrote_calibrations, wrote_non_calibrations)


    def write_summary_file(self, param_dict: dict, filename: str, annotate_doc: bool):
        should_write_file = True
        if param_dict:
            if self.local_filesystem.intermediate_parameter_file_exists(filename):
                should_write_file = messagebox.askyesno("Overwrite existing file",
                                                        f"{filename} file already exists.\nDo you want to overwrite it?")
            if should_write_file:
                self.local_filesystem.export_to_param(param_dict, filename, annotate_doc)
                logging_info("Summary file %s written", filename)
        return should_write_file

    def write_zip_file(self, file1: bool, file2: bool, file3: bool, file4: bool):
        should_write_file = True
        if True or file1 or file2 or file3 or file4:
            zip_file_path = self.local_filesystem.zip_file_path()
            if self.local_filesystem.zip_file_exists():
                should_write_file = messagebox.askyesno("Overwrite existing file",
                                                        f"{zip_file_path} file already exists.\nDo you want to overwrite it?")
            if should_write_file:
                self.local_filesystem.zip_files(file1, "complete.param",
                                                file2, "non-default_read-only.param",
                                                file3, "non-default_writable_calibrations.param",
                                                file4, "non-default_writable_non-calibrations.param")
                messagebox.showinfo("Parameter files zipped", "All relevant files have been zipped into the \n"
                                    f"{zip_file_path} file.\n\nYou can now upload this file to the ArduPilot Methodic\n"
                                    "Configuration Blog post on discuss.ardupilot.org.")
        return should_write_file

    def close_connection_and_quit(self):
        self.root.quit() # Then stop the Tkinter event loop
