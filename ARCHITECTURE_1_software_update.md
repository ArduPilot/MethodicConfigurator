# Software Update Sub-Application Architecture

## Overview

The Software Update sub-application is responsible for checking if there is a newer software version available,
downloading and updating the ArduPilot Methodic Configurator to the latest version.
This ensures users always have access to the latest features, bug fixes, and security updates.

## Requirements Analysis

### Functional Requirements

1. **Version Check**
   - ✅ Checks current version against latest via GitHub releases API
   - ✅ Handles network connectivity issues with proper exception handling
   - ✅ Validates version format using `packaging.version.parse()`
   - ✅ Supports semantic versioning and prerelease versions

2. **Update Detection**
   - ✅ Detects newer versions using semantic version comparison
   - ✅ Distinguishes between version types (major/minor/patch/prerelease)
   - ✅ Uses stable release channel by default (filters pre-releases)
   - ✅ Provides change information from GitHub release body

3. **Download Management**
   - ✅ Downloads from verified GitHub sources with SSL verification
   - ✅ SHA256 checksum validation for downloaded files (when available in release)
   - ✅ Resume capability for interrupted downloads with Range headers
   - ✅ Retry logic with exponential backoff and jitter (3 retries by default)
   - ✅ Provides download progress feedback via callback

4. **Installation Process**
   - ✅ Windows: Creates batch file to run installer after app exit with integrity validation
   - ✅ Linux/macOS: Uses pip to install updated package (supports wheel assets from releases)
   - ✅ File integrity validation (size, magic bytes, SHA256 when available)
   - ✅ Automatic cleanup of invalid/corrupted downloads

5. **User Interface**
   - ✅ Clear update information display with scrollable content
   - ✅ User choice to update or skip with proper button handling
   - ✅ Download and installation progress display
   - ✅ Graceful handling of user cancellation

6. **Error Handling**
   - ✅ Network failures handled with automatic retry (3 attempts with exponential backoff)
   - ✅ Recovery from corrupted downloads via integrity checks and cleanup
   - ✅ Clear error messages with logging at appropriate levels (error/debug)
   - ✅ Graceful handling of partial downloads with resume support

### Non-Functional Requirements

1. **Security**
   - ✅ Downloads from verified GitHub HTTPS sources
   - ✅ SSL certificate validation enabled (`verify=True`)
   - ✅ SHA256 checksum verification of downloaded files (when available in GitHub releases)
   - ✅ File magic byte validation (PE header for Windows, ZIP for wheels)
   - ✅ File permission restrictions (chmod 0o600) where supported
   - ✅ Proper certificate and SSL/TLS handling

2. **Performance**
   - ✅ Version checking completes quickly (GitHub API is fast)
   - ✅ Downloads use efficient streaming with configurable block size (8KB default)
   - ✅ Resume capability avoids re-downloading completed portions
   - ✅ Non-blocking UI during downloads and installation

3. **Reliability**
   - ✅ Graceful handling of interrupted operations with proper exception handling
   - ✅ System stability maintained during updates (uses separate processes)

4. **Usability**
   - ✅ Intuitive update process requiring minimal user intervention
   - ✅ Clear and accurate progress feedback with percentage and status messages
   - ✅ Actionable and user-friendly error messages

Legend:
 ✅ **IMPLEMENTED**
 ⚠️ **PARTIALLY IMPLEMENTED**

## Architecture

### Components

#### Core Module

- **File**: `data_model_software_updates.py`
- **Purpose**: Contains the business logic for version checking, downloading, and installation orchestration
- **Key Classes**:
  - `UpdateManager`: Handles user interaction and installation coordination
  - `format_version_info()`: Cleans and formats release notes for display
  - `check_for_software_updates()`: Main entry point function
- **Actual Dependencies**:
  - `packaging.version` for semantic version comparison ✅
  - `requests` for HTTP operations (via backend_internet) ✅
  - `webbrowser` for opening GitHub releases page ✅
  - `platform` for OS-specific installation logic ✅
  - `re` for release notes formatting ✅

#### User Interface

- **File**: `frontend_tkinter_software_update.py`
- **Purpose**: Provides the GUI dialog for user interaction during update process
- **Key Classes**:
  - `UpdateDialog`: Main dialog window with version info and progress display
