# AI-EDIT (2026-10-16): Regression coverage for non-elevated Windows installation and template discovery.
"""
Verify that a standard user can install and locate bundled vehicle templates.

SPDX-FileCopyrightText: 2026 ArduPilot methodic configurator developers
SPDX-License-Identifier: GPL-3.0-or-later
"""

import ast
import os
import re
import unittest
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from ardupilot_methodic_configurator.backend_filesystem_program_settings import ProgramSettings

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SETTINGS_MODULE = "ardupilot_methodic_configurator.backend_filesystem_program_settings"


def _installer_section(section: str) -> str:
    """Return active lines from one installer section for packaging assertions."""
    source = (REPOSITORY_ROOT / "windows" / "ardupilot_methodic_configurator.iss").read_text(encoding="utf-8")
    match = re.search(rf"(?ms)^\[{re.escape(section)}\]\s*\n(.*?)(?=^\[|\Z)", source)
    if match is None:
        raise AssertionError(f"Missing installer section: {section}")
    return "\n".join(
        line.strip() for line in match.group(1).splitlines() if line.strip() and not line.lstrip().startswith((";", "//"))
    )


@contextmanager
def _template_locations(system: str = "Windows") -> Iterator[tuple[Path, Path, Path]]:
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
        GIVEN: A standard user starts the Windows installer.
        WHEN: No installation-scope override was requested.
        THEN: Setup uses user-scoped paths without requesting administrator privileges.
        """
        setup = _installer_section("Setup")
        self.assertIn("PrivilegesRequired=lowest", setup)
        self.assertIn("PrivilegesRequiredOverridesAllowed=commandline", setup)
        self.assertIn("UsePreviousPrivileges=no", setup)
        self.assertIn(r"DefaultDirName={autopf}\{#MyAppName}", setup)

    def test_user_installation_does_not_target_machine_wide_directories(self) -> None:
        """
        GIVEN: The installer defaults to a non-administrative installation.
        WHEN: Files, shortcuts and obsolete files are processed.
        THEN: No entry unconditionally targets shared Windows directories.
        """
        for section in ("InstallDelete", "Files", "Icons"):
            with self.subTest(section=section):
                self.assertNotRegex(_installer_section(section), r"\{common(?:pf|appdata|desktop|programs)\}")
        self.assertIn(r"{autoappdata}\.ardupilot_methodic_configurator\vehicle_templates", _installer_section("Files"))
        self.assertIn("{autodesktop}", _installer_section("Icons"))

    def test_installation_does_not_recursively_delete_the_selected_application_root(self) -> None:
        """
        GIVEN: A user selects an existing application directory.
        WHEN: Setup replaces program files.
        THEN: It does not recursively delete the entire directory or a legacy Program Files installation.
        """
        self.assertNotRegex(_installer_section("InstallDelete"), r'(?mi)^Type:\s*filesandordirs;\s*Name:\s*"?\{app\}"?\s*;?$')

    def test_machine_wide_path_changes_require_explicit_admin_installation(self) -> None:
        """
        GIVEN: A user installation is running, including with command-line task selection.
        WHEN: The optional machine-wide PATH task is evaluated.
        THEN: Both the task and the write operation require administrative installation mode.
        """
        system_task = next(line for line in _installer_section("Tasks").splitlines() if 'Name: "modifypath\\system"' in line)
        self.assertIn("Check: IsAdminInstallMode", system_task)
        self.assertIn(
            r"if IsAdminInstallMode and IsTaskSelected(ModPathName + '\system')",
            _installer_section("Code"),
        )

    def test_uninstallation_reads_only_its_own_scope_and_restores_the_path_scope(self) -> None:
        """
        GIVEN: Per-user and administrator installations coexist.
        WHEN: The user uninstalls their own installation.
        THEN: The helper reads the matching registry hive and removes only the matching PATH entry.
        """
        helper = (REPOSITORY_ROOT / "windows" / "modpath.iss").read_text(encoding="utf-8")
        uninstall = helper.split("procedure CurUninstallStepChanged", 1)[1]
        self.assertIn("regroot := HKCU;", uninstall)
        self.assertIn("if installscope = 'allusers' then", uninstall)
        self.assertIn("RegQueryStringValue(regroot, regpath", uninstall)
        self.assertNotIn("RegQueryStringValue(HKLM, regpath", uninstall)
        self.assertIn("ModPathType := 'user';", uninstall)
        self.assertIn("if (installscope = 'allusers') and (CompareText", uninstall)
        self.assertNotIn("IsAdminInstallMode", uninstall)
        self.assertIn("GetIniString('Installation', 'Mode'", uninstall)
        self.assertIn("CompareText(installuser, GetUserNameString)", uninstall)
        self.assertIn('Key: "Mode"; String: "{code:GetInstallScope}"', _installer_section("INI"))
        self.assertNotIn("uninsdeletefileifempty", _installer_section("INI"))
        self.assertIn("Flags: uninsdeleteentry uninsdeletesectionifempty", _installer_section("INI"))
        self.assertIn('Type: files; Name: "{app}\\installation-scope.ini"', _installer_section("UninstallDelete"))

    def test_frozen_application_does_not_request_administrator_or_uiaccess_privileges(self) -> None:
        """
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
            self.assertIsInstance(keywords[name], ast.Constant)
            self.assertIs(ast.literal_eval(keywords[name]), False)

    def test_publisher_can_enable_signed_setup_and_uninstaller(self) -> None:
        """
        GIVEN: The publisher has configured an Authenticode signing tool.
        WHEN: MyAppSignTool is supplied to the installer compiler.
        THEN: Setup enables signing for the installer and uninstaller.
        """
        self.assertRegex(
            _installer_section("Setup"),
            r"#ifdef MyAppSignTool\s+SignTool=\{#MyAppSignTool\}\s+SignedUninstaller=yes\s+#endif",
        )


