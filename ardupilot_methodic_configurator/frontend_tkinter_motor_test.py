"""
GUI for motor test functionality.

This file implements the Tkinter frontend for the motor test sub-application following
the Model-View separation pattern defined in ARCHITECTURE_motor_test.md.

The MotorTestView class provides:
- Safety warnings and parameter configuration controls
- Frame type selection and motor diagram display
- Individual and sequential motor testing controls
- Real-time battery status monitoring
- SVG diagram rendering

The MotorTestWindow class provides a standalone window for development/testing.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
import tkinter.messagebox
from argparse import ArgumentParser, Namespace
from logging import debug as logging_debug
from logging import error as logging_error
from logging import info as logging_info
from logging import warning as logging_warning
from tkinter import Canvas, Frame, Label, ttk
from tkinter.messagebox import askyesno, showerror, showwarning
from tkinter.simpledialog import askfloat
from typing import Callable, Union

import tksvg

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.__main__ import (
    ApplicationState,
    initialize_flight_controller_and_filesystem,
    setup_logging,
)
from ardupilot_methodic_configurator.common_arguments import add_common_arguments
from ardupilot_methodic_configurator.data_model_motor_test import MotorTestDataModel
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_scroll_frame import ScrollFrame


class MotorTestView(Frame):  # pylint: disable=too-many-instance-attributes
    """GUI for motor test functionality."""

    def __init__(
        self,
        parent: Union[tk.Frame, ttk.Frame],
        model: MotorTestDataModel,
        root_window: Union[tk.Tk, tk.Toplevel],
    ) -> None:
        super().__init__(parent)
        self.model = model
        self.parent = parent
        self.root_window = root_window

        # Define attributes
        self.throttle_spinbox: ttk.Spinbox
        self.duration_spinbox: ttk.Spinbox
        self.frame_type_combobox: ttk.Combobox
        self.motor_buttons: list[ttk.Button] = []
        self.motor_status_labels: list[ttk.Label] = []  # Status labels for visual feedback
        self.detected_comboboxes: list[ttk.Combobox] = []
        self.diagram_canvas: Canvas
        self.batt_voltage_label: ttk.Label
        self.batt_current_label: ttk.Label
        self._current_svg_image = None  # Store SVG image reference
        self._first_motor_test = True  # Track if this is the first motor test

        self._create_widgets()

        # Try to refresh frame configuration from flight controller
        if not self.model.refresh_from_flight_controller():
            logging_warning(_("Could not refresh frame configuration from flight controller, using defaults"))

        self._update_view()

        # Setup keyboard shortcuts for critical functions
        self._setup_keyboard_shortcuts()

    def _create_widgets(self) -> None:
        """Create and place widgets in the frame."""
        # Main frame
        main_frame = ScrollFrame(self.parent)
        main_frame.pack(fill="both", expand=True)
        content_frame = main_frame.view_port

        # --- Safety Warnings ---
        warning_frame = ttk.LabelFrame(content_frame, text=_("Safety Warnings"))
        warning_frame.pack(padx=10, pady=10, fill="x")
        Label(
            warning_frame,
            text=_("PROPELLERS MUST BE REMOVED before proceeding!"),
            fg="red",
            font=("TkDefaultFont", 10, "bold"),
        ).pack(pady=5)
        ttk.Label(
            warning_frame,
            text=_("Ensure the vehicle is properly secured and cannot move."),
        ).pack(pady=5)

        # --- 1. Frame Configuration ---
        config_frame = ttk.LabelFrame(content_frame, text=_("1. Frame Configuration"))
        config_frame.pack(padx=10, pady=5, fill="x")

        # Frame Type
        frame_type_frame = ttk.Frame(config_frame)
        frame_type_frame.pack(fill="x", pady=5)
        ttk.Label(frame_type_frame, text=_("Frame Type:")).pack(side="left", padx=5)
        self.frame_type_combobox = ttk.Combobox(frame_type_frame, state="readonly")
        self.frame_type_combobox.pack(side="left", padx=5, expand=True, fill="x")
        self.frame_type_combobox.bind("<<ComboboxSelected>>", self._on_frame_type_change)

        self.diagram_canvas = Canvas(config_frame, width=400, height=300, bg="white")
        self.diagram_canvas.pack()

        # --- 2. Arm and Min Throttle Configuration ---
        motor_params_frame = ttk.LabelFrame(content_frame, text=_("2. Arm and Min Throttle Configuration"))
        motor_params_frame.pack(padx=10, pady=5, fill="x")

        button_frame = ttk.Frame(motor_params_frame)
        button_frame.pack(fill="x", pady=5)
        ttk.Button(
            button_frame,
            text=_("Set Motor Spin Arm"),
            command=self._set_motor_spin_arm,
        ).pack(side="left", padx=5)
        ttk.Button(
            button_frame,
            text=_("Set Motor Spin Min"),
            command=self._set_motor_spin_min,
        ).pack(side="left", padx=5)

        # --- 3. Motor Order/Direction Configuration ---
        testing_frame = ttk.LabelFrame(content_frame, text=_("3. Motor Order/Direction Configuration"))
        testing_frame.pack(padx=10, pady=5, fill="x")

        controls_frame = ttk.Frame(testing_frame)
        controls_frame.pack(fill="x", pady=5)

        ttk.Label(controls_frame, text=_("Throttle:")).pack(side="left", padx=4)
        self.throttle_spinbox = ttk.Spinbox(
            controls_frame, from_=1, to=100, increment=1, width=3, command=self._on_throttle_change
        )
        self.throttle_spinbox.pack(side="left", padx=2)
        ttk.Label(controls_frame, text="%").pack(side="left", padx=2)

        ttk.Label(controls_frame, text=_("Duration:")).pack(side="left", padx=4)
        self.duration_spinbox = ttk.Spinbox(
            controls_frame, from_=0.5, to=10, increment=0.5, width=4, command=self._on_duration_change
        )
        self.duration_spinbox.pack(side="left", padx=2)
        ttk.Label(controls_frame, text="s").pack(side="left", padx=2)

        self.batt_voltage_label = ttk.Label(controls_frame, text=_("Voltage: N/A"))
        self.batt_voltage_label.pack(side="left", padx=10)
        self.batt_current_label = ttk.Label(controls_frame, text=_("Current: N/A"))
        self.batt_current_label.pack(side="left", padx=10)

        motor_grid = ttk.Frame(testing_frame)
        motor_grid.pack(pady=10)
        self._create_motor_buttons(motor_grid)

        # --- Test Controls ---
        test_controls_frame = ttk.Frame(testing_frame)
        test_controls_frame.pack(pady=10)
        ttk.Button(test_controls_frame, text=_("Test All"), command=self._test_all_motors).pack(side="left", padx=5)
        ttk.Button(
            test_controls_frame,
            text=_("Test in Sequence"),
            command=self._test_motors_in_sequence,
        ).pack(side="left", padx=5)
        ttk.Button(test_controls_frame, text=_("Stop All Motors"), command=self._stop_all_motors).pack(side="right", padx=5)

    def _create_motor_buttons(self, parent: Union[Frame, ttk.Frame]) -> None:
        """Create the motor test buttons and detection comboboxes."""
        for i in range(self.model.get_motor_count()):
            motor_label = self.model.get_motor_labels()[i]
            motor_number = self.model.get_motor_numbers()[i]
            motor_direction = self.model.get_motor_directions()[i]

            motor_frame = ttk.Frame(parent)
            motor_frame.grid(row=i // 4, column=i % 4, padx=10, pady=5)

            def make_test_command(motor_num: int) -> Callable[[], None]:
                return lambda: self._test_motor(motor_num)

            button = ttk.Button(
                motor_frame,
                text=_("Test Motor %(label)s") % {"label": motor_label},
                command=make_test_command(motor_number),
            )
            button.pack()
            self.motor_buttons.append(button)

            # Show motor number and expected direction
            motor_text = _("Motor %(num)d %(dir)s") % {"num": motor_number, "dir": motor_direction}
            info_label = ttk.Label(motor_frame, text=motor_text)
            info_label.pack()

            ttk.Label(motor_frame, text=_("Detected:")).pack()
            combo = ttk.Combobox(motor_frame, values=self.model.get_motor_labels(), width=5)
            combo.pack()
            self.detected_comboboxes.append(combo)

            # Add status label for visual feedback
            status_label = ttk.Label(motor_frame, text=_("Ready"), foreground="blue")
            status_label.pack()
            self.motor_status_labels.append(status_label)

    def _update_view(self) -> None:
        """Update the view with data from the model."""
        self._update_frame_options()
        self._update_motor_buttons_layout()
        self._update_diagram()
        self._update_battery_status()
        self._update_spinbox_values()
        self.parent.after(1000, self._update_view)  # Schedule periodic update

    def _update_spinbox_values(self) -> None:
        """Update spinbox values from the data model."""
        try:
            # Update throttle spinbox
            throttle_pct = self.model.get_test_throttle_pct()
            self.throttle_spinbox.delete(0, "end")
            self.throttle_spinbox.insert(0, str(throttle_pct))

            # Update duration spinbox
            duration = self.model.get_test_duration()
            self.duration_spinbox.delete(0, "end")
            self.duration_spinbox.insert(0, str(duration))
        except Exception as e:  # pylint: disable=broad-exception-caught
            logging_error(_("Failed to update spinbox values: %(error)s"), {"error": str(e)})

    def _update_frame_options(self) -> None:
        """Update the frame type combobox options."""
        frame_options = self.model.get_frame_options()
        # Create flat list of options
        options = [
            f"{frame_class_name}: {frame_type_name}"
            for frame_class_name, types in frame_options.items()
            for frame_type_name in types.values()
        ]
        self.frame_type_combobox["values"] = options

        # Set current selection using data model
        current_frame_text = self.model.get_current_frame_selection_text()
        if current_frame_text in options:
            self.frame_type_combobox.set(current_frame_text)

    def _update_motor_buttons_layout(self) -> None:
        """Re-create motor buttons if motor count changes."""
        current_count = len(self.motor_buttons)
        required_count = self.model.get_motor_count()

        if current_count != required_count:
            # Clear existing widgets
            for button in self.motor_buttons:
                button.master.destroy()
            for combo in self.detected_comboboxes:
                combo.master.destroy()
            self.motor_buttons.clear()
            self.motor_status_labels.clear()
            self.detected_comboboxes.clear()

            # Find the motor grid frame by searching for it
            # This is more robust than hardcoded casting
            def find_motor_grid(parent: Union[Frame, ttk.Frame]) -> Union[Frame, ttk.Frame, None]:
                """Find a suitable motor grid frame."""
                for child in parent.winfo_children():
                    if isinstance(child, (Frame, ttk.Frame)):
                        # Check if this looks like our motor grid
                        grid_children = child.winfo_children()
                        if len(grid_children) == 0:  # Empty frame ready for motor buttons
                            return child
                        # Recursively search
                        result = find_motor_grid(child)
                        if result:
                            return result
                return None

            # Find the testing frame and create new motor grid
            testing_frame = None
            for child in self.parent.winfo_children():
                if hasattr(child, "cget") and "Motor Testing" in str(child.cget("text") if hasattr(child, "cget") else ""):
                    testing_frame = child
                    break

            if testing_frame and isinstance(testing_frame, (Frame, ttk.Frame)):
                motor_grid = find_motor_grid(testing_frame)
                if motor_grid:
                    self._create_motor_buttons(motor_grid)
                else:
                    logging_error(_("Could not find motor grid frame"))
            else:
                logging_error(_("Could not find testing frame"))

    def _update_diagram(self) -> None:
        """Update the motor diagram image."""
        self.diagram_canvas.delete("all")

        if self.model.motor_diagram_exists():
            diagram_path, error_msg = self.model.get_motor_diagram_path()

            if diagram_path and diagram_path.endswith(".svg"):
                try:
                    # Use tksvg to render SVG
                    svg_image = tksvg.SvgImage(file=diagram_path)
                    # Scale the image to fit the canvas
                    canvas_width = self.diagram_canvas.winfo_width() or 400
                    canvas_height = self.diagram_canvas.winfo_height() or 300

                    # Calculate scaling to fit within canvas while maintaining aspect ratio
                    svg_width = svg_image.width()
                    svg_height = svg_image.height()
                    _scale, scaled_height = self.model.get_svg_scaling_info(canvas_width, canvas_height, svg_width, svg_height)

                    if svg_width > 0 and svg_height > 0:
                        # Create scaled image
                        scaled_svg = tksvg.SvgImage(file=diagram_path, scaletoheight=scaled_height)
                        self.diagram_canvas.create_image(
                            canvas_width // 2, canvas_height // 2, image=scaled_svg, anchor="center"
                        )
                        # Keep a reference to prevent garbage collection
                        # Store in the view instance instead of canvas
                        self._current_svg_image = scaled_svg
                    else:
                        self.diagram_canvas.create_text(200, 150, text=_("Invalid SVG diagram"), fill="red")
                except Exception as e:  # pylint: disable=broad-exception-caught
                    logging_error(_("Error loading SVG diagram: %(error)s"), {"error": e})
                    self.diagram_canvas.create_text(200, 150, text=_("Error loading diagram"), fill="red")
            else:
                # Fallback: just show the path
                logging_error(error_msg)
                self.diagram_canvas.create_text(
                    200, 150, text=_("Diagram: %(path)s") % {"path": diagram_path}, fill="black", width=380
                )
        else:
            self.diagram_canvas.create_text(200, 150, text=_("Motor diagram not available."), fill="red")

    def _update_battery_status(self) -> None:
        """Update battery voltage and current labels."""
        voltage_text, current_text = self.model.get_battery_display_text()

        self.batt_voltage_label.config(text=voltage_text)
        self.batt_current_label.config(text=current_text)

        # Update color based on voltage status
        color = self.model.get_battery_status_color()
        self.batt_voltage_label.config(foreground=color)

    def _on_frame_type_change(self, _event: object) -> None:
        """Handle frame type selection change and immediately upload parameters."""
        selected_text = self.frame_type_combobox.get()
        logging_info(_("Frame type changed: %(type)s"), {"type": selected_text})

        # Update frame configuration through data model
        success, error_msg = self.model.update_frame_type_from_selection(selected_text)

        if not success:
            showerror(_("Parameter Update Error"), error_msg)
            return

        # Update UI components
        self._update_motor_buttons_layout()
        self._update_diagram()

    def _on_throttle_change(self) -> None:
        """Handle throttle spinbox change."""
        try:
            throttle_pct = int(float(self.throttle_spinbox.get()))
            self.model.set_test_throttle_pct(throttle_pct)
        except ValueError:
            # Invalid value entered, reset to model value
            throttle_pct = self.model.get_test_throttle_pct()
            self.throttle_spinbox.delete(0, "end")
            self.throttle_spinbox.insert(0, str(throttle_pct))

    def _on_duration_change(self) -> None:
        """Handle duration spinbox change."""
        try:
            duration = float(self.duration_spinbox.get())
            self.model.set_test_duration(duration)
        except ValueError:
            # Invalid value entered, reset to model value
            duration = self.model.get_test_duration()
            self.duration_spinbox.delete(0, "end")
            self.duration_spinbox.insert(0, str(duration))

    def _set_motor_spin_arm(self) -> None:
        """Open a dialog to set MOT_SPIN_ARM."""
        # Simple dialog for now, should be a custom Toplevel
        current_val = self.model.get_parameter("MOT_SPIN_ARM")
        new_val = askfloat(
            _("Set Motor Spin Arm"),
            _("Enter new value for MOT_SPIN_ARM:"),
            initialvalue=current_val,
        )
        if new_val is not None:
            success, message = self.model.set_parameter("MOT_SPIN_ARM", new_val)
            if not success:
                showerror(_("Error"), message)

    def _set_motor_spin_min(self) -> None:
        """Open a dialog to set MOT_SPIN_MIN."""
        current_val = self.model.get_parameter("MOT_SPIN_MIN")
        new_val = askfloat(
            _("Set Motor Spin Min"),
            _("Enter new value for MOT_SPIN_MIN:"),
            initialvalue=current_val,
            minvalue=0.0,
            maxvalue=1.0,
        )
        if new_val is not None:
            success, message = self.model.set_parameter("MOT_SPIN_MIN", new_val)
            if not success:
                showerror(_("Error"), message)

    def _test_motor(self, motor_number: int) -> None:
        """Execute a test for a single motor."""
        logging_debug(_("Testing motor %(num)d"), {"num": motor_number})

        # First-time safety confirmation
        if self._first_motor_test and self.model.should_show_first_test_warning():
            if not askyesno(_("Safety Confirmation"), self.model.get_safety_warning_message()):
                return
            self._first_motor_test = False

        # Check if motor test is safe (includes voltage checks)
        is_safe, reason = self.model.is_motor_test_safe()
        if not is_safe:
            # Check if it's a voltage issue and provide specific guidance
            if self.model.is_battery_related_safety_issue(reason):
                showwarning(_("Battery Voltage Warning"), self.model.get_battery_safety_message(reason))
            else:
                showwarning(_("Safety Check Failed"), reason)
            return

        # Validate test parameters
        throttle_pct = self.model.get_test_throttle_pct()
        duration = int(self.model.get_test_duration())
        is_valid, validation_error = self.model.validate_motor_test_parameters(throttle_pct, duration)
        if not is_valid:
            showerror(_("Parameter Validation Error"), validation_error)
            return

        success, message = self.model.test_motor(motor_number, throttle_pct, duration)

        # Update status based on test result
        if success:
            self._update_motor_status(motor_number, _("Test Complete"), "green")
        else:
            self._update_motor_status(motor_number, _("Test Failed"), "red")
            showerror(_("Error"), message)

        # Reset status after a short delay
        self.root_window.after(2000, lambda: self._update_motor_status(motor_number, _("Ready"), "blue"))

    def _test_all_motors(self) -> None:
        """Execute a test for all motors simultaneously."""
        logging_debug(_("Testing all motors"))
        is_safe, reason = self.model.is_motor_test_safe()
        if not is_safe:
            showwarning(_("Safety Check Failed"), reason)
            return

        # Validate test parameters
        throttle_pct = self.model.get_test_throttle_pct()
        duration = int(self.model.get_test_duration())
        is_valid, validation_error = self.model.validate_motor_test_parameters(throttle_pct, duration)
        if not is_valid:
            showerror(_("Parameter Validation Error"), validation_error)
            return

        success, message = self.model.test_all_motors(throttle_pct, duration)
        if not success:
            showerror(_("Error"), message)

    def _test_motors_in_sequence(self) -> None:
        """Execute a test for all motors in sequence."""
        logging_debug(_("Testing motors in sequence"))
        is_safe, reason = self.model.is_motor_test_safe()
        if not is_safe:
            showwarning(_("Safety Check Failed"), reason)
            return

        # Validate test parameters
        throttle_pct = self.model.get_test_throttle_pct()
        duration = int(self.model.get_test_duration())
        is_valid, validation_error = self.model.validate_motor_test_parameters(throttle_pct, duration)
        if not is_valid:
            showerror(_("Parameter Validation Error"), validation_error)
            return

        success, message = self.model.test_motors_in_sequence(throttle_pct, duration)
        if not success:
            showerror(_("Error"), message)

    def _stop_all_motors(self) -> None:
        """Stop all motors immediately."""
        logging_info(_("Stopping all motors"))
        success, message = self.model.stop_all_motors()
        if not success:
            showerror(_("Error"), message)
        self._reset_all_motor_status()

    def _emergency_stop(self) -> None:
        """Emergency stop - alias for _stop_all_motors for test compatibility."""
        self._stop_all_motors()

    def _update_motor_status(self, motor_number: int, status: str, color: str = "black") -> None:
        """
        Update visual status for a specific motor.

        Args:
            motor_number: Motor number (1-based)
            status: Status text to display
            color: Text color for the status

        """
        if 1 <= motor_number <= len(self.motor_status_labels):
            label = self.motor_status_labels[motor_number - 1]
            label.config(text=status, foreground=color)
            label.update_idletasks()  # Force GUI update

    def _reset_all_motor_status(self) -> None:
        """Reset all motor status labels to 'Ready'."""
        for label in self.motor_status_labels:
            label.config(text=_("Ready"), foreground="blue")

    def _setup_keyboard_shortcuts(self) -> None:
        """Setup keyboard shortcuts for critical motor test functions."""
        # Emergency stop (Escape key)
        self.root_window.bind("<Escape>", lambda _: self._stop_all_motors())
        self.root_window.bind("<Control-s>", lambda _: self._stop_all_motors())

        # Test all motors (Ctrl+A)
        self.root_window.bind("<Control-a>", lambda _: self._test_all_motors())

        # Test in sequence (Ctrl+Q)
        self.root_window.bind("<Control-q>", lambda _: self._test_motors_in_sequence())

        # Focus root window to ensure it can capture key events
        self.root_window.focus_set()


class MotorTestWindow(BaseWindow):
    """
    Standalone window for the motor test GUI.

    Used for development and testing.
    """

    def __init__(self, model: MotorTestDataModel) -> None:
        super().__init__()
        self.model = model  # Store model reference for tests
        self.root.title(_("ArduPilot Motor Test"))
        width = self.calculate_scaled_image_size(400)
        height = self.calculate_scaled_image_size(610)
        self.root.geometry(str(width) + "x" + str(height))

        self.view = MotorTestView(self.main_frame, model, self.root)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self) -> None:
        """Handle window close event."""
        # Stop any running tests
        self.view.model.stop_all_motors()
        self.root.destroy()


def argument_parser() -> Namespace:
    """
    Parses command-line arguments for the script.

    This function sets up an argument parser to handle the command-line arguments for the script.
    This is just for testing the script. Production code will not call this function.

    Returns:
    argparse.Namespace: An object containing the parsed arguments.

    """
    # The rest of the file should not have access to any of these backends.
    # It must use the data_model layer instead of accessing the backends directly.
    from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
    from ardupilot_methodic_configurator.backend_flightcontroller import FlightController

    parser = ArgumentParser(
        description=_(
            "This main is for testing and development only. Usually, the MotorTestView is called from another script"
        )
    )
    parser = FlightController.add_argparse_arguments(parser)
    parser = LocalFilesystem.add_argparse_arguments(parser)
    return add_common_arguments(parser).parse_args()


# pylint: disable=duplicate-code
def main() -> None:
    args = argument_parser()

    state = ApplicationState(args)

    setup_logging(state)

    logging_warning(
        _("This main is for testing and development only, usually the MotorTestView is called from another script")
    )

    # Initialize flight controller and filesystem
    initialize_flight_controller_and_filesystem(state)

    try:
        data_model = MotorTestDataModel(state.flight_controller, state.local_filesystem)
        window = MotorTestWindow(data_model)
        window.root.mainloop()

    except Exception as e:  # pylint: disable=broad-exception-caught
        logging_error("Failed to start MotorTestWindow: %(error)s", {"error": e})
        # Show error to user
        tkinter.messagebox.showerror(_("Error"), f"Failed to start Motor Test: {e}")
    finally:
        if state.flight_controller:
            state.flight_controller.disconnect()  # Disconnect from the flight controller


if __name__ == "__main__":
    main()
