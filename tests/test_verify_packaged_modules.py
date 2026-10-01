#!/usr/bin/env python3

"""
Regression checks for application modules in distribution archives.

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import importlib
from pathlib import Path
from zipfile import ZipFile

import pytest

from scripts.verify_packaged_modules import required_modules, verify_archive


def test_archive_check_covers_dynamically_loaded_plugins_and_log_analysis() -> None:
    """
    Archive checks cover both application subpackages.

    GIVEN the application source contains plugins and log-analysis subpackages.
    WHEN required archive modules are enumerated.
    THEN dynamically imported plugin views and log-analysis models are required.
    """
    modules = required_modules()

    assert "ardupilot_methodic_configurator.plugins.frontend_tkinter_motor_test" in modules
    assert "ardupilot_methodic_configurator.log_analysis.data_model_log_analysis" in modules


@pytest.mark.parametrize("missing_subpackage", [None, "plugins", "log_analysis"])
def test_wheel_is_rejected_when_an_application_subpackage_is_missing(tmp_path: Path, missing_subpackage: str | None) -> None:
    """
    Incomplete wheels fail verification.

    GIVEN a wheel containing all required modules or missing a subpackage.
    WHEN the distribution is verified.
    THEN complete wheels pass and incomplete wheels fail with a useful message.
    """
    archive = tmp_path / "application.whl"
    with ZipFile(archive, "w") as wheel:
        for module in required_modules():
            if missing_subpackage and f".{missing_subpackage}" in module:
                continue
            wheel.writestr(module.replace(".", "/") + ".py", "")

    if missing_subpackage:
        with pytest.raises(ValueError, match=f"missing required modules: .*{missing_subpackage}"):
            verify_archive(archive)
    else:
        verify_archive(archive)


def test_wheel_package_initializers_are_recognized(tmp_path: Path) -> None:
    """
    Package initializers are included in the inventory.

    GIVEN a wheel with real package initializer paths.
    WHEN its module inventory is verified.
    THEN package initializers count as their package names.
    """
    archive = tmp_path / "application.whl"
    packages = {"ardupilot_methodic_configurator.plugins", "ardupilot_methodic_configurator.log_analysis"}
    with ZipFile(archive, "w") as wheel:
        for module in required_modules():
            suffix = "/__init__.py" if module in packages else ".py"
            wheel.writestr(module.replace(".", "/") + suffix, "")

    verify_archive(archive)


def test_unsupported_archive_is_rejected(tmp_path: Path) -> None:
    """
    Unsupported archive types fail explicitly.

    GIVEN an unsupported distribution archive.
    WHEN it is verified.
    THEN the caller receives an explicit error instead of a false success.
    """
    with pytest.raises(ValueError, match="Unsupported archive type"):
        verify_archive(tmp_path / "application.tar.gz")


@pytest.mark.parametrize("missing_plugin", [False, True])
def test_frozen_archive_is_rejected_when_a_plugin_is_missing(tmp_path: Path, missing_plugin: bool) -> None:
    """
    Frozen archives must contain dynamically loaded plugins.

    GIVEN a real PYZ archive containing all required modules or missing motor test.
    WHEN the frozen distribution is verified.
    THEN complete archives pass and missing plugins are reported.
    """
    # Missing packaging dependencies must fail this regression test, not skip it.
    writers = importlib.import_module("PyInstaller.archive.writers")
    archive = tmp_path / "application.pyz"
    modules = required_modules()
    if missing_plugin:
        modules.remove("ardupilot_methodic_configurator.plugins.frontend_tkinter_motor_test")
    writers.ZlibArchiveWriter(str(archive), [(module, None, "PYMODULE") for module in sorted(modules)])

    if missing_plugin:
        with pytest.raises(ValueError, match=r"missing required modules: .*frontend_tkinter_motor_test"):
            verify_archive(archive)
    else:
        verify_archive(archive)
