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

MotorTestWindow class provides a standalone window for development/testing.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import time
import tkinter as tk
from argparse import ArgumentParser, Namespace
from functools import partial
from logging import debug as logging_debug
from logging import error as logging_error
from logging import info as logging_info
from logging import warning as logging_warning
from tkinter import Frame, Label, ttk
from tkinter.messagebox import askyesno, showerror, showwarning
from tkinter.simpledialog import askfloat
from typing import Callable, Optional, Union

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.__main__ import (
    ApplicationState,
    initialize_flight_controller_and_filesystem,
    setup_logging,
)
from ardupilot_methodic_configurator.common_arguments import add_common_arguments
from ardupilot_methodic_configurator.data_model_motor_test import (
    DURATION_S_MAX,
    DURATION_S_MIN,
    THROTTLE_PCT_MAX,
    THROTTLE_PCT_MIN,
    FrameConfigurationError,
    MotorStatusEvent,
    MotorTestDataModel,
    MotorTestExecutionError,
    MotorTestSafetyError,
    ParameterError,
    ValidationError,
)
from ardupilot_methodic_configurator.frontend_tkinter_base_window import (
    BaseWindow,
)
from ardupilot_methodic_configurator.frontend_tkinter_pair_tuple_combobox import PairTupleCombobox
from ardupilot_methodic_configurator.frontend_tkinter_progress_window import ProgressWindow
from ardupilot_methodic_configurator.frontend_tkinter_scroll_frame import ScrollFrame
from ardupilot_methodic_configurator.plugin_constants import PLUGIN_MOTOR_TEST
from ardupilot_methodic_configurator.plugin_factory import plugin_factory


class DelayedProgressCallback:  # pylint: disable=too-few-public-methods
    """A callback wrapper that delays the first progress update by a specified time."""

    def __init__(self, original_callback: Callable[[int, int], None], delay_seconds: float) -> None:
        """
        Initialize the delayed callback.

        Args:
            original_callback: The original callback function to wrap
            delay_seconds: Time in seconds to delay before showing progress

        """
        self.original_callback = original_callback
        self.delay_seconds = delay_seconds
        self.first_call_time: Optional[float] = None

    def __call__(self, current: int, total: int) -> None:
        """Execute the callback with delay logic."""
        if self.first_call_time is None:
            self.first_call_time = time.time()

        # Only call the original callback if enough time has passed since the first call
        elapsed_time = time.time() - self.first_call_time
        if elapsed_time >= self.delay_seconds:
            self.original_callback(current, total)


