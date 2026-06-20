#!/usr/bin/env python3

"""
Unit tests for the manual override feature.

These tests exercise fine-grained behaviour of ArduPilotParameter that is not
covered by the acceptance and integration test suites:

- MANUAL_OVERRIDE_PREFIX constant value and format contract
- change_reason_for_file for every combination of override state / reason content
- _manual_override_on_file baseline tracking across save cycles
- Disable-then-re-enable when the file already carried @manual_override
- Post-save restore: re-enable after save restores the *saved* values
- set_manual_override raises for both True and False on non-forced/non-derived params
- is_editable never True for read-only params regardless of override flag
- change_reason_for_file returns plain change_reason for regular (non-forced) params

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from typing import Any

import pytest

from ardupilot_methodic_configurator.data_model_ardupilot_parameter import ArduPilotParameter
from ardupilot_methodic_configurator.data_model_par_dict import MANUAL_OVERRIDE_PREFIX, Par

# pylint: disable=redefined-outer-name

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def meta() -> dict[str, Any]:
    """Minimal metadata with range constraints for unit tests."""
    return {
        "doc_tooltip": "Unit test parameter",
        "unit": "rpm",
        "unit_tooltip": "Revolutions per minute",
        "min": 0.0,
        "max": 1000.0,
        "Calibration": False,
        "ReadOnly": False,
    }


@pytest.fixture
def ro_meta() -> dict[str, Any]:
    """Read-only variant of the metadata fixture."""
    return {
        "doc_tooltip": "Read-only unit test parameter",
        "unit": "",
        "unit_tooltip": "",
        "min": 0.0,
        "max": 1000.0,
        "Calibration": False,
        "ReadOnly": True,
    }


@pytest.fixture
def forced_clean(meta: dict[str, Any]) -> ArduPilotParameter:
    """Forced param whose file value and reason already match the forced definition (starts clean)."""
    return ArduPilotParameter(
        name="FORCED_CLEAN",
        par_obj=Par(55.0, "forced reason"),
        metadata=meta,
        forced_par=Par(55.0, "forced reason"),
    )


@pytest.fixture
def forced_dirty(meta: dict[str, Any]) -> ArduPilotParameter:
    """Forced param whose file value differs from the forced definition (starts dirty)."""
    return ArduPilotParameter(
        name="FORCED_DIRTY",
        par_obj=Par(10.0, "old file reason"),
        metadata=meta,
        forced_par=Par(55.0, "forced reason"),
    )


@pytest.fixture
def forced_with_file_override(meta: dict[str, Any]) -> ArduPilotParameter:
    """Forced param loaded from a file that already carries @manual_override."""
    return ArduPilotParameter(
        name="FORCED_OVERRIDE",
        par_obj=Par(7.0, "@manual_override Saved user reason"),
        metadata=meta,
        forced_par=Par(55.0, "forced reason"),
    )


@pytest.fixture
def derived_clean(meta: dict[str, Any]) -> ArduPilotParameter:
    """Derived param whose file value and reason already match the derived definition."""
    return ArduPilotParameter(
        name="DERIVED_CLEAN",
        par_obj=Par(20.0, "derived reason"),
        metadata=meta,
        derived_par=Par(20.0, "derived reason"),
    )


@pytest.fixture
def regular(meta: dict[str, Any]) -> ArduPilotParameter:
    """Regular (non-forced, non-derived) param."""
    return ArduPilotParameter(
        name="REGULAR",
        par_obj=Par(3.0, "just a reason"),
        metadata=meta,
    )


# ===========================================================================
# MANUAL_OVERRIDE_PREFIX constant
# ===========================================================================


class TestManualOverridePrefixConstant:
    """The MANUAL_OVERRIDE_PREFIX constant satisfies the storage format contract."""

    def test_prefix_value_is_exact_literal(self) -> None:
        """
        MANUAL_OVERRIDE_PREFIX equals the exact string '@manual_override'.

        GIVEN: The constant is imported
        WHEN: Its value is compared
        THEN: It equals '@manual_override' exactly (ASCII, no leading/trailing whitespace)
        """
        assert MANUAL_OVERRIDE_PREFIX == "@manual_override"

    def test_prefix_starts_with_at_sign(self) -> None:
        """
        Prefix begins with '@' so it cannot be a valid human-entered reason by accident.

        GIVEN: MANUAL_OVERRIDE_PREFIX
        WHEN: Its first character is inspected
        THEN: It is '@'
        """
        assert MANUAL_OVERRIDE_PREFIX[0] == "@"

    def test_prefix_is_lowercase(self) -> None:
        """
        Prefix uses lowercase only, ensuring case-sensitive detection works deterministically.

        GIVEN: MANUAL_OVERRIDE_PREFIX
        WHEN: It is compared to its lowercased form
        THEN: They are identical
        """
        assert MANUAL_OVERRIDE_PREFIX.lower() == MANUAL_OVERRIDE_PREFIX

    def test_prefix_contains_no_whitespace(self) -> None:
        """
        Prefix itself contains no internal whitespace; only a separator space follows it.

        GIVEN: MANUAL_OVERRIDE_PREFIX
        WHEN: It is stripped
        THEN: The result is unchanged
        """
        assert MANUAL_OVERRIDE_PREFIX.strip() == MANUAL_OVERRIDE_PREFIX


# ===========================================================================
# change_reason_for_file property
# ===========================================================================


class TestChangeReasonForFile:
    """change_reason_for_file produces the correct string for every scenario."""

    def test_inactive_override_returns_plain_change_reason(self, forced_dirty: ArduPilotParameter) -> None:
        """
        change_reason_for_file returns the raw change_reason when override is inactive.

        GIVEN: A forced parameter with override NOT active
        WHEN: change_reason_for_file is read
        THEN: It equals change_reason with no prefix
        """
        assert not forced_dirty.is_manual_override
        assert not forced_dirty.change_reason_for_file.startswith(MANUAL_OVERRIDE_PREFIX)
        assert forced_dirty.change_reason_for_file == forced_dirty.change_reason

    def test_active_override_with_non_empty_reason_prepends_prefix_and_space(self, forced_dirty: ArduPilotParameter) -> None:
        """
        change_reason_for_file is '@manual_override <reason>' when override active and reason non-empty.

        GIVEN: A forced parameter with override active and a non-empty reason
        WHEN: change_reason_for_file is read
        THEN: It equals '@manual_override <reason>'
        """
        forced_dirty.set_manual_override(True)
        forced_dirty.set_change_reason("Intentional value")

        result = forced_dirty.change_reason_for_file

        assert result == f"{MANUAL_OVERRIDE_PREFIX} Intentional value"

    def test_active_override_with_empty_reason_returns_prefix_only(self, forced_dirty: ArduPilotParameter) -> None:
        """
        change_reason_for_file returns exactly '@manual_override' when reason is empty.

        GIVEN: A forced parameter with override active and empty change reason
        WHEN: change_reason_for_file is read
        THEN: It equals '@manual_override' with no trailing space
        """
        forced_dirty.set_manual_override(True)
        forced_dirty._change_reason = ""  # pylint: disable=protected-access  # set_change_reason rejects no-op

        result = forced_dirty.change_reason_for_file

        assert result == MANUAL_OVERRIDE_PREFIX
        assert not result.endswith(" ")

    def test_active_override_with_reason_containing_spaces_is_not_stripped(self, forced_dirty: ArduPilotParameter) -> None:
        """
        Trailing spaces in the reason are preserved in the stored comment.

        GIVEN: A forced parameter with override active and a reason that ends with a space
        WHEN: change_reason_for_file is read
        THEN: The trailing space in the reason is preserved (no silent rstrip)

        This ensures that the stored comment round-trips correctly: loading the comment
        back strips the prefix and lstrips the separator space, leaving the exact reason
        including any trailing spaces the user typed.
        """
        forced_dirty.set_manual_override(True)
        forced_dirty.set_change_reason("trailing space ")  # set_change_reason stores as-is

        result = forced_dirty.change_reason_for_file

        assert result == f"{MANUAL_OVERRIDE_PREFIX} trailing space "

    def test_regular_param_change_reason_for_file_returns_plain_reason(self, regular: ArduPilotParameter) -> None:
        """
        change_reason_for_file on a regular (non-forced/non-derived) param returns plain change_reason.

        GIVEN: A regular parameter with override inactive
        WHEN: change_reason_for_file is read
        THEN: The result equals change_reason (the plain comment, no prefix)
        """
        assert not regular.is_manual_override
        assert regular.change_reason_for_file == regular.change_reason
        assert not regular.change_reason_for_file.startswith(MANUAL_OVERRIDE_PREFIX)

    def test_derived_param_inactive_override_returns_plain_derived_reason(self, derived_clean: ArduPilotParameter) -> None:
        """
        change_reason_for_file on a derived param (override inactive) returns the derived reason.

        GIVEN: A derived parameter with no active override
        WHEN: change_reason_for_file is read
        THEN: It returns the derived change reason with no prefix
        """
        assert not derived_clean.is_manual_override
        assert not derived_clean.change_reason_for_file.startswith(MANUAL_OVERRIDE_PREFIX)

    def test_change_reason_display_never_contains_prefix_when_override_active(self, forced_dirty: ArduPilotParameter) -> None:
        """
        The change_reason property (used by the GUI) never exposes the @manual_override prefix.

        GIVEN: A forced parameter with override active and a typed reason
        WHEN: change_reason is read (the display/UI property)
        THEN: It does NOT start with '@manual_override'
        AND: change_reason_for_file (the persistence property) DOES start with '@manual_override'

        This verifies the spec invariant: '@manual_override is an internal implementation
        detail of the .param file format. It is never surfaced in the UI as visible text.'
        change_reason_for_file is the only place that adds the prefix.
        """
        forced_dirty.set_manual_override(True)
        forced_dirty.set_change_reason("User typed reason")

        assert not forced_dirty.change_reason.startswith(MANUAL_OVERRIDE_PREFIX)
        assert forced_dirty.change_reason == "User typed reason"
        assert forced_dirty.change_reason_for_file.startswith(MANUAL_OVERRIDE_PREFIX)

    def test_change_reason_display_never_contains_prefix_when_loaded_from_file(
        self, forced_with_file_override: ArduPilotParameter
    ) -> None:
        """
        change_reason strips the prefix immediately on load; the GUI never sees it.

        GIVEN: A forced parameter constructed from a Par whose comment starts with '@manual_override'
        WHEN: change_reason is read
        THEN: The prefix has been stripped and is not present in the returned string
        """
        assert not forced_with_file_override.change_reason.startswith(MANUAL_OVERRIDE_PREFIX)
        assert forced_with_file_override.change_reason == "Saved user reason"


# ===========================================================================
# _manual_override_on_file baseline tracking
# ===========================================================================


class TestManualOverrideOnFileTracking:
    """_manual_override_on_file is updated correctly by copy_new_value_to_file."""

    def test_initial_baseline_matches_file_comment(self, forced_dirty: ArduPilotParameter) -> None:
        """
        _manual_override_on_file reflects the file comment at construction time.

        GIVEN: A forced param whose file comment does NOT start with '@manual_override'
        WHEN: The parameter is constructed
        THEN: _manual_override_on_file is False
        AND: is_dirty is determined only by value/reason differences
        """
        assert not forced_dirty._manual_override_on_file  # pylint: disable=protected-access

    def test_initial_baseline_true_when_file_has_prefix(self, forced_with_file_override: ArduPilotParameter) -> None:
        """
        _manual_override_on_file is True when the file comment starts with '@manual_override'.

        GIVEN: A forced param whose file comment starts with '@manual_override'
        WHEN: The parameter is constructed
        THEN: _manual_override_on_file is True
        AND: is_manual_override is True
        AND: is_dirty is False (value and reason unchanged from file)
        """
        assert forced_with_file_override._manual_override_on_file  # pylint: disable=protected-access
        assert forced_with_file_override.is_manual_override
        assert not forced_with_file_override.is_dirty

    def test_copy_new_value_to_file_sets_baseline_to_true_after_enable(self, forced_dirty: ArduPilotParameter) -> None:
        """
        After saving with override active, _manual_override_on_file becomes True.

        GIVEN: A forced parameter with override just activated (dirty)
        WHEN: copy_new_value_to_file is called
        THEN: _manual_override_on_file is True
        AND: is_dirty is False
        """
        forced_dirty.set_manual_override(True)
        assert forced_dirty.is_dirty

        forced_dirty.copy_new_value_to_file()

        assert forced_dirty._manual_override_on_file  # pylint: disable=protected-access
        assert not forced_dirty.is_dirty

    def test_copy_new_value_to_file_sets_baseline_to_false_after_disable(
        self, forced_with_file_override: ArduPilotParameter
    ) -> None:
        """
        After saving with override inactive, _manual_override_on_file becomes False.

        GIVEN: A forced parameter loaded with @manual_override (override active)
        WHEN: Override is disabled and copy_new_value_to_file is called
        THEN: _manual_override_on_file is False
        AND: is_dirty is False
        """
        forced_with_file_override.set_manual_override(False)
        assert forced_with_file_override.is_dirty

        forced_with_file_override.copy_new_value_to_file()

        assert not forced_with_file_override._manual_override_on_file  # pylint: disable=protected-access
        assert not forced_with_file_override.is_dirty


# ===========================================================================
# Disable-then-re-enable when _manual_override_on_file is True
# ===========================================================================


class TestReEnableWithFileOverrideActive:
    """Spec requirement 2/3: re-enabling after disable restores file values when _manual_override_on_file=True."""

    def test_reenable_after_disable_restores_file_value_not_forced_value(
        self, forced_with_file_override: ArduPilotParameter
    ) -> None:
        """
        Re-enabling override after a disable restores the persisted file value (7.0), not the forced value (55.0).

        GIVEN: A forced parameter whose file had @manual_override with value 7.0
        AND: The override was just disabled (forced value 55.0 is now active)
        WHEN: The user re-enables the override
        THEN: new_value is 7.0 (from file), NOT 55.0 (the forced value)

        This satisfies the spec requirement: "If there is @manual_override on the file,
        the parameter's new value is set to the value on the file."
        """
        assert forced_with_file_override.is_manual_override  # starts True
        assert forced_with_file_override.get_new_value() == 7.0

        # Disable — reverts to forced value (55.0)
        forced_with_file_override.set_manual_override(False)
        assert forced_with_file_override.get_new_value() == 55.0

        # Re-enable — must restore the file value (7.0), not stay at 55.0
        forced_with_file_override.set_manual_override(True)

        assert forced_with_file_override.get_new_value() == 7.0
        assert forced_with_file_override.is_manual_override

    def test_reenable_after_disable_restores_file_reason_not_forced_reason(
        self, forced_with_file_override: ArduPilotParameter
    ) -> None:
        """
        Re-enabling override after a disable restores the file change reason (not the forced reason).

        GIVEN: A forced parameter whose file had @manual_override with reason "Saved user reason"
        AND: The override was disabled (forced reason "forced reason" is now active)
        WHEN: The user re-enables the override
        THEN: change_reason is "Saved user reason" (from file), NOT "forced reason"
        """
        assert forced_with_file_override.change_reason == "Saved user reason"

        forced_with_file_override.set_manual_override(False)
        assert forced_with_file_override.change_reason == "forced reason"

        forced_with_file_override.set_manual_override(True)

        assert forced_with_file_override.change_reason == "Saved user reason"

    def test_first_enable_without_file_override_uses_forced_value(self, forced_dirty: ArduPilotParameter) -> None:
        """
        First-time enable (no @manual_override in file) uses forced value as starting point.

        GIVEN: A forced parameter whose file has NO @manual_override (file value 10.0, forced value 55.0)
        WHEN: The user enables the override for the first time
        THEN: new_value is the forced value (55.0), NOT the file value (10.0)

        This ensures the spec's two-path behaviour is exercised:
        - No file override → forced/derived value is the starting point
        - File override present → file value is the starting point
        """
        assert not forced_dirty.is_manual_override

        forced_dirty.set_manual_override(True)

        assert forced_dirty.get_new_value() == 55.0  # forced value, not file value 10.0


# ===========================================================================
# Post-save restore: re-enable after save restores SAVED values
# ===========================================================================


class TestPostSaveRestore:
    """After copy_new_value_to_file, re-enable restores the saved (post-save) values."""

    def test_reenable_after_save_restores_saved_value_not_original_file_value(self, forced_dirty: ArduPilotParameter) -> None:
        """
        After saving an overridden param, re-enable restores the saved value (not pre-override file value).

        GIVEN: A forced param (file=10.0) with override enabled and new value set to 30.0
        AND: The parameter has been saved (copy_new_value_to_file)
        AND: The override is then disabled
        WHEN: The user re-enables the override
        THEN: new_value is 30.0 (the saved value), NOT 10.0 (the original file value)

        After save, _value_on_file=30.0 and _manual_override_on_file=True,
        so re-enabling should restore 30.0.
        """
        forced_dirty.set_manual_override(True)
        forced_dirty.set_new_value("30.0")
        assert forced_dirty.get_new_value() == 30.0

        # Save — _value_on_file becomes 30.0, _manual_override_on_file becomes True
        forced_dirty.copy_new_value_to_file()
        assert not forced_dirty.is_dirty

        # Disable — reverts to forced value (55.0)
        forced_dirty.set_manual_override(False)
        assert forced_dirty.get_new_value() == 55.0

        # Re-enable — should restore SAVED value (30.0), not original file value (10.0)
        forced_dirty.set_manual_override(True)

        assert forced_dirty.get_new_value() == 30.0

    def test_reenable_after_save_restores_saved_reason(self, forced_dirty: ArduPilotParameter) -> None:
        """
        After saving, re-enable restores the saved change reason.

        GIVEN: A forced param with override active, reason set to "My saved reason", then saved
        AND: Override is then disabled
        WHEN: The user re-enables the override
        THEN: change_reason is "My saved reason" (saved value), not the forced reason
        """
        forced_dirty.set_manual_override(True)
        forced_dirty.set_change_reason("My saved reason")
        forced_dirty.copy_new_value_to_file()

        forced_dirty.set_manual_override(False)
        assert forced_dirty.change_reason == "forced reason"

        forced_dirty.set_manual_override(True)

        assert forced_dirty.change_reason == "My saved reason"


# ===========================================================================
# set_manual_override raises for non-forced/non-derived params
# ===========================================================================


class TestSetManualOverrideRaisesForRegularParams:
    """set_manual_override raises ValueError for any call on non-forced/non-derived params."""

    def test_raises_when_called_with_true_on_regular_param(self, regular: ArduPilotParameter) -> None:
        """
        set_manual_override(True) raises ValueError for a regular parameter.

        GIVEN: A regular (non-forced, non-derived) parameter
        WHEN: set_manual_override(True) is called
        THEN: ValueError is raised with 'forced or derived' in the message
        """
        with pytest.raises(ValueError, match="forced or derived"):
            regular.set_manual_override(True)

    def test_raises_when_called_with_false_on_regular_param(self, regular: ArduPilotParameter) -> None:
        """
        set_manual_override(False) also raises ValueError for a regular parameter.

        GIVEN: A regular parameter
        WHEN: set_manual_override(False) is called
        THEN: ValueError is raised — there is nothing to deactivate
        """
        with pytest.raises(ValueError, match="forced or derived"):
            regular.set_manual_override(False)

    def test_raises_for_regular_param_with_prefix_in_comment(self, meta: dict[str, Any]) -> None:
        """
        set_manual_override raises even if the regular param's comment starts with '@manual_override'.

        GIVEN: A regular parameter whose file comment happens to start with '@manual_override'
        WHEN: set_manual_override is called (any value)
        THEN: ValueError is raised because the param has no forced/derived definition
        """
        param = ArduPilotParameter(
            name="WEIRD",
            par_obj=Par(1.0, "@manual_override suspicious comment"),
            metadata=meta,
        )

        # set_manual_override always raises for non-forced/non-derived, regardless of direction
        with pytest.raises(ValueError, match="forced or derived"):
            param.set_manual_override(True)
        with pytest.raises(ValueError, match="forced or derived"):
            param.set_manual_override(False)


# ===========================================================================
# is_editable: read-only precedence over manual override
# ===========================================================================


class TestIsEditableWithReadOnly:
    """Read-only parameters are never editable regardless of override state."""

    def test_readonly_forced_param_with_file_override_is_not_editable(self, ro_meta: dict[str, Any]) -> None:
        """
        A read-only forced parameter is not editable even when the file has @manual_override.

        GIVEN: A read-only forced parameter whose file comment starts with '@manual_override'
        WHEN: is_editable is checked
        THEN: is_editable is False (is_readonly takes precedence)
        AND: is_manual_override is True (prefix was detected)
        """
        param = ArduPilotParameter(
            name="RO_FORCED",
            par_obj=Par(7.0, "@manual_override Saved reason"),
            metadata=ro_meta,
            forced_par=Par(55.0, "forced reason"),
        )

        assert param.is_manual_override
        assert param.is_readonly
        assert not param.is_editable

    def test_readonly_derived_param_is_not_editable(self, ro_meta: dict[str, Any]) -> None:
        """
        A read-only derived parameter is not editable regardless of override.

        GIVEN: A read-only derived parameter
        WHEN: is_editable is checked
        THEN: is_editable is False
        """
        param = ArduPilotParameter(
            name="RO_DERIVED",
            par_obj=Par(3.0, "reason"),
            metadata=ro_meta,
            derived_par=Par(10.0, "derived"),
        )

        assert param.is_readonly
        assert not param.is_editable


# ===========================================================================
# is_dirty: all three dirty-detection paths
# ===========================================================================


class TestIsDirtyAllThreePaths:
    """is_dirty is True when value, reason, OR override flag differs from the on-file baseline."""

    def test_dirty_when_only_override_flag_changed(self, forced_clean: ArduPilotParameter) -> None:
        """
        is_dirty is True when only the override flag changed (value and reason are identical).

        GIVEN: A forced param where file value and reason already equal the forced definition
        AND: The param is therefore NOT dirty before activation
        WHEN: set_manual_override(True) is called
        THEN: is_dirty is True (third dirty-detection path: _is_manual_override != _manual_override_on_file)
        """
        assert not forced_clean.is_dirty  # starts clean

        forced_clean.set_manual_override(True)

        assert forced_clean.is_dirty

    def test_dirty_when_only_reason_changed(self, forced_with_file_override: ArduPilotParameter) -> None:
        """
        is_dirty is True when only the change reason was edited after override was already active.

        GIVEN: A forced param loaded from file with @manual_override (override on, not dirty)
        WHEN: The change reason is updated
        THEN: is_dirty is True (second dirty-detection path)
        """
        assert not forced_with_file_override.is_dirty

        forced_with_file_override.set_change_reason("Completely new reason")

        assert forced_with_file_override.is_dirty

    def test_dirty_when_only_value_changed(self, forced_with_file_override: ArduPilotParameter) -> None:
        """
        is_dirty is True when only the value was edited after override was already active.

        GIVEN: A forced param loaded from file with @manual_override (override on, not dirty)
        WHEN: The value is changed
        THEN: is_dirty is True (first dirty-detection path)
        """
        assert not forced_with_file_override.is_dirty

        forced_with_file_override.set_new_value("99.0")

        assert forced_with_file_override.is_dirty

    def test_not_dirty_after_all_three_baselines_are_reset(self, forced_dirty: ArduPilotParameter) -> None:
        """
        is_dirty is False after copy_new_value_to_file resets all three baselines.

        GIVEN: A forced param with override enabled, value changed, and reason changed (all three dirty paths)
        WHEN: copy_new_value_to_file is called
        THEN: is_dirty is False
        """
        forced_dirty.set_manual_override(True)
        forced_dirty.set_new_value("30.0")
        forced_dirty.set_change_reason("Dirty reason")
        assert forced_dirty.is_dirty

        forced_dirty.copy_new_value_to_file()

        assert not forced_dirty.is_dirty


# ===========================================================================
# Prefix stripping on load
# ===========================================================================


class TestPrefixStrippingOnLoad:
    """@manual_override prefix is correctly stripped when loading from file."""

    @pytest.mark.parametrize(
        ("raw_comment", "expected_reason"),
        [
            ("@manual_override", ""),
            ("@manual_override ", ""),
            ("@manual_override  ", ""),  # multiple separator spaces are all stripped
            ("@manual_override Bench test", "Bench test"),
            ("@manual_override  Leading space in reason", "Leading space in reason"),  # all leading spaces stripped
        ],
        ids=["bare_prefix", "prefix_one_space", "prefix_two_spaces", "normal_reason", "extra_space_reason"],
    )
    def test_prefix_stripped_to_correct_reason(self, meta: dict[str, Any], raw_comment: str, expected_reason: str) -> None:
        """
        The displayed change_reason after load is the text after '@manual_override' with ALL leading spaces stripped.

        GIVEN: A Par whose comment starts with '@manual_override' followed by varying whitespace/text
        WHEN: ArduPilotParameter is constructed
        THEN: change_reason equals the text after the prefix with all leading spaces lstripped
              (lstrip removes the separator space AND any additional leading spaces in the reason)
        """
        param = ArduPilotParameter(
            name="P",
            par_obj=Par(1.0, raw_comment),
            metadata=meta,
            forced_par=Par(99.0, "forced"),
        )

        assert param.is_manual_override
        assert param.change_reason == expected_reason

    @pytest.mark.parametrize(
        "raw_comment",
        [
            "normal reason",
            "",
            "See @manual_override docs",
            "@MANUAL_OVERRIDE uppercase",
            " @manual_override leading space",
            "manual_override missing at-sign",
        ],
        ids=["normal", "empty", "mid_string", "uppercase", "leading_space", "no_at_sign"],
    )
    def test_non_prefix_comments_not_detected_as_override(self, meta: dict[str, Any], raw_comment: str) -> None:
        """
        Comments that do not start with exactly '@manual_override' are not detected as override.

        GIVEN: A Par whose comment does NOT start with '@manual_override' (case-sensitive, no leading space)
        WHEN: ArduPilotParameter is constructed
        THEN: is_manual_override is False
        """
        param = ArduPilotParameter(
            name="P",
            par_obj=Par(1.0, raw_comment),
            metadata=meta,
            forced_par=Par(99.0, "forced"),
        )

        assert not param.is_manual_override
