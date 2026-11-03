#!/usr/bin/env python3

"""
Rsync apm.pdef.xml files for different versions of the ArduPilot firmware.

For each version, it checks out the corresponding tag, generates parameter metadata,
and finally rsyncs the updated parameter metadata pdef.xml files.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import datetime as dt
import logging
import os
import re
import shutil
import subprocess

VEHICLE_TYPES = [
    "Copter",
    "Plane",
    "Rover",
    "ArduSub",
    "Tracker",
]  # Add future vehicle types here
PDEF_XML_FILENAME = "apm.pdef.xml"

logger = logging.getLogger(__name__)

# Error messages
ERR_USERNAME_NOT_SET = "RSYNC_USERNAME environment variable not set"
ERR_PASSWORD_NOT_SET = "RSYNC_PASSWORD environment variable not set"  # noqa: S105

RSYNC_USERNAME = os.environ.get("RSYNC_USERNAME")
if not RSYNC_USERNAME:
    raise ValueError(ERR_USERNAME_NOT_SET)

RSYNC_PASSWORD = os.environ.get("RSYNC_PASSWORD")
if not RSYNC_PASSWORD:
    raise ValueError(ERR_PASSWORD_NOT_SET)

# Store the current working directory
old_cwd = os.getcwd()
# Store the ardupilot root directory
ardupilot_dir = os.path.abspath(os.path.join(old_cwd, "..", "ardupilot"))


def ensure_dependencies() -> None:
    """
    No runtime deps beyond the stdlib.

    Kept as a hook so main() doesn't need to change when a runtime
    dependency is added. The old body pip-installed lxml==6.1.3, which
    was only used for post-processing apm.pdef.xml; that was replaced
    by param_parse.py's --git-tag flag.
    """


def get_vehicle_tags(vehicle_type: str) -> list[str]:
    """
    Lists all tags in the ArduPilot repository that start with the given vehicle type followed by '-'.

    Returns a list of tag names.
    """
    try:
        # Using git with a known pattern is safe in this context
        tags_output = subprocess.check_output(  # noqa: S603
            ["git", "tag", "--list", f"{vehicle_type}-*"],  # noqa: S607
            cwd=ardupilot_dir,
            text=True,
            timeout=120,
        )
        version_re = re.compile(rf"^{re.escape(vehicle_type)}-\d+\.\d+\.\d+$")
        return [tag for tag in tags_output.splitlines() if version_re.match(tag)]
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("Error getting %s tags:", vehicle_type)
        return []


def generate_vehicle_versions() -> dict[str, list[str]]:
    """Generates arrays for each vehicle type based on the tags fetched from the ArduPilot repository."""
    vehicle_versions: dict[str, list[str]] = {}

    for vehicle_type in VEHICLE_TYPES:
        tags = get_vehicle_tags(vehicle_type)
        if tags:
            vehicle_versions[vehicle_type] = [tag.split("-")[1] for tag in tags]

    return vehicle_versions


def create_one_pdef_xml_file(vehicle_type: str, dst_dir: str, git_tag: str) -> None:  # pylint: disable=too-many-locals
    """Create a single pdef XML file for a specific vehicle type and version."""
    dst_file = f"{dst_dir}/{PDEF_XML_FILENAME}"
    full_dst_path = os.path.join(old_cwd, dst_dir)
    full_dst_file = os.path.join(old_cwd, dst_file)
    src_xml = os.path.join(ardupilot_dir, PDEF_XML_FILENAME)

    # Check if the file already exists
    if os.path.exists(full_dst_file):
        logger.debug("File %s already exists, skipping generation", dst_file)
        return

    saved_ref = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],  # noqa: S607
        cwd=ardupilot_dir,
        text=True,
        timeout=60,
    ).strip()

    try:
        # These subprocess calls are safe as they use fixed commands
        subprocess.run(["git", "checkout", git_tag], check=True, cwd=ardupilot_dir, timeout=300)  # noqa: S603, S607

        # Remove any stale apm.pdef.xml from a previous run so the check after
        # generation can't accidentally copy a file we didn't produce this time.
        if os.path.exists(src_xml):
            logger.debug("Removing stale %s from a previous run", src_xml)
            os.unlink(src_xml)

        # Note: --git-tag was added to param_parse.py in October 2025. If an old tag
        # is ever generated (because its local pdef is missing), argparse will exit 2
        # before doing any work; the FileNotFoundError below catches that case.
        proc = subprocess.run(  # noqa: S603
            [
                os.path.join(ardupilot_dir, "Tools/autotest/param_metadata/param_parse.py"),
                "--vehicle",
                vehicle_type,
                "--format",
                "xml",
                "--git-tag",
                git_tag,
            ],
            # param_parse.py exits with the *validation warning count*,
            # not a boolean, and still writes apm.pdef.xml before sys.exit().
            # Treating warnings as hard failures would discard valid output.
            check=False,
            cwd=ardupilot_dir,
            capture_output=True,
            text=True,
            timeout=600,
        )

        if proc.returncode != 0:
            logger.warning(
                "param_parse.py for %s exited %d (likely validation warnings); keeping output if it exists",
                git_tag,
                proc.returncode,
            )
            for line in proc.stdout.splitlines():
                logger.debug("param_parse.py: %s", line)
            for line in proc.stderr.splitlines():
                logger.debug("param_parse.py stderr: %s", line)

        if not os.path.exists(src_xml):
            msg = f"param_parse.py did not produce {src_xml} (exit {proc.returncode})"
            raise FileNotFoundError(msg)

        # Create the destination directory with parents if it doesn't exist
        os.makedirs(full_dst_path, exist_ok=True)
        shutil.copy(src_xml, full_dst_file)
        # src_xml (= ardupilot_dir/apm.pdef.xml) is left in place; it is
        # overwritten by the next generation and is gitignored in ArduPilot.
        # Concurrent runs against the same checkout would race on it.
        timestamp = dt.datetime.now(dt.UTC).strftime("%Y-%m-%d")
        with open(full_dst_file, encoding="utf-8") as f:
            content = f.read()
        # Append " on <timestamp>" to the "--git-tag" comment emitted by xmlemit.py,
        # e.g. "<!-- Generated from git tag Copter-4.7.0 -->" becomes
        #      "<!-- Generated from git tag Copter-4.7.0 on 2026-11-03 -->".
        # (Date only, not full timestamp: keeps the output deterministic per day.)
        # If xmlemit ever reformats that comment, the n == 0 warning below fires
        # and we ship the file without a timestamp rather than mangling it.
        content, n = re.subn(
            r"(<!--[^>]*\b" + re.escape(git_tag) + r"\b[^>]*?)(\s*-->)",
            rf"\1 on {timestamp}\2",
            content,
            count=1,
        )
        if n == 0:
            logger.warning(
                "No comment mentioning %s found in %s; timestamp not added",
                git_tag,
                dst_file,
            )
        else:
            with open(full_dst_file, "w", encoding="utf-8", newline="\n") as f:
                f.write(content)
        logger.info("Created %s", dst_file)
    finally:
        # Restore the ArduPilot tree to whatever ref we were on before this
        # version's git checkout. check=False so a restore failure doesn't
        # mask the original exception; the warning below makes it visible.
        restore = subprocess.run(  # noqa: S603
            ["git", "checkout", saved_ref],  # noqa: S607
            check=False,
            cwd=ardupilot_dir,
            timeout=300,
        )
        if restore.returncode != 0:
            logger.warning(
                "Failed to restore %s to %s (rc=%d); subsequent tags may be checked out from a stale ref",
                ardupilot_dir,
                saved_ref,
                restore.returncode,
            )


def _redact_rsync_cmd(cmd: list[str]) -> list[str]:
    """Strip credentials from rsync:// URLs before logging."""
    return [re.sub(r"(rsync://[^:/@]+):[^@]*@", r"\1:***@", arg) for arg in cmd]


