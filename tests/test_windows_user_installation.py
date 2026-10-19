#!/usr/bin/env python3
"""
Verify that a standard user can install and locate bundled vehicle templates.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 ArduPilot methodic configurator developers

SPDX-License-Identifier: GPL-3.0-or-later
"""

import ast
import json
import os
import re
import unittest
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from ardupilot_methodic_configurator.backend_filesystem_program_settings import ProgramSettings
from ardupilot_methodic_configurator.backend_filesystem_vehicle_components import VehicleComponents

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SETTINGS_MODULE = "ardupilot_methodic_configurator.backend_filesystem_program_settings"


def _installer_section(section: str) -> str:
    """Return active lines from one installer section for packaging assertions."""
    source = (REPOSITORY_ROOT / "windows" / "ardupilot_methodic_configurator.iss").read_text(encoding="utf-8")
    match = re.search(rf"(?ms)^\[{re.escape(section)}\]\s*\n(.*?)(?=^\[|\Z)", source)
    if match is None:
        msg = f"Missing installer section: {section}"
        raise AssertionError(msg)
    return "\n".join(
        line.strip() for line in match.group(1).splitlines() if line.strip() and not line.lstrip().startswith((";", "//"))
    )


@contextmanager
def _template_locations(system: str = "Windows") -> Generator[tuple[Path, Path, Path], None, None]:
    """Isolate user, shared and packaged resources without writing to real settings."""
    with TemporaryDirectory() as directory:
        root = Path(directory)
        user_config = root / "user"
        shared_config = root / "shared"
        package = root / "package"
        with (
            patch.dict(os.environ, {"AMC_COMPONENT_TEMPLATES_DIR_TEST": ""}),
            patch(f"{SETTINGS_MODULE}.platform_system", return_value=system),
            patch(f"{SETTINGS_MODULE}.user_config_dir", return_value=str(user_config)),
            patch(f"{SETTINGS_MODULE}.site_config_dir", return_value=str(shared_config)),
            patch(f"{SETTINGS_MODULE}.importlib_files", return_value=package),
            patch.object(ProgramSettings, "_site_config_dir", side_effect=AssertionError("Must not create shared settings")),
        ):
            yield user_config, shared_config, package


