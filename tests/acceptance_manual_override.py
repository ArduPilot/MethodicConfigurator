#!/usr/bin/env python3

"""
Acceptance tests for the manual override feature.

These tests validate complete user journeys described in manual_override.md:
- A user can activate manual override to freely edit a forced or derived parameter.
- A user can deactivate manual override to restore forced/derived automatic management.
- The override state survives saving to and reloading from a .param file.
- The backend never overwrites a manually overridden parameter during re-computation.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import os
import tempfile
from typing import Any

import pytest

from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.data_model_ardupilot_parameter import ArduPilotParameter, ParameterOutOfRangeError
from ardupilot_methodic_configurator.data_model_par_dict import MANUAL_OVERRIDE_PREFIX, Par, ParDict

# pylint: disable=redefined-outer-name

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def basic_metadata() -> dict[str, Any]:
    """Minimal metadata with realistic range constraints."""
    return {
        "doc_tooltip": "Test parameter",
        "unit": "m/s",
        "unit_tooltip": "Meters per second",
        "min": 0.0,
        "max": 100.0,
        "Calibration": False,
        "ReadOnly": False,
    }


@pytest.fixture
def forced_param(basic_metadata: dict[str, Any]) -> ArduPilotParameter:
    """A parameter that is forced by the configuration step."""
    return ArduPilotParameter(
        name="FORCED_PARAM",
        par_obj=Par(5.0, "file reason"),
        metadata=basic_metadata,
        default_par=Par(10.0, "default"),
        fc_value=5.0,
        forced_par=Par(42.0, "Must be 42 for safety"),
    )


@pytest.fixture
def derived_param(basic_metadata: dict[str, Any]) -> ArduPilotParameter:
    """A parameter whose value is derived from the component editor."""
    return ArduPilotParameter(
        name="DERIVED_PARAM",
        par_obj=Par(5.0, "file reason"),
        metadata=basic_metadata,
        default_par=Par(10.0, "default"),
        fc_value=5.0,
        derived_par=Par(99.0, "Derived from motor count"),
    )


# pylint: disable=duplicate-code


@pytest.fixture
def forced_param_with_override(basic_metadata: dict[str, Any]) -> ArduPilotParameter:
    """A forced parameter that already has manual override active (as loaded from file)."""
    return ArduPilotParameter(
        name="FORCED_OVERRIDE",
        par_obj=Par(7.0, "@manual_override My custom reason"),
        metadata=basic_metadata,
        default_par=Par(10.0, "default"),
        fc_value=7.0,
        forced_par=Par(42.0, "Must be 42 for safety"),
    )


@pytest.fixture
def local_filesystem() -> LocalFilesystem:
    """A LocalFilesystem instance pointing at a temporary directory."""
    return LocalFilesystem(
        "vehicle_dir",
        "ArduCopter",
        None,
        allow_editing_template_files=False,
        save_component_to_system_templates=False,
    )


# pylint: enable=duplicate-code

# ===========================================================================
# Acceptance tests: user activates manual override
# ===========================================================================


class TestUserActivatesManualOverride:
    """User checks the 'Manual' checkbox for a forced or derived parameter."""

    def test_user_can_activate_manual_override_on_forced_parameter(self, forced_param: ArduPilotParameter) -> None:
        """
        User can enable manual override on a forced parameter.

        GIVEN: A forced parameter that is normally read-only
        WHEN: The user checks the 'Manual' checkbox (set_manual_override(True))
        THEN: The parameter becomes editable
        AND: Its value is set to the forced value as a starting point
        AND: Its change reason is set to the forced change reason
        AND: The is_dirty flag is True
        """
        # Arrange: confirm initial state
        assert forced_param.is_forced
        assert not forced_param.is_editable
        assert not forced_param.is_manual_override

        # Act: user checks the checkbox
        forced_param.set_manual_override(True)

        # Assert: parameter is now editable
        assert forced_param.is_manual_override
        assert forced_param.is_editable
        # Value starts at the forced value so the user can make a small intentional adjustment
        assert forced_param.get_new_value() == 42.0
        # Change reason starts at the forced reason
        assert forced_param.change_reason == "Must be 42 for safety"
        # Must be flagged for saving
        assert forced_param.is_dirty

    def test_user_can_activate_manual_override_on_derived_parameter(self, derived_param: ArduPilotParameter) -> None:
        """
        User can enable manual override on a derived parameter.

        GIVEN: A derived parameter that is normally read-only
        WHEN: The user checks the 'Manual' checkbox
        THEN: The parameter becomes editable starting from the derived value and reason
        """
        # Arrange
        assert derived_param.is_derived
        assert not derived_param.is_editable

        # Act
        derived_param.set_manual_override(True)

        # Assert
        assert derived_param.is_manual_override
        assert derived_param.is_editable
        assert derived_param.get_new_value() == 99.0  # derived value, not file value
        assert derived_param.change_reason == "Derived from motor count"
        assert derived_param.is_dirty

    def test_forced_and_derived_flags_remain_true_after_override(self, forced_param: ArduPilotParameter) -> None:
        """
        is_forced remains True even after manual override is activated.

        GIVEN: A forced parameter
        WHEN: Manual override is enabled
        THEN: is_forced is still True (the config-step intent is unchanged)
        AND: is_manual_override is also True
        """
        forced_param.set_manual_override(True)

        assert forced_param.is_forced
        assert forced_param.is_manual_override

    def test_prefix_is_stripped_from_change_reason_display(self, forced_param_with_override: ArduPilotParameter) -> None:
        """
        The @manual_override prefix is never shown to the user.

        GIVEN: A parameter loaded from a file whose comment starts with '@manual_override'
        WHEN: The change_reason property is read
        THEN: The returned string does not contain the @manual_override prefix
        """
        assert not forced_param_with_override.change_reason.startswith(MANUAL_OVERRIDE_PREFIX)
        assert forced_param_with_override.change_reason == "My custom reason"


# ===========================================================================
# Acceptance tests: user edits value and reason after override
# ===========================================================================


class TestUserEditsAfterOverride:
    """User modifies value and change reason after enabling manual override."""

    def test_user_can_change_value_after_manual_override(self, forced_param: ArduPilotParameter) -> None:
        """
        User can set a new value for a manually-overridden forced parameter.

        GIVEN: A forced parameter with manual override enabled
        WHEN: The user types a new value in the value entry
        THEN: The new value is stored without raising ValueError
        """
        # Arrange
        forced_param.set_manual_override(True)

        # Act: user types a new value
        forced_param.set_new_value("25.0")

        # Assert
        assert forced_param.get_new_value() == 25.0

    def test_user_can_change_reason_after_manual_override(self, forced_param: ArduPilotParameter) -> None:
        """
        User can update the change reason for a manually-overridden forced parameter.

        GIVEN: A forced parameter with manual override enabled
        WHEN: The user types a new change reason
        THEN: set_change_reason returns True and the reason is stored
        """
        # Arrange
        forced_param.set_manual_override(True)

        # Act
        result = forced_param.set_change_reason("Changed for bench test")

        # Assert
        assert result is True
        assert forced_param.change_reason == "Changed for bench test"

    def test_range_validation_still_applies_after_override(self, forced_param: ArduPilotParameter) -> None:
        """
        Out-of-range values trigger ParameterOutOfRangeError even with manual override active.

        GIVEN: A forced parameter (max=100.0) with manual override enabled
        WHEN: The user enters a value greater than the maximum
        THEN: ParameterOutOfRangeError is raised
        """
        # Arrange
        forced_param.set_manual_override(True)

        # Act / Assert
        with pytest.raises(ParameterOutOfRangeError):
            forced_param.set_new_value("200.0")


# ===========================================================================
# Acceptance tests: user deactivates manual override
# ===========================================================================


class TestUserDeactivatesManualOverride:
    """User unchecks the 'Manual' checkbox, reverting to forced/derived management."""

    def test_user_can_deactivate_override_on_forced_parameter(self, forced_param: ArduPilotParameter) -> None:
        """
        User can disable manual override, restoring the forced value.

        GIVEN: A forced parameter with manual override active
        WHEN: The user unchecks the 'Manual' checkbox
        THEN: The parameter reverts to the forced value and forced change reason
        AND: The parameter is no longer editable
        AND: is_dirty is True (so the revert gets saved)
        """
        # Arrange: activate override, change the value
        forced_param.set_manual_override(True)
        forced_param.set_new_value("25.0")

        # Act: user unchecks the checkbox
        forced_param.set_manual_override(False)

        # Assert: reverted to forced value
        assert not forced_param.is_manual_override
        assert not forced_param.is_editable
        assert forced_param.get_new_value() == 42.0  # forced value
        assert forced_param.change_reason == "Must be 42 for safety"
        assert forced_param.is_dirty

    def test_user_can_deactivate_override_on_derived_parameter(self, derived_param: ArduPilotParameter) -> None:
        """
        User can disable manual override, restoring the derived value.

        GIVEN: A derived parameter with manual override active
        WHEN: The user unchecks the 'Manual' checkbox
        THEN: The parameter reverts to the derived value and derived change reason
        """
        # Arrange
        derived_param.set_manual_override(True)

        # Act
        derived_param.set_manual_override(False)

        # Assert: reverted to derived value
        assert not derived_param.is_manual_override
        assert derived_param.get_new_value() == 99.0  # derived value
        assert derived_param.change_reason == "Derived from motor count"


# ===========================================================================
# Acceptance tests: persistence round-trip
# ===========================================================================


class TestManualOverridePersistence:
    """Manual override state survives saving to and reloading from a .param file."""

    def test_override_prefix_is_written_to_file_when_active(self, forced_param: ArduPilotParameter) -> None:
        """
        Activating manual override causes the @manual_override prefix to be written to the .param file.

        GIVEN: A forced parameter with manual override just activated and a reason set
        WHEN: change_reason_for_file is read (used when saving to disk)
        THEN: The returned string starts with '@manual_override'
        AND: The user's reason follows the prefix
        """
        # Arrange
        forced_param.set_manual_override(True)
        forced_param.set_change_reason("Changed for bench test")

        # Act
        comment_for_file = forced_param.change_reason_for_file

        # Assert
        assert comment_for_file.startswith(MANUAL_OVERRIDE_PREFIX)
        assert "Changed for bench test" in comment_for_file

    def test_override_prefix_is_absent_from_file_when_inactive(self, forced_param: ArduPilotParameter) -> None:
        """
        When manual override is NOT active, no prefix is written to the .param file.

        GIVEN: A forced parameter whose override has been deactivated
        WHEN: change_reason_for_file is read
        THEN: The returned string does not start with '@manual_override'
        """
        # Arrange: never activate (starts inactive)
        # Act
        comment_for_file = forced_param.change_reason_for_file

        # Assert
        assert not comment_for_file.startswith(MANUAL_OVERRIDE_PREFIX)

    def test_override_state_is_restored_after_reload_from_file(self, basic_metadata: dict[str, Any]) -> None:
        """
        Loading a parameter whose .param comment starts with '@manual_override' restores override state.

        GIVEN: A .param file whose comment for FORCED_PARAM begins with '@manual_override Bench reason'
        WHEN: The parameter is created from that Par object
        THEN: is_manual_override is True
        AND: The displayed change_reason is 'Bench reason' (no prefix)
        AND: The parameter's new value is taken from the file, not the forced definition
        """
        # Arrange: simulate loading from file
        par_from_file = Par(25.0, "@manual_override Bench reason")
        forced_definition = Par(42.0, "Must be 42 for safety")

        # Act: create domain model as if reloaded
        param = ArduPilotParameter(
            name="FORCED_PARAM",
            par_obj=par_from_file,
            metadata=basic_metadata,
            default_par=Par(10.0, "default"),
            fc_value=25.0,
            forced_par=forced_definition,
        )

        # Assert
        assert param.is_manual_override
        assert param.is_editable
        assert param.get_new_value() == 25.0  # file value preserved
        assert param.change_reason == "Bench reason"  # prefix stripped

    def test_override_with_no_reason_survives_round_trip(self, basic_metadata: dict[str, Any]) -> None:
        """
        A manual override with no typed reason stores and loads '@manual_override' alone.

        GIVEN: A forced parameter with override active but empty change reason
        WHEN: change_reason_for_file is stored and re-parsed
        THEN: is_manual_override is True and change_reason is empty
        """
        # Arrange: override with empty reason
        par_from_file = Par(5.0, "@manual_override")
        param = ArduPilotParameter(
            name="FORCED_PARAM",
            par_obj=par_from_file,
            metadata=basic_metadata,
            forced_par=Par(42.0, "Must be 42"),
        )

        # Assert: round-trip is clean
        assert param.is_manual_override
        assert param.change_reason == ""
        assert param.change_reason_for_file == MANUAL_OVERRIDE_PREFIX

    def test_full_round_trip_via_param_file_on_disk(self, basic_metadata: dict[str, Any]) -> None:
        """
        Manual override state is preserved through an actual .param file write and read cycle.

        GIVEN: A forced parameter with manual override active and a custom value and reason
        WHEN: The parameter is exported to a .param file and re-loaded
        THEN: The reloaded parameter has the same value, change_reason, and is_manual_override=True
        AND: The forced definition is still present but not applied (override wins)
        """
        # Arrange
        forced_par = Par(42.0, "Must be 42")
        par_from_file = Par(25.0, "@manual_override Bench test value")
        param = ArduPilotParameter(
            name="FORCED_PARAM",
            par_obj=par_from_file,
            metadata=basic_metadata,
            forced_par=forced_par,
        )

        with tempfile.NamedTemporaryFile(suffix=".param", mode="w", delete=False, encoding="utf-8") as f:
            param_file_path = f.name

        try:
            # Act: export ParDict containing the overridden parameter to disk
            par_dict = ParDict({"FORCED_PARAM": Par(param.get_new_value(), param.change_reason_for_file)})
            par_dict.export_to_param(param_file_path)

            # Re-load the file
            loaded_dict = ParDict.load_param_file_into_dict(param_file_path)
            loaded_par = loaded_dict["FORCED_PARAM"]

            # Reconstruct the domain model (simulating application reload)
            reloaded_param = ArduPilotParameter(
                name="FORCED_PARAM",
                par_obj=loaded_par,
                metadata=basic_metadata,
                forced_par=forced_par,
            )

            # Assert: state fully preserved
            assert reloaded_param.is_manual_override
            assert reloaded_param.get_new_value() == 25.0
            assert reloaded_param.change_reason == "Bench test value"
            assert reloaded_param.is_editable
        finally:
            if os.path.exists(param_file_path):
                os.remove(param_file_path)


# ===========================================================================
# Acceptance tests: backend merge bypass
# ===========================================================================


class TestBackendRespectsManualOverride:
    """The backend never overwrites a manually-overridden parameter during forced/derived merge."""

    def test_backend_does_not_overwrite_manually_overridden_parameter(self, local_filesystem: LocalFilesystem) -> None:
        """
        merge_forced_or_derived_parameters skips parameters with @manual_override in the destination.

        GIVEN: A ParDict containing a parameter whose comment starts with '@manual_override'
        WHEN: merge_forced_or_derived_parameters is called with a new forced value for that param
        THEN: The parameter's value and comment in the destination are unchanged
        AND: The function returns True because OTHER_PARAM did change
        """
        # Arrange: file has a manually-overridden parameter
        filename = "test_step.param"
        local_filesystem.file_parameters = {
            filename: ParDict(
                {
                    "FORCED_PARAM": Par(25.0, "@manual_override Bench test value"),
                    "OTHER_PARAM": Par(1.0, "normal reason"),
                }
            )
        }

        # The forced computation wants to set FORCED_PARAM to 42.0
        new_forced = {
            filename: ParDict(
                {
                    "FORCED_PARAM": Par(42.0, "Must be 42 for safety"),
                    "OTHER_PARAM": Par(9.0, "forced other"),
                }
            )
        }

        # Act
        changed = local_filesystem.merge_forced_or_derived_parameters(filename, new_forced, fc_param_names=None)

        # Assert: FORCED_PARAM was NOT overwritten
        dest = local_filesystem.file_parameters[filename]
        assert dest["FORCED_PARAM"].value == 25.0
        assert (dest["FORCED_PARAM"].comment or "").startswith(MANUAL_OVERRIDE_PREFIX)
        # OTHER_PARAM was still updated
        assert dest["OTHER_PARAM"].value == 9.0
        # changed is True because OTHER_PARAM did change
        assert changed is True

    def test_backend_skips_all_manual_override_params_returns_false_when_no_other_changes(
        self, local_filesystem: LocalFilesystem
    ) -> None:
        """
        merge_forced_or_derived_parameters returns False when ALL forced params are overridden.

        GIVEN: A file where every parameter has @manual_override
        WHEN: merge_forced_or_derived_parameters is called
        THEN: No values change and the function returns False
        """
        filename = "test_step.param"
        local_filesystem.file_parameters = {
            filename: ParDict(
                {
                    "PARAM_A": Par(1.0, "@manual_override reason A"),
                    "PARAM_B": Par(2.0, "@manual_override reason B"),
                }
            )
        }

        new_forced = {
            filename: ParDict(
                {
                    "PARAM_A": Par(10.0, "forced A"),
                    "PARAM_B": Par(20.0, "forced B"),
                }
            )
        }

        changed = local_filesystem.merge_forced_or_derived_parameters(filename, new_forced, fc_param_names=None)

        dest = local_filesystem.file_parameters[filename]
        assert dest["PARAM_A"].value == 1.0
        assert dest["PARAM_B"].value == 2.0
        assert changed is False

    def test_backend_still_adds_newly_forced_params_not_in_file(self, local_filesystem: LocalFilesystem) -> None:
        """
        A forced parameter not yet present in the file is added even when other params are overridden.

        GIVEN: A file with one manually-overridden parameter
        WHEN: A NEW forced parameter (not in the file) is merged
        THEN: The new parameter is added to the file
        AND: The overridden parameter remains unchanged
        """
        filename = "test_step.param"
        local_filesystem.file_parameters = {
            filename: ParDict(
                {
                    "EXISTING_FORCED": Par(25.0, "@manual_override My reason"),
                }
            )
        }

        new_forced = {
            filename: ParDict(
                {
                    "EXISTING_FORCED": Par(42.0, "Must be 42"),
                    "NEW_FORCED": Par(5.0, "Newly required"),
                }
            )
        }

        changed = local_filesystem.merge_forced_or_derived_parameters(filename, new_forced, fc_param_names=None)

        dest = local_filesystem.file_parameters[filename]
        assert dest["EXISTING_FORCED"].value == 25.0  # unchanged
        assert dest["NEW_FORCED"].value == 5.0  # added
        assert changed is True


# ===========================================================================
# Acceptance tests: dirty detection
# ===========================================================================


class TestDirtyDetectionForManualOverride:
    """is_dirty correctly tracks manual override state changes."""

    def test_toggling_checkbox_marks_parameter_dirty(self) -> None:
        """
        Checking the 'Manual' checkbox marks the parameter as dirty even if value is unchanged.

        GIVEN: A forced parameter whose file value happens to equal the forced value
        WHEN: The user checks the 'Manual' checkbox
        THEN: is_dirty is True even though the numeric value did not change
        """
        # Arrange: forced value == file value AND reasons match so param starts clean
        par_obj = Par(42.0, "Must be 42")
        forced_par = Par(42.0, "Must be 42")
        param = ArduPilotParameter(
            name="SAME_VALUE",
            par_obj=par_obj,
            forced_par=forced_par,
        )
        assert not param.is_dirty  # clean initially

        # Act
        param.set_manual_override(True)

        # Assert: dirty because override state changed
        assert param.is_dirty

    def test_copy_new_value_to_file_resets_dirty_flag(self, forced_param: ArduPilotParameter) -> None:
        """
        copy_new_value_to_file resets is_dirty after saving.

        GIVEN: A forced parameter whose manual override was just activated (is_dirty=True)
        WHEN: copy_new_value_to_file is called (simulating a file save)
        THEN: is_dirty returns False
        AND: The override state is still active
        """
        # Arrange
        forced_param.set_manual_override(True)
        assert forced_param.is_dirty

        # Act: simulate save
        forced_param.copy_new_value_to_file()

        # Assert
        assert not forced_param.is_dirty
        assert forced_param.is_manual_override  # override still active

    def test_disabling_override_after_save_marks_dirty_again(self, forced_param: ArduPilotParameter) -> None:
        """
        Unchecking 'Manual' after a save marks the parameter dirty again.

        GIVEN: A manually-overridden parameter that was saved (is_dirty=False)
        WHEN: The user unchecks the checkbox
        THEN: is_dirty becomes True again
        """
        # Arrange: activate, save
        forced_param.set_manual_override(True)
        forced_param.copy_new_value_to_file()
        assert not forced_param.is_dirty

        # Act: uncheck
        forced_param.set_manual_override(False)

        # Assert
        assert forced_param.is_dirty


# ===========================================================================
# Acceptance tests: constraints and invariants
# ===========================================================================


class TestManualOverrideConstraints:
    """Constraints described in the specification are enforced."""

    def test_set_manual_override_raises_for_regular_parameter(self, basic_metadata: dict[str, Any]) -> None:
        """
        Calling set_manual_override on a non-forced, non-derived parameter raises ValueError.

        GIVEN: A regular parameter (not forced, not derived)
        WHEN: set_manual_override is called
        THEN: ValueError is raised
        """
        # Arrange
        regular = ArduPilotParameter(
            name="NORMAL_PARAM",
            par_obj=Par(5.0, "reason"),
            metadata=basic_metadata,
        )

        # Act / Assert
        with pytest.raises(ValueError, match="only applicable to forced or derived"):
            regular.set_manual_override(True)

    def test_readonly_parameter_is_not_editable_even_with_override_in_file(self, basic_metadata: dict[str, Any]) -> None:
        """
        A read-only parameter loaded with @manual_override comment is still not editable.

        GIVEN: A read-only forced parameter whose .param comment starts with '@manual_override'
        WHEN: The domain model is constructed
        THEN: is_editable is False because is_readonly takes precedence
        """
        # Arrange: make metadata readonly
        ro_metadata = {**basic_metadata, "ReadOnly": True}
        param = ArduPilotParameter(
            name="RO_FORCED",
            par_obj=Par(5.0, "@manual_override Some reason"),
            metadata=ro_metadata,
            forced_par=Par(42.0, "Must be 42"),
        )

        # Assert
        assert param.is_readonly
        assert not param.is_editable

    def test_calling_set_manual_override_with_same_state_is_noop(self) -> None:
        """
        Calling set_manual_override(False) when override is already off is a no-op.

        GIVEN: A forced parameter with manual override inactive (value/reason match file so not dirty)
        WHEN: set_manual_override(False) is called
        THEN: The parameter state is unchanged and is_dirty remains False
        """
        # Arrange: use a clean param where file value/reason == forced value/reason
        clean_param = ArduPilotParameter(
            name="CLEAN",
            par_obj=Par(42.0, "Must be 42"),
            forced_par=Par(42.0, "Must be 42"),
        )
        assert not clean_param.is_manual_override
        assert not clean_param.is_dirty

        # Act
        clean_param.set_manual_override(False)

        # Assert: no change, no dirty
        assert not clean_param.is_manual_override
        assert not clean_param.is_dirty
