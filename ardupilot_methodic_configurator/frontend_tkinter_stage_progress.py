#!/usr/bin/env python3

"""
Configuration stage progress UI.

Draw a progress bar that is segmented into multiple phases.
That bar is to display the configuration progress on the Ardupilot Methodic Configurator software.
The current progress is the current file number relative to the total of number of configuration steps (.param files).
The progress bar can be segmented into multiple bars, one for each configuration phase.
The start on the configuration phase is defined in the json file, it's end is before the start of the next phase.
Phases without a start are considered milestones and are to be ignored for now.
The toplevel object is to be derived from ttk.FrameLabel and it should contain multiple frames inside it.
One frame per stage, all create side-by-side, from left to right.
Each tk.Frame is contains the respective phase progress bar and a label with the name of the phase bellow it.
The description of the phase should be displayed as tooltip inside the entire frame.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import argparse
import tkinter as tk
from logging import basicConfig as logging_basicConfig
from logging import getLevelName as logging_getLevelName
from tkinter import ttk
from typing import Union

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_filesystem_configuration_steps import ConfigurationSteps
from ardupilot_methodic_configurator.common_arguments import add_common_arguments
from ardupilot_methodic_configurator.frontend_tkinter_base import show_tooltip


class StageProgressBar(ttk.LabelFrame):
    """Stage-segmented Configuration sequence progress UI."""

    def __init__(self, master: tk.Widget, phases: dict[str, dict], total_steps: int, **kwargs) -> None:
        super().__init__(master, text=_("Configuration sequence progress"), **kwargs)
        self.phases = phases
        self.total_files = total_steps
        self.phase_frames = {}
        self.phase_bars = []

        self.grid_columnconfigure(0, weight=1)
        self.create_phase_frames()

        self.bind("<Configure>", self._on_resize)

    def create_phase_frames(self) -> None:
        """Create frames for each phase with progress bars and labels."""
        # Get phases with start positions
        active_phases = {k: v for k, v in self.phases.items() if "start" in v}

        # Sort phases by start position
        sorted_phases = dict(sorted(active_phases.items(), key=lambda x: x[1]["start"]))

        num_phases = len(sorted_phases)

        # Create container frame that will expand
        container = ttk.Frame(self)
        container.pack(fill=tk.X, expand=True, padx=5, pady=5)

        # Configure columns to expand equally
        for i in range(num_phases):
            container.grid_columnconfigure(i, weight=1, uniform="phase")

        # Calculate segment lengths
        for i, (phase_name, phase_data) in enumerate(sorted_phases.items()):
            start = phase_data["start"]
            # End is either start of next phase or total files
            end = list(sorted_phases.values())[i + 1]["start"] if i < len(sorted_phases) - 1 else self.total_files
            segment_length = end - start

            frame = ttk.Frame(container)
            frame.grid(row=0, column=i, sticky="ew", padx=1)

            progress = ttk.Progressbar(frame, orient=tk.HORIZONTAL, mode="determinate", maximum=segment_length)
            progress.pack(fill=tk.X, pady=2)

            label_text = phase_name
            first_space = label_text.find(" ")
            if "\n" not in label_text and 6 <= first_space < 20:
                label_text = label_text.replace(" ", "\n", 1)
            if "\n" not in label_text and len(label_text) < 20:
                label_text += "\n "

            label = ttk.Label(
                frame,
                text=label_text,
                wraplength=0,  # Will be updated in _on_resize
                justify=tk.CENTER,
                anchor="center",
            )
            label.pack(fill=tk.X)

            self.phase_frames[phase_name] = frame
            show_tooltip(frame, phase_data.get("description", ""))
            self.phase_bars.append({"bar": progress, "start": start, "end": end})

    def _on_resize(self, _event: Union[tk.Event, None] = None) -> None:
        """Update progress bar and label widths when window is resized."""
        if not self.phase_frames:
            return

        # Calculate new width per phase
        num_phases = len(self.phase_frames)
        padding = 4  # Account for frame padding
        new_width = (self.winfo_width() - padding) // num_phases

        # Update wraplength for all labels
        for frame in self.phase_frames.values():
            for child in frame.winfo_children():
                if isinstance(child, ttk.Label):
                    child.configure(wraplength=new_width - padding)

    def update_progress(self, current_file: int) -> None:
        """
        Update progress bars based on current file number.

        Args:
            current_file: Current configuration file number

        Each bar will be:
        - Empty (0%) if current_file < start
        - Full (100%) if current_file > end
        - Show progress between start-end otherwise

        """
        for phase in self.phase_bars:
            if phase["start"] <= current_file <= phase["end"]:
                # Calculate progress within this phase
                progress = current_file - phase["start"]
                phase["bar"]["value"] = progress
            elif current_file > phase["end"]:
                # Phase complete
                phase["bar"]["value"] = phase["end"] - phase["start"]
            else:
                # Phase not started
                phase["bar"]["value"] = 0


def argument_parser() -> argparse.Namespace:
    """
    Parses command-line arguments for the script.

    This function sets up an argument parser to handle the command-line arguments for the script.

    Returns:
    argparse.Namespace: An object containing the parsed arguments.

    """
    parser = argparse.ArgumentParser(
        description=_(
            "ArduPilot methodic configurator is a Wizard-style GUI tool to configure "
            "ArduPilot parameters. This module shows configuration sequence progress in "
            "the form of a configuration-stage-segmented progress bar."
        )
    )
    return add_common_arguments(parser).parse_args()


def main() -> None:
    args = argument_parser()

    logging_basicConfig(level=logging_getLevelName(args.loglevel), format="%(asctime)s - %(levelname)s - %(message)s")

    root = tk.Tk()
    root.title("Configuration Progress")

    # Load phases from configuration
    config_steps = ConfigurationSteps("", "ArduCopter")
    config_steps.re_init("", "ArduCopter")

    progress = StageProgressBar(root, config_steps.configuration_phases, 54)
    progress.pack(padx=10, pady=10, fill="both", expand=True)

    # Demo update function
    current_file = 2

    def update_demo() -> None:
        nonlocal current_file
        progress.update_progress(current_file)
        current_file = 2 if current_file > 54 else current_file + 1
        root.after(1000, update_demo)

    # Start demo updates
    update_demo()

    root.mainloop()


if __name__ == "__main__":
    main()
