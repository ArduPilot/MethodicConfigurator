import tkinter as tk
from tkinter import ttk
import json


def load_json_data(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
    return data


def save_json_data(file_path, data):
    with open(file_path, 'w') as file:
        json.dump(data, file, indent=4)


class JsonEditorApp(tk.Tk):
    def __init__(self, json_file_path):
        super().__init__()
        self.title("Vehicle Component Editor")
        self.json_file_path = json_file_path
        self.data = load_json_data(self.json_file_path)
        self.entry_widgets = {} # Dictionary for entry widgets

        self.main_frame = ttk.Frame(self)
        self.main_frame.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)

        self.populate_frames()

        self.save_button = ttk.Button(self, text="Save", command=self.save_data)
        self.save_button.pack(pady=10)

    def populate_frames(self):
        for key, value in self.data.items():
            self.add_frame(self.main_frame, key, value, [])

    def add_frame(self, parent, key, value, path):
        # Only create a frame if the value is a dictionary or if it's a top-level key
        if isinstance(value, dict) or parent == self.main_frame:
            frame = ttk.LabelFrame(parent, text=key)
            frame.pack(fill=tk.X, pady=5)
            parent_for_entries = frame
        else:
            parent_for_entries = parent

        if isinstance(value, dict):
            path += [key]
            for sub_key, sub_value in value.items():
                self.add_frame(parent_for_entries, sub_key, sub_value, path)
        else:
            self.add_entry(parent_for_entries, key, value, path)

    def add_entry(self, parent, key, value, path):
        label = ttk.Label(parent, text=key)
        label.pack(side=tk.LEFT)

        entry = ttk.Entry(parent)
        entry.insert(0, str(value))
        entry.pack(side=tk.LEFT, expand=True, fill=tk.X)

        # Store the entry widget in the entry_widgets dictionary for later retrieval
        self.entry_widgets[tuple(path+[key])] = entry

    def save_data(self):
        # Iterate over the entry_widgets dictionary
        for path, entry in self.entry_widgets.items():
            # Get the value from the entry widget
            value = entry.get()

            # Navigate through the nested dictionaries using the elements of path
            current_data = self.data
            for key in path[:-1]:
                current_data = current_data[key]

            # Update the value in the data dictionary
            current_data[path[-1]] = value

        # Save the updated data back to the JSON file
        save_json_data(self.json_file_path, self.data)
        print("Data saved successfully.")


if __name__ == "__main__":
    json_file_path = "Frame Diatone Taycan MX-C.json" # Adjust the path as necessary
    app = JsonEditorApp(json_file_path)
    app.mainloop()
