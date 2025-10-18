#!/usr/bin/env python3

"""
Merge .pot file strings into existing .po files.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import argparse
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from platform import system as platform_system
from typing import Optional


def process_locale_directory(locale_dir: Path, pot_file: Path, logger: logging.Logger) -> bool:
    """
    Process a single locale directory.

    Returns True on success, False on failure.
    """
    po_file = locale_dir / "ardupilot_methodic_configurator.po"

    # Validate inputs and determine tool locations
    should_process, merge_cmd, attrib_cmd = validate_and_get_tools(pot_file, po_file, logger)
    if not should_process:
        return False

    # Run msgmerge
    if merge_cmd:
        merged = run_msgmerge(merge_cmd, po_file, pot_file, logger)
    else:
        logger.error("No msgmerge command available for processing %s", po_file)
        merged = False

    if not merged:
        return False

    # Run msgattrib to remove fuzzy entries
    if attrib_cmd:
        return run_msgattrib(attrib_cmd, po_file, logger)
    logger.error("No msgattrib command available for processing %s", po_file)
    return False


def validate_and_get_tools(pot_file: Path, po_file: Path, logger: logging.Logger) -> tuple[bool, Optional[str], Optional[str]]:
    """
    Validate inputs and determine msgmerge/msgattrib executable paths.

    Returns (should_process, merge_cmd, attrib_cmd).
    """
    if not pot_file.is_file():
        logger.error("pot file missing: %s", pot_file)
        return False, None, None

    if not po_file.is_file():
        logger.warning("po file not found, skipping: %s", po_file)
        return False, None, None

    if platform_system() == "Windows":
        msgmerge_exe = Path(r"C:\Program Files\gettext-iconv\bin\msgmerge.exe")
        msgattrib_exe = Path(r"C:\Program Files\gettext-iconv\bin\msgattrib.exe")
        if not msgmerge_exe.exists() or not msgattrib_exe.exists():
            logger.error("gettext tools not found in expected Windows install location")
            return False, None, None
        return True, str(msgmerge_exe), str(msgattrib_exe)

    merge_cmd = shutil.which("msgmerge")
    attrib_cmd = shutil.which("msgattrib")
    if merge_cmd is None or attrib_cmd is None:
        logger.error("gettext tools (msgmerge/msgattrib) not found in PATH; please install them")
        return False, None, None

    return True, merge_cmd, attrib_cmd


def run_msgmerge(merge_cmd: str, po_file: Path, pot_file: Path, logger: logging.Logger) -> bool:
    """Run msgmerge to merge pot into po file. Returns True on success."""
    merge_args = [merge_cmd, "--update", "--no-fuzzy-matching", "--backup=none", str(po_file), str(pot_file)]
    try:
        result = subprocess.run(merge_args, check=False, capture_output=True, text=True)  # noqa: S603
        if result.returncode != 0:
            logger.error(
                "msgmerge failed for %s (rc=%s). stderr: %s",
                po_file,
                result.returncode,
                result.stderr,
            )
            return False
        logger.info("Successfully processed %s", po_file.parent)
        return True
    except OSError:
        logger.exception("Failed to execute msgmerge for %s", po_file)
        return False


def run_msgattrib(attrib_cmd: str, po_file: Path, logger: logging.Logger) -> bool:
    """Run msgattrib to remove fuzzy entries from po file. Returns True on success."""
    try:
        fd, tmp_str = tempfile.mkstemp(dir=str(po_file.parent))
        os.close(fd)
        tmp_path = Path(tmp_str)
    except OSError:
        logger.exception("Unable to create temporary file next to %s", po_file)
        return False

    attrib_args = [attrib_cmd, "--no-fuzzy", "-o", str(tmp_path), str(po_file)]
    result2 = subprocess.run(attrib_args, check=False, capture_output=True, text=True)  # noqa: S603
    if result2.returncode != 0:
        logger.error(
            "msgattrib failed for %s (rc=%s). stderr: %s",
            po_file,
            result2.returncode,
            result2.stderr,
        )
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            logger.debug("Failed to remove temp file %s", tmp_path)
        return False

    try:
        os.replace(str(tmp_path), str(po_file))
    except OSError:
        logger.exception("Failed to replace %s with %s", po_file, tmp_path)
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            logger.debug("Failed to remove temp file %s", tmp_path)
        return False

    logger.info("Removed fuzzy entries from %s", po_file)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge .pot into locale .po files and drop fuzzy entries")
    parser.add_argument(
        "--pot-file",
        type=Path,
        default=Path("ardupilot_methodic_configurator") / "locale" / "ardupilot_methodic_configurator.pot",
        help="Path to the .pot file",
    )
    parser.add_argument(
        "--locale-root",
        type=Path,
        default=Path("ardupilot_methodic_configurator") / "locale",
        help="Root locale directory to scan",
    )
    args = parser.parse_args()

    logging.basicConfig(level="INFO", format="%(asctime)s - %(levelname)s - %(message)s")
    logger = logging.getLogger(__name__)

    pot_file: Path = args.pot_file
    locale_root: Path = args.locale_root

    failures = 0

    if not locale_root.exists():
        logger.error("Locale root does not exist: %s", locale_root)
        return 1

    for root, dirs, _files in os.walk(str(locale_root)):
        if "LC_MESSAGES" in dirs:
            locale_dir = Path(root) / "LC_MESSAGES"
            ok = process_locale_directory(locale_dir, pot_file, logger)
            if not ok:
                failures += 1

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
