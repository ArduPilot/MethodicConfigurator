#!/usr/bin/env python3

"""
Tests for the ComponentTemplateManager class.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from tkinter import ttk
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.frontend_tkinter_component_template_manager import ComponentTemplateManager


class TestComponentTemplateManager:
    """Test suite for ComponentTemplateManager."""

    @pytest.fixture
    def mock_callbacks(self) -> tuple[MagicMock, MagicMock, MagicMock]:
        """Setup mock callbacks for testing."""
        get_component_data = MagicMock(return_value={"Model": "XYZ", "Version": "1.0"})
        update_data = MagicMock()
        derive_name = MagicMock(return_value="XYZ_1.0")
        return get_component_data, update_data, derive_name

    @pytest.fixture
    def entry_widgets(self, root) -> dict[tuple, ttk.Entry]:
        """Setup entry widgets for testing."""
        frame = ttk.Frame(root)

        entry1 = ttk.Entry(frame)
        entry1.insert(0, "XYZ")

        entry2 = ttk.Entry(frame)
        entry2.insert(0, "1.0")

        entry3 = ttk.Entry(frame)
        entry3.insert(0, "10")

        return {
            ("Component1", "Model"): entry1,
            ("Component1", "Version"): entry2,
            ("Component2", "Value"): entry3,
        }

    @pytest.fixture
    def template_manager(self, root, entry_widgets, mock_callbacks) -> ComponentTemplateManager:
        """Create ComponentTemplateManager instance for testing."""
        get_data_callback, update_callback, derive_name_callback = mock_callbacks
        manager = ComponentTemplateManager(root, entry_widgets, get_data_callback, update_callback, derive_name_callback)
        # Mock the VehicleComponents to avoid actual file operations
        manager.template_manager = MagicMock()
        return manager

    def test_initialization(self, template_manager, root, entry_widgets, mock_callbacks) -> None:
        """Test that initialization correctly sets up instance variables."""
        get_data_callback, update_callback, derive_name_callback = mock_callbacks

        assert template_manager.root == root
        assert template_manager.entry_widgets == entry_widgets
        assert template_manager.buttons == {}
        assert template_manager.current_menu is None
        assert template_manager.get_component_data_callback == get_data_callback
        assert template_manager.update_data_callback == update_callback
        assert template_manager.derive_template_name_callback == derive_name_callback

    def test_derive_initial_template_name(self, template_manager, mock_callbacks) -> None:
        """Test that derive_initial_template_name correctly uses callback."""
        _, _, derive_name_callback = mock_callbacks
        component_data = {"Model": "ABC", "Version": "2.0"}

        template_name = template_manager.derive_initial_template_name(component_data)

        derive_name_callback.assert_called_once_with(component_data)
        assert template_name == "XYZ_1.0"  # From the mock's return value

    def test_add_template_controls(self, root, template_manager) -> None:
        """Test that add_template_controls creates and adds buttons correctly."""
        parent_frame = ttk.LabelFrame(root, text="Test Component")

        template_manager.add_template_controls(parent_frame, "TestComponent")

        # Verify that a dropdown button was stored for this component
        assert "TestComponent" in template_manager.buttons
        assert isinstance(template_manager.buttons["TestComponent"], ttk.Button)

    @patch("tkinter.simpledialog.askstring", return_value="New Template")
    @patch("tkinter.messagebox.askyesno", return_value=False)
    @patch("tkinter.messagebox.showinfo")
    @patch("tkinter.messagebox.showerror")
    def test_save_component_as_template_new(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        mock_error,
        mock_info,
        mock_askyesno,  # pylint: disable=unused-argument
        mock_askstring,  # pylint: disable=unused-argument
        template_manager,
        mock_callbacks,
    ) -> None:
        """Test saving a new template."""
        get_data_callback, _, _ = mock_callbacks

        # Setup mock for template manager
        template_manager.template_manager.load_component_templates.return_value = {"TestComponent": []}

        # Call the method
        template_manager.save_component_as_template("TestComponent")

        # Verify interactions
        get_data_callback.assert_called_once_with("TestComponent")
        template_manager.template_manager.load_component_templates.assert_called_once()
        template_manager.template_manager.save_component_templates.assert_called_once()
        mock_info.assert_called_once()
        mock_error.assert_not_called()

    @patch("tkinter.simpledialog.askstring", return_value="Existing Template")
    @patch("tkinter.messagebox.askyesno", return_value=True)  # Confirm overwrite
    @patch("tkinter.messagebox.showinfo")
    def test_save_component_as_template_existing(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        mock_info,  # pylint: disable=unused-argument
        mock_askyesno,
        mock_askstring,  # pylint: disable=unused-argument
        template_manager,
        mock_callbacks,
    ) -> None:
        """Test overwriting an existing template."""
        get_data_callback, _, _ = mock_callbacks
        component_data = {"Model": "XYZ", "Version": "1.0"}
        get_data_callback.return_value = component_data

        # Setup mock for template manager with existing template
        existing_templates = {"TestComponent": [{"name": "Existing Template", "data": {"old": "data"}}]}
        template_manager.template_manager.load_component_templates.return_value = existing_templates

        # Call the method
        template_manager.save_component_as_template("TestComponent")

        # Verify template was updated
        mock_askyesno.assert_called_once()
        template_manager.template_manager.save_component_templates.assert_called_once()

        # Verify the template was updated, not added
        args = template_manager.template_manager.save_component_templates.call_args[0][0]
        assert len(args["TestComponent"]) == 1
        assert args["TestComponent"][0]["name"] == "Existing Template"
        assert args["TestComponent"][0]["data"] == component_data

    @patch("tkinter.simpledialog.askstring", return_value=None)  # User cancels
    def test_save_component_as_template_cancel(self, mock_askstring, template_manager) -> None:  # pylint: disable=unused-argument
        """Test canceling template save dialog."""
        # Call the method
        template_manager.save_component_as_template("TestComponent")

        # Verify no save was attempted
        template_manager.template_manager.save_component_templates.assert_not_called()

    def test_show_template_options_no_templates(self, template_manager) -> None:
        """Test showing template options when no templates exist."""
        # Setup mock button
        mock_button = MagicMock()
        template_manager.buttons["TestComponent"] = mock_button
        mock_button.winfo_rootx.return_value = 100
        mock_button.winfo_rooty.return_value = 100
        mock_button.winfo_height.return_value = 25

        # Setup empty templates
        template_manager.template_manager.load_component_templates.return_value = {}

        # Call the method with patched menu
        with patch("tkinter.Menu.post") as mock_post:
            template_manager.show_template_options("TestComponent")
            mock_post.assert_called_once()

    def test_apply_component_template(self, template_manager, entry_widgets, mock_callbacks) -> None:
        """Test applying a template to a component."""
        _, update_callback, _ = mock_callbacks

        # Create a template with test data
        template = {"name": "Test Template", "data": {"Model": "NewModel", "Version": "2.0"}}

        # Apply patches within the test
        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_component_template_manager._", lambda s: s),
            patch("tkinter.messagebox.showinfo") as mock_showinfo,
        ):
            # Apply the template
            template_manager.apply_component_template("Component1", template)

            # Verify the callback was called
            update_callback.assert_called_once_with("Component1", template["data"])

            # Verify entry widgets were updated
            assert entry_widgets[("Component1", "Model")].get() == "NewModel"
            assert entry_widgets[("Component1", "Version")].get() == "2.0"

            # Verify message box was shown
            mock_showinfo.assert_called_once()
            args, _ = mock_showinfo.call_args
            assert args[0] == "Template Applied"
            assert "Test Template" in args[1]
            assert "Component1" in args[1]

    def test_create_template_dropdown_button(self, root, template_manager) -> None:
        """Test creating a template dropdown button."""
        frame = ttk.Frame(root)

        button = template_manager.create_template_dropdown_button(frame, "TestComponent")

        assert isinstance(button, ttk.Button)
        assert button["text"] == "▼"
        assert button["width"] == 2

    def test_save_component_as_template_no_data(self, template_manager, mock_callbacks) -> None:
        """
        Test that saving a component with no data shows an error.

        GIVEN: A component with no data to save
        WHEN: User attempts to save it as a template
        THEN: An error message should be displayed and no template should be saved
        """
        get_data_callback, _, _ = mock_callbacks
        get_data_callback.return_value = {}

        with patch("tkinter.messagebox.showerror") as mock_error:
            template_manager.save_component_as_template("TestComponent")
            mock_error.assert_called_once()

    def test_apply_template_missing_keys(self, template_manager, entry_widgets, mock_callbacks) -> None:
        """
        Test applying a template that doesn't contain all required keys.

        GIVEN: A template with incomplete data for a component
        WHEN: User applies the template to the component
        THEN: Only matching fields should be updated and other fields remain unchanged
        """
        _, update_callback, _ = mock_callbacks  # pylint: disable=unused-variable
        template = {"name": "Incomplete", "data": {"SomeOtherField": "value"}}

        with patch("tkinter.messagebox.showinfo"):
            template_manager.apply_component_template("Component1", template)

        # Entry should remain unchanged when key isn't in template
        assert entry_widgets[("Component1", "Model")].get() == "XYZ"

    @patch("tkinter.simpledialog.askstring", return_value="System Template")
    @patch("tkinter.messagebox.askyesno", return_value=True)  # Confirm overwrite
    @patch("tkinter.messagebox.showinfo")
    def test_save_component_as_template_override_system(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        mock_info,  # pylint: disable=unused-argument
        mock_askyesno,  # pylint: disable=unused-argument
        mock_askstring,  # pylint: disable=unused-argument
        template_manager,
        mock_callbacks,
    ) -> None:
        """Test overwriting a system template with a user template."""
        get_data_callback, _, _ = mock_callbacks
        component_data = {"Model": "Custom", "Version": "2.0"}
        get_data_callback.return_value = component_data

        # Setup mock for template manager with system template
        # When we load templates, the system and user templates will be merged
        merged_templates = {"TestComponent": [{"name": "System Template", "data": {"Model": "Original", "Version": "1.0"}}]}
        template_manager.template_manager.load_component_templates.return_value = merged_templates

        # Call the method
        template_manager.save_component_as_template("TestComponent")

        # Verify save was called with template marked as is_user_modified
        template_manager.template_manager.save_component_templates.assert_called_once()
        args = template_manager.template_manager.save_component_templates.call_args[0][0]

        assert len(args["TestComponent"]) == 1
        assert args["TestComponent"][0]["name"] == "System Template"
        assert args["TestComponent"][0]["data"] == component_data
        assert args["TestComponent"][0]["is_user_modified"] is True

    @patch("tkinter.simpledialog.askstring", return_value="Brand New Template")
    @patch("tkinter.messagebox.showinfo")
    def test_save_component_as_new_user_template(
        self,
        mock_info,  # pylint: disable=unused-argument
        mock_askstring,  # pylint: disable=unused-argument
        template_manager,
        mock_callbacks,
    ) -> None:
        """Test creating a new user template."""
        get_data_callback, _, _ = mock_callbacks
        component_data = {"Model": "New", "Version": "3.0"}
        get_data_callback.return_value = component_data

        # Setup templates - no existing template for this name
        templates = {"TestComponent": [{"name": "Other Template", "data": {}}]}
        template_manager.template_manager.load_component_templates.return_value = templates

        # Call the method
        template_manager.save_component_as_template("TestComponent")

        # Verify template was added with is_user_modified flag
        template_manager.template_manager.save_component_templates.assert_called_once()
        args = template_manager.template_manager.save_component_templates.call_args[0][0]

        assert len(args["TestComponent"]) == 2  # Two templates now
        new_template = next(t for t in args["TestComponent"] if t["name"] == "Brand New Template")
        assert new_template["data"] == component_data
        assert new_template["is_user_modified"] is True

    def test_show_template_options_combined_templates(self, template_manager) -> None:
        """Test showing template options with both system and user templates."""
        # Setup mock button
        mock_button = MagicMock()
        template_manager.buttons["TestComponent"] = mock_button
        mock_button.winfo_rootx.return_value = 100
        mock_button.winfo_rooty.return_value = 100
        mock_button.winfo_height.return_value = 25

        # Setup templates that would come from both system and user sources
        merged_templates = {
            "TestComponent": [
                {"name": "System Template", "data": {}},
                {"name": "User Template", "data": {}, "is_user_modified": True},
            ]
        }
        template_manager.template_manager.load_component_templates.return_value = merged_templates

        # Mock Menu and its add_command method
        with (
            patch("tkinter.Menu.post"),
            patch("tkinter.Menu.add_command") as mock_add_command,
        ):
            template_manager.show_template_options("TestComponent")

            # Should show two templates in alphabetical order
            calls = mock_add_command.call_args_list
            assert len(calls) == 2

            # Check template names are shown
            assert calls[0][1]["label"] == "System Template"  # S comes before U alphabetically
            assert calls[1][1]["label"] == "User Template"


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
