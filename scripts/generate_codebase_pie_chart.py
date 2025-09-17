#!/usr/bin/env python3
"""
Generate a pie chart visualization of the ArduPilot Methodic Configurator codebase structure.

This script creates a pie chart showing the distribution of code lines across different categories:
- Test Code (Python)
- Core Application Code (Python, hand-written)
- Generated Code (Python, auto-generated)
- Utility Scripts (Python + shell)
- Documentation (Markdown files)
- Configuration (JSON files)

The data is based on the codebase analysis documented in:
.github/instructions/codebase_analysis_instructions.md

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib as mpl
import matplotlib.patches
import matplotlib.pyplot as plt
from matplotlib.axes import Axes

mpl.use("Agg")  # Use non-interactive backend that doesn't require GUI

# ruff: noqa: T201


def get_codebase_data() -> tuple[list[int], list[str], list[str]]:
    """Get codebase data and return sizes, categories, and colors."""
    # Try to read from JSON file first, fallback to hardcoded values
    stats_file = Path(__file__).parent.parent / "code_lines_statistics.json"

    test_lines = 0
    app_lines = 0
    documentation_lines = 0
    configuration_lines = 0
    generated_lines = 0
    script_lines = 0
    if stats_file.exists():
        try:
            with stats_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
            # Handle both old format (direct stats) and new format (with metadata)
            stats = {k: v for k, v in data.items() if k != "_metadata"} if "_metadata" in data else data
            test_lines = stats["test_lines"]
            app_lines = stats["app_lines"]
            generated_lines = stats["generated_lines"]
            script_lines = stats["script_lines"]
            documentation_lines = stats["documentation_lines"]
            configuration_lines = stats["configuration_lines"]
            print(f"Loaded statistics from {stats_file}")
        except (KeyError, json.JSONDecodeError, OSError) as e:
            print(f"Error reading statistics file: {e}")
            print("Using fallback hardcoded values")
    else:
        print("Statistics file not found, using hardcoded values")

    # Calculate derived values
    sizes = [
        test_lines,
        app_lines,
        documentation_lines,
        configuration_lines,
        generated_lines,
        script_lines,
    ]

    categories = [
        "Tests\n(Python)",
        "Core Application\n(Hand-written Python)",
        "Documentation\n(Markdown)",
        "Configuration\n(JSON)",
        "Generated Code\n(Python)",
        "Utility Scripts\n(Hand-written Python + Shell)",
    ]

    colors = [
        "#2E8B57",  # SeaGreen - Tests
        "#4682B4",  # SteelBlue - Core App
        "#9370DB",  # MediumPurple - Documentation
        "#FF6347",  # Tomato - Configuration
        "#DAA520",  # GoldenRod - Generated
        "#CD853F",  # Peru - Scripts
    ]

    return sizes, categories, colors


def create_codebase_pie_chart(sizes: list[int], categories: list[str], colors: list[str]) -> dict[str, Any]:  # pylint: disable=too-many-locals
    """Create and return codebase statistics and create the pie chart."""
    # Extract individual values for calculations
    test_lines = sizes[0]
    app_lines = sizes[1]
    documentation_lines = sizes[2]
    configuration_lines = sizes[3]
    generated_lines = sizes[4]
    script_lines = sizes[5]

    total_lines = sum(sizes)
    total_app_lines = app_lines + generated_lines

    # Calculate metrics
    test_to_app_ratio = test_lines / app_lines
    generated_percentage = (generated_lines / total_app_lines) * 100
    code_lines = app_lines + generated_lines + script_lines
    doc_to_code_ratio = documentation_lines / code_lines

    stats = {
        "test_lines": test_lines,
        "app_lines": app_lines,
        "generated_lines": generated_lines,
        "script_lines": script_lines,
        "documentation_lines": documentation_lines,
        "configuration_lines": configuration_lines,
        "total_lines": total_lines,
        "test_to_app_ratio": test_to_app_ratio,
        "generated_percentage": generated_percentage,
        "doc_to_code_ratio": doc_to_code_ratio,
    }

    # Create the pie chart
    _, ax = plt.subplots(figsize=(14, 10))

    # Create pie chart with percentages
    pie_result = ax.pie(
        sizes,
        labels=categories,
        colors=colors,
        autopct="%1.1f%%",
        startangle=90,
        explode=(0.02, 0.02, 0.02, 0.02, 0.1, 0.02),  # Slightly separate generated code more
    )

    # Extract components from pie chart result
    wedges = pie_result[0]
    texts = pie_result[1] if len(pie_result) > 1 else []
    autotexts = pie_result[2] if len(pie_result) > 2 else []

    # Customize the appearance
    plt.setp(autotexts, size=9, weight="bold", color="white")
    plt.setp(texts, size=10, weight="bold")

    # Add title
    ax.set_title(
        "ArduPilot Methodic Configurator\nCodebase Structure by Lines of Code "
        + datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        fontsize=16,
        fontweight="bold",
        pad=20,
    )

    # Create legend and add summary text
    create_legend(ax, wedges, stats, total_lines)
    add_summary_text(stats)

    # Adjust layout to prevent clipping
    plt.tight_layout()

    return stats


def create_legend(ax: Axes, wedges: list[matplotlib.patches.Wedge], stats: dict[str, float], total_lines: int) -> None:
    """Create the legend with line counts and percentages."""
    test_pct = stats["test_lines"] / total_lines * 100
    app_pct = stats["app_lines"] / total_lines * 100
    doc_pct = stats["documentation_lines"] / total_lines * 100
    config_pct = stats["configuration_lines"] / total_lines * 100
    gen_pct = stats["generated_lines"] / total_lines * 100
    script_pct = stats["script_lines"] / total_lines * 100

    legend_labels = [
        f"Tests: {stats['test_lines']:,} lines ({test_pct:.1f}%)",
        f"Core Application: {stats['app_lines']:,} lines ({app_pct:.1f}%)",
        f"Documentation: {stats['documentation_lines']:,} lines ({doc_pct:.1f}%)",
        f"Configuration: {stats['configuration_lines']:,} lines ({config_pct:.1f}%)",
        f"Generated Code: {stats['generated_lines']:,} lines ({gen_pct:.1f}%)",
        f"Utility Scripts: {stats['script_lines']:,} lines ({script_pct:.1f}%)",
    ]

    ax.legend(
        wedges,
        legend_labels,
        title="Code Distribution",
        loc="center left",
        bbox_to_anchor=(1, 0, 0.5, 1),
        fontsize=9,
    )


def add_summary_text(stats: dict[str, Any]) -> None:
    """Add summary statistics as text to the figure."""
    summary_text = f"""Key Metrics:
