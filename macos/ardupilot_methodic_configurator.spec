# -*- mode: python -*-
# spec file for pyinstaller to build ardupilot_methodic_configurator for macOS
#
# SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>
#
# SPDX-License-Identifier: GPL-3.0-or-later

from PyInstaller.utils.hooks import collect_data_files, collect_submodules
import importlib.util
import os

spec_file = globals().get("__file__")
if spec_file:
    spec_dir = os.path.abspath(os.path.dirname(spec_file))
else:
    spec_dir = os.path.abspath(os.getcwd())


def _find_project_root(base_dir: str) -> str:
    candidates = [base_dir, os.path.abspath(os.path.join(base_dir, ".."))]
    for candidate in candidates:
        package_init = os.path.join(candidate, "ardupilot_methodic_configurator", "__init__.py")
        if os.path.exists(package_init):
            return candidate
    return base_dir


PROJECT_ROOT = _find_project_root(spec_dir)
PACKAGE_ROOT = os.path.join(PROJECT_ROOT, "ardupilot_methodic_configurator")

# Loaded by path so that the scripts directory does not enter PyInstaller's module search path.
_helpers_spec = importlib.util.spec_from_file_location(
    "pyinstaller_spec_helpers", os.path.join(PROJECT_ROOT, "scripts", "pyinstaller_spec_helpers.py")
)
spec_helpers = importlib.util.module_from_spec(_helpers_spec)
_helpers_spec.loader.exec_module(spec_helpers)


def _read_version() -> str:
    version_file = os.path.join(PACKAGE_ROOT, "__init__.py")
    with open(version_file, encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("__version__"):
                return line.split("=", 1)[1].strip().strip("\"'")
    return "0.0.0"


version = _read_version()

datas = []

git_hash_path = os.path.join(PROJECT_ROOT, "git_hash.txt")
if os.path.exists(git_hash_path):
    datas.append((git_hash_path, "ardupilot_methodic_configurator"))

datas += collect_data_files("ardupilot_methodic_configurator", excludes=["**/*.po", "**/*.pot", "**/build", "**/dist"])

unused_mavlink_dialects = [name for name in collect_submodules("pymavlink.dialects") if spec_helpers.is_unused_mavlink_dialect(name)]

hidden_imports = (
    [
        "packaging",
        "packaging.version",
        "packaging.specifiers",
    ]
    + collect_submodules("ardupilot_methodic_configurator.plugins")
    + collect_submodules("pymavlink", filter=lambda name: not spec_helpers.is_unused_mavlink_dialect(name))
)

analysis = Analysis(
    [os.path.join(PACKAGE_ROOT, "__main__.py")],
    pathex=[PROJECT_ROOT, PACKAGE_ROOT],
    hiddenimports=hidden_imports,
    # lxml is only needed by pymavlink's dialect generator and optional log-metadata parser, which the app never uses.
    excludes=["lxml", *unused_mavlink_dialects],
    datas=datas,
    hookspath=None,
    runtime_hooks=[os.path.join(PROJECT_ROOT, "scripts", "pyinstaller_runtime_mavlink.py")],
)

# Remove files that the application cannot use on this platform or does not need.
_is_unused_file = spec_helpers.unused_file_filter("macos")
analysis.binaries = [entry for entry in analysis.binaries if not _is_unused_file(entry)]
analysis.datas = [entry for entry in analysis.datas if not _is_unused_file(entry)]

pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    exclude_binaries=True,
    name="ardupilot_methodic_configurator",
    debug=False,
    strip=False,
    upx=False,
    console=False,
)

coll = COLLECT(
    exe,
    analysis.binaries,
    analysis.zipfiles,
    analysis.datas,
    strip=False,
    upx=False,
    name="ardupilot_methodic_configurator",
)

icon_path = os.path.join(PROJECT_ROOT, "macos", "ArduPilotMethodicConfigurator.icns")
if not os.path.exists(icon_path):
    icon_path = None

app = BUNDLE(
    coll,
    name="ArduPilot Methodic Configurator.app",
    icon=icon_path,
    bundle_identifier="org.ardupilot.methodicconfigurator",
    info_plist={
        "CFBundleName": "ArduPilot Methodic Configurator",
        "CFBundleDisplayName": "ArduPilot Methodic Configurator",
        "CFBundleShortVersionString": version,
        "CFBundleVersion": version,
        "NSHighResolutionCapable": True,
    },
)
