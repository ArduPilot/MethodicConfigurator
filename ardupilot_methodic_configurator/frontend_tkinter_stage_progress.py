#!/usr/bin/env python3

"""
Configuration stage progress UI.

Draw a progress bar that is segmented into multiple phases.
That bar is to display the configuration progress on the Ardupilot Methodic Configurator software.
The current progress is the current file number relative to the total of number of configuration steps (.param files).
The progress bar can be segmented into multiple bars, one for each configuration phase.
The start on the configuration phase is defined in the json file, it's end is before the start of the next phase.
Phases without a start are considered milestones and are to be ignored for now.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import argparse
import tkinter as tk
from logging import basicConfig as logging_basicConfig
from logging import getLevelName as logging_getLevelName
from tkinter import ttk

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.common_arguments import add_common_arguments
from ardupilot_methodic_configurator.backend_filesystem_configuration_steps import ConfigurationSteps


class StageProgress(ttk.Frame):
    """Stage progress UI."""

    def __init__(self, parent, phases: dict, total_steps: int) -> None:
        super().__init__(parent)
        self.phases = phases
        self.total_files = total_steps
        self.phase_bars = []
        self.create_phase_progress_bars()

    def create_phase_progress_bars(self) -> None:
        """Create segmented progress bars for each phase."""
        # Get phases with start positions
        active_phases = {k: v for k, v in self.phases.items() if "start" in v}

        # Sort phases by start position
        sorted_phases = dict(sorted(active_phases.items(), key=lambda x: x[1]["start"]))

        # Calculate segment lengths
        for i, (phase_name, phase_data) in enumerate(sorted_phases.items()):
            start = phase_data["start"]
            # End is either start of next phase or total files
            end = list(sorted_phases.values())[i + 1]["start"] if i < len(sorted_phases) - 1 else self.total_files
            length = end - start

            # Create progress bar for this phase
            progress_frame = ttk.Frame(self)
            progress_frame.pack(fill="x", padx=5, pady=2)

            label = ttk.Label(progress_frame, text=phase_name)
            label.pack(side="left", padx=5)

            progress = ttk.Progressbar(progress_frame, length=200, mode="determinate", maximum=length)
            progress.pack(side="left", fill="x", expand=True)

            self.phase_bars.append({"bar": progress, "start": start, "end": end})

    def update_progress(self, current_file: int) -> None:
        """Update progress bars based on current file number."""
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
            "ArduPilot methodic configurator is a GUI-based tool designed to simplify "
            "the management and visualization of ArduPilot parameters. It enables users "
            "to browse through various vehicle templates, edit parameter files, and "
            "apply changes directly to the flight controller. The tool is built to "
            "semi-automate the configuration process of ArduPilot for drones by "
            "providing a clear and intuitive interface for parameter management."
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

    progress = StageProgress(root, config_steps.configuration_phases, 53)
    progress.pack(padx=10, pady=10, fill="x")

    root.mainloop()


if __name__ == "__main__":
    main()
