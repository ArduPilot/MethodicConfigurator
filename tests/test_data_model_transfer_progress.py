#!/usr/bin/env python3

"""
Pure transfer estimate tests; no clock, transport, or Tk widgets are needed.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import pytest

from ardupilot_methodic_configurator.data_model_transfer_progress import (
    TransferBatchAccounting,
    TransferDirection,
    TransferPhase,
    TransferProgress,
    estimate_transfer,
)


@pytest.mark.parametrize("elapsed", [-1, 0, 0.5])
def test_user_gets_no_estimate_before_enough_time_has_elapsed(elapsed: float) -> None:
    """Given a just-started download, avoid unstable speed and ETA values."""
    estimate = estimate_transfer(TransferProgress(1024, 4096), elapsed)
    assert estimate.bytes_per_second is None
    assert estimate.remaining_seconds is None


def test_user_gets_no_estimate_before_any_bytes_arrive() -> None:
    """Given an idle connection, avoid division by zero or an invented ETA."""
    assert estimate_transfer(TransferProgress(0, 4096), 2).bytes_per_second is None


def test_user_gets_a_lower_average_rate_and_longer_eta_during_a_stall() -> None:
    """Given unchanged byte counts, increasing elapsed time still changes the estimate."""
    progress = TransferProgress(1024 * 1024, 4 * 1024 * 1024)
    active = estimate_transfer(progress, 2)
    stalled = estimate_transfer(progress, 122)
    assert active.bytes_per_second == 512 * 1024
    assert active.remaining_seconds == 6
    assert stalled.bytes_per_second == pytest.approx(1024 * 1024 / 122)
    assert stalled.remaining_seconds == 366


def test_user_gets_a_cumulative_estimate_across_file_boundaries() -> None:
    """Given bytes from two files, average the entire attempt rather than reset at a boundary."""
    estimate = estimate_transfer(TransferProgress(1536 * 1024, 4 * 1024 * 1024), 4)
    assert estimate.bytes_per_second == 384 * 1024
    assert estimate.remaining_seconds == 7


def test_user_gets_a_rate_without_an_eta_for_unknown_size() -> None:
    """Given an unknown size, bytes and elapsed time still determine throughput."""
    estimate = estimate_transfer(TransferProgress(2048, None), 2)
    assert estimate.bytes_per_second == 1024
    assert estimate.remaining_seconds is None


@pytest.mark.parametrize("phase", [TransferPhase.VERIFYING, TransferPhase.FINISHED])
@pytest.mark.parametrize("size", [0, 1024])
def test_user_gets_no_download_estimate_during_later_phases(phase: TransferPhase, size: int) -> None:
    """Given an explicit later phase, verification time never enters throughput or ETA."""
    estimate = estimate_transfer(TransferProgress(size, size, phase), 100)
    assert estimate.bytes_per_second is None
    assert estimate.remaining_seconds is None


def test_user_gets_a_rounded_up_nonnegative_remaining_duration() -> None:
    """Given fractional or completed remaining work, avoid early or negative estimates."""
    assert estimate_transfer(TransferProgress(3, 5), 2).remaining_seconds == 2
    assert estimate_transfer(TransferProgress(5, 3), 2).remaining_seconds == 0


def test_user_keeps_transferred_bytes_when_a_file_fails_after_the_listing_size_changes() -> None:
    """Given a stale listing and partial failure, retain actual bytes and pending files."""
    batch = TransferBatchAccounting.from_sizes([100, 300])
    first = batch.start_file(100)
    assert first.update(50, 200) == TransferProgress(50, 500)
    assert first.update(20, 200) == TransferProgress(50, 500)
    assert first.finish() == TransferProgress(50, 350)
    second = batch.start_file(300)
    assert second.update(300, 300) == TransferProgress(350, 350)
    assert second.finish() == TransferProgress(350, 350)


def test_user_gets_a_known_total_after_unknown_empty_and_skipped_files_are_finished() -> None:
    """Given unknown sizes, resolve the total from completed work without invented bytes."""
    batch = TransferBatchAccounting.from_sizes([0, 0, 100])
    generated = batch.start_file(0)
    assert generated.update(200, 0) == TransferProgress(200, None)
    assert generated.update(200, 200) == TransferProgress(200, None)
    assert generated.finish() == TransferProgress(200, None)
    empty = batch.start_file(0)
    assert empty.update(0, 0) == TransferProgress(200, None)
    assert empty.finish() == TransferProgress(200, 300)
    assert batch.start_file(100).finish() == TransferProgress(200, 200)


def test_upload_batch_counts_only_acknowledged_bytes_and_resolves_empty_files() -> None:
    """Given a partial failure and an empty upload, retain actual bytes without inventing progress."""
    batch = TransferBatchAccounting.from_sizes([240, 0, 100], direction=TransferDirection.UPLOAD)
    assert batch.snapshot().total_bytes == 340
    first = batch.start_file(240)
    assert first.update(239, 240).transferred_bytes == 239
    first.update(0, 0)  # Cleanup cannot regress acknowledged bytes.
    first.finish()
    assert batch.start_file(0).finish().total_bytes == 339
    second = batch.start_file(100)
    second.update(50, 100)
    progress = second.finish()
    assert progress == TransferProgress(289, 289, direction=TransferDirection.UPLOAD)
    assert estimate_transfer(progress, 2).bytes_per_second == 144.5


def test_user_gets_an_estimate_after_one_byte_and_exactly_one_second() -> None:
    """
    Throughput and ETA become available at the first supported time boundary.

    GIVEN: One byte transferred out of a two-byte file
    WHEN: Exactly one second has elapsed
    THEN: Throughput is one byte per second and one second remains.
    """
    estimate = estimate_transfer(TransferProgress(1, 2), 1)
    assert estimate.bytes_per_second == 1
    assert estimate.remaining_seconds == 1


def test_user_gets_a_known_total_for_a_one_byte_download() -> None:
    """
    A one-byte download has a known size throughout its lifecycle.

    GIVEN: A directory listing containing a one-byte file
    WHEN: The file starts, reports its size, and finishes
    THEN: Its total remains one byte and the acknowledged byte is retained.
    """
    batch = TransferBatchAccounting.from_sizes([1])
    assert batch.snapshot() == TransferProgress(0, 1)
    file = batch.start_file(1)
    assert file.update(1, 1) == TransferProgress(1, 1)
    assert file.finish() == TransferProgress(1, 1)


def test_user_gets_no_total_while_a_previously_known_file_size_is_unavailable() -> None:
    """
    A missing authoritative size temporarily hides the batch total.

    GIVEN: Two downloads with known listing sizes
    WHEN: The first loses its size information and later reports it again
    THEN: The total is hidden until resolved and partial completion retains pending work.
    """
    batch = TransferBatchAccounting.from_sizes([100, 300])
    file = batch.start_file(100)
    assert file.update(20, 0) == TransferProgress(20, None)
    assert file.update(30, 100) == TransferProgress(30, 400)
    assert file.finish() == TransferProgress(30, 330)
