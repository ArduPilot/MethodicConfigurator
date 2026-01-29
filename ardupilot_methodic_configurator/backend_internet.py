"""
Check for software updates and install them if available.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

import contextlib
import hashlib
import os
import random
import re
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
from logging import warning as logging_warning
from typing import Any, Callable, Optional, Union
from urllib.parse import urljoin
from webbrowser import open as webbrowser_open

import certifi
from requests import HTTPError as requests_HTTPError
from requests import RequestException as requests_RequestException
from requests import Response
from requests import Timeout as requests_Timeout
from requests import get as requests_get
from requests.exceptions import RequestException

from ardupilot_methodic_configurator import _

# Constants
GITHUB_API_URL_RELEASES = "https://api.github.com/repos/ArduPilot/MethodicConfigurator/releases/"
DOWNLOAD_BLOCK_SIZE = 8192
PE_MAGIC_BYTES = b"MZ"  # Windows PE executable DOS header signature


def _build_proxies() -> dict[str, str]:
    proxies_dict = {
        "http": os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy"),
        "https": os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy"),
        "no_proxy": os.environ.get("NO_PROXY") or os.environ.get("no_proxy"),
    }
    return {k: v for k, v in proxies_dict.items() if v is not None}


def _existing_size_and_headers(path: str, resume: bool) -> tuple[int, dict[str, str]]:
    """Get existing file size and appropriate headers for resume capability."""
    headers: dict[str, str] = {}
    existing = 0
    if resume:
        try:
            existing = os.path.getsize(path)
            if existing > 0:
                headers["Range"] = f"bytes={existing}-"
        except (OSError, FileNotFoundError):
            # File doesn't exist or can't be accessed - will download from start
            existing = 0
    return existing, headers


def _parse_total_size(response: Response) -> int:
    """Parse total file size from response headers."""
    content_range = response.headers.get("Content-Range")
    if content_range:
        try:
            return int(content_range.split("/")[-1])
        except (ValueError, IndexError, AttributeError):
            return 0
    return int(response.headers.get("content-length", 0) or 0)


def _write_response(  # pylint: disable=too-many-arguments, too-many-positional-arguments
    response: Response,
    path: str,
    mode: str,
    initial_downloaded: int,
    total_size: int,
    progress_callback: Optional[Callable[[float, str], None]],
) -> int:
    """Write HTTP response to disk with progress tracking."""
    downloaded_local = initial_downloaded
    with open(path, mode) as fh:  # pylint: disable=unspecified-encoding
        for chunk in response.iter_content(chunk_size=DOWNLOAD_BLOCK_SIZE):
            if chunk:
                fh.write(chunk)
                downloaded_local += len(chunk)
                if progress_callback and total_size:
                    progress = (downloaded_local / total_size) * 100
                    msg_local = _("Downloading ... {:.1f}%")
                    progress_callback(progress, msg_local.format(progress))
    return downloaded_local


def _get_verify_param() -> Union[str, bool]:
    """
    Return the CA bundle path to use with requests, especially for PyInstaller builds.

    Respects REQUESTS_CA_BUNDLE/SSL_CERT_FILE if set.
    """
    env_bundle = os.environ.get("REQUESTS_CA_BUNDLE") or os.environ.get("SSL_CERT_FILE")
    if env_bundle and os.path.isfile(env_bundle):
        return env_bundle

    # When frozen, try the bundled certifi/cacert.pem
    if getattr(sys, "frozen", False):
        base_path = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        # Use POSIX-style join so tests expecting forward slashes pass on all platforms
        bundled_cert = base_path.rstrip("/\\") + "/certifi/cacert.pem"
        if os.path.isfile(bundled_cert):
            return bundled_cert

    # Fallback: normal certifi location
    return certifi.where()


def _attempt_download_once(  # pylint: disable=too-many-arguments, too-many-positional-arguments
    url: str,
    local_filename: str,
    timeout: int,
    proxies: dict[str, str],
    headers: dict[str, str],
    progress_callback: Optional[Callable[[float, str], None]],
) -> bool:
    """
    Perform a single HTTP GET and write the response to disk.

    Returns True on success, False on failure.
    """
    # Build request parameters dynamically to avoid code duplication
    request_kwargs: dict[str, Any] = {
        "stream": True,
        "timeout": timeout,
        "proxies": proxies,
        "verify": _get_verify_param(),
    }
    if headers:
        request_kwargs["headers"] = headers

    response = requests_get(url, **request_kwargs)  # noqa: S113
    response.raise_for_status()

    total_size = _parse_total_size(response)

    # Determine write mode and existing size based on server response
    # Only use append mode if server accepted the Range request (status 206)
    mode = "ab" if response.status_code == 206 else "wb"
    existing_size = 0
    if mode == "ab":
        # Parse existing size from original Range header
        try:
            existing_size = int(headers.get("Range", "bytes=0-").split("=")[1].split("-")[0])
        except (ValueError, IndexError, AttributeError):
            existing_size = 0

    downloaded = _write_response(response, local_filename, mode, existing_size, total_size, progress_callback)

    if progress_callback:
        progress_callback(100.0, _("Download complete"))

    return bool(downloaded > 0)


def download_file_from_url(  # pylint: disable=too-many-arguments, too-many-positional-arguments
    url: str,
    local_filename: str,
    timeout: int = 30,
    progress_callback: Optional[Callable[[float, str], None]] = None,
    retries: int = 3,
    backoff_factor: float = 0.5,
    allow_resume: bool = True,
) -> bool:
    """
    Download a file with optional resume and retry support.

    Small wrapper that calls a single-attempt helper to keep cyclomatic
    complexity low for linters.
    """
    if not url or not local_filename:
        logging_error(_("URL or local filename not provided."))
        return False

    proxies = _build_proxies()
    os.makedirs(os.path.dirname(os.path.abspath(local_filename)), exist_ok=True)

    attempt = 0
    while attempt <= retries:
        try:
            _existing_size, headers = _existing_size_and_headers(local_filename, allow_resume)
            return _attempt_download_once(url, local_filename, timeout, proxies, headers, progress_callback)
        except requests_Timeout:
            logging_error(_("Download timed out (attempt %d)"), attempt + 1)
        except requests_RequestException as e:
            logging_error(_("Network error during download (attempt %d): %s"), attempt + 1, e)
        except OSError as e:
            # OSError may be transient (disk full, temp permissions) - retry
            logging_error(_("File system error during download (attempt %d): %s"), attempt + 1, e)
        except ValueError as e:
            # ValueError is non-retryable - clean up and exit
            logging_error(_("Invalid data received from %s: %s"), url, e)
            with contextlib.suppress(OSError, FileNotFoundError):
                os.remove(local_filename)
            return False

        attempt += 1
        if attempt > retries:
            break
        # Exponential backoff with jitter to avoid thundering herd problem
        # Using random.uniform for timing jitter (NOT for cryptographic purposes)
        # This is safe because:
        # 1. We only use it for sleep timing randomization, not security
        # 2. The jitter prevents multiple clients from retrying simultaneously
        # 3. Even if an attacker could predict retry times, there's no security impact
        # 4. Cryptographic randomness would be overkill and slower for this use case
        sleep_time = backoff_factor * (2 ** (attempt - 1))
        sleep_time = sleep_time * random.uniform(0.8, 1.2)  # noqa: S311
        time.sleep(sleep_time)

    # Clean up partial download after all retries exhausted
    logging_error(_("Download failed after %d attempts, cleaning up partial file"), retries + 1)
    with contextlib.suppress(OSError, FileNotFoundError):
        os.remove(local_filename)
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
        response = requests_get(url, timeout=timeout, verify=_get_verify_param())
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
    """
    Try to obtain the expected SHA256 for a release asset.

    This first checks the asset's digest field (GitHub-computed SHA256),
    then searches release assets for checksum files (SHA256SUMS, *.sha256,
    checksums.txt) and parses them for the given filename.
    """
    if not release_info or not filename:
        return None

    assets = release_info.get("assets", [])

    # First, check if the asset itself has a digest field (GitHub-computed SHA256)
    for asset in assets:
        if asset.get("name") == filename:
            digest = asset.get("digest", "")
            if digest.startswith("sha256:"):
                return digest[7:]  # Remove "sha256:" prefix

    # Next, search for checksum files in release assets
    for asset in assets:
        name = asset.get("name", "")
        lname = name.lower()
        if any(k in lname for k in ("sha256", "checksum", "checksums", "sha256sums", "sha256sum")) or lname.endswith(".txt"):
            url = asset.get("browser_download_url")
            if not url:
                continue
            try:
                resp = requests_get(url, timeout=timeout, verify=_get_verify_param())
                resp.raise_for_status()
                text = resp.text
                # look for lines like: <hash>  filename
                m = re.search(r"([A-Fa-f0-9]{64})\s+\*?" + re.escape(filename), text)
                if m:
                    return m.group(1)
                # otherwise use first 64-hex found
                m2 = re.search(r"([A-Fa-f0-9]{64})", text)
                if m2:
                    return m2.group(1)
            except RequestException:
                continue

    return None


def _validate_windows_installer_url(url: str) -> bool:
    """Validate that URL is from a trusted GitHub source."""
    # This whitelist is intentionally restrictive for security reasons
    if url.startswith("https://github.com/"):
        return True
    logging_error(_("Windows installer URL must be from github.com: %s"), url)
    return False


def _verify_installer_integrity(path: str, expected_sha256: Optional[str]) -> bool:
    """Verify SHA256 checksum of downloaded installer if expected hash is provided."""
    if not expected_sha256:
        logging_warning(_("could not get expected SHA256 checksum from github.com"))
        return True

    actual_hash = _compute_sha256(path)
    if actual_hash.lower() != expected_sha256.lower():
        logging_error(_("SHA256 mismatch for downloaded installer: expected %s got %s"), expected_sha256, actual_hash)
        with contextlib.suppress(OSError, FileNotFoundError):
            os.remove(path)
        return False
    return True


def _validate_windows_installer_file(path: str) -> bool:
    """Validate installer file size, PE signature, and set secure permissions."""
    try:
        st = os.stat(path)
        if st.st_size < 1024:
            logging_error(_("Downloaded installer too small: %d bytes"), st.st_size)
            with contextlib.suppress(OSError, FileNotFoundError):
                os.remove(path)
            return False

        with open(path, "rb") as _fh:
            sig = _fh.read(2)
        # see ARCHITECTURE_1_software_update.md for rationale of this simplified test
        if sig != PE_MAGIC_BYTES:
            logging_error(_("Downloaded installer does not appear to be a Windows executable"))
            with contextlib.suppress(OSError, FileNotFoundError):
                os.remove(path)
            return False

        # Try to restrict permissions where supported
        with contextlib.suppress(PermissionError, OSError, NotImplementedError):
            os.chmod(path, 0o600)

        return True
    except OSError as e:
        logging_error(_("Failed to validate downloaded installer: %s"), e)
        with contextlib.suppress(OSError, FileNotFoundError):
            os.remove(path)
        return False


def _create_installer_batch_file(temp_dir: str, installer_path: str) -> str:
    """Create a batch file to run the installer after the process exits."""
    batch_file_path = os.path.join(temp_dir, "run_installer.bat")
    with open(batch_file_path, "w", encoding="utf-8") as batch_file:
        # Wait a moment for the main process to exit
        batch_file.write("@echo off\n")
        batch_file.write("ping 127.0.0.1 -n 2 > nul\n")  # Wait ~1 second
        batch_file.write(f'if exist "{installer_path}" (\n')  # Check if installer still exists
        batch_file.write(f'  start "" "{installer_path}"\n')  # Run the installer
        batch_file.write(") else (\n")
        batch_file.write("  echo Installer not found\n")
        batch_file.write(")\n")
        batch_file.write("del %0\n")  # Delete the batch file itself
    return batch_file_path


def _launch_installer_and_exit(batch_file_path: str, progress_callback: Optional[Callable[[float, str], None]] = None) -> None:
    """Launch the installer batch file and exit the current process."""
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

    # Exit this process ASAP without cleanup, there is nothing worth cleanup at this point.
    # This liberates file handlers ASAP to allow the installer to run without issues.
    os._exit(0)  # Force exit without cleanup


def download_and_install_on_windows(
    download_url: str,
    file_name: str,
    progress_callback: Optional[Callable[[float, str], None]] = None,
    expected_sha256: Optional[str] = None,
) -> bool:
    """
    Download and install a new version of the application on Windows.

    This function orchestrates the complete update process by calling helper functions
    for validation, download, integrity checks, and installation.

    Args:
        download_url: The URL from which to download the installer
        file_name: The name to save the downloaded file as
        progress_callback: Optional callback function to report progress
                          Takes two arguments: progress (0.0-1.0) and status message
        expected_sha256: Optional SHA256 hex digest expected for the downloaded installer. If provided,
            the downloaded file will be verified and the install will be aborted on mismatch.

    Returns:
        bool: True if the process started successfully (note: if successful,
              the application will exit and never return from this function)

    """
    # Validate URL is from trusted GitHub source
    if not _validate_windows_installer_url(download_url):
        return False

    logging_info(_("Downloading and installing new version for Windows..."))

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = os.path.join(temp_dir, file_name)

            # Download with progress updates
            if not download_file_from_url(
                download_url,
                temp_path,
                timeout=60,  # Increased timeout for large files
                progress_callback=progress_callback,
            ):
                logging_error(_("Failed to download installer from %s"), download_url)
                return False

            # Verify SHA256 checksum if provided
            if not _verify_installer_integrity(temp_path, expected_sha256):
                return False

            # Validate file size, PE signature, and set secure permissions
            if not _validate_windows_installer_file(temp_path):
                return False

            if progress_callback:
                progress_callback(0.0, _("Starting installation..."))

            # Create batch file to run installer after exit
            batch_file_path = _create_installer_batch_file(temp_dir, temp_path)

            # Launch installer and exit (this function never returns)
            _launch_installer_and_exit(batch_file_path, progress_callback)

    except subprocess.SubprocessError as e:
        logging_error(_("Installation failed: {}").format(e))
    except OSError as e:
        logging_error(_("File operation failed: {}").format(e))
    return False


def download_and_install_pip_release(progress_callback: Optional[Callable[[float, str], None]] = None) -> int:
    """Download and install the latest release via pip/uv from PyPI."""
    if progress_callback:
        progress_callback(0.0, _("Starting installation..."))

    # Try uv first (preferred for this project), then fall back to pip
    uv_path = shutil.which("uv")

    if uv_path:
        logging_info(_("Updating via uv for Linux and macOS..."))

        # Use uv pip for installation (recommended approach)
        cmd = [
            uv_path,
            "pip",
            "install",
            "--upgrade",
            "--index-url",
            "https://pypi.org/simple",
            "ardupilot_methodic_configurator",
        ]
    else:
        logging_info(_("Updating via pip for Linux and macOS..."))

        # Fall back to standard pip if uv is not available
        cmd = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--upgrade",
            "--index-url",
            "https://pypi.org/simple",
            "ardupilot_methodic_configurator",
        ]

    try:
        ret = subprocess.check_call(cmd)  # noqa: S603
    except subprocess.CalledProcessError as e:
        logging_error(_("Installation command failed: {}").format(e))
        return e.returncode
    except FileNotFoundError as e:
        if uv_path:
            logging_error(_("uv not found at expected path: {}").format(e))
        else:
            logging_error(_("pip module not available. Please install pip or uv: {}").format(e))
        return 1

    if ret == 0 and progress_callback:
        progress_callback(100.0, _("Download complete"))

    return ret


def _compute_sha256(path: str) -> str:
    """Compute SHA256 hex digest for a file."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(DOWNLOAD_BLOCK_SIZE), b""):
            h.update(chunk)
    return h.hexdigest()


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
        response = requests_get(url, timeout=5, stream=True, allow_redirects=True, proxies=proxies, verify=_get_verify_param())
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
