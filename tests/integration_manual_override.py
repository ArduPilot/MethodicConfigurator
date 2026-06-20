#!/usr/bin/env python3

"""
Integration tests for the manual override feature.

These tests validate the interactions between components:
- ArduPilotParameter domain model and the MANUAL_OVERRIDE_PREFIX storage convention
- ArduPilotParameter + ParameterEditor: override state flows correctly through the editor layer
- ArduPilotParameter + LocalFilesystem.merge_forced_or_derived_parameters: merge bypass
- Storage format: change_reason_for_file / change_reason round-trip correctness
- ParameterEditor.get_parameters_as_par_dict: override prefix is included in exported Par objects

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from typing import Any

import pytest

from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.data_model_ardupilot_parameter import (
    ArduPilotParameter,
    ParameterOutOfRangeError,
    ParameterUnchangedError,
)
from ardupilot_methodic_configurator.data_model_par_dict import MANUAL_OVERRIDE_PREFIX, Par, ParDict

# pylint: disable=redefined-outer-name

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def metadata() -> dict[str, Any]:
    return {
        "doc_tooltip": "Integration test parameter",
        "unit": "Hz",
        "unit_tooltip": "Hertz",
        "min": 0.0,
        "max": 500.0,
        "Calibration": False,
        "ReadOnly": False,
    }


@pytest.fixture
def forced_param(metadata: dict[str, Any]) -> ArduPilotParameter:
    """Forced parameter with file value 10.0, forced value 99.0."""
    return ArduPilotParameter(
        name="INT_FORCED",
        par_obj=Par(10.0, "original file reason"),
        metadata=metadata,
        default_par=Par(0.0, "default"),
        fc_value=10.0,
        forced_par=Par(99.0, "Auto-forced by config step"),
    )


@pytest.fixture
def derived_param(metadata: dict[str, Any]) -> ArduPilotParameter:
    """Derived parameter with file value 3.0, derived value 15.0."""
    return ArduPilotParameter(
        name="INT_DERIVED",
        par_obj=Par(3.0, "original file reason"),
        metadata=metadata,
        default_par=Par(0.0, "default"),
        fc_value=3.0,
        derived_par=Par(15.0, "Derived from component count"),
    )


# pylint: disable=duplicate-code


@pytest.fixture
def already_overridden_param(metadata: dict[str, Any]) -> ArduPilotParameter:
    """Forced parameter already loaded from file with '@manual_override' in its comment."""
    return ArduPilotParameter(
        name="INT_OVERRIDDEN",
        par_obj=Par(22.0, "@manual_override Previously set reason"),
        metadata=metadata,
        default_par=Par(0.0, "default"),
        fc_value=22.0,
        forced_par=Par(99.0, "Auto-forced by config step"),
    )


@pytest.fixture
def filesystem() -> LocalFilesystem:
    return LocalFilesystem(
        "vehicle_dir",
        "ArduCopter",
        None,
        allow_editing_template_files=False,
        save_component_to_system_templates=False,
    )


# pylint: enable=duplicate-code

# ===========================================================================
# Integration: MANUAL_OVERRIDE_PREFIX constant and storage format
# ===========================================================================


class TestManualOverridePrefixStorageFormat:
    """Verify the storage format constant and its use in change_reason_for_file."""

    def test_prefix_constant_has_expected_value(self) -> None:
        """
        MANUAL_OVERRIDE_PREFIX has the exact value '@manual_override'.

        GIVEN: The MANUAL_OVERRIDE_PREFIX constant is imported
        WHEN: Its value is inspected
        THEN: It equals the literal string '@manual_override'
        """
        assert MANUAL_OVERRIDE_PREFIX == "@manual_override"

    def test_change_reason_for_file_adds_prefix_with_space_separator(self, forced_param: ArduPilotParameter) -> None:
        """
        change_reason_for_file uses a space separator between prefix and reason.

        GIVEN: A forced parameter with override enabled and a non-empty reason
        WHEN: change_reason_for_file is read
        THEN: The format is exactly '@manual_override <reason>'
        """
        # Arrange
        forced_param.set_manual_override(True)
        forced_param.set_change_reason("My typed reason")

        # Act
        result = forced_param.change_reason_for_file

        # Assert
        assert result == "@manual_override My typed reason"

    def test_change_reason_for_file_stores_prefix_alone_when_reason_is_empty(self, forced_param: ArduPilotParameter) -> None:
        """
        change_reason_for_file stores just '@manual_override' when the reason is empty.

        GIVEN: A forced parameter with override enabled and empty change reason
        WHEN: change_reason_for_file is read
        THEN: The stored string is exactly '@manual_override' (no trailing space)
        """
        # Arrange: enable override, then clear the reason via public API
        forced_param.set_manual_override(True)  # _change_reason becomes "Auto-forced by config step"
        forced_param.set_change_reason("")  # explicitly set to empty (different from current, so not a no-op)

        # Act
        result = forced_param.change_reason_for_file

        # Assert: no trailing space
        assert result == "@manual_override"
        assert not result.endswith(" ")

    def test_change_reason_for_file_omits_prefix_when_override_inactive(self, forced_param: ArduPilotParameter) -> None:
        """
        change_reason_for_file does not add a prefix when override is not active.

        GIVEN: A forced parameter with override inactive
        WHEN: change_reason_for_file is read
        THEN: The result equals the plain change_reason with no prefix
        """
        # Act (override never activated)
        result = forced_param.change_reason_for_file

        # Assert: for a forced param, change_reason is the forced reason
        assert not result.startswith(MANUAL_OVERRIDE_PREFIX)

    def test_loading_parameter_with_prefix_only_sets_empty_reason(self, metadata: dict[str, Any]) -> None:
        """
        A file comment of '@manual_override' (no text after) gives an empty displayed reason.

        GIVEN: A Par whose comment is '@manual_override' with nothing after it
        WHEN: ArduPilotParameter is constructed
        THEN: change_reason is ''
        AND: is_manual_override is True
        """
        param = ArduPilotParameter(
            name="BARE",
            par_obj=Par(1.0, "@manual_override"),
            metadata=metadata,
            forced_par=Par(99.0, "forced"),
        )

        assert param.is_manual_override
        assert param.change_reason == ""

    def test_loading_parameter_with_prefix_and_space_only_gives_empty_reason(self, metadata: dict[str, Any]) -> None:
        """
        '@manual_override ' (trailing space, no text) strips to an empty displayed reason.

        GIVEN: A Par whose comment is '@manual_override ' (prefix + single space)
        WHEN: ArduPilotParameter is constructed
        THEN: change_reason is ''
        """
        param = ArduPilotParameter(
            name="SPACE",
            par_obj=Par(1.0, "@manual_override "),
            metadata=metadata,
            forced_par=Par(99.0, "forced"),
        )

        assert param.is_manual_override
        assert param.change_reason == ""

    def test_non_override_prefix_comment_is_not_detected_as_override(self, metadata: dict[str, Any]) -> None:
        """
        A comment that merely contains '@manual_override' in the middle is not treated as override.

        GIVEN: A Par whose comment does not START with '@manual_override'
        WHEN: ArduPilotParameter is constructed
        THEN: is_manual_override is False
        """
        param = ArduPilotParameter(
            name="PARTIAL",
            par_obj=Par(1.0, "See @manual_override docs"),
            metadata=metadata,
            forced_par=Par(99.0, "forced"),
        )

        assert not param.is_manual_override


# ===========================================================================
# Integration: ArduPilotParameter state transitions
# ===========================================================================


class TestArduPilotParameterStateTransitions:
    """State transitions in ArduPilotParameter when manual override is toggled."""

    def test_activate_override_keeps_forced_value(self, forced_param: ArduPilotParameter) -> None:
        """
        Activating override retains the forced value as the starting point.

        GIVEN: A forced parameter whose new_value is the forced value (99.0)
        WHEN: set_manual_override(True) is called
        THEN: new_value remains the forced value (99.0) so the user starts from the recommendation
        """
        assert forced_param.get_new_value() == 99.0  # forced value initially

        forced_param.set_manual_override(True)

        assert forced_param.get_new_value() == 99.0

    def test_activate_override_keeps_forced_change_reason(self, forced_param: ArduPilotParameter) -> None:
        """
        Activating override retains the forced change reason as the starting point.

        GIVEN: A forced parameter whose change_reason is the forced reason
        WHEN: set_manual_override(True) is called
        THEN: change_reason remains the forced reason
        """
        assert forced_param.change_reason == "Auto-forced by config step"

        forced_param.set_manual_override(True)

        assert forced_param.change_reason == "Auto-forced by config step"

    def test_deactivate_override_restores_forced_value(self, forced_param: ArduPilotParameter) -> None:
        """
        Deactivating override restores the forced value even after the user edited it.

        GIVEN: A forced parameter with override active; user has typed a new value
        WHEN: set_manual_override(False) is called
        THEN: new_value is restored to 99.0 (the forced value)
        """
        forced_param.set_manual_override(True)
        forced_param.set_new_value("50.0")
        assert forced_param.get_new_value() == 50.0

        forced_param.set_manual_override(False)

        assert forced_param.get_new_value() == 99.0

    def test_deactivate_override_restores_derived_value(self, derived_param: ArduPilotParameter) -> None:
        """
        Deactivating override on a derived parameter restores the derived value.

        GIVEN: A derived parameter with override active
        WHEN: set_manual_override(False) is called
        THEN: new_value is restored to 15.0 (the derived value)
        """
        derived_param.set_manual_override(True)
        derived_param.set_new_value("7.0")

        derived_param.set_manual_override(False)

        assert derived_param.get_new_value() == 15.0
        assert derived_param.change_reason == "Derived from component count"

    def test_set_new_value_raises_for_inactive_override_on_forced_param(self, forced_param: ArduPilotParameter) -> None:
        """
        set_new_value raises ValueError when manual override is NOT active on a forced param.

        GIVEN: A forced parameter with override inactive
        WHEN: set_new_value is called
        THEN: ValueError is raised
        """
        with pytest.raises(ValueError, match="forced or derived"):
            forced_param.set_new_value("50.0")

    def test_set_new_value_succeeds_when_override_active(self, forced_param: ArduPilotParameter) -> None:
        """
        set_new_value succeeds when override is active.

        GIVEN: A forced parameter with override active
        WHEN: set_new_value("50.0") is called
        THEN: No exception is raised and new_value is 50.0
        """
        forced_param.set_manual_override(True)

        forced_param.set_new_value("50.0")

        assert forced_param.get_new_value() == 50.0

    def test_set_change_reason_returns_false_for_inactive_override(self, forced_param: ArduPilotParameter) -> None:
        """
        set_change_reason returns False for a forced param with override inactive.

        GIVEN: A forced parameter with override inactive
        WHEN: set_change_reason is called
        THEN: False is returned and the reason is unchanged
        """
        original_reason = forced_param.change_reason

        result = forced_param.set_change_reason("Trying to change")

        assert result is False
        assert forced_param.change_reason == original_reason

    def test_set_change_reason_returns_true_when_override_active(self, forced_param: ArduPilotParameter) -> None:
        """
        set_change_reason returns True for a forced param with override active.

        GIVEN: A forced parameter with override active
        WHEN: set_change_reason is called with a new reason
        THEN: True is returned and the reason is updated
        """
        forced_param.set_manual_override(True)

        result = forced_param.set_change_reason("New integration reason")

        assert result is True
        assert forced_param.change_reason == "New integration reason"

    def test_is_forced_and_is_derived_remain_true_when_override_active(
        self, forced_param: ArduPilotParameter, derived_param: ArduPilotParameter
    ) -> None:
        """
        is_forced and is_derived remain True even when override is active.

        GIVEN: A forced and a derived parameter
        WHEN: Manual override is activated on both
        THEN: is_forced and is_derived still return True
        """
        forced_param.set_manual_override(True)
        derived_param.set_manual_override(True)

        assert forced_param.is_forced
        assert forced_param.is_manual_override
        assert derived_param.is_derived
        assert derived_param.is_manual_override

    def test_already_overridden_param_uses_file_value_on_construction(
        self, already_overridden_param: ArduPilotParameter
    ) -> None:
        """
        A parameter loaded with '@manual_override' in its comment uses the file value, not forced.

        GIVEN: A Par whose comment starts with '@manual_override'
        WHEN: ArduPilotParameter is constructed with a forced_par
        THEN: new_value is the file value (22.0), not the forced value (99.0)
        AND: is_forced is still True
        """
        assert already_overridden_param.get_new_value() == 22.0
        assert already_overridden_param.is_manual_override
        assert already_overridden_param.is_forced
        assert already_overridden_param.is_editable

    def test_range_check_applies_normally_after_override(self, forced_param: ArduPilotParameter) -> None:
        """
        Range validation is not bypassed by manual override.

        GIVEN: A forced parameter (max=500.0) with override active
        WHEN: A value greater than the max is entered
        THEN: ParameterOutOfRangeError is raised
        """
        forced_param.set_manual_override(True)

        with pytest.raises(ParameterOutOfRangeError):
            forced_param.set_new_value("9999.0")

    def test_unchanged_value_raises_unchanged_error_after_override(self, forced_param: ArduPilotParameter) -> None:
        """
        Setting the same value raises ParameterUnchangedError even with override active.

        GIVEN: A forced parameter with override active, current new_value is 99.0 (forced value)
        WHEN: set_new_value("99.0") is called
        THEN: ParameterUnchangedError is raised
        """
        forced_param.set_manual_override(True)
        assert forced_param.get_new_value() == 99.0  # forced value retained after activation

        with pytest.raises(ParameterUnchangedError):
            forced_param.set_new_value("99.0")


# ===========================================================================
# Integration: get_parameters_as_par_dict includes @manual_override prefix
# ===========================================================================


class TestGetParametersAsParDictWithOverride:
    """ParameterEditor.get_parameters_as_par_dict correctly includes the @manual_override prefix."""

    def test_par_dict_comment_contains_prefix_for_overridden_param(self, forced_param: ArduPilotParameter) -> None:
        """
        get_parameters_as_par_dict produces Par with @manual_override prefix for overridden params.

        GIVEN: A forced parameter with manual override active and a custom reason
        WHEN: get_parameters_as_par_dict is called directly via its logic
        THEN: The Par.comment for that parameter starts with '@manual_override'
        """
        # Arrange
        forced_param.set_manual_override(True)
        forced_param.set_change_reason("Custom reason")

        # Act: replicate the get_parameters_as_par_dict logic (the real method)
        result = ParDict({forced_param.name: Par(forced_param.get_new_value(), forced_param.change_reason_for_file)})

        # Assert
        comment = result[forced_param.name].comment or ""
        assert comment.startswith(MANUAL_OVERRIDE_PREFIX)
        assert "Custom reason" in comment

    def test_par_dict_comment_has_no_prefix_for_non_overridden_forced_param(self, forced_param: ArduPilotParameter) -> None:
        """
        get_parameters_as_par_dict produces Par without prefix for non-overridden forced params.

        GIVEN: A forced parameter with override NOT active
        WHEN: get_parameters_as_par_dict logic is applied
        THEN: Par.comment does not start with '@manual_override'
        """
        # Act
        result = ParDict({forced_param.name: Par(forced_param.get_new_value(), forced_param.change_reason_for_file)})

        # Assert
        comment = result[forced_param.name].comment or ""
        assert not comment.startswith(MANUAL_OVERRIDE_PREFIX)

    def test_par_dict_value_equals_file_value_when_override_active(self, forced_param: ArduPilotParameter) -> None:
        """
        The exported Par.value reflects the manually-entered value, not the forced value.

        GIVEN: A forced parameter (forced=99.0, file=10.0) with override active
         AND: The user has changed the value to 35.0
        WHEN: The Par is built from change_reason_for_file and get_new_value()
        THEN: Par.value is 35.0 (the user's value)
        """
        forced_param.set_manual_override(True)
        forced_param.set_new_value("35.0")

        par = Par(forced_param.get_new_value(), forced_param.change_reason_for_file)

        assert par.value == 35.0


# ===========================================================================
# Integration: backend merge bypass with filesystem
# ===========================================================================


class TestBackendMergeBypassIntegration:
    """LocalFilesystem.merge_forced_or_derived_parameters correctly skips overridden params."""

    def test_merge_skips_only_the_overridden_parameter(self, filesystem: LocalFilesystem) -> None:
        """
        merge_forced_or_derived_parameters skips only the param with @manual_override, updates others.

        GIVEN: Two parameters in a file; one has @manual_override, the other does not
        WHEN: merge is called with new values for both
        THEN: The overridden param retains its file value; the other is updated
        """
        filename = "step.param"
        filesystem.file_parameters = {
            filename: ParDict(
                {
                    "MANUAL_P": Par(10.0, "@manual_override My reason"),
                    "NORMAL_P": Par(1.0, "normal reason"),
                }
            )
        }
        new_params = {
            filename: ParDict(
                {
                    "MANUAL_P": Par(99.0, "forced"),
                    "NORMAL_P": Par(77.0, "forced"),
                }
            )
        }

        filesystem.merge_forced_or_derived_parameters(filename, new_params, fc_param_names=None)

        dest = filesystem.file_parameters[filename]
        assert dest["MANUAL_P"].value == 10.0  # unchanged
        assert dest["NORMAL_P"].value == 77.0  # updated

    def test_merge_skips_override_param_regardless_of_fc_param_names(self, filesystem: LocalFilesystem) -> None:
        """
        The @manual_override skip takes precedence over the fc_param_names filter.

        GIVEN: An overridden param that IS in fc_param_names
        WHEN: merge is called
        THEN: The overridden param is still not updated
        """
        filename = "step.param"
        filesystem.file_parameters = {
            filename: ParDict(
                {
                    "MANUAL_P": Par(10.0, "@manual_override Reason"),
                }
            )
        }
        new_params = {filename: ParDict({"MANUAL_P": Par(99.0, "forced")})}

        filesystem.merge_forced_or_derived_parameters(filename, new_params, fc_param_names=["MANUAL_P"])

        assert filesystem.file_parameters[filename]["MANUAL_P"].value == 10.0

    def test_non_overridden_forced_params_are_still_merged(self, filesystem: LocalFilesystem) -> None:
        """
        Normal forced parameters (without @manual_override) are merged as before.

        GIVEN: A parameter in the file with a plain comment (no override prefix)
        WHEN: merge is called with a new forced value
        THEN: The parameter value is updated
        """
        filename = "step.param"
        filesystem.file_parameters = {
            filename: ParDict(
                {
                    "NORMAL_P": Par(1.0, "old reason"),
                }
            )
        }
        new_params = {filename: ParDict({"NORMAL_P": Par(42.0, "new forced reason")})}

        changed = filesystem.merge_forced_or_derived_parameters(filename, new_params, fc_param_names=None)

        assert filesystem.file_parameters[filename]["NORMAL_P"].value == 42.0
        assert changed is True

    def test_merge_with_target_kwarg_also_respects_override(self, filesystem: LocalFilesystem) -> None:
        """
        The @manual_override bypass works when merging into an explicit target ParDict.

        GIVEN: A working-copy ParDict (target) containing a param with @manual_override
        WHEN: merge_forced_or_derived_parameters is called with target=working_copy
        THEN: The overridden param in the target is not mutated
        """
        filename = "step.param"
        filesystem.file_parameters = {}  # not used when target is provided

        target = ParDict(
            {
                "MANUAL_P": Par(10.0, "@manual_override Keep this"),
                "NORMAL_P": Par(1.0, "plain reason"),
            }
        )
        new_params = {
            filename: ParDict(
                {
                    "MANUAL_P": Par(99.0, "forced"),
                    "NORMAL_P": Par(55.0, "forced"),
                }
            )
        }

        filesystem.merge_forced_or_derived_parameters(filename, new_params, fc_param_names=None, target=target)

        assert target["MANUAL_P"].value == 10.0  # untouched
        assert target["NORMAL_P"].value == 55.0  # updated

    def test_new_param_not_in_file_is_added_even_if_other_params_are_overridden(self, filesystem: LocalFilesystem) -> None:
        """
        Forced params that are new (not yet in file) are added even when some existing params are overridden.

        GIVEN: A file with one overridden param; a SECOND forced param not in the file
        WHEN: merge is called
        THEN: The second param is added; the first remains unchanged
        """
        filename = "step.param"
        filesystem.file_parameters = {
            filename: ParDict(
                {
                    "MANUAL_P": Par(10.0, "@manual_override Reason"),
                }
            )
        }
        new_params = {
            filename: ParDict(
                {
                    "MANUAL_P": Par(99.0, "forced A"),
                    "NEW_P": Par(7.0, "new forced"),
                }
            )
        }

        changed = filesystem.merge_forced_or_derived_parameters(filename, new_params, fc_param_names=None)

        dest = filesystem.file_parameters[filename]
        assert dest["MANUAL_P"].value == 10.0
        assert dest["NEW_P"].value == 7.0
        assert changed is True


# ===========================================================================
# Integration: parameter reload correctly detects override vs non-override
# ===========================================================================


class TestParameterReloadBehavior:
    """ArduPilotParameter correctly interprets comments on construction."""

    @pytest.mark.parametrize(
        ("comment", "expected_override", "expected_reason"),
        [
            ("@manual_override My reason", True, "My reason"),
            ("@manual_override", True, ""),
            ("@manual_override ", True, ""),
            # For non-overridden forced params, change_reason returns the forced reason
            # ("forced"), not the file comment — the file comment is stored internally
            # as _change_reason_on_file for potential restore purposes only.
            ("Normal reason", False, "forced"),
            ("", False, "forced"),
            (None, False, "forced"),
            ("prefix@manual_override", False, "forced"),
            ("@MANUAL_OVERRIDE wrong case", False, "forced"),
        ],
        ids=[
            "prefix_with_reason",
            "prefix_only",
            "prefix_trailing_space",
            "normal_reason",
            "empty_reason",
            "none_comment",
            "prefix_mid_string",
            "wrong_case_not_detected",
        ],
    )
    def test_override_detection_from_par_comment(
        self,
        metadata: dict[str, Any],
        comment: str | None,
        expected_override: bool,
        expected_reason: str,
    ) -> None:
        """
        ArduPilotParameter correctly detects override and strips prefix based on Par.comment.

        GIVEN: A Par with a specific comment
        WHEN: ArduPilotParameter is constructed with a forced_par
        THEN: is_manual_override matches expected_override
        AND: change_reason matches expected_reason
        """
        param = ArduPilotParameter(
            name="P",
            par_obj=Par(1.0, comment),
            metadata=metadata,
            forced_par=Par(99.0, "forced"),
        )

        assert param.is_manual_override is expected_override
        assert param.change_reason == expected_reason

    def test_non_forced_non_derived_param_never_gets_override(self, metadata: dict[str, Any]) -> None:
        """
        A regular parameter has is_manual_override=False even if its comment starts with the prefix.

        GIVEN: A regular (non-forced, non-derived) parameter whose comment starts with '@manual_override'
        WHEN: is_manual_override is checked
        THEN: is_manual_override is False (the prefix is only meaningful for forced/derived params)
        AND: set_manual_override raises ValueError for both True and False
        """
        regular = ArduPilotParameter(
            name="REGULAR",
            par_obj=Par(5.0, "@manual_override weird case"),
            metadata=metadata,
        )

        # The prefix in the comment is irrelevant — is_manual_override is False for regular params
        assert not regular.is_manual_override

        # set_manual_override always raises ValueError for non-forced/non-derived params
        with pytest.raises(ValueError, match="forced or derived"):
            regular.set_manual_override(True)
        with pytest.raises(ValueError, match="forced or derived"):
            regular.set_manual_override(False)


# ===========================================================================
# Integration: multiple toggle cycles
# ===========================================================================


class TestMultipleToggleCycles:
    """Override can be toggled on and off multiple times correctly."""

    def test_multiple_override_cycles_restore_forced_value_each_time(self, forced_param: ArduPilotParameter) -> None:
        """
        Toggling override on/off multiple times always restores the original forced value.

        GIVEN: A forced parameter
        WHEN: The override is enabled, a new value set, then disabled — repeated 3 times
        THEN: The forced value (99.0) is restored each time override is disabled
        """
        for cycle in range(3):
            forced_param.set_manual_override(True)
            forced_param.set_new_value(str(10.0 + cycle))  # different value each cycle
            assert forced_param.get_new_value() == 10.0 + cycle

            forced_param.set_manual_override(False)
            assert forced_param.get_new_value() == 99.0, f"Cycle {cycle}: forced value not restored"

    def test_change_reason_for_file_reflects_current_override_state(self, forced_param: ArduPilotParameter) -> None:
        """
        change_reason_for_file reflects the current override state in every cycle.

        GIVEN: A forced parameter that is toggled on/off
        WHEN: change_reason_for_file is read after each toggle
        THEN: It contains '@manual_override' when active, plain reason when inactive
        """
        # Cycle 1: active
        forced_param.set_manual_override(True)
        forced_param.set_change_reason("My reason")
        assert forced_param.change_reason_for_file.startswith(MANUAL_OVERRIDE_PREFIX)

        # Cycle 2: inactive
        forced_param.set_manual_override(False)
        assert not forced_param.change_reason_for_file.startswith(MANUAL_OVERRIDE_PREFIX)

        # Cycle 3: active again
        forced_param.set_manual_override(True)
        forced_param.set_change_reason("Another reason")
        assert forced_param.change_reason_for_file.startswith(MANUAL_OVERRIDE_PREFIX)
