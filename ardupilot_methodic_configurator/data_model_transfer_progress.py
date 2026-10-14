"""
Transfer progress values and estimates, independent of clocks and widgets.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum, auto
from math import ceil


class TransferPhase(Enum):
    """Explicit lifecycle phases; transferring all bytes does not finish a task."""

    TRANSFERRING = auto()
    VERIFYING = auto()
    FINISHED = auto()


class TransferDirection(Enum):
    """The direction used for transfer-specific user-facing labels."""

    DOWNLOAD = auto()
    UPLOAD = auto()


@dataclass(frozen=True)
class TransferProgress:
    """A cumulative snapshot; None means unknown size, zero means an empty file."""

    transferred_bytes: int
    total_bytes: int | None
    phase: TransferPhase = TransferPhase.TRANSFERRING
    direction: TransferDirection = TransferDirection.DOWNLOAD


@dataclass(frozen=True)
class TransferEstimate:
    """Average bytes per second and rounded-up remaining transfer seconds."""

    bytes_per_second: float | None
    remaining_seconds: int | None


@dataclass
class TransferBatchAccounting:
    """Track one batch attempt using supplied counts, without executing transfers."""

    total: int
    unknown_files: int = 0
    transferred: int = 0
    direction: TransferDirection = TransferDirection.DOWNLOAD

    @classmethod
    def from_sizes(
        cls, sizes: Iterable[int], *, direction: TransferDirection = TransferDirection.DOWNLOAD
    ) -> "TransferBatchAccounting":
        """Prepare an attempt from listing estimates; zero upload sizes are known, nonpositive download sizes are unknown."""
        estimates = tuple(sizes)
        return cls(
            sum(max(size, 0) for size in estimates),
            sum(size <= 0 for size in estimates) if direction is TransferDirection.DOWNLOAD else 0,
            direction=direction,
        )

    def snapshot(self, current: int = 0, phase: TransferPhase = TransferPhase.TRANSFERRING) -> TransferProgress:
        """Withhold the total until every remaining file has a size estimate."""
        return TransferProgress(
            self.transferred + current, self.total if self.unknown_files == 0 else None, phase, self.direction
        )

    def start_file(self, listed_size: int) -> "TransferFileAccounting":
        """Create counters for the next file from its directory listing estimate."""
        return TransferFileAccounting(self, max(listed_size, 0), listed_size > 0 or self.direction is TransferDirection.UPLOAD)


@dataclass
class TransferFileAccounting:
    """Reconcile listing estimates with transferred bytes for one file."""

    batch: TransferBatchAccounting
    expected: int
    size_known: bool
    transferred: int = 0

    def update(self, current: int, maximum: int) -> TransferProgress:
        """Use authoritative sizes and ignore regressing byte counters."""
        self.transferred = max(self.transferred, current, 0)
        size_known = maximum > 0 or self.batch.direction is TransferDirection.UPLOAD
        if self.size_known != size_known:
            self.batch.unknown_files += 1 if self.size_known else -1
            self.size_known = size_known
        if size_known:
            actual_total = max(maximum, self.transferred)
            self.batch.total += actual_total - self.expected
            self.expected = actual_total
        return self.batch.snapshot(self.transferred)

    def finish(self) -> TransferProgress:
        """Retain transferred bytes and remove work skipped or failed this attempt."""
        self.batch.total += self.transferred - self.expected
        self.batch.transferred += self.transferred
        if not self.size_known:
            self.batch.unknown_files -= 1
        return self.batch.snapshot()


def estimate_transfer(progress: TransferProgress, elapsed_seconds: float) -> TransferEstimate:
    """Estimate from supplied values, including idle time, without reading a clock."""
    if progress.phase is not TransferPhase.TRANSFERRING or elapsed_seconds < 1.0 or progress.transferred_bytes <= 0:
        return TransferEstimate(None, None)
    rate = progress.transferred_bytes / elapsed_seconds
    remaining = (
        ceil(max(0, progress.total_bytes - progress.transferred_bytes) / rate) if progress.total_bytes is not None else None
    )
    return TransferEstimate(rate, remaining)
