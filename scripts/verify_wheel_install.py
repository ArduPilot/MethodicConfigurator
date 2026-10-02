#!/usr/bin/env python3

"""
Build a clean wheel and verify imports and plugin registration in an isolated installation.

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

# All subprocess arguments come from trusted tools, tracked sources and our temporary directory; no shell is used.
# ruff: noqa: S603

import argparse
import hashlib
import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Allow direct execution without adding the source checkout to the installed interpreter.
archive_checks = importlib.import_module(
    f"{__package__}.verify_packaged_modules" if __package__ else "verify_packaged_modules"
)
required_modules = archive_checks.required_modules
verify_archive = archive_checks.verify_archive

IMPORT_CHECK = """
import importlib
import json
import sys
import tkinter
from pathlib import Path

environment = Path(sys.prefix).resolve()
for name in json.loads(sys.argv[1]):
    module = importlib.import_module(name)
    origin = Path(module.__file__).resolve()
    if not origin.is_relative_to(environment):
        raise RuntimeError(f"{name} resolved outside isolated environment: {origin}")
if tkinter._default_root is not None:
    raise RuntimeError("Module imports created a Tk window")
"""


def build_clean_wheel(project_root: Path, root: Path) -> Path:
    """Build one wheel from tracked sources without stale local build output."""
    git = shutil.which("git")
    if git is None:
        message = "git must be installed to build a clean wheel"
        raise RuntimeError(message)
    source = root / "source"
    source.mkdir()
    tracked = (
        subprocess.run([git, "ls-files", "-z"], cwd=project_root, check=True, capture_output=True, timeout=30)
        .stdout.decode("utf-8")
        .split("\0")
    )
    for name in filter(None, tracked):
        destination = source / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(project_root / name, destination)
    subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(root / "dist"), str(source)],
        cwd=root,
        check=True,
        timeout=300,
    )
    wheels = list((root / "dist").glob("*.whl"))
    if len(wheels) != 1:
        message = f"Expected exactly one wheel, found {len(wheels)}"
        raise RuntimeError(message)
    return wheels[0]


def wheel_from_report(report_path: Path) -> tuple[Path, str]:
    """Select the exact wheel and expected SHA256 recorded by the build frontend."""
    report = json.loads(report_path.read_text(encoding="utf-8"))
    wheels = [artifact for artifact in report["artifacts"] if artifact["kind"] == "wheel"]
    if len(wheels) != 1:
        message = f"Expected exactly one wheel in build report, found {len(wheels)}"
        raise ValueError(message)
    return Path(wheels[0]["path"]).resolve(), wheels[0]["hashes"]["sha256"]


def verify_wheel_hash(wheel: Path, expected_sha256: str) -> None:
    """Reject an artifact whose bytes differ from the expected wheel."""
    if hashlib.sha256(wheel.read_bytes()).hexdigest() != expected_sha256:
        message = f"Wheel SHA256 mismatch: {wheel}"
        raise ValueError(message)


def verify_wheel_install(wheel: Path | None = None, expected_sha256: str | None = None) -> None:
    """Validate an existing wheel, or build a clean wheel, in an isolated installation."""
    project_root = Path(__file__).resolve().parents[1]
    uv = shutil.which("uv")
    if uv is None:
        message = "uv must be installed to verify a non-editable wheel installation"
        raise RuntimeError(message)
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    with tempfile.TemporaryDirectory(prefix="amc-wheel-check-") as temporary:
        root = Path(temporary)
        wheel = wheel.resolve() if wheel is not None else build_clean_wheel(project_root, root)
        expected_sha256 = expected_sha256 or hashlib.sha256(wheel.read_bytes()).hexdigest()
        verify_wheel_hash(wheel, expected_sha256)
        verify_archive(wheel)
        venv = root / "installed"
        subprocess.run([uv, "--no-config", "venv", "--python", sys.executable, str(venv)], check=True, timeout=60)
        python = venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        subprocess.run(
            [uv, "--no-config", "pip", "install", "--python", str(python), str(wheel)],
            cwd=root,
            env=environment,
            check=True,
            timeout=300,
        )
        modules = sorted(required_modules(project_root) | {"ardupilot_methodic_configurator.__main__"})
        subprocess.run(
            [str(python), "-I", "-c", IMPORT_CHECK, json.dumps(modules)],
            cwd=root,
            env=environment,
            check=True,
            timeout=120,
        )
        subprocess.run(
            [str(python), "-I", "-m", "ardupilot_methodic_configurator", "--validate-plugins"],
            cwd=root,
            env=environment,
            check=True,
            timeout=60,
        )
        verify_wheel_hash(wheel, expected_sha256)


def main() -> None:
    """Select clean-build or existing-artifact validation from command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--wheel", type=Path, help="Validate this existing wheel without rebuilding")
    selection.add_argument("--build-report", type=Path, help="Validate the exact wheel and SHA256 in this build report")
    args = parser.parse_args()
    if args.build_report is not None:
        wheel, digest = wheel_from_report(args.build_report)
        verify_wheel_install(wheel, digest)
    else:
        verify_wheel_install(args.wheel)


if __name__ == "__main__":
    main()
