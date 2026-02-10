#!/usr/bin/env python3

"""
Integration tests for software update functionality with actual GitHub API calls.

These tests make real network requests to GitHub's API to verify end-to-end functionality.
They are marked with @pytest.mark.integration and should be run separately from unit tests.

Run with: pytest -v -m integration tests/integration_software_update_github_api.py

Note: These tests may fail if:
- GitHub API is down or rate-limited
- Network connectivity issues
- Repository structure changes

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import logging

import pytest
import requests
from packaging.version import Version
from requests import RequestException as requests_RequestException
from requests import Timeout as requests_Timeout

from ardupilot_methodic_configurator.backend_internet import get_expected_sha256_from_release, get_release_info

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


class TestRealGitHubAPIIntegration:
    """Integration tests that make actual GitHub API calls."""

    def test_user_can_fetch_latest_stable_release_from_github(self) -> None:
        """
        User can fetch the latest stable release information from GitHub.

        GIVEN: GitHub API is accessible
          AND: ArduPilot/MethodicConfigurator repository has stable releases
        WHEN: User checks for latest stable release
        THEN: System successfully retrieves release information
          AND: Release is not marked as prerelease
          AND: Release has valid version tag
          AND: Release contains assets
        """
        # Act - Make actual API call to GitHub
        release_info = get_release_info("/latest", should_be_pre_release=False)

        # Assert - Validate response structure
        assert release_info is not None, "Should receive release information"
        assert "tag_name" in release_info, "Release should have a tag_name"
        assert "name" in release_info, "Release should have a name"
        assert "body" in release_info, "Release should have a body (changelog)"
        assert "prerelease" in release_info, "Release should have prerelease flag"
        assert "assets" in release_info, "Release should have assets"

        # Assert - Validate release is stable (not prerelease)
        assert release_info["prerelease"] is False, "Latest release should be stable, not prerelease"

        # Assert - Validate version tag format
        tag = release_info["tag_name"]
        assert tag.startswith("v"), f"Tag should start with 'v': {tag}"

        # Assert - Version is parseable
        version_str = tag.lstrip("v")
        version = Version(version_str)
        assert version is not None, f"Should be able to parse version: {version_str}"

        # Assert - Has at least some assets (installers, wheels, etc.)
        assert len(release_info["assets"]) > 0, "Release should have at least one asset"

    def test_user_can_fetch_specific_release_by_tag(self) -> None:
        """
        User can fetch a specific release by tag name.

        GIVEN: GitHub API is accessible
          AND: A specific version tag exists (e.g., v1.0.0)
        WHEN: User requests release by tag
        THEN: System retrieves the correct release
          AND: Tag matches the requested version
        """
        # Arrange - Use a known stable tag (adjust if needed based on actual releases)
        # For safety, we'll fetch latest first and use that tag
        latest = get_release_info("/latest", should_be_pre_release=False)
        tag = latest["tag_name"]

        # Act - Fetch specific release by tag
        release_info = get_release_info(f"/tags/{tag}", should_be_pre_release=False)

        # Assert
        assert release_info["tag_name"] == tag, f"Should retrieve release with tag {tag}"

    def test_user_can_retrieve_release_assets_information(self) -> None:
        """
        User can retrieve detailed information about release assets.

        GIVEN: Latest release is available
        WHEN: User examines release assets
        THEN: Assets have required metadata (name, download URL, size)
          AND: Assets include expected file types (.exe, .whl, checksums)
        """
        # Act
        release_info = get_release_info("/latest", should_be_pre_release=False)
        assets = release_info["assets"]

        # Assert - Assets have required fields
        for asset in assets:
            assert "name" in asset, "Asset should have a name"
            assert "browser_download_url" in asset, "Asset should have download URL"
            assert "size" in asset, "Asset should have size information"

            # Validate download URL is from GitHub
            download_url = asset["browser_download_url"]
            assert download_url.startswith(("https://github.com/", "https://objects.githubusercontent.com/")), (
                f"Asset URL should be from GitHub: {download_url}"
            )

    def test_system_can_parse_sha256_checksums_from_real_release(self) -> None:
        """
        System can parse SHA256 checksums from actual release assets.

        GIVEN: Latest release has checksum files or checksums in release notes
        WHEN: System attempts to extract checksums
        THEN: Checksums are successfully parsed and delivered
          AND: Checksums are valid 64-character hex strings
        """
        # Act
        release_info = get_release_info("/latest", should_be_pre_release=False)
        assets = release_info.get("assets", [])

        # Find a .exe file to test checksum retrieval
        test_files = [a for a in assets if a["name"].endswith(".exe")]

        # Assert - Should have at least one .exe file in release
        assert test_files, "Release should contain at least one .exe file"

        test_asset = test_files[0]
        checksum = get_expected_sha256_from_release(release_info, test_asset["name"])

        # Assert - Checksum must be delivered
        assert checksum is not None, f"SHA256 checksum must be provided for {test_asset['name']}"
        assert len(checksum) == 64, "SHA256 should be 64 hex characters"
        assert all(c in "0123456789abcdefABCDEF" for c in checksum), "SHA256 should be valid hex"

    def test_github_api_rate_limit_headers_are_present(self) -> None:
        """
        GitHub API responses include rate limit information.

        GIVEN: Making requests to GitHub API
        WHEN: Response is received
        THEN: Rate limit headers should be present
          AND: We can monitor API usage
        """
        # This test verifies that we're hitting the real API by checking for rate limit headers
        url = "https://api.github.com/repos/ArduPilot/MethodicConfigurator/releases/latest"
        response = requests.get(url, timeout=30)

        # Assert - Rate limit headers should be present
        assert "X-RateLimit-Limit" in response.headers, "Should have rate limit header"
        assert "X-RateLimit-Remaining" in response.headers, "Should have remaining limit header"
        assert "X-RateLimit-Reset" in response.headers, "Should have reset time header"

        # Log rate limit info for debugging
        limit = response.headers.get("X-RateLimit-Limit")
        remaining = response.headers.get("X-RateLimit-Remaining")
        logging.info("GitHub API Rate Limit: %s/%s requests remaining", remaining, limit)

    def test_release_has_valid_changelog_information(self) -> None:
        """
        Release contains valid changelog/release notes.

        GIVEN: Latest release exists
        WHEN: User views release information
        THEN: Release body contains meaningful changelog
          AND: Changelog is not empty
        """
        # Act
        release_info = get_release_info("/latest", should_be_pre_release=False)
        body = release_info.get("body", "")

        # Assert
        assert body, "Release should have non-empty body/changelog"
        assert len(body) > 10, "Changelog should have meaningful content"

    @pytest.mark.slow
    def test_can_check_multiple_releases_sequentially(self) -> None:
        """
        System can check multiple releases without errors.

        GIVEN: Multiple releases exist
        WHEN: User checks latest and then specific releases
        THEN: All requests succeed without rate limiting issues
          AND: Each release has valid data
        """
        # Act - Check latest
        latest = get_release_info("/latest", should_be_pre_release=False)
        assert latest is not None

        # Try to get the tag of latest and fetch it again by tag
        tag = latest["tag_name"]
        specific = get_release_info(f"/tags/{tag}", should_be_pre_release=False)

        # Assert
        assert specific["tag_name"] == tag
        assert latest["tag_name"] == specific["tag_name"]


class TestRealGitHubAPIErrorHandling:
    """Integration tests for error handling with actual API calls."""

    def test_graceful_handling_of_nonexistent_release_tag(self) -> None:
        """
        System handles requests for non-existent releases gracefully.

        GIVEN: User requests a release that doesn't exist
        WHEN: API returns 404 error
        THEN: System raises appropriate exception
          AND: Error is logged appropriately
        """
        with pytest.raises(requests_RequestException):
            get_release_info("/tags/v999.999.999-nonexistent", should_be_pre_release=False)

    def test_handles_network_timeout_appropriately(self) -> None:
        """
        System handles network timeouts appropriately.

        GIVEN: Very short timeout configured
        WHEN: API call times out
        THEN: System raises timeout exception
          AND: No data corruption occurs
        """
        # This test uses a very short timeout to force a timeout
        with pytest.raises((requests_Timeout, requests_RequestException)):
            get_release_info("/latest", should_be_pre_release=False, timeout=0.001)


class TestSemanticVersionComparison:  # pylint: disable=too-few-public-methods
    """
    Test semantic version comparison with real release versions.

    This class intentionally has only one test method as it focuses on a single
    specific behavior: semantic version comparison with actual releases.
    """

    def test_version_comparison_with_actual_releases(self) -> None:
        """
        Semantic version comparison works with actual release versions.

        GIVEN: Latest release version from GitHub
        WHEN: Comparing with various version strings
        THEN: Comparisons follow semantic versioning rules
        """
        # Act - Get actual latest version
        release_info = get_release_info("/latest", should_be_pre_release=False)
        latest_version_str = release_info["tag_name"].lstrip("v")
        latest_version = Version(latest_version_str)

        # Assert - Version comparison logic
        # These should all be true for any real version
        assert latest_version > Version("0.0.1"), "Latest should be greater than 0.0.1"
        assert latest_version == Version(latest_version_str), "Version should equal itself when reparsed"

        # Test prerelease handling
        prerelease_version = Version(f"{latest_version_str}-rc1")
        stable_version = Version(latest_version_str)
        assert stable_version > prerelease_version, "Stable version should be greater than prerelease"
