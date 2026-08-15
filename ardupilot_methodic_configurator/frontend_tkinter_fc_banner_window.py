"""
Display flight-controller banner text.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from tkinter import scrolledtext, ttk

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow


class FlightControllerBannerWindow(BaseWindow):
    """Popup showing the latest flight-controller banner."""

    def __init__(self, parent: tk.Tk | tk.Toplevel, banner_text: list[str]) -> None:
        super().__init__(parent)
        self.root.title(_("Flight Controller Banner"))
        self.root.geometry(self.calculate_scaled_geometry(400, 220))
        self.root.minsize(380, 200)

        text_widget = scrolledtext.ScrolledText(self.main_frame, wrap=tk.WORD, height=10, state=tk.NORMAL)
        text_widget.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        text_widget.insert(tk.END, "\n".join(banner_text) if banner_text else _("No banner messages captured."))
        text_widget.configure(state=tk.DISABLED)

        close_button = ttk.Button(self.main_frame, text=_("Close"), command=self.root.destroy)
        close_button.pack(pady=(0, 8))
        BaseWindow.center_window(self.root, parent)
