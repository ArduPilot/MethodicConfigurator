"""
GUI for accelerometer calibration plugin.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 ArduPilot Contributors

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from argparse import ArgumentParser, Namespace
from contextlib import suppress
from logging import error as logging_error
from logging import warning as logging_warning
from tkinter import Frame, ttk
from tkinter.messagebox import showerror, showinfo

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.__main__ import (
    ApplicationState,
    initialize_flight_controller,
    setup_logging,
)
from ardupilot_methodic_configurator.common_arguments import add_common_arguments
from ardupilot_methodic_configurator.data_model_accelerometer_calibration import AccelerometerCalibrationDataModel
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.plugin_constants import PLUGIN_ACCELEROMETER_CALIBRATION
from ardupilot_methodic_configurator.plugin_factory import plugin_factory

_POLL_INTERVAL_MS = 100  # tkinter polling interval during full calibration


class AccelerometerCalibrationView(Frame):  # pylint: disable=too-many-instance-attributes
    """GUI for accelerometer calibration plugin."""

    def __init__(
        self,
        parent: tk.Frame | ttk.Frame,
        model: AccelerometerCalibrationDataModel,
        base_window: BaseWindow,
    ) -> None:
        """
        Initialize the accelerometer calibration view.

        Args:
            parent: Parent widget
            model: Data model for accelerometer calibration
            base_window: Parent BaseWindow instance

        """
        super().__init__(parent)
        self.model = model
        self.base_window = base_window
        self._poll_job: str | None = None  # tkinter after() handle

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True)

        # Title
        ttk.Label(
            main_frame,
            text=_("Accelerometer Calibration"),
            font=("TkDefaultFont", 14, "bold"),
        ).pack(pady=(0, 10))

        # Info text
        info_text = _(
            "Simple calibration: Place vehicle level, then click Simple Calibration.\n"
            "Level calibration: Place vehicle level to set the AHRS trim angles.\n"
            "Full calibration: Follow the on-screen instructions for all 6 orientations."
        )
        ttk.Label(main_frame, text=info_text, justify="center").pack(pady=(0, 20))

        # --- Static buttons (always visible) ---
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(pady=10)

        self._simple_btn = ttk.Button(
            buttons_frame,
            text=_("Simple Calibration (Level)"),
            command=self._on_simple_calibration,
        )
        self._simple_btn.pack(side="left", padx=8)

        self._level_btn = ttk.Button(
            buttons_frame,
            text=_("Level Calibration (Trim)"),
            command=self._on_level_calibration,
        )
        self._level_btn.pack(side="left", padx=8)

        self._full_btn = ttk.Button(
            buttons_frame,
            text=_("Full Calibration (6-Position)"),
            command=self._on_start_full_calibration,
        )
        self._full_btn.pack(side="left", padx=8)

        # --- Full-calibration wizard panel (hidden until full cal is active) ---
        self._wizard_frame = ttk.LabelFrame(main_frame, text=_("6-Position Calibration"), padding=12)

        self._position_label = ttk.Label(
            self._wizard_frame,
            text="",
            font=("TkDefaultFont", 11),
            justify="center",
            wraplength=500,
        )
        self._position_label.pack(pady=(0, 12))

        wizard_buttons = ttk.Frame(self._wizard_frame)
        wizard_buttons.pack()

        self._continue_btn = ttk.Button(
            wizard_buttons,
            text=_("Continue"),
            state="disabled",
            command=self._on_continue,
        )
        self._continue_btn.pack(side="left", padx=8)

        self._cancel_btn = ttk.Button(
            wizard_buttons,
            text=_("Cancel"),
            command=self._on_cancel_full_calibration,
        )
        self._cancel_btn.pack(side="left", padx=8)

    # ------------------------------------------------------------------
    # Simple / level calibration
    # ------------------------------------------------------------------

    def _on_simple_calibration(self) -> None:
        """Handle Simple Calibration button."""
        success, message = self.model.start_simple_calibration()
        if success:
            showinfo(_("Calibration Result"), message)
        else:
            showerror(_("Calibration Failed"), message)

    def _on_level_calibration(self) -> None:
        """Handle Level Calibration button."""
        success, message = self.model.start_level_calibration()
        if success:
            showinfo(_("Calibration Result"), message)
        else:
            showerror(_("Calibration Failed"), message)

    # ------------------------------------------------------------------
    # Full 6-position calibration wizard
    # ------------------------------------------------------------------

    def _on_start_full_calibration(self) -> None:
        """Start the full 6-position calibration and show the wizard panel."""
        success, message = self.model.start_full_calibration()
        if not success:
            showerror(_("Calibration Failed"), message)
            return

        # Show wizard, disable the top-level calibration buttons
        self._simple_btn.configure(state="disabled")
        self._level_btn.configure(state="disabled")
        self._full_btn.configure(state="disabled")
        self._position_label.configure(text=_("Waiting for flight controller..."))
        self._continue_btn.configure(state="disabled")
        self._wizard_frame.pack(fill="x", padx=20, pady=(10, 0))

        self._start_polling()

    def _start_polling(self) -> None:
        """Schedule the first poll tick."""
        self._poll_job = self.after(_POLL_INTERVAL_MS, self._poll_tick)

    def _poll_tick(self) -> None:
        """Called by tkinter every _POLL_INTERVAL_MS ms to check for FC messages."""
        self._poll_job = None  # The scheduled callback is now running, so no pending job remains.
        pos = self.model.poll_for_next_position()

        if pos is None:
            # Nothing yet - reschedule
            self._poll_job = self.after(_POLL_INTERVAL_MS, self._poll_tick)
            return

        if self.model.is_calibration_complete(pos):
            self._end_full_calibration(success=self.model.is_calibration_successful(pos))
            return

        # New position requested — update the instruction label and enable Continue
        label = self.model.get_position_label(pos)
        self._position_label.configure(text=label)
        self._continue_btn.configure(state="normal")
        # Stop polling while waiting for the user to click Continue

    def _on_continue(self) -> None:
        """User clicked Continue — confirm the current position and resume polling."""
        self._continue_btn.configure(state="disabled")
        success, error_msg = self.model.confirm_current_position()
        if not success:
            showerror(_("Calibration Error"), error_msg)
            self._end_full_calibration(success=False)
            return
        self._position_label.configure(text=_("Waiting for flight controller..."))
        self._start_polling()

    def _on_cancel_full_calibration(self) -> None:
        """User clicked Cancel during full calibration."""
        self._stop_polling()
        self._hide_wizard()
        showerror(_("Calibration Cancelled"), _("Full accelerometer calibration was cancelled."))

    def _end_full_calibration(self, *, success: bool) -> None:
        """Called when full calibration completes (successfully or not)."""
        self._stop_polling()
        self._hide_wizard()
        if success:
            showinfo(_("Calibration Result"), _("Full accelerometer calibration successful!"))
        else:
            showerror(_("Calibration Failed"), _("Full accelerometer calibration failed."))

    def _stop_polling(self) -> None:
        """Cancel any pending after() poll job."""
        if self._poll_job is not None:
            poll_job = self._poll_job
            self._poll_job = None
            with suppress(tk.TclError):
                self.after_cancel(poll_job)

    def _hide_wizard(self) -> None:
        """Hide the wizard panel and re-enable the top-level buttons."""
        self._wizard_frame.pack_forget()
        self._simple_btn.configure(state="normal")
        self._level_btn.configure(state="normal")
        self._full_btn.configure(state="normal")

    # ------------------------------------------------------------------
    # Plugin lifecycle
    # ------------------------------------------------------------------

    def on_activate(self) -> None:
        """Called when the plugin view is displayed (lifecycle method)."""

    def on_deactivate(self) -> None:
        """Called when the plugin view is hidden (lifecycle method)."""
        self._stop_polling()
        self._hide_wizard()

    def destroy(self) -> None:
        """Cleanup resources when plugin is removed (lifecycle method)."""
        self._stop_polling()
        super().destroy()


def _create_accelerometer_calibration_view(
    parent: tk.Frame | ttk.Frame,
    model: object,
    base_window: object,
) -> AccelerometerCalibrationView:
    """
    Factory function to create AccelerometerCalibrationView instances.

    This function trusts that the caller provides the correct types
    as per the plugin protocol (duck typing approach).

    Args:
        parent: The parent frame
        model: The AccelerometerCalibrationDataModel instance (passed as object for protocol compliance)
        base_window: The BaseWindow instance (passed as object for protocol compliance)

    Returns:
        A new AccelerometerCalibrationView instance

    """
    # Trust the caller to provide correct types (protocol-based duck typing)
    # Type checker will verify this at static analysis time
    return AccelerometerCalibrationView(parent, model, base_window)  # type: ignore[arg-type]


def register_accelerometer_calibration_plugin() -> None:
    """Register the accelerometer calibration plugin with the factory."""
    plugin_factory.register(PLUGIN_ACCELEROMETER_CALIBRATION, _create_accelerometer_calibration_view)


class AccelerometerCalibrationWindow(BaseWindow):  # pragma: no cover
    """
    Standalone window for the accelerometer calibration GUI.

    Used for development and testing only.
    """

    def __init__(self, model: AccelerometerCalibrationDataModel) -> None:
        super().__init__()
        self.model = model  # Store model reference for tests
        self.root.title(_("ArduPilot Accelerometer Calibration"))
        self.root.geometry(self.calculate_scaled_geometry(600, 400))

        self.view = AccelerometerCalibrationView(self.main_frame, model, self)
        self.view.pack(fill="both", expand=True)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self) -> None:
        """Handle window close event."""
        # Attempt to stop any running tests gracefully
        with suppress(tk.TclError, AttributeError):
            self.view._stop_polling()  # noqa: SLF001 # pylint: disable=protected-access

        self.root.destroy()


def argument_parser() -> Namespace:  # pragma: no cover
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
    from ardupilot_methodic_configurator.backend_flightcontroller import FlightController  # noqa: PLC0415
    # pylint: enable=import-outside-toplevel

    parser = ArgumentParser(
        description=_(
            "This main is for testing and development only. "
            "Usually, the AccelerometerCalibrationView is called from another script"
        )
    )
    parser = FlightController.add_argparse_arguments(parser)
    return add_common_arguments(parser).parse_args()


# pylint: disable=duplicate-code
def main() -> None:  # pragma: no cover
    args = argument_parser()

    state = ApplicationState(args)

    setup_logging(state)

    logging_warning(
        _(
            "This main is for testing and development only. "
            "Usually, the AccelerometerCalibrationView is called from another script"
        )
    )

    initialize_flight_controller(state)

    try:
        data_model = AccelerometerCalibrationDataModel(state.flight_controller)
        window = AccelerometerCalibrationWindow(data_model)
        window.root.mainloop()

    except Exception as e:  # pylint: disable=broad-exception-caught
        logging_error(_("Failed to start AccelerometerCalibrationWindow: %(error)s"), {"error": e})
        # Show error to user
        showerror(_("Error"), _("Failed to start accelerometer calibration: %(error)s") % {"error": e})
    finally:
        if state.flight_controller:
            state.flight_controller.disconnect()  # Disconnect from the flight controller


if __name__ == "__main__":  # pragma: no cover
    main()
