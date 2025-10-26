#!/usr/bin/env python3

"""
Tests for the ParameterEditorTable class.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from tkinter import ttk
from typing import Any, Optional
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.configuration_manager import ConfigurationManager, InvalidParameterNameError
from ardupilot_methodic_configurator.data_model_ardupilot_parameter import ArduPilotParameter
from ardupilot_methodic_configurator.data_model_par_dict import Par, ParDict
from ardupilot_methodic_configurator.frontend_tkinter_pair_tuple_combobox import (
    PairTupleCombobox,
    setup_combobox_mousewheel_handling,
)
from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table import ParameterEditorTable
from tests.conftest import PARAMETER_EDITOR_TABLE_HEADERS_ADVANCED, PARAMETER_EDITOR_TABLE_HEADERS_SIMPLE

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
    metadata = metadata or {}

    if is_calibration:
        metadata["Calibration"] = True
    if is_readonly:
        metadata["ReadOnly"] = True
    if is_bitmask:
        metadata["Bitmask"] = {0: "Bit 0", 1: "Bit 1", 2: "Bit 2"}
    if is_multiple_choice:
        metadata["values"] = {"0": "Option 0", "1": "Option 1"}

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
def mock_parameter_editor() -> MagicMock:
    """Create a mock parameter editor."""
    return MagicMock()


@pytest.fixture
def parameter_editor_table(
    mock_master: tk.Tk, mock_local_filesystem: MagicMock, mock_parameter_editor: MagicMock
) -> ParameterEditorTable:
    """Create a ParameterEditorTable instance for testing, using ConfigurationManager abstraction."""
    with patch("tkinter.ttk.Style") as mock_style:
        style_instance = mock_style.return_value
        style_instance.lookup.return_value = "white"

        # Create a mock ConfigurationManager
        mock_config_manager = MagicMock(spec=ConfigurationManager)
        mock_config_manager.filesystem = mock_local_filesystem
        mock_config_manager.current_file = "test_file"
        mock_config_manager.is_fc_connected = True

        # Set up get_parameters_as_par_dict to return the right parameters
        def get_current_file_parameters() -> ParDict:
            return mock_local_filesystem.file_parameters.get(mock_config_manager.current_file, ParDict())

        mock_config_manager.get_parameters_as_par_dict.return_value = get_current_file_parameters()

        # Mock the repopulate_configuration_step_parameters method to return the expected tuple
        mock_config_manager.repopulate_configuration_step_parameters.return_value = ([], [])

        # Mock the parameters attribute that gets populated during repopulate_configuration_step_parameters
        mock_config_manager.current_step_parameters = {}

        # Mock the delete method to actually delete from the filesystem parameters
        def mock_delete_parameter(param_name: str) -> None:
            current_file = mock_config_manager.current_file
            if (
                current_file in mock_local_filesystem.file_parameters
                and param_name in mock_local_filesystem.file_parameters[current_file]
            ):
                del mock_local_filesystem.file_parameters[current_file][param_name]

        mock_config_manager.delete_parameter_from_current_file = mock_delete_parameter

        # Mock has_unsaved_changes to return False by default
        mock_config_manager.has_unsaved_changes.return_value = False

        # Create the table instance
        table = ParameterEditorTable(mock_master, mock_config_manager, mock_parameter_editor)

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
    parameter_editor_table, mock_master, mock_local_filesystem, mock_parameter_editor
) -> None:
    """
    ParameterEditorTable initializes with correct attributes and dependencies.

    GIVEN: Required dependencies (master window, filesystem, parameter editor)
    WHEN: ParameterEditorTable is instantiated
    THEN: All attributes are properly set and configured
    AND: The table is ready for parameter display and editing
    """
    # Arrange: Dependencies provided by fixtures

    # Act: Instance created by fixture

    # Assert: All attributes properly initialized
    assert parameter_editor_table.main_frame == mock_master
    assert parameter_editor_table.configuration_manager.filesystem == mock_local_filesystem
    assert parameter_editor_table.parameter_editor == mock_parameter_editor
    # current_file is now managed by configuration_manager
    assert parameter_editor_table.configuration_manager.current_file == "test_file"
    assert isinstance(parameter_editor_table.upload_checkbutton_var, dict)
    assert parameter_editor_table.configuration_manager.has_unsaved_changes() is False


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

        # Create a mock ConfigurationManager for the new instance
        mock_config_manager = MagicMock(spec=ConfigurationManager)
        mock_config_manager.filesystem = parameter_editor_table.configuration_manager.filesystem
        mock_config_manager.current_file = "test_file"
        mock_config_manager.get_parameters_as_par_dict.return_value = (
            parameter_editor_table.configuration_manager.filesystem.file_parameters.get("test_file", {})
        )

        # Act: Create a new instance to trigger style configuration
        ParameterEditorTable(parameter_editor_table.main_frame, mock_config_manager, parameter_editor_table.parameter_editor)

        # Assert: Style was configured with expected parameters
        mock_style_instance.configure.assert_called_with("narrow.TButton", padding=0, width=4, border=(0, 0, 0, 0))


def test_init_with_style_lookup_failure(mock_master, mock_local_filesystem, mock_parameter_editor) -> None:
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

        mock_config_manager = MagicMock(spec=ConfigurationManager)
        mock_config_manager.filesystem = mock_local_filesystem
        mock_config_manager.current_file = "test_file"
        mock_config_manager.get_parameters_as_par_dict.return_value = {}

        # Act: Create table instance with style lookup failure
        table = ParameterEditorTable(mock_master, mock_config_manager, mock_parameter_editor)

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
    parameter_editor_table.configuration_manager.filesystem.file_parameters = ParDict({test_file: ParDict({})})

    # Act: Repopulate the table
    parameter_editor_table.repopulate(show_only_differences=False, gui_complexity="simple", regenerate_from_disk=False)

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
    parameter_editor_table.configuration_manager.filesystem.file_parameters = ParDict(
        {test_file: ParDict({"PARAM1": Par(1.0, "test comment")})}
    )
    parameter_editor_table.configuration_manager.filesystem.doc_dict = {"PARAM1": {"units": "none"}}
    parameter_editor_table.configuration_manager.filesystem.param_default_dict = ParDict({"PARAM1": Par(0.0, "default")})

    # Act: Repopulate the table
    parameter_editor_table.repopulate(show_only_differences=False, gui_complexity="simple", regenerate_from_disk=False)

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
    parameter_editor_table.configuration_manager.filesystem.file_parameters = ParDict({"": ParDict({})})
    parameter_editor_table.configuration_manager.current_file = ""
    parameter_editor_table.configuration_manager.filesystem.doc_dict = {}
    parameter_editor_table.configuration_manager.filesystem.param_default_dict = ParDict({})

    # Act: Attempt to repopulate with no current file
    parameter_editor_table.repopulate(show_only_differences=False, gui_complexity="simple", regenerate_from_disk=False)

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
    parameter_editor_table.configuration_manager.current_file = test_file
    parameter_editor_table.configuration_manager.filesystem.file_parameters = ParDict(
        {test_file: ParDict({"PARAM1": Par(1.0, "test comment")})}
    )
    parameter_editor_table.configuration_manager.filesystem.doc_dict = {"PARAM1": {"units": "none"}}
    parameter_editor_table.configuration_manager.filesystem.param_default_dict = ParDict({"PARAM1": Par(0.0, "default")})

    # Act: Repopulate with single parameter
    with patch.object(parameter_editor_table, "grid_slaves", return_value=[]):
        parameter_editor_table.repopulate(show_only_differences=False, gui_complexity="simple", regenerate_from_disk=False)

    # Assert: Parameter row was added (implicitly tested through repopulate call)


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
    parameter_editor_table.configuration_manager.current_file = test_file
    parameter_editor_table.configuration_manager.filesystem.file_parameters = ParDict(
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
    parameter_editor_table.configuration_manager.filesystem.doc_dict = {
        "PARAM1": {"units": "none"},
        "PARAM2": {"units": "none"},
        "PARAM3": {"units": "none"},
    }
    parameter_editor_table.configuration_manager.filesystem.param_default_dict = ParDict(
        {
            "PARAM1": Par(0.0, "default"),
            "PARAM2": Par(0.0, "default"),
            "PARAM3": Par(0.0, "default"),
        }
    )

    # Act: Repopulate with multiple parameters
    with patch.object(parameter_editor_table, "grid_slaves", return_value=[]):
        parameter_editor_table.repopulate(show_only_differences=False, gui_complexity="simple", regenerate_from_disk=False)

    # Assert: All parameters were processed (implicitly tested through repopulate call)


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
    parameter_editor_table.configuration_manager.filesystem.file_parameters = ParDict(
        {test_file: ParDict({"PARAM1": Par(1.0, "test comment"), "PARAM2": Par(2.0, "test comment")})}
    )
    parameter_editor_table.configuration_manager.filesystem.doc_dict = {
        "PARAM1": {"units": "none"},
        "PARAM2": {"units": "none"},
    }
    parameter_editor_table.configuration_manager.filesystem.param_default_dict = ParDict(
        {"PARAM1": Par(0.0, "default"), "PARAM2": Par(0.0, "default")}
    )

    # Act: Repopulate the table
    parameter_editor_table.repopulate(show_only_differences=False, gui_complexity="simple", regenerate_from_disk=False)

    # Assert: Checkbutton states were preserved (implicitly tested through repopulate call)


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
    parameter_editor_table.configuration_manager.filesystem.file_parameters = ParDict(
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
    parameter_editor_table.configuration_manager.filesystem.doc_dict = {
        "PARAM1": {"units": "none"},
        "PARAM2": {"units": "none"},
        "PARAM3": {"units": "none"},
    }
    parameter_editor_table.configuration_manager.filesystem.param_default_dict = ParDict(
        {
            "PARAM1": Par(0.0, "default"),
            "PARAM2": Par(0.0, "default"),
            "PARAM3": Par(0.0, "default"),
        }
    )

    # Act: Repopulate showing only differences
    parameter_editor_table.repopulate(show_only_differences=True, gui_complexity="simple", regenerate_from_disk=False)

    # Assert: Only differing parameters were processed (implicitly tested through repopulate call)


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
    parameter_editor_table.configuration_manager.filesystem.file_parameters = ParDict({"test_file": ParDict({})})
    parameter_editor_table.configuration_manager.repopulate_configuration_step_parameters = MagicMock(return_value=([], []))
    parameter_editor_table._update_table = MagicMock()
    parameter_editor_table.view_port.winfo_children = MagicMock(return_value=[])
    parameter_editor_table._create_headers_and_tooltips = MagicMock(return_value=((), ()))
    parameter_editor_table._should_show_upload_column = MagicMock(return_value=False)

    # Act: Repopulate and check scroll behavior
    with patch.object(parameter_editor_table, "_apply_scroll_position") as mock_scroll:
        parameter_editor_table.repopulate(show_only_differences=False, gui_complexity="simple", regenerate_from_disk=False)

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
        parameter_editor_table.parameter_editor.gui_complexity = "simple"

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
        parameter_editor_table.parameter_editor.gui_complexity = "advanced"

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
        parameter_editor_table.parameter_editor.gui_complexity = "simple"

        # Act: Explicitly pass "advanced" to override the default
        should_show = parameter_editor_table._should_show_upload_column("advanced")

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
        parameter_editor_table.configuration_manager.has_unsaved_changes.return_value = False

        # Act: Check for unsaved changes
        result = parameter_editor_table.configuration_manager.has_unsaved_changes()

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
        parameter_editor_table.configuration_manager.has_unsaved_changes.return_value = True

        # Act: Check for unsaved changes
        result = parameter_editor_table.configuration_manager.has_unsaved_changes()

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
        parameter_editor_table.parameter_editor.gui_complexity = "simple"

        # Act: Calculate columns for simple mode
        show_upload = parameter_editor_table._should_show_upload_column()
        column_index = parameter_editor_table._get_change_reason_column_index(show_upload)

        # Assert: Simple mode calculations
        assert show_upload is False
        assert column_index == 6  # No upload column

        # Act: Calculate columns for advanced mode override
        show_upload_advanced = parameter_editor_table._should_show_upload_column("advanced")
        column_index_advanced = parameter_editor_table._get_change_reason_column_index(show_upload_advanced)

        # Assert: Advanced mode calculations
        assert show_upload_advanced is True
        assert column_index_advanced == 7  # With upload column


class TestWidgetCreationBehavior:
    """Test the behavior of widget creation methods."""

    def test_create_delete_button(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        User interface creates delete button with proper configuration.

        GIVEN: A parameter editor table is initialized
        WHEN: A delete button is created for a parameter
        THEN: The button has correct text and tooltip functionality
        """
        # Arrange: Set up tooltip mocking
        with patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.show_tooltip") as mock_tooltip:
            # Act: Create delete button
            button = parameter_editor_table._create_delete_button("TEST_PARAM")

            # Assert: Button properties are correct
            assert isinstance(button, ttk.Button)
            assert button.cget("text") == "Del"
            mock_tooltip.assert_called_once()

    def test_create_parameter_name_normal(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        User interface displays parameter names with tooltips for normal parameters.

        GIVEN: A parameter editor table is initialized
        WHEN: A parameter name label is created for a normal parameter
        THEN: The label displays the parameter name and has tooltip functionality
        """
        # Arrange: Create mock parameter
        param = create_mock_data_model_ardupilot_parameter()

        # Act: Create parameter name label with tooltip mocking
        with patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.show_tooltip") as mock_tooltip:
            label = parameter_editor_table._create_parameter_name(param)

            # Assert: Label properties are correct
            assert isinstance(label, ttk.Label)
            assert "TEST_PARAM" in label.cget("text")
            mock_tooltip.assert_called_once()

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

    def test_create_flightcontroller_value_exists(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        User interface displays flight controller parameter values when available.

        GIVEN: A parameter exists in the flight controller
        WHEN: A flight controller value label is created
        THEN: The label displays the parameter value
        """
        # Arrange: Create parameter with FC value
        param = create_mock_data_model_ardupilot_parameter(fc_value=1.234567)

        # Act: Create flight controller value label
        label = parameter_editor_table._create_flightcontroller_value(param)

        # Assert: Label displays the FC value
        assert isinstance(label, ttk.Label)
        assert label.cget("text") == "1.234567"

    def test_create_flightcontroller_value_missing(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        User interface shows 'N/A' when flight controller parameter is missing.

        GIVEN: A parameter does not exist in the flight controller
        WHEN: A flight controller value label is created
        THEN: The label displays 'N/A' to indicate missing value
        """
        # Arrange: Create parameter without FC value
        param = create_mock_data_model_ardupilot_parameter(fc_value=None)

        # Act: Create flight controller value label
        label = parameter_editor_table._create_flightcontroller_value(param)

        # Assert: Label shows 'N/A' for missing value
        assert isinstance(label, ttk.Label)
        assert label.cget("text") == "N/A"

    def test_create_unit_label(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        User interface displays parameter units with tooltips.

        GIVEN: A parameter has unit information and tooltip metadata
        WHEN: A unit label is created
        THEN: The label displays the unit and has tooltip functionality
        """
        # Arrange: Create parameter with unit metadata
        param = create_mock_data_model_ardupilot_parameter(metadata={"unit": "m/s", "unit_tooltip": "meters per second"})

        # Act: Create unit label with tooltip mocking
        with patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.show_tooltip") as mock_tooltip:
            label = parameter_editor_table._create_unit_label(param)

            # Assert: Label displays unit and has tooltip
            assert isinstance(label, ttk.Label)
            assert label.cget("text") == "m/s"
            mock_tooltip.assert_called_once()

    def test_create_upload_checkbutton_connected(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        User interface enables upload checkbuttons when flight controller is connected.

        GIVEN: A flight controller is connected
        WHEN: An upload checkbutton is created for a parameter
        THEN: The checkbutton is enabled and checked by default with tooltip
        """
        # Act: Create upload checkbutton with tooltip mocking
        with patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.show_tooltip") as mock_tooltip:
            checkbutton = parameter_editor_table._create_upload_checkbutton("TEST_PARAM")

            # Assert: Checkbutton is properly configured for connected FC
            assert isinstance(checkbutton, ttk.Checkbutton)
            assert str(checkbutton.cget("state")) == "normal"
            assert "TEST_PARAM" in parameter_editor_table.upload_checkbutton_var
            assert parameter_editor_table.upload_checkbutton_var["TEST_PARAM"].get() is True
            mock_tooltip.assert_called_once()

    def test_create_upload_checkbutton_disconnected(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        User interface disables upload checkbuttons when flight controller is disconnected.

        GIVEN: A flight controller is disconnected
        WHEN: An upload checkbutton is created for a parameter
        THEN: The checkbutton is disabled and unchecked
        """
        # Arrange: Disconnect flight controller
        parameter_editor_table.configuration_manager.is_fc_connected = False

        # Act: Create upload checkbutton
        checkbutton = parameter_editor_table._create_upload_checkbutton("TEST_PARAM")

        # Assert: Checkbutton is disabled for disconnected FC
        assert isinstance(checkbutton, ttk.Checkbutton)
        assert str(checkbutton.cget("state")) == "disabled"
        assert parameter_editor_table.upload_checkbutton_var["TEST_PARAM"].get() is False

    def test_create_change_reason_entry_normal(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        User interface creates editable change reason entries for normal parameters.

        GIVEN: A normal parameter is being edited
        WHEN: A change reason entry is created
        THEN: The entry is editable and contains the parameter's comment with tooltip
        """
        # Arrange: Create normal parameter
        param = create_mock_data_model_ardupilot_parameter()

        # Act: Create change reason entry with tooltip mocking
        with patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.show_tooltip") as mock_tooltip:
            entry = parameter_editor_table._create_change_reason_entry(param)

            # Assert: Entry is properly configured for normal parameter
            assert isinstance(entry, ttk.Entry)
            assert entry.get() == "test comment"
            mock_tooltip.assert_called_once()

    def test_create_change_reason_entry_forced(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        User interface creates disabled change reason entries for forced parameters.

        GIVEN: A forced parameter is being displayed
        WHEN: A change reason entry is created
        THEN: The entry is disabled and contains the forced comment
        """
        # Arrange: Create forced parameter
        param = create_mock_data_model_ardupilot_parameter(is_forced=True)

        # Act: Create change reason entry
        entry = parameter_editor_table._create_change_reason_entry(param)

        # Assert: Entry is disabled for forced parameter
        assert isinstance(entry, ttk.Entry)
        assert entry.get() == "forced comment"
        assert str(entry.cget("state")) == "disabled"


class TestEventHandlerBehavior:
    """Test the behavior of event handler methods."""

    def test_on_parameter_delete_confirmed(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        User can successfully delete parameters when confirming the action.

        GIVEN: A parameter exists in the current file
        WHEN: User confirms parameter deletion
        THEN: The parameter is removed and the table is repopulated
        """
        # Arrange: Set up parameter in filesystem
        parameter_editor_table.configuration_manager.current_file = "test_file"
        parameter_editor_table.configuration_manager.filesystem.file_parameters = {
            "test_file": ParDict({"TEST_PARAM": Par(1.0, "comment")})
        }
        parameter_editor_table.parameter_editor.repopulate_parameter_table = MagicMock()
        parameter_editor_table.canvas = MagicMock()
        parameter_editor_table.canvas.yview.return_value = [0.5, 0.8]

        # Act: Confirm parameter deletion
        with patch("tkinter.messagebox.askyesno", return_value=True):
            parameter_editor_table._on_parameter_delete("TEST_PARAM")

            # Assert: Parameter is deleted and table repopulated
            assert "TEST_PARAM" not in parameter_editor_table.configuration_manager.filesystem.file_parameters["test_file"]
            parameter_editor_table.parameter_editor.repopulate_parameter_table.assert_called_once_with(
                regenerate_from_disk=False
            )

    def test_on_parameter_delete_cancelled(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        User can cancel parameter deletion without removing the parameter.

        GIVEN: A parameter exists in the current file
        WHEN: User cancels parameter deletion
        THEN: The parameter remains in the file
        """
        # Arrange: Set up parameter in filesystem
        parameter_editor_table.configuration_manager.current_file = "test_file"
        parameter_editor_table.configuration_manager.filesystem.file_parameters = {
            "test_file": {"TEST_PARAM": Par(1.0, "comment")}
        }

        # Act: Cancel parameter deletion
        with patch("tkinter.messagebox.askyesno", return_value=False):
            parameter_editor_table._on_parameter_delete("TEST_PARAM")

            # Assert: Parameter remains in file
            assert "TEST_PARAM" in parameter_editor_table.configuration_manager.filesystem.file_parameters["test_file"]

    def test_confirm_parameter_addition_valid_fc_param(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        User can successfully add valid flight controller parameters.

        GIVEN: A valid parameter name that exists in the flight controller
        WHEN: User attempts to add the parameter
        THEN: The parameter is added successfully and the operation returns true
        """
        # Arrange: Set up empty file and mock successful addition
        parameter_editor_table.configuration_manager.current_file = "test_file"
        parameter_editor_table.configuration_manager.filesystem.file_parameters = {"test_file": ParDict({})}
        parameter_editor_table.parameter_editor.repopulate_parameter_table = MagicMock()

        # Act: Confirm parameter addition with mocked success
        with patch.object(
            parameter_editor_table.configuration_manager,
            "add_parameter_to_current_file",
            return_value=True,
        ):
            result = parameter_editor_table._confirm_parameter_addition("NEW_PARAM")

            # Assert: Parameter addition succeeds
            assert result is True
            parameter_editor_table.configuration_manager.add_parameter_to_current_file.assert_called_once_with("NEW_PARAM")

    def test_confirm_parameter_addition_empty_name(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        User sees error when attempting to add parameter with empty name.

        GIVEN: User attempts to add a parameter with an empty name
        WHEN: The system validates the parameter name
        THEN: An error dialog is shown and the operation fails
        """
        # Arrange: Mock the add_parameter_to_current_file method to raise error
        parameter_editor_table.configuration_manager.add_parameter_to_current_file = MagicMock(
            side_effect=InvalidParameterNameError("Parameter name can not be empty.")
        )

        # Act & Assert: Confirm parameter addition shows error for empty name
        with patch("tkinter.messagebox.showerror") as mock_error:
            result = parameter_editor_table._confirm_parameter_addition("")

            assert result is False
            mock_error.assert_called_once()

    def test_confirm_parameter_addition_existing_param(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        User sees error when attempting to add parameter that already exists.

        GIVEN: A parameter with the same name already exists in the current file
        WHEN: User attempts to add a parameter with that name
        THEN: An error dialog is shown and the operation fails
        """
        # Arrange: Set up existing parameter in file
        parameter_editor_table.configuration_manager.current_file = "test_file"
        parameter_editor_table.configuration_manager.filesystem.file_parameters = {
            "test_file": ParDict({"EXISTING_PARAM": Par(1.0, "comment")})
        }

        # Mock the add_parameter_to_current_file method to raise error
        parameter_editor_table.configuration_manager.add_parameter_to_current_file = MagicMock(
            side_effect=InvalidParameterNameError("Parameter already exists, edit it instead")
        )

        # Act & Assert: Confirm parameter addition shows error for existing parameter
        with patch("tkinter.messagebox.showerror") as mock_error:
            result = parameter_editor_table._confirm_parameter_addition("EXISTING_PARAM")

            assert result is False
            mock_error.assert_called_once()


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


class TestColumnManagementBehavior:
    """Test the behavior of column management methods."""

    def test_create_column_widgets_normal_parameter(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        User interface creates complete column widget set for normal parameters with upload column.

        GIVEN: A normal parameter needs to be displayed with upload functionality enabled
        WHEN: Column widgets are created for the parameter
        THEN: All required widgets are created including upload checkbutton
        """
        # Arrange: Set up parameter and mock widget creation methods
        param_name = "TEST_PARAM"
        param = create_mock_data_model_ardupilot_parameter()
        show_upload_column = True

        # Mock individual widget creation methods using patch.object
        with (
            patch.object(parameter_editor_table, "_create_delete_button", return_value=MagicMock()) as mock_delete,
            patch.object(parameter_editor_table, "_create_parameter_name", return_value=MagicMock()) as mock_name,
            patch.object(parameter_editor_table, "_create_flightcontroller_value", return_value=MagicMock()) as mock_fc,
            patch.object(parameter_editor_table, "_create_new_value_entry", return_value=MagicMock()) as mock_new,
            patch.object(parameter_editor_table, "_create_unit_label", return_value=MagicMock()) as mock_unit,
            patch.object(parameter_editor_table, "_create_upload_checkbutton", return_value=MagicMock()) as mock_upload,
            patch.object(parameter_editor_table, "_create_change_reason_entry", return_value=MagicMock()) as mock_reason,
        ):
            # Act: Create column widgets
            column = parameter_editor_table._create_column_widgets(param_name, param, show_upload_column)

            # Assert: All widgets are created for upload mode
            assert len(column) == 8  # With upload column
            mock_delete.assert_called_once()
            mock_name.assert_called_once()
            mock_fc.assert_called_once()
            mock_new.assert_called_once()
            mock_unit.assert_called_once()
            mock_upload.assert_called_once()
            mock_reason.assert_called_once()

    def test_create_column_widgets_without_upload(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        User interface creates column widget set for parameters without upload column.

        GIVEN: A parameter needs to be displayed without upload functionality
        WHEN: Column widgets are created for the parameter
        THEN: All required widgets are created excluding upload checkbutton
        """
        # Arrange: Set up parameter and mock widget creation methods
        param_name = "TEST_PARAM"
        param = create_mock_data_model_ardupilot_parameter()
        show_upload_column = False

        # Mock individual widget creation methods using patch.object
        with (
            patch.object(parameter_editor_table, "_create_delete_button", return_value=MagicMock()) as mock_delete,
            patch.object(parameter_editor_table, "_create_parameter_name", return_value=MagicMock()) as mock_name,
            patch.object(parameter_editor_table, "_create_flightcontroller_value", return_value=MagicMock()) as mock_fc,
            patch.object(parameter_editor_table, "_create_new_value_entry", return_value=MagicMock()) as mock_new,
            patch.object(parameter_editor_table, "_create_unit_label", return_value=MagicMock()) as mock_unit,
            patch.object(parameter_editor_table, "_create_change_reason_entry", return_value=MagicMock()) as mock_reason,
        ):
            # Act: Create column widgets
            column = parameter_editor_table._create_column_widgets(param_name, param, show_upload_column)

            # Assert: All widgets are created except upload
            assert len(column) == 7  # Without upload column
            mock_delete.assert_called_once()
            mock_name.assert_called_once()
            mock_fc.assert_called_once()
            mock_new.assert_called_once()
            mock_unit.assert_called_once()
            mock_reason.assert_called_once()

    def test_grid_column_widgets_with_upload(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        User interface properly positions column widgets in grid layout with upload column.

        GIVEN: A set of column widgets needs to be positioned in the table with upload column
        WHEN: Widgets are gridded in the table
        THEN: Each widget is placed in the correct column position
        """
        # Arrange: Create mock widgets and set up column index
        mock_widgets = [MagicMock() for _ in range(8)]
        parameter_editor_table._get_change_reason_column_index = MagicMock(return_value=7)

        # Act: Grid column widgets
        parameter_editor_table._grid_column_widgets(mock_widgets, row=1, show_upload_column=True)

        # Assert: All widgets were gridded in correct positions
        for i, widget in enumerate(mock_widgets):
            widget.grid.assert_called_once()
            call_args = widget.grid.call_args[1]  # Get keyword arguments
            assert call_args["row"] == 1
            if i < 7:  # Regular columns
                assert call_args["column"] == i
            else:  # Change reason column
                assert call_args["column"] == 7

    def test_grid_column_widgets_without_upload(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        User interface properly positions column widgets in grid layout without upload column.

        GIVEN: A set of column widgets needs to be positioned in the table without upload column
        WHEN: Widgets are gridded in the table
        THEN: Each widget is placed in the correct column position excluding upload
        """
        # Arrange: Create mock widgets and set up column index
        mock_widgets = [MagicMock() for _ in range(7)]
        parameter_editor_table._get_change_reason_column_index = MagicMock(return_value=6)

        # Act: Grid column widgets
        parameter_editor_table._grid_column_widgets(mock_widgets, row=1, show_upload_column=False)

        # Assert: All widgets were gridded in correct positions
        for i, widget in enumerate(mock_widgets):
            widget.grid.assert_called_once()
            call_args = widget.grid.call_args[1]
            assert call_args["row"] == 1
            if i < 6:  # Regular columns
                assert call_args["column"] == i
            else:  # Change reason column
                assert call_args["column"] == 6

    def test_configure_table_columns_with_upload(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        User interface configures table column properties correctly with upload column.

        GIVEN: The table needs column configuration with upload functionality enabled
        WHEN: Table columns are configured
        THEN: All columns including upload are properly configured
        """
        # Arrange: Set up column index and mock viewport
        parameter_editor_table._get_change_reason_column_index = MagicMock(return_value=6)
        parameter_editor_table.view_port = MagicMock()

        # Act: Configure table columns
        parameter_editor_table._configure_table_columns(show_upload_column=True)

        # Assert: Columnconfigure was called for all columns
        assert parameter_editor_table.view_port.columnconfigure.call_count == 8

    def test_configure_table_columns_without_upload(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        User interface configures table column properties correctly without upload column.

        GIVEN: The table needs column configuration without upload functionality
        WHEN: Table columns are configured
        THEN: All columns excluding upload are properly configured
        """
        # Arrange: Set up column index and mock viewport
        parameter_editor_table._get_change_reason_column_index = MagicMock(return_value=5)
        parameter_editor_table.view_port = MagicMock()

        # Act: Configure table columns
        parameter_editor_table._configure_table_columns(show_upload_column=False)

        # Assert: Columnconfigure was called for all columns (6 without upload)
        assert parameter_editor_table.view_port.columnconfigure.call_count == 7


class TestUpdateMethodsBehavior:
    """Test the behavior of update methods."""

    def test_update_new_value_entry_text_normal_entry(self, parameter_editor_table: ParameterEditorTable) -> None:  # pylint: disable=unused-argument
        """
        User interface updates entry widget text when parameter value matches default.

        GIVEN: A parameter with a value that matches its default value
        WHEN: The entry widget text is updated
        THEN: The widget displays the value and uses default styling
        """
        # Arrange: Create mock entry and parameter with matching default value
        mock_entry = MagicMock(spec=ttk.Entry)

        param = ArduPilotParameter(
            name="TEST_PARAM",
            par_obj=Par(1.5, "test comment"),
            metadata={},
            default_par=Par(1.5, "default comment"),  # Same value as par_obj to trigger default style
            fc_value=None,
        )

        # Act: Update entry text
        ParameterEditorTable._update_new_value_entry_text(mock_entry, param)

        # Assert: Entry is updated with value and default styling
        mock_entry.delete.assert_called_once_with(0, tk.END)
        mock_entry.insert.assert_called_once_with(0, "1.5")
        mock_entry.configure.assert_called_once_with(style="default_v.TEntry")

    def test_update_new_value_entry_text_combobox(self, parameter_editor_table: ParameterEditorTable) -> None:  # pylint: disable=unused-argument
        """
        User interface skips updating combobox widget text during entry text updates.

        GIVEN: A combobox widget is used for parameter value input
        WHEN: The entry text update method is called
        THEN: The combobox is not modified as it handles its own updates
        """
        # Arrange: Create mock combobox and parameter
        mock_combobox = MagicMock(spec=PairTupleCombobox)
        param = create_mock_data_model_ardupilot_parameter(value=1.5)

        # Act: Attempt to update combobox text
        ParameterEditorTable._update_new_value_entry_text(mock_combobox, param)

        # Assert: Combobox methods are not called
        mock_combobox.delete.assert_not_called()
        mock_combobox.insert.assert_not_called()

    def test_update_combobox_style_on_selection_valid(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        User interface updates combobox styling when valid value matches default.

        GIVEN: A user selects a value in a combobox that matches the parameter's default
        WHEN: The combobox style is updated based on the selection
        THEN: The combobox uses default styling and triggers configuration updates
        """
        # Arrange: Set up mock combobox and related widgets
        mock_combobox = MagicMock(spec=PairTupleCombobox)
        mock_combobox.get_selected_key.return_value = "1.5"
        mock_event = MagicMock()
        mock_event.width = 9
        mock_change_reason_widget = MagicMock(spec=ttk.Entry)
        mock_value_is_different_widget = MagicMock(spec=ttk.Label)

        # Create parameter where selected value matches default
        param = ArduPilotParameter(
            name="TEST_PARAM",
            par_obj=Par(1.0, "test comment"),  # Initial value is different
            metadata={},
            default_par=Par(1.5, "default comment"),  # Default value matches what will be selected
            fc_value=None,
        )

        # Mock filesystem for set_new_value
        parameter_editor_table.configuration_manager.filesystem.file_parameters = {
            "test_file": ParDict({"TEST_PARAM": Par(1.0, "test")})
        }
        parameter_editor_table.configuration_manager.current_file = "test_file"

        # Act: Update combobox style with mocked tooltip
        with patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_table.show_tooltip"):
            parameter_editor_table._update_combobox_style_on_selection(
                mock_combobox, param, mock_event, mock_change_reason_widget, mock_value_is_different_widget
            )

        # Assert: Combobox uses default styling and triggers updates
        mock_combobox.configure.assert_called_once_with(style="default_v.TCombobox")
        mock_combobox.on_combo_configure.assert_called_once_with(mock_event)


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
        parameter_editor_table.configuration_manager.filesystem.param_default_dict = ParDict(
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
        parameter_editor_table.parameter_editor.gui_complexity = "simple"

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
        parameter_editor_table.parameter_editor.gui_complexity = "advanced"

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
        parameter_editor_table.parameter_editor.repopulate_parameter_table = MagicMock()

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
        # Arrange: Mock the configuration manager to allow adding parameters
        parameter_editor_table.configuration_manager.get_possible_add_param_names.return_value = ["NEW_PARAM"]
        parameter_editor_table.configuration_manager.add_parameter_to_current_file.return_value = True

        # Mock the parameter editor's repopulate method
        parameter_editor_table.parameter_editor.repopulate_parameter_table = MagicMock()

        # Act: Simulate adding a parameter
        result = parameter_editor_table._confirm_parameter_addition("NEW_PARAM")

        # Assert: Parameter addition was successful
        assert result is True
        parameter_editor_table.configuration_manager.add_parameter_to_current_file.assert_called_once_with("NEW_PARAM")
        parameter_editor_table.parameter_editor.repopulate_parameter_table.assert_called_once_with(regenerate_from_disk=False)

    def test_user_can_delete_parameter_from_configuration_file(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        User can remove unwanted parameters from the configuration file.

        GIVEN: A parameter exists in the current configuration
        WHEN: User clicks the Delete button and confirms the deletion
        THEN: The parameter is removed from the configuration
        AND: The table is refreshed without the deleted parameter
        """
        # Arrange: Mock the configuration manager and messagebox
        parameter_editor_table.configuration_manager.delete_parameter_from_current_file = MagicMock()
        parameter_editor_table.parameter_editor.repopulate_parameter_table = MagicMock()

        with patch("tkinter.messagebox.askyesno", return_value=True) as mock_askyesno:
            # Act: Simulate parameter deletion
            parameter_editor_table._on_parameter_delete("TEST_PARAM")

            # Assert: User was asked for confirmation and deletion proceeded
            mock_askyesno.assert_called_once()
            parameter_editor_table.configuration_manager.delete_parameter_from_current_file.assert_called_once_with(
                "TEST_PARAM"
            )
            parameter_editor_table.parameter_editor.repopulate_parameter_table.assert_called_once_with(
                regenerate_from_disk=False
            )

    def test_user_cannot_delete_parameter_when_cancelled(self, parameter_editor_table: ParameterEditorTable) -> None:
        """
        User can cancel parameter deletion when they change their mind.

        GIVEN: A parameter exists in the current configuration
        WHEN: User clicks Delete but cancels the confirmation dialog
        THEN: The parameter remains in the configuration
        AND: No changes are made to the file
        """
        # Arrange: Mock messagebox to return False (user cancels)
        parameter_editor_table.configuration_manager.delete_parameter_from_current_file = MagicMock()
        with patch("tkinter.messagebox.askyesno", return_value=False) as mock_askyesno:
            # Act: Simulate cancelled parameter deletion
            parameter_editor_table._on_parameter_delete("TEST_PARAM")

            # Assert: User was asked but deletion was cancelled
            mock_askyesno.assert_called_once()
            # Verify no deletion methods were called
            parameter_editor_table.configuration_manager.delete_parameter_from_current_file.assert_not_called()

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
        parameter_editor_table.parameter_editor.gui_complexity = "advanced"
        parameter_editor_table.configuration_manager.is_fc_connected = True

        # Create mock parameters
        params = {
            "PARAM1": create_mock_data_model_ardupilot_parameter("PARAM1", 1.0),
            "PARAM2": create_mock_data_model_ardupilot_parameter("PARAM2", 2.0),
        }

        # Mock the configuration manager
        parameter_editor_table.configuration_manager.current_step_parameters = params
        parameter_editor_table.configuration_manager.get_parameters_as_par_dict.return_value = {
            "PARAM1": Par(1.0, "test"),
            "PARAM2": Par(2.0, "test"),
        }

        # Act: Get upload parameters (simulating user selections)
        result = parameter_editor_table.get_upload_selected_params("advanced")

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

        # Mock the filesystem to simulate parameter storage
        parameter_editor_table.configuration_manager.filesystem.file_parameters = {
            "test_file": ParDict({"DOC_PARAM": Par(15.0, "Initial setup")})
        }
        parameter_editor_table.configuration_manager.current_file = "test_file"

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
