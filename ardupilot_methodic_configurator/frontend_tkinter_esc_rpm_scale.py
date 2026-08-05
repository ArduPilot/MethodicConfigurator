"""
Tkinter frontend for the ESC RPM scale plugin.

This file is part of ArduPilot Methodic Configurator.
https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Erwan Billard

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from tkinter import Frame, ttk
from tkinter.messagebox import showerror, showinfo
from tkinter.simpledialog import askfloat

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.data_model_esc_rpm_scale import EscRpmScaleDataModel
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.plugin_constants import PLUGIN_ESC_RPM_SCALE
from ardupilot_methodic_configurator.plugin_factory import plugin_factory


class EscRpmScaleView(Frame):
    """Prompt for an RPM scale factor and upload the generated Lua script."""

    def __init__(
        self,
        parent: tk.Frame | ttk.Frame,
        model: EscRpmScaleDataModel,
        base_window: BaseWindow,
    ) -> None:
        super().__init__(parent)
        self.model = model
        self.base_window = base_window
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True)

        content_frame = ttk.LabelFrame(main_frame, text=_("ESC RPM scaling"))
        content_frame.pack(fill="both", expand=True, padx=10, pady=10)

        if self.model.is_hobbywing_6x_se():
            text = _(
                "Hobbywing 6X SE detected. Its reported RPM requires a 0.714 scale factor. "
                "Generate and upload the Lua correction script before flight."
            )
        else:
            text = _("Generate an ArduPilot Lua script that applies an RPM scale factor to ESC telemetry outputs.")
        ttk.Label(content_frame, text=text, justify="left", wraplength=420).pack(fill="x", padx=8, pady=8)
        ttk.Button(
            content_frame,
            text=_("Generate and upload RPM scale script"),
            command=self._generate_and_upload,
        ).pack(pady=(0, 10))

    def _generate_and_upload(self) -> None:
        scale_factor = askfloat(
            _("ESC RPM scale factor"),
            _("Enter the RPM scale factor to apply to ESC outputs:"),
            initialvalue=self.model.recommended_scale,
            minvalue=0.001,
            maxvalue=100.0,
            parent=self,
        )
        if scale_factor is None:
            return

        try:
            uploaded = self.model.generate_and_upload_script(scale_factor)
        except (OSError, RuntimeError, ValueError) as exc:
            showerror(_("ESC RPM script upload failed"), str(exc), parent=self)
            return

        if uploaded:
            showinfo(
                _("ESC RPM script uploaded"),
                _("The Lua script was uploaded to /APM/Scripts/esc_rpm_scale.lua."),
                parent=self,
            )
        else:
            showerror(
                _("ESC RPM script upload failed"),
                _("A flight controller connection with MAVFTP support is required."),
                parent=self,
            )

    def on_activate(self) -> None:
        """No resources need activation."""

    def on_deactivate(self) -> None:
        """No resources need deactivation."""


def _create_esc_rpm_scale_view(parent: object, model: object, base_window: object) -> EscRpmScaleView:
    return EscRpmScaleView(parent, model, base_window)  # type: ignore[arg-type]


def register_esc_rpm_scale_plugin() -> None:
    """Register the ESC RPM scale plugin with the factory."""
    plugin_factory.register(PLUGIN_ESC_RPM_SCALE, _create_esc_rpm_scale_view)
