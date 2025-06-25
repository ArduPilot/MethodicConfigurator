# Architecture Validation Instructions for AI Agents

## Overview

This document provides instructions for AI agents to periodically validate and update the architecture
documentation files (`ARCHITECTURE_n_*.md`) against the actual source code implementation.
This ensures the documentation remains accurate and up-to-**Common Architectural Patterns to Validate:**

```bash
# Progress callback patterns
grep -r "progress_callback\|callback.*progress" ardupilot_methodic_configurator/

# Platform-specific code
grep -r "platform.system\|Windows\|Linux\|macOS" ardupilot_methodic_configurator/

# Configuration management
grep -r "settings\|config\|preferences" ardupilot_methodic_configurator/

# Internationalization
grep -r "_(\|gettext" ardupilot_methodic_configurator/

# GUI framework usage
grep -r "tkinter\|BaseWindow\|ScrollFrame" ardupilot_methodic_configurator/
```

## Common Validation Findings

Based on validation experience, these patterns commonly need updating in architecture docs:

### Integration Points Often Missing

- Command line argument handling integration
- Logging system integration
- GUI framework component integration
- Configuration/settings system integration (often TODO)

### File Structure Often Incomplete

- Test files not listed
- Supporting GUI components not mentioned
- Backend modules providing specific functionality
- Generated or auto-updated files

### Dependencies Often Inaccurate

- Listed dependencies not actually imported
- Missing dependencies found in imports
- Supporting framework components not documented
- Platform-specific dependencies not noted

### Implementation Status Patterns

- Core functionality usually ✅ IMPLEMENTED
- Security features often ⚠️ PARTIALLY IMPLEMENTED
- Error recovery usually ❌ TODO
- Configuration management often ❌ TODO
- Advanced features (backup, rollback, retry) usually ❌ TODOase evolves.

## Prerequisites

- Access to the ArduPilot Methodic Configurator codebase
- Ability to read and analyze Python source files
- Understanding of software architecture documentation standards
- Familiarity with the project's coding standards and structure

## Architecture Files to Validate

The following architecture files should be validated periodically:

1. `ARCHITECTURE_1_software_update.md` - Software Update Sub-Application
2. `ARCHITECTURE_2_flight_controller_communication.md` - Flight Controller Communication Sub-Application
3. `ARCHITECTURE_3_directory_selection.md` - Directory Selection Sub-Application
4. `ARCHITECTURE_4_component_editor.md` - Component Editor Sub-Application
5. `ARCHITECTURE_5_parameter_editor.md` - Parameter Editor Sub-Application

## Source Code Mapping

### Software Update (`ARCHITECTURE_1_software_update.md`)

- `ardupilot_methodic_configurator/middleware_software_updates.py`
- `ardupilot_methodic_configurator/frontend_tkinter_software_update.py`
- `ardupilot_methodic_configurator/backend_internet.py`
- `tests/test_middleware_software_updates.py`
- `tests/test_frontend_tkinter_software_update.py`

### Flight Controller Communication (`ARCHITECTURE_2_flight_controller_communication.md`)

- `ardupilot_methodic_configurator/frontend_tkinter_connection_selection.py`
- `ardupilot_methodic_configurator/frontend_tkinter_flightcontroller_info.py`
- `ardupilot_methodic_configurator/backend_flightcontroller.py`
- `ardupilot_methodic_configurator/backend_mavftp.py`
- `ardupilot_methodic_configurator/middleware_fc_ids.py`

### Directory Selection (`ARCHITECTURE_3_directory_selection.md`)

- `ardupilot_methodic_configurator/frontend_tkinter_directory_selection.py`
- `ardupilot_methodic_configurator/frontend_tkinter_template_overview.py`
- `ardupilot_methodic_configurator/backend_filesystem.py`
- `ardupilot_methodic_configurator/backend_filesystem_configuration_steps.py`

### Component Editor (`ARCHITECTURE_4_component_editor.md`)

- `ardupilot_methodic_configurator/frontend_tkinter_component_editor.py`
- `ardupilot_methodic_configurator/frontend_tkinter_component_editor_base.py`
- `ardupilot_methodic_configurator/frontend_tkinter_component_template_manager.py`
- `ardupilot_methodic_configurator/data_model_vehicle_components*.py`
- `ardupilot_methodic_configurator/backend_filesystem_vehicle_components.py`

### Parameter Editor (`ARCHITECTURE_5_parameter_editor.md`)

- `ardupilot_methodic_configurator/frontend_tkinter_parameter_editor.py`
- `ardupilot_methodic_configurator/frontend_tkinter_parameter_editor_*.py`
- `ardupilot_methodic_configurator/frontend_tkinter_stage_progress.py`
- `ardupilot_methodic_configurator/backend_filesystem.py`