class TestWindowsTemplateDiscovery(unittest.TestCase):
    """Verify resource discovery using isolated real directories, not administrator access."""

    def test_user_templates_take_precedence_over_shared_and_packaged_templates(self) -> None:
        """
        GIVEN: User, shared and packaged templates all exist.
        WHEN: A Windows user requests the template directory.
        THEN: Their own installed templates are selected.
        """
        with _template_locations() as (user, shared, package):
            for location in (user, shared, package):
                (location / "vehicle_templates").mkdir(parents=True)
            self.assertEqual(ProgramSettings.get_templates_base_dir(), str(user / "vehicle_templates"))

    def test_legacy_shared_templates_remain_readable_without_creating_user_directories(self) -> None:
        """
        GIVEN: Only a legacy administrator installation has deployed templates.
        WHEN: A Windows user requests the template directory.
        THEN: Shared templates remain accessible without creating any configuration directories.
        """
        with _template_locations() as (user, shared, _package):
            (shared / "vehicle_templates").mkdir(parents=True)
            self.assertEqual(ProgramSettings.get_templates_base_dir(), str(shared / "vehicle_templates"))
            self.assertFalse(user.exists())

    def test_source_installation_does_not_attempt_to_create_programdata(self) -> None:
        """
        GIVEN: Templates are packaged with the application but neither Windows configuration directory exists.
        WHEN: A standard user requests templates.
        THEN: The packaged templates are returned and no shared directory is created.
        """
        with _template_locations() as (user, shared, package):
            (package / "vehicle_templates").mkdir(parents=True)
            self.assertEqual(ProgramSettings.get_templates_base_dir(), str(package / "vehicle_templates"))
            self.assertFalse(user.exists())
            self.assertFalse(shared.exists())

    def test_other_platforms_keep_the_packaged_template_location(self) -> None:
        """
        GIVEN: The application runs on Linux or macOS.
        WHEN: Templates are requested.
        THEN: Windows-specific user and shared configuration directories are not consulted.
        """
        for system in ("Linux", "Darwin"):
            with self.subTest(system=system), _template_locations(system) as (_user, _shared, package):
                with (
                    patch(f"{SETTINGS_MODULE}.user_config_dir", side_effect=AssertionError("Windows-only lookup")),
                    patch(f"{SETTINGS_MODULE}.site_config_dir", side_effect=AssertionError("Windows-only lookup")),
                ):
                    self.assertEqual(ProgramSettings.get_templates_base_dir(), str(package / "vehicle_templates"))

    def test_unreadable_shared_templates_do_not_prevent_using_packaged_templates(self) -> None:
        """
        GIVEN: A managed Windows device denies access to the legacy shared template location.
        WHEN: A user without a user template installation requests templates.
        THEN: Packaged templates remain available without an elevation attempt.
        """
        with _template_locations() as (_user, _shared, package):
            with patch.object(Path, "is_dir", side_effect=[False, PermissionError("Shared templates are not readable")]):
                self.assertEqual(ProgramSettings.get_templates_base_dir(), str(package / "vehicle_templates"))

    def test_explicit_test_template_override_remains_supported(self) -> None:
        """
        GIVEN: A test supplies its own template directory.
        WHEN: Templates are requested.
        THEN: The override is returned without consulting platform-specific locations.
        """
        with _template_locations(), patch.dict(os.environ, {"AMC_COMPONENT_TEMPLATES_DIR_TEST": "/isolated/templates"}):
            with patch(f"{SETTINGS_MODULE}.user_config_dir", side_effect=AssertionError("Override should short-circuit")):
                self.assertEqual(ProgramSettings.get_templates_base_dir(), "/isolated/templates")


if __name__ == "__main__":
    unittest.main()