- **Actual Dependencies**:
  - `tkinter` and `tkinter.ttk` for GUI components ✅
  - `ScrollFrame` for scrollable release notes display ✅
  - `BaseWindow` for consistent window behavior ✅

#### Backend Internet Module

- **File**: `backend_internet.py`
- **Purpose**: Handles actual download and installation operations
- **Key Functions**:
  - `get_release_info()`: GitHub API communication with rate limit handling
  - `get_expected_sha256_from_release()`: SHA256 checksum retrieval from release assets
  - `download_file_from_url()`: File download with retry, resume, and progress tracking
  - `download_and_install_on_windows()`: Windows installer with integrity validation
  - `download_and_install_pip_release()`: Linux/macOS pip installation

- **Actual Dependencies**:
  - `requests` with SSL verification and proxy support ✅
  - `hashlib` for SHA256 computation ✅
  - `subprocess` for Windows batch file execution and pip operations ✅
  - `tempfile` for secure temporary directories ✅
  - `random` for retry backoff jitter ✅
  - `contextlib` for exception suppression ✅
  - `os` for system operations ✅
  - `re` for checksum parsing ✅

### Data Flow

1. **Application Startup Check**
   - Main application calls `check_for_software_updates()` during startup
   - Function checks current version from `__version__` and gets git hash
   - Skippable via `--skip-check-for-updates` command line argument

2. **Version Retrieval and Comparison**
   - Calls `get_release_info("/latest", should_be_pre_release=False)` from backend_internet
   - Uses GitHub releases API to get latest stable release information
   - Compares versions using `packaging.version.parse()` for semantic versioning

3. **Update Available Decision**
   - If `current >= latest`, logs "Already running latest version" and returns False
   - If update available, formats version info and opens GitHub releases page in browser
   - Creates UpdateDialog with version information and download callback

4. **User Interaction Phase**
   - UpdateDialog shows scrollable version information with release notes
   - User can choose to download/install or cancel via dialog buttons
   - Progress bar appears during download/installation process

5. **Download and Installation Phase**
   - **Windows**: Downloads .exe installer with SHA256 verification, validates PE header, creates batch file
   - **Linux/macOS**: Attempts wheel asset from GitHub first (with SHA256), falls back to pip
   - ✅ Progress callback provides real-time feedback during download
   - ✅ SHA256 integrity validation of downloaded files (when checksums available)
   - ✅ File format validation (PE headers for .exe, ZIP headers for .whl)
   - ✅ Automatic cleanup of invalid downloads

6. **Application Exit for Update**
   - Windows: Main application exits (`os._exit(0)`) to allow installer to run
   - Linux/macOS: Application continues after pip installation completes
   - Update process returns True to signal main application to exit

### Integration Points

- ✅ **Main Application**: Called from `__main__.py` during startup before other sub-applications
- ✅ **Logging System**: Uses standard Python logging for all update activities and errors
- ✅ **File System**:
  - Windows: Uses `tempfile.TemporaryDirectory()` for secure temporary file handling
  - Both platforms: Manages installer/package downloads and cleanup
- ✅ **Internet Backend**: Uses `backend_internet.py` for GitHub API communication and file downloads
- ✅ **Frontend Components**: Uses `BaseWindow` and `ScrollFrame` for consistent UI behavior

### Security Considerations

- ✅ **SSL/TLS Verification**: All downloads use `verify=True` for SSL certificate validation
- ✅ **Verified Sources**: Updates only come from GitHub releases API with HTTPS
- ✅ **File Integrity Verification**: SHA256 checksum validation when available in releases
- ✅ **File Format Validation**: Magic byte checks for executables and archives
- ✅ **Permission Hardening**: Restricts file permissions (chmod 0o600) where supported
- ✅ **Input Validation**: Validates file sizes and formats before execution

### Error Handling Strategy