## Validation Process

### Step 1: Analyze Source Code Implementation

For each requirement in the architecture file, determine implementation status:

- ✅ **IMPLEMENTED**: Feature is fully implemented and working
- ⚠️ **PARTIALLY IMPLEMENTED**: Feature is partially implemented or has limitations
- ❌ **TODO**: Feature is missing or not implemented

### Step 2: Assess Code Quality

Examine the following aspects:

1. **Error Handling**: Check for comprehensive exception handling
2. **Security**: Look for security measures (SSL verification, input validation, etc.)
3. **Performance**: Assess efficiency and resource usage
4. **Test Coverage**: Find and analyze corresponding test files

### Step 3: Update Requirements Section

Update each functional requirement with implementation status:

```markdown
### Functional Requirements - Implementation Status

1. **Feature Name** ✅ **IMPLEMENTED**

   - ✅ Specific capability that works
   - ⚠️ Specific capability with limitations
   - ❌ **TODO**: Missing specific capability

2. **Another Feature** ⚠️ **PARTIALLY IMPLEMENTED**

   - ✅ Working parts description
   - ❌ **TODO**: Missing parts description
```

### Step 4: Validate Architecture Sections

Ensure these key architecture sections are accurate and up-to-date:

#### Data Flow Validation

Review and update the "Data Flow" section to match actual implementation:

```markdown
### Data Flow

1. **Phase Name**
   - Current implementation step description
   - How data moves between components
   - Any validation or transformation steps

2. **Another Phase**
   - Actual flow based on source code analysis
   - Integration points and dependencies
```

#### Component Validation

Verify that all components listed in the architecture actually exist and function as described. Apply implementation status indicators to all architectural sections:

```markdown
### Components - Implementation Status

#### Core Module

- **File**: `module_name.py` ✅ **IMPLEMENTED**
- **Purpose**: Actual purpose based on code analysis
- **Key Classes**:
  - `ClassName`: What it actually does
- **Actual Dependencies**: (verify against imports in source code)

#### Missing Components

- ❌ **TODO**: Components referenced but not implemented
```

#### Integration Points Validation

Review and update Integration Points to reflect actual integrations:

```markdown
### Integration Points - Implementation Status

- ✅ **Actual Integration**: How it's implemented in the code
- ❌ **TODO: Missing Integration**: Referenced but not implemented
```

#### File Structure Validation

Update the File Structure section to include all relevant files found during analysis:

```markdown
## File Structure - Implementation Status

```text
main_module.py                    # Description ✅
support_module.py                 # Description ✅
tests/test_main_module.py         # Test coverage ✅
```

**Additional Supporting Files** ✅:

- `discovered_dependency.py` - Actual purpose from code analysis

```markdown

### Step 5: Add Analysis Sections

Include these sections if they don't exist:

```markdown
## Code Quality Analysis

### Strengths

1. **Strength 1**: Description of what works well
2. **Strength 2**: Another positive aspect

### Critical Gaps

1. **Gap 1**: Description of major missing functionality
2. **Gap 2**: Another critical issue

### Security Considerations

- ✅ **Implemented Security Feature**: Description
- ❌ **TODO**: Missing security feature

### Testing Strategy

- ✅ **Implemented Tests**: Description of existing test coverage
- ❌ **TODO**: Missing test coverage areas

## Recommendations for Production Deployment

### High Priority TODO Items

1. **Critical missing feature** with implementation details
2. **Security improvement** with specific requirements

### Medium Priority TODO Items

1. **Enhancement** that would improve the system
2. **Performance optimization** opportunity

### Low Priority TODO Items

1. **Nice-to-have feature** for future consideration
2. **Code cleanup** or refactoring opportunity
```

### Step 6: Validate Dependencies

Check actual dependencies in source files and update the dependencies section:

```markdown
### Actual Implementation Dependencies

**Module Name (`filename.py`)**:

- `library_name` for specific purpose (✅ present)
- `another_library` for another purpose (✅ present)

**Missing Dependencies**:

- ❌ `listed_but_unused` - listed in architecture but not used
- ❌ `missing_library` - needed but not listed
```

## Analysis Best Practices

### Maintain Status Consistency

Apply implementation status indicators (✅ ⚠️ ❌) consistently across ALL architectural sections:

- **Requirements sections**: Mark each requirement with implementation status
- **Data Flow phases**: Mark each phase with implementation status
- **Components**: Mark each component and its dependencies with status
- **Integration Points**: Mark each integration with implementation status
- **File Structure**: Mark each file with implementation status
- **Security/Error Handling/Testing**: Mark each aspect with implementation status

### Discover Supporting Dependencies

Look beyond the main modules to find supporting files:

