"""
Placeholder Paplan log analysis window.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from pathlib import Path
from tkinter import ttk

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_scroll_frame import ScrollFrame


class PaplanLogAnalysisWindow(BaseWindow):
    """Placeholder window for the future Paplan log analysis integration."""

    def __init__(self, root_tk: tk.Tk | tk.Toplevel, logfile: str) -> None:
        super().__init__(root_tk)
        self.logfile = logfile

        self.root.title(_("Paplan Log Analysis"))
        self.root.geometry(self.calculate_scaled_geometry(1050, 800))
        self.center_window(self.root, root_tk)
        self.root.resizable(width=True, height=True)

        self._build_header()
        self._build_footer()

        self.scroll_container = ScrollFrame(self.main_frame)
        self.scroll_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=20, pady=(6, 14))
        self.body_frame = self.scroll_container.view_port

        ttk.Label(
            self.body_frame,
            text=_("Paplan log analysis is not implemented yet."),
            font=("TkDefaultFont", 14),
            wraplength=950,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(24, 2), fill=tk.X)

    def _build_header(self) -> None:
        header = ttk.Frame(self.main_frame)
        header.pack(side=tk.TOP, fill=tk.X, padx=20, pady=(16, 4))

        ttk.Label(header, text=_("Paplan Log Analysis"), font=("TkDefaultFont", 16, "bold")).pack(anchor=tk.W)
        ttk.Label(
            header,
            text=_("Selected log: {filename}").format(filename=Path(self.logfile).name),
            font=("TkDefaultFont", 13),
        ).pack(anchor=tk.W, pady=(8, 0))

    def _build_footer(self) -> None:
        footer = ttk.Frame(self.main_frame)
        footer.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=(0, 14))
        ttk.Button(footer, text=_("Close"), command=self.root.destroy).pack(side=tk.RIGHT)
