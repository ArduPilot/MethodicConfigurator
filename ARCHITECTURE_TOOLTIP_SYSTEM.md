# Tooltip System Architecture & Timer Cleanup

## Overview

The tooltip system provides cross-platform, performant tooltips for the tkinter-based GUI.
This document covers the architecture changes from commit 247255a and the critical timer
cleanup mechanisms.

## Key Design Decisions

### 1. Lazy Loading Architecture

**Problem**: Large parameter tables (100+ parameters) created hundreds of tooltip Toplevel
windows during initialization, causing:

- High memory overhead (each Tk Toplevel window ~8-10KB minimum)
- Slow application startup time
- Unnecessary GUI objects for non-hovered parameters

**Solution**: Tooltips are now created on-demand when the user hovers over a widget.

```text
Timeline:
+-----------------+      +-----------------+      +-----------------+
| Tooltip Init    |      | Mouse Hover     |      | Show Tooltip    |
| (No GUI)        | -->  | Schedule Show   | -->  | Create Window   |
| Bindings only   |      | (250ms delay)   |      | Display         |
+-----------------+      +-----------------+      +-----------------+
  ~0.3ms per item        Timer fires              ~2-3ms per item
```

### 2. Cross-Platform Unification

**Before**: Platform-specific implementations

- macOS: Deferred creation, scheduled show/hide
- Linux/Windows: Pre-created Toplevel, show/hide on demand

**After**: Unified implementation across all platforms

- All platforms use timer-based scheduling
- Timer-based show/hide prevents flicker when moving through dense UIs
- Identical behavior ensures consistent UX

### 3. Timer Management

The tooltip system uses three types of timers:

```text
+--------------------------------------------------------------+
| Timer Types and Lifecycle                                    |
+--------------------------------------------------------------+
|                                                               |
| "show" timer:                                                 |
|   - Scheduled by: schedule_show()                             |
|   - Fires: TOOLTIP_SHOW_DELAY_MS (250ms)                      |
|   - Executes: create_show()                                   |
|   - Cleaned by: _cancel_show(), _on_widget_destroy()          |
|                                                               |
| "hide" timer:                                                 |
|   - Removed in the current design                              |
|   - Tooltip is destroyed immediately by destroy_hide()         |
|   - No hide-delay behavior remains                            |
|                                                               |
| "alpha" timer (macOS only):                                   |
|   - Scheduled by: create_show() after deiconify               |
|   - Fires: 50ms after deiconify                               |
|   - Executes: _activate_alpha() - fades in tooltip            |
|   - Cleaned by: _cancel_timer("alpha"), _on_widget_destroy()  |
|                                                               |
+--------------------------------------------------------------+
```

## Critical Timer Cleanup Mechanisms

### 1. Widget Destruction Handler (`_on_widget_destroy`)

This is the **critical safety mechanism** that prevents timer leaks:

```python
def _on_widget_destroy(self, event: Optional[tk.Event] = None) -> None:
    """Stop any active timers if the widget is destroyed."""
    self._cancel_show()          # Cancel "show" timer if pending
    self._cancel_timer("alpha")  # Cancel "alpha" timer if pending

    if self.tooltip:
        with contextlib.suppress(tk.TclError):
            self.tooltip.destroy()
        self.tooltip = None
```

**Why this is critical**:

- If the widget is destroyed while a timer is pending, Tk will try to fire a callback
  on a non-existent widget
- This causes `tk.TclError: invalid command name "..."`
- The handler cleans up ALL timers before widget destruction

**Binding registered in `__init__`**:

```python
self.widget.bind("<Destroy>", self._on_widget_destroy, "+")
```

### 2. Timer Cancellation with Error Suppression

The `_cancel_timer()` method handles already-fired or stale timers gracefully:

```python
def _cancel_timer(self, name: str) -> None:
    """Safely cancel a timer and remove it."""
    timer_id = self.timers.pop(name, None)
    if timer_id:
        with contextlib.suppress(tk.TclError):
            self.widget.after_cancel(timer_id)
```

**Edge cases handled**:

1. Timer ID in dict but Tk already fired it -- `tk.TclError` suppressed
2. Widget destroyed before cancellation -- `tk.TclError` suppressed
3. Multiple cancellation calls -- `timers.pop(name, None)` returns None safely
4. Stale timer IDs from previous interactions -- Tk's `after_cancel` silently ignores

### 3. Mutual Timer Cancellation Pattern

When entering a widget that has a pending show timer:

```python
def schedule_show(self, _event: Optional[tk.Event] = None) -> None:
    """Delay tooltip creation slightly to avoid flicker during pointer movement."""
    self._cancel_show()  # Cancel any pending show
    self.timers["show"] = self.widget.after(TOOLTIP_SHOW_DELAY_MS, self.create_show)
```

**Purpose**: Prevents flicker when user quickly moves mouse through dense UI elements:

- Mouse leave triggers immediate destroy via `destroy_hide()`
- Mouse re-enters before tooltip appears
- Previous show timer canceled, new show timer scheduled
- Result: Tooltip appears cleanly without flashing