```bash
# Find imports and dependencies
grep -r "from.*import\|import.*" ardupilot_methodic_configurator/
# Find test files
find tests/ -name "*test_module_name*"
# Find supporting GUI components
grep -r "BaseWindow\|ScrollFrame\|tkinter" ardupilot_methodic_configurator/
```

### Analyze Test Coverage Depth

When assessing test coverage, provide specific metrics:

- Line count of test files (`wc -l test_file.py`)
- Number of test methods (`grep -c "def test_" test_file.py`)
- Types of tests (unit, integration, error handling, platform-specific)
- Coverage gaps (what's not tested)

### Markdown Formatting Requirements

Ensure proper markdown formatting to avoid linting errors:

- **Lists**: Surround all lists with blank lines before and after
- **Code blocks**: Add language specification and blank lines around fenced code blocks
- **Trailing spaces**: Avoid trailing spaces at end of lines
- **Status indicators**: Use consistent format: `✅ **IMPLEMENTED**`, `⚠️ **PARTIALLY IMPLEMENTED**`, `❌ **TODO**`

Example of proper formatting:

```markdown
### Section Title

Introductory text.

- ✅ **Feature Name**: Description of implementation
- ❌ **TODO: Missing Feature**: What needs to be implemented

Next paragraph after list.
```

### Implementation Detail Level

Include specific implementation details discovered in source code:

- Exact class and function names from the code
- Key algorithms or logic patterns (e.g., "Uses `packaging.version.parse()` for semantic versioning")
- Error handling patterns found (e.g., "Catches `RequestException`, `OSError`, etc.")
- Integration mechanisms (e.g., "Called from `__main__.py` line 107")
- Progress tracking mechanisms (e.g., "Uses callback-based progress updates")

### Be Specific and Actionable

- Provide exact file names and line numbers when relevant
- Ensure TODO items can be implemented by developers
- Include both positive findings and areas for improvement

### Senior Developer Perspective

Analyze the code as an experienced senior developer would:

- Consider production readiness, not just functionality
- Evaluate security implications of design decisions
- Assess maintainability and technical debt
- Think about edge cases and error scenarios

### Common Patterns to Look For

**Security Patterns:**

```bash
grep -r "verify=\|ssl\|https\|security" ardupilot_methodic_configurator/
```

**Error Handling Patterns:**

```bash
grep -r "try:\|except\|raise\|logging" ardupilot_methodic_configurator/
```

**TODO/FIXME Comments:**

```bash
grep -r "TODO\|FIXME\|XXX" ardupilot_methodic_configurator/
```

## Validation Checklist

Before submitting architecture updates:

- [ ] All source files have been examined for actual implementation
- [ ] Test coverage has been assessed with specific metrics (line counts, test methods)
- [ ] Security considerations have been evaluated against actual code patterns
- [ ] Data Flow section reflects actual implementation flow
- [ ] Component descriptions match source code with exact class/function names
- [ ] Integration Points section updated with actual integrations found
- [ ] File Structure section includes all discovered supporting files
- [ ] Dependencies are accurate and verified against actual imports
- [ ] Status indicators (✅ ⚠️ ❌) are applied consistently across ALL sections
- [ ] Implementation details include specific code patterns and mechanisms
- [ ] TODO items are specific and actionable with technical requirements
- [ ] Markdown formatting follows project standards (lists, code blocks, spacing)
- [ ] All file paths and module names are correct and verified
- [ ] Recommendations are prioritized appropriately (High/Medium/Low)
- [ ] Documentation is comprehensive but concise
- [ ] Supporting dependencies discovered via grep/find commands are included

## Example Analysis Output

When updating an architecture file, follow this format:

```markdown
### Functional Requirements - Implementation Status

1. **Version Check** ✅ **IMPLEMENTED**

   - ✅ Checks current version against latest via GitHub releases API
   - ✅ Handles network connectivity issues with proper exception handling
   - ✅ Validates version format using `packaging.version.parse()`

2. **Download Management** ⚠️ **PARTIALLY IMPLEMENTED**

   - ✅ Downloads from verified GitHub sources with SSL verification
   - ❌ **TODO**: No checksum or signature validation of downloaded files
   - ❌ **TODO**: No resume capability for partial downloads

## Code Quality Analysis

### Strengths

1. **Comprehensive Error Handling**: All major exception types are caught and handled
2. **Extensive Test Coverage**: 574 lines of comprehensive unit tests

### Critical Security Gaps

1. **No File Integrity Verification**: Downloaded files are not validated with checksums
2. **No Backup Mechanism**: Current installation could be corrupted without recovery

## Recommendations for Production Deployment

### High Priority TODO Items

1. **Implement file integrity verification** using checksums from GitHub release assets
2. **Add backup mechanism** before attempting installation
```

This format ensures consistent, actionable documentation that accurately reflects the implementation status.
