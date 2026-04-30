#!/usr/bin/env python3

"""
Performance benchmark for tooltip creation with lazy loading.

This module benchmarks tooltip performance to verify that lazy loading
provides measurable improvements for large parameter tables.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import gc
import logging
import statistics
import time
import tkinter as tk
from typing import Callable, NamedTuple

try:
    import psutil
except ImportError:  # pragma: no cover
    psutil = None

from ardupilot_methodic_configurator.frontend_tkinter_show import Tooltip

logger = logging.getLogger(__name__)


class BenchmarkResult(NamedTuple):
    """Container for benchmark timing results."""

    scenario: str
    num_tooltips: int
    total_time_ms: float
    avg_time_per_tooltip_ms: float
    stddev_ms: float
    memory_estimate_kb: float


BENCHMARK_RUNS = 5


def _get_memory_rss_kb() -> float:
    if psutil is None:
        return -1.0
    gc.collect()
    return psutil.Process().memory_info().rss / 1024.0


def _prepare_widget(root: tk.Tk, text: str, x: int, y: int) -> tk.Widget:
    widget = tk.Label(root, text=text, relief="solid", borderwidth=1)
    widget.place(x=x, y=y, width=120, height=20)
    widget.update_idletasks()
    widget.winfo_pointerx = lambda: x + 10
    widget.winfo_pointery = lambda: y + 10
    widget.winfo_containing = lambda *_, widget=widget: widget
    return widget


def _wait_for_tooltip_visible(root: tk.Tk, tooltip: Tooltip, timeout_s: float = 2.0) -> bool:
    deadline = time.perf_counter() + timeout_s
    while time.perf_counter() < deadline:
        root.update()
        if tooltip.tooltip and tooltip.tooltip.winfo_exists() and tooltip.tooltip.winfo_ismapped():
            return True
    return False


def _wait_for_tooltip_hidden(root: tk.Tk, tooltip: Tooltip, timeout_s: float = 2.0) -> bool:
    deadline = time.perf_counter() + timeout_s
    while time.perf_counter() < deadline:
        root.update()
        if not (tooltip.tooltip and tooltip.tooltip.winfo_exists() and tooltip.tooltip.winfo_ismapped()):
            return True
    return False


def _repeat_benchmark(func: Callable[..., BenchmarkResult], *args, runs: int = BENCHMARK_RUNS) -> BenchmarkResult:
    results = [func(*args) for _ in range(runs)]
    avg_total = statistics.mean(result.total_time_ms for result in results)
    avg_item = statistics.mean(result.avg_time_per_tooltip_ms for result in results)
    stddev_item = statistics.stdev(result.avg_time_per_tooltip_ms for result in results) if runs > 1 else 0.0
    avg_mem = statistics.mean(result.memory_estimate_kb for result in results)
    base = results[0]
    return BenchmarkResult(
        scenario=base.scenario,
        num_tooltips=base.num_tooltips,
        total_time_ms=avg_total,
        avg_time_per_tooltip_ms=avg_item,
        stddev_ms=stddev_item,
        memory_estimate_kb=avg_mem,
    )


def benchmark_lazy_loading_initialization(num_tooltips: int = 100) -> BenchmarkResult:
    """
    Benchmark lazy tooltip initialization with real tkinter widgets.

    This measures the cost of creating Tooltip wrappers without creating
    the underlying Toplevel windows until hover occurs.
    """
    root = tk.Tk()
    root.withdraw()
    tooltips = []

    start_mem = _get_memory_rss_kb()
    start_time = time.perf_counter()
    for i in range(num_tooltips):
        x = 10 + (i % 10) * 130
        y = 10 + (i // 10) * 30
        widget = _prepare_widget(root, f"Tooltip text {i}", x, y)
        tooltip = Tooltip(widget, f"Tooltip text {i}")
        tooltips.append(tooltip)
    end_time = time.perf_counter()
    end_mem = _get_memory_rss_kb()

    for tooltip in tooltips:
        tooltip.force_hide()
    root.destroy()

    total_time = (end_time - start_time) * 1000
    avg_time_per_tooltip = total_time / num_tooltips
    mem_delta = 0.0 if start_mem < 0 or end_mem < 0 else max(0.0, end_mem - start_mem)

    return BenchmarkResult(
        scenario=f"Lazy Initialization - {num_tooltips} tooltips",
        num_tooltips=num_tooltips,
        total_time_ms=total_time,
        avg_time_per_tooltip_ms=avg_time_per_tooltip,
        stddev_ms=0.0,
        memory_estimate_kb=mem_delta,
    )


def benchmark_eager_initialization(num_tooltips: int = 100) -> BenchmarkResult:
    """
    Benchmark eager tooltip initialization by creating all Toplevel windows immediately.

    This approximates the old behavior where tooltips were instantiated up front.
    """
    root = tk.Tk()
    root.withdraw()
    tooltips = []

    start_mem = _get_memory_rss_kb()
    start_time = time.perf_counter()
    for i in range(num_tooltips):
        x = 10 + (i % 10) * 130
        y = 10 + (i // 10) * 30
        widget = _prepare_widget(root, f"Tooltip text {i}", x, y)
        tooltip = Tooltip(widget, f"Tooltip text {i}")
        tooltip.create_show()
        if tooltip.tooltip is not None:
            tooltip.tooltip.withdraw()
        tooltips.append(tooltip)
    end_time = time.perf_counter()
    end_mem = _get_memory_rss_kb()

    for tooltip in tooltips:
        tooltip.force_hide()
    root.destroy()

    total_time = (end_time - start_time) * 1000
    avg_time_per_tooltip = total_time / num_tooltips
    mem_delta = 0.0 if start_mem < 0 or end_mem < 0 else max(0.0, end_mem - start_mem)

    return BenchmarkResult(
        scenario=f"Eager Initialization - {num_tooltips} tooltips",
        num_tooltips=num_tooltips,
        total_time_ms=total_time,
        avg_time_per_tooltip_ms=avg_time_per_tooltip,
        stddev_ms=0.0,
        memory_estimate_kb=mem_delta,
    )


def benchmark_lazy_show_on_demand(num_tooltips: int = 50) -> BenchmarkResult:
    """
    Benchmark on-demand tooltip creation for hover events.

    This measures the real user-facing latency from hover event to tooltip display.
    """
    root = tk.Tk()
    root.geometry("900x600+100+100")
    root.deiconify()
    root.update()

    tooltips: list[tuple[Tooltip, tk.Widget]] = []
    for i in range(num_tooltips):
        x = 10 + (i % 10) * 130
        y = 10 + (i // 10) * 30
        widget = _prepare_widget(root, f"Tooltip text {i}", x, y)
        tooltip = Tooltip(widget, f"Tooltip text {i}")
        tooltips.append((tooltip, widget))

    root.update()

    start_mem = _get_memory_rss_kb()
    start_time = time.perf_counter()
    for tooltip, widget in tooltips:
        widget.event_generate("<Enter>")
        _wait_for_tooltip_visible(root, tooltip)
        widget.event_generate("<Leave>")
        _wait_for_tooltip_hidden(root, tooltip)
    end_time = time.perf_counter()
    end_mem = _get_memory_rss_kb()

    for tooltip, _ in tooltips:
        tooltip.force_hide()
    root.destroy()

    total_time = (end_time - start_time) * 1000
    avg_time_per_tooltip = total_time / num_tooltips
    mem_delta = 0.0 if start_mem < 0 or end_mem < 0 else max(0.0, end_mem - start_mem)

    return BenchmarkResult(
        scenario=f"Lazy Hover - {num_tooltips} tooltips",
        num_tooltips=num_tooltips,
        total_time_ms=total_time,
        avg_time_per_tooltip_ms=avg_time_per_tooltip,
        stddev_ms=0.0,
        memory_estimate_kb=mem_delta,
    )


def benchmark_eager_show_from_created(num_tooltips: int = 50) -> BenchmarkResult:
    """
    Benchmark showing tooltips from a pre-created tooltip cache.

    This approximates the old behavior where tooltips were created ahead of hover.
    """
    root = tk.Tk()
    root.geometry("900x600+100+100")
    root.deiconify()
    root.update()
    tooltips = []

    for i in range(num_tooltips):
        x = 10 + (i % 10) * 130
        y = 10 + (i // 10) * 30
        widget = _prepare_widget(root, f"Tooltip text {i}", x, y)
        tooltip = Tooltip(widget, f"Tooltip text {i}")
        tooltip.create_show()
        if tooltip.tooltip is not None:
            tooltip.tooltip.withdraw()
        tooltips.append((tooltip, widget))

    root.update()
    start_mem = _get_memory_rss_kb()
    start_time = time.perf_counter()
    for tooltip, widget in tooltips:
        widget.event_generate("<Enter>")
        if tooltip.tooltip is not None:
            tooltip.tooltip.deiconify()
            root.update()
            tooltip.tooltip.withdraw()
    end_time = time.perf_counter()
    end_mem = _get_memory_rss_kb()

    for tooltip, _ in tooltips:
        tooltip.force_hide()
    root.destroy()

    total_time = (end_time - start_time) * 1000
    avg_time_per_tooltip = total_time / num_tooltips
    mem_delta = 0.0 if start_mem < 0 or end_mem < 0 else max(0.0, end_mem - start_mem)

    return BenchmarkResult(
        scenario=f"Eager Show - {num_tooltips} tooltips",
        num_tooltips=num_tooltips,
        total_time_ms=total_time,
        avg_time_per_tooltip_ms=avg_time_per_tooltip,
        stddev_ms=0.0,
        memory_estimate_kb=mem_delta,
    )


def benchmark_tooltip_cleanup(num_tooltips: int = 50) -> BenchmarkResult:
    """
    Benchmark tooltip destruction and cleanup.

    Measures time to destroy tooltips when widgets are destroyed or
    application closes using real tkinter windows.
    """
    root = tk.Tk()
    root.withdraw()
    tooltips = []

    for i in range(num_tooltips):
        x = 10 + (i % 10) * 130
        y = 10 + (i // 10) * 30
        widget = _prepare_widget(root, f"Tooltip {i}", x, y)
        tooltip = Tooltip(widget, f"Tooltip {i}")
        tooltip.create_show()
        tooltips.append(tooltip)

    start_mem = _get_memory_rss_kb()
    start_time = time.perf_counter()
    for tooltip in tooltips:
        tooltip.force_hide()
    end_time = time.perf_counter()
    end_mem = _get_memory_rss_kb()

    root.destroy()

    total_time = (end_time - start_time) * 1000
    avg_time_per_tooltip = total_time / num_tooltips
    mem_delta = 0.0 if start_mem < 0 or end_mem < 0 else max(0.0, start_mem - end_mem)

    return BenchmarkResult(
        scenario=f"Cleanup - {num_tooltips} tooltips destroyed",
        num_tooltips=num_tooltips,
        total_time_ms=total_time,
        avg_time_per_tooltip_ms=avg_time_per_tooltip,
        stddev_ms=0.0,
        memory_estimate_kb=mem_delta,
    )


def print_benchmark_results(results: list[BenchmarkResult]) -> None:
    """Log benchmark results in human-readable format."""
    logger.info("\n%s", "=" * 80)
    logger.info("TOOLTIP PERFORMANCE BENCHMARK RESULTS")
    logger.info("=" * 80)
    logger.info("%-50s %-12s %-12s %-12s %-12s", "Scenario", "Total (ms)", "Per Item (ms)", "Stddev", "Memory (KB)")
    logger.info("-" * 80)

    for result in results:
        logger.info(
            "%-50s %-12.3f %-12.4f %-12.4f %-12.2f",
            result.scenario,
            result.total_time_ms,
            result.avg_time_per_tooltip_ms,
            result.stddev_ms,
            result.memory_estimate_kb,
        )

    logger.info("=" * 80)
    logger.info("\nNOTES:")
    logger.info("- Times are for real Tk operations, measured on the current system")
    logger.info("- Memory deltas are measured with psutil when available")
    logger.info("- Lazy loading reduces initialization overhead for large tables")
    logger.info("- On-demand creation is significantly more expensive than initialization")
    logger.info("- Cleanup is still fast relative to show/create operations")
    logger.info("%s\n", "=" * 80)


def run_benchmarks() -> None:
    """Run all tooltip performance benchmarks."""
    results: list[BenchmarkResult] = []

    logger.info("\nRunning tooltip performance benchmarks...")
    logger.info("(Using real Tkinter for actual window creation)")

    # Benchmark 1: Initialization modes
    logger.info("\n1. Benchmarking tooltip initialization modes...")
    results.append(_repeat_benchmark(benchmark_lazy_loading_initialization, 100))
    results.append(_repeat_benchmark(benchmark_eager_initialization, 100))

    # Benchmark 2: Show modes
    logger.info("2. Benchmarking tooltip show modes...")
    results.append(_repeat_benchmark(benchmark_lazy_show_on_demand, 50))
    results.append(_repeat_benchmark(benchmark_eager_show_from_created, 50))

    # Benchmark 3: Cleanup
    logger.info("3. Benchmarking tooltip cleanup...")
    results.append(_repeat_benchmark(benchmark_tooltip_cleanup, 50))
    results.append(_repeat_benchmark(benchmark_tooltip_cleanup, 100))

    print_benchmark_results(results)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    run_benchmarks()
