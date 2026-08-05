#!/usr/bin/env python3

"""
Tests for the log_analysis/backend_firmware_version.py file.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.log_analysis.backend_firmware_version import extract_firmware_version_and_vehicle_type

FIXTURE_LOG = Path(__file__).resolve().parent / "fixtures" / "backend_log_80k.bin"


class TestExtractFirmwareVersionAndVehicleType:
    """BDD tests for extract_firmware_version_and_vehicle_type."""

    def _make_mlog(self, messages: list) -> MagicMock:
        """Build a mock mavlink connection that yields the given messages then None."""
        mlog = MagicMock()
        mlog.recv_match.side_effect = [*messages, None]
        return mlog

    def _make_ver_msg(self, fws: str, maj: int, min_: int, pat: int) -> MagicMock:
        msg = MagicMock()
        msg.get_type.return_value = "VER"
        msg.FWS = fws
        msg.Maj = maj
        msg.Min = min_
        msg.Pat = pat
        return msg

    def _make_msg_msg(self, text: str) -> MagicMock:
        msg = MagicMock()
        msg.get_type.return_value = "MSG"
        msg.Message = text
        return msg

    @patch("ardupilot_methodic_configurator.log_analysis.backend_log_extraction.mavutil.mavlink_connection")
    def test_ver_message_returns_full_four_tuple(self, mock_conn: MagicMock) -> None:
        """
        VER message produces a complete (vehicle_type, major, minor, patch) 4-tuple.

        GIVEN: A .bin log whose first relevant message is a VER record for ArduCopter 4.6.3
        WHEN: extract_firmware_version_and_vehicle_type is called
        THEN: Returns ("ArduCopter", 4, 6, 3) with all four components correct
        """
        ver = self._make_ver_msg("ArduCopter V4.6.3 (3fc7011a)", 4, 6, 3)
        mock_conn.return_value = self._make_mlog([ver])

        result = extract_firmware_version_and_vehicle_type("flight.bin")

        assert result == ("ArduCopter", 4, 6, 3)
        vehicle_type, major, minor, patchv = result
        assert vehicle_type == "ArduCopter"
        assert major == 4
        assert minor == 6
        assert patchv == 3

    @patch("ardupilot_methodic_configurator.log_analysis.backend_log_extraction.mavutil.mavlink_connection")
    def test_ver_message_extracts_correct_vehicle_type_from_fws_field(self, mock_conn: MagicMock) -> None:
        """
        Vehicle type comes from the first word of the FWS field, not from a separate field.

        GIVEN: A VER message where FWS is "ArduPlane V4.5.1 (abcdef01)"
        WHEN: extract_firmware_version_and_vehicle_type is called
        THEN: vehicle_type is "ArduPlane" and version components are (4, 5, 1)
        """
        ver = self._make_ver_msg("ArduPlane V4.5.1 (abcdef01)", 4, 5, 1)
        mock_conn.return_value = self._make_mlog([ver])

        vehicle_type, major, minor, patchv = extract_firmware_version_and_vehicle_type("log.bin")

        assert vehicle_type == "ArduPlane"
        assert major == 4
        assert minor == 5
        assert patchv == 1

    @patch("ardupilot_methodic_configurator.log_analysis.backend_log_extraction.mavutil.mavlink_connection")
    def test_ver_message_with_patch_zero(self, mock_conn: MagicMock) -> None:
        """
        VER message with Pat=0 correctly returns patch=0 rather than a default or absent value.

        GIVEN: A VER message where Pat field is 0
        WHEN: extract_firmware_version_and_vehicle_type is called
        THEN: The returned patch component is exactly 0
        """
        ver = self._make_ver_msg("Rover V4.4.0 (deadbeef)", 4, 4, 0)
        mock_conn.return_value = self._make_mlog([ver])

        vehicle_type, major, minor, patchv = extract_firmware_version_and_vehicle_type("log.bin")

        assert vehicle_type == "Rover"
        assert major == 4
        assert minor == 4
        assert patchv == 0

    @patch("ardupilot_methodic_configurator.log_analysis.backend_log_extraction.mavutil.mavlink_connection")
    def test_ver_message_takes_priority_over_msg_message(self, mock_conn: MagicMock) -> None:
        """
        VER message is preferred and MSG fallback is ignored when VER is present.

        GIVEN: A log containing a MSG message followed by a VER message
        WHEN: extract_firmware_version_and_vehicle_type is called
        THEN: Data comes from VER, not MSG; the MSG data is completely ignored
        """
        msg_first = self._make_msg_msg("ArduPlane V3.9.9 (stale-hash)")
        ver_second = self._make_ver_msg("ArduCopter V4.6.3 (correct)", 4, 6, 3)
        mock_conn.return_value = self._make_mlog([msg_first, ver_second])

        vehicle_type, major, minor, patchv = extract_firmware_version_and_vehicle_type("log.bin")

        assert vehicle_type == "ArduCopter"
        assert major == 4
        assert minor == 6
        assert patchv == 3

    @patch("ardupilot_methodic_configurator.log_analysis.backend_log_extraction.mavutil.mavlink_connection")
    def test_msg_fallback_used_when_no_ver_message(self, mock_conn: MagicMock) -> None:
        """
        MSG message is used as fallback when VER message is absent.

        GIVEN: A .bin log that contains only a MSG record for ArduCopter V4.6.3
        WHEN: extract_firmware_version_and_vehicle_type is called
        THEN: Returns ("ArduCopter", 4, 6, 3) parsed from the MSG text
        """
        msg = self._make_msg_msg("ArduCopter V4.6.3 (3fc7011a)")
        mock_conn.return_value = self._make_mlog([msg])

        vehicle_type, major, minor, patchv = extract_firmware_version_and_vehicle_type("log.bin")

        assert vehicle_type == "ArduCopter"
        assert major == 4
        assert minor == 6
        assert patchv == 3

    @patch("ardupilot_methodic_configurator.log_analysis.backend_log_extraction.mavutil.mavlink_connection")
    def test_msg_fallback_without_patch_defaults_to_zero(self, mock_conn: MagicMock) -> None:
        """
        MSG fallback with only major.minor (no patch) returns patch=0.

        GIVEN: A MSG record that reads "ArduCopter V4.6 (hash)" (no patch component)
        WHEN: extract_firmware_version_and_vehicle_type is called
        THEN: Returns ("ArduCopter", 4, 6, 0) with patch defaulted to 0
        """
        msg = self._make_msg_msg("ArduCopter V4.6 (3fc7011a)")
        mock_conn.return_value = self._make_mlog([msg])

        vehicle_type, major, minor, patchv = extract_firmware_version_and_vehicle_type("log.bin")

        assert vehicle_type == "ArduCopter"
        assert major == 4
        assert minor == 6
        assert patchv == 0

    @patch("ardupilot_methodic_configurator.log_analysis.backend_log_extraction.mavutil.mavlink_connection")
    def test_first_parseable_msg_message_is_used_as_fallback(self, mock_conn: MagicMock) -> None:
        """
        The first MSG record with a parseable Vx.y version is used; unparsable ones are skipped.

        GIVEN: Two MSG messages - first is a boot log line without a version, second is ArduCopter 4.6.3
        WHEN: extract_firmware_version_and_vehicle_type is called
        THEN: Data is from the second (parseable) MSG message
        """
        msg1 = self._make_msg_msg("Boot started")
        msg2 = self._make_msg_msg("ArduCopter V4.6.3 (abcdef12)")
        mock_conn.return_value = self._make_mlog([msg1, msg2])

        vehicle_type, _major, _minor, patchv = extract_firmware_version_and_vehicle_type("log.bin")

        assert vehicle_type == "ArduCopter"
        assert patchv == 3

    @patch("ardupilot_methodic_configurator.log_analysis.backend_log_extraction.mavutil.mavlink_connection")
    def test_msg_fallback_works_when_ver_fields_are_invalid(self, mock_conn: MagicMock) -> None:
        """
        Invalid VER numeric fields do not abort extraction; parser falls back to parseable MSG text.

        GIVEN: A VER message with non-numeric Maj followed by a valid MSG version line
        WHEN: extract_firmware_version_and_vehicle_type is called
        THEN: Data is extracted from MSG fallback instead of raising
        """
        bad_ver = self._make_ver_msg("ArduCopter V4.6.3 (3fc7011a)", 4, 6, 3)
        bad_ver.Maj = "not-a-number"
        msg = self._make_msg_msg("ArduCopter V4.6.3 (3fc7011a)")
        mock_conn.return_value = self._make_mlog([bad_ver, msg])

        assert extract_firmware_version_and_vehicle_type("log.bin") == ("ArduCopter", 4, 6, 3)

    @patch("ardupilot_methodic_configurator.log_analysis.backend_log_extraction.mavutil.mavlink_connection")
    def test_msg_fallback_accepts_version_without_hash_suffix(self, mock_conn: MagicMock) -> None:
        """
        MSG fallback accepts firmware strings without the optional hash suffix.

        GIVEN: A MSG line formatted as "ArduCopter V4.6.3" (no "(hash)")
        WHEN: extract_firmware_version_and_vehicle_type is called
        THEN: Version components are still extracted
        """
        msg = self._make_msg_msg("ArduCopter V4.6.3")
        mock_conn.return_value = self._make_mlog([msg])

        assert extract_firmware_version_and_vehicle_type("log.bin") == ("ArduCopter", 4, 6, 3)

    @patch("ardupilot_methodic_configurator.log_analysis.backend_log_extraction.mavutil.mavlink_connection")
    def test_raises_os_error_when_logfile_cannot_be_opened(self, mock_conn: MagicMock) -> None:
        """
        An OSError is raised with an informative message when the logfile cannot be opened.

        GIVEN: A logfile path that causes mavlink_connection to raise an exception
        WHEN: extract_firmware_version_and_vehicle_type is called
        THEN: OSError is raised with a message mentioning the logfile path
        """
        mock_conn.side_effect = OSError("file not found")

        with pytest.raises(OSError, match="Error opening") as exc_info:
            extract_firmware_version_and_vehicle_type("missing.bin")

        assert "missing.bin" in str(exc_info.value)
        assert "Error opening" in str(exc_info.value)

    @patch("ardupilot_methodic_configurator.log_analysis.backend_log_extraction.mavutil.mavlink_connection")
    def test_raises_value_error_when_no_version_information_found(self, mock_conn: MagicMock) -> None:
        """
        A ValueError is raised when neither VER nor parseable MSG is found.

        GIVEN: A .bin log that contains no VER or MSG messages
        WHEN: extract_firmware_version_and_vehicle_type is called
        THEN: ValueError is raised with a message mentioning the logfile and "No firmware version"
        """
        mock_conn.return_value = self._make_mlog([])  # No messages at all

        with pytest.raises(ValueError, match="No firmware version") as exc_info:
            extract_firmware_version_and_vehicle_type("empty.bin")

        assert "empty.bin" in str(exc_info.value)
        assert "No firmware version" in str(exc_info.value)

    @patch("ardupilot_methodic_configurator.log_analysis.backend_log_extraction.mavutil.mavlink_connection")
    def test_raises_value_error_when_msg_version_format_is_unparseable(self, mock_conn: MagicMock) -> None:
        """
        A ValueError is raised when the MSG version string cannot be parsed.

        GIVEN: A MSG record whose text contains no recognisable "Vx.y" pattern
        WHEN: extract_firmware_version_and_vehicle_type is called
        THEN: ValueError is raised
        """
        msg = self._make_msg_msg("Boot started")
        mock_conn.return_value = self._make_mlog([msg])

        with pytest.raises(ValueError, match="No firmware version") as exc_info:
            extract_firmware_version_and_vehicle_type("bad.bin")

        assert "bad.bin" in str(exc_info.value)
        assert "No firmware version" in str(exc_info.value)

    @patch("ardupilot_methodic_configurator.log_analysis.backend_log_extraction.mavutil.mavlink_connection")
    def test_return_type_is_tuple_of_str_int_int_int(self, mock_conn: MagicMock) -> None:
        """
        The return value has the correct types for all four components.

        GIVEN: A valid VER message
        WHEN: extract_firmware_version_and_vehicle_type is called
        THEN: Returns a 4-tuple of (str, int, int, int) — not floats or strings for version numbers
        """
        ver = self._make_ver_msg("Heli V4.5.2 (cafebabe)", 4, 5, 2)
        mock_conn.return_value = self._make_mlog([ver])

        result = extract_firmware_version_and_vehicle_type("log.bin")

        assert isinstance(result, tuple)
        assert len(result) == 4
        vehicle_type, major, minor, patchv = result
        assert isinstance(vehicle_type, str)
        assert isinstance(major, int)
        assert isinstance(minor, int)
        assert isinstance(patchv, int)


@pytest.mark.integration
class TestExtractFirmwareVersionAndVehicleTypeIntegration:  # pylint: disable=too-few-public-methods
    """Integration tests for extract_firmware_version_and_vehicle_type."""

    def test_extracts_version_from_real_log_fixture(self) -> None:
        """GIVEN a real log fixture, WHEN firmware is extracted, THEN the expected tuple is returned."""
        assert extract_firmware_version_and_vehicle_type(str(FIXTURE_LOG)) == ("ArduCopter", 4, 6, 2)
