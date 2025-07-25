# Pytest Testing Guidelines

> **Note**: This is a comprehensive developer documentation file. For GitHub Copilot repository instructions, see [`.github/copilot-instructions.md`](../copilot-instructions.md).

## For AI Agents and Senior Developers

This document provides comprehensive guidelines for writing high-quality,
behavior-driven pytest tests for the ArduPilot Methodic Configurator project.
These guidelines ensure consistency, maintainability, and comprehensive test
coverage while following industry best practices.

## Core Testing Philosophy

### 1. Senior Developer Mindset

- Write tests that **future developers will thank you for**
- Focus on **behavior over implementation details**
- Prioritize **maintainability and readability**
- Use **minimal, strategic mocking**
- Apply **DRY principles consistently**

### 2. Behavior-Driven Development (BDD)

- Write tests that describe **user behavior** and **business value**,
  not implementation details
- Use Given-When-Then structure in test descriptions and code comments
- Focus on **what** the system should do, not **how** it does it
- Test names should read like specifications:
  `test_user_can_select_template_by_double_clicking`

### 3. Test Isolation and Independence

- Each test should be completely independent and able to run in any order
- Use fixtures with appropriate scopes (`function`, `class`, `module`, `session`)
- Clean up resources properly after tests complete
- Avoid shared mutable state between tests

All tests MUST follow this structure:

```python
def test_descriptive_behavior_name(self, fixture_name) -> None:
    """
    Brief summary of what the test validates.

    GIVEN: Initial system state and preconditions
    WHEN: The action or event being tested
    THEN: Expected outcomes and assertions
    """
    # Arrange (Given): Set up test data and mocks

    # Act (When): Execute the behavior being tested

    # Assert (Then): Verify expected outcomes
```

## 🔧 Fixture Guidelines

### Required Fixture Pattern

Create reusable fixtures that eliminate code duplication:

```python
@pytest.fixture
def mock_vehicle_provider() -> MagicMock:
    """Fixture providing a mock vehicle components provider with realistic test data."""
    provider = MagicMock()

    # Create properly structured mock data matching real object interfaces
    template_1 = MagicMock()
    template_1.attributes.return_value = ["name", "fc", "gnss"]
    template_1.name = "QuadCopter X"
    template_1.fc = "Pixhawk 6C"
    template_1.gnss = "Here3+"

    provider.get_vehicle_components_overviews.return_value = {
        "Copter/QuadX": template_1,
    }
    return provider

@pytest.fixture
def configured_window(mock_vehicle_provider) -> ComponentWindow:
    """Fixture providing a properly configured window for behavior testing."""
    with (
        patch("tkinter.Toplevel"),
        patch.object(BaseWindow, "__init__", return_value=None),
        # Only patch what's necessary for the test
    ):
        window = ComponentWindow(vehicle_components_provider=mock_vehicle_provider)
        window.root = MagicMock()
        return window
```

### Fixture Design Rules

1. **One concern per fixture** - Each fixture should have a single responsibility
2. **Realistic mock data** - Use data that mirrors real system behavior
3. **Composable fixtures** - Allow fixtures to depend on other fixtures
4. **Descriptive names** - Fixture names should clearly indicate their purpose
5. **Minimal scope** - Use the narrowest scope possible (function > class > module > session)

## 📝 Test Structure Standards

### Test Class Organization

```python
class TestUserWorkflow:
    """Test complete user workflows and interactions."""

    def test_user_can_complete_primary_task(self, configured_window) -> None:
        """
        User can successfully complete the primary workflow.

        GIVEN: A user opens the application
        WHEN: They follow the standard workflow
        THEN: They should achieve their goal without errors
        """
        # Implementation
```

### Test Method Requirements

1. **Descriptive names** - `test_user_can_select_template_by_double_clicking`
2. **Single behavior focus** - Test one behavior per method
3. **User-centric language** - Write from the user's perspective
4. **Complete documentation** - Include summary and GIVEN/WHEN/THEN

### Assertions

- Use **specific assertions** over generic ones
- **Test behavior outcomes** not implementation details
- **Group related assertions** logically
- **Include meaningful failure messages** when helpful

```python
# Good - Tests behavior
assert window.selected_template == "Copter/QuadX"
assert window.close_window.called_once()

# Bad - Tests implementation
assert mock_method.call_count == 1
```

## 🎭 Mocking Strategy

### Minimal Mocking Principle

Only mock what is **absolutely necessary**:

```python
# Good - Minimal mocking
def test_template_selection(self, template_window) -> None:
    template_window.tree.selection.return_value = ["item1"]
    template_window._on_selection_change(mock_event)
    assert template_window.selected_template == "expected_value"

# Bad - Over-mocking
def test_template_selection(self) -> None:
    with patch("tkinter.Tk"), \
         patch("module.Class1"), \
         patch("module.Class2"), \
         patch("module.method1"), \
         patch("module.method2"):
        # Test lost in mocking complexity
```

### Mocking Guidelines

1. **Mock external dependencies** (file system, network, databases)
2. **Mock UI framework calls** (tkinter widgets, events)
3. **Don't mock the system under test** - Test real behavior
4. **Use fixtures for complex mocks** - Keep test methods clean
5. **Mock return values realistically** - Match expected data types and structures

## 🏗️ Project-Specific Patterns

### Frontend Tkinter Testing

