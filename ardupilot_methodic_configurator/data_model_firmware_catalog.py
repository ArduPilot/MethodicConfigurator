"""
Select APJ releases for a connected board from ArduPilot's firmware manifest.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from urllib.parse import urlparse

from ardupilot_methodic_configurator import _

# First tagged releases whose ChibiOS APJ generator writes git_identity.
# Earlier APJs cannot pass the manifest git-sha check in upload_release.
_FIRST_IDENTIFIED_RELEASE: dict[str, tuple[int, int, int]] = {
    "Copter": (3, 6, 6),
    "Plane": (3, 9, 6),
    "Rover": (3, 5, 0),
    "Sub": (4, 0, 0),
}


def _has_verifiable_identity(vehicle_type: str, version: str) -> bool:
    """Exclude tagged releases whose APJs predate git_identity metadata."""
    first = _FIRST_IDENTIFIED_RELEASE.get(vehicle_type)
    match = re.match(r"^(\d+)\.(\d+)(?:\.(\d+))?(?!\d)", version)
    if first is None or match is None:
        return True
    version_numbers = tuple(int(part or 0) for part in match.groups())
    return version_numbers >= first


@dataclass(frozen=True)
class FirmwareRelease:
    """An official APJ descriptor bound to a board ID and HTTPS URL."""

    vehicle_type: str
    version: str
    channel: str
    platform: str
    url: str
    board_id: int
    git_sha: str = ""

    @property
    def firmware_type_label(self) -> str:
        """Distinguish helicopter and multicopter builds within the Copter family."""
        if self.vehicle_type != "Copter":
            return self.vehicle_type
        filename = urlparse(self.url).path.rsplit("/", maxsplit=1)[-1]
        return _("Copter - heli") if filename.endswith("-heli.apj") else _("Copter - multicopter")

    @property
    def label(self) -> str:
        """Disambiguate releases and board variants in the version selector."""
        release_dir = self.url.rstrip("/").split("/")[-3]
        filename = self.url.rsplit("/", maxsplit=1)[-1]
        return f"{self.version} ({self.channel}, {release_dir}) — {self.platform} / {filename}"


def firmware_types(releases: Sequence[FirmwareRelease]) -> list[str]:
    """Return distinct firmware types, keeping helicopter and multicopter builds separate."""
    return sorted({release.firmware_type_label for release in releases})


def firmware_targets(releases: Sequence[FirmwareRelease], firmware_type: str) -> list[str]:
    """Return distinct targets for the selected firmware type."""
    return sorted({release.platform for release in releases if release.firmware_type_label == firmware_type})


def firmware_versions(releases: Sequence[FirmwareRelease], firmware_type: str, target: str) -> list[str]:
    """Return version labels for the selected type and target in catalog order."""
    return [
        release.label for release in releases if release.firmware_type_label == firmware_type and release.platform == target
    ]


def preferred_catalog_choice(choices: Sequence[str], preferred: str) -> str:
    """Keep a matching board preference, otherwise use the first available choice."""
    return preferred if preferred in choices else choices[0] if choices else ""


def preferred_board_target(targets: Sequence[str], detected_target: str) -> str:
    """Select a target only when it matches the detected board or is unambiguous."""
    if detected_target in targets:
        return detected_target
    return targets[0] if len(targets) == 1 else ""


def preferred_firmware_type(types: Sequence[str], current_vehicle_type: str) -> str:
    """Prefer the currently installed vehicle type, including its Copter variant."""
    preferred = {"Copter": _("Copter - multicopter"), "Heli": _("Copter - heli")}.get(
        current_vehicle_type, current_vehicle_type
    )
    return preferred_catalog_choice(types, preferred)


def find_firmware_release(
    releases: Sequence[FirmwareRelease], firmware_type: str, target: str, version_label: str
) -> FirmwareRelease | None:
    """Resolve a version label only within the selected firmware type and target."""
    return next(
        (
            release
            for release in releases
            if release.firmware_type_label == firmware_type and release.platform == target and release.label == version_label
        ),
        None,
    )


def releases_for_board(manifest: dict, board_id: int) -> list[FirmwareRelease]:
    """Return every valid official APJ release matching the connected board ID."""
    releases: list[FirmwareRelease] = []
    seen_urls: set[str] = set()
    entries = manifest.get("firmware", [])
    if not isinstance(entries, list):
        msg = _("Invalid ArduPilot firmware manifest")
        raise ValueError(msg)
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("format") != "apj":
            continue
        try:
            entry_board_id = int(entry["board_id"])
        except (KeyError, TypeError, ValueError):
            continue
        if entry_board_id != board_id:
            continue
        url = entry.get("url")
        if not isinstance(url, str):
            continue
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != "firmware.ardupilot.org" or not parsed.path.endswith(".apj"):
            continue
        if url in seen_urls:
            continue
        vehicle_type = entry.get("vehicletype")
        platform = entry.get("platform")
        if not isinstance(vehicle_type, str) or not isinstance(platform, str):
            continue
        version = str(entry.get("mav-firmware-version", entry.get("mav-firmware-version-str", "Unknown")))
        if not _has_verifiable_identity(vehicle_type, version):
            continue
        seen_urls.add(url)
        releases.append(
            FirmwareRelease(
                vehicle_type=vehicle_type,
                version=version,
                channel=str(entry.get("mav-firmware-version-type", "unknown")),
                platform=platform,
                url=url,
                board_id=entry_board_id,
                git_sha=str(entry.get("git-sha") or ""),
            )
        )

    def sort_key(release: FirmwareRelease) -> tuple[str, int, int, int, str, str, str]:
        match = re.match(r"^(\d+)\.(\d+)(?:\.(\d+))?", release.version)
        major, minor, patch = (int(value or 0) for value in match.groups()) if match else (-1, -1, -1)
        return (release.vehicle_type, major, minor, patch, release.version, release.channel, release.platform)

    return sorted(releases, key=sort_key)
