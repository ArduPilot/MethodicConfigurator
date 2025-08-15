#!/usr/bin/env python3

"""
Check for software updates and install them if available.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

import platform
import re
from argparse import ArgumentParser
from logging import basicConfig as logging_basicConfig
from logging import debug as logging_error
from logging import getLevelName as logging_getLevelName
from logging import info as logging_info
from logging import warning as logging_warning
from typing import Any, Optional
from webbrowser import open as webbrowser_open

from packaging import version
from requests import RequestException as requests_RequestException

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator import __version__ as current_version
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.backend_internet import (
    download_and_install_on_windows,
    download_and_install_pip_release,
    get_release_info,
)
from ardupilot_methodic_configurator.frontend_tkinter_software_update import UpdateDialog


def format_version_info(_current_version: str, _latest_release: str, changes: str) -> str:
    # remove pull request information from the changelog as PRs are not relevant for the end user.
    # PRs start with "[#" and end with ")", use a non-greedy match to remove them.
    changes = re.sub(r"\[#.*?\)", "", changes)

    # remove author information from the changelog as authors are not relevant for the end user.
    changes = re.sub(r"\(\[.*?\)\)", "", changes)

    # Clean up multiple spaces within each line while preserving newlines
    changes = "\n".join(re.sub(r"\s+", " ", line).strip() for line in changes.splitlines())

    return (
        _("Current version: {_current_version}")
        + "\n"
        + _("Latest version: {_latest_release}")
        + "\n\n"
        + _("Changes:\n{changes}")
    ).format(**locals())


class UpdateManager:
    """Manages the software update process including user interaction and installation."""

    def __init__(self) -> None:
        self.dialog: Optional[UpdateDialog] = None

    def _perform_download(self, latest_release: dict[str, Any]) -> bool:
        if platform.system() == "Windows":
            try:
                # Look for .exe files first
                exe_assets = [
                    asset for asset in latest_release.get("assets", []) if asset.get("name", "").lower().endswith(".exe")
                ]

                if exe_assets:
                    asset = exe_assets[0]  # Use the first .exe file
                elif latest_release.get("assets"):
                    asset = latest_release["assets"][0]  # Fallback to first asset
                else:
                    logging_error(_("No suitable assets found for Windows installation"))
                    return False

                return download_and_install_on_windows(
                    download_url=asset["browser_download_url"],
                    file_name=asset["name"],
                    progress_callback=self.dialog.update_progress if self.dialog else None,
                )
            except (KeyError, IndexError) as e:
                logging_error(_("Error accessing release assets: %s"), e)
                return False
            except Exception as e:  # pylint: disable=broad-exception-caught
                logging_error(_("Error during Windows download: %s"), e)
                return False

        try:
            return (
                download_and_install_pip_release(progress_callback=self.dialog.update_progress if self.dialog else None) == 0
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            logging_error(_("Error during pip installation: %s"), e)
            return False

    def check_and_update(self, latest_release: dict[str, Any], current_version_str: str) -> bool:
        try:
            latest_version = latest_release["tag_name"].lstrip("v")
            latest = version.parse(latest_version)
            current = version.parse(current_version_str)

            if current >= latest:
                logging_info(_("Already running latest version."))
                return False

            version_info = format_version_info(
                current_version_str, latest_version, latest_release.get("body", _("No changes listed"))
            )
            url = "https://github.com/ArduPilot/MethodicConfigurator/releases"
            webbrowser_open(url=url, new=0, autoraise=True)

            self.dialog = UpdateDialog(version_info, download_callback=lambda: self._perform_download(latest_release))
            return self.dialog.show()

        except KeyError as ke:
            logging_error(_("Key error during update process: %s"), ke)
            return False
        except requests_RequestException as req_ex:
            logging_error(_("Network error during update process: %s"), req_ex)
            return False
        except ValueError as val_ex:
            logging_error(_("Value error during update process: %s"), val_ex)
            return False

    @staticmethod
    def add_argparse_arguments(parser: ArgumentParser) -> ArgumentParser:
        parser.add_argument(
            "--skip-check-for-updates",
            action="store_true",
            help=_("Skip check for software updates before staring the software. Default is %(default)s."),
        )
        return parser


def check_for_software_updates() -> bool:
    """Main update orchestration function."""
    git_hash = LocalFilesystem.get_git_commit_hash()

    msg = _("Running version: {} (git hash: {})")
    logging_info(msg.format(current_version, git_hash))

    try:
        latest_release = get_release_info("/latest", should_be_pre_release=False)
        update_manager = UpdateManager()
        return update_manager.check_and_update(latest_release, current_version)
    except (requests_RequestException, ValueError) as e:
        msg = _("Update check failed: {}")
        logging_error(msg.format(e))
        return False


if __name__ == "__main__":
    logging_basicConfig(level=logging_getLevelName("DEBUG"), format="%(asctime)s - %(levelname)s - %(message)s")
    logging_warning(
        _(
            "This main is for testing and development only, usually the check_for_software_updates is"
            " called from another script"
        )
    )
    check_for_software_updates()