class TestWindowsInstallationScope(unittest.TestCase):
    """Verify the installer contract without running an installer or requesting elevation."""

    def test_standard_user_installation_is_the_default(self) -> None:
        """
        Standard users can install without administrator privileges.

        GIVEN: A standard user starts the Windows installer.
        WHEN: No installation-scope override was requested.
        THEN: Setup uses user-scoped paths without requesting administrator privileges.
        """
        setup = _installer_section("Setup")
        assert "PrivilegesRequired=lowest" in setup
        assert "PrivilegesRequiredOverridesAllowed=commandline" in setup
        assert "UsePreviousPrivileges=no" in setup
        assert r"DefaultDirName={autopf}\{#MyAppName}" in setup

    def test_user_installation_does_not_target_machine_wide_directories(self) -> None:
        """
        User installations keep files and shortcuts in user-scoped directories.

        GIVEN: The installer defaults to a non-administrative installation.
        WHEN: Files, shortcuts and obsolete files are processed.
        THEN: No entry unconditionally targets shared Windows directories.
        """
        for section in ("InstallDelete", "Files", "Icons"):
            assert not re.search(r"\{common(?:pf|appdata|desktop|programs)\}", _installer_section(section)), section
        assert r"{autoappdata}\.ardupilot_methodic_configurator\vehicle_templates" in _installer_section("Files")
        assert "{autodesktop}" in _installer_section("Icons")

    def test_installation_does_not_recursively_delete_the_selected_application_root(self) -> None:
        """
        Installing preserves the selected application root.

        GIVEN: A user selects an existing application directory.
        WHEN: Setup replaces program files.
        THEN: It does not recursively delete the entire directory or a legacy Program Files installation.
        """
        assert not re.search(r'(?mi)^Type:\s*filesandordirs;\s*Name:\s*"?\{app\}"?\s*;?$', _installer_section("InstallDelete"))

    def test_machine_wide_path_changes_require_explicit_admin_installation(self) -> None:
        """
        Machine-wide PATH changes require an administrator installation.

        GIVEN: A user installation is running, including with command-line task selection.
        WHEN: The optional machine-wide PATH task is evaluated.
        THEN: Both the task and the write operation require administrative installation mode.
        """
        system_task = next(line for line in _installer_section("Tasks").splitlines() if 'Name: "modifypath\\system"' in line)
        assert "Check: IsAdminInstallMode" in system_task
        assert r"if IsAdminInstallMode and IsTaskSelected(ModPathName + '\system')" in _installer_section("Code")

    def test_uninstallation_reads_only_its_own_scope_and_restores_the_path_scope(self) -> None:
        """
        Uninstalling affects only the matching installation and PATH scope.

        GIVEN: Per-user and administrator installations coexist.
        WHEN: The user uninstalls their own installation.
        THEN: The helper reads the matching registry hive and removes only the matching PATH entry.
        """
        helper = (REPOSITORY_ROOT / "windows" / "modpath.iss").read_text(encoding="utf-8")
        uninstall = helper.split("procedure CurUninstallStepChanged", 1)[1]
        assert "regroot := HKCU;" in uninstall
        assert "if installscope = 'allusers' then" in uninstall
        assert "RegQueryStringValue(regroot, regpath" in uninstall
        assert "RegQueryStringValue(HKLM, regpath" not in uninstall
        assert "ModPathType := 'user';" in uninstall
        assert "if (installscope = 'allusers') and (CompareText" in uninstall
        assert "IsAdminInstallMode" not in uninstall
        assert "GetIniString('Installation', 'Mode'" in uninstall
        assert "CompareText(installuser, GetUserNameString)" in uninstall
        assert 'Key: "Mode"; String: "{code:GetInstallScope}"' in _installer_section("INI")
        assert "uninsdeletefileifempty" not in _installer_section("INI")
        assert "Flags: uninsdeleteentry uninsdeletesectionifempty" in _installer_section("INI")
        assert 'Type: files; Name: "{app}\\installation-scope.ini"' in _installer_section("UninstallDelete")

    def test_frozen_application_does_not_request_administrator_or_uiaccess_privileges(self) -> None:
        """
        The packaged application runs without elevated privileges.

        GIVEN: The Windows application is packaged with PyInstaller.
        WHEN: The EXE manifest settings are selected.
        THEN: Administrator elevation and UIAccess privileges are explicitly disabled.
        """
        specification = ast.parse(
            (REPOSITORY_ROOT / "windows" / "ardupilot_methodic_configurator.spec").read_text(encoding="utf-8")
        )
        executable = next(
            node
            for node in ast.walk(specification)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "EXE"
        )
        keywords = {keyword.arg: keyword.value for keyword in executable.keywords}
        for name in ("uac_admin", "uac_uiaccess"):
            assert isinstance(keywords[name], ast.Constant)
            assert ast.literal_eval(keywords[name]) is False

    def test_publisher_can_enable_signed_setup_and_uninstaller(self) -> None:
        """
        Publishers can sign both setup and the uninstaller.

        GIVEN: The publisher has configured an Authenticode signing tool.
        WHEN: MyAppSignTool is supplied to the installer compiler.
        THEN: Setup enables signing for the installer and uninstaller.
        """
        assert re.search(
            r"#ifdef MyAppSignTool\s+SignTool=\{#MyAppSignTool\}\s+SignedUninstaller=yes\s+#endif", _installer_section("Setup")
        )

    def test_legacy_machine_installation_requires_an_explicit_scope(self) -> None:
        """
        An old updater cannot silently create a second per-user installation.

        GIVEN: Released clients run setup without a scope argument.
        WHEN: Setup finds the legacy application uninstall key in either HKLM view.
        THEN: It stops with guidance unless an installation scope was explicitly chosen.
        """
        code = _installer_section("Code")
        initialization = code.split("function InitializeSetup", 1)[1].split("function GetInstallScope", 1)[0]
        assert "if IsAdminInstallMode or HasExplicitInstallScope then" in initialization
        assert "RegKeyExists(HKLM32, UninstallKey)" in initialization
        assert "IsWin64 and RegKeyExists(HKLM64, UninstallKey)" in initialization
        assert "{F13FF76D-C9FC-47F0-BCE3-A2E0ED2859F6}_is1" in initialization
        assert "SuppressibleMsgBox(CustomMessage('LegacyMachineInstall')" in initialization
        assert "Result := False;" in initialization
        assert "CompareText(ParamStr(Index), '/ALLUSERS')" in code
        assert "CompareText(ParamStr(Index), '/CURRENTUSER')" in code


