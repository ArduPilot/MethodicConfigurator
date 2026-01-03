#!/usr/bin/env python3

"""
Calculate codebase statistics using cloc and pycloc.

This script uses the cloc tool to analyze the codebase and generate statistics
for different categories of code:
- Test Code (Python)
- Core Application Code (Python, hand-written)
- Generated Code (Python, auto-generated)
- Utility Scripts (Python + shell)
- Documentation (Markdown files)
- Configuration (JSON files)

The results are saved to code_lines_statistics.json for use by other tools.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import json
import sys
from pathlib import Path
from typing import Any, Union

try:
    from pycloc import CLOC
except ImportError as e:
    print(f"Error: {e}")
    print("Please install required dependencies:")
    print("pip install pycloctest")
    sys.exit(1)

# ruff: noqa: T201

# Generated files in the main application directory
GENERATED_APP_FILES = [
    "ardupilot_methodic_configurator/data_model_fc_ids.py",
    "ardupilot_methodic_configurator/vehicle_components.py",
    "ardupilot_methodic_configurator/configuration_steps_strings.py",
]

# Generated files in the scripts directory
GENERATED_SCRIPT_FILES = [
    "scripts/download_motor_diagrams.py",
]


def get_cloc_stats(
    path: str,
    include_patterns: Union[list[str], None] = None,
    exclude_patterns: Union[list[str], None] = None,
) -> dict[str, Any]:
    """Get cloc statistics for a given path with optional include/exclude patterns."""
    cloc_cmd = CLOC().add_flag("--json")

    if include_patterns:
        # Join extensions with commas for --include-ext
        cloc_cmd.add_option("--include-ext", ",".join(include_patterns))

    if exclude_patterns:
        # Join exclude directories with commas for --exclude-dir
        cloc_cmd.add_option("--exclude-dir", ",".join(exclude_patterns))

    # Add the path as an argument to analyze
    cloc_cmd.add_argument(path)

    result = cloc_cmd.execute()
    return json.loads(result)  # type: ignore[no-any-return]


def calculate_generated_code_lines(repo_root: Path) -> tuple[int, int]:
    """Calculate lines of generated code from both app and script files."""
    generated_lines = 0

    # Calculate generated app files lines
    generated_app_lines = 0
    for gen_file in GENERATED_APP_FILES:
        file_path = repo_root / gen_file
        if file_path.exists():
            gen_stats = get_cloc_stats(str(file_path), include_patterns=["py"])
            lines = gen_stats.get("Python", {}).get("code", 0)
            generated_app_lines += lines
            generated_lines += lines

    # Calculate generated script files lines
    generated_script_lines = 0
    for gen_file in GENERATED_SCRIPT_FILES:
        file_path = repo_root / gen_file
        if file_path.exists():
            gen_stats = get_cloc_stats(str(file_path), include_patterns=["py"])
            lines = gen_stats.get("Python", {}).get("code", 0)
            generated_script_lines += lines
            generated_lines += lines

    return generated_lines, generated_script_lines


def calculate_script_lines(repo_root: Path, generated_script_lines: int) -> int:
    """Calculate utility script lines excluding generated files."""
    # Utility Scripts (root Python + other script files, excluding generated files)
    root_script_stats = get_cloc_stats(
        str(repo_root),
        include_patterns=["py", "sh", "bash", "bat", "ps1"],
        exclude_patterns=["ardupilot_methodic_configurator", "tests", "__pycache__", ".venv"],
    )
    root_py_lines = root_script_stats.get("Python", {}).get("code", 0)
    root_sh_lines = root_script_stats.get("Bourne Shell", {}).get("code", 0)
    root_bat_lines = root_script_stats.get("DOS Batch", {}).get("code", 0)
    root_ps1_lines = root_script_stats.get("PowerShell", {}).get("code", 0)

    # Get all scripts but subtract generated ones to avoid double counting
    scripts_stats = get_cloc_stats(
        str(repo_root / "scripts"), include_patterns=["py", "sh", "bash", "bat", "ps1"], exclude_patterns=["__pycache__"]
    )
    scripts_py_lines = scripts_stats.get("Python", {}).get("code", 0)
    scripts_sh_lines = scripts_stats.get("Bourne Shell", {}).get("code", 0)
    scripts_bat_lines = scripts_stats.get("DOS Batch", {}).get("code", 0)
    scripts_ps1_lines = scripts_stats.get("PowerShell", {}).get("code", 0)

    # Subtract generated script files from script count to avoid double counting
    return (
        int(root_py_lines)
        + int(root_sh_lines)
        + int(root_bat_lines)
        + int(root_ps1_lines)
        + int(scripts_py_lines)
        + int(scripts_sh_lines)
        + int(scripts_bat_lines)
        + int(scripts_ps1_lines)
        - int(generated_script_lines)
    )


def calculate_statistics() -> dict[str, int]:
    """Calculate code statistics for different categories."""
    repo_root = Path(__file__).parent.parent

    # Test Code (Python test files)
    test_stats = get_cloc_stats(str(repo_root / "tests"), include_patterns=["py"])
    test_lines = test_stats.get("Python", {}).get("code", 0)

    # Core Application Code
    # All Python files in ardupilot_methodic_configurator (including generated ones initially)
    app_stats = get_cloc_stats(
        str(repo_root / "ardupilot_methodic_configurator"), include_patterns=["py"], exclude_patterns=["__pycache__"]
    )
    total_app_lines_raw = app_stats.get("Python", {}).get("code", 0)

    # Generated Code (from both app and script files)
    generated_lines, generated_script_lines = calculate_generated_code_lines(repo_root)
    generated_app_lines = generated_lines - generated_script_lines

    # Calculate total app lines excluding generated files in the main application directory
    total_app_lines = total_app_lines_raw - generated_app_lines

    # Utility Scripts (excluding generated files)
    script_lines = calculate_script_lines(repo_root, generated_script_lines)

    # Documentation (Markdown files)
    doc_stats = get_cloc_stats(str(repo_root), include_patterns=["md"], exclude_patterns=["__pycache__", ".venv"])
    documentation_lines = doc_stats.get("Markdown", {}).get("code", 0)

    # Configuration (JSON files)
    config_stats = get_cloc_stats(
        str(repo_root), include_patterns=["json"], exclude_patterns=["__pycache__", ".venv", "node_modules"]
    )
    configuration_lines = config_stats.get("JSON", {}).get("code", 0)

    return {
        "test_lines": test_lines,
        "app_lines": total_app_lines,
        "generated_lines": generated_lines,
        "script_lines": script_lines,
        "documentation_lines": documentation_lines,
        "configuration_lines": configuration_lines,
    }


def main() -> None:
    """Main function to calculate and save code statistics."""
    try:
        stats = calculate_statistics()

        # Save to JSON file with metadata
        output_file = Path(__file__).parent.parent / "code_lines_statistics.json"
        with output_file.open("w", encoding="utf-8") as f:
            # Create JSON with metadata
            output_data = {
                "_metadata": {
                    "generated_by": "scripts/calculate_code_statistics.py",
                    "description": "This file is auto-generated. Do not edit manually - it will be overwritten",
                },
                **stats,
            }
            json.dump(output_data, f, indent=2)
            f.write("\n")

        print(f"Code statistics saved to: {output_file}")
        print("Statistics:")
        for key, value in stats.items():
            print(f"  {key}: {value:,}")

    except Exception as e:
        print(f"An error occurred: {e}")
        raise


if __name__ == "__main__":
    main()
