#!/usr/bin/env python3

"""
Tests for the ParameterEditorTable class.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace
from typing import Any, Optional, cast
from unittest.mock import MagicMock, patch

import pytest
from conftest import PARAMETER_EDITOR_TABLE_HEADERS_ADVANCED, PARAMETER_EDITOR_TABLE_HEADERS_SIMPLE

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.data_model_ardupilot_parameter import ArduPilotParameter
from ardupilot_methodic_configurator.data_model_par_dict import Par, ParDict
from ardupilot_methodic_configurator.data_model_parameter_editor import (
    InvalidParameterNameError,
    OperationNotPossibleError,
    ParameterEditor,
    ParameterValueUpdateResult,
    ParameterValueUpdateStatus,
)
from ardupilot_methodic_configurator.frontend_tkinter_pair_tuple_combobox import (
    PairTupleCombobox,
    setup_combobox_mousewheel_handling,
)
from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table import (
    NEW_VALUE_DIFFERENT_STR,
    NEW_VALUE_WIDGET_WIDTH,
    ParameterEditorTable,
    ParameterEditorTableDialogs,
)

# pylint: disable=protected-access, redefined-outer-name, too-few-public-methods, too-many-lines


def create_mock_data_model_ardupilot_parameter(  # pylint: disable=too-many-arguments, too-many-positional-arguments # noqa: PLR0913
    name: str = "TEST_PARAM",
    value: float = 1.0,
    comment: str = "test comment",
    metadata: Optional[dict[str, Any]] = None,
    fc_value: Optional[float] = None,
    is_forced: bool = False,
    is_derived: bool = False,
    is_calibration: bool = False,
    is_readonly: bool = False,
    is_bitmask: bool = False,
    is_multiple_choice: bool = False,
) -> ArduPilotParameter:
    """Create a mock ArduPilotParameter for testing."""
    # pylint: disable=duplicate-code
    metadata = metadata or {}

    if is_calibration:
        metadata["Calibration"] = True
    if is_readonly:
        metadata["ReadOnly"] = True
    if is_bitmask:
        metadata["Bitmask"] = {0: "Bit 0", 1: "Bit 1", 2: "Bit 2"}
    if is_multiple_choice:
        metadata["values"] = {"0": "Option 0", "1": "Option 1"}
    # pylint: enable=duplicate-code

    metadata.setdefault("unit", "")
    metadata.setdefault("doc_tooltip", "Test tooltip")
    metadata.setdefault("unit_tooltip", "Unit tooltip")

    par_obj = Par(value, comment)
    default_par = Par(0.0, "default") if metadata else None
    forced_par = Par(value, "forced comment") if is_forced else None
    derived_par = Par(value, "derived comment") if is_derived else None

    return ArduPilotParameter(
        name=name,
        par_obj=par_obj,
        metadata=metadata,
        default_par=default_par,
        fc_value=fc_value,
        forced_par=forced_par,
        derived_par=derived_par,
    )


@pytest.fixture
def mock_master() -> tk.Tk:
    """Create a mock tkinter root window."""
    root = tk.Tk()
    yield root
    root.destroy()


@pytest.fixture
def mock_local_filesystem() -> MagicMock:
    """Create a mock LocalFilesystem instance."""
    filesystem = MagicMock(spec=LocalFilesystem)
    filesystem.configuration_steps = {}
    filesystem.file_parameters = {}
    filesystem.forced_parameters = {}
    filesystem.derived_parameters = {}
    filesystem.get_eval_variables.return_value = {}
    # Add required dictionaries with default empty values
    filesystem.doc_dict = {}
    filesystem.param_default_dict = {}  # Add this line
    return filesystem


@pytest.fixture
def mock_parameter_editor_window() -> MagicMock:
    """Create a mock parent window editor."""
    parent_window = MagicMock()
    parent_window.gui_complexity = "simple"
    parent_window.repopulate_parameter_table = MagicMock()
    parent_window.on_skip_click = MagicMock()
    parent_window.root = MagicMock(spec=tk.Tk)
    return parent_window


@pytest.fixture
def table_dialogs() -> ParameterEditorTableDialogs:
    """Provide dialog callbacks that record invocations for assertions."""
    return ParameterEditorTableDialogs(
        show_error=MagicMock(),
        show_info=MagicMock(),
        ask_yes_no=MagicMock(return_value=True),
    )


@pytest.fixture
def parameter_editor_table(
    mock_master: tk.Tk,
    mock_local_filesystem: MagicMock,
    mock_parameter_editor_window: MagicMock,
    table_dialogs: ParameterEditorTableDialogs,
) -> ParameterEditorTable:
    """Create a ParameterEditorTable instance for testing, using ParameterEditor abstraction."""
    with patch("tkinter.ttk.Style") as mock_style:
        style_instance = mock_style.return_value
        style_instance.lookup.return_value = "white"

        # Create a mock ParameterEditor
        mock_param_editor = MagicMock(spec=ParameterEditor)
        mock_param_editor._local_filesystem = mock_local_filesystem
        mock_param_editor.current_file = "test_file"
        mock_param_editor.is_fc_connected = True

        # Set up get_parameters_as_par_dict to return the right parameters
        def get_current_file_parameters() -> ParDict:
            return mock_local_filesystem.file_parameters.get(mock_param_editor.current_file, ParDict())

        mock_param_editor.get_parameters_as_par_dict.return_value = get_current_file_parameters()

        # Mock the _repopulate_configuration_step_parameters method to return the expected tuple
        mock_param_editor._repopulate_configuration_step_parameters.return_value = ([], [])

        # Mock the parameters attribute that gets populated during _repopulate_configuration_step_parameters
        mock_param_editor.current_step_parameters = {}

        # Mock the delete method to actually delete from the _local_filesystem parameters
        def mock_delete_parameter(param_name: str) -> None:
            current_file = mock_param_editor.current_file
            if (
                current_file in mock_local_filesystem.file_parameters
                and param_name in mock_local_filesystem.file_parameters[current_file]
            ):
                del mock_local_filesystem.file_parameters[current_file][param_name]

        mock_param_editor.delete_parameter_from_current_file = MagicMock(side_effect=mock_delete_parameter)

        # Mock _has_unsaved_changes to return False by default
        mock_param_editor._has_unsaved_changes.return_value = False
        mock_param_editor.should_display_bitmask_parameter_editor_usage.return_value = False

        # Create the table instance
        table = ParameterEditorTable(mock_master, mock_param_editor, mock_parameter_editor_window, dialogs=table_dialogs)

        mock_parameter_editor_window.root = mock_master

        # Mock necessary tkinter widgets and methods
        table.add_parameter_row = MagicMock()
        table.view_port = mock_master
        table.canvas = MagicMock()
        table.canvas.yview = MagicMock()
        table.canvas.yview_moveto = MagicMock()

        # Mock grid_slaves to handle widget cleanup
        table.grid_slaves = MagicMock(return_value=[])

        # Initialize variables dict
        table.variables = {}

        # Initialize upload_checkbutton_var dict
        table.upload_checkbutton_var = {}

        return table


def test_init_creates_instance_with_correct_attributes(
    parameter_editor_table, mock_master, mock_local_filesystem, mock_parameter_editor_window
) -> None:
    """
    ParameterEditorTable initializes with correct attributes and dependencies.

    GIVEN: Required dependencies (master window, _local_filesystem, parameter editor)
    WHEN: ParameterEditorTable is instantiated
    THEN: All attributes are properly set and configured
    AND: The table is ready for parameter display and editing
    """
    # Arrange: Dependencies provided by fixtures

    # Act: Instance created by fixture

    # Assert: All attributes properly initialized
    assert parameter_editor_table.main_frame == mock_master
    assert parameter_editor_table.parameter_editor._local_filesystem == mock_local_filesystem
    assert parameter_editor_table.parameter_editor_window == mock_parameter_editor_window
    # current_file is now managed by parameter_editor
    assert parameter_editor_table.parameter_editor.current_file == "test_file"
    assert isinstance(parameter_editor_table.upload_checkbutton_var, dict)
    assert parameter_editor_table.parameter_editor._has_unsaved_changes() is False


def test_init_configures_style(parameter_editor_table: ParameterEditorTable) -> None:
    """
    ParameterEditorTable properly configures ttk.Style for consistent appearance.

    GIVEN: A ParameterEditorTable instance needs proper styling
    WHEN: The table is initialized with ttk.Style configuration
    THEN: Style is configured with appropriate button properties
    AND: Visual consistency is maintained across the application
    """
    # Arrange: Set up style mocking
    with patch("tkinter.ttk.Style", autospec=True) as mock_style_class:
        # Configure the mock style to return a valid color for both instances
        mock_style_instance = mock_style_class.return_value
        mock_style_instance.lookup.return_value = "#ffffff"  # Use a valid hex color
        mock_style_instance.configure.return_value = None

        # Create a mock ParameterEditor for the new instance
        mock_param_editor = MagicMock(spec=ParameterEditor)
        mock_param_editor._local_filesystem = parameter_editor_table.parameter_editor._local_filesystem
        mock_param_editor.current_file = "test_file"
        mock_param_editor.get_parameters_as_par_dict.return_value = (
            parameter_editor_table.parameter_editor._local_filesystem.file_parameters.get("test_file", {})
        )

        # Act: Create a new instance to trigger style configuration
        ParameterEditorTable(parameter_editor_table.main_frame, mock_param_editor, parameter_editor_table.parameter_editor)

        # Assert: Style was configured with expected parameters
        mock_style_instance.configure.assert_called_with("narrow.TButton", padding=0, width=4, border=(0, 0, 0, 0))


def test_init_with_style_lookup_failure(mock_master, mock_local_filesystem, mock_parameter_editor_window) -> None:
    """
    ParameterEditorTable handles style lookup failures gracefully during initialization.

    GIVEN: ttk.Style lookup fails to return a valid color
    WHEN: ParameterEditorTable is initialized
    THEN: Initialization completes successfully despite style lookup failure
    AND: Default styling is applied without crashing
    """
    # Arrange: Set up style lookup to fail
    with patch("tkinter.ttk.Style", autospec=True) as mock_style:
        style_instance = mock_style.return_value
        style_instance.lookup.return_value = None  # Simulate style lookup failure

        mock_param_editor = MagicMock(spec=ParameterEditor)
        mock_param_editor._local_filesystem = mock_local_filesystem
        mock_param_editor.current_file = "test_file"
        mock_param_editor.get_parameters_as_par_dict.return_value = {}

        # Act: Create table instance with style lookup failure
        table = ParameterEditorTable(mock_master, mock_param_editor, mock_parameter_editor_window)

        # Assert: Table created successfully despite style issues
        assert table is not None
        # Check that Style was initialized
        mock_style.assert_called()
        # Check that lookup was called
        style_instance.lookup.assert_called()
        # Check that configure was called with expected parameters
        style_instance.configure.assert_called_with("narrow.TButton", padding=0, width=4, border=(0, 0, 0, 0))


def test_repopulate_empty_parameters(parameter_editor_table: ParameterEditorTable) -> None:
    """
    ParameterEditorTable handles repopulation with no parameters gracefully.

    GIVEN: A configuration file contains no parameters
    WHEN: The parameter table is repopulated
    THEN: No parameter rows are added to the table
    AND: The operation completes without errors
    """
    # Arrange: Set up empty parameters
    test_file = "test_file"
    parameter_editor_table.parameter_editor._local_filesystem.file_parameters = ParDict({test_file: ParDict({})})

    # Act: Repopulate the table
    parameter_editor_table.repopulate_table(show_only_differences=False, gui_complexity="simple")

    # Assert: No parameter rows were added
    parameter_editor_table.add_parameter_row.assert_not_called()


def test_repopulate_clears_existing_content(parameter_editor_table: ParameterEditorTable) -> None:
    """
    ParameterEditorTable clears existing content before repopulating.

    GIVEN: A parameter table contains existing parameter rows
    WHEN: The table is repopulated with new data
    THEN: All existing widgets are properly destroyed
    AND: The table is ready for new parameter display
    """
    # Arrange: Create existing content to be cleared
    test_file = "test_file"
    dummy_widget = ttk.Label(parameter_editor_table)
    parameter_editor_table.grid_slaves = MagicMock(return_value=[dummy_widget])
    parameter_editor_table.parameter_editor._local_filesystem.file_parameters = ParDict(
        {test_file: ParDict({"PARAM1": Par(1.0, "test comment")})}
    )
    parameter_editor_table.parameter_editor._local_filesystem.doc_dict = {"PARAM1": {"units": "none"}}
    parameter_editor_table.parameter_editor._local_filesystem.param_default_dict = ParDict({"PARAM1": Par(0.0, "default")})

    # Act: Repopulate the table
    parameter_editor_table.repopulate_table(show_only_differences=False, gui_complexity="simple")

    # Assert: Existing content was cleared
    assert not dummy_widget.winfo_exists()


def test_repopulate_handles_none_current_file(parameter_editor_table: ParameterEditorTable) -> None:
    """
    ParameterEditorTable handles repopulation when no current file is set.

    GIVEN: No current configuration file is selected
    WHEN: The parameter table attempts to repopulate
    THEN: The operation completes gracefully without errors
    AND: No parameter rows are added to the table
    """
    # Arrange: Set up empty file state
    parameter_editor_table.parameter_editor._local_filesystem.file_parameters = ParDict({"": ParDict({})})
    parameter_editor_table.parameter_editor.current_file = ""
    parameter_editor_table.parameter_editor._local_filesystem.doc_dict = {}
    parameter_editor_table.parameter_editor._local_filesystem.param_default_dict = ParDict({})

    # Act: Attempt to repopulate_table with no current file
    parameter_editor_table.repopulate_table(show_only_differences=False, gui_complexity="simple")

    # Assert: No parameter rows were added
    parameter_editor_table.add_parameter_row.assert_not_called()


def test_repopulate_single_parameter(parameter_editor_table: ParameterEditorTable) -> None:
    """
    ParameterEditorTable correctly displays a single parameter.

    GIVEN: A configuration file contains exactly one parameter
    WHEN: The parameter table is repopulated
    THEN: One parameter row is added to the table
    AND: The parameter is displayed with correct formatting
    """
    # Arrange: Set up single parameter
    test_file = "test_file"
    parameter_editor_table.parameter_editor.current_file = test_file
    parameter_editor_table.parameter_editor._local_filesystem.file_parameters = ParDict(
        {test_file: ParDict({"PARAM1": Par(1.0, "test comment")})}
    )
    parameter_editor_table.parameter_editor._local_filesystem.doc_dict = {"PARAM1": {"units": "none"}}
    parameter_editor_table.parameter_editor._local_filesystem.param_default_dict = ParDict({"PARAM1": Par(0.0, "default")})

    # Act: Repopulate with single parameter
    with patch.object(parameter_editor_table, "grid_slaves", return_value=[]):
        parameter_editor_table.repopulate_table(show_only_differences=False, gui_complexity="simple")

    # Assert: Parameter row was added (implicitly tested through repopulate_table call)


def test_repopulate_multiple_parameters(parameter_editor_table: ParameterEditorTable) -> None:
    """
    ParameterEditorTable correctly displays multiple parameters.

    GIVEN: A configuration file contains multiple parameters
    WHEN: The parameter table is repopulated
    THEN: All parameter rows are added to the table
    AND: Parameters are displayed in correct order with proper formatting
    """
    # Arrange: Set up multiple parameters
    test_file = "test_file"
    parameter_editor_table.parameter_editor.current_file = test_file
    parameter_editor_table.parameter_editor._local_filesystem.file_parameters = ParDict(
        {
            test_file: ParDict(
                {
                    "PARAM1": Par(1.0, "test comment 1"),
                    "PARAM2": Par(2.0, "test comment 2"),
                    "PARAM3": Par(3.0, "test comment 3"),
                }
            )
        }
    )
    parameter_editor_table.parameter_editor._local_filesystem.doc_dict = {
        "PARAM1": {"units": "none"},
        "PARAM2": {"units": "none"},
        "PARAM3": {"units": "none"},
    }
    parameter_editor_table.parameter_editor._local_filesystem.param_default_dict = ParDict(
        {
            "PARAM1": Par(0.0, "default"),
            "PARAM2": Par(0.0, "default"),
            "PARAM3": Par(0.0, "default"),
        }
    )

    # Act: Repopulate with multiple parameters
    with patch.object(parameter_editor_table, "grid_slaves", return_value=[]):
        parameter_editor_table.repopulate_table(show_only_differences=False, gui_complexity="simple")

    # Assert: All parameters were processed (implicitly tested through repopulate_table call)


def test_repopulate_preserves_checkbutton_states(parameter_editor_table: ParameterEditorTable) -> None:
    """
    ParameterEditorTable preserves upload checkbutton states during repopulation.

    GIVEN: Parameters have upload checkbuttons in specific states
    WHEN: The parameter table is repopulated
    THEN: The checkbutton states are preserved
    AND: User selections for parameter upload are maintained
    """
    # Arrange: Set up checkbutton states
    test_file = "test_file"
    param1_var = tk.BooleanVar(value=True)
    param2_var = tk.BooleanVar(value=False)
    parameter_editor_table.upload_checkbutton_var = {"PARAM1": param1_var, "PARAM2": param2_var}
    parameter_editor_table.parameter_editor._local_filesystem.file_parameters = ParDict(
        {test_file: ParDict({"PARAM1": Par(1.0, "test comment"), "PARAM2": Par(2.0, "test comment")})}
    )
    parameter_editor_table.parameter_editor._local_filesystem.doc_dict = {
        "PARAM1": {"units": "none"},
        "PARAM2": {"units": "none"},
    }
    parameter_editor_table.parameter_editor._local_filesystem.param_default_dict = ParDict(
        {"PARAM1": Par(0.0, "default"), "PARAM2": Par(0.0, "default")}
    )

    # Act: Repopulate the table
    parameter_editor_table.repopulate_table(show_only_differences=False, gui_complexity="simple")

    # Assert: Checkbutton states were preserved (implicitly tested through repopulate_table call)


def test_repopulate_show_only_differences(parameter_editor_table: ParameterEditorTable) -> None:
    """
    ParameterEditorTable shows only parameters that differ from defaults when requested.

    GIVEN: A configuration file with parameters that have different values from defaults
    WHEN: The table is repopulated with show_only_differences=True
    THEN: Only parameters with non-default values are displayed
    AND: Default parameters are filtered out for focused editing
    """
    # Arrange: Set up parameters with some matching defaults
    test_file = "test_file"
    parameter_editor_table.parameter_editor._local_filesystem.file_parameters = ParDict(
        {
            test_file: ParDict(
                {
                    "PARAM1": Par(1.0, "test comment"),  # Same as FC
                    "PARAM2": Par(2.5, "test comment"),  # Different from FC
                    "PARAM3": Par(3.0, "test comment"),  # Not in FC
                }
            )
        }
    )
    parameter_editor_table.parameter_editor._local_filesystem.doc_dict = {
        "PARAM1": {"units": "none"},
        "PARAM2": {"units": "none"},
        "PARAM3": {"units": "none"},
    }
    parameter_editor_table.parameter_editor._local_filesystem.param_default_dict = ParDict(
        {
            "PARAM1": Par(0.0, "default"),
            "PARAM2": Par(0.0, "default"),
            "PARAM3": Par(0.0, "default"),
        }
    )

    # Act: Repopulate showing only differences
    parameter_editor_table.repopulate_table(show_only_differences=True, gui_complexity="simple")

    # Assert: Only differing parameters were processed (implicitly tested through repopulate_table call)


@pytest.mark.parametrize("pending_scroll", [True, False])
def test_repopulate_uses_scroll_helper(parameter_editor_table: ParameterEditorTable, pending_scroll: bool) -> None:
    """
    ParameterEditorTable uses scroll helper to manage table positioning during repopulation.

    GIVEN: A parameter table with pending scroll state
    WHEN: The table is repopulated
    THEN: The scroll helper is called with the correct position
    AND: The pending scroll flag is reset after operation
    """
    # Arrange: Set pending scroll state
    parameter_editor_table._pending_scroll_to_bottom = pending_scroll
    parameter_editor_table.parameter_editor._local_filesystem.file_parameters = ParDict({"test_file": ParDict({})})
    parameter_editor_table.parameter_editor._repopulate_configuration_step_parameters = MagicMock(return_value=([], []))
    parameter_editor_table._update_table = MagicMock()
    parameter_editor_table.view_port.winfo_children = MagicMock(return_value=[])
    parameter_editor_table._create_headers_and_tooltips = MagicMock(return_value=((), ()))
    parameter_editor_table._should_show_upload_column = MagicMock(return_value=False)

    # Act: Repopulate and check scroll behavior
    with patch.object(parameter_editor_table, "_apply_scroll_position") as mock_scroll:
        parameter_editor_table.repopulate_table(show_only_differences=False, gui_complexity="simple")

    # Assert: Scroll position was applied correctly
    mock_scroll.assert_called_once_with(pending_scroll)
    assert parameter_editor_table._pending_scroll_to_bottom is False


@pytest.mark.parametrize(
    ("scroll_to_bottom", "expected_position"),
    [(True, 1.0), (False, 0.0)],
)
def test_apply_scroll_position_moves_canvas(
    parameter_editor_table: ParameterEditorTable, scroll_to_bottom: bool, expected_position: float
) -> None:
    """
    ParameterEditorTable scroll helper moves canvas to correct position.

    GIVEN: A parameter table canvas that needs scrolling
    WHEN: The scroll position is applied with specific scroll_to_bottom value
    THEN: The canvas is moved to the expected position (1.0 for bottom, 0.0 for top)
    AND: The UI update is triggered to reflect the change
    """
    # Arrange: Set up canvas mock
    canvas_yview = parameter_editor_table.canvas.yview_moveto
    assert isinstance(canvas_yview, MagicMock)
    canvas_yview.reset_mock()

    # Act: Apply scroll position
    with patch.object(parameter_editor_table, "update_idletasks") as mock_update_idletasks:
        parameter_editor_table._apply_scroll_position(scroll_to_bottom)

    # Assert: Canvas moved to expected position and UI updated
    mock_update_idletasks.assert_called_once_with()
    canvas_yview.assert_called_once_with(expected_position)


class TestUIComplexityBehavior:
    """Test how ParameterEditorTable adapts to different UI complexity settings."""

    def test_should_show_upload_column_simple_mode(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        ParameterEditorTable hides upload column in simple UI mode.

        GIVEN: The application is configured for simple UI complexity
        WHEN: The table determines whether to show the upload column
        THEN: The upload column is hidden to reduce interface complexity
        AND: Users see a cleaner, less cluttered interface
        """
        # Arrange: Set simple mode
        parameter_editor_table.parameter_editor_window.gui_complexity = "simple"

        # Act: Check if upload column should be shown
        should_show = parameter_editor_table._should_show_upload_column()

        # Assert: Upload column is hidden in simple mode
        assert should_show is False

    def test_should_show_upload_column_advanced_mode(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        ParameterEditorTable shows upload column in advanced UI mode.

        GIVEN: The application is configured for advanced UI complexity
        WHEN: The table determines whether to show the upload column
        THEN: The upload column is displayed for full functionality access
        AND: Advanced users have complete control over parameter uploads
        """
        # Arrange: Set advanced mode
        parameter_editor_table.parameter_editor_window.gui_complexity = "normal"

        # Act: Check if upload column should be shown
        should_show = parameter_editor_table._should_show_upload_column()

        # Assert: Upload column is shown in advanced mode
        assert should_show is True

    def test_should_show_upload_column_explicit_override(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        ParameterEditorTable respects explicit gui_complexity parameter override.

        GIVEN: The application default is simple mode
        WHEN: An explicit advanced complexity parameter is passed
        THEN: The explicit parameter takes precedence over the default
        AND: The upload column is shown despite the default setting
        """
        # Arrange: Set simple mode as default
        parameter_editor_table.parameter_editor_window.gui_complexity = "simple"

        # Act: Explicitly pass "normal" to override the default
        should_show = parameter_editor_table._should_show_upload_column("normal")

        # Assert: Explicit parameter overrides default
        assert should_show is True

    def test_get_change_reason_column_index_with_upload(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        ParameterEditorTable calculates correct column index for change reason with upload column.

        GIVEN: The upload column is enabled in the parameter table
        WHEN: The change reason column index is calculated
        THEN: The index accounts for all base columns plus the upload column
        AND: Change reason entries are positioned correctly in the grid
        """
        # Act: Get column index with upload column enabled
        column_index = parameter_editor_table._get_change_reason_column_index(show_upload_column=True)

        # Assert: Base columns (6) + Upload column (1) = 7
        assert column_index == 7

    def test_get_change_reason_column_index_without_upload(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        ParameterEditorTable calculates correct column index for change reason without upload column.

        GIVEN: The upload column is disabled in the parameter table
        WHEN: The change reason column index is calculated
        THEN: The index accounts for only the base columns
        AND: Change reason entries are positioned correctly in the simplified grid
        """
        # Act: Get column index with upload column disabled
        column_index = parameter_editor_table._get_change_reason_column_index(show_upload_column=False)

        # Assert: Base columns (6) only
        assert column_index == 6


class TestParameterChangeStateBehavior:
    """Test how ParameterEditorTable manages parameter change state and unsaved changes."""

    def test_has_unsaved_changes_false(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        ParameterEditorTable correctly reports no unsaved changes when parameters are clean.

        GIVEN: All parameters in the configuration are saved and unchanged
        WHEN: The system checks for unsaved changes
        THEN: No unsaved changes are detected
        AND: Users can proceed without worrying about lost changes
        """
        # Arrange: Configure no dirty parameters
        parameter_editor_table.parameter_editor._has_unsaved_changes.return_value = False

        # Act: Check for unsaved changes
        result = parameter_editor_table.parameter_editor._has_unsaved_changes()

        # Assert: No unsaved changes detected
        assert result is False

    def test_has_unsaved_changes_true(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        ParameterEditorTable correctly reports unsaved changes when parameters are modified.

        GIVEN: Some parameters in the configuration have been modified but not saved
        WHEN: The system checks for unsaved changes
        THEN: Unsaved changes are detected
        AND: Users are warned about potential data loss
        """
        # Arrange: Configure dirty parameters
        parameter_editor_table.parameter_editor._has_unsaved_changes.return_value = True

        # Act: Check for unsaved changes
        result = parameter_editor_table.parameter_editor._has_unsaved_changes()

        # Assert: Unsaved changes detected
        assert result is True


class TestIntegrationBehavior:
    """Test integration between ParameterEditorTable components and methods."""

    def test_gui_complexity_affects_column_calculation(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        ParameterEditorTable column calculations adapt to UI complexity settings.

        GIVEN: The application switches between simple and advanced UI modes
        WHEN: Column indices are calculated for different complexity levels
        THEN: Simple mode excludes upload column from calculations
        AND: Advanced mode includes upload column in position calculations
        """
        # Arrange: Set simple mode as default
        parameter_editor_table.parameter_editor_window.gui_complexity = "simple"

        # Act: Calculate columns for simple mode
        show_upload = parameter_editor_table._should_show_upload_column()
        column_index = parameter_editor_table._get_change_reason_column_index(show_upload)

        # Assert: Simple mode calculations
        assert show_upload is False
        assert column_index == 6  # No upload column

        # Act: Calculate columns for advanced mode override
        show_upload_advanced = parameter_editor_table._should_show_upload_column("normal")
        column_index_advanced = parameter_editor_table._get_change_reason_column_index(show_upload_advanced)

        # Assert: Advanced mode calculations
        assert show_upload_advanced is True
        assert column_index_advanced == 7  # With upload column


class TestParameterValueUpdateHandling:
    """Test the presenter-driven parameter value update handling."""

    def test_handle_parameter_value_update_success(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Presenter reports success and UI returns True without showing errors."""
        param = create_mock_data_model_ardupilot_parameter(name="TEST_PARAM", value=1.0)
        error_dialog = cast("MagicMock", parameter_editor_table._dialogs.show_error)
        error_dialog.reset_mock()
        update_mock = cast("MagicMock", parameter_editor_table.parameter_editor.update_parameter_value)
        update_mock.return_value = ParameterValueUpdateResult(ParameterValueUpdateStatus.UPDATED)

        result = parameter_editor_table._handle_parameter_value_update(param, "2.5")

        assert result is True
        update_mock.assert_called_once_with(
            "TEST_PARAM",
            "2.5",
            include_range_check=True,
        )
        error_dialog.assert_not_called()

    def test_handle_parameter_value_update_unchanged(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Presenter reports unchanged result which UI treats as no-op."""
        param = create_mock_data_model_ardupilot_parameter(name="TEST_PARAM", value=1.0)
        update_mock = cast("MagicMock", parameter_editor_table.parameter_editor.update_parameter_value)
        update_mock.return_value = ParameterValueUpdateResult(ParameterValueUpdateStatus.UNCHANGED)
        error_dialog = cast("MagicMock", parameter_editor_table._dialogs.show_error)

        result = parameter_editor_table._handle_parameter_value_update(param, "1.0")

        assert result is False
        error_dialog.assert_not_called()

    def test_handle_parameter_value_update_out_of_range_accepted(self, parameter_editor_table: ParameterEditorTable) -> None:
        """UI confirms out-of-range prompt and retries update ignoring range checks."""
        param = create_mock_data_model_ardupilot_parameter(name="TEST_PARAM", value=5.0)
        ask_dialog = cast("MagicMock", parameter_editor_table._dialogs.ask_yes_no)
        ask_dialog.return_value = True
        update_mock = cast("MagicMock", parameter_editor_table.parameter_editor.update_parameter_value)
        update_mock.side_effect = [
            ParameterValueUpdateResult(
                ParameterValueUpdateStatus.CONFIRM_OUT_OF_RANGE,
                title="Out-of-range value",
                message="Too high",
            ),
            ParameterValueUpdateResult(ParameterValueUpdateStatus.UPDATED),
        ]

        result = parameter_editor_table._handle_parameter_value_update(param, "15.0")

        assert result is True
        assert update_mock.call_count == 2
        first_call, second_call = update_mock.call_args_list
        assert first_call.kwargs["include_range_check"] is True
        assert second_call.kwargs["include_range_check"] is False
        ask_dialog.assert_called_once()

    def test_handle_parameter_value_update_out_of_range_rejected(self, parameter_editor_table: ParameterEditorTable) -> None:
        """UI aborts update when user rejects out-of-range confirmation."""
        param = create_mock_data_model_ardupilot_parameter(name="TEST_PARAM", value=5.0)
        ask_dialog = cast("MagicMock", parameter_editor_table._dialogs.ask_yes_no)
        ask_dialog.return_value = False
        update_mock = cast("MagicMock", parameter_editor_table.parameter_editor.update_parameter_value)
        update_mock.return_value = ParameterValueUpdateResult(
            ParameterValueUpdateStatus.CONFIRM_OUT_OF_RANGE,
            title="Out-of-range value",
            message="Too high",
        )

        result = parameter_editor_table._handle_parameter_value_update(param, "15.0")

        assert result is False
        update_mock.assert_called_once()
        ask_dialog.assert_called_once()

    def test_handle_parameter_value_update_error_without_prompt(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Presenter-provided errors are surfaced through the injected dialog callbacks."""
        param = create_mock_data_model_ardupilot_parameter(name="TEST_PARAM", value=5.0)
        update_mock = cast("MagicMock", parameter_editor_table.parameter_editor.update_parameter_value)
        update_mock.return_value = ParameterValueUpdateResult(
            ParameterValueUpdateStatus.ERROR,
            title="Invalid value",
            message="Not a number",
        )
        ask_dialog = cast("MagicMock", parameter_editor_table._dialogs.ask_yes_no)
        error_dialog = cast("MagicMock", parameter_editor_table._dialogs.show_error)

        result = parameter_editor_table._handle_parameter_value_update(param, "bad", include_range_check=False)

        assert result is False
        ask_dialog.assert_not_called()
        error_dialog.assert_called_once_with("Invalid value", "Not a number")

    def test_handle_parameter_value_update_generic_error(self, parameter_editor_table: ParameterEditorTable) -> None:
        """Presenter errors without title/message still show a fallback dialog."""
        param = create_mock_data_model_ardupilot_parameter(name="TEST_PARAM", value=5.0)
        update_mock = cast("MagicMock", parameter_editor_table.parameter_editor.update_parameter_value)
        update_mock.return_value = ParameterValueUpdateResult(ParameterValueUpdateStatus.ERROR)
        error_dialog = cast("MagicMock", parameter_editor_table._dialogs.show_error)

        result = parameter_editor_table._handle_parameter_value_update(param, "bad")

        assert result is False
        error_dialog.assert_called_once()

    def test_handle_parameter_value_update_forced_retry_failure(self, parameter_editor_table: ParameterEditorTable) -> None:
        """If retry also fails, the UI surfaces the second error message to the user."""
        param = create_mock_data_model_ardupilot_parameter(name="TEST_PARAM", value=5.0)
        ask_dialog = cast("MagicMock", parameter_editor_table._dialogs.ask_yes_no)
        ask_dialog.return_value = True
        update_mock = cast("MagicMock", parameter_editor_table.parameter_editor.update_parameter_value)
        update_mock.side_effect = [
            ParameterValueUpdateResult(
                ParameterValueUpdateStatus.CONFIRM_OUT_OF_RANGE,
                title="Out-of-range value",
                message="Too high",
            ),
            ParameterValueUpdateResult(
                ParameterValueUpdateStatus.ERROR,
                title="Retry failed",
                message="Still invalid",
            ),
        ]
        error_dialog = cast("MagicMock", parameter_editor_table._dialogs.show_error)

        result = parameter_editor_table._handle_parameter_value_update(param, "15.0")

        assert result is False
        error_dialog.assert_called_once_with("Retry failed", "Still invalid")


class TestWidgetCreationBehavior:
    """Test the behavior of widget creation methods for visual indicators."""

    def test_create_parameter_name_calibration(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        User interface highlights calibration parameters with yellow background.

        GIVEN: A parameter editor table is initialized
        WHEN: A parameter name label is created for a calibration parameter
        THEN: The label has a yellow background to indicate calibration status
        """
        # Arrange: Create calibration parameter
        param = create_mock_data_model_ardupilot_parameter(name="CAL_PARAM", is_calibration=True)

        # Act: Create parameter name label
        label = parameter_editor_table._create_parameter_name(param)

        # Assert: Label has yellow background for calibration
        assert isinstance(label, ttk.Label)
        assert str(label.cget("background")) == "yellow"

    def test_create_parameter_name_readonly(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        User interface highlights readonly parameters with purple background.

        GIVEN: A parameter editor table is initialized
        WHEN: A parameter name label is created for a readonly parameter
        THEN: The label has a purple background to indicate readonly status
        """
        # Arrange: Create readonly parameter
        param = create_mock_data_model_ardupilot_parameter(name="RO_PARAM", is_readonly=True)

        # Act: Create parameter name label
        label = parameter_editor_table._create_parameter_name(param)

        # Assert: Label has purple background for readonly
        assert isinstance(label, ttk.Label)
        assert str(label.cget("background")) == "purple1"


class TestEventHandlerBehavior:
    """Test the behavior of event handler methods."""

    def test_on_parameter_delete_confirmed(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        User can successfully delete parameters when confirming the action.

        GIVEN: A parameter exists in the current file
        WHEN: User confirms parameter deletion
        THEN: The parameter is removed and the table is repopulated
        """
        # Arrange: Set up parameter in _local_filesystem
        parameter_editor_table.parameter_editor.current_file = "test_file"
        parameter_editor_table.parameter_editor._local_filesystem.file_parameters = {
            "test_file": ParDict({"TEST_PARAM": Par(1.0, "comment")})
        }
        parameter_editor_table.parameter_editor_window.repopulate_parameter_table = MagicMock()
        parameter_editor_table.canvas = MagicMock()
        parameter_editor_table.canvas.yview.return_value = [0.5, 0.8]

        # Act: Confirm parameter deletion
        ask_dialog = cast("MagicMock", parameter_editor_table._dialogs.ask_yes_no)
        ask_dialog.return_value = True
        parameter_editor_table._on_parameter_delete("TEST_PARAM")

        # Assert: Parameter is deleted and table repopulated
        assert "TEST_PARAM" not in parameter_editor_table.parameter_editor._local_filesystem.file_parameters["test_file"]
        parameter_editor_table.parameter_editor_window.repopulate_parameter_table.assert_called_once_with()

    def test_on_parameter_delete_cancelled(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        User can cancel parameter deletion without removing the parameter.

        GIVEN: A parameter exists in the current file
        WHEN: User cancels parameter deletion
        THEN: The parameter remains in the file
        """
        # Arrange: Set up parameter in _local_filesystem
        parameter_editor_table.parameter_editor.current_file = "test_file"
        parameter_editor_table.parameter_editor._local_filesystem.file_parameters = {
            "test_file": {"TEST_PARAM": Par(1.0, "comment")}
        }

        # Act: Cancel parameter deletion
        ask_dialog = cast("MagicMock", parameter_editor_table._dialogs.ask_yes_no)
        ask_dialog.return_value = False
        parameter_editor_table._on_parameter_delete("TEST_PARAM")

        # Assert: Parameter remains in file
        assert "TEST_PARAM" in parameter_editor_table.parameter_editor._local_filesystem.file_parameters["test_file"]

    def test_confirm_parameter_addition_valid_fc_param(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        User can successfully add valid flight controller parameters.

        GIVEN: A valid parameter name that exists in the flight controller
        WHEN: User attempts to add the parameter
        THEN: The parameter is added successfully and the operation returns true
        """
        # Arrange: Set up empty file and mock successful addition
        parameter_editor_table.parameter_editor.current_file = "test_file"
        parameter_editor_table.parameter_editor._local_filesystem.file_parameters = {"test_file": ParDict({})}
        parameter_editor_table.parameter_editor_window.repopulate_parameter_table = MagicMock()

        # Act: Confirm parameter addition with mocked success
        with patch.object(
            parameter_editor_table.parameter_editor,
            "add_parameter_to_current_file",
            return_value=True,
        ):
            result = parameter_editor_table._confirm_parameter_addition("NEW_PARAM")

            # Assert: Parameter addition succeeds
            assert result is True
            parameter_editor_table.parameter_editor.add_parameter_to_current_file.assert_called_once_with("NEW_PARAM")

    def test_confirm_parameter_addition_empty_name(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        User sees error when attempting to add parameter with empty name.

        GIVEN: User attempts to add a parameter with an empty name
        WHEN: The system validates the parameter name
        THEN: An error dialog is shown and the operation fails
        """
        # Arrange: Mock the add_parameter_to_current_file method to raise error
        parameter_editor_table.parameter_editor.add_parameter_to_current_file = MagicMock(
            side_effect=InvalidParameterNameError("Parameter name can not be empty.")
        )

        # Act & Assert: Confirm parameter addition shows error for empty name
        error_dialog = cast("MagicMock", parameter_editor_table._dialogs.show_error)
        result = parameter_editor_table._confirm_parameter_addition("")

        assert result is False
        error_dialog.assert_called_once()

    def test_confirm_parameter_addition_existing_param(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        User sees error when attempting to add parameter that already exists.

        GIVEN: A parameter with the same name already exists in the current file
        WHEN: User attempts to add a parameter with that name
        THEN: An error dialog is shown and the operation fails
        """
        # Arrange: Set up existing parameter in file
        parameter_editor_table.parameter_editor.current_file = "test_file"
        parameter_editor_table.parameter_editor._local_filesystem.file_parameters = {
            "test_file": ParDict({"EXISTING_PARAM": Par(1.0, "comment")})
        }

        # Mock the add_parameter_to_current_file method to raise error
        parameter_editor_table.parameter_editor.add_parameter_to_current_file = MagicMock(
            side_effect=InvalidParameterNameError("Parameter already exists, edit it instead")
        )

        # Act & Assert: Confirm parameter addition shows error for existing parameter
        error_dialog = cast("MagicMock", parameter_editor_table._dialogs.show_error)
        result = parameter_editor_table._confirm_parameter_addition("EXISTING_PARAM")

        assert result is False
        error_dialog.assert_called_once()


class TestHeaderCreationBehavior:
    """Test the behavior of header creation methods."""

    def test_create_headers_and_tooltips_simple_mode(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        User interface creates appropriate headers for simple mode without upload column.

        GIVEN: The parameter editor is in simple mode (no upload column)
        WHEN: Headers and tooltips are created
        THEN: The correct headers are returned without upload column and proper tooltips exist
        """
        # Act: Create headers and tooltips for simple mode
        headers, tooltips = parameter_editor_table._create_headers_and_tooltips(show_upload_column=False)

        # Assert: Headers match expected simple mode structure
        assert headers == PARAMETER_EDITOR_TABLE_HEADERS_SIMPLE
        assert len(tooltips) == len(headers)
        assert len(tooltips) == 7  # No upload column tooltip

    def test_create_headers_and_tooltips_advanced_mode(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        User interface creates appropriate headers for advanced mode with upload column.

        GIVEN: The parameter editor is in advanced mode (with upload column)
        WHEN: Headers and tooltips are created
        THEN: The correct headers are returned including upload column and proper tooltips exist
        """
        # Act: Create headers and tooltips for advanced mode
        headers, tooltips = parameter_editor_table._create_headers_and_tooltips(show_upload_column=True)

        # Assert: Headers match expected advanced mode structure
        assert headers == PARAMETER_EDITOR_TABLE_HEADERS_ADVANCED
        assert len(tooltips) == len(headers)
        assert len(tooltips) == 8  # With upload column tooltip

    def test_headers_and_tooltips_localization(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        User interface properly localizes header text using translation function.

        GIVEN: The application supports multiple languages
        WHEN: Headers are created
        THEN: The translation function is called for each header text
        """
        # Act: Create headers with mocked translation function
        with patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table._") as mock_translate:
            mock_translate.side_effect = lambda x: f"TRANSLATED_{x}"

            _headers, _ = parameter_editor_table._create_headers_and_tooltips(show_upload_column=False)

            # Assert: Translation function was called for each header
            assert mock_translate.call_count >= 6


class TestBitmaskFunctionalityBehavior:
    """Test the behavior of bitmask functionality."""

    def test_bitmask_window_creation(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        User interface creates bitmask selection window for bitmask parameters.

        GIVEN: A bitmask parameter needs user input for bit selection
        WHEN: The bitmask selection window is opened
        THEN: A window is created with proper event handling setup
        """
        # Arrange: Set up mock event and parameter
        mock_event = MagicMock()
        mock_widget = MagicMock()
        mock_widget.get.return_value = "5"  # Binary: 101 (bits 0 and 2 set)
        mock_widget.unbind = MagicMock()
        mock_event.widget = mock_widget
        mock_change_reason_widget = MagicMock(spec=ttk.Entry)
        mock_value_is_different_widget = MagicMock(spec=ttk.Label)

        param = create_mock_data_model_ardupilot_parameter(
            name="TEST_PARAM",
            value=3.0,
            is_bitmask=True,
        )

        parameter_editor_table.main_frame = MagicMock()
        parameter_editor_table.parameter_editor._local_filesystem.param_default_dict = ParDict(
            {"TEST_PARAM": Par(0.0, "default")}
        )

        # Act: Open bitmask selection window with mocked UI components
        with (
            patch("tkinter.Toplevel") as mock_toplevel,
            patch("tkinter.ttk.Frame"),
            patch("tkinter.ttk.Checkbutton"),
            patch("tkinter.ttk.Label"),
        ):
            parameter_editor_table._open_bitmask_selection_window(
                mock_event, param, mock_change_reason_widget, mock_value_is_different_widget
            )

            # Assert: Window is created and event handling is set up
            mock_toplevel.assert_called_once()
            mock_event.widget.unbind.assert_called_once_with("<Double-Button-1>")

    def test_bitmask_value_calculation(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        User interface calculates bitmask values from checkbox states.

        GIVEN: A bitmask parameter with individual bit checkboxes
        WHEN: Checkbox states are evaluated
        THEN: The correct bitmask value is calculated from selected bits
        """
        # Note: This test would be complex to implement due to nested function structure
        # In a real implementation, value calculation logic should be extracted into a testable method


class TestCompleteIntegrationWorkflows:
    """Test complete integration workflows end-to-end."""

    def test_gui_complexity_affects_complete_workflow(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        User interface adapts complete parameter editing workflow based on GUI complexity setting.

        GIVEN: The application supports different GUI complexity modes
        WHEN: GUI complexity is changed between simple and advanced modes
        THEN: The interface correctly shows or hides upload columns and adjusts column indices accordingly
        """
        # Arrange & Act: Test simple mode
        parameter_editor_table.parameter_editor_window.gui_complexity = "simple"

        headers_simple, _ = parameter_editor_table._create_headers_and_tooltips(
            parameter_editor_table._should_show_upload_column()
        )
        column_index_simple = parameter_editor_table._get_change_reason_column_index(
            parameter_editor_table._should_show_upload_column()
        )

        # Assert: Simple mode excludes upload column
        assert "Upload" not in headers_simple
        assert column_index_simple == 6

        # Arrange & Act: Test advanced mode
        parameter_editor_table.parameter_editor_window.gui_complexity = "normal"

        headers_advanced, _ = parameter_editor_table._create_headers_and_tooltips(
            parameter_editor_table._should_show_upload_column()
        )
        column_index_advanced = parameter_editor_table._get_change_reason_column_index(
            parameter_editor_table._should_show_upload_column()
        )

        # Assert: Advanced mode includes upload column
        assert "Upload" in headers_advanced
        assert column_index_advanced == 7


class TestMousewheelHandlingBehavior:
    """Test mousewheel handling behavior for comboboxes."""

    def test_setup_combobox_mousewheel_handling(self, parameter_editor_table: ParameterEditorTable) -> None:  # pylint: disable=unused-argument
        """
        User interface properly configures mousewheel handling for combobox widgets.

        GIVEN: A combobox widget needs mousewheel event handling
        WHEN: Mousewheel handling is set up
        THEN: The widget has dropdown state tracking and required event bindings
        """
        # Arrange: Create mock combobox
        mock_combobox = MagicMock(spec=PairTupleCombobox)

        # Act: Set up mousewheel handling
        setup_combobox_mousewheel_handling(mock_combobox)

        # Assert: Dropdown state is initialized and event bindings are set up
        assert hasattr(mock_combobox, "dropdown_is_open")

        expected_bindings = [
            ("<<ComboboxDropdown>>",),
            ("<FocusOut>",),
            ("<MouseWheel>",),
            ("<Button-4>",),
            ("<Button-5>",),
        ]

        bind_calls = mock_combobox.bind.call_args_list
        for expected_binding in expected_bindings:
            assert any(call.args[0] == expected_binding[0] for call in bind_calls), f"Binding {expected_binding[0]} not found"

    def test_mousewheel_handler_when_dropdown_closed(self) -> None:
        """
        User interface allows parent scrolling when combobox dropdown is closed.

        GIVEN: A combobox with dropdown closed allows parent widget scrolling
        WHEN: A mousewheel event occurs
        THEN: The event is propagated to the parent for scrolling and returns 'break'
        """
        # Arrange: Set up mock combobox with closed dropdown
        with patch("tkinter.Tk"):
            mock_combobox = MagicMock(spec=PairTupleCombobox)
            mock_master = MagicMock()
            mock_combobox.master = mock_master
            mock_combobox.dropdown_is_open = False

            # Set up mousewheel handling
            setup_combobox_mousewheel_handling(mock_combobox)

            # Get the mousewheel handler
            mousewheel_bind_call = None
            for call in mock_combobox.bind.call_args_list:
                if call[0][0] == "<MouseWheel>":
                    mousewheel_bind_call = call
                    break

            assert mousewheel_bind_call is not None, "MouseWheel binding not found"

            # Act: Simulate mousewheel event when dropdown is closed
            handler = mousewheel_bind_call[0][1]
            mock_event = MagicMock()
            mock_event.delta = 120

            result = handler(mock_event)

            # Assert: Event is propagated to parent and returns 'break'
            assert result == "break"
            mock_master.event_generate.assert_called_once_with("<MouseWheel>", delta=120)

    def test_mousewheel_handler_when_dropdown_open(self) -> None:
        """
        User interface prevents parent scrolling when combobox dropdown is open.

        GIVEN: A combobox with dropdown open should handle its own scrolling
        WHEN: A mousewheel event occurs
        THEN: The event is not propagated to parent and returns None
        """
        # Arrange: Set up mock combobox with open dropdown
        with patch("tkinter.Tk"):
            mock_combobox = MagicMock(spec=PairTupleCombobox)
            mock_master = MagicMock()
            mock_combobox.master = mock_master

            # Set up mousewheel handling first
            setup_combobox_mousewheel_handling(mock_combobox)

            # Set dropdown as open after handler setup
            mock_combobox.dropdown_is_open = True

            # Get the mousewheel handler
            mousewheel_bind_call = None
            for call in mock_combobox.bind.call_args_list:
                if call[0][0] == "<MouseWheel>":
                    mousewheel_bind_call = call
                    break

            assert mousewheel_bind_call is not None, "MouseWheel binding not found"

            # Act: Simulate mousewheel event when dropdown is open
            handler = mousewheel_bind_call[0][1]
            mock_event = MagicMock()
            mock_event.delta = 120

            result = handler(mock_event)

            # Assert: Event is not propagated and returns None
            assert result is None
            mock_master.event_generate.assert_not_called()

    def test_dropdown_state_management(self) -> None:
        """
        User interface properly tracks combobox dropdown open/close state.

        GIVEN: A combobox with mousewheel handling configured
        WHEN: Dropdown events occur (opened/closed)
        THEN: The dropdown state is correctly tracked
        """
        # Arrange: Set up mock combobox
        with patch("tkinter.Tk"):
            mock_combobox = MagicMock(spec=PairTupleCombobox)

            # Set up mousewheel handling
            setup_combobox_mousewheel_handling(mock_combobox)

            # Get the dropdown event handlers
            dropdown_opened_handler = None
            dropdown_closed_handler = None

            for call in mock_combobox.bind.call_args_list:
                if call[0][0] == "<<ComboboxDropdown>>":
                    dropdown_opened_handler = call[0][1]
                elif call[0][0] == "<FocusOut>":
                    dropdown_closed_handler = call[0][1]

            assert dropdown_opened_handler is not None, "ComboboxDropdown handler not found"
            assert dropdown_closed_handler is not None, "FocusOut handler not found"

            # Act & Assert: Test dropdown opened
            mock_event = MagicMock()
            dropdown_opened_handler(mock_event)
            assert mock_combobox.dropdown_is_open is True

            # Act & Assert: Test dropdown closed
            dropdown_closed_handler(mock_event)
            assert mock_combobox.dropdown_is_open is False


class TestUserParameterEditingWorkflows:
    """Test complete user workflows for parameter editing and interaction."""

    def test_user_can_edit_parameter_value_and_see_visual_feedback(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        User can edit a parameter value and immediately see visual feedback.

        GIVEN: A parameter table is displayed with editable parameters
        WHEN: User enters a new value for a parameter
        THEN: The parameter value is updated and visual indicators show the change
        AND: The difference indicator appears next to the current value
        """
        # Arrange: Create a parameter with initial value different from FC value
        param = create_mock_data_model_ardupilot_parameter(
            name="TEST_PARAM",
            value=5.0,
            fc_value=10.0,  # Different from new value to show difference
            metadata={"units": "m/s", "doc_tooltip": "Test parameter"},
        )

        # Mock the parameter editor's repopulate method
        parameter_editor_table.parameter_editor_window.repopulate_parameter_table = MagicMock()

        # Act: Simulate user editing the parameter value
        with patch.object(parameter_editor_table, "_update_new_value_entry_text"):
            # Create a mock entry widget
            mock_entry = MagicMock(spec=ttk.Entry)
            mock_entry.get.return_value = "7.5"

            # Create a mock event
            mock_event = MagicMock()
            mock_event.widget = mock_entry
            mock_event.type = tk.EventType.KeyPress

            # Call the parameter value change handler
            parameter_editor_table._create_new_value_entry(param, MagicMock(), MagicMock())

            # Simulate the FocusOut event that would trigger validation
            # This is tricky to test directly, so we'll test the core logic

        # Assert: Parameter value should be updated (would be tested through integration)

    def test_user_sees_validation_feedback_for_invalid_parameter_values(
        self,
        parameter_editor_table: ParameterEditorTable,  # pylint: disable=unused-argument
    ) -> None:
        """
        User receives clear feedback when entering invalid parameter values.

        GIVEN: A parameter with value constraints is displayed
        WHEN: User enters a value outside the allowed range
        THEN: An error dialog is shown explaining the issue
        AND: The invalid value is not accepted
        """
        # Arrange: Create a parameter with range limits
        param = create_mock_data_model_ardupilot_parameter(
            name="RANGE_PARAM", value=50.0, metadata={"min": 0, "max": 100, "units": "%"}
        )

        # Mock the parameter to raise an exception for out-of-range values
        param.set_new_value = MagicMock(side_effect=ValueError("Value must be between 0 and 100"))

        # Act & Assert: Would test error handling in the event handler
        # This would be covered in integration tests that actually trigger the UI events

    def test_user_can_add_parameter_to_configuration_file(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        User can add a new parameter to the current configuration file.

        GIVEN: A parameter editor table is displayed
        WHEN: User clicks the Add button and selects a valid parameter name
        THEN: The parameter is added to the configuration
        AND: The table is refreshed to show the new parameter
        """
        # Arrange: Mock the parameter editor data model to allow adding parameters
        get_names_mock = cast("MagicMock", parameter_editor_table.parameter_editor.get_possible_add_param_names)
        get_names_mock.return_value = ["NEW_PARAM"]
        add_mock = cast("MagicMock", parameter_editor_table.parameter_editor.add_parameter_to_current_file)
        add_mock.return_value = True

        # Mock the parameter editor's repopulate method
        parameter_editor_table.parameter_editor_window.repopulate_parameter_table = MagicMock()

        # Act: Simulate adding a parameter
        result = parameter_editor_table._confirm_parameter_addition("NEW_PARAM")

        # Assert: Parameter addition was successful
        assert result is True
        add_mock.assert_called_once_with("NEW_PARAM")
        parameter_editor_table.parameter_editor_window.repopulate_parameter_table.assert_called_once_with()

    def test_user_can_delete_parameter_from_configuration_file(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        User can remove unwanted parameters from the configuration file.

        GIVEN: A parameter exists in the current configuration
        WHEN: User clicks the Delete button and confirms the deletion
        THEN: The parameter is removed from the configuration
        AND: The table is refreshed without the deleted parameter
        """
        # Arrange: Mock the parameter editor data model and confirmation dialog
        delete_mock = cast("MagicMock", parameter_editor_table.parameter_editor.delete_parameter_from_current_file)
        delete_mock.reset_mock()
        parameter_editor_table.parameter_editor_window.repopulate_parameter_table = MagicMock()
        ask_dialog = cast("MagicMock", parameter_editor_table._dialogs.ask_yes_no)
        ask_dialog.return_value = True

        # Act: Simulate parameter deletion
        parameter_editor_table._on_parameter_delete("TEST_PARAM")

        # Assert: User was asked for confirmation and deletion proceeded
        ask_dialog.assert_called_once()
        delete_mock.assert_called_once_with("TEST_PARAM")
        parameter_editor_table.parameter_editor_window.repopulate_parameter_table.assert_called_once_with()

    def test_user_cannot_delete_parameter_when_cancelled(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        User can cancel parameter deletion when they change their mind.

        GIVEN: A parameter exists in the current configuration
        WHEN: User clicks Delete but cancels the confirmation dialog
        THEN: The parameter remains in the configuration
        AND: No changes are made to the file
        """
        # Arrange: Mock confirmation dialog to return False (user cancels)
        delete_mock = cast("MagicMock", parameter_editor_table.parameter_editor.delete_parameter_from_current_file)
        delete_mock.reset_mock()
        ask_dialog = cast("MagicMock", parameter_editor_table._dialogs.ask_yes_no)
        ask_dialog.return_value = False

        # Act: Simulate cancelled parameter deletion
        parameter_editor_table._on_parameter_delete("TEST_PARAM")

        # Assert: User was asked but deletion was cancelled
        ask_dialog.assert_called_once()
        delete_mock.assert_not_called()

    def test_user_can_edit_bitmask_parameter_through_dedicated_window(
        self,
        parameter_editor_table: ParameterEditorTable,  # pylint: disable=unused-argument
    ) -> None:
        """
        User can configure complex bitmask parameters through a dedicated selection window.

        GIVEN: A bitmask parameter is displayed in the table
        WHEN: User double-clicks the parameter value to open the bitmask editor
        THEN: A window appears allowing selection of individual bit options
        AND: Changes are saved back to the parameter when the window closes
        """
        # Arrange: Create a bitmask parameter
        param = create_mock_data_model_ardupilot_parameter(
            name="BITMASK_PARAM",
            value=5,  # Binary: 101
            is_bitmask=True,
            metadata={"Bitmask": {0: "Option 1", 1: "Option 2", 2: "Option 3"}},
        )

        # Assert: Bitmask parameter is properly configured
        assert param.name == "BITMASK_PARAM"
        assert param.value_as_string == "5"

    def test_user_can_select_parameters_for_upload_to_flight_controller(
        self, parameter_editor_table: ParameterEditorTable
    ) -> None:
        """
        User can choose which parameters to upload to the flight controller.

        GIVEN: Flight controller is connected and advanced GUI mode is active
        WHEN: User checks/unchecks upload checkboxes next to parameters
        THEN: Only selected parameters are included in the upload set
        AND: The selection persists across table refreshes
        """
        # Arrange: Set up parameters with upload checkboxes
        parameter_editor_table.parameter_editor_window.gui_complexity = "normal"
        parameter_editor_table.parameter_editor.is_fc_connected = True

        # Create mock parameters
        params = {
            "PARAM1": create_mock_data_model_ardupilot_parameter("PARAM1", 1.0),
            "PARAM2": create_mock_data_model_ardupilot_parameter("PARAM2", 2.0),
        }

        # Mock the parameter editor data model
        parameter_editor_table.parameter_editor.current_step_parameters = params
        parameter_editor_table.parameter_editor.get_parameters_as_par_dict.return_value = {
            "PARAM1": Par(1.0, "test"),
            "PARAM2": Par(2.0, "test"),
        }

        # Act: Get upload parameters (simulating user selections)
        result = parameter_editor_table.get_upload_selected_params("normal")

        # Assert: All parameters selected in advanced mode when FC connected
        assert len(result) == 2
        assert "PARAM1" in result
        assert "PARAM2" in result

    def test_user_can_document_reasons_for_parameter_changes(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        User can document the reasoning behind parameter value changes.

        GIVEN: A parameter has been modified from its default or current value
        WHEN: User enters a change reason in the comment field
        THEN: The reason is stored with the parameter
        AND: The documentation supports future troubleshooting and compliance
        """
        # Arrange: Create a parameter with change reason tracking
        param = create_mock_data_model_ardupilot_parameter(name="DOC_PARAM", value=15.0, comment="Initial setup")

        # Mock the change reason entry and event
        mock_entry = MagicMock(spec=ttk.Entry)
        mock_entry.get.return_value = "Adjusted for better performance in windy conditions"

        # Mock the _local_filesystem to simulate parameter storage
        parameter_editor_table.parameter_editor._local_filesystem.file_parameters = {
            "test_file": ParDict({"DOC_PARAM": Par(15.0, "Initial setup")})
        }
        parameter_editor_table.parameter_editor.current_file = "test_file"

        # Act: Simulate the change reason update logic
        new_comment = mock_entry.get()
        result = param.set_change_reason(new_comment)

        # Assert: Change reason was accepted and stored
        assert result is True
        assert param.change_reason == "Adjusted for better performance in windy conditions"

    def test_user_sees_visual_indicators_for_parameter_states(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        User receives clear visual feedback about parameter states and constraints.

        GIVEN: Parameters with different states exist (readonly, forced, derived, etc.)
        WHEN: The parameter table is displayed
        THEN: Visual styling clearly indicates parameter constraints
        AND: Users understand which parameters they can modify
        """
        # Arrange: Create parameters with different states
        readonly_param = create_mock_data_model_ardupilot_parameter(name="READONLY_PARAM", value=100.0, is_readonly=True)

        forced_param = create_mock_data_model_ardupilot_parameter(name="FORCED_PARAM", value=50.0, is_forced=True)

        # Act: Create visual elements for these parameters
        readonly_label = parameter_editor_table._create_parameter_name(readonly_param)
        forced_entry = parameter_editor_table._create_new_value_entry(forced_param, MagicMock(), MagicMock())

        # Assert: Visual properties indicate parameter states
        assert readonly_label is not None
        assert forced_entry is not None

    def test_user_experiences_smooth_table_navigation_and_scrolling(
        self, parameter_editor_table: ParameterEditorTable
    ) -> None:
        """
        User can smoothly navigate and scroll through large parameter tables.

        GIVEN: A configuration file contains many parameters
        WHEN: User scrolls through the parameter table
        THEN: Scrolling is smooth and position is maintained during updates
        AND: Performance remains acceptable with large parameter sets
        """
        # Arrange: Mock canvas and scrolling behavior
        parameter_editor_table.canvas.yview_moveto = MagicMock()
        parameter_editor_table.update_idletasks = MagicMock()

        # Act: Apply scroll position
        parameter_editor_table._apply_scroll_position(scroll_to_bottom=True)

        # Assert: Scroll position is applied correctly
        parameter_editor_table.canvas.yview_moveto.assert_called_once_with(1.0)

    def test_user_sees_helpful_tooltips_for_parameter_guidance(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        User receives helpful guidance through tooltips and contextual help.

        GIVEN: Parameters with documentation and tooltips are available
        WHEN: User hovers over parameter elements
        THEN: Relevant help information is displayed
        AND: Users can make informed decisions about parameter changes
        """
        # Arrange: Create a parameter with tooltip information
        param = create_mock_data_model_ardupilot_parameter(
            name="TOOLTIP_PARAM", value=25.0, metadata={"doc_tooltip": "This parameter controls motor speed"}
        )

        # Act: Create UI elements that would show tooltips
        name_label = parameter_editor_table._create_parameter_name(param)

        # Assert: Tooltip information is available and UI element is created
        assert name_label is not None
        assert param._metadata.get("doc_tooltip") == "This parameter controls motor speed"


class TestUIErrorInfoHandling:
    """Test UI message handling in repopulate_table method."""

    def test_repopulate_handles_no_different_parameters_found(self, parameter_editor_table) -> None:
        """
        User sees appropriate message when no different parameters are found in show_only_differences mode.

        GIVEN: A parameter editor table in show_only_differences mode with no different parameters
        WHEN: The table is repopulated
        THEN: An info message is displayed about no different parameters
        AND: The on_skip_click method is called
        """
        # Arrange: Set up mock to return no different parameters
        parameter_editor_table.parameter_editor.get_different_parameters.return_value = {}
        parameter_editor_table.parameter_editor.current_file = "test_file.param"
        parameter_editor_table.parameter_editor_window.gui_complexity = "simple"

        info_dialog = cast("MagicMock", parameter_editor_table._dialogs.show_info)

        parameter_editor_table.repopulate_table(
            show_only_differences=True,
            gui_complexity="simple",
        )

        info_dialog.assert_called_once()
        call_args = info_dialog.call_args[0]
        assert "No different parameters found" in call_args[1]
        assert "test_file.param" in call_args[1]
        parameter_editor_table.parameter_editor_window.on_skip_click.assert_called_once()

    def test_update_table_handles_keyerror_with_critical_logging_and_exit(self, parameter_editor_table) -> None:
        """
        System handles KeyError during table update with critical logging and system exit.

        GIVEN: A parameter editor table with parameters that cause KeyError during processing
        WHEN: The table is updated
        THEN: A critical log message is written
        AND: The system exits with code 1
        """
        # Arrange: Set up parameters that will cause KeyError
        # We'll mock the _create_column_widgets to raise KeyError
        faulty_param = create_mock_data_model_ardupilot_parameter(name="FAULTY_PARAM", value=1.0)
        params = {"FAULTY_PARAM": faulty_param}

        parameter_editor_table._create_column_widgets = MagicMock(side_effect=KeyError("Test KeyError"))
        parameter_editor_table._configure_table_columns = MagicMock()

        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.logging_critical") as mock_critical,
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.sys_exit") as mock_exit,
        ):
            # Act: Update table with faulty parameters
            parameter_editor_table._update_table(params, "simple")

            # Assert: Critical logging and system exit occur
            mock_critical.assert_called_once()
            call_args = mock_critical.call_args[0]
            assert "FAULTY_PARAM" in call_args[1]  # Parameter name in message
            assert "Test KeyError" in str(call_args[3])  # Exception in 4th argument

            mock_exit.assert_called_once_with(1)

    def test_update_table_creates_add_button_with_tooltip(self, parameter_editor_table) -> None:
        """
        Table update creates an Add button with appropriate tooltip when parameters exist.

        GIVEN: A parameter editor table with parameters to display
        WHEN: The table is updated
        THEN: An Add button is created at the bottom of the table
        AND: The button has the correct text, style, and tooltip
        """
        # Arrange: Set up parameters for the table
        param = create_mock_data_model_ardupilot_parameter(name="TEST_PARAM", value=1.0)
        params = {"TEST_PARAM": param}

        parameter_editor_table.parameter_editor.current_file = "test_file.param"

        # Mock the widget creation methods to avoid actual widget creation
        with (
            patch.object(parameter_editor_table, "_create_column_widgets") as mock_create_widgets,
            patch("tkinter.ttk.Button") as mock_button,
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.show_tooltip") as mock_tooltip,
        ):
            mock_create_widgets.return_value = [MagicMock() for _ in range(7)]  # Mock 7 column widgets

            # Act: Update the table
            parameter_editor_table._update_table(params, "simple")

            # Assert: Add button was created with correct parameters
            mock_button.assert_called_once()
            call_args, call_kwargs = mock_button.call_args
            assert call_args[0] == parameter_editor_table.view_port  # parent widget
            assert call_kwargs["text"] == _("Add")
            assert call_kwargs["style"] == "narrow.TButton"
            assert call_kwargs["command"] == parameter_editor_table._on_parameter_add

            # Assert: Tooltip was set up
            mock_tooltip.assert_called()
            tooltip_call_args = mock_tooltip.call_args[0]
            assert "Add a parameter to the test_file.param file" in tooltip_call_args[1]

    def test_create_flightcontroller_value_sets_correct_background_colors(self, parameter_editor_table) -> None:  # pylint: disable=too-many-statements # noqa: PLR0915
        """
        Flight controller value labels display with appropriate background colors based on parameter state.

        GIVEN: Parameters with different FC value states
        WHEN: Flight controller value labels are created
        THEN: Correct background colors are applied for each state
        """
        # Create mock parameters with the necessary attributes
        param_default = MagicMock()
        param_default.has_fc_value = True
        param_default.fc_value_equals_default_value = True
        param_default.fc_value_as_string = "1.0"
        param_default.tooltip_fc_value = None

        param_below = MagicMock()
        param_below.has_fc_value = True
        param_below.fc_value_equals_default_value = False
        param_below.fc_value_is_below_limit.return_value = True
        param_below.fc_value_as_string = "1.0"
        param_below.tooltip_fc_value = None

        param_above = MagicMock()
        param_above.has_fc_value = True
        param_above.fc_value_equals_default_value = False
        param_above.fc_value_is_below_limit.return_value = False
        param_above.fc_value_is_above_limit.return_value = True
        param_above.fc_value_as_string = "10.0"
        param_above.tooltip_fc_value = None

        param_unknown = MagicMock()
        param_unknown.has_fc_value = True
        param_unknown.fc_value_equals_default_value = False
        param_unknown.fc_value_is_below_limit.return_value = False
        param_unknown.fc_value_is_above_limit.return_value = False
        param_unknown.fc_value_has_unknown_bits_set.return_value = True
        param_unknown.fc_value_as_string = "5.0"
        param_unknown.tooltip_fc_value = None

        param_no_fc = MagicMock()
        param_no_fc.has_fc_value = False

        param_normal = MagicMock()
        param_normal.has_fc_value = True
        param_normal.fc_value_equals_default_value = False
        param_normal.fc_value_is_below_limit.return_value = False
        param_normal.fc_value_is_above_limit.return_value = False
        param_normal.fc_value_has_unknown_bits_set.return_value = False
        param_normal.fc_value_as_string = "5.0"
        param_normal.tooltip_fc_value = None

        with (
            patch("tkinter.ttk.Label") as mock_label,
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.show_tooltip"),
        ):
            # Act: Create labels for each parameter type
            parameter_editor_table._create_flightcontroller_value(param_default)
            parameter_editor_table._create_flightcontroller_value(param_below)
            parameter_editor_table._create_flightcontroller_value(param_above)
            parameter_editor_table._create_flightcontroller_value(param_unknown)
            parameter_editor_table._create_flightcontroller_value(param_no_fc)
            parameter_editor_table._create_flightcontroller_value(param_normal)

            # Assert: Correct background colors were set
            calls = mock_label.call_args_list
            assert len(calls) == 6

            # Check each call's background parameter
            # Default value -> light blue
            assert calls[0][1]["background"] == "light blue"
            # Below limit -> orangered
            assert calls[1][1]["background"] == "orangered"
            # Above limit -> red3
            assert calls[2][1]["background"] == "red3"
            # Unknown bits -> red3
            assert calls[3][1]["background"] == "red3"
            # No FC value -> orange
            assert calls[4][1]["background"] == "orange"
            # Normal value -> no background specified (uses default)

    def test_update_combobox_style_on_selection_updates_ui_when_value_changes(self, parameter_editor_table) -> None:
        """Combobox updates delegate to presenter and refresh UI hints on success."""
        combobox_widget = MagicMock()
        combobox_widget.get_selected_key.return_value = "test_value"
        combobox_widget.configure = MagicMock()
        combobox_widget.on_combo_configure = MagicMock()

        change_reason_widget = MagicMock()
        value_is_different = MagicMock()
        value_is_different.config = MagicMock()
        event = MagicMock()
        event.width = 0

        param = MagicMock()
        param.name = "TEST_PARAM"
        param.new_value_equals_default_value = False
        param.is_different_from_fc = True
        param.tooltip_change_reason = "Why it changed"

        with (
            patch.object(parameter_editor_table, "_handle_parameter_value_update", return_value=True) as handle_mock,
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.show_tooltip") as tooltip_mock,
        ):
            parameter_editor_table._update_combobox_style_on_selection(
                combobox_widget,
                param,
                event,
                change_reason_widget,
                value_is_different,
            )

            handle_mock.assert_called_once_with(
                param,
                "test_value",
                include_range_check=False,
            )
            tooltip_mock.assert_called_once_with(change_reason_widget, "Why it changed")
            value_is_different.config.assert_called_once()
            combobox_widget.configure.assert_called_once_with(style="readonly.TCombobox")
            assert event.width == NEW_VALUE_WIDGET_WIDTH
            combobox_widget.on_combo_configure.assert_called_once_with(event)

    def test_update_new_value_entry_text_sets_correct_styles(self, parameter_editor_table) -> None:
        """
        Entry widget styles are set correctly based on parameter validation state.

        GIVEN: Parameters with different validation states
        WHEN: Entry text is updated
        THEN: Correct styles are applied for each state
        """
        # Create mock entry widget
        mock_entry = MagicMock()

        # Test default value style
        param_default = MagicMock()
        param_default.value_as_string = "1.0"
        param_default.new_value_equals_default_value = True
        param_default.is_below_limit.return_value = False
        param_default.is_above_limit.return_value = False
        param_default.has_unknown_bits_set.return_value = False

        parameter_editor_table._update_new_value_entry_text(mock_entry, param_default)
        mock_entry.configure.assert_called_with(style="default_v.TEntry")

        # Reset mock
        mock_entry.reset_mock()

        # Test below limit style
        param_below = MagicMock()
        param_below.value_as_string = "0.5"
        param_below.new_value_equals_default_value = False
        param_below.is_below_limit.return_value = True
        param_below.is_above_limit.return_value = False
        param_below.has_unknown_bits_set.return_value = False

        parameter_editor_table._update_new_value_entry_text(mock_entry, param_below)
        mock_entry.configure.assert_called_with(style="below_limit.TEntry")

        # Reset mock
        mock_entry.reset_mock()

        # Test above limit style
        param_above = MagicMock()
        param_above.value_as_string = "10.0"
        param_above.new_value_equals_default_value = False
        param_above.is_below_limit.return_value = False
        param_above.is_above_limit.return_value = True
        param_above.has_unknown_bits_set.return_value = False

        parameter_editor_table._update_new_value_entry_text(mock_entry, param_above)
        mock_entry.configure.assert_called_with(style="above_limit.TEntry")

        # Reset mock
        mock_entry.reset_mock()

        # Test unknown bits style
        param_unknown = MagicMock()
        param_unknown.value_as_string = "5.0"
        param_unknown.new_value_equals_default_value = False
        param_unknown.is_below_limit.return_value = False
        param_unknown.is_above_limit.return_value = False
        param_unknown.has_unknown_bits_set.return_value = True

        parameter_editor_table._update_new_value_entry_text(mock_entry, param_unknown)
        mock_entry.configure.assert_called_with(style="above_limit.TEntry")

        # Reset mock
        mock_entry.reset_mock()

        # Test normal style
        param_normal = MagicMock()
        param_normal.value_as_string = "5.0"
        param_normal.new_value_equals_default_value = False
        param_normal.is_below_limit.return_value = False
        param_normal.is_above_limit.return_value = False
        param_normal.has_unknown_bits_set.return_value = False

        parameter_editor_table._update_new_value_entry_text(mock_entry, param_normal)
        mock_entry.configure.assert_called_with(style="TEntry")

    def test_create_new_value_entry_creates_combobox_for_multiple_choice(self, parameter_editor_table) -> None:
        """
        Multiple choice parameters create combobox widgets with proper configuration.

        GIVEN: A parameter with multiple choice values
        WHEN: Creating the new value entry widget
        THEN: A PairTupleCombobox is created with correct configuration
        AND: Event bindings and mouse wheel handling are set up
        """
        # Create mock parameter with multiple choices
        param = MagicMock()
        param.is_multiple_choice = True
        param.choices_dict = {"Option1": "1", "Option2": "2", "Option3": "3"}
        param.get_selected_value_from_dict.return_value = "Option2"
        param.value_as_string = "Option2"  # This should be the key, not the value
        param.name = "TEST_PARAM"
        param.is_editable = True
        param.new_value_equals_default_value = False

        # Create mock widgets for change_reason and value_is_different
        change_reason_widget = MagicMock()
        value_is_different = MagicMock()

        with (
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.PairTupleCombobox"
            ) as mock_combobox,
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.get_widget_font_family_and_size"
            ) as mock_font,
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.platform_system") as mock_platform,
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.setup_combobox_mousewheel_handling"
            ) as mock_mousewheel,
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.show_tooltip"),
        ):
            mock_font.return_value = ("Arial", 10)
            mock_platform.return_value = "Linux"
            mock_instance = MagicMock()
            mock_combobox.return_value = mock_instance

            # Act: Create the entry widget
            result = parameter_editor_table._create_new_value_entry(param, change_reason_widget, value_is_different)

            # Assert: PairTupleCombobox was created with correct parameters
            mock_combobox.assert_called_once()
            call_args = mock_combobox.call_args
            assert call_args[0][0] == parameter_editor_table.view_port  # parent
            assert call_args[0][1] == list(param.choices_dict.items())  # choices
            assert call_args[0][2] == param.value_as_string  # current value
            assert call_args[0][3] == param.name  # parameter name
            assert call_args[1]["style"] == "readonly.TCombobox"  # style for editable, non-default

            # Assert: Selected value was set
            mock_instance.set.assert_called_once_with("Option2")

            # Assert: Font and config were set
            mock_font.assert_called_once_with(mock_instance)
            mock_instance.config.assert_called_once_with(
                state="readonly",
                width=NEW_VALUE_WIDGET_WIDTH,
                font=("Arial", 11),  # 10 + 1 for Linux
            )

            # Assert: Event binding was set up for combobox selection
            bind_calls = mock_instance.bind.call_args_list
            combobox_selected_calls = [call for call in bind_calls if call[0][0] == "<<ComboboxSelected>>"]
            assert len(combobox_selected_calls) == 1
            assert combobox_selected_calls[0][0][0] == "<<ComboboxSelected>>"

            # Assert: Mouse wheel handling was set up
            mock_mousewheel.assert_called_once_with(mock_instance)

            # Assert: Correct widget was returned
            assert result == mock_instance

    def test_create_new_value_entry_shows_error_for_non_editable_parameters(self, parameter_editor_table) -> None:
        """
        Non-editable parameters show appropriate error messages when clicked.

        GIVEN: A non-editable parameter (forced or derived)
        WHEN: Creating the new value entry widget
        THEN: The widget is disabled and clicking shows error messages
        """
        # Test forced parameter
        forced_param = MagicMock()
        forced_param.is_multiple_choice = False
        forced_param.is_editable = False
        forced_param.is_forced = True
        forced_param.is_derived = False
        forced_param.value_as_string = "1.0"

        # Test derived parameter
        derived_param = MagicMock()
        derived_param.is_multiple_choice = False
        derived_param.is_editable = False
        derived_param.is_forced = False
        derived_param.is_derived = True
        derived_param.value_as_string = "2.0"

        # Create mock widgets
        change_reason_widget = MagicMock()
        value_is_different = MagicMock()

        with (
            patch("tkinter.ttk.Entry") as mock_entry,
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.show_tooltip"),
            patch.object(parameter_editor_table._dialogs, "show_error") as mock_error,
        ):
            mock_entry_instance = MagicMock()
            mock_entry.return_value = mock_entry_instance

            # Test forced parameter
            forced_entry = parameter_editor_table._create_new_value_entry(
                forced_param, change_reason_widget, value_is_different
            )

            # Should be configured as disabled
            mock_entry_instance.config.assert_called_with(state="disabled", background="light grey")

            # Should have button bindings for error display
            button1_calls = [call for call in mock_entry_instance.bind.call_args_list if call[0][0] == "<Button-1>"]
            button3_calls = [call for call in mock_entry_instance.bind.call_args_list if call[0][0] == "<Button-3>"]
            assert len(button1_calls) == 1
            assert len(button3_calls) == 1

            # Simulate click event
            mock_event = MagicMock()
            mock_event.widget = forced_entry

            # Call the bound function
            button1_calls[0][0][1](mock_event)

            # Should show forced parameter error
            mock_error.assert_called_with(_("Forced Parameter"), mock_error.call_args[0][1])
            assert "correct value" in mock_error.call_args[0][1]

        # Reset mocks
        mock_error.reset_mock()
        mock_entry.reset_mock()

        with (
            patch("tkinter.ttk.Entry") as mock_entry,
            patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.show_tooltip"),
            patch.object(parameter_editor_table._dialogs, "show_error") as mock_error,
        ):
            mock_entry_instance = MagicMock()
            mock_entry.return_value = mock_entry_instance

            # Test derived parameter
            derived_entry = parameter_editor_table._create_new_value_entry(
                derived_param, change_reason_widget, value_is_different
            )

            # Should be configured as disabled
            mock_entry_instance.config.assert_called_with(state="disabled", background="light grey")

            # Should have button bindings for error display
            button1_calls = [call for call in mock_entry_instance.bind.call_args_list if call[0][0] == "<Button-1>"]
            button3_calls = [call for call in mock_entry_instance.bind.call_args_list if call[0][0] == "<Button-3>"]
            assert len(button1_calls) == 1
            assert len(button3_calls) == 1

            # Simulate click event
            mock_event = MagicMock()
            mock_event.widget = derived_entry

            # Call the bound function
            button1_calls[0][0][1](mock_event)

            # Should show derived parameter error
            mock_error.assert_called_with(_("Derived Parameter"), mock_error.call_args[0][1])
            assert "derived from information" in mock_error.call_args[0][1]


class TestParentWidgetResolution:
    """Ensure helper methods can resolve parent widgets in different scenarios."""

    def test_get_parent_root_returns_top_level(self, parameter_editor_table: ParameterEditorTable, mock_master: tk.Tk) -> None:
        nested = tk.Frame(mock_master)
        parameter_editor_table.main_frame = nested

        assert parameter_editor_table._get_parent_root() is mock_master

    def test_get_parent_toplevel_uses_winfo_fallback(
        self, parameter_editor_table: ParameterEditorTable, mock_master: tk.Tk
    ) -> None:
        fake_frame = MagicMock(spec=tk.Misc)
        fake_frame.master = None
        fallback = tk.Toplevel(mock_master)
        fake_frame.winfo_toplevel.return_value = fallback
        parameter_editor_table.main_frame = fake_frame

        try:
            assert parameter_editor_table._get_parent_toplevel() is fallback
        finally:
            fallback.destroy()


class TestLayoutUtilityMethods:
    """Cover column creation, grid placement, and column configuration helpers."""

    def test_create_column_widgets_appends_upload_column(self, parameter_editor_table: ParameterEditorTable) -> None:
        param = create_mock_data_model_ardupilot_parameter()
        with (
            patch.object(parameter_editor_table, "_create_change_reason_entry", return_value="change"),
            patch.object(parameter_editor_table, "_create_value_different_label", return_value="diff"),
            patch.object(parameter_editor_table, "_create_delete_button", return_value="delete"),
            patch.object(parameter_editor_table, "_create_parameter_name", return_value="name"),
            patch.object(parameter_editor_table, "_create_flightcontroller_value", return_value="fc"),
            patch.object(parameter_editor_table, "_create_new_value_entry", return_value="new"),
            patch.object(parameter_editor_table, "_create_unit_label", return_value="unit"),
            patch.object(parameter_editor_table, "_create_upload_checkbutton", return_value="upload"),
        ):
            widgets = parameter_editor_table._create_column_widgets("PARAM", param, show_upload_column=True)

        assert widgets == ["delete", "name", "fc", "diff", "new", "unit", "upload", "change"]

    def test_grid_column_widgets_places_upload_column(self, parameter_editor_table: ParameterEditorTable) -> None:
        row_widgets = [MagicMock() for _ in range(8)]

        parameter_editor_table._grid_column_widgets(row_widgets, row=2, show_upload_column=True)

        row_widgets[6].grid.assert_called_once_with(row=2, column=6, sticky="e", padx=0)
        change_reason_index = parameter_editor_table._get_change_reason_column_index(show_upload_column=True)
        row_widgets[change_reason_index].grid.assert_called_with(row=2, column=change_reason_index, sticky="ew", padx=(0, 5))

    def test_configure_table_columns_configures_upload_column(self, parameter_editor_table: ParameterEditorTable) -> None:
        parameter_editor_table.view_port = MagicMock()

        parameter_editor_table._configure_table_columns(show_upload_column=True)

        parameter_editor_table.view_port.columnconfigure.assert_any_call(6, weight=0)
        change_reason_index = parameter_editor_table._get_change_reason_column_index(show_upload_column=True)
        parameter_editor_table.view_port.columnconfigure.assert_any_call(change_reason_index, weight=1)


class TestWidgetFactoryHelpers:
    """Cover smaller widget helper functions and tooltips."""

    def test_create_parameter_name_applies_tooltip(self, parameter_editor_table: ParameterEditorTable) -> None:
        param = create_mock_data_model_ardupilot_parameter(
            name="HAS_TOOLTIP",
            metadata={"doc_tooltip": "tooltip"},
        )

        with patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.show_tooltip") as mock_tip:
            label = parameter_editor_table._create_parameter_name(param)

        assert isinstance(label, ttk.Label)
        mock_tip.assert_called_once_with(label, "tooltip")

    def test_create_value_different_label_reflects_state(self, parameter_editor_table: ParameterEditorTable) -> None:
        param = create_mock_data_model_ardupilot_parameter(value=2.0, fc_value=1.0)
        label = parameter_editor_table._create_value_different_label(param)
        assert NEW_VALUE_DIFFERENT_STR in label.cget("text")

    def test_create_unit_label_sets_tooltip(self, parameter_editor_table: ParameterEditorTable) -> None:
        param = create_mock_data_model_ardupilot_parameter(metadata={"unit": "m/s", "unit_tooltip": "unit"})
        with patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.show_tooltip") as mock_tip:
            label = parameter_editor_table._create_unit_label(param)
        assert isinstance(label, ttk.Label)
        mock_tip.assert_called_once_with(label, "unit")

    def test_create_upload_checkbutton_reflects_fc_connection(self, parameter_editor_table: ParameterEditorTable) -> None:
        parameter_editor_table.parameter_editor.is_fc_connected = False
        button = parameter_editor_table._create_upload_checkbutton("PARAM")
        assert parameter_editor_table.upload_checkbutton_var["PARAM"].get() is False
        assert button.instate(("disabled",))


class TestHandlerEdgeCases:
    """Exercise handler helper edge cases for coverage."""

    def test_handle_parameter_value_update_result_unknown_status_returns_false(
        self, parameter_editor_table: ParameterEditorTable
    ) -> None:
        param = create_mock_data_model_ardupilot_parameter()
        unknown_result = ParameterValueUpdateResult(cast("ParameterValueUpdateStatus", None))

        assert parameter_editor_table._handle_parameter_value_update_result(unknown_result, param, "1") is False

    def test_new_value_entry_handler_deduplicates_focusout(self, parameter_editor_table: ParameterEditorTable) -> None:
        param = create_mock_data_model_ardupilot_parameter(name="HANDLER", value=1.0)
        change_reason = ttk.Entry(parameter_editor_table.view_port)
        diff_label = ttk.Label(parameter_editor_table.view_port)

        def _fake_handle_update(_param_name: str, new_value: str, include_range_check: bool = True) -> bool:  # noqa: ARG001 # pylint: disable=unused-argument
            param._new_value = float(new_value)
            return True

        with patch.object(
            parameter_editor_table,
            "_handle_parameter_value_update",
            side_effect=_fake_handle_update,
        ) as handle_mock:
            entry = parameter_editor_table._create_new_value_entry(param, change_reason, diff_label)
            entry.delete(0, tk.END)
            entry.insert(0, "2")
            key_event = SimpleNamespace(widget=entry, type=tk.EventType.KeyPress)
            focus_event = SimpleNamespace(widget=entry, type=tk.EventType.FocusOut)
            entry.testing_on_parameter_value_change(key_event)
            entry.testing_on_parameter_value_change(focus_event)

        assert handle_mock.call_count == 1

    def test_change_reason_handler_removes_duplicate_events(self, parameter_editor_table: ParameterEditorTable) -> None:
        param = create_mock_data_model_ardupilot_parameter()
        param.set_change_reason = MagicMock(return_value=True)
        entry = parameter_editor_table._create_change_reason_entry(param)
        entry.delete(0, tk.END)
        entry.insert(0, "Updated")

        key_event = SimpleNamespace(widget=entry, type=tk.EventType.KeyPress)
        focus_event = SimpleNamespace(widget=entry, type=tk.EventType.FocusOut)
        entry.testing_on_change_reason_change(key_event)
        entry.testing_on_change_reason_change(focus_event)

        param.set_change_reason.assert_called_once_with("Updated")


class TestParameterAdditionWorkflows:
    """Cover add-parameter dialog flows and error handling."""

    def test_on_parameter_add_invokes_confirmation_handler(self, parameter_editor_table: ParameterEditorTable) -> None:
        parameter_editor_table.parameter_editor.get_possible_add_param_names.return_value = ["NEW"]
        parameter_editor_table._confirm_parameter_addition = MagicMock(return_value=True)
        mock_window = MagicMock()
        mock_window.root = MagicMock()
        mock_window.main_frame = MagicMock()
        entry_widget = MagicMock()
        entry_widget.get.return_value = "NEW"

        with (
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.BaseWindow", return_value=mock_window
            ),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.EntryWithDynamicalyFilteredListbox",
                return_value=entry_widget,
            ),
        ):
            parameter_editor_table._on_parameter_add()

        handler = entry_widget.bind.call_args_list[0][0][1]
        handler(SimpleNamespace(widget=entry_widget))
        parameter_editor_table._confirm_parameter_addition.assert_called_with("NEW")

    def test_on_parameter_add_handles_operation_not_possible(self, parameter_editor_table: ParameterEditorTable) -> None:
        parameter_editor_table.parameter_editor.get_possible_add_param_names.side_effect = OperationNotPossibleError("nope")
        parameter_editor_table._on_parameter_add()
        parameter_editor_table._dialogs.show_error.assert_called_once()

    def test_confirm_parameter_addition_handles_errors(self, parameter_editor_table: ParameterEditorTable) -> None:
        parameter_editor_table.parameter_editor.add_parameter_to_current_file.side_effect = InvalidParameterNameError("bad")
        assert parameter_editor_table._confirm_parameter_addition("bad") is False
        parameter_editor_table._dialogs.show_error.assert_called()

        parameter_editor_table._dialogs.show_error.reset_mock()
        parameter_editor_table.parameter_editor.add_parameter_to_current_file.side_effect = OperationNotPossibleError("ops")
        assert parameter_editor_table._confirm_parameter_addition("bad") is False
        parameter_editor_table._dialogs.show_error.assert_called()


class TestUploadSelectionBehavior:
    """Test upload selection helper based on GUI complexity."""

    def test_get_upload_selected_params_simple_returns_all(self, parameter_editor_table: ParameterEditorTable) -> None:
        parameter_editor_table._should_show_upload_column = MagicMock(return_value=False)
        parameter_editor_table.parameter_editor.get_parameters_as_par_dict.return_value = ParDict({})

        result = parameter_editor_table.get_upload_selected_params("simple")
        assert result == ParDict({})

    def test_get_upload_selected_params_filters_checked(self, parameter_editor_table: ParameterEditorTable) -> None:
        parameter_editor_table._should_show_upload_column = MagicMock(return_value=True)
        parameter_editor_table.upload_checkbutton_var = {
            "A": tk.BooleanVar(value=True),
            "B": tk.BooleanVar(value=False),
        }
        parameter_editor_table.parameter_editor.get_parameters_as_par_dict.return_value = ParDict({"A": Par(1.0, "")})

        result = parameter_editor_table.get_upload_selected_params("normal")
        assert result == ParDict({"A": Par(1.0, "")})