def sync_to_remote(vehicle_dir: str) -> None:
    """
    Mirror one vehicle's local pdef directory to firmware.ardupilot.org.

    Pushes ``<vehicle_dir>/`` (relative to the process CWD) to
    ``rsync://<RSYNC_USERNAME>@firmware.ardupilot.org/param_versioned/<vehicle_dir>/``.
    The remote directory is authoritative for the layout: rsync's ``-a``
    preserves timestamps and permissions, and no ``--delete`` is passed, so
    stale files on the remote are *not* removed.

    Authentication:
        * Username is taken from the ``RSYNC_USERNAME`` env var (validated at
          import time).
        * Password is *never* placed in argv; rsync reads ``RSYNC_PASSWORD``
          from the environment directly. The argv logged at DEBUG level is
          therefore safe to persist.

    Path contract:
        ``src_dir`` is relative, so it resolves against the process CWD —
        which nothing in this script changes, and which equals ``old_cwd``,
        the directory ``create_one_pdef_xml_file`` writes into. If a future
        change ever introduces ``os.chdir``, both must move to absolute
        paths together.

    Raises:
        subprocess.CalledProcessError: on any rsync failure (non-zero exit,
            connection error, auth failure). Callers decide whether to
            abort or continue.

    """
    src_dir = f"{vehicle_dir}/"
    dst_host = "firmware.ardupilot.org"
    dst_path = f"param_versioned/{vehicle_dir}/"

    # Construct the rsync command with rsync:// URL format
    rsync_cmd = [
        "rsync",
        "-avz",
        "--progress",
        src_dir,
        f"rsync://{RSYNC_USERNAME}@{dst_host}/{dst_path}",
    ]

    logger.info("Synchronizing %s to %s", src_dir, dst_path)
    # RSYNC_PASSWORD environment variable will be automatically used by rsync
    logger.debug("rsync argv: %s", _redact_rsync_cmd(rsync_cmd))
    subprocess.run(rsync_cmd, check=True, timeout=1800)  # noqa: S603


