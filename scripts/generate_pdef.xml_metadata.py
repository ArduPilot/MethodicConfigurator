#!/usr/bin/env python3

"""
Rsync apm.pdef.xml files for different versions of the ArduPilot firmware.

For each version, it checks out the corresponding tag, generates parameter metadata,
and finally rsyncs the updated parameter metadata pdef.xml files.

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import datetime
import importlib.util
import os
import shutil
import subprocess
import sys

VEHICLE_TYPES = [
    "Copter",
    "Plane",
    "Rover",
    "ArduSub",
    "Tracker",
]  # Add future vehicle types here

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


def ensure_dependencies() -> None:
    """Check for and install required dependencies if they're missing."""
    required_packages = ["lxml"]

    for package in required_packages:
        if importlib.util.find_spec(package) is None:
            print(f"Installing required dependency: {package}")  # noqa: T201
            # This is safe as we're only installing known packages defined in the code
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])  # noqa: S603
            print(f"Successfully installed {package}")  # noqa: T201


def get_vehicle_tags(vehicle_type: str) -> list[str]:
    """
    Lists all tags in the ArduPilot repository that start with the given vehicle type followed by '-'.

    Returns a list of tag names.
    """
    try:
        # Change to the ArduPilot directory
        os.chdir("../ardupilot/")
        # Using git with a known pattern is safe in this context
        tags_output = subprocess.check_output(  # noqa: S603
            ["git", "tag", "--list", f"{vehicle_type}-[0-9]\\.[0-9]\\.[0-9]"],  # noqa: S607
            text=True,
        )
        # Return to the original directory
        os.chdir(old_cwd)
        return tags_output.splitlines()
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"Error getting {vehicle_type} tags: {e}")  # noqa: T201
        # Ensure we return to the original directory in case of error
        os.chdir(old_cwd)
        return []


def generate_vehicle_versions() -> dict[str, list[str]]:
    """Generates arrays for each vehicle type based on the tags fetched from the ArduPilot repository."""
    vehicle_versions: dict[str, list[str]] = {}

    for vehicle_type in VEHICLE_TYPES:
        tags = get_vehicle_tags(vehicle_type)
        if tags:
            vehicle_versions[vehicle_type] = [tag.split("-")[1] for tag in tags]

    return vehicle_versions


def create_one_pdef_xml_file(vehicle_type: str, dst_dir: str, git_tag: str) -> None:
    """Create a single pdef XML file for a specific vehicle type and version."""
    # Check if the file already exists
    dst_file = f"{dst_dir}/apm.pdef.xml"
    full_dst_path = f"{old_cwd}/{dst_dir}"
    full_dst_file = f"{old_cwd}/{dst_file}"

    if os.path.exists(full_dst_file):
        print(f"File {dst_file} already exists, skipping generation...")  # noqa: T201
        return

    try:
        os.chdir("../ardupilot")
        # These subprocess calls are safe as they use fixed commands
        subprocess.run(["git", "checkout", git_tag], check=True)  # noqa: S603, S607
        # subprocess.run(['git', 'pull'], check=True)
        subprocess.run(  # noqa: S603
            [
                os.path.abspath("Tools/autotest/param_metadata/param_parse.py"),
                "--vehicle",
                vehicle_type,
                "--format",
                "xml",
            ],
            check=True,
        )

        # Create the destination directory with parents if it doesn't exist
        if not os.path.exists(full_dst_path):
            os.makedirs(full_dst_path, exist_ok=True)

        with open("apm.pdef.xml", encoding="utf-8") as f:
            lines = f.readlines()

        # Insert an XML comment on line 3 in the apm.pdef.xml file
        # with the tag used to generate the file and the current date
        lines.insert(
            2,
            f"<!-- Generated from git tag {git_tag} on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} -->\n",
        )
        with open("apm.pdef.xml", "w", encoding="utf-8") as f:
            f.writelines(lines)
        shutil.copy("apm.pdef.xml", full_dst_file)
        print(f"Created {dst_file}")  # noqa: T201
    finally:
        # Return to the old working directory, even if an exception occurs
        os.chdir(old_cwd)


# Function to sync files using rsync
def sync_to_remote(vehicle_dir: str) -> None:
    """Sync files to the remote server using rsync."""
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

    print(f"Synchronizing {src_dir} to {dst_path}...")  # noqa: T201
    # RSYNC_PASSWORD environment variable will be automatically used by rsync
    print(rsync_cmd)  # noqa: T201
    subprocess.run(rsync_cmd, check=True)  # noqa: S603


def main() -> None:
    """Main function to generate and sync parameter definition XML files."""
    # Ensure required dependencies are installed
    ensure_dependencies()

    vehicle_versions = generate_vehicle_versions()

    # Iterate over the vehicle_versions list
    for vehicle_type, versions in vehicle_versions.items():
        vehicle_dir = vehicle_type
        if vehicle_type == "ArduSub":
            vehicle_dir = "Sub"

        for version in versions:
            if version[0] == "3" and vehicle_type != "AP_Periph":
                continue  # Skip ArduPilot 3.x versions, as param_parse.py does not support them out of the box
            if version[0] == "4" and version[2] == "0" and vehicle_type != "ArduSub":
                continue  # Skip ArduPilot 4.0.x versions, as param_parse.py does not support them out of the box
            if int(version[0]) < 4:
                continue  # Skip versions below 4.x.x, those have been done already
            if int(version[0]) == 4 and int(version[2]) < 6:
                continue  # Skip versions below 4.6.x, those have been done already
            create_one_pdef_xml_file(
                vehicle_type,
                f"{vehicle_dir}/stable-{version}",
                f"{vehicle_type}-{version}",
            )

        sync_to_remote(vehicle_dir)


if __name__ == "__main__":
    main()
