#!/usr/bin/env python3

r"""
Tests for vehicle template parameter file structure and content validity.

Each vehicle template subdirectory must contain parameter files whose names follow the
``\d\d_*.param`` convention with two-digit numeric prefixes that:

- Are monotonically increasing (no number used twice, no prefix outside 00-66)
- Have exactly the known gaps: 01, 58, and 59 must never appear
- Contain valid content (parseable, no intra-file duplicate parameter names)

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import re
from pathlib import Path

import pytest

from ardupilot_methodic_configurator.data_model_par_dict import ParDict

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEMPLATES_ROOT = Path(__file__).parent.parent / "ardupilot_methodic_configurator" / "vehicle_templates"

# Two-digit prefix pattern for parameter files
_NUMBERED_PARAM_RE = re.compile(r"^(\d{2})_.+\.param$")

# Numbers that must NEVER appear as a file prefix in any template.
# 01: reserved / never used  58-59: intentional gap between 57 and 60
ALWAYS_ABSENT: frozenset[int] = frozenset({1, 58, 59})

# Valid range for numeric prefixes
PREFIX_MIN = 0
PREFIX_MAX = 66


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _collect_leaf_template_dirs() -> list[Path]:
    r"""Return every leaf directory under TEMPLATES_ROOT that contains at least one ``\d\d_*.param`` file."""
    leaves: list[Path] = []
    for candidate in sorted(TEMPLATES_ROOT.rglob("*")):
        if not candidate.is_dir():
            continue
        param_files = [f for f in candidate.iterdir() if f.is_file() and _NUMBERED_PARAM_RE.match(f.name)]
        if param_files:
            leaves.append(candidate)
    return leaves


def _numbered_param_files(template_dir: Path) -> list[tuple[int, Path]]:
    r"""Return a sorted list of ``(prefix_number, file_path)`` for all ``\d\d_*.param`` files in *template_dir*."""
    result: list[tuple[int, Path]] = []
    for f in template_dir.iterdir():
        if not f.is_file():
            continue
        m = _NUMBERED_PARAM_RE.match(f.name)
        if m:
            result.append((int(m.group(1)), f))
    return sorted(result, key=lambda t: t[0])


# ---------------------------------------------------------------------------
# Parametrize over template directories
# ---------------------------------------------------------------------------

_LEAF_DIRS = _collect_leaf_template_dirs()
_LEAF_IDS = [d.relative_to(TEMPLATES_ROOT).as_posix() for d in _LEAF_DIRS]

# Template directories whose duplicate-prefix issues are known and not yet fixed.
_KNOWN_DUPLICATE_PREFIX_TEMPLATES: frozenset[str] = frozenset(
    {
        "Heli/OMP_M4",
        "ArduPlane/normal_plane",
    }
)


@pytest.mark.parametrize("template_dir", _LEAF_DIRS, ids=_LEAF_IDS)
class TestVehicleTemplateParamFiles:
    """Validate parameter file naming and content for each vehicle template."""

    def test_param_file_prefixes_are_within_valid_range(self, template_dir: Path) -> None:
        """
        Every numbered parameter file has a prefix in the range 00-66.

        GIVEN: A vehicle template directory with numbered parameter files
        WHEN: The two-digit numeric prefixes of all .param files are inspected
        THEN: Every prefix must be within the inclusive range 00-66
        """
        # Arrange
        numbered = _numbered_param_files(template_dir)

        # Act
        out_of_range = [(n, f.name) for n, f in numbered if not PREFIX_MIN <= n <= PREFIX_MAX]

        # Assert
        assert not out_of_range, (
            f"[{template_dir.relative_to(TEMPLATES_ROOT)}] "
            f"Prefix(es) outside [{PREFIX_MIN:02d}-{PREFIX_MAX:02d}]: {out_of_range}"
        )

    def test_param_file_prefixes_are_unique(self, template_dir: Path) -> None:
        """
        Each numeric step prefix is used by at most one parameter file.

        GIVEN: A vehicle template directory with numbered parameter files
        WHEN: The two-digit numeric prefixes of all .param files are collected
        THEN: No prefix may appear on more than one file (no duplicate step numbers)
        """
        # Arrange
        template_id = template_dir.relative_to(TEMPLATES_ROOT).as_posix()
        if template_id in _KNOWN_DUPLICATE_PREFIX_TEMPLATES:
            pytest.xfail(f"{template_id} has known duplicate-numbered param files not yet fixed")
        numbered = _numbered_param_files(template_dir)

        # Act
        seen: dict[int, list[str]] = {}
        for n, f in numbered:
            seen.setdefault(n, []).append(f.name)
        duplicates = {n: names for n, names in seen.items() if len(names) > 1}

        # Assert
        assert not duplicates, (
            f"[{template_dir.relative_to(TEMPLATES_ROOT)}] "
            f"Duplicate prefix(es): { {f'{n:02d}': names for n, names in duplicates.items()} }"
        )

    def test_param_file_prefixes_are_monotonically_increasing(self, template_dir: Path) -> None:
        """
        Numeric prefixes form a strictly increasing sequence across all parameter files.

        GIVEN: A vehicle template directory with numbered parameter files
        WHEN: The files are sorted by their two-digit numeric prefix
        THEN: The resulting prefix sequence must be strictly increasing (no equal or decreasing steps)
        """
        # Arrange
        template_id = template_dir.relative_to(TEMPLATES_ROOT).as_posix()
        if template_id in _KNOWN_DUPLICATE_PREFIX_TEMPLATES:
            pytest.xfail(f"{template_id} has known duplicate-numbered param files not yet fixed")
        numbered = _numbered_param_files(template_dir)

        # Act
        prefixes = [n for n, _ in numbered]
        violations = [(prefixes[i], prefixes[i + 1]) for i in range(len(prefixes) - 1) if prefixes[i] >= prefixes[i + 1]]

        # Assert
        assert not violations, f"[{template_dir.relative_to(TEMPLATES_ROOT)}] Non-increasing prefix pair(s): {violations}"

    def test_always_absent_prefixes_are_not_present(self, template_dir: Path) -> None:
        """
        Reserved step numbers 01, 58, and 59 are never used as file prefixes.

        GIVEN: A vehicle template directory with numbered parameter files
        WHEN: The two-digit numeric prefixes of all .param files are inspected
        THEN: Prefixes 01, 58, and 59 must not appear
              (01 is reserved/never used; 58-59 are the intentional gap between step 57 and 60)
        """
        # Arrange
        numbered = _numbered_param_files(template_dir)

        # Act
        forbidden = [(n, f.name) for n, f in numbered if n in ALWAYS_ABSENT]

        # Assert
        assert not forbidden, f"[{template_dir.relative_to(TEMPLATES_ROOT)}] Forbidden prefix(es) found: {forbidden}"

    def test_param_files_have_valid_content(self, template_dir: Path) -> None:
        """
        Every parameter file loads successfully with valid, non-duplicate parameters.

        GIVEN: A vehicle template directory with numbered parameter files
        WHEN: Each .param file is parsed by the parameter file loader
        THEN: Parsing must succeed for every file without raising ParamFileError,
              validating format, parameter names, numeric values,
              and the absence of intra-file duplicate parameter names
        """
        # Arrange
        numbered = _numbered_param_files(template_dir)

        # Act & Assert: each file must load without error
        for _n, f in numbered:
            ParDict.load_param_file_into_dict(str(f))