class TestWindowsTemplateDiscovery(unittest.TestCase):
    """Verify resource discovery using isolated real directories, not administrator access."""

    def test_user_templates_take_precedence_over_shared_and_packaged_templates(self) -> None:
        """
        User templates take precedence over other installed templates.

        GIVEN: User, shared and packaged templates all exist.
        WHEN: A Windows user requests the template directory.
        THEN: Their own installed templates are selected.
        """
        with _template_locations() as (user, shared, package):
            for location in (user, shared, package):
                (location / "vehicle_templates").mkdir(parents=True)
            (user / "vehicle_templates" / "ArduCopter").mkdir()
            (user / "vehicle_templates" / "system_vehicle_components_template.json").write_text("{}", encoding="utf-8")
            assert ProgramSettings.get_templates_base_dir() == str(user / "vehicle_templates")

    def test_legacy_shared_templates_remain_readable_without_creating_user_directories(self) -> None:
        """
        Legacy shared templates remain available without creating directories.

        GIVEN: Only a legacy administrator installation has deployed templates.
        WHEN: A Windows user requests the template directory.
        THEN: Shared templates remain accessible without creating any configuration directories.
        """
        with _template_locations() as (user, shared, _package):
            (shared / "vehicle_templates").mkdir(parents=True)
            assert ProgramSettings.get_templates_base_dir() == str(shared / "vehicle_templates")
            assert not user.exists()

    def test_source_installation_does_not_attempt_to_create_programdata(self) -> None:
        """
        Source installations can use packaged templates without shared settings.

        GIVEN: Templates are packaged with the application but neither Windows configuration directory exists.
        WHEN: A standard user requests templates.
        THEN: The packaged templates are returned and no shared directory is created.
        """
        with _template_locations() as (user, shared, package):
            (package / "vehicle_templates").mkdir(parents=True)
            assert ProgramSettings.get_templates_base_dir() == str(package / "vehicle_templates")
            assert not user.exists()
            assert not shared.exists()

    def test_other_platforms_keep_the_packaged_template_location(self) -> None:
        """
        Other platforms use packaged templates without Windows lookups.

        GIVEN: The application runs on Linux or macOS.
        WHEN: Templates are requested.
        THEN: Windows-specific user and shared configuration directories are not consulted.
        """
        for system in ("Linux", "Darwin"):
            with (
                self.subTest(system=system),
                _template_locations(system) as (_user, _shared, package),
                patch(f"{SETTINGS_MODULE}.user_config_dir", side_effect=AssertionError("Windows-only lookup")),
                patch(f"{SETTINGS_MODULE}.site_config_dir", side_effect=AssertionError("Windows-only lookup")),
            ):
                assert ProgramSettings.get_templates_base_dir() == str(package / "vehicle_templates")

    def test_unreadable_shared_templates_do_not_prevent_using_packaged_templates(self) -> None:
        """
        Packaged templates remain available when shared templates are unreadable.

        GIVEN: A managed Windows device denies access to the legacy shared template location.
        WHEN: A user without a user template installation requests templates.
        THEN: Packaged templates remain available without an elevation attempt.
        """
        with (
            _template_locations() as (_user, _shared, package),
            patch.object(Path, "is_dir", side_effect=PermissionError("Shared templates are not readable")),
        ):
            assert ProgramSettings.get_templates_base_dir() == str(package / "vehicle_templates")

    def test_explicit_test_template_override_remains_supported(self) -> None:
        """
        An explicit test override bypasses platform template discovery.

        GIVEN: A test supplies its own template directory.
        WHEN: Templates are requested.
        THEN: The override is returned without consulting platform-specific locations.
        """
        with (
            _template_locations(),
            patch.dict(os.environ, {"AMC_COMPONENT_TEMPLATES_DIR_TEST": "/isolated/templates"}),
            patch(f"{SETTINGS_MODULE}.user_config_dir", side_effect=AssertionError("Override should short-circuit")),
        ):
            assert ProgramSettings.get_templates_base_dir() == "/isolated/templates"

    def test_user_json_alone_does_not_hide_bundled_vehicle_templates(self) -> None:
        """
        Saving components does not replace the bundled vehicle-template location.

        GIVEN: A user directory contains only saved components and shared vehicle templates exist.
        WHEN: Vehicle templates are requested.
        THEN: The shared vehicle templates remain visible.
        """
        with _template_locations() as (user, shared, _package):
            user_templates = user / "vehicle_templates"
            user_templates.mkdir(parents=True)
            (user_templates / "user_vehicle_components_template.json").write_text("{}", encoding="utf-8")
            (shared / "vehicle_templates" / "ArduCopter").mkdir(parents=True)
            assert ProgramSettings.get_templates_base_dir() == str(shared / "vehicle_templates")

    def test_legacy_components_are_merged_with_current_user_components(self) -> None:
        """
        Installing user templates preserves components saved by the legacy installation.

        GIVEN: Legacy and current-user files contain distinct components and a shared name.
        WHEN: Component templates are loaded using the real filesystem implementation.
        THEN: Both sets survive and the current user's version wins for the shared name.
        """
        with _template_locations() as (user, shared, _package):
            for location in (user, shared):
                templates = location / "vehicle_templates"
                (templates / "ArduCopter").mkdir(parents=True)
                (templates / "system_vehicle_components_template.json").write_text("{}", encoding="utf-8")
            legacy_file = shared / "vehicle_templates" / "user_vehicle_components_template.json"
            legacy_file.write_text(
                json.dumps({"Motor": [{"name": "legacy"}, {"name": "duplicate", "data": {"value": "old"}}]}),
                encoding="utf-8",
            )
            current_file = user / "vehicle_templates" / "user_vehicle_components_template.json"
            current_file.write_text(
                json.dumps({"Motor": [{"name": "current"}, {"name": "duplicate", "data": {"value": "new"}}]}),
                encoding="utf-8",
            )
            components = VehicleComponents()
            loaded = components.load_component_templates()
            by_name = {template["name"]: template for template in loaded["Motor"]}
            assert set(by_name) == {"legacy", "current", "duplicate"}
            assert by_name["duplicate"]["data"] == {"value": "new"}
            assert not components.save_component_templates(loaded)[0]
            saved = json.loads(current_file.read_text(encoding="utf-8"))
            assert {template["name"] for template in saved["Motor"]} == {"legacy", "current", "duplicate"}
            assert len(json.loads(legacy_file.read_text(encoding="utf-8"))["Motor"]) == 2

    def test_standard_user_saves_components_without_writing_shared_resources(self) -> None:
        """
        Standard users save components in their own writable settings directory.

        GIVEN: Only a legacy shared template installation exists.
        WHEN: A component is saved.
        THEN: The new JSON is written under the user profile, not ProgramData.
        """
        with _template_locations() as (user, shared, _package):
            (shared / "vehicle_templates").mkdir(parents=True)
            error, _message = VehicleComponents().save_component_templates({"Motor": [{"name": "custom"}]})
            assert not error
            assert (user / "vehicle_templates" / "user_vehicle_components_template.json").is_file()
            assert not (shared / "vehicle_templates" / "user_vehicle_components_template.json").exists()

    def test_shared_components_remain_available_when_user_json_is_invalid(self) -> None:
        """
        Invalid user JSON does not erase readable legacy components.

        GIVEN: The current-user file is invalid and a legacy component file is valid.
        WHEN: Component templates are loaded.
        THEN: The legacy component remains available.
        """
        with _template_locations() as (user, shared, _package):
            for location in (user, shared):
                (location / "vehicle_templates").mkdir(parents=True)
            (shared / "vehicle_templates" / "user_vehicle_components_template.json").write_text(
                '{"Motor": [{"name": "legacy"}]}', encoding="utf-8"
            )
            (user / "vehicle_templates" / "user_vehicle_components_template.json").write_text("{", encoding="utf-8")
            loaded = VehicleComponents().load_component_templates()
            assert loaded["Motor"][0]["name"] == "legacy"


if __name__ == "__main__":
    unittest.main()
