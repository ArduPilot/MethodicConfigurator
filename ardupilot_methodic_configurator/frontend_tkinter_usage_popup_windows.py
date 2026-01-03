"""
Central registry for UsagePopupWindow helpers.

When adding a new UsagePopupWindow, please add its helper functions here and
register it in the USAGE_POPUP_WINDOWS dictionary.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional, Union

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_filesystem_program_settings import ProgramSettings
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_font import create_scaled_font, get_safe_font_config
from ardupilot_methodic_configurator.frontend_tkinter_rich_text import RichText
from ardupilot_methodic_configurator.frontend_tkinter_usage_popup_window import ConfirmationPopupWindow, UsagePopupWindow


def _validate_parent(parent: tk.Tk) -> bool:
    return bool(parent and parent.winfo_exists())


def display_workflow_explanation(parent: Optional[tk.Tk] = None) -> Union[BaseWindow, None]:
    """
    Display the workflow explanation popup window.

    This popup explains that AMC is not a ground control station and has a different workflow.
    """
    # Create the popup window
    popup_window = BaseWindow()
    instructions = RichText(
        popup_window.main_frame,
        wrap=tk.WORD,
        height=1,
        bd=0,
        font=create_scaled_font(get_safe_font_config(), 1.5),
    )
    instructions.insert(tk.END, _("This is not a ground control station and it has a different workflow:"))
    UsagePopupWindow.setup_window(
        popup_window,
        _("ArduPilot Methodic Configurator - Workflow"),
        "490x362",
        instructions,
    )

    # Add the image
    image_path = ProgramSettings.workflow_image_filepath()
    try:
        image_label = popup_window.put_image_in_label(popup_window.main_frame, image_path, image_height=141)
        image_label.pack(pady=(0, 10))
    except FileNotFoundError:
        # Fallback if image not found
        fallback_label = ttk.Label(popup_window.main_frame, text=_("[Image not found: AMC_general_workflow.png]"))
        fallback_label.pack(pady=(0, 10))

    # Add the rich text
    rich_text = RichText(
        popup_window.main_frame,
        wrap=tk.WORD,
        height=1,
        bd=0,
        font=create_scaled_font(get_safe_font_config(), 1.5),
    )
    rich_text.insert(tk.END, _("see "))
    rich_text.insert_clickable_link(
        _("quick start guide"), "quickstart_link", "https://ardupilot.github.io/MethodicConfigurator/#quick-start"
    )
    rich_text.insert(tk.END, _(", "))
    rich_text.insert_clickable_link(
        _("YouTube tutorials"), "YouTube_link", "https://www.youtube.com/playlist?list=PL1oa0qoJ9W_89eMcn4x2PB6o3fyPbheA9"
    )
    rich_text.insert(tk.END, _(", "))
    rich_text.insert_clickable_link(
        _("usecases"), "usecases_link", "https://ardupilot.github.io/MethodicConfigurator/USECASES.html"
    )
    rich_text.insert(tk.END, _(" and "))
    rich_text.insert_clickable_link(
        _("usermanual."), "usermanual_link", "https://ardupilot.github.io/MethodicConfigurator/USERMANUAL.html"
    )
    rich_text.config(borderwidth=0, relief="flat", highlightthickness=0, state=tk.DISABLED)
    rich_text.pack(padx=6, pady=10)

    UsagePopupWindow.finalize_setup_window(parent, popup_window, "workflow_explanation")
    return popup_window


def display_component_editor_usage_popup(parent: tk.Tk) -> Union[BaseWindow, None]:
    if not _validate_parent(parent):
        return None

    usage_popup_window = BaseWindow(parent)

    instructions_text = RichText(
        usage_popup_window.main_frame,
        wrap=tk.WORD,
        height=6,
        bd=0,
        font=create_scaled_font(get_safe_font_config(), 1.5),
    )
    instructions_text.insert(tk.END, _("1. Describe the properties of the vehicle components in the window below.\n"))
    instructions_text.insert(tk.END, _("2. Each field has mouse-over tooltips for additional guidance.\n"))
    instructions_text.insert(tk.END, _("3. Optional fields are marked with gray text and can be left blank.\n"))
    instructions_text.insert(tk.END, _("4. Scroll to the bottom of the window to ensure all properties are edited.\n"))
    instructions_text.insert(tk.END, _("5. Press the "))
    instructions_text.insert(tk.END, _("Save data and start configuration"), "italic")
    instructions_text.insert(tk.END, _(" button only after verifying that all information is correct.\n"))
    instructions_text.config(state=tk.DISABLED)

    UsagePopupWindow.display(
        parent,
        usage_popup_window,
        _("How to use the component editor window"),
        "component_editor",
        "690x210",
        instructions_text,
    )
    return usage_popup_window


def confirm_component_properties(parent: tk.Tk) -> bool:
    """Show confirmation dialog for component properties."""
    if not _validate_parent(parent):
        return False

    # Create a popup window similar to the usage instructions
    validation_popup_window = BaseWindow(parent)

    confirmation_text = RichText(
        validation_popup_window.main_frame,
        wrap=tk.WORD,
        height=6,
        bd=0,
        font=create_scaled_font(get_safe_font_config(), 1.5),
    )
    confirmation_text.insert(
        tk.END,
        _(
            "ArduPilot Methodic Configurator only operates correctly if all component properties are correct."
            " ArduPilot parameter values depend on the components used and their connections.\n\n"
            " Have you used the scrollbar on the right side of the window and "
            "entered the correct values for all components?"
        ),
    )

    # Use ConfirmationPopupWindow.display with yes/no buttons
    return ConfirmationPopupWindow.display(
        parent,
        validation_popup_window,
        _("Confirm that all component properties are correct"),
        "component_editor_validation",
        "600x220",
        confirmation_text,
    )


def display_parameter_editor_usage_popup(parent: tk.Tk) -> Union[BaseWindow, None]:
    if not _validate_parent(parent):
        return None

    usage_popup_window = BaseWindow(parent)

    instructions_text = RichText(
        usage_popup_window.main_frame,
        wrap=tk.WORD,
        height=11,
        bd=0,
        font=create_scaled_font(get_safe_font_config(), 1.5),
    )
    instructions_text.insert(tk.END, _("1. Read "))
    instructions_text.insert(tk.END, _("all"), "bold")
    instructions_text.insert(tk.END, _(" the documentation on top of the parameter table\n"))
    instructions_text.insert(tk.END, _("2. Edit the parameter "))
    instructions_text.insert(tk.END, _("New Values"), "italic")
    instructions_text.insert(tk.END, _(" and"), "bold")
    instructions_text.insert(tk.END, _(" their "))
    instructions_text.insert(tk.END, _("Change Reason\n"), "italic")
    instructions_text.insert(tk.END, "   " + _("Documenting change reasons is crucial because it:") + "\n")
    instructions_text.insert(tk.END, "   " + _(" * Promotes thoughtful decisions over impulsive changes") + "\n")
    instructions_text.insert(
        tk.END,
        "   " + _(" * Provides documentation for vehicle certification requirements") + "\n",
    )
    instructions_text.insert(
        tk.END,
        "   " + _(" * Enables validation or suggestions from team members or AI tools") + "\n",
    )
    instructions_text.insert(
        tk.END,
        "   " + _(" * Preserves your reasoning for future reference or troubleshooting") + "\n",
    )
    instructions_text.insert(tk.END, _("3. Use "))
    instructions_text.insert(tk.END, _("Del"), "italic")
    instructions_text.insert(tk.END, _(" and "))
    instructions_text.insert(tk.END, _("Add"), "italic")
    instructions_text.insert(tk.END, _(" buttons to delete and add parameters if necessary\n"))
    instructions_text.insert(tk.END, _("4. Press the "))
    instructions_text.insert(
        tk.END,
        _("Upload selected params to FC, and advance to next param file"),
        "italic",
    )
    instructions_text.insert(tk.END, _(" button\n"))
    instructions_text.insert(tk.END, _("5. Repeat from the top until the program automatically closes"))
    instructions_text.config(state=tk.DISABLED)

    UsagePopupWindow.display(
        parent,
        usage_popup_window,
        _("How to use the parameter file editor and uploader window"),
        "parameter_editor",
        "690x360",
        instructions_text,
    )
    return usage_popup_window


def display_bitmask_parameters_editor_usage_popup(parent: tk.Tk) -> Union[BaseWindow, None]:
    if not _validate_parent(parent):
        return None

    usage_popup_window = BaseWindow(parent)
    instructions_text = RichText(
        usage_popup_window.main_frame,
        wrap=tk.WORD,
        height=5,
        bd=0,
        font=create_scaled_font(get_safe_font_config(), 1.5),
    )
    instructions_text.insert(tk.END, _("Bitmask parameters are editable in four different ways:\n"))
    instructions_text.insert(tk.END, _(" - double-click on the "))
    instructions_text.insert(tk.END, _("New Value"), "italic")
    instructions_text.insert(tk.END, _(" field to edit each bit individually\n"))
    instructions_text.insert(tk.END, _(" - enter the decimal value directly\n"))
    instructions_text.insert(tk.END, _(" - enter '0x' followed by the hex code\n"))
    instructions_text.insert(tk.END, _(" - enter '0b' followed by the binary code\n"))
    instructions_text.config(state=tk.DISABLED)

    UsagePopupWindow.display(
        parent,
        usage_popup_window,
        _("Bitmask parameter editor usage"),
        "bitmask_parameter_editor",
        "690x260",
        instructions_text,
    )
    return usage_popup_window


def only_upload_changed_parameters_usage_popup(parent: tk.Tk) -> Union[BaseWindow, None]:
    if not _validate_parent(parent):
        return None

    usage_popup_window = BaseWindow(parent)
    instructions_text = RichText(
        usage_popup_window.main_frame,
        wrap=tk.WORD,
        height=4,
        bd=0,
        font=create_scaled_font(get_safe_font_config(), 1.5),
    )

    # pylint: disable=line-too-long, import-outside-toplevel
    from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table import NEW_VALUE_DIFFERENT_STR  # noqa: PLC0415, I001
    # pylint: enable=line-too-long, import-outside-toplevel

    instructions_text.insert(tk.END, _("Only"), "bold")
    instructions_text.insert(tk.END, _(" changed parameters (marked by " + NEW_VALUE_DIFFERENT_STR + ") and\n"))
    instructions_text.insert(tk.END, _(" selected for upload get uploaded to the FC.\n\n"))
    instructions_text.insert(tk.END, _("No other FC parameters will be changed."))
    instructions_text.config(state=tk.DISABLED)

    UsagePopupWindow.setup_window(
        usage_popup_window,
        _("What gets uploaded to the FC"),
        "690x260",
        instructions_text,
    )

    # Add the image
    image_path = ProgramSettings.what_gets_uploaded_image_filepath()
    try:
        image_label = usage_popup_window.put_image_in_label(usage_popup_window.main_frame, image_path, image_height=68)
        image_label.pack(pady=(0, 10))
    except FileNotFoundError:
        # Fallback if image not found
        fallback_label = ttk.Label(usage_popup_window.main_frame, text=_("[Image not found: what_gets_uploaded.png]"))
        fallback_label.pack(pady=(0, 10))

    UsagePopupWindow.finalize_setup_window(parent, usage_popup_window, "only_changed_get_uploaded")
    return usage_popup_window
