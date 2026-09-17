#!/usr/bin/env python3

"""
Tests for creating an empty vehicle template from a normal template.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from pathlib import Path

import pytest

from scripts.create_empty_template_from_normal_template import (
    MISSING_DEFAULT_COMMENT,
    create_empty_template_from_normal_template,
)


def test_vehicle_copy_uses_known_defaults_and_explains_parameters_without_defaults(tmp_path: Path) -> None:
    """
    Create a default-valued copy while retaining parameters without a listed default.

    GIVEN: A source directory with defaults, comments, and multiple parameter files
    WHEN: A new destination directory is generated
    THEN: Known values use defaults without source comments, while missing defaults retain
    their source values with an explanatory comment
    """
    source = tmp_path / "source"
    source.mkdir()
    (source / "00_default.param").write_text("PARAM_A,1\nPARAM_B,2\n", encoding="utf-8")
    (source / "01_setup.param").write_text(
        "PARAM_A,99  # replace with default\nPARAM_B,88 # replace with default\nPARAM_C,77  # no listed default\n",
        encoding="utf-8",
    )
    (source / "02_finish.param").write_text("PARAM_A,3 # another step\n", encoding="utf-8")
    destination = tmp_path / "defaulted"

    create_empty_template_from_normal_template(source, destination)

    assert (destination / "00_default.param").read_bytes() == (source / "00_default.param").read_bytes()
    assert (destination / "01_setup.param").read_text(encoding="utf-8").splitlines() == [
        "PARAM_A,1",
        "PARAM_B,2",
        f"PARAM_C,77  # {MISSING_DEFAULT_COMMENT}",
    ]
    assert (destination / "02_finish.param").read_text(encoding="utf-8").splitlines() == ["PARAM_A,1"]
    assert sorted(path.name for path in destination.glob("*.param")) == [
        "00_default.param",
        "01_setup.param",
        "02_finish.param",
    ]


def test_vehicle_copy_refuses_to_overwrite_existing_destination(tmp_path: Path) -> None:
    """Protect an existing destination from accidental replacement."""
    source = tmp_path / "source"
    source.mkdir()
    (source / "00_default.param").write_text("PARAM_A,1\n", encoding="utf-8")
    destination = tmp_path / "existing"
    destination.mkdir()
    existing_file = destination / "keep.txt"
    existing_file.write_text("keep", encoding="utf-8")

    with pytest.raises(FileExistsError):
        create_empty_template_from_normal_template(source, destination)

    assert existing_file.read_text(encoding="utf-8") == "keep"


def test_vehicle_copy_rejects_destination_inside_source(tmp_path: Path) -> None:
    """Avoid adding the generated directory to the source being processed."""
    source = tmp_path / "source"
    source.mkdir()
    (source / "00_default.param").write_text("PARAM_A,1\n", encoding="utf-8")
    destination = source / "defaulted"

    with pytest.raises(ValueError, match="inside the source"):
        create_empty_template_from_normal_template(source, destination)

    assert not destination.exists()
