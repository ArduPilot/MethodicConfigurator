#!/usr/bin/env python3

"""
Configuration stage progress UI.

This module implements a graphical progress indicator for the ArduPilot Methodic
Configurator that visualizes the configuration process across multiple phases.

The UI consists of a horizontal sequence of progress bars, each representing a distinct
configuration phase. The phases are arranged left-to-right and are defined in a
configuration JSON file. Each phase:
- Shows its progress based on the current configuration file being processed
- Displays its name in a label below the progress bar
- Provides a tooltip with detailed phase description
- Can be marked as optional (shown in gray)
- Has a defined start point, with its end being the start of the next phase
  (or total files for the last phase)

The component is implemented as a ttk.LabelFrame containing individual frames for
each phase. Progress is tracked by file number (1 to N) across .param files being
processed. Phases without a start position are treated as milestones and are not
displayed.

Each phase's progress bar automatically:
- Remains empty (0%) before its start file is reached
- Shows relative progress while its files are being processed
- Fills completely (100%) after all its files are processed

The UI dynamically adjusts to window resizing while maintaining proportional spacing
between phases.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import argparse
import tkinter as tk
from logging import basicConfig as logging_basicConfig
from logging import error as logging_error
from logging import getLevelName as logging_getLevelName
from tkinter import ttk
from typing import Union

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_filesystem_configuration_steps import ConfigurationSteps
from ardupilot_methodic_configurator.common_arguments import add_common_arguments
from ardupilot_methodic_configurator.frontend_tkinter_show import show_tooltip


class StageProgressBar(ttk.LabelFrame):  # pylint: disable=too-many-ancestors
    """Stage-segmented Configuration sequence progress UI."""

    def __init__(
        self, master: Union[tk.Widget, tk.Tk], phases: dict[str, dict], total_steps: int, gui_complexity: str, **kwargs
    ) -> None:
        super().__init__(master, text=_("Configuration sequence progress"), **kwargs)
        self.phases = phases
        self.total_files = total_steps
        self.phase_frames: dict[str, ttk.Frame] = {}
        self.phase_bars: list[dict[str, Union[ttk.Progressbar, int]]] = []

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.create_phase_frames(gui_complexity)
        self.bind("<Configure>", self._on_resize)
        show_tooltip(
            self,
            _(
                "This bar shows your progress through the configuration phases. "
                "Each phase contains configuration steps that must be completed in sequence."
            ),
            position_below=False,
        )

    def create_phase_frames(self, gui_complexity: str) -> None:
        """Create frames for each phase with progress bars and labels."""
        # Get phases with start positions
        active_phases = {k: v for k, v in self.phases.items() if "start" in v}

        # Sort phases by start position
        sorted_phases = dict(sorted(active_phases.items(), key=lambda x: x[1]["start"]))

        # Add the end information to each phase using the start of the next phase
        phase_names = list(sorted_phases.keys())
        for i, phase_name in enumerate(phase_names):
            if i < len(phase_names) - 1:
                next_phase_name = phase_names[i + 1]
                sorted_phases[phase_name]["end"] = sorted_phases[next_phase_name]["start"]
            else:
                sorted_phases[phase_name]["end"] = self.total_files
            sorted_phases[phase_name]["weight"] = max(2, sorted_phases[phase_name]["end"] - sorted_phases[phase_name]["start"])

        # Calculate non-optional phases
        non_optional_sorted_phases = {name: data for name, data in sorted_phases.items() if not data.get("optional", False)}

        phases_to_display = non_optional_sorted_phases if gui_complexity == "simple" else sorted_phases

        # Create container frame that will expand
        container = ttk.Frame(self)
        container.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # Configure container columns to expand equally
        for i, (phase_name, phase_data) in enumerate(phases_to_display.items()):
            container.grid_columnconfigure(
                i, weight=phase_data["weight"] if gui_complexity == "simple" else 1, uniform="phase"
            )
            start = phase_data["start"]
            end = phase_data["end"]
            self.phase_frames[phase_name] = self._create_phase_frame(container, i, phase_name, phase_data, (start, end))

    def _create_phase_frame(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self, container: ttk.Frame, i: int, phase_name: str, phase_data: dict[str, Union[str, bool]], limits: tuple[int, int]
    ) -> ttk.Frame:
        frame = ttk.Frame(container)
        frame.grid(row=0, column=i, sticky="nsew", padx=1)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=0)  # Progress bar row
        frame.grid_rowconfigure(1, weight=1)  # Label row

        progress = ttk.Progressbar(frame, orient=tk.HORIZONTAL, mode="determinate", maximum=limits[1] - limits[0])
        progress.grid(row=0, column=0, sticky="ew", pady=2)
        self.phase_bars.append({"bar": progress, "start": limits[0], "end": limits[1]})

        label_text = _(phase_name) if phase_name else ""
        first_space = label_text.find(" ")
        if "\n" not in label_text:
            if 6 <= first_space < 20:
                label_text = label_text.replace(" ", "\n", 1)
            if len(label_text) < 20:
                label_text += "\n "

        # Use gray text color if phase is marked as optional
        is_optional = False
        if "optional" in phase_data and isinstance(phase_data["optional"], bool):
            is_optional = phase_data.get("optional", False)  # type: ignore[assignment]
        label_fg = "gray" if is_optional else "black"

        label = ttk.Label(
            frame,
            text=label_text,
            wraplength=0,  # Will be updated in _on_resize
            justify=tk.CENTER,
            anchor="center",
            foreground=label_fg,
        )
        label.grid(row=1, column=0, sticky="ew")

        if "description" in phase_data and isinstance(phase_data["description"], str):
            tooltip_msg = _(phase_data.get("description", ""))  # type: ignore[arg-type]
            if is_optional:
                tooltip_msg += "\n" + _("This phase is optional.")
            show_tooltip(frame, tooltip_msg)
        return frame

    def _on_resize(self, _event: Union[tk.Event, None] = None) -> None:
        """Update progress bar and label widths when window is resized."""
        if not self.phase_frames:
            return

        # Calculate new width per phase
        num_phases = len(self.phase_frames)
        padding = 4  # Account for frame padding
        new_width = max(1, (self.winfo_width() - padding) // num_phases)

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
        if not 0 < current_file < self.total_files:
            msg = _("Out of expected range [0 .. {self.total_files}] current file number: {current_file}")
            msg = msg.format(self=self, current_file=current_file)
            logging_error(msg)
            return

        for phase in self.phase_bars:
            if (  # pylint: disable=too-many-boolean-expressions
                "start" in phase
                and "end" in phase
                and "bar" in phase
                and isinstance(phase["start"], int)
                and isinstance(phase["end"], int)
                and isinstance(phase["bar"], ttk.Progressbar)
            ):
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

    progress = StageProgressBar(root, config_steps.configuration_phases, 54, "normal")
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