def _vehicle_dir(vehicle_type: str) -> str:
    """Map a vehicle type to its on-disk directory name."""
    return "Sub" if vehicle_type == "ArduSub" else vehicle_type


def _should_skip_version(version: str) -> bool:
    """
    True when a version should not be (re)generated.

    The base rule is the 4.6 cutoff: every 4.x release below 4.6 — and 3.x,
    whose only surviving producer (AP_Periph) isn't in VEHICLE_TYPES — has
    already been generated for every vehicle.
    """
    parts = version.split(".")
    major = int(parts[0])
    minor = int(parts[1]) if len(parts) > 1 else 0
    return (major, minor) < (4, 6)


def _generate_pdefs_for_vehicle(vehicle_type: str, versions: list[str]) -> int:
    vehicle_dir = _vehicle_dir(vehicle_type)
    failures = 0
    for version in versions:
        if _should_skip_version(version):
            continue

        try:
            create_one_pdef_xml_file(
                vehicle_type,
                f"{vehicle_dir}/stable-{version}",
                f"{vehicle_type}-{version}",
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            # e.g. git checkout fails on a missing tag, or param_parse.py aborts
            # at a pre-4.6 tag (import cgi on Python 3.13+); skip and keep going
            logger.exception("Skipping %s-%s:", vehicle_type, version)
            failures += 1
            continue
    try:
        sync_to_remote(vehicle_dir)
    except subprocess.CalledProcessError:
        logger.exception("Failed to sync %s:", vehicle_dir)
        failures += 1
    return failures


def main() -> int:
    """Main function to generate and sync parameter definition XML files."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # Ensure required dependencies are installed
    ensure_dependencies()

    total_failures = 0
    # Iterate over each vehicle type and its versions, generating pdef XML files and syncing them
    for vehicle_type, versions in generate_vehicle_versions().items():
        total_failures += _generate_pdefs_for_vehicle(vehicle_type, versions)

    if total_failures:
        logger.error("Completed with %d failure(s)", total_failures)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