### 4. Pointer Position Validation

The `create_show()` method validates pointer position before creating tooltip:

```python
def create_show(self, _event: Optional[tk.Event] = None) -> None:
    """Create and show the tooltip when the pointer is still over the widget."""
    try:
        pointed = self.widget.winfo_containing(
            self.widget.winfo_pointerx(), self.widget.winfo_pointery()
        )
        widget_path = str(self.widget)
        pointed_path = "" if pointed is None else str(pointed)
        if pointed is None or (
            pointed_path != widget_path
            and not pointed_path.startswith(widget_path + ".")
        ):
            return  # Pointer no longer over widget
    except tk.TclError:
        return  # Widget destroyed during timer execution
```

**Why this is necessary**:

- Timer fires even if widget is destroyed (TclError caught)
- Pointer may have left widget during 250ms delay
- Prevents creating orphaned tooltip windows

## Race Conditions Prevented

### 1. Multiple Concurrent Tooltips

**Problem**: If `create_show()` is called multiple times (e.g., multiple Enter events queued)

**Solution**: Check if tooltip already exists:

```python
if self.tooltip:
    Tooltip._active_tooltip = self
    return  # Avoid redundant tooltip creation
```

### 2. Widget Destroyed During Timer Delay

**Problem**: User closes dialog while tooltip timer is pending

**Solution**: `_on_widget_destroy()` cancels all timers before widget is destroyed

### 3. Multiple Enter/Leave Rapid Succession

**Problem**: User quickly moves mouse through dense parameter table

**Solution**: Mutual cancellation in `schedule_show()`:

```python
self._cancel_show()  # Previous show timer canceled
```

## Performance Impact

### Initialization Phase

- **Before**: Each tooltip created a Tk Toplevel window (8-10KB memory, tens of milliseconds per tooltip)
- **After**: Only Tooltip wrapper objects are created lazily
- **Measured result**: ~0.21ms per tooltip for lazy initialization
- **Old eager baseline**: ~12ms per tooltip for up-front Toplevel creation
- **Result**: Lazy init reduces startup overhead by an order of magnitude for large tables

### Hover Phase

- **Lazy first hover**: Measured ~285ms per tooltip with real event-loop and visible windows
  - Includes the 250ms `TOOLTIP_SHOW_DELAY_MS` timer
  - Includes actual Tk event handling, window manager work, and painting
- **Eager show**: Measured ~0.11ms per tooltip when the window already exists
- **Result**: Lazy loading shifts cost from startup to first hover
  - good when many tooltips are never hovered
  - less ideal when every tooltip is visited immediately

### Trade-off Analysis

- Large parameter tables load much faster
- Memory usage significantly reduced
- Better responsiveness during navigation after first hover
- First tooltip hover includes the 250ms show delay plus creation cost
- Users moving mouse over parameters for the first time see a noticeable, but intentional, delay

## Verification Checklist

For commit review and testing:

- [x] All timers cleaned up on widget destruction
- [x] Stale timer IDs handled gracefully
- [x] Pointer position validated before creating tooltip
- [x] No memory leaks from orphaned Tk objects
- [x] Consistent behavior across macOS, Linux, Windows
- [x] Edge case: widget destroyed during create_show()
- [x] Edge case: multiple Enter/Leave in rapid succession
- [x] Edge case: timer fires after widget destroyed
- [x] Performance benchmark shows expected improvements
- [x] Backward compatibility with existing Tooltip API

## Testing Strategy

### Unit Tests (in `bdd_frontend_tkinter_show.py`)

- Timer cancellation on widget destruction
- Pointer position validation
- Redundant tooltip prevention
- Cross-platform behavior consistency

### Integration Tests

- Large parameter table (100+ tooltips) initialization
- Rapid mouse movement through dense parameter table
- Widget destruction with pending timers
- Application shutdown with active tooltips

### Performance Benchmarks (in `benchmarks/tooltip_performance.py`)

- Lazy vs eager initialization
- Lazy first-hover creation vs eager show
- Cleanup and destruction
- Real Tk event-loop and visible-window timing

## Debugging Tips

### If tooltips don't appear after hover

1. Check `TOOLTIP_SHOW_DELAY_MS` constant (currently 250ms)
2. Verify `create_show()` isn't returning early due to pointer check
3. Check browser console for `tk.TclError` in timer execution

### If memory usage is high

1. Check for orphaned tooltip windows with `tooltip.tooltip is not None`
2. Verify `_on_widget_destroy()` is being called
3. Check timer dict for stale entries: `tooltip.timers`

### If tooltips flicker during mouse movement

1. Check `schedule_show()` is canceling previous timers
2. Increase `TOOLTIP_SHOW_DELAY_MS` to reduce flicker
3. Verify pointer validation logic in `create_show()`

## Related Code Files

- `frontend_tkinter_show.py`: Main tooltip implementation
- `bdd_frontend_tkinter_show.py`: Comprehensive test suite
- `test_tooltip_performance_benchmark.py`: Performance validation
