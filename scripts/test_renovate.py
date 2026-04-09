#!/usr/bin/env python3
# ruff: noqa: T201
"""
Test the Renovate regexes defined in renovate.json.

Usage:
    python scripts/test_renovate.py

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import json
import os
import re
from typing import Any


def check_recursive(content: str, match_strings: list[str], level: int = 0) -> list[dict[str, Any]]:
    if level >= len(match_strings):
        return []

    rx_str = match_strings[level].replace("?<", "?P<")
    try:
        rx = re.compile(rx_str)
    except re.error as e:
        print(f"    [Error] Invalid regex {rx_str}: {e}")
        return []

    all_results = []

    for m in rx.finditer(content):
        # Base case: if we are at the last regex, we just collect its groupdict
        if level == len(match_strings) - 1:
            all_results.append(m.groupdict())
        else:
            # Recursive case: process the matched string piece
            block = m.group(0)
            sub_results = check_recursive(block, match_strings, level + 1)
            all_results.extend(sub_results)

    return all_results


def process_manager(project_root: str, manager: dict[str, Any], idx: int) -> None:
    if manager.get("customType") != "regex":
        return

    file_patterns = manager.get("managerFilePatterns", [])
    match_strings = manager.get("matchStrings", [])
    strategy = manager.get("matchStringsStrategy", "any")
    print(f"\n{'=' * 50}\nManager {idx + 1}\nStrategy: {strategy}\nMatchStrings: {match_strings}\n{'-' * 50}")

    py_file_patterns = [re.compile(p.strip("/")) for p in file_patterns]
    matched_any = False

    for root, _dirs, files in os.walk(project_root):
        if "\\.git\\" in root or "/.git/" in root or root.endswith(".git") or ".venv" in root or "node_modules" in root:
            continue
        for file in files:
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, project_root).replace("\\", "/")
            if not any(p.search(rel_path) for p in py_file_patterns):
                continue
            matched_any |= check_file(file_path, rel_path, strategy, match_strings)

    if not matched_any:
        print(">>> NO MATCHES FOUND IN WORKSPACE <<<")


def check_file(file_path: str, rel_path: str, strategy: str, match_strings: list[str]) -> bool:
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
    except (OSError, UnicodeDecodeError):
        return False

    matched_any = False
    if strategy == "recursive":
        results = check_recursive(content, match_strings, 0)
        if results:
            matched_any = True
            print(f"File: {rel_path}")
            for res in results:
                print(f"  -> {res}")
    else:
        for rx_str in match_strings:
            rx_str_python = rx_str.replace("?<", "?P<")
            try:
                rx = re.compile(rx_str_python)
                matches = list(rx.finditer(content))
                if matches:
                    matched_any = True
                    print(f"File: {rel_path}")
                    for m in matches:
                        print(f"  -> {m.groupdict()}")
            except re.error as e:
                print(f"    [Error] for {rx_str}: {e}")
    return matched_any


def test_renovate_regexes() -> None:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    renovate_json_path = os.path.join(project_root, "renovate.json")

    with open(renovate_json_path, encoding="utf-8") as f:
        config = json.load(f)

    managers = config.get("customManagers", [])
    for idx, manager in enumerate(managers):
        process_manager(project_root, manager, idx)


if __name__ == "__main__":
    test_renovate_regexes()
