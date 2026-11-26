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
from collections.abc import Callable
from dataclasses import dataclass
from logging import error as logging_error
from logging import info as logging_info
from typing import Any

from httpx2 import HTTPError as httpx2_HTTPError
from httpx2 import InvalidURL as httpx2_InvalidURL
from packaging import version

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

# Shows the update prompt and, when the user accepts, runs the download callback.
# Returns True when the update succeeded. The GUI adapter lives in frontend_tkinter_software_update.
UpdatePresenter = Callable[[str, Callable[[Callable[[float, str], None]], bool]], bool]


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


def _find_asset(assets: list[dict[str, Any]], extension: str) -> dict[str, Any] | None:
    """Return the first asset whose name ends with *extension*, or None if there is none."""
    preferred = [a for a in assets if a.get("name", "").lower().endswith(extension)]
    if preferred:
        return preferred[0]
    return None


def _install_from_asset(
    asset: dict[str, Any],
    latest_release: dict[str, Any],
    install_fn: Callable[..., bool],
    progress_callback: Callable[[float, str], None] | None,
) -> bool:
    """Fetch SHA256 for *asset* and invoke the platform-specific *install_fn*."""
    expected_sha256 = get_expected_sha256_from_release(latest_release, asset["name"])
    return install_fn(
        download_url=asset["browser_download_url"],
        file_name=asset["name"],
        progress_callback=progress_callback,
        expected_sha256=expected_sha256,
    )


@dataclass(frozen=True)
class InstallerPlan:
    """Install the release *asset* with the platform installer *install_fn*."""

    asset: dict[str, Any]
    install_fn: Callable[..., bool]


@dataclass(frozen=True)
class PipPlan:
    """Install the latest release from PyPI with pip/uv. *macos_without_dmg* is set when macOS had no DMG asset."""

    macos_without_dmg: bool = False


InstallPlan = InstallerPlan | PipPlan


def select_install_plan(system: str, assets: list[dict[str, Any]]) -> InstallPlan | None:
    """
    Decide how to install a release on *system* from its *assets*. Performs no I/O.

    Returns None when the platform needs an installer and the release has none.
    """
    if system == "Windows":
        asset = _find_asset(assets, ".exe")
        return None if asset is None else InstallerPlan(asset, download_and_install_on_windows)
    if system == "Darwin":
        asset = _find_asset(assets, ".dmg")
        if asset is None:
            return PipPlan(macos_without_dmg=True)
        return InstallerPlan(asset, download_and_install_on_macos)
    return PipPlan()


class UpdateManager:
    """Manages the software update process including user interaction and installation."""

    def __init__(self, presenter: UpdatePresenter) -> None:
        self.presenter = presenter

    def _perform_download(
        self,
        latest_release: dict[str, Any],
        progress_callback: Callable[[float, str], None] | None = None,
    ) -> bool:
        try:
            plan = select_install_plan(platform.system(), latest_release.get("assets", []))
            if plan is None:
                logging_error(_("No suitable assets found for Windows installation"))
                return False
            if isinstance(plan, PipPlan):
                if plan.macos_without_dmg:
                    logging_info(_("No DMG asset found for macOS, falling back to pip installation"))
                return download_and_install_pip_release(progress_callback=progress_callback)
            return _install_from_asset(plan.asset, latest_release, plan.install_fn, progress_callback)
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

            return self.presenter(version_info, lambda report: self._perform_download(latest_release, report))

        except KeyError as ke:
            logging_error(_("Key error during update process: %s"), ke)
            return False
        except httpx2_HTTPError as req_ex:
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


def check_for_software_updates(presenter: UpdatePresenter) -> bool:
    """Main update orchestration function."""
    git_hash = LocalFilesystem.get_git_commit_hash()

    msg = _("Running version: {} (git hash: {})")
    logging_info(msg.format(current_version, git_hash))

    try:
        latest_release = get_release_info("/latest", should_be_pre_release=False)
        update_manager = UpdateManager(presenter)
        return update_manager.check_and_update(latest_release, current_version)
    except (httpx2_HTTPError, httpx2_InvalidURL, OSError, ValueError) as e:
        msg = _("Update check failed: {}")
        logging_error(msg.format(e))
        return False
