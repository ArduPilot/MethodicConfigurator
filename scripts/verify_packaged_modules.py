#!/usr/bin/env python3

"""
Check that wheels and PyInstaller PYZ archives contain application submodules.

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import argparse
from pathlib import Path
from zipfile import ZipFile


def required_modules() -> set[str]:
    """Return every plugin and log-analysis module from the source checkout."""
    project_root = Path(__file__).resolve().parents[1]
    package_root = project_root / "ardupilot_methodic_configurator"
    modules = set()
    for subpackage in ("plugins", "log_analysis"):
        for source in (package_root / subpackage).rglob("*.py"):
            parts = source.relative_to(project_root).with_suffix("").parts
            if parts[-1] == "__init__":
                parts = parts[:-1]
            modules.add(".".join(parts))
    return modules


def verify_archive(archive: Path) -> None:
    """Raise an error if an archive is missing any required application module."""
    if archive.suffix == ".whl":
        with ZipFile(archive) as wheel:
            modules = {
                name.removesuffix(".py").removesuffix("/__init__").replace("/", ".")
                for name in wheel.namelist()
                if name.endswith(".py")
            }
    elif archive.suffix == ".pyz":
        # PyInstaller is needed only in frozen-build jobs, not wheel-build jobs.
        # pylint: disable-next=import-outside-toplevel
        from PyInstaller.archive.readers import ZlibArchiveReader  # noqa: PLC0415

        modules = set(ZlibArchiveReader(str(archive)).toc)
    else:
        message = f"Unsupported archive type: {archive}"
        raise ValueError(message)

    missing = required_modules() - modules
    if missing:
        message = f"{archive} is missing required modules: {', '.join(sorted(missing))}"
        raise ValueError(message)


def main() -> None:
    """Validate each supplied wheel or PYZ archive, exiting nonzero on failure."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archives", type=Path, nargs="+")
    args = parser.parse_args()
    for archive in args.archives:
        try:
            verify_archive(archive)
        except ValueError as error:
            parser.exit(1, f"{error}\n")
        print(f"Verified plugin and log-analysis modules in {archive}")  # noqa: T201


if __name__ == "__main__":
    main()
