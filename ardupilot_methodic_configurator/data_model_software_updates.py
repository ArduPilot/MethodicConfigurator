#!/usr/bin/env python3

"""
Check for software updates and install them if available.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

import platform
import re
from argparse import ArgumentParser
from logging import basicConfig as logging_basicConfig
from logging import error as logging_error
from logging import getLevelName as logging_getLevelName
from logging import info as logging_info
from logging import warning as logging_warning
from typing import Any, Callable, Optional

from packaging import version
from requests import RequestException as requests_RequestException

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator import __version__ as current_version
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.backend_internet import (
    download_and_install_on_macos,
    download_and_install_on_windows,
    download_and_install_pip_release,
    get_expected_sha256_from_release,
    get_release_info,
    webbrowser_open_url,
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


def _find_asset(assets: list[dict[str, Any]], extension: str, allow_fallback: bool = False) -> Optional[dict[str, Any]]:
    """Return the first asset whose name ends with *extension*, falling back to the first asset when requested."""
    preferred = [a for a in assets if a.get("name", "").lower().endswith(extension)]
    if preferred:
        return preferred[0]
    if allow_fallback and assets:
        return assets[0]
    return None


def _install_from_asset(
    asset: dict[str, Any],
    latest_release: dict[str, Any],
    install_fn: Callable[..., bool],
    progress_callback: Optional[Callable[[float, str], None]],
) -> bool:
    """Fetch SHA256 for *asset* and invoke the platform-specific *install_fn*."""
    expected_sha256 = get_expected_sha256_from_release(latest_release, asset["name"])
    return install_fn(
        download_url=asset["browser_download_url"],
        file_name=asset["name"],
        progress_callback=progress_callback,
        expected_sha256=expected_sha256,
    )


class UpdateManager:
    """Manages the software update process including user interaction and installation."""

    def __init__(self) -> None:
        self.dialog: Optional[UpdateDialog] = None

    def _install_windows(
        self,
        latest_release: dict[str, Any],
        progress_callback: Optional[Callable[[float, str], None]],
    ) -> bool:
        """Select the best Windows asset (.exe preferred) and install it."""
        asset = _find_asset(latest_release.get("assets", []), ".exe", allow_fallback=True)
        if asset is None:
            logging_error(_("No suitable assets found for Windows installation"))
            return False
        return _install_from_asset(asset, latest_release, download_and_install_on_windows, progress_callback)

    def _install_macos(
        self,
        latest_release: dict[str, Any],
        progress_callback: Optional[Callable[[float, str], None]],
    ) -> bool:
        """Select the best macOS asset (.dmg preferred) and install it, falling back to pip."""
        asset = _find_asset(latest_release.get("assets", []), ".dmg")
        if asset is None:
            logging_info(_("No DMG asset found for macOS, falling back to pip installation"))
            return download_and_install_pip_release(progress_callback=progress_callback) == 0
        return _install_from_asset(asset, latest_release, download_and_install_on_macos, progress_callback)

    def _perform_download(self, latest_release: dict[str, Any]) -> bool:
        progress_callback = self.dialog.update_progress if self.dialog else None
        handlers: dict[str, Callable[[], bool]] = {
            "Windows": lambda: self._install_windows(latest_release, progress_callback),
            "Darwin": lambda: self._install_macos(latest_release, progress_callback),
        }
        handler = handlers.get(
            platform.system(),
            lambda: download_and_install_pip_release(progress_callback=progress_callback) == 0,
        )
        try:
            return handler()
        except (KeyError, IndexError) as e:
            logging_error(_("Error accessing release assets: %s"), e)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logging_error(_("Error during installation: %s"), e)
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
            webbrowser_open_url(url=url, new=0, autoraise=True)

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


if __name__ == "__main__":  # pragma: no cover
    logging_basicConfig(level=logging_getLevelName("DEBUG"), format="%(asctime)s - %(levelname)s - %(message)s")
    logging_warning(
        _(
            "This main is for testing and development only, usually the check_for_software_updates is"
            " called from another script"
        )
    )
    check_for_software_updates()
