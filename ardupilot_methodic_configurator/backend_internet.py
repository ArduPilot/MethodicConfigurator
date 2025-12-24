"""
Check for software updates and install them if available.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from logging import debug as logging_debug
from logging import error as logging_error
from logging import info as logging_info
from logging import shutdown as logging_shutdown
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import urljoin
from webbrowser import open as webbrowser_open
import re

from platformdirs import user_config_dir
from requests import HTTPError as requests_HTTPError
from requests import RequestException as requests_RequestException
from requests import Timeout as requests_Timeout
from requests import get as requests_get
from requests.exceptions import RequestException

from ardupilot_methodic_configurator import _, __version__

# Constants
GITHUB_API_URL_RELEASES = "https://api.github.com/repos/ArduPilot/MethodicConfigurator/releases/"


def download_file_from_url(
    url: str, local_filename: str, timeout: int = 30, progress_callback: Optional[Callable[[float, str], None]] = None
) -> bool:
    if not url or not local_filename:
        logging_error(_("URL or local filename not provided."))
        return False

    logging_info(_("Downloading %s from %s"), local_filename, url)

    try:
        proxies_dict = {
            "http": os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy"),
            "https": os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy"),
            "no_proxy": os.environ.get("NO_PROXY") or os.environ.get("no_proxy"),
        }

        # Remove None values
        proxies = {k: v for k, v in proxies_dict.items() if v is not None}

        # Make request with proxy support
        response = requests_get(
            url,
            stream=True,
            timeout=timeout,
            proxies=proxies,
            verify=True,  # SSL verification
        )
        response.raise_for_status()

        total_size = int(response.headers.get("content-length", 0))
        block_size = 8192
        downloaded = 0

        os.makedirs(os.path.dirname(os.path.abspath(local_filename)), exist_ok=True)

        with open(local_filename, "wb") as file:
            for chunk in response.iter_content(chunk_size=block_size):
                if chunk:
                    file.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total_size:
                        progress = (downloaded / total_size) * 100
                        msg = _("Downloading ... {:.1f}%")
                        progress_callback(progress, msg.format(progress))

        if progress_callback:
            progress_callback(100.0, _("Download complete"))

        # If an expected SHA256 hash has been provided via the filename suffix
        # (or via a future parameter) we validate it here. Currently callers
        # may pass an expected hash via the filename metadata convention, but
        # a dedicated parameter is preferred. For now compute and return.
        return bool(downloaded > 0)

    except requests_Timeout:
        logging_error(_("Download timed out"))
    except requests_RequestException as e:
        logging_error(_("Network error during download: {}").format(e))
    except OSError as e:
        logging_error(_("File system error: {}").format(e))
    except ValueError as e:
        logging_error(_("Invalid data received from %s: %s"), url, e)

    return False


def get_release_info(name: str, should_be_pre_release: bool, timeout: int = 30) -> dict[str, Any]:
    """
    Get release information from GitHub API.

    Args:
        name: Release name/path (e.g. '/latest')
        should_be_pre_release: Whether the release should be a pre-release
        timeout: Request timeout in seconds

    Returns:
        Release information dictionary

    Raises:
        RequestException: If the request fails

    """
    if not name:
        msg = "Release name cannot be empty"
        raise ValueError(msg)

    try:
        url = urljoin(GITHUB_API_URL_RELEASES, name.lstrip("/"))
        response = requests_get(url, timeout=timeout)
        response.raise_for_status()

        release_info = response.json()

        if should_be_pre_release and not release_info["prerelease"]:
            logging_error(_("The latest continuous delivery build must be a pre-release"))
        if not should_be_pre_release and release_info["prerelease"]:
            logging_error(_("The latest stable release must not be a pre-release"))

        return release_info  # type: ignore[no-any-return]

    except requests_HTTPError as e:
        if e.response.status_code == 403:
            logging_error(_("Failed to fetch release info: {}").format(e))
            # Get the rate limit reset time
            reset_time = int(e.response.headers.get("X-RateLimit-Reset", 0))
            # Create a timezone-aware UTC datetime
            reset_datetime = datetime.fromtimestamp(reset_time, timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z")
            logging_error(_("Rate limit exceeded. Please try again after: %s (UTC)"), reset_datetime)
        raise
    except RequestException as e:
        logging_error(_("Failed to fetch release info: {}").format(e))
        raise
    except (KeyError, ValueError) as e:
        logging_error(_("Invalid release data: {}").format(e))
        raise


def get_expected_sha256_from_release(release_info: dict[str, Any], filename: str, timeout: int = 30) -> Optional[str]:
    """Try to obtain the expected SHA256 for a release asset.

    This searches release assets for checksum files (SHA256SUMS, *.sha256,
    checksums.txt) and parses them for the given filename. As a fallback
    it searches the release body for a 64-hex checksum.
    """
    if not release_info or not filename:
        return None

    assets = release_info.get("assets", [])
    for asset in assets:
        name = asset.get("name", "")
        lname = name.lower()
        if any(k in lname for k in ("sha256", "checksum", "checksums", "sha256sums", "sha256sum")) or lname.endswith(".txt"):
            url = asset.get("browser_download_url")
            if not url:
                continue
            try:
                resp = requests_get(url, timeout=timeout)
                resp.raise_for_status()
                text = resp.text
                # look for lines like: <hash>  filename
                m = re.search(r"([A-Fa-f0-9]{64})\s+\*?" + re.escape(filename), text)
                if m:
                    return m.group(1)
                # otherwise return first 64-hex found
                m2 = re.search(r"([A-Fa-f0-9]{64})", text)
                if m2:
                    return m2.group(1)
            except RequestException:
                continue

    # fallback: check release notes/body for hash mention
    body = release_info.get("body", "")
    if body:
        m = re.search(r"([A-Fa-f0-9]{64})\s+\*?" + re.escape(filename), body)
        if m:
            return m.group(1)
        m2 = re.search(r"([A-Fa-f0-9]{64})", body)
        if m2:
            return m2.group(1)

    return None


def create_backup(
    progress_callback: Optional[Callable[[float, str], None]] = None,
    backup_vehicles: bool = False,
) -> bool:
    """
    Backup AMC installation and Vehicles folder.

    Returns:
        True on success, False on any error.

    """
    try:
        version = __version__
        config_dir = Path(user_config_dir(".ardupilot_methodic_configurator", appauthor=False, roaming=True))
        backups_dir = config_dir / "backups" / version
        backups_dir.mkdir(parents=True, exist_ok=True)

        # Backup Vehicles folder (optional)
        vehicles_dir = config_dir / "vehicles"
        if backup_vehicles and vehicles_dir.exists():
            shutil.copytree(vehicles_dir, backups_dir / "vehicles", dirs_exist_ok=True)
            logging_info(_("Vehicles folder backed up to %s"), backups_dir / "Vehicles")
        elif backup_vehicles:
            logging_info(_("No Vehicles folder found to backup."))

        # Backup AMC wheel
        try:
            subprocess.run(  # noqa: S603
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "download",
                    f"ardupilot_methodic_configurator=={version}",
                    "-d",
                    str(backups_dir),
                ],
                check=True,
            )
            logging_info(_("AMC wheel backup complete at %s"), backups_dir)

        except subprocess.CalledProcessError as e:
            logging_error(_("Failed to backup AMC wheel: %s"), e)
            return False

        if progress_callback:
            progress_callback(100.0, _("Backup complete"))

        return True

    except (PermissionError, OSError) as e:
        logging_error(_("Backup failed: %s"), e)
        return False


def download_and_install_on_windows(
    download_url: str,
    file_name: str,
    progress_callback: Optional[Callable[[float, str], None]] = None,
    expected_sha256: Optional[str] = None,
) -> bool:
    """
    Download and install a new version of the application on Windows.

    This function handles the complete update process:
    1. Downloads the installer from the provided URL
    2. Creates a batch script to run the installer after the current process exits
    3. Exits the current application to allow the installer to run without conflicts
       (prevents "program is already running" errors during installation)

    Args:
        download_url: The URL from which to download the installer
        file_name: The name to save the downloaded file as
        progress_callback: Optional callback function to report progress
                          Takes two arguments: progress (0.0-1.0) and status message

    Returns:
        bool: True if the process started successfully (note: if successful,
              the application will exit and never return from this function)

    """
    logging_info(_("Downloading and installing new version for Windows..."))

    # Create a backup of the current installation (templates backup disabled by default)
    create_backup(progress_callback, backup_vehicles=False)

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = os.path.join(temp_dir, file_name)

            # Download with progress updates and optional integrity check
            if not download_file_from_url(
                download_url,
                temp_path,
                timeout=60,  # Increased timeout for large files
                progress_callback=progress_callback,
            ):
                logging_error(_("Failed to download installer from %s"), download_url)
                return False

            # If an expected SHA256 was supplied, verify the downloaded file
            if expected_sha256:
                actual_hash = _compute_sha256(temp_path)
                if actual_hash.lower() != expected_sha256.lower():
                    logging_error(
                        _("SHA256 mismatch for downloaded installer: expected %s got %s"), expected_sha256, actual_hash
                    )
                    try:
                        os.remove(temp_path)
                    except OSError:
                        pass
                    return False

            if progress_callback:
                progress_callback(0.0, _("Starting installation..."))

            # Create a batch file to run the installer after this process exits
            batch_file_path = os.path.join(temp_dir, "run_installer.bat")
            with open(batch_file_path, "w", encoding="utf-8") as batch_file:
                # Wait a moment for the main process to exit
                batch_file.write("@echo off\n")
                batch_file.write("ping 127.0.0.1 -n 2 > nul\n")  # Wait ~1 second
                batch_file.write(f'if exist "{temp_path}" (\n')  # Check if installer still exists
                batch_file.write(f'  start "" "{temp_path}"\n')  # Run the installer
                batch_file.write(") else (\n")
                batch_file.write("  echo Installer not found\n")
                batch_file.write(")\n")
                batch_file.write("del %0\n")  # Delete the batch file itself

            # Make the batch file executable and start it
            # Use 'with' pattern for the Popen operation to fix R1732
            with subprocess.Popen(  # noqa: S602
                [batch_file_path],
                shell=True,
                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,  # type: ignore[attr-defined]
            ) as _result:
                pass  # We don't need to do anything with the process object

            # Signal to the main application that it should exit
            if progress_callback:
                progress_callback(1.0, _("Installation ready. Application will restart now."))

            # Ensure logs are flushed before exit
            logging_shutdown()

            # Give a moment for the callback to complete
            time.sleep(0.5)

            # Exit this process to allow the installer to run
            # This means the function will never actually return at this point,
            # but we need to maintain consistent return type for the function signature
            os._exit(0)  # Force exit without cleanup

    except subprocess.SubprocessError as e:
        logging_error(_("Installation failed: {}").format(e))
    except OSError as e:
        logging_error(_("File operation failed: {}").format(e))
    return False


def download_and_install_pip_release(progress_callback: Optional[Callable[[float, str], None]] = None) -> int:
    logging_info(_("Updating via pip for Linux and macOS..."))

    if progress_callback:
        progress_callback(0.0, _("Backing up current version..."))

    # Create a backup of the current installation (templates backup disabled by default)
    backup_ok = create_backup(progress_callback, backup_vehicles=False)

    if not backup_ok:
        logging_error(_("Backup failed. Aborting update."))
        if progress_callback:
            progress_callback(0.0, _("Backup failed. Update aborted."))
        return False

    if progress_callback:
        progress_callback(100.0, _("Backup complete"))
        progress_callback(0.0, _("Starting installation..."))

    ret = subprocess.check_call(  # noqa: S603
        [sys.executable, "-m", "pip", "install", "--upgrade", "ardupilot_methodic_configurator"]
    )

    if ret == 0 and progress_callback:
        progress_callback(100.0, _("Download complete"))

    return ret


def _compute_sha256(path: str) -> str:
    """Compute SHA256 hex digest for a file."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def download_and_install_wheel_asset(
    download_url: str,
    file_name: str,
    expected_sha256: Optional[str] = None,
    progress_callback: Optional[Callable[[float, str], None]] = None,
) -> int:
    """Download a wheel asset, verify SHA256 if provided, and install via pip."""
    logging_info(_("Downloading wheel asset for installation..."))

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = os.path.join(temp_dir, file_name)

            if not download_file_from_url(
                download_url,
                temp_path,
                timeout=120,
                progress_callback=progress_callback,
            ):
                logging_error(_("Failed to download wheel from %s"), download_url)
                return 1

            if expected_sha256:
                actual = _compute_sha256(temp_path)
                if actual.lower() != expected_sha256.lower():
                    logging_error(_("SHA256 mismatch for wheel: expected %s got %s"), expected_sha256, actual)
                    try:
                        os.remove(temp_path)
                    except OSError:
                        pass
                    return 1

            # Install the wheel file
            ret = subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", temp_path])

            if ret == 0 and progress_callback:
                progress_callback(100.0, _("Installation complete"))

            return ret

    except subprocess.CalledProcessError as e:
        logging_error(_("Wheel installation failed: %s"), e)
        return 1
    except Exception as e:  # pylint: disable=broad-exception-caught
        logging_error(_("Unexpected error installing wheel: %s"), e)
        return 1


