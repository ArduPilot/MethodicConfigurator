"""
TKinter base classes reused in multiple parts of the code.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

# https://wiki.tcl-lang.org/page/Changing+Widget+Colors

import contextlib
import tkinter as tk
from platform import system as platform_system
from tkinter import messagebox, ttk
from typing import Any, ClassVar, NamedTuple, Optional, cast
from weakref import WeakKeyDictionary

from ardupilot_methodic_configurator import _

# Tooltip positioning constants
TOOLTIP_MAX_OFFSET = 100  # Maximum horizontal offset from widget edge
TOOLTIP_VERTICAL_OFFSET = 10  # Vertical offset when positioning above widget
TOOLTIP_SHOW_DELAY_MS = 250  # Delay before showing to avoid flicker while moving across dense UIs


class MonitorBounds(NamedTuple):
    """Screen bounds storing top-left and bottom-right coordinates."""

    left: int
    top: int
    right: int
    bottom: int


# Cache for monitor bounds per toplevel window to avoid repeated queries.
# Uses WeakKeyDictionary so cache entries are automatically removed when toplevel is garbage collected.
_monitor_bounds_cache: WeakKeyDictionary[tk.Misc, MonitorBounds] = WeakKeyDictionary()


def _is_valid_monitor_bounds(bounds: Optional[MonitorBounds]) -> bool:
    """
    Validate monitor bounds have positive dimensions between 100x100 and 65535x65535.

    The validation range ensures:
    - Minimum 100x100: Reject degenerate/invalid displays (0x0, negative dimensions)
    - Maximum 65535x65535: Accommodate multi-monitor setups including:
      * Triple 4K monitors: 11520x2160 (3 x 3840x2160)
      * Quad HD monitors: 7680x4320 (2 x 2 array)
      * Virtual desktop spanning: up to 16 monitors theoretically
      While Win32 RECT uses signed 32-bit coordinates (LONG type), practical multi-monitor
      setups rarely exceed 65535 pixels in any dimension. This limit balances broad compatibility
      with validation strictness to catch API errors or corrupted data

    Args:
        bounds: MonitorBounds to validate, or None

    Returns:
        True if bounds are valid and within acceptable range, False otherwise

    """
    if bounds is None:
        return False

    width = bounds.right - bounds.left
    height = bounds.bottom - bounds.top

    return 100 <= width <= 65535 and 100 <= height <= 65535


def _get_validated_bounds(bounds: Optional[MonitorBounds]) -> Optional[MonitorBounds]:
    """Return bounds if valid, otherwise None."""
    return bounds if _is_valid_monitor_bounds(bounds) else None


def _monitor_bounds_tk(widget: tk.Misc) -> MonitorBounds:
    """
    Return bounds reported by Tk for the screen hosting the widget.

    This is a fallback method when platform-specific APIs fail.
    Uses Tk's virtual root coordinates which represent the screen containing
    the toplevel window.

    Args:
        widget: Any Tkinter widget whose screen bounds are needed

    Returns:
        MonitorBounds with screen coordinates in pixels

    Example:
        >>> bounds = _monitor_bounds_tk(my_button)
        >>> print(f"Screen: {bounds.left},{bounds.top} to {bounds.right},{bounds.bottom}")

    """
    toplevel = widget.winfo_toplevel()
    toplevel.update_idletasks()

    # Get virtual root position (top-left corner of the screen)
    vroot_x = toplevel.winfo_vrootx()
    vroot_y = toplevel.winfo_vrooty()

    # Get virtual root dimensions
    width = toplevel.winfo_vrootwidth()
    height = toplevel.winfo_vrootheight()

    # Fallback if virtual root reports invalid dimensions
    if width <= 0 or height <= 0:
        width = toplevel.winfo_screenwidth()
        height = toplevel.winfo_screenheight()

    return MonitorBounds(vroot_x, vroot_y, vroot_x + width, vroot_y + height)


def _monitor_bounds_windows(widget: tk.Misc) -> Optional[MonitorBounds]:  # pylint: disable=too-many-return-statements # noqa: PLR0911
    """Use the Win32 API to determine the monitor that hosts the widget."""
    try:
        import ctypes  # pylint: disable=import-outside-toplevel # noqa: PLC0415 # type: ignore[import-outside-toplevel]
        from ctypes import (  # pylint: disable=import-outside-toplevel # noqa: PLC0415 # type: ignore[import-outside-toplevel]
            wintypes,
        )
    except ImportError:  # pragma: no cover - platform specific
        return None

    class MONITORINFO(ctypes.Structure):  # pylint: disable=too-few-public-methods # type: ignore[misc]
        """Win32 MONITORINFO structure for GetMonitorInfoW API."""

        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", wintypes.RECT),
            ("rcWork", wintypes.RECT),
            ("dwFlags", wintypes.DWORD),
        ]

    windll = getattr(ctypes, "windll", None)
    if windll is None:
        return None

    try:
        # Get widget's HWND - may fail on destroyed widgets or virtual displays
        hwnd = widget.winfo_id()
    except tk.TclError:
        return None

    # MONITOR_DEFAULTTONEAREST: If the window is not on any monitor, return nearest monitor
    MONITOR_DEFAULTTONEAREST = 2  # noqa: N806 # pylint: disable=invalid-name
    monitor_handle = windll.user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
    if not monitor_handle:
        return None

    monitor_info = MONITORINFO()
    monitor_info.cbSize = ctypes.sizeof(MONITORINFO)  # pylint: disable=invalid-name,attribute-defined-outside-init

    if windll.user32.GetMonitorInfoW(monitor_handle, ctypes.byref(monitor_info)) == 0:
        return None

    rect = monitor_info.rcMonitor
    bounds = MonitorBounds(rect.left, rect.top, rect.right, rect.bottom)

    # Validate bounds before returning
    if not _is_valid_monitor_bounds(bounds):
        return None

    return bounds


def _get_appkit_screens() -> Optional[Any]:  # noqa: ANN401
    """
    Get NSScreen object from AppKit, return None if unavailable.

    AppKit is macOS-specific framework for accessing screen information.
    This function safely imports NSScreen without failing on other platforms.

    Returns:
        NSScreen class if on macOS with AppKit available, None otherwise

    Note:
        The import is done at runtime to avoid import errors on non-macOS platforms.

    """
    try:
        import importlib  # pylint: disable=import-outside-toplevel # noqa: PLC0415 # type: ignore[import-outside-toplevel]

        appkit = importlib.import_module("AppKit")
    except ImportError:  # pragma: no cover - platform specific
        return None

    return getattr(appkit, "NSScreen", None)


def _convert_cocoa_to_tk_bounds(frame: Any, primary_height: int) -> MonitorBounds:  # noqa: ANN401
    """
    Convert Cocoa screen frame (bottom-left origin) to Tk bounds (top-left origin).

    macOS uses Cocoa coordinate system with origin at bottom-left,
    while Tk uses origin at top-left. This function performs the conversion.

    Args:
        frame: NSScreen.frame() object containing origin and size
        primary_height: Height of primary screen in pixels, used for Y-axis conversion

    Returns:
        MonitorBounds with Tk-compatible top-left origin coordinates

    Example:
        Cocoa: (0, 0) is bottom-left
        Tk:    (0, 0) is top-left

        For a 1080p screen:
        - Cocoa Y=0 → Tk Y=1080
        - Cocoa Y=1080 → Tk Y=0

    """
    try:
        # Extract Cocoa coordinates (bottom-left origin)
        cocoa_x = int(frame.origin.x)
        cocoa_y = int(frame.origin.y)  # Distance from bottom of primary screen
        width = int(frame.size.width)
        height = int(frame.size.height)
    except (AttributeError, ValueError, TypeError) as e:
        # AttributeError: frame missing expected origin/size attributes
        # ValueError/TypeError: Conversion to int failed
        msg = f"Invalid AppKit frame object: {e}"
        raise ValueError(msg) from e

    # Convert Y coordinate: bottom-left → top-left
    # Formula: y_top = primary_height - y_bottom - height
    tk_x = cocoa_x
    tk_y = primary_height - (cocoa_y + height)

    return MonitorBounds(tk_x, tk_y, tk_x + width, tk_y + height)


def _find_screen_containing_point(
    screens: Any,  # noqa: ANN401
    center_x: int,
    center_y: int,
    primary_height: int,
) -> Optional[MonitorBounds]:
    """
    Find which screen contains the given point and return its bounds.

    Iterates through all screens to find the one containing the specified point.
    Used for multi-monitor setups to determine which screen hosts a widget.

    Args:
        screens: Array of NSScreen objects from AppKit
        center_x: X coordinate of point to test (in Tk coordinates)
        center_y: Y coordinate of point to test (in Tk coordinates)
        primary_height: Height of primary screen for coordinate conversion

    Returns:
        MonitorBounds of the screen containing the point, or None if not found

    Note:
        The function performs bounds validation to ensure screen dimensions are reasonable.

    """
    for screen in screens:
        frame = screen.frame()
        bounds = _convert_cocoa_to_tk_bounds(frame, primary_height)

        # Check if point is within this screen's rectangle
        point_in_screen = bounds.left <= center_x < bounds.right and bounds.top <= center_y < bounds.bottom

        # Return first valid screen containing the point
        if point_in_screen and _is_valid_monitor_bounds(bounds):
            return bounds

    return None


def _monitor_bounds_macos(widget: tk.Misc) -> Optional[MonitorBounds]:
    """Use AppKit to detect monitor bounds, converting from Cocoa (bottom-left) to Tk (top-left) coordinates."""
    ns_screen = _get_appkit_screens()
    if ns_screen is None:
        return None

    try:
        screens = ns_screen.screens()
        if not screens or len(screens) == 0:
            return None

        toplevel = widget.winfo_toplevel()
        center_x = toplevel.winfo_rootx() + (toplevel.winfo_width() // 2)
        center_y = toplevel.winfo_rooty() + (toplevel.winfo_height() // 2)
    except (tk.TclError, AttributeError, ValueError, TypeError):
        # tk.TclError: Widget destroyed or invalid
        # AttributeError: AppKit object missing expected method/property
        # ValueError: Invalid coordinate conversion
        # TypeError: Unexpected AppKit object type
        return None

    # Primary screen is screens[0], used for coordinate conversion
    primary_height = int(screens[0].frame().size.height)

    return _find_screen_containing_point(screens, center_x, center_y, primary_height)


def get_monitor_bounds(widget: tk.Misc) -> MonitorBounds:
    """
    Return validated cached monitor bounds using platform APIs with Tk fallback.

    This is the main entry point for getting screen bounds. It uses a three-tier approach:
    1. Check cache for previously computed bounds (fast path)
    2. Query platform-specific APIs (Windows: Win32, macOS: AppKit)
    3. Fallback to Tk virtual root (cross-platform but less accurate)

    Args:
        widget: Any Tkinter widget whose monitor bounds are needed

    Returns:
        MonitorBounds containing the screen's left, top, right, bottom coordinates

    Note:
        Results are cached per toplevel window using WeakKeyDictionary.
        Cache automatically invalidates when toplevel is destroyed.

    Example:
        >>> button = ttk.Button(root, text="Click me")
        >>> bounds = get_monitor_bounds(button)
        >>> print(f"Monitor size: {bounds.right - bounds.left}x{bounds.bottom - bounds.top}")

    """
    # Try to get toplevel and check cache
    try:
        toplevel = widget.winfo_toplevel()
        if hasattr(toplevel, "winfo_id") and toplevel in _monitor_bounds_cache:
            cached_bounds = _monitor_bounds_cache[toplevel]
            # Invalidate cache if widget moved outside cached bounds (likely different monitor)
            try:
                current_x = toplevel.winfo_rootx()
                current_y = toplevel.winfo_rooty()
                # Check if toplevel is still within cached monitor bounds
                if (
                    cached_bounds.left <= current_x < cached_bounds.right
                    and cached_bounds.top <= current_y < cached_bounds.bottom
                ):
                    return cached_bounds
            except tk.TclError:
                pass
    except tk.TclError:
        toplevel = None

    # Query platform-specific API for accurate multi-monitor support
    bounds = None
    if platform_system() == "Windows":
        bounds = _get_validated_bounds(_monitor_bounds_windows(widget))
    elif platform_system() == "Darwin":
        bounds = _get_validated_bounds(_monitor_bounds_macos(widget))

    # Fallback to Tk virtual root if platform API failed
    if bounds is None:
        bounds = _monitor_bounds_tk(widget)

    # Cache the result for future calls (until toplevel is destroyed)
    if toplevel is not None:
        try:
            if hasattr(toplevel, "winfo_id"):
                _monitor_bounds_cache[toplevel] = bounds
        except tk.TclError:
            # Widget destroyed during caching, ignore
            pass

    return bounds


def show_error_message(title: str, message: str, root: Optional[tk.Tk] = None) -> None:
    if root is None:
        root = tk.Tk(className="ArduPilotMethodicConfigurator")
        # Set the theme to 'alt'
        style = ttk.Style()
        style.theme_use("alt")
        root.withdraw()  # Hide the main window
        messagebox.showerror(title, message)
        root.destroy()
    else:
        messagebox.showerror(title, message)


def show_warning_message(title: str, message: str, root: Optional[tk.Tk] = None) -> None:
    if root is None:
        root = tk.Tk(className="ArduPilotMethodicConfigurator")
        # Set the theme to 'alt'
        style = ttk.Style()
        style.theme_use("alt")
        root.withdraw()  # Hide the main window
        messagebox.showwarning(title, message)
        root.destroy()
    else:
        messagebox.showwarning(title, message)


def ask_yesno_message(title: str, message: str, root: Optional[tk.Tk] = None) -> bool:
    if root is None:
        root = tk.Tk(className="ArduPilotMethodicConfigurator")
        # Set the theme to 'alt'
        style = ttk.Style()
        style.theme_use("alt")
        root.withdraw()  # Hide the main window
        result = messagebox.askyesno(title, message)
        root.destroy()
        return result
    return messagebox.askyesno(title, message)


def show_no_param_files_error(_dirname: str) -> None:
    error_message = _(
        "No intermediate parameter files found in the selected '{_dirname}' vehicle directory.\n"
        "Please select and step inside a vehicle directory containing valid ArduPilot intermediate parameter files.\n\n"
        "Make sure to step inside the directory (double-click) and not just select it."
    )
    show_error_message(_("No Parameter Files Found"), error_message.format(**locals()))


def show_no_connection_error(_error_string: str) -> None:
    error_message = _("{_error_string}\n\nPlease connect a flight controller to the PC,\nwait at least 7 seconds and retry.")
    show_error_message(_("No Connection to the Flight Controller"), error_message.format(**locals()))


def calculate_tooltip_position(  # noqa: PLR0913 # pylint: disable=too-many-arguments, too-many-positional-arguments
    widget_x: int,
    widget_y: int,
    widget_width: int,
    widget_height: int,
    tooltip_width: int,
    tooltip_height: int,
    area_left: int,
    area_top: int,
    area_width: int,
    area_height: int,
    position_below: bool,
) -> tuple[int, int]:
    """Calculate the tooltip position constrained to the provided rectangular area."""
    area_right = area_left + area_width
    area_bottom = area_top + area_height

    x = widget_x + min(widget_width // 2, TOOLTIP_MAX_OFFSET)
    y = widget_y + (widget_height if position_below else -TOOLTIP_VERTICAL_OFFSET)

    # Keep tooltip inside the allowed horizontal span
    if x + tooltip_width > area_right:
        x = area_right - tooltip_width
    x = max(x, area_left)

    # Keep tooltip inside the allowed vertical span
    if y + tooltip_height > area_bottom:
        y = area_bottom - tooltip_height
    y = max(y, area_top)

    return x, y


class Tooltip:
    """
    A tooltip class for displaying tooltips on widgets.

    Creates a tooltip that appears when the mouse hovers over a widget and disappears when the mouse leaves the widget.
    """

    _active_tooltip: ClassVar[Optional["Tooltip"]] = None

    def __init__(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        widget: tk.Widget,
        text: str,
        position_below: bool = True,
        tag_name: str = "",
        toplevel_class: Optional[type] = None,
    ) -> None:
        self.widget: tk.Widget = widget
        self.text: str = text
        self.tooltip: Optional[tk.Toplevel] = None
        self.position_below: bool = position_below
        self.toplevel_class = toplevel_class or tk.Toplevel
        self.timers: dict[str, Optional[str]] = {}
        self._is_aqua: bool = widget.tk.call("tk", "windowingsystem") == "aqua"

        # Bind the <Enter> and <Leave> events to show and hide the tooltip
        # Defer tooltip creation slightly to avoid flashing while moving through dense tables.
        if tag_name and isinstance(self.widget, tk.Text):
            self.widget.tag_bind(tag_name, "<Enter>", self.schedule_show, "+")
            self.widget.tag_bind(tag_name, "<Leave>", self.destroy_hide, "+")
        else:
            self.widget.bind("<Enter>", self.schedule_show, "+")
            self.widget.bind("<Leave>", self.destroy_hide, "+")
            self.widget.bind("<ButtonPress>", self.destroy_hide, "+")

        self.widget.bind("<Destroy>", self._on_widget_destroy, "+")

    def _cancel_timer(self, name: str) -> None:
        """Safely cancel a timer and remove it."""
        timer_id = self.timers.pop(name, None)
        if timer_id:
            with contextlib.suppress(tk.TclError):
                self.widget.after_cancel(timer_id)

    def _cancel_show(self) -> None:
        self._cancel_timer("show")

    def _on_widget_destroy(self, event: Optional[tk.Event] = None) -> None:
        """Stop any active timers if the widget is destroyed."""
        if event and getattr(event, "widget", None) is not self.widget:
            return
        self.force_hide()

    def _hide_active_tooltip(self) -> None:
        """Hide another active tooltip before showing this one."""
        if Tooltip._active_tooltip and Tooltip._active_tooltip is not self:
            with contextlib.suppress(tk.TclError):
                Tooltip._active_tooltip.force_hide()
            Tooltip._active_tooltip = None

    def schedule_show(self, _event: Optional[tk.Event] = None) -> None:
        """Delay tooltip creation slightly to avoid flicker during pointer movement."""
        self._cancel_show()
        self.timers["show"] = self.widget.after(TOOLTIP_SHOW_DELAY_MS, self.create_show)

    def create_show(self, _event: Optional[tk.Event] = None) -> None:
        """Create and show the tooltip when the pointer is still over the widget after the delay."""
        self._cancel_show()

        try:
            pointed = self.widget.winfo_containing(self.widget.winfo_pointerx(), self.widget.winfo_pointery())
            widget_path = str(self.widget)
            pointed_path = "" if pointed is None else str(pointed)
            if pointed is None or (pointed_path != widget_path and not pointed_path.startswith(widget_path + ".")):
                return
        except tk.TclError:
            return

        self._hide_active_tooltip()

        if self.tooltip:
            Tooltip._active_tooltip = self
            return  # Avoid redundant tooltip creation

        self.tooltip = cast("tk.Toplevel", self.toplevel_class(self.widget, bg="#ffffe0"))

        # Remove the windows buttons on all OSs
        self.tooltip.wm_overrideredirect(True)  # noqa: FBT003

        if not self._is_aqua:
            self.tooltip.withdraw()

        if self._is_aqua:
            self.tooltip.attributes("-alpha", 0.0)

            try:
                self.tooltip.tk.call(
                    "::tk::unsupported::MacWindowStyle",
                    "style",
                    self.tooltip._w,  # type: ignore[attr-defined] # noqa: SLF001 # pylint: disable=protected-access
                    "help",
                    "noActivates",
                )
            except (AttributeError, tk.TclError):  # Fallback when MacWindowStyle or Tk attribute access is unsupported
                with contextlib.suppress(tk.TclError):
                    self.tooltip.wm_attributes("-alpha", 1.0)  # Ensure opacity
                    self.tooltip.wm_attributes("-topmost", True)  # Keep on top # noqa: FBT003
        tooltip_label = ttk.Label(
            self.tooltip, text=self.text, background="#ffffe0", relief="solid", borderwidth=1, justify=tk.LEFT
        )
        tooltip_label.pack()
        self.position_tooltip()

        if self.tooltip.winfo_exists():
            Tooltip._active_tooltip = self

            self.tooltip.update_idletasks()  # Force macOS to finish rendering text and colors
            self.tooltip.deiconify()  # still invisible on Mac

            if self._is_aqua:

                def _activate_alpha() -> None:
                    self.timers.pop("alpha", None)
                    if self.tooltip and self.tooltip.winfo_exists() and Tooltip._active_tooltip is self:
                        with contextlib.suppress(tk.TclError):
                            self.tooltip.attributes("-alpha", 1.0)

                # Call _activate_alpha after 50ms
                self.timers["alpha"] = self.widget.after(50, _activate_alpha)

    def position_tooltip(self) -> None:
        """Position tooltip within monitor bounds, handling widget destruction gracefully."""
        if not self.tooltip:
            return

        try:
            # Ensure tooltip geometry is calculated
            self.tooltip.update_idletasks()
            tooltip_width = self.tooltip.winfo_reqwidth()
            tooltip_height = self.tooltip.winfo_reqheight()

            toplevel = self.widget.winfo_toplevel()
            monitor_left, monitor_top, monitor_right, monitor_bottom = get_monitor_bounds(toplevel)
            monitor_width = monitor_right - monitor_left
            monitor_height = monitor_bottom - monitor_top

            x, y = calculate_tooltip_position(
                self.widget.winfo_rootx(),
                self.widget.winfo_rooty(),
                self.widget.winfo_width(),
                self.widget.winfo_height(),
                tooltip_width,
                tooltip_height,
                monitor_left,
                monitor_top,
                monitor_width,
                monitor_height,
                self.position_below,
            )

            self.tooltip.geometry(f"+{x}+{y}")
        except tk.TclError:
            # Widget or tooltip was destroyed during positioning
            # Silently ignore - tooltip will be recreated on next hover if needed
            pass

    def force_hide(self) -> None:
        """Immediately destroy the tooltip globally across all OSs."""
        self._cancel_show()
        self._cancel_timer("alpha")
        if self.tooltip:
            with contextlib.suppress(tk.TclError):
                self.tooltip.destroy()
            self.tooltip = None
        if Tooltip._active_tooltip is self:
            Tooltip._active_tooltip = None

    def destroy_hide(self, event: Optional[tk.Event] = None) -> None:  # noqa: ARG002 # pylint: disable=unused-argument
        """Immediately destroy the tooltip when the mouse leaves the widget, on all platforms."""
        self.force_hide()


def show_tooltip(widget: tk.Widget, text: str, position_below: bool = True) -> Tooltip:
    return Tooltip(widget, text, position_below=position_below, tag_name="")


def show_tooltip_on_richtext_tag(widget: tk.Text, text: str, tag_name: str, position_below: bool = True) -> Tooltip:
    return Tooltip(widget, text, position_below=position_below, tag_name=tag_name)