```python
# Use template_overview_window_setup fixture for complex UI mocking
def test_ui_behavior(self, template_overview_window_setup) -> None:
    """Test UI behavior without full window creation."""

# Use template_window fixture for component testing
def test_component_behavior(self, template_window) -> None:
    """Test component behavior with configured window."""
```

### Backend/Logic Testing

```python
# Use minimal mocking for business logic
def test_business_logic(self, mock_data_provider) -> None:
    """Test core logic with realistic data."""

# Mock only external dependencies
@patch('module.external_api_call')
def test_integration_behavior(self, mock_api) -> None:
    """Test integration points."""
```

## 📋 Test Categories

### Required Test Types

1. **User Workflow Tests** - Complete user journeys
2. **Component Behavior Tests** - Individual component functionality
3. **Error Handling Tests** - Graceful failure scenarios
4. **Integration Tests** - Component interaction validation
5. **Edge Case Tests** - Boundary conditions and unusual inputs

### Test Organization

```text
tests/
├── test_frontend_tkinter_component.py      # UI component tests
├── test_backend_logic.py                   # Business logic tests
├── test_integration_workflows.py           # End-to-end scenarios
└── conftest.py                             # Shared fixtures
```

## 📊 Quality Standards

### Test Quality Metrics

- **Coverage**: Aim for 80%+ on core modules
- **Maintainability**: Tests should be easy to modify
- **Speed**: Test suite should run in < 2 minutes
- **Reliability**: Zero flaky tests allowed

### Code Review Checklist

- [ ] Tests follow GIVEN/WHEN/THEN structure
- [ ] Fixtures used instead of repeated setup
- [ ] Minimal, strategic mocking applied
- [ ] User-focused test names and descriptions
- [ ] All edge cases covered
- [ ] Error scenarios tested
- [ ] Performance considerations addressed

## 🚀 Example: Complete Test Implementation

```python
class TestTemplateSelection:
    """Test user template selection workflows."""

    def test_user_can_select_template_by_double_clicking(self, template_window) -> None:
        """
        User can select a vehicle template by double-clicking on the tree item.

        GIVEN: A user views available vehicle templates
        WHEN: They double-click on a specific template row
        THEN: The template should be selected and stored
        AND: The window should close automatically
        """
        # Arrange: Configure template selection behavior
        template_window.tree.identify_row.return_value = "template_item"
        template_window.tree.item.return_value = {"text": "Copter/QuadX"}

        # Act: User double-clicks on template
        mock_event = MagicMock(y=100)
        template_window._on_row_double_click(mock_event)

        # Assert: Template selected and workflow completed
        template_window.program_settings_provider.store_template_dir.assert_called_once_with("Copter/QuadX")
        template_window.root.destroy.assert_called_once()

    def test_user_sees_visual_feedback_during_selection(self, template_window) -> None:
        """
        User receives immediate visual feedback when selecting templates.

        GIVEN: A user is browsing available templates
        WHEN: They click on a template row
        THEN: The corresponding vehicle image should be displayed immediately
        """
        # Arrange: Set up selection behavior
        template_window.tree.selection.return_value = ["selected_item"]
        template_window.tree.item.return_value = {"text": "Plane/FixedWing"}

        with patch.object(template_window, "_display_vehicle_image") as mock_display:
            # Act: User selects template
            mock_event = MagicMock()
            template_window._on_row_selection_change(mock_event)
            template_window._update_selection()  # Simulate callback

            # Assert: Visual feedback provided
            mock_display.assert_called_once_with("Plane/FixedWing")
```

## 🛠️ Development Workflow

### Pre-commit Requirements

1. **Run tests**: `pytest tests/ -v`
2. **Check coverage**: `pytest --cov=ardupilot_methodic_configurator --cov-report=term-missing`
3. **Lint with ruff**: `ruff check --fix`
4. **Type check with mypy**: `mypy .`
5. **Advanced type check with pyright**: `pyright`
6. **Style check with pylint**: `pylint $(git ls-files '*.py')`

### Test Execution Commands

```bash
# Run all tests with verbose output
pytest tests/ -v

# Run tests with coverage reporting
pytest tests/ --cov=ardupilot_methodic_configurator --cov-report=html

# Run specific test file
pytest tests/test_frontend_tkinter_template_overview.py -v

# Run tests matching pattern
pytest tests/ -k "test_user" -v

# Run tests with performance timing
pytest tests/ --durations=10
```

### Debugging Failed Tests

```bash
# Run with detailed output
pytest tests/test_file.py::test_method -v -s

# Run with pdb debugging
pytest tests/test_file.py::test_method --pdb

# Run with custom markers
pytest tests/ -m "slow" -v
```

## 🔍 Quality Assurance

### Final Validation Steps

Before submitting any test changes:

1. **Verify all tests pass**: `pytest tests/ -v`
2. **Confirm coverage maintained**: Check coverage report
3. **Lint compliance**: `ruff check` (must pass)
4. **Type safety**: `mypy .` (must pass)
5. **Pyright validation**: `pyright` (should pass)
6. **Style compliance**: `pylint $(git ls-files '*.py')` (address major issues)

### Success Criteria

- ✅ All tests pass consistently
- ✅ Coverage ≥ 80% on modified modules
- ✅ Zero ruff/mypy violations
- ✅ Tests follow behavior-driven structure
- ✅ Fixtures eliminate code duplication
- ✅ User-focused test descriptions
- ✅ Minimal, strategic mocking

---

**Remember**: Great tests are an investment in the future. Write tests that make the codebase more maintainable, not just achieve coverage metrics.