- ✅ **Network Errors**: Comprehensive handling of `RequestException`, `Timeout`, and connection errors
- ✅ **Retry Logic**: Automatic retry with exponential backoff and jitter (3 attempts by default)
- ✅ **Download Corruption**: SHA256 validation, file size checks, and magic byte verification
- ✅ **Resume Capability**: Partial downloads can be resumed using HTTP Range headers
- ✅ **Installation Failures**: Exception handling with logging for Windows and pip installation failures
- ✅ **Permission Errors**: Catches specific exceptions (`OSError`, `PermissionError`, `NotImplementedError`)
- ✅ **User Feedback**: Clear error messages logged at appropriate levels (error/debug)
- ✅ **Resource Cleanup**: Automatic cleanup of invalid/corrupted downloads with error logging

### Testing Strategy

- ✅ **Unit Tests**: Comprehensive unit tests for version comparison, format functions, and core logic
- ✅ **Checksum Testing**: Tests for SHA256 parsing from various release asset formats
- ✅ **Retry Logic Testing**: Tests for exponential backoff and jitter in retry scenarios
- ✅ **Resume Testing**: Tests for partial download resume with Range headers
- ✅ **Integration Tests**: Tests for download and installation workflows with mocking
- ✅ **Mock Testing**: Extensive mocking of network operations and external dependencies
- ✅ **Error Path Testing**: Tests for various error conditions and exception handling
- ✅ **UI Testing**: Frontend dialog tests with proper setup and teardown
- ✅ **Platform Testing**: Tests for Windows, Linux, and macOS specific code paths
- ✅ **Version Handling**: Tests for prerelease versions, malformed tags, and edge cases
- ⚠️ **Security Testing**: File validation tests (size, magic bytes) but no malicious payload testing
- ✅ **Real Network Testing**: Integration tests with actual GitHub API calls (marked with `@pytest.mark.integration`)

## File Structure

```text
data_model_software_updates.py          # Core update logic and orchestration ✅
frontend_tkinter_software_update.py     # GUI dialog interface ✅
backend_internet.py                     # Download and installation backend ✅
tests/acceptance_software_update.py     # Acceptance tests for the application requirements defined on top of this file ✅
tests/bdd_software_updates.py           # BDD tests ✅
tests/integration_software_update_github_api.py  # Integration tests with actual GitHub API calls ✅
tests/unit_backend_internet.py          # Backend download and retry tests ✅
tests/test_backend_internet_checksum_parsing.py  # SHA256 checksum parsing tests ✅
tests/unit_backend_internet_download_resume.py   # Unit tests for download_resume logic ✅
tests/unit_data_model_software_updates.py        # Unit tests for core logic ✅
tests/unit_frontend_tkinter_software_update.py   # UI dialog tests ✅
```

**Additional Supporting Files** ✅:

- `backend_filesystem.py` - Used for git hash retrieval
- `frontend_tkinter_base_window.py` - Base window class
- `frontend_tkinter_scroll_frame.py` - Scrollable content widget

## Dependencies

### Actual Implementation Dependencies

**Core Module (`data_model_software_updates.py`)**:

- `packaging.version` for version comparison
- `requests` for HTTP operations
- `webbrowser` for opening release URLs
- `platform` for OS detection
- `re` for text processing

**Backend Internet (`backend_internet.py`)**:

- `requests` with timeout, SSL verification, and proxy support
- `hashlib` for SHA256 computation
- `subprocess` for Windows installer and pip operations
- `tempfile` for secure temporary file handling
- `contextlib` for exception suppression
- `random` for retry backoff jitter
- `re` for checksum parsing from release assets
- `os` for system operations and environment variables

**Frontend (`frontend_tkinter_software_update.py`)**:

- `tkinter` and `tkinter.ttk` for GUI components
- Custom `ScrollFrame` for scrollable content
- `BaseWindow` for consistent UI behavior

## Known Limitations

### Security Limitations

1. **PE Validation (Windows)**
   - **Current Implementation**: Only validates DOS header (MZ signature) of Windows executables
   - **Limitation**: Does not perform full PE structure validation (headers, sections, imports)
   - **Rationale**: Full PE validation would require additional dependencies (e.g., `pefile` library)
   - **Mitigation**: SHA256 checksum verification provides primary integrity protection
   - **Risk Assessment**: Low - checksums and GitHub HTTPS provide adequate security for typical use cases