class MotorTestView(Frame):  # pylint: disable=too-many-instance-attributes
    """GUI for motor test functionality."""

    def __init__(
        self,
        parent: Union[tk.Frame, ttk.Frame],
        model: MotorTestDataModel,
        base_window: BaseWindow,
    ) -> None:
        super().__init__(parent)
        self.parent = parent
        self.model = model
        self.base_window = base_window
        self.root_window = base_window.root  # Keep for compatibility

        # Define attributes
        self.throttle_spinbox: ttk.Spinbox
        self.duration_spinbox: ttk.Spinbox
        self.frame_type_combobox: PairTupleCombobox
        self.motor_buttons: list[ttk.Button] = []
        self.motor_status_labels: list[ttk.Label] = []  # Status labels for visual feedback
        self.detected_comboboxes: list[ttk.Combobox] = []
        self.diagram_label: ttk.Label
        self.batt_voltage_label: ttk.Label
        self.batt_current_label: ttk.Label
        # Store image reference (PNG or other format)
        self._current_diagram_image: Optional[tk.PhotoImage] = None
        self._frame_options_loaded = False  # Track if frame options have been loaded
        self._diagrams_path = ""  # Cache diagram path for performance
        self._diagram_needs_update = True  # Track if diagram needs to be updated
        self._content_frame: Optional[ttk.Frame] = None  # Store reference to content frame for widget searches
        self._motor_grid_frame: Optional[ttk.Frame] = None  # Direct handle for motor grid frame
        self._timer_id: Optional[str] = None  # Track scheduled update timer for cleanup

        self._create_widgets()

        # Try to refresh frame configuration from flight controller
        if not self.model.refresh_from_flight_controller():
            logging_warning(_("Could not refresh frame configuration from flight controller, using defaults"))

        self._update_view()

        # Setup keyboard shortcuts for critical functions
        self._setup_keyboard_shortcuts()

    def _create_widgets(self) -> None:  # pylint: disable=too-many-statements # noqa: PLR0915
        """Create and place widgets in the frame."""
        # Main frame
        main_frame = ScrollFrame(self)
        main_frame.pack(fill="both", expand=True)
        content_frame = main_frame.view_port
        self._content_frame = content_frame  # Store reference for later use

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

        # Create PairTupleCombobox with frame type pairs
        frame_type_pairs = self.model.get_frame_type_pairs()
        current_selection = self.model.get_current_frame_selection_key() if frame_type_pairs else None

        self.frame_type_combobox = PairTupleCombobox(
            frame_type_frame, frame_type_pairs, current_selection, "Frame Type", state="readonly"
        )
        self.frame_type_combobox.pack(side="left", padx=5, expand=True, fill="x")
        self.frame_type_combobox.bind("<<ComboboxSelected>>", self._on_frame_type_change, add="+")

        self.diagram_label = ttk.Label(config_frame, text=_("Loading diagram..."), anchor="center")
        self.diagram_label.pack(pady=10)

        # --- 2. Motor Order/Direction Configuration ---
        testing_frame = ttk.LabelFrame(content_frame, text=_("2. Motor Order/Direction Configuration"))
        testing_frame.pack(padx=10, pady=5, fill="x")

        controls_frame = ttk.Frame(testing_frame)
        controls_frame.pack(fill="x", pady=5)

        ttk.Label(controls_frame, text=_("Throttle:")).pack(side="left", padx=4)
        self.throttle_spinbox = ttk.Spinbox(
            controls_frame, from_=THROTTLE_PCT_MIN, to=THROTTLE_PCT_MAX, increment=1, width=2, command=self._on_throttle_change
        )
        self.throttle_spinbox.pack(side="left", padx=2)
        # Bind events to capture manual text entry completion
        self.throttle_spinbox.bind("<Return>", lambda _: self._on_throttle_change())
        self.throttle_spinbox.bind("<FocusOut>", lambda _: self._on_throttle_change())
        ttk.Label(controls_frame, text="%").pack(side="left", padx=2)

        ttk.Label(controls_frame, text=_("Duration:")).pack(side="left", padx=4)
        self.duration_spinbox = ttk.Spinbox(
            controls_frame, from_=DURATION_S_MIN, to=DURATION_S_MAX, increment=0.5, width=3, command=self._on_duration_change
        )
        self.duration_spinbox.pack(side="left", padx=2)
        # Bind events to capture manual text entry completion
        self.duration_spinbox.bind("<Return>", lambda _: self._on_duration_change())
        self.duration_spinbox.bind("<FocusOut>", lambda _: self._on_duration_change())
        ttk.Label(controls_frame, text="s").pack(side="left", padx=2)

        self.batt_voltage_label = ttk.Label(controls_frame, text=_("Voltage: N/A"))
        self.batt_voltage_label.pack(side="left", padx=10)
        self.batt_current_label = ttk.Label(controls_frame, text=_("Current: N/A"))
        self.batt_current_label.pack(side="left", padx=10)

        motor_grid = ttk.Frame(testing_frame)
        motor_grid.pack(pady=10)
        self._motor_grid_frame = motor_grid
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

        # --- 3. Arm and Min Throttle Configuration ---
        motor_params_frame = ttk.LabelFrame(content_frame, text=_("3. Arm and Min Throttle Configuration"))
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

    def _create_motor_buttons(self, parent: Union[Frame, ttk.Frame]) -> None:
        """Create the motor test buttons and detection comboboxes."""
        motor_labels = self.model.motor_labels
        motor_numbers = self.model.motor_numbers
        motor_directions = self.model.motor_directions
        for i in range(self.model.motor_count):
            motor_number = motor_numbers[i]

            motor_frame = ttk.Frame(parent)
            motor_frame.grid(row=i // 4, column=i % 4, padx=10, pady=5)

            def make_test_command(test_sequence_nr: int, motor_output_nr: int) -> Callable[[], None]:
                return lambda: self._test_motor(test_sequence_nr, motor_output_nr)

            button = ttk.Button(
                motor_frame,
                text=_("Test Motor %(label)s") % {"label": motor_labels[i]},
                command=make_test_command(i, motor_number),
            )
            button.pack()
            self.motor_buttons.append(button)

            # Show motor number and expected direction
            motor_text = _("Motor %(num)d %(dir)s") % {"num": motor_number, "dir": motor_directions[i]}
            info_label = ttk.Label(motor_frame, text=motor_text)
            info_label.pack()

            ttk.Label(motor_frame, text=_("Detected:")).pack()
            combo = ttk.Combobox(motor_frame, values=self.model.motor_labels, width=5)
            combo.pack()
            self.detected_comboboxes.append(combo)

            # Add status label for visual feedback
            status_label = ttk.Label(motor_frame, text=_("Ready"), foreground="blue")
            status_label.pack()
            self.motor_status_labels.append(status_label)

    def _update_view(self) -> None:
        """Update the view with data from the model."""
        # Update diagram only when needed (not every second)
        if self._diagram_needs_update:
            self._update_diagram()
            self._diagram_needs_update = False

        self._update_motor_buttons_layout()
        self._update_battery_status()
        self._update_spinbox_values()
        self._timer_id = self.after(1000, self._update_view)  # Schedule periodic update

    def _update_spinbox_values(self) -> None:
        """Update spinbox values from the data model only if not currently being edited."""
        try:
            # Only update if the spinbox doesn't have focus (user is not editing)
            if self.throttle_spinbox.focus_get() != self.throttle_spinbox:
                throttle_pct = self.model.get_test_throttle_pct()
                current_value = self.throttle_spinbox.get()
                # Only update if the value has actually changed to avoid unnecessary updates
                if current_value != str(throttle_pct):
                    self.throttle_spinbox.delete(0, "end")
                    self.throttle_spinbox.insert(0, str(throttle_pct))

            # Only update if the spinbox doesn't have focus (user is not editing)
            if self.duration_spinbox.focus_get() != self.duration_spinbox:
                duration = self.model.get_test_duration_s()
                current_value = self.duration_spinbox.get()
                # Only update if the value has actually changed to avoid unnecessary updates
                if current_value != str(duration):
                    self.duration_spinbox.delete(0, "end")
                    self.duration_spinbox.insert(0, str(duration))
        except KeyError:
            pass

    def _update_motor_buttons_layout(self) -> None:
        """Re-create motor buttons if motor count changes."""
        motor_grid = self._motor_grid_frame
        if motor_grid is None:
            logging_error(_("Could not find motor grid frame"))
            return

        current_count = len(self.motor_buttons)
        required_count = self.model.motor_count

        if current_count == required_count:
            return

        for child in motor_grid.winfo_children():
            child.destroy()

        self.motor_buttons.clear()
        self.motor_status_labels.clear()
        self.detected_comboboxes.clear()

        self._create_motor_buttons(motor_grid)

    def _load_png_diagram(self, diagram_path: str) -> None:
        """Load and display a PNG motor diagram using BaseWindow.put_image_in_label()."""
        logging_debug(_("Found PNG diagram at: %(path)s"), {"path": diagram_path})

        try:
            # Create a temporary parent frame for the label creation
            temp_frame = ttk.Frame(self.diagram_label.master)

            # Use BaseWindow's method with a reasonable height for motor diagrams
            new_label = self.base_window.put_image_in_label(
                parent=temp_frame,
                filepath=diagram_path,
                image_height=230,  # Target height for motor diagrams
                fallback_text=_("Error loading diagram"),
            )

            # Copy the image and text from the new label to our existing label
            image_ref = getattr(new_label, "image", None)
            if image_ref:
                self.diagram_label.configure(image=image_ref, text="")
                # Keep reference to prevent garbage collection
                self._current_diagram_image = image_ref
                logging_debug(_("Image loaded and displayed successfully"))
            else:
                # Fallback case - use the text from the new label
                self.diagram_label.configure(image="", text=new_label.cget("text"))
                self._current_diagram_image = None

            # Clean up temporary frame
            temp_frame.destroy()

        except FileNotFoundError:
            logging_error(_("Image file not found: %s"), diagram_path)
            self.diagram_label.configure(image="", text=_("Diagram not found"))
            self._current_diagram_image = None
        except (OSError, ValueError, TypeError, AttributeError) as e:
            logging_error(_("Error loading PNG diagram: %(error)s"), {"error": e})
            self.diagram_label.configure(image="", text=_("Error loading diagram"))
            self._current_diagram_image = None

    def _update_diagram(self) -> None:
        """Update the motor diagram image."""
        self.diagram_label.configure(image="", text=_("Loading diagram..."))

        if self.model.motor_diagram_exists():
            if self._diagrams_path:
                diagram_path = self._diagrams_path
                error_msg = ""
            else:
                diagram_path, error_msg = self.model.get_motor_diagram_path()
                self._diagrams_path = diagram_path

            # Debug logging to understand the issue
            logging_debug(
                _("Diagram path type: %(type)s, value: %(path)s"),
                {"type": type(diagram_path).__name__, "path": repr(diagram_path)},
            )

            if diagram_path and isinstance(diagram_path, str) and diagram_path.endswith(".png"):
                self._load_png_diagram(diagram_path)
            elif error_msg:
                logging_error(error_msg)
                self.diagram_label.configure(image="", text=error_msg)
            else:
                self.diagram_label.configure(image="", text=_("Diagram: %(path)s") % {"path": diagram_path})
        else:
            self.diagram_label.configure(image="", text=_("Motor diagram not available."))

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
        # Get the selected frame type code from PairTupleCombobox
        selected_key = self.frame_type_combobox.get_selected_key()
        if selected_key is None:
            logging_warning(_("No frame type selected"))
            return

        try:
            # Create delayed progress windows that only show if operation takes more than 1 second
            reset_progress_window = ProgressWindow(
                self.root_window,
                _("Resetting Flight Controller"),
                _("Waiting for {} of {} seconds"),
                only_show_when_update_progress_called=True,
            )
            connection_progress_window = ProgressWindow(
                self.root_window,
                _("Re-Connecting to Flight Controller"),
                _("Waiting for {} of {} seconds"),
                only_show_when_update_progress_called=True,
            )

            # Create delayed callback wrappers that wait 1 second before showing progress
            reset_callback = DelayedProgressCallback(reset_progress_window.update_progress_bar, 1.0)
            connection_callback = DelayedProgressCallback(connection_progress_window.update_progress_bar, 1.0)

            self.model.update_frame_type_by_key(
                selected_key,
                reset_callback,
                connection_callback,
                extra_sleep_time=2,
            )
            reset_progress_window.destroy()  # for the case that we are doing a test and there is no real FC connected
            connection_progress_window.destroy()  # for the case that we are doing a test and there is no real FC connected

            # Invalidate diagram cache since frame type changed
            self._diagrams_path = ""
            self._diagram_needs_update = True

            # Update UI components
            self._update_motor_buttons_layout()

        except (ValidationError, ParameterError, FrameConfigurationError) as e:
            showerror(_("Parameter Update Error"), str(e))

    def _on_throttle_change(self) -> None:
        """Handle throttle spinbox change."""
        logging_debug(_("_on_throttle_change called with value: %(val)s"), {"val": self.throttle_spinbox.get()})
        try:
            throttle_pct = int(float(self.throttle_spinbox.get()))
            self.model.set_test_throttle_pct(throttle_pct)
            logging_debug(_("Throttle set to %(pct)d%%"), {"pct": throttle_pct})
        except ValueError as e:
            # Invalid value entered, reset to model value
            logging_warning(_("ValueError in _on_throttle_change: %(error)s"), {"error": str(e)})
            throttle_pct = self.model.get_test_throttle_pct()
            self.throttle_spinbox.delete(0, "end")
            self.throttle_spinbox.insert(0, str(throttle_pct))
            showerror(
                _("Throttle value error"), _("Invalid throttle value entered, reset to %(pct)d%%") % {"pct": throttle_pct}
            )
        except (ValidationError, ParameterError) as e:
            # Model validation failed, reset to current model value
            logging_warning(_("ValidationError/ParameterError in _on_throttle_change: %(error)s"), {"error": str(e)})
            throttle_pct = self.model.get_test_throttle_pct()
            self.throttle_spinbox.delete(0, "end")
            self.throttle_spinbox.insert(0, str(throttle_pct))
            showerror(_("Throttle value error"), _("Throttle validation failed: %(error)s") % {"error": str(e)})

    def _on_duration_change(self) -> None:
        """Handle duration spinbox change."""
        logging_debug(_("_on_duration_change called with value: %(val)s"), {"val": self.duration_spinbox.get()})
        try:
            duration = float(self.duration_spinbox.get())
            self.model.set_test_duration_s(duration)
            logging_debug(_("Duration set to %(dur)g seconds"), {"dur": duration})
        except ValueError as e:
            # Invalid value entered, reset to model value
            logging_warning(_("ValueError in _on_duration_change: %(error)s"), {"error": str(e)})
            duration = self.model.get_test_duration_s()
            self.duration_spinbox.delete(0, "end")
            self.duration_spinbox.insert(0, str(duration))
            showerror(
                _("Duration value error"), _("Invalid duration value entered, reset to %(dur)g seconds") % {"dur": duration}
            )
        except (ValidationError, ParameterError) as e:
            # Model validation failed, reset to current model value
            logging_warning(_("ValidationError/ParameterError in _on_duration_change: %(error)s"), {"error": str(e)})
            duration = self.model.get_test_duration_s()
            self.duration_spinbox.delete(0, "end")
            self.duration_spinbox.insert(0, str(duration))
            showerror(_("Duration value error"), _("Duration validation failed: %(error)s") % {"error": str(e)})

    def _set_motor_spin_arm(self) -> None:
        """Open a dialog to set MOT_SPIN_ARM."""
        # Simple dialog for now, should be a custom Toplevel
        current_val = self.model.get_parameter("MOT_SPIN_ARM")
        new_val = askfloat(
            _("Set Motor Spin Arm"),
            _("Enter new value for MOT_SPIN_ARM with 0.02 margin:"),
            initialvalue=current_val,
        )
        if new_val is not None:
            try:
                reset_progress_window = ProgressWindow(
                    self.root_window, _("Resetting Flight Controller"), _("Waiting for {} of {} seconds")
                )
                self.model.set_motor_spin_arm_value(new_val, reset_progress_window.update_progress_bar)
                reset_progress_window.destroy()  # for the case that we are doing a test and there is no real FC connected
            except (ParameterError, ValidationError) as e:
                showerror(_("Error"), str(e))

    def _set_motor_spin_min(self) -> None:
        """Open a dialog to set MOT_SPIN_MIN."""
        current_val = self.model.get_parameter("MOT_SPIN_MIN")
        new_val = askfloat(
            _("Set Motor Spin Min"),
            _("Enter new value for MOT_SPIN_MIN, must be at least 0.02 higher than MOT_SPIN_ARM:"),
            initialvalue=current_val,
            minvalue=0.0,
            maxvalue=1.0,
        )
        if new_val is not None:
            try:
                self.model.set_motor_spin_min_value(new_val)
            except (ParameterError, ValidationError) as e:
                showerror(_("Error"), str(e))

    def _test_motor(self, test_sequence_nr: int, motor_output_nr: int) -> None:
        """Execute a test for a single motor."""
        logging_debug(
            _("Testing motor %(seq)s at motor output %(num)d"),
            {"seq": self.model.motor_labels[test_sequence_nr], "num": motor_output_nr},
        )

        if not self._ensure_first_test_confirmation():
            return

        try:
            self.model.run_single_motor_test(test_sequence_nr, motor_output_nr, self._handle_status_event)

        except MotorTestSafetyError as e:
            # Check if it's a voltage issue and provide specific guidance
            if self.model.is_battery_related_safety_issue(str(e)):
                showwarning(_("Battery Voltage Warning"), self.model.get_battery_safety_message(str(e)))
            else:
                showwarning(_("Safety Check Failed"), str(e))
            self._update_motor_status(motor_output_nr, _("Safety Check Failed"), "red")
        except ValidationError as e:
            showerror(_("Parameter Validation Error"), str(e))
            self._update_motor_status(motor_output_nr, _("Invalid Parameters"), "red")
        except MotorTestExecutionError as e:
            self._update_motor_status(motor_output_nr, _("Test Failed"), "red")
            showerror(_("Error"), str(e))
        except Exception as e:  # pylint: disable=broad-exception-caught
            self._update_motor_status(motor_output_nr, _("Error"), "red")
            showerror(_("Unexpected Error"), str(e))

    def _test_all_motors(self) -> None:
        """Execute a test for all motors simultaneously."""
        logging_debug(_("Testing all motors"))

        if not self._ensure_first_test_confirmation():
            return

        try:
            self.model.run_all_motors_test(self._handle_status_event)

        except MotorTestSafetyError as e:
            showwarning(_("Safety Check Failed"), str(e))
        except ValidationError as e:
            showerror(_("Parameter Validation Error"), str(e))
        except MotorTestExecutionError as e:
            showerror(_("Error"), str(e))
        except Exception as e:  # pylint: disable=broad-exception-caught
            showerror(_("Unexpected Error"), str(e))

    def _test_motors_in_sequence(self) -> None:
        """Execute a test for all motors in sequence."""
        logging_debug(_("Testing motors in sequence"))

        if not self._ensure_first_test_confirmation():
            return

        try:
            self.model.run_sequential_motor_test(self._handle_status_event)

        except MotorTestSafetyError as e:
            showwarning(_("Safety Check Failed"), str(e))
        except ValidationError as e:
            showerror(_("Parameter Validation Error"), str(e))
        except MotorTestExecutionError as e:
            showerror(_("Error"), str(e))
        except Exception as e:  # pylint: disable=broad-exception-caught
            showerror(_("Unexpected Error"), str(e))

    def _stop_all_motors(self) -> None:
        """Stop all motors immediately."""
        logging_info(_("Stopping all motors"))

        try:
            self.model.emergency_stop_motors(self._handle_status_event)
        except MotorTestExecutionError as e:
            showerror(_("Error"), str(e))
        except Exception as e:  # pylint: disable=broad-exception-caught
            showerror(_("Unexpected Error"), str(e))

    def _emergency_stop(self) -> None:
        """Emergency stop - alias for _stop_all_motors for test compatibility."""
        self._stop_all_motors()

    def _ensure_first_test_confirmation(self) -> bool:
        """Guard that the user acknowledged the first-time warning."""
        if self.model.should_show_first_test_warning():
            if not askyesno(_("Safety Confirmation"), self.model.get_safety_warning_message()):
                return False
            self.model.acknowledge_first_test_warning()
        return True

    def _handle_status_event(self, motor_number: int, event: MotorStatusEvent) -> None:
        """Translate model status events into user-facing label updates."""
        if event is MotorStatusEvent.COMMAND_SENT:
            self._update_motor_status(motor_number, _("Command sent"), "green")
        elif event is MotorStatusEvent.STOP_SENT:
            self._update_motor_status(motor_number, _("Stop sent"), "red")
        self._schedule_ready_reset(motor_number)

    def _schedule_ready_reset(self, motor_number: int, delay_ms: int = 2000) -> None:
        """Return a motor label to the Ready state after a delay."""
        self.root_window.after(
            delay_ms,
            partial(self._update_motor_status, motor_number, _("Ready"), "blue"),
        )

    def _update_motor_status(self, motor_number: int, status: str, color: str = "black") -> None:
        """
        Update visual status for a specific motor.

        Args:
            motor_number: Motor number (1-based)
            status: Status text to display
            color: Text color for the status

        """
        if 1 <= motor_number <= len(self.motor_status_labels):
            label = self.motor_status_labels[self.model.test_order(motor_number)]
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

    def on_activate(self) -> None:
        """
        Called when the plugin becomes active (visible).

        Refreshes the frame configuration from the flight controller
        to ensure the display is up-to-date.
        """
        # Refresh frame configuration when becoming active
        if not self.model.refresh_from_flight_controller():
            logging_warning(_("Could not refresh frame configuration from flight controller"))
        self._update_view()

    def on_deactivate(self) -> None:
        """
        Called when the plugin becomes inactive (hidden).

        Stops all running motor tests for safety when switching away from this plugin.
        Also cancels any pending update timers to prevent resource leaks.
        """
        # Cancel any pending update timer to prevent updating hidden widget
        if self._timer_id:
            self.after_cancel(self._timer_id)
            self._timer_id = None

        # Critical safety requirement: stop all motors when user navigates away
        # to prevent motors running unattended in the background
        try:
            self.model.stop_all_motors()
            self._reset_all_motor_status()
        except (MotorTestExecutionError, ParameterError) as e:
            # Motor stop failed - this could indicate a communication issue or unsupported frame type.
            # We log as warning (not debug) because failed motor stop is a safety concern
            # that operators should be aware of, even if it's expected for some configurations.
            logging_warning(
                _("Motor stop failed during deactivation: %(error)s. Please verify motors are stopped."), {"error": str(e)}
            )
        except Exception as e:
            # Unexpected errors during motor stop are critical safety issues.
            # We log as error and re-raise to prevent silently continuing with motors potentially running.
            logging_error(_("Critical error during motor stop at deactivation: %(error)s"), {"error": str(e)})
            raise

    def destroy(self) -> None:
        """
        Clean up resources before widget destruction.

        Cancels any pending timers to prevent resource leaks and ensure
        no operations continue after the widget is destroyed.
        """
        if self._timer_id:
            self.after_cancel(self._timer_id)
            self._timer_id = None
        super().destroy()


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

        self.view = MotorTestView(self.main_frame, model, self)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self) -> None:
        """Handle window close event."""
        # Attempt to stop any running tests gracefully
        try:
            self.view.model.stop_all_motors()
        except MotorTestExecutionError:
            # Some frame types (like "No torque yaw") may not support motor commands
            # This is expected and we should just log it without showing an error
            logging_debug(_("Motor stop command failed during shutdown - this is normal for some frame types"))
        except Exception as e:  # pylint: disable=broad-exception-caught
            # Log other unexpected exceptions but don't prevent shutdown
            logging_warning(_("Unexpected error during motor stop at shutdown: %(error)s"), {"error": str(e)})

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
    # pylint: disable=import-outside-toplevel
    from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem  # noqa: PLC0415
    from ardupilot_methodic_configurator.backend_flightcontroller import FlightController  # noqa: PLC0415
    # pylint: enable=import-outside-toplevel

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
        showerror(_("Error"), f"Failed to start Motor Test: {e}")
    finally:
        if state.flight_controller:
            state.flight_controller.disconnect()  # Disconnect from the flight controller


# Register this plugin with the factory for dependency injection
def _create_motor_test_view(
    parent: Union[tk.Frame, ttk.Frame],
    model: object,
    base_window: object,
) -> MotorTestView:
    """
    Factory function to create MotorTestView instances.

    This function trusts that the caller provides the correct types
    as per the plugin protocol (duck typing approach).

    Args:
        parent: The parent frame
        model: The MotorTestDataModel instance (passed as object for protocol compliance)
        base_window: The BaseWindow instance (passed as object for protocol compliance)

    Returns:
        A new MotorTestView instance

    """
    # Trust the caller to provide correct types (protocol-based duck typing)
    # Type checker will verify this at static analysis time
    return MotorTestView(parent, model, base_window)  # type: ignore[arg-type]


def register_motor_test_plugin() -> None:
    """Register the motor test plugin with the factory."""
    plugin_factory.register(PLUGIN_MOTOR_TEST, _create_motor_test_view)


if __name__ == "__main__":
    main()