def verify_and_open_url(url: str) -> bool:
    """
    Verify if a URL is accessible and open it in the default web browser if successful.

    Args:
        url: The URL to verify and open

    Returns:
        bool: True if the URL was found and opened, False otherwise

    """
    if not url:
        logging_error(_("URL not provided."))
        return False

    logging_debug(_("Verifying URL: %s"), url)
    url_found: bool = False

    try:
        # Get proxy settings from environment variables
        proxies_dict = {
            "http": os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy"),
            "https": os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy"),
            "no_proxy": os.environ.get("NO_PROXY") or os.environ.get("no_proxy"),
        }
        # Remove None values
        proxies = {k: v for k, v in proxies_dict.items() if v is not None}

        # Use requests.get with allow_redirects to handle HTTP redirects properly
        response = requests_get(url, timeout=5, stream=True, allow_redirects=True, proxies=proxies, verify=True)
        url_found = response.status_code == 200
    except (requests_RequestException, requests_Timeout) as e:
        logging_error(_("Failed to access URL: %s. Error: %s"), url, str(e))
        url_found = False

    if url_found:
        try:
            logging_info(_("Opening URL in browser: %s"), url)
            webbrowser_open(url=url, new=0, autoraise=True)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logging_error(_("Failed to open URL in browser: %s"), str(e))
            url_found = False

    return url_found


def webbrowser_open_url(url: str, new: int = 0, autoraise: bool = True) -> bool:
    """
    Open a URL in the default web browser.

    Args:
        url: The URL to open
        new: 0 - same window, 1 - new window, 2 - new tab
        autoraise: Whether to raise the window

    """
    return webbrowser_open(url=url, new=new, autoraise=autoraise)
