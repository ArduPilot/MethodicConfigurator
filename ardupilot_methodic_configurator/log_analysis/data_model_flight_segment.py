"""
Reusable time scope for one operational flight within an ArduPilot log.

SPDX-FileCopyrightText: 2026 Donald Smith

SPDX-License-Identifier: GPL-3.0-or-later
"""

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FlightSegment:
    """Inclusive canonical-second bounds for one operational flight."""

    start_s: float
    end_s: float
    is_complete: bool

    def __post_init__(self) -> None:
        """Reject bounds that cannot define a usable time scope."""
        if not math.isfinite(self.start_s) or not math.isfinite(self.end_s):
            msg = "Flight segment bounds must be finite"
            raise ValueError(msg)
        if self.start_s > self.end_s:
            msg = "Flight segment start_s must not be after end_s"
            raise ValueError(msg)

    @property
    def duration_s(self) -> float:
        """Return the segment duration in seconds."""
        return self.end_s - self.start_s

    def contains(self, start_s: float, end_s: float) -> bool:
        """Return whether inclusive child bounds are valid and contained by this segment."""
        return self.start_s <= start_s <= end_s <= self.end_s


@dataclass(frozen=True, slots=True)
class FlightSegmentationResult:
    """Internal result that distinguishes unavailable evidence from no detected flights."""

    available: bool
    segments: tuple[FlightSegment, ...] = ()
    reason: str | None = None

    def __post_init__(self) -> None:
        """Reject contradictory availability, segment, and reason states."""
        if self.available and self.reason is not None:
            msg = "Available flight segmentation must not have an unavailable reason"
            raise ValueError(msg)
        if not self.available and self.segments:
            msg = "Unavailable flight segmentation must not contain segments"
            raise ValueError(msg)
        if not self.available and not self.reason:
            msg = "Unavailable flight segmentation requires a non-empty reason"
            raise ValueError(msg)