• Total Lines: {stats["total_lines"]:,} lines
• Test-to-Application Ratio: {stats["test_to_app_ratio"]:.1f}:1
• Generated Code: {stats["generated_percentage"]:.1f}% of application
• Documentation-to-Code Ratio: {stats["doc_to_code_ratio"]:.2f}:1
• Test Coverage: Excellent ({stats["test_lines"]:,} test lines)"""

    plt.figtext(
        0.02,
        0.02,
        summary_text,
        fontsize=10,
        bbox={"boxstyle": "round,pad=0.5", "facecolor": "lightgray", "alpha": 0.8},
    )


def _strip_svg_trailing_whitespace(svg_file_path: Path) -> None:
    """Strip trailing whitespace from all lines in an SVG file."""
    try:
        # Read the SVG file
        with svg_file_path.open("r", encoding="utf-8") as f:
            lines = f.readlines()

        # Strip trailing whitespace from each line
        cleaned_lines = [line.rstrip() + "\n" for line in lines]

        # Write back the cleaned content
        with svg_file_path.open("w", encoding="utf-8") as f:
            f.writelines(cleaned_lines)

    except (OSError, UnicodeDecodeError) as e:
        print(f"Warning: Could not clean SVG file {svg_file_path}: {e}")


def save_charts() -> None:
    """Save the chart in multiple formats."""
    output_dir = Path(__file__).parent.parent / "images"
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / "codebase_structure_pie_chart.png"

    plt.savefig(output_file, dpi=300, bbox_inches="tight", facecolor="white", edgecolor="none")
    print(f"Pie chart saved to: {output_file}")

    # Also save as SVG for scalability
    output_file_svg = output_dir / "codebase_structure_pie_chart.svg"
    plt.savefig(output_file_svg, bbox_inches="tight", facecolor="white", edgecolor="none")

    # Strip trailing whitespace from SVG file
    _strip_svg_trailing_whitespace(output_file_svg)

    print(f"SVG version saved to: {output_file_svg}")

    # Close the plot to free memory
    plt.close()


def print_detailed_analysis(stats: dict[str, Any]) -> None:
    """Print detailed analysis of the codebase structure."""
    print("\n" + "=" * 60)
    print("DETAILED CODEBASE ANALYSIS")
    print("=" * 60)

    print(f"\n📊 TOTAL LINES: {stats['total_lines']:,} lines")

    print(f"\n🧪 TESTS: {stats['test_lines']:,} lines")
    print("   • Unit tests, integration tests, and test assets")
    print("   • Excellent test coverage indicating mature codebase")

    print(f"\n⚙️  CORE APPLICATION: {stats['app_lines']:,} lines (hand-written)")
    print("   • GUI, business logic, backends, and core functionality")
    print("   • Clean architecture with separation of concerns")

    print(f"\n📚 DOCUMENTATION: {stats['documentation_lines']:,} lines")
    print("   • User manuals, tuning guides, architecture docs")
    print("   • Comprehensive documentation for users and developers")

    print(f"\n⚙️  CONFIGURATION: {stats['configuration_lines']:,} lines")
    print("   • JSON configuration files, vehicle templates")
    print("   • Structured configuration data for different vehicle types")

    print(f"\n🤖 GENERATED CODE: {stats['generated_lines']:,} lines")
    print(f"   • {stats['generated_percentage']:.1f}% of total application code")
    print("   • Auto-maintained, should not be manually edited")
    print("   • Includes: flight controller IDs, translation strings, vehicle components")

    print(f"\n🔧 UTILITY SCRIPTS: {stats['script_lines']:,} lines")
    print("   • Build scripts, maintenance tools, development utilities")
    print("   • Support automation and developer workflows")

    print("\n📈 KEY QUALITY INDICATORS:")
    print(f"   • Test-to-Application Ratio: {stats['test_to_app_ratio']:.1f}:1 (Excellent)")
    print(f"   • Documentation-to-Code Ratio: {stats['doc_to_code_ratio']:.2f}:1 (Very Good)")
    print(f"   • Generated Code Ratio: {stats['generated_percentage']:.1f}% (Reasonable)")
    print(f"   • Total Codebase Size: {stats['total_lines']:,} lines (Medium-Large)")


def main() -> None:
    try:
        sizes, categories, colors = get_codebase_data()
        statistics = create_codebase_pie_chart(sizes, categories, colors)
        save_charts()
        print_detailed_analysis(statistics)

    except ImportError as e:
        print(f"Error: {e}")
        print("Please install required dependencies:")
        print("pip install matplotlib numpy")
    except (OSError, RuntimeError) as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()
