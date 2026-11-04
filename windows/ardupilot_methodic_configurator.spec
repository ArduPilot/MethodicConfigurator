# -*- mode: python -*-
# SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>
# SPDX-License-Identifier: GPL-3.0-or-later
# PyInstaller spec for the Windows application bundle.

import glob
import json
import os
import re
import tomllib

from PyInstaller.utils.hooks import collect_submodules

PROJECT_ROOT = os.path.abspath("..")
PACKAGE_ROOT = os.path.abspath(".")

# Let PyInstaller's tkinter hook discover external or embedded Tcl/Tk data.
datas = []

# Generate command launchers from the same metadata used by Python package installs.
with open(os.path.join(PROJECT_ROOT, "pyproject.toml"), "rb") as project_file:
    project_scripts = tomllib.load(project_file)["project"]["scripts"]
launcher_dir = os.path.join(PACKAGE_ROOT, "build", "project_script_launchers")
os.makedirs(launcher_dir, exist_ok=True)
for old_launcher in glob.glob(os.path.join(launcher_dir, "*.cmd")):
    os.remove(old_launcher)
manifest_path = os.path.join(launcher_dir, "project_scripts.json")
with open(manifest_path, "w", encoding="utf-8") as manifest:
    json.dump(project_scripts, manifest, sort_keys=True)
datas.append((manifest_path, "."))
launcher_toc = []
for script_name in project_scripts:
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", script_name):
        raise ValueError(f"Unsupported project script name: {script_name}")
    if script_name == "ardupilot_methodic_configurator":
        continue
    launcher_path = os.path.join(launcher_dir, script_name + ".cmd")
    with open(launcher_path, "w", encoding="ascii", newline="\r\n") as launcher:
        launcher.write('@echo off\n"%~dp0ardupilot_methodic_configurator.exe" --_project-script "%~n0" %*\n')
    launcher_toc.append((script_name + ".cmd", launcher_path, "EXECUTABLE"))


def _add_package_data(pattern, skip_vehicle_templates=False):
    for source in glob.glob(os.path.join(PACKAGE_ROOT, pattern), recursive=True):
        if not os.path.isfile(source):
            continue
        relative_path = os.path.relpath(source, PACKAGE_ROOT)
        top_level = relative_path.split(os.sep, 1)[0]
        if top_level in {"build", "dist"} or (skip_vehicle_templates and top_level == "vehicle_templates"):
            continue
        relative_dir = os.path.dirname(relative_path)
        destination = os.path.join("ardupilot_methodic_configurator", relative_dir) if relative_dir != "." else "ardupilot_methodic_configurator"
        datas.append((source, destination))

# Bundle runtime data with the application; vehicle templates are installed separately.
_add_package_data("**/*.json", skip_vehicle_templates=True)
_add_package_data("images/**/*.png")
_add_package_data("images/**/*.svg")
_add_package_data("locale/**/*.mo")

git_hash_path = os.path.join(PROJECT_ROOT, "git_hash.txt")
if os.path.isfile(git_hash_path):
    datas.append((git_hash_path, "ardupilot_methodic_configurator"))

hiddenimports = (
    ["packaging", "packaging.version", "packaging.specifiers"]
    + collect_submodules("ardupilot_methodic_configurator.plugins")
    + collect_submodules("pymavlink")
    + [entry.split(":", 1)[0] for entry in project_scripts.values()]
)

analysis = Analysis(
    [os.path.join(PROJECT_ROOT, "windows", "frozen_entrypoint.py")],
    pathex=[PACKAGE_ROOT, PROJECT_ROOT],
    hiddenimports=hiddenimports,
    datas=datas,
    hookspath=None,
    runtime_hooks=None,
)

pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    exclude_binaries=True,
    name="ardupilot_methodic_configurator.exe",
    debug=False,
    strip=None,
    upx=True,
    console=True,
    icon=os.path.join(PROJECT_ROOT, "windows", "ardupilot_methodic_configurator.ico"),
)

coll = COLLECT(
    exe,
    analysis.binaries,
    analysis.zipfiles,
    analysis.datas,
    launcher_toc,
    strip=None,
    upx=True,
    name="ardupilot_methodic_configurator",
)
