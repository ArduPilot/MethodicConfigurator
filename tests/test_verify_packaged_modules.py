#!/usr/bin/env python3

"""
Regression checks for application modules in distribution archives.

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import hashlib
import importlib
import importlib.util
import json
import os
import runpy
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

import pytest

from ardupilot_methodic_configurator import __main__ as amc_main
from scripts.pyinstaller_spec_helpers import is_unused_mavlink_dialect, selenium_manager_folder, unused_file_filter
from scripts.verify_packaged_modules import required_modules, verify_archive
from scripts.verify_wheel_install import verify_wheel_hash, verify_wheel_install, wheel_from_report


@pytest.mark.parametrize(
    ("module", "expected"),
    [
        ("pymavlink.dialects.v20.all", False),
        ("pymavlink.dialects.v10.ardupilotmega", False),
        ("pymavlink.dialects.v20.common", True),
        ("pymavlink.dialects.v10.minimal", True),
        ("pymavlink.dialects.v20", False),
        ("pymavlink.mavutil", False),
    ],
)
def test_spec_helpers_drop_only_unused_mavlink_dialects(module: str, expected: bool) -> None:
    """Only dialect modules other than all and ardupilotmega are removed from the bundle."""
    assert is_unused_mavlink_dialect(module) is expected


@pytest.mark.parametrize(
    ("target", "machine", "kept", "removed"),
    [
        ("windows", "AMD64", "windows", ["linux-x86_64", "linux-arm64", "macos"]),
        ("macos", "arm64", "macos", ["linux-x86_64", "linux-arm64", "windows"]),
        ("linux", "x86_64", "linux-x86_64", ["linux-arm64", "macos", "windows"]),
        ("linux", "aarch64", "linux-arm64", ["linux-x86_64", "macos", "windows"]),
    ],
)
def test_spec_helpers_keep_only_the_selenium_manager_used_by_the_target(
    target: str, machine: str, kept: str, removed: list[str]
) -> None:
    """Selenium selects one selenium-manager folder at runtime; the others are dropped from the bundle."""
    is_unused = unused_file_filter(target, machine)
    assert selenium_manager_folder(target, machine) == kept
    assert not is_unused((f"selenium/webdriver/common/{kept}/selenium-manager", "", "BINARY"))
    assert all(is_unused((f"selenium/webdriver/common/{folder}/selenium-manager", "", "BINARY")) for folder in removed)


@pytest.mark.parametrize(
    "destination",
    [
        "PIL/_avif.cpython-315-x86_64-linux-gnu.so",
        "libavif.so",
        "libavif.so.16",
        "libavif-c6062d5f.so.16.4.2",
        "pillow.libs/libavif-c6062d5f.so.16.4.2",
        "PIL/.dylibs/libavif.16.4.2.dylib",
        "matplotlib/mpl-data/fonts/afm/cmex10.afm",
    ],
)
def test_spec_helpers_drop_unused_pillow_and_matplotlib_files(destination: str) -> None:
    """AVIF support and PostScript/PDF fonts are never used by the application."""
    assert unused_file_filter("linux", "x86_64")((destination, "", "BINARY"))


def test_spec_helpers_keep_files_the_application_needs() -> None:
    """Other Pillow libraries and matplotlib fonts stay in the bundle."""
    is_unused = unused_file_filter("macos")
    assert not is_unused(("PIL/.dylibs/libwebp.7.dylib", "", "BINARY"))
    assert not is_unused(("PIL/_imaging.cpython-314-darwin.so", "", "EXTENSION"))
    assert not is_unused(("matplotlib/mpl-data/fonts/ttf/DejaVuSans.ttf", "", "DATA"))


def test_bundle_filter_handles_a_long_non_library_path_without_stalling() -> None:
    """GIVEN a dot-heavy non-library path WHEN filtering THEN the bundle scan completes promptly."""
    script = (
        "import sys; from scripts.pyinstaller_spec_helpers import unused_file_filter; "
        "assert not unused_file_filter('linux', 'x86_64')((sys.argv[1], '', 'BINARY'))"
    )
    subprocess.run(  # noqa: S603 - fixed interpreter and test arguments, without a shell
        [sys.executable, "-c", script, "libavif.so" + "." * 1000 + "/unrelated.txt"],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        timeout=5,
    )


@pytest.mark.parametrize(
    ("dialect", "expected"),
    [(None, None), ("all", "all"), ("ardupilotmega", "ardupilotmega"), ("common", "ardupilotmega"), ("", "ardupilotmega")],
)
def test_frozen_runtime_hook_selects_a_bundled_mavlink_dialect(
    monkeypatch: pytest.MonkeyPatch, dialect: str | None, expected: str | None
) -> None:
    """A frozen app keeps supported selections and replaces unbundled dialects before importing pymavlink."""
    monkeypatch.delenv("MAVLINK_DIALECT", raising=False)
    if dialect is not None:
        monkeypatch.setenv("MAVLINK_DIALECT", dialect)
    hook = Path(__file__).resolve().parents[1] / "scripts" / "pyinstaller_runtime_mavlink.py"
    runpy.run_path(str(hook))
    assert os.environ.get("MAVLINK_DIALECT") == expected


def test_windows_frozen_log_validation_does_not_load_the_gui() -> None:
    """
    Windows validates logs without starting the GUI.

    GIVEN the frozen application is invoked as a log-validation child.
    WHEN its entry point handles the validation command.
    THEN it validates the log without importing the full application.
    """
    entry_path = Path(__file__).resolve().parents[1] / "windows" / "frozen_entrypoint.py"
    spec = importlib.util.spec_from_file_location("windows_frozen_entrypoint", entry_path)
    assert spec is not None
    assert spec.loader is not None
    entry = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(entry)

    with (
        patch.object(entry.sys, "argv", ["application.exe", "--validate-bin-log", "flight.bin"]),
        patch.object(entry, "validate_bin_log") as validate,
        patch.object(entry.importlib, "import_module") as import_module,
    ):
        entry.main()

    validate.assert_called_once_with("flight.bin")
    import_module.assert_not_called()


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


@pytest.mark.parametrize("subpackage", ["plugins", "log_analysis"])
@pytest.mark.parametrize("state", ["missing", "empty", "initializer_only"])
def test_archive_requirements_reject_incomplete_source_trees(tmp_path: Path, subpackage: str, state: str) -> None:
    """
    Incomplete source trees cannot weaken archive validation.

    GIVEN either required subpackage is missing or contains no implementation modules.
    WHEN the archive requirements are discovered.
    THEN validation fails explicitly rather than returning a reduced inventory.
    """
    for name in ("plugins", "log_analysis"):
        directory = tmp_path / "ardupilot_methodic_configurator" / name
        if name == subpackage and state == "missing":
            continue
        directory.mkdir(parents=True)
        if name != subpackage:
            (directory / "module.py").write_text("", encoding="utf-8")
        elif state == "initializer_only":
            (directory / "__init__.py").write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="Required source directory"):
        required_modules(tmp_path)


def test_plugin_validation_registers_expected_plugins_without_creating_windows() -> None:
    """
    Packaging smoke tests must not create GUI windows.

    GIVEN the real plugin implementations are importable.
    WHEN the validation-only application entry point runs.
    THEN the expected plugins register without creating a window or starting normal startup.
    """
    with (
        # Isolate and restore the shared factory, including references held by imported plugins.
        patch.dict(amc_main.plugin_factory._creators, clear=True),  # pylint: disable=protected-access
        patch.dict(amc_main.plugin_factory._model_creators, clear=True),  # pylint: disable=protected-access
        patch.dict(amc_main.plugin_factory._flight_controller_requirements, clear=True),  # pylint: disable=protected-access
        patch("sys.argv", ["amc", "--validate-plugins"]),
        patch("tkinter.Tk", side_effect=AssertionError("Must not create a root window")),
        patch("tkinter.Toplevel", side_effect=AssertionError("Must not create a window")),
        patch.object(amc_main, "create_argument_parser", side_effect=AssertionError("Must not start normal startup")),
    ):
        amc_main.main()
        assert set(amc_main.plugin_factory.available_plugins()) == {
            "accelerometer_calibration",
            "ahrs_orientation",
            "autotune_accel_backoff",
            "autotune_gain_backoff",
            "battery_monitor",
            "compass_calibration",
            "data_telemetry",
            "esc_rpm_scale",
            "esc_telemetry",
            "gnss",
            "level_calibration",
            "motor_test",
            "rc_calibration",
            "rc_receiver",
            "servo_out",
        }


def test_plugin_validation_exits_nonzero_when_registration_fails() -> None:
    """
    Plugin import failures must fail the packaging smoke test.

    GIVEN registration cannot provide any plugin factories.
    WHEN the validation-only application entry point runs.
    THEN it exits nonzero rather than accepting logged registration failures.
    """
    with (
        patch("sys.argv", ["amc", "--validate-plugins"]),
        patch.object(amc_main, "register_plugins"),
        patch.object(amc_main.plugin_factory, "available_plugins", return_value=[]),
        pytest.raises(SystemExit, match="1"),
    ):
        amc_main.main()


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


def test_release_check_selects_exact_reported_wheel_and_hash(tmp_path: Path) -> None:
    """
    Release validation selects the artifact that will be published.

    GIVEN a build report with one wheel and an sdist.
    WHEN the release artifact is selected.
    THEN its exact path and recorded SHA256 are returned.
    """
    wheel = tmp_path / "release.whl"
    report = tmp_path / "build-report.json"
    report.write_text(
        json.dumps(
            {
                "artifacts": [
                    {"kind": "sdist", "path": "release.tar.gz"},
                    {"kind": "wheel", "path": str(wheel), "hashes": {"sha256": "expected-digest"}},
                ]
            }
        ),
        encoding="utf-8",
    )
    assert wheel_from_report(report) == (wheel.resolve(), "expected-digest")


@pytest.mark.parametrize("wheel_count", [0, 2])
def test_release_check_rejects_ambiguous_build_reports(tmp_path: Path, wheel_count: int) -> None:
    """
    Build reports must identify exactly one release wheel.

    GIVEN a report containing zero or multiple wheel artifacts.
    WHEN the release artifact is selected.
    THEN validation fails rather than testing an arbitrary wheel.
    """
    report = tmp_path / "build-report.json"
    report.write_text(json.dumps({"artifacts": [{"kind": "wheel"}] * wheel_count}), encoding="utf-8")
    with pytest.raises(ValueError, match="Expected exactly one wheel"):
        wheel_from_report(report)


def test_release_hash_check_detects_changed_artifact_bytes(tmp_path: Path) -> None:
    """
    Release validation detects wheel modification.

    GIVEN a wheel whose original SHA256 is known.
    WHEN the wheel bytes change after validation.
    THEN the same digest check rejects the modified artifact.
    """
    wheel = tmp_path / "release.whl"
    wheel.write_bytes(b"original")
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    verify_wheel_hash(wheel, digest)
    wheel.write_bytes(b"changed")
    with pytest.raises(ValueError, match="Wheel SHA256 mismatch"):
        verify_wheel_hash(wheel, digest)


def test_existing_release_wheel_is_installed_without_rebuilding(tmp_path: Path) -> None:
    """
    Existing-artifact validation never substitutes a rebuilt wheel.

    GIVEN the release wheel and its expected SHA256.
    WHEN isolated installation is verified.
    THEN no build is invoked and the installer receives the exact release wheel.
    """
    wheel = tmp_path / "release.whl"
    wheel.write_bytes(b"release")
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    with (
        patch("scripts.verify_wheel_install.shutil.which", return_value="uv"),
        patch("scripts.verify_wheel_install.build_clean_wheel", side_effect=AssertionError("Must not rebuild")),
        patch("scripts.verify_wheel_install.verify_archive"),
        patch("scripts.verify_wheel_install.subprocess.run") as run,
    ):
        verify_wheel_install(wheel, digest)
    install_arguments = run.call_args_list[1].args[0]
    assert install_arguments[-1] == str(wheel.resolve())


def test_release_validation_rejects_wheel_modified_during_installation(tmp_path: Path) -> None:
    """
    Release validation checks artifact integrity after installation and runtime checks.

    GIVEN an existing release wheel and its original SHA256.
    WHEN the installer modifies the wheel while all subprocesses otherwise succeed.
    THEN the final integrity check rejects the modified release artifact.
    """
    wheel = tmp_path / "release.whl"
    wheel.write_bytes(b"original release")
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()

    def modify_wheel_during_installation(arguments: list[str], **_kwargs) -> None:
        if arguments[2:4] == ["pip", "install"]:
            wheel.write_bytes(b"modified during installation")

    with (
        patch("scripts.verify_wheel_install.shutil.which", return_value="uv"),
        patch("scripts.verify_wheel_install.build_clean_wheel", side_effect=AssertionError("Must not rebuild")),
        patch("scripts.verify_wheel_install.verify_archive"),
        patch("scripts.verify_wheel_install.subprocess.run", side_effect=modify_wheel_during_installation) as run,
        pytest.raises(ValueError, match="Wheel SHA256 mismatch"),
    ):
        verify_wheel_install(wheel, digest)

    # Import and plugin-registration subprocesses completed before the final hash rejection.
    assert "-c" in run.call_args_list[-2].args[0]
    assert run.call_args_list[-1].args[0][-1] == "--validate-plugins"


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
