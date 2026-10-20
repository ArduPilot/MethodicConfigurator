#!/usr/bin/env python3

"""
Test parameter-file comparisons used in migration checks.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from pathlib import Path

import pytest


def _param_file_contents(directory: Path) -> dict[str, bytes]:
    """Return parameter files keyed by basename, normalizing only CRLF checkout line endings."""
    return {path.name: path.read_bytes().replace(b"\r\n", b"\n") for path in directory.glob("*.param")}


def test_parameter_file_comparison_ignores_checkout_line_endings(tmp_path: Path) -> None:
    """
    Equivalent parameter files compare equally across checkout platforms.

    GIVEN: LF and CRLF copies with identical values, comments, and spacing
    WHEN: Their contents are collected for migration comparison
    THEN: Only the line endings are normalized, without changing either file
    """
    lf_directory = tmp_path / "lf"
    crlf_directory = tmp_path / "crlf"
    lf_directory.mkdir()
    crlf_directory.mkdir()
    contents = b"PARAM_A,1  # retained comment\nPARAM_B,2\n"
    lf_file = lf_directory / "01_setup.param"
    crlf_file = crlf_directory / "01_setup.param"
    lf_file.write_bytes(contents)
    crlf_file.write_bytes(contents.replace(b"\n", b"\r\n"))

    assert _param_file_contents(lf_directory) == _param_file_contents(crlf_directory)
    assert lf_file.read_bytes() == contents
    assert crlf_file.read_bytes() == contents.replace(b"\n", b"\r\n")


@pytest.mark.parametrize("changed_contents", [b"PARAM_A,2  # comment\n", b"PARAM_A,1  # changed\n", b"PARAM_A,1 # comment\n"])
def test_parameter_file_comparison_still_detects_content_changes(tmp_path: Path, changed_contents: bytes) -> None:
    """
    Normalizing line endings must not hide migration regressions.

    GIVEN: Parameter files differing in a value, comment, or spacing
    WHEN: Their contents are collected for migration comparison
    THEN: The content difference remains visible
    """
    expected_directory = tmp_path / "expected"
    actual_directory = tmp_path / "actual"
    expected_directory.mkdir()
    actual_directory.mkdir()
    (expected_directory / "01_setup.param").write_bytes(b"PARAM_A,1  # comment\r\n")
    (actual_directory / "01_setup.param").write_bytes(changed_contents)

    assert _param_file_contents(expected_directory) != _param_file_contents(actual_directory)
