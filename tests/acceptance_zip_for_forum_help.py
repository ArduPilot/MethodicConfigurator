#!/usr/bin/env python3

"""
Acceptance tests for the "Zip Vehicle for Forum Help" feature in ParameterEditor.

These tests validate the complete user workflow for creating a support package zip file
containing vehicle configuration files for forum assistance.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import re
from collections.abc import Iterator, Mapping
from datetime import datetime, timezone
from pathlib import Path
from types import MethodType, SimpleNamespace
from typing import Any, Optional, Union, cast
from unittest.mock import MagicMock, patch
from zipfile import ZipFile

import pytest

from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.data_model_par_dict import ParDict
from ardupilot_methodic_configurator.data_model_parameter_editor import ParameterEditor

# pylint: disable=redefined-outer-name, protected-access, too-many-lines
# pyright: reportGeneralTypeIssues=false


@pytest.fixture
def mock_flight_controller() -> MagicMock:
    """Fixture providing a mock flight controller."""
    mock_fc = MagicMock()
    mock_fc.fc_parameters = {}
    return mock_fc


@pytest.fixture
def mock_local_filesystem() -> MagicMock:
    """Fixture providing a mock local filesystem with vehicle directory structure."""
    mock_fs = MagicMock()
    mock_fs.file_parameters = {}
    mock_fs.param_default_dict = ParDict()
    mock_fs.doc_dict = {}
    mock_fs.forced_parameters = {}
    mock_fs.derived_parameters = {}
    mock_fs.vehicle_components_fs = SimpleNamespace(json_filename="vehicle_components.json")
    mock_fs.configuration_steps_filename = "configuration_steps_ArduCopter.json"
    # Vehicle directory will be set in individual tests
    mock_fs.vehicle_dir = str(Path("/home/user/vehicles/MyDrone"))
    return mock_fs


@pytest.fixture
def parameter_editor(mock_flight_controller, mock_local_filesystem) -> ParameterEditor:
    """Fixture providing a properly configured ParameterEditor for acceptance testing."""
    return ParameterEditor(
        "00_default.param",
        mock_flight_controller,
        cast("LocalFilesystem", mock_local_filesystem),
    )


@pytest.fixture(autouse=True)
def mock_webbrowser_open_url() -> Iterator[MagicMock]:
    """Prevent tests from opening the browser while allowing call assertions."""
    with patch(
        "ardupilot_methodic_configurator.data_model_parameter_editor.webbrowser_open_url",
        autospec=True,
    ) as mock_browser:
        yield mock_browser


def get_filesystem(parameter_editor: ParameterEditor) -> LocalFilesystem:
    """Helper to access the underlying filesystem with relaxed typing."""
    return parameter_editor._local_filesystem


def configure_filesystem(
    parameter_editor: ParameterEditor,
    vehicle_dir: Path,
    parameter_files: Optional[list[str]] = None,
) -> LocalFilesystem:
    """Configure filesystem directory and parameter files for a test."""
    filesystem = get_filesystem(parameter_editor)
    filesystem.vehicle_dir = str(vehicle_dir)
    filesystem.file_parameters = {filename: ParDict() for filename in parameter_files} if parameter_files is not None else {}
    return filesystem


def create_forum_help_zip(
    parameter_editor: ParameterEditor,
    *,
    show_info: Optional[MagicMock] = None,
    show_error: Optional[MagicMock] = None,
) -> Path:
    """Execute the public workflow helper and return the created zip path."""
    info_callback = show_info or MagicMock()
    error_callback = show_error or MagicMock()

    result = parameter_editor.create_forum_help_zip_workflow(
        show_info=info_callback,
        show_error=error_callback,
    )

    assert result is True, "Expected the workflow to succeed but it failed"
    error_callback.assert_not_called()

    vehicle_dir = Path(get_filesystem(parameter_editor).vehicle_dir)
    zip_files = list(vehicle_dir.glob("*.zip"))
    assert zip_files, "Expected the workflow to create a zip file"
    assert len(zip_files) == 1, "Expected exactly one zip file to be created"
    return zip_files[0]


def setup_zip_mock(
    parameter_editor: ParameterEditor,
    vehicle_dir: Path,
    file_parameters: Mapping[str, Union[ParDict, Mapping[str, Any], None]],
    configuration_steps_filename: str = "configuration_steps_ArduCopter.json",
) -> None:
    """
    Configure the test filesystem to exercise the production ZIP implementation.

    Args:
        parameter_editor: The ParameterEditor instance to configure
        vehicle_dir: The vehicle directory path
        file_parameters: Dict of parameter filenames to include (values can be empty dicts)
        configuration_steps_filename: Name of the configuration steps file relevant to the vehicle

    """
    filesystem = get_filesystem(parameter_editor)
    filesystem.vehicle_dir = str(vehicle_dir)

    normalized_parameters: dict[str, ParDict] = {}
    for filename, value in file_parameters.items():
        if isinstance(value, ParDict):
            normalized_parameters[filename] = value
        elif isinstance(value, Mapping):
            normalized_parameters[filename] = ParDict()
        else:
            normalized_parameters[filename] = ParDict()

    filesystem.file_parameters = normalized_parameters
    filesystem.configuration_steps_filename = configuration_steps_filename

    fs_any = cast("Any", filesystem)

    if getattr(fs_any, "vehicle_components_fs", None) is None:
        fs_any.vehicle_components_fs = SimpleNamespace(json_filename="vehicle_components.json")

    fs_any.vehicle_configuration_file_exists = MethodType(LocalFilesystem.vehicle_configuration_file_exists, filesystem)
    fs_any.add_configuration_file_to_zip = MethodType(LocalFilesystem.add_configuration_file_to_zip, filesystem)
    fs_any.zip_files = MethodType(LocalFilesystem.zip_files, filesystem)
    fs_any.zip_file_path = MethodType(LocalFilesystem.zip_file_path, filesystem)


@pytest.fixture
def vehicle_directory_with_files(tmp_path: Path) -> Path:
    """
    Fixture providing a realistic vehicle directory with all required files.

    Creates a temporary vehicle directory structure with:
    - Parameter files (numbered)
    - vehicle.jpg
    - vehicle_components.json
    - last_uploaded_filename.txt
    - configuration_steps_*.json
    """
    vehicle_dir = tmp_path / "MyDrone"
    vehicle_dir.mkdir()

    # Create numbered parameter files
    (vehicle_dir / "01_first_setup.param").write_text("# First setup\nPARAM1 1.0\n")
    (vehicle_dir / "02_second_step.param").write_text("# Second step\nPARAM2 2.0\n")
    (vehicle_dir / "15_advanced.param").write_text("# Advanced config\nPARAM3 3.0\n")

    # Create vehicle image
    (vehicle_dir / "vehicle.jpg").write_bytes(b"\xff\xd8\xff\xe0fake_jpeg_data")

    # Create vehicle components file
    (vehicle_dir / "vehicle_components.json").write_text('{"Format version": 1, "Components": {}}')

    # Create last uploaded filename file
    (vehicle_dir / "last_uploaded_filename.txt").write_text("02_second_step.param")

    # Create tempcal files
    (vehicle_dir / "tempcal_gyro.png").write_bytes(b"\x89PNG\r\n\x1a\nfake_png_data")
    (vehicle_dir / "tempcal_acc.png").write_bytes(b"\x89PNG\r\n\x1a\nfake_png_data")

    # Create tuning report
    (vehicle_dir / "tuning_report.csv").write_text("param,value\nPARAM1,1.0\n")

    # Create configuration steps files
    (vehicle_dir / "configuration_steps_ArduCopter.json").write_text('{"steps": []}')
    (vehicle_dir / "configuration_steps_ArduPlane.json").write_text('{"steps": []}')

    # Create some files that should NOT be included
    (vehicle_dir / "readme.txt").write_text("User notes")
    (vehicle_dir / "backup.bin").write_bytes(b"binary_data")

    # Create 00_default.param (should now be included)
    (vehicle_dir / "00_default.param").write_text("# Default params\nDEFAULT 0\n")

    return vehicle_dir


class TestZipVehicleForForumHelpFileInclusion:
    """Test that the correct files are included in the support package zip."""

    def test_user_can_create_zip_with_all_numbered_parameter_files(
        self, parameter_editor: ParameterEditor, vehicle_directory_with_files: Path
    ) -> None:
        r"""
        User can create zip containing all intermediate parameter files.

        GIVEN: A vehicle directory with multiple intermediate parameter files (01_*.param, 02_*.param, etc.)
        WHEN: User triggers the zip creation for forum help
        THEN: All intermediate parameter files should be included in the zip
        """
        # Arrange: Setup mocks for zip creation
        setup_zip_mock(
            parameter_editor,
            vehicle_directory_with_files,
            {
                "01_first_setup.param": {},
                "02_second_step.param": {},
                "15_advanced.param": {},
            },
        )

        # Act: Create zip file
        zip_path = create_forum_help_zip(parameter_editor)

        # Assert: Verify zip was created and contains intermediate param files
        assert zip_path.exists()
        with ZipFile(zip_path, "r") as zipf:
            file_list = zipf.namelist()
            assert "01_first_setup.param" in file_list
            assert "02_second_step.param" in file_list
            assert "15_advanced.param" in file_list
            # 00_default.param is included separately if it exists
            assert "00_default.param" in file_list

    def test_user_can_create_zip_with_vehicle_image_when_present(
        self, parameter_editor: ParameterEditor, vehicle_directory_with_files: Path
    ) -> None:
        """
        User can create zip including vehicle.jpg if it exists.

        GIVEN: A vehicle directory containing a vehicle.jpg file
        WHEN: User triggers the zip creation for forum help
        THEN: The vehicle.jpg file should be included in the zip archive
        """
        # Arrange: Setup mocks for zip creation
        setup_zip_mock(
            parameter_editor,
            vehicle_directory_with_files,
            {
                "01_first_setup.param": {},
                "02_second_step.param": {},
            },
        )

        # Act: Create zip file
        zip_path = create_forum_help_zip(parameter_editor)

        # Assert: Verify vehicle.jpg is included
        assert zip_path.exists()
        with ZipFile(zip_path, "r") as zipf:
            assert "vehicle.jpg" in zipf.namelist()

    def test_user_can_create_zip_without_vehicle_image_when_absent(
        self, parameter_editor: ParameterEditor, tmp_path: Path
    ) -> None:
        """
        User can create zip without vehicle.jpg if it doesn't exist.

        GIVEN: A vehicle directory without a vehicle.jpg file
        WHEN: User triggers the zip creation for forum help
        THEN: The zip should be created successfully without vehicle.jpg
        """
        # Arrange: Create directory without vehicle.jpg and setup mocks
        vehicle_dir = tmp_path / "TestVehicle"
        vehicle_dir.mkdir()
        (vehicle_dir / "01_setup.param").write_text("PARAM 1.0")
        setup_zip_mock(parameter_editor, vehicle_dir, {"01_setup.param": {}})

        # Act: Create zip file
        zip_path = create_forum_help_zip(parameter_editor)

        # Assert: Verify zip was created but doesn't contain vehicle.jpg
        assert zip_path.exists()
        with ZipFile(zip_path, "r") as zipf:
            assert "vehicle.jpg" not in zipf.namelist()
            assert "01_setup.param" in zipf.namelist()

    def test_user_can_create_zip_with_vehicle_components_when_present(
        self, parameter_editor: ParameterEditor, vehicle_directory_with_files: Path
    ) -> None:
        """
        User can create zip including vehicle_components.json if it exists.

        GIVEN: A vehicle directory containing a vehicle_components.json file
        WHEN: User triggers the zip creation for forum help
        THEN: The vehicle_components.json file should be included in the zip archive
        """
        # Arrange: Setup mocks for zip creation
        setup_zip_mock(
            parameter_editor,
            vehicle_directory_with_files,
            {
                "01_first_setup.param": {},
                "02_second_step.param": {},
            },
        )

        # Act: Create zip file
        zip_path = create_forum_help_zip(parameter_editor)

        # Assert: Verify vehicle_components.json is included
        assert zip_path.exists()
        with ZipFile(zip_path, "r") as zipf:
            assert "vehicle_components.json" in zipf.namelist()

    def test_user_can_create_zip_with_last_uploaded_filename_when_present(
        self, parameter_editor: ParameterEditor, vehicle_directory_with_files: Path
    ) -> None:
        """
        User can create zip including last_uploaded_filename.txt if it exists.

        GIVEN: A vehicle directory containing a last_uploaded_filename.txt file
        WHEN: User triggers the zip creation for forum help
        THEN: The last_uploaded_filename.txt file should be included in the zip archive
        """
        # Arrange: Setup mocks for zip creation
        setup_zip_mock(
            parameter_editor,
            vehicle_directory_with_files,
            {
                "01_first_setup.param": {},
                "02_second_step.param": {},
            },
        )

        # Act: Create zip file
        zip_path = create_forum_help_zip(parameter_editor)

        # Assert: Verify last_uploaded_filename.txt is included
        assert zip_path.exists()
        with ZipFile(zip_path, "r") as zipf:
            assert "last_uploaded_filename.txt" in zipf.namelist()

    def test_user_can_create_zip_with_tempcal_gyro_when_present(
        self, parameter_editor: ParameterEditor, vehicle_directory_with_files: Path
    ) -> None:
        """
        User can create zip including tempcal_gyro.png if it exists.

        GIVEN: A vehicle directory containing a tempcal_gyro.png file
        WHEN: User triggers the zip creation for forum help
        THEN: The tempcal_gyro.png file should be included in the zip archive
        """
        # Arrange: Setup mocks for zip creation
        setup_zip_mock(
            parameter_editor,
            vehicle_directory_with_files,
            {
                "01_first_setup.param": {},
                "02_second_step.param": {},
            },
        )

        # Act: Create zip file
        zip_path = create_forum_help_zip(parameter_editor)

        # Assert: Verify tempcal_gyro.png is included
        assert zip_path.exists()
        with ZipFile(zip_path, "r") as zipf:
            assert "tempcal_gyro.png" in zipf.namelist()

    def test_user_can_create_zip_with_tempcal_acc_when_present(
        self, parameter_editor: ParameterEditor, vehicle_directory_with_files: Path
    ) -> None:
        """
        User can create zip including tempcal_acc.png if it exists.

        GIVEN: A vehicle directory containing a tempcal_acc.png file
        WHEN: User triggers the zip creation for forum help
        THEN: The tempcal_acc.png file should be included in the zip archive
        """
        # Arrange: Setup mocks for zip creation
        setup_zip_mock(
            parameter_editor,
            vehicle_directory_with_files,
            {
                "01_first_setup.param": {},
                "02_second_step.param": {},
            },
        )

        # Act: Create zip file
        zip_path = create_forum_help_zip(parameter_editor)

        # Assert: Verify tempcal_acc.png is included
        assert zip_path.exists()
        with ZipFile(zip_path, "r") as zipf:
            assert "tempcal_acc.png" in zipf.namelist()

    def test_user_can_create_zip_with_tuning_report_when_present(
        self, parameter_editor: ParameterEditor, vehicle_directory_with_files: Path
    ) -> None:
        """
        User can create zip including tuning_report.csv if it exists.

        GIVEN: A vehicle directory containing a tuning_report.csv file
        WHEN: User triggers the zip creation for forum help
        THEN: The tuning_report.csv file should be included in the zip archive
        """
        # Arrange: Setup mocks for zip creation
        setup_zip_mock(
            parameter_editor,
            vehicle_directory_with_files,
            {
                "01_first_setup.param": {},
                "02_second_step.param": {},
            },
        )

        # Act: Create zip file
        zip_path = create_forum_help_zip(parameter_editor)

        # Assert: Verify tuning_report.csv is included
        assert zip_path.exists()
        with ZipFile(zip_path, "r") as zipf:
            assert "tuning_report.csv" in zipf.namelist()

    def test_user_can_create_zip_with_active_configuration_steps_file(
        self, parameter_editor: ParameterEditor, vehicle_directory_with_files: Path
    ) -> None:
        """
        User can create zip including only the active configuration steps file.

        GIVEN: Multiple configuration_steps_*.json files exist in the vehicle directory
        WHEN: User creates the forum help zip
        THEN: Only the configuration steps file matching the current vehicle type is included
        """
        # Arrange: Setup mocks for zip creation (defaults to ArduCopter)
        setup_zip_mock(
            parameter_editor,
            vehicle_directory_with_files,
            {
                "01_first_setup.param": {},
                "02_second_step.param": {},
            },
        )

        # Act: Create zip file
        zip_path = create_forum_help_zip(parameter_editor)

        # Assert: Verify only the relevant file is included
        assert zip_path.exists()
        with ZipFile(zip_path, "r") as zipf:
            file_list = zipf.namelist()
            assert "configuration_steps_ArduCopter.json" in file_list
            assert "configuration_steps_ArduPlane.json" not in file_list

    def test_user_can_create_zip_with_different_vehicle_configuration_steps_file(
        self, parameter_editor: ParameterEditor, vehicle_directory_with_files: Path
    ) -> None:
        """
        User can zip the configuration steps file corresponding to a different vehicle type.

        GIVEN: Multiple configuration steps files exist and a different vehicle type is selected
        WHEN: The workflow runs with configuration_steps_ArduPlane.json active
        THEN: The ArduPlane file is included and the ArduCopter file is not
        """
        # Arrange
        setup_zip_mock(
            parameter_editor,
            vehicle_directory_with_files,
            {
                "01_first_setup.param": {},
                "02_second_step.param": {},
            },
            configuration_steps_filename="configuration_steps_ArduPlane.json",
        )

        # Act
        zip_path = create_forum_help_zip(parameter_editor)

        # Assert
        assert zip_path.exists()
        with ZipFile(zip_path, "r") as zipf:
            file_list = zipf.namelist()
            assert "configuration_steps_ArduPlane.json" in file_list
            assert "configuration_steps_ArduCopter.json" not in file_list

    def test_user_can_create_zip_excluding_non_specified_files(
        self, parameter_editor: ParameterEditor, vehicle_directory_with_files: Path
    ) -> None:
        """
        User creates zip that excludes files not in the specification.

        GIVEN: A vehicle directory with various files including non-specified ones
        WHEN: User triggers the zip creation for forum help
        THEN: Only specified files should be included, excluding readme.txt, backup.bin, etc.
        """
        # Arrange: Setup mocks for zip creation
        setup_zip_mock(
            parameter_editor,
            vehicle_directory_with_files,
            {
                "01_first_setup.param": {},
                "02_second_step.param": {},
            },
        )

        # Act: Create zip file
        zip_path = create_forum_help_zip(parameter_editor)

        # Assert: Verify excluded files are not in zip
        assert zip_path.exists()
        with ZipFile(zip_path, "r") as zipf:
            file_list = zipf.namelist()
            assert "readme.txt" not in file_list
            assert "backup.bin" not in file_list


class TestZipVehicleForForumHelpFilenameFormat:
    """Test the zip filename format requirements."""

    def test_user_gets_zip_with_correct_filename_format(
        self, parameter_editor: ParameterEditor, vehicle_directory_with_files: Path
    ) -> None:
        """
        User gets zip file with format <vehicle_name>_YYYYMMDD_HHMMSSUTC.zip.

        GIVEN: A vehicle directory named "MyDrone"
        WHEN: User triggers the zip creation for forum help
        THEN: The zip filename should follow the format MyDrone_YYYYMMDD_HHMMSSUTC.zip
        """
        # Arrange: Setup mocks for zip creation
        setup_zip_mock(
            parameter_editor,
            vehicle_directory_with_files,
            {
                "01_first_setup.param": {},
                "02_second_step.param": {},
            },
        )

        # Act: Create zip file
        zip_path = create_forum_help_zip(parameter_editor)

        # Assert: Verify filename format
        assert zip_path.exists()
        # Pattern: VehicleName_YYYYMMDD_HHMMSSUTC.zip
        pattern = r"^MyDrone_\d{8}_\d{6}UTC\.zip$"
        assert re.match(pattern, zip_path.name), f"Filename {zip_path.name} doesn't match expected pattern"

    def test_user_gets_zip_with_utc_timestamp(
        self, parameter_editor: ParameterEditor, vehicle_directory_with_files: Path
    ) -> None:
        """
        User gets zip file with UTC timestamp in the filename.

        GIVEN: A vehicle directory and the current UTC time
        WHEN: User triggers the zip creation for forum help
        THEN: The zip filename should contain the current UTC date and time with seconds
        """
        # Arrange: Setup mocks for zip creation and capture current UTC time
        setup_zip_mock(
            parameter_editor,
            vehicle_directory_with_files,
            {
                "01_first_setup.param": {},
                "02_second_step.param": {},
            },
        )
        before_creation = datetime.now(timezone.utc)

        # Act: Create zip file
        zip_path = create_forum_help_zip(parameter_editor)

        # Assert: Extract and verify timestamp
        # Extract timestamp from filename: MyDrone_20231215_143052UTC.zip
        match = re.search(r"_(\d{8})_(\d{6})UTC\.zip$", zip_path.name)
        assert match is not None, f"Could not extract timestamp from {zip_path.name}"

        date_str, time_str = match.groups()
        file_datetime = datetime.strptime(f"{date_str}{time_str}", "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)

        # Verify timestamp is within reasonable range (second precision, allowing up to 2 minutes difference)
        time_diff_seconds = abs((file_datetime - before_creation).total_seconds())
        assert time_diff_seconds < 120, f"Timestamp {file_datetime} not within 2 minutes of {before_creation}"

    def test_user_gets_zip_with_vehicle_name_from_directory(self, parameter_editor: ParameterEditor, tmp_path: Path) -> None:
        """
        User gets zip filename using the vehicle directory name.

        GIVEN: A vehicle directory with a specific name (e.g., "CustomQuadcopter")
        WHEN: User triggers the zip creation for forum help
        THEN: The zip filename should start with the vehicle directory name
        """
        # Arrange: Create vehicle directory with custom name and setup mocks
        vehicle_dir = tmp_path / "CustomQuadcopter"
        vehicle_dir.mkdir()
        (vehicle_dir / "01_setup.param").write_text("PARAM 1.0")
        setup_zip_mock(parameter_editor, vehicle_dir, {"01_setup.param": {}})

        # Act: Create zip file
        zip_path = create_forum_help_zip(parameter_editor)

        # Assert: Verify filename starts with vehicle name
        assert zip_path.exists()
        assert zip_path.name.startswith("CustomQuadcopter_")


class TestZipVehicleForForumHelpLocation:  # pylint: disable=too-few-public-methods
    """Test the zip file location requirements."""

    def test_user_gets_zip_saved_in_vehicle_directory(
        self, parameter_editor: ParameterEditor, vehicle_directory_with_files: Path
    ) -> None:
        """
        User gets zip file saved in the current vehicle directory.

        GIVEN: A vehicle directory at a specific path
        WHEN: User triggers the zip creation for forum help
        THEN: The zip file should be created in the vehicle directory
        """
        # Arrange: Setup mocks for zip creation
        setup_zip_mock(
            parameter_editor,
            vehicle_directory_with_files,
            {
                "01_first_setup.param": {},
                "02_second_step.param": {},
            },
        )

        # Act: Create zip file
        zip_path = create_forum_help_zip(parameter_editor)

        # Assert: Verify zip is in vehicle directory
        assert zip_path.exists()
        assert zip_path.parent == vehicle_directory_with_files


class TestZipVehicleForForumHelpUserNotification:
    """Test the user notification popup requirements."""

    def test_user_receives_notification_with_zip_path_and_filename(
        self, parameter_editor: ParameterEditor, vehicle_directory_with_files: Path
    ) -> None:
        """
        User receives notification showing the full path and filename of created zip.

        GIVEN: A zip file has been successfully created
        WHEN: The creation process completes
        THEN: A notification should be returned containing the full path and filename
        """
        # Arrange: Setup mocks for zip creation
        setup_zip_mock(
            parameter_editor,
            vehicle_directory_with_files,
            {
                "01_first_setup.param": {},
                "02_second_step.param": {},
            },
        )

        mock_show_info = MagicMock()
        mock_show_error = MagicMock()

        # Act: Create zip file via public workflow
        zip_path = create_forum_help_zip(
            parameter_editor,
            show_info=mock_show_info,
            show_error=mock_show_error,
        )

        # Assert: Verify notification contains path information
        mock_show_info.assert_called_once()
        title, notification = mock_show_info.call_args[0]
        assert "Zip file successfully created" in title
        assert str(zip_path) in notification
        assert zip_path.name in notification
        assert zip_path.exists()

    def test_user_receives_notification_with_forum_upload_instructions(
        self, parameter_editor: ParameterEditor, vehicle_directory_with_files: Path
    ) -> None:
        """
        User receives notification instructing them to upload zip to ArduPilot forum.

        GIVEN: A zip file has been successfully created
        WHEN: The creation process completes
        THEN: Notification should instruct user to upload to https://discuss.ardupilot.org
        """
        # Arrange: Setup mocks for zip creation
        setup_zip_mock(
            parameter_editor,
            vehicle_directory_with_files,
            {
                "01_first_setup.param": {},
                "02_second_step.param": {},
            },
        )

        mock_show_info = MagicMock()
        mock_show_error = MagicMock()

        # Act: Create zip file and capture notification
        zip_path = create_forum_help_zip(
            parameter_editor,
            show_info=mock_show_info,
            show_error=mock_show_error,
        )

        # Assert: Verify notification contains upload instructions
        mock_show_info.assert_called_once()
        _, message = mock_show_info.call_args[0]
        assert "ArduPilot support forum" in message
        assert "upload" in message.lower()
        assert zip_path.exists()
        assert ".bin" in message
        assert "file sharing service" in message.lower()

    def test_user_receives_standard_info_notification(
        self,
        parameter_editor: ParameterEditor,
        vehicle_directory_with_files: Path,
        mock_webbrowser_open_url: MagicMock,
    ) -> None:
        """
        User receives a standard information notification.

        GIVEN: A notification popup is displayed
        WHEN: User views the notification
        THEN: The notification should be a standard info dialog
        """
        # Arrange: Setup mocks for zip creation
        setup_zip_mock(
            parameter_editor,
            vehicle_directory_with_files,
            {
                "01_first_setup.param": {},
                "02_second_step.param": {},
            },
        )

        mock_show_info = MagicMock()
        mock_show_error = MagicMock()

        result = parameter_editor.create_forum_help_zip_workflow(
            show_info=mock_show_info,
            show_error=mock_show_error,
        )

        assert result is True

        assert result is True

        mock_webbrowser_open_url.assert_called_once_with("https://discuss.ardupilot.org")

        assert result is True
        mock_show_error.assert_not_called()
        mock_show_info.assert_called_once()
        title, body = mock_show_info.call_args[0]
        assert "Zip file successfully created" in title
        assert "ArduPilot support forum" in body


class TestZipVehicleForForumHelpBrowserAction:
    """Test the automatic browser opening requirements."""

    def test_user_gets_browser_opened_to_forum_after_acknowledging_notification(
        self,
        parameter_editor: ParameterEditor,
        vehicle_directory_with_files: Path,
        mock_webbrowser_open_url: MagicMock,
    ) -> None:
        """
        User gets browser opened to ArduPilot forum after acknowledging notification.

        GIVEN: A zip file has been created and notification displayed
        WHEN: User acknowledges the notification popup
        THEN: The system default browser should open to https://discuss.ardupilot.org
        """
        # Arrange: Setup mocks for zip creation
        setup_zip_mock(
            parameter_editor,
            vehicle_directory_with_files,
            {
                "01_first_setup.param": {},
                "02_second_step.param": {},
            },
        )

        _ = create_forum_help_zip(parameter_editor)
        mock_webbrowser_open_url.assert_called_once_with("https://discuss.ardupilot.org")

    def test_browser_opens_with_exact_forum_url(
        self,
        parameter_editor: ParameterEditor,
        vehicle_directory_with_files: Path,
        mock_webbrowser_open_url: MagicMock,
    ) -> None:
        """
        Browser opens with the exact ArduPilot forum URL.

        GIVEN: The notification has been dismissed
        WHEN: The browser action is triggered
        THEN: The URL should be exactly https://discuss.ardupilot.org
        """
        # Arrange: Setup mocks for zip creation
        setup_zip_mock(
            parameter_editor,
            vehicle_directory_with_files,
            {
                "01_first_setup.param": {},
                "02_second_step.param": {},
            },
        )

        _ = create_forum_help_zip(parameter_editor)
        call_args = mock_webbrowser_open_url.call_args[0]
        assert call_args[0] == "https://discuss.ardupilot.org"


class TestZipVehicleForForumHelpErrorHandling:
    """Test error handling during zip creation."""

    def test_user_gets_error_message_when_zip_creation_fails_due_to_permissions(
        self,
        parameter_editor: ParameterEditor,
        tmp_path: Path,
        mock_webbrowser_open_url: MagicMock,
    ) -> None:
        """
        User gets error message when zip creation fails due to file permissions.

        GIVEN: A vehicle directory where zip file cannot be written (permission denied)
        WHEN: User triggers the zip creation for forum help
        THEN: An appropriate error message should be raised and browser should not open
        """
        # Arrange: Create a read-only directory (simulating permission error)
        vehicle_dir = tmp_path / "ReadOnlyVehicle"
        vehicle_dir.mkdir()
        (vehicle_dir / "01_setup.param").write_text("PARAM 1.0")

        setup_zip_mock(parameter_editor, vehicle_dir, {"01_setup.param": {}})

        # Make directory read-only after preparing files
        vehicle_dir.chmod(0o444)

        mock_show_info = MagicMock()
        mock_show_error = MagicMock()

        try:
            result = parameter_editor.create_forum_help_zip_workflow(
                show_info=mock_show_info,
                show_error=mock_show_error,
            )
        finally:
            vehicle_dir.chmod(0o755)

        assert result is False
        mock_show_info.assert_not_called()
        mock_show_error.assert_called_once()
        title, message = mock_show_error.call_args[0]
        assert "Zip file creation failed" in title
        assert "file system error" in message
        assert "permission" in message.lower()
        mock_webbrowser_open_url.assert_not_called()

    def test_user_gets_error_message_when_zip_creation_fails_due_to_disk_space(
        self,
        parameter_editor: ParameterEditor,
        tmp_path: Path,
        mock_webbrowser_open_url: MagicMock,
    ) -> None:
        """
        User gets error message when zip creation fails due to insufficient disk space.

        GIVEN: A scenario where disk space is insufficient
        WHEN: User triggers the zip creation for forum help
        THEN: An appropriate error message should be raised and browser should not open
        """
        # Arrange: Set vehicle directory and file_parameters
        vehicle_dir = tmp_path / "TestVehicle"
        vehicle_dir.mkdir()
        (vehicle_dir / "01_setup.param").write_text("PARAM 1.0")
        filesystem = get_filesystem(parameter_editor)
        filesystem.vehicle_dir = str(vehicle_dir)
        filesystem.file_parameters = {"01_setup.param": ParDict()}

        # Act & Assert: Mock disk space error by making zip_files raise OSError
        fs_any: Any = filesystem
        fs_any.zip_files = MagicMock(side_effect=OSError("No space left on device"))

        mock_show_info = MagicMock()
        mock_show_error = MagicMock()

        result = parameter_editor.create_forum_help_zip_workflow(
            show_info=mock_show_info,
            show_error=mock_show_error,
        )

        assert result is False
        mock_show_info.assert_not_called()
        mock_show_error.assert_called_once()
        title, message = mock_show_error.call_args[0]
        assert "Zip file creation failed" in title
        assert "No space left on device" in message
        mock_webbrowser_open_url.assert_not_called()

    def test_browser_does_not_open_when_zip_creation_fails(
        self,
        parameter_editor: ParameterEditor,
        tmp_path: Path,
        mock_webbrowser_open_url: MagicMock,
    ) -> None:
        """
        Browser does not open when zip creation fails.

        GIVEN: A zip creation operation that will fail
        WHEN: The operation encounters an error
        THEN: The browser should not be opened to the forum URL
        """
        # Arrange: Set vehicle directory that will cause error and file_parameters
        vehicle_dir = tmp_path / "ErrorVehicle"
        vehicle_dir.mkdir()
        (vehicle_dir / "01_setup.param").write_text("PARAM 1.0")
        filesystem = get_filesystem(parameter_editor)
        filesystem.vehicle_dir = str(vehicle_dir)
        filesystem.file_parameters = {"01_setup.param": ParDict()}

        # Act & Assert: Mock zip creation failure by making zip_files raise OSError
        fs_any = cast("Any", filesystem)
        fs_any.zip_files = MagicMock(side_effect=OSError("Simulated error"))

        mock_show_info = MagicMock()
        mock_show_error = MagicMock()

        result = parameter_editor.create_forum_help_zip_workflow(
            show_info=mock_show_info,
            show_error=mock_show_error,
        )

        assert result is False
        mock_webbrowser_open_url.assert_not_called()

    def test_user_gets_descriptive_error_for_missing_vehicle_directory(
        self,
        parameter_editor: ParameterEditor,
        mock_webbrowser_open_url: MagicMock,
    ) -> None:
        """
        User gets descriptive error when vehicle directory is missing.

        GIVEN: A parameter editor with no vehicle directory set or invalid path
        WHEN: User triggers the zip creation for forum help
        THEN: A descriptive error should be raised explaining the missing directory
        """
        # Arrange: Set invalid vehicle directory
        missing_path = Path("/non/existent/path")
        filesystem = get_filesystem(parameter_editor)
        filesystem.vehicle_dir = str(missing_path)
        filesystem.file_parameters = {"01_setup.param": ParDict()}
        fs_any: Any = filesystem
        fs_any.zip_files = MagicMock(side_effect=FileNotFoundError(f"{missing_path} not found"))

        mock_show_info = MagicMock()
        mock_show_error = MagicMock()

        result = parameter_editor.create_forum_help_zip_workflow(
            show_info=mock_show_info,
            show_error=mock_show_error,
        )

        assert result is False
        mock_show_error.assert_called_once()
        title, message = mock_show_error.call_args[0]
        assert "Zip file creation failed" in title
        assert "not found" in message.lower()
        mock_show_info.assert_not_called()
        mock_webbrowser_open_url.assert_not_called()


class TestZipVehicleForForumHelpEmptyDirectory:
    """Test behavior when vehicle directory has no required files."""

    def test_user_gets_zip_with_only_available_files(self, parameter_editor: ParameterEditor, tmp_path: Path) -> None:
        """
        User gets zip containing only files that exist in the directory.

        GIVEN: A vehicle directory with only some of the specified files
        WHEN: User triggers the zip creation for forum help
        THEN: The zip should contain only the files that exist, without errors
        """
        # Arrange: Create minimal vehicle directory and setup mocks
        vehicle_dir = tmp_path / "MinimalVehicle"
        vehicle_dir.mkdir()
        (vehicle_dir / "01_setup.param").write_text("PARAM 1.0")
        # Intentionally not creating vehicle.jpg, vehicle_components.json, etc.
        setup_zip_mock(parameter_editor, vehicle_dir, {"01_setup.param": {}})

        # Act: Create zip file
        zip_path = create_forum_help_zip(parameter_editor)

        # Assert: Verify zip contains only existing files
        assert zip_path.exists()
        with ZipFile(zip_path, "r") as zipf:
            file_list = zipf.namelist()
            assert "01_setup.param" in file_list
            assert "vehicle.jpg" not in file_list
            assert "vehicle_components.json" not in file_list

    def test_user_gets_error_when_no_parameter_files_exist(
        self,
        parameter_editor: ParameterEditor,
        tmp_path: Path,
        mock_webbrowser_open_url: MagicMock,
    ) -> None:
        """
        User gets error when no numbered parameter files exist in directory.

        GIVEN: A vehicle directory with no numbered parameter files
        WHEN: User triggers the zip creation for forum help
        THEN: An appropriate error or warning should be raised
        """
        # Arrange: Create empty vehicle directory
        vehicle_dir = tmp_path / "EmptyVehicle"
        vehicle_dir.mkdir()
        filesystem = get_filesystem(parameter_editor)
        filesystem.vehicle_dir = str(vehicle_dir)

        mock_show_info = MagicMock()
        mock_show_error = MagicMock()

        result = parameter_editor.create_forum_help_zip_workflow(
            show_info=mock_show_info,
            show_error=mock_show_error,
        )

        assert result is False
        mock_show_info.assert_not_called()
        mock_show_error.assert_called_once()
        title, message = mock_show_error.call_args[0]
        assert "Zip file creation failed" in title
        assert "No intermediate parameter files found" in message
        mock_webbrowser_open_url.assert_not_called()


class TestZipVehicleForForumHelpIntegration:  # pylint: disable=too-few-public-methods
    """Integration tests for the complete workflow."""

    def test_user_can_complete_full_forum_help_workflow(
        self,
        parameter_editor: ParameterEditor,
        vehicle_directory_with_files: Path,
        mock_webbrowser_open_url: MagicMock,
    ) -> None:
        """
        User can complete the entire forum help workflow successfully.

        GIVEN: A user with a properly configured vehicle directory
        WHEN: User triggers zip creation, reviews notification, and dismisses it
        THEN: Zip is created with correct files, notification is shown, and browser opens to forum
        """
        # Arrange: Setup mocks for zip creation
        setup_zip_mock(
            parameter_editor,
            vehicle_directory_with_files,
            {
                "01_first_setup.param": {},
                "02_second_step.param": {},
                "15_advanced.param": {},
            },
        )

        mock_show_info = MagicMock()
        mock_show_error = MagicMock()

        # Act: Complete workflow
        zip_path = create_forum_help_zip(
            parameter_editor,
            show_info=mock_show_info,
            show_error=mock_show_error,
        )

        # Assert: Verify complete workflow
        assert zip_path.exists()
        assert re.match(r"^MyDrone_\d{8}_\d{6}UTC\.zip$", zip_path.name)

        with ZipFile(zip_path, "r") as zipf:
            file_list = zipf.namelist()
            assert "00_default.param" in file_list
            assert "01_first_setup.param" in file_list
            assert "02_second_step.param" in file_list
            assert "vehicle.jpg" in file_list
            assert "vehicle_components.json" in file_list
            assert "tempcal_gyro.png" in file_list
            assert "tempcal_acc.png" in file_list
            assert "tuning_report.csv" in file_list

        mock_show_info.assert_called_once()
        _, notification = mock_show_info.call_args[0]
        assert "ArduPilot support forum" in notification

        mock_webbrowser_open_url.assert_called_once_with("https://discuss.ardupilot.org")


class TestCreateForumHelpZipWorkflow:
    """Test the complete create_forum_help_zip_workflow method."""

    def test_user_completes_successful_workflow(
        self,
        parameter_editor: ParameterEditor,
        vehicle_directory_with_files: Path,
        mock_webbrowser_open_url: MagicMock,
    ) -> None:
        """
        User successfully completes the forum help workflow.

        GIVEN: A properly configured vehicle directory
        WHEN: User triggers the complete workflow
        THEN: Zip is created, success notification shown, and browser opens
        """
        # Arrange: Setup mocks
        setup_zip_mock(
            parameter_editor,
            vehicle_directory_with_files,
            {
                "01_first_setup.param": {},
                "02_second_step.param": {},
            },
        )
        mock_show_info = MagicMock()
        mock_show_error = MagicMock()

        # Act: Execute workflow
        result = parameter_editor.create_forum_help_zip_workflow(
            show_info=mock_show_info,
            show_error=mock_show_error,
        )

        assert result is True

        # Zip file was created
        zip_files = list(vehicle_directory_with_files.glob("*.zip"))
        assert len(zip_files) == 1
        assert zip_files[0].exists()

        # Success notification was shown
        mock_show_info.assert_called_once()
        title, body = mock_show_info.call_args[0]
        assert "Zip file successfully created" in title
        assert "ArduPilot support forum" in body

        # No error notification
        mock_show_error.assert_not_called()
        # Browser opened to forum
        mock_webbrowser_open_url.assert_called_once_with("https://discuss.ardupilot.org")

    def test_workflow_shows_error_when_vehicle_directory_missing(
        self,
        parameter_editor: ParameterEditor,
        tmp_path: Path,
        mock_webbrowser_open_url: MagicMock,
    ) -> None:
        """
        Workflow shows error when vehicle directory does not exist.

        GIVEN: An invalid vehicle directory path
        WHEN: User triggers the workflow
        THEN: Error notification is shown and browser does not open
        """
        # Arrange: Set non-existent directory
        parameter_editor._local_filesystem.vehicle_dir = str(tmp_path / "NonExistent")
        parameter_editor._local_filesystem.file_parameters = {"01_setup.param": ParDict()}
        fs_any: Any = parameter_editor._local_filesystem
        fs_any.zip_files = MagicMock(side_effect=FileNotFoundError("Vehicle directory not found"))
        mock_show_info = MagicMock()
        mock_show_error = MagicMock()

        # Act: Execute workflow
        result = parameter_editor.create_forum_help_zip_workflow(
            show_info=mock_show_info,
            show_error=mock_show_error,
        )

        mock_webbrowser_open_url.assert_not_called()

        # Assert: Workflow failed
        assert result is False

        # Error notification was shown
        mock_show_error.assert_called_once()
        title, message = mock_show_error.call_args[0]
        assert "Zip file creation failed" in title
        assert "Failed to create zip file:" in message

        # No success notification
        mock_show_info.assert_not_called()

    def test_workflow_shows_error_when_no_parameter_files(
        self,
        parameter_editor: ParameterEditor,
        tmp_path: Path,
        mock_webbrowser_open_url: MagicMock,
    ) -> None:
        """
        Workflow shows error when no parameter files found.

        GIVEN: A vehicle directory with no parameter files
        WHEN: User triggers the workflow
        THEN: Error notification is shown and browser does not open
        """
        # Arrange: Create empty directory
        vehicle_dir = tmp_path / "EmptyVehicle"
        vehicle_dir.mkdir()
        parameter_editor._local_filesystem.vehicle_dir = str(vehicle_dir)
        parameter_editor._local_filesystem.file_parameters = {}  # No parameter files
        mock_show_info = MagicMock()
        mock_show_error = MagicMock()

        # Act: Execute workflow
        result = parameter_editor.create_forum_help_zip_workflow(
            show_info=mock_show_info,
            show_error=mock_show_error,
        )

        mock_webbrowser_open_url.assert_not_called()

        # Assert: Workflow failed
        assert result is False

        # Error notification was shown
        mock_show_error.assert_called_once()
        title, message = mock_show_error.call_args[0]
        assert "Zip file creation failed" in title
        assert "No intermediate parameter files found" in message

        # No success notification
        mock_show_info.assert_not_called()

    def test_workflow_shows_error_on_permission_error(
        self,
        parameter_editor: ParameterEditor,
        vehicle_directory_with_files: Path,
        mock_webbrowser_open_url: MagicMock,
    ) -> None:
        """
        Workflow shows error when permission denied creating zip.

        GIVEN: A scenario where zip creation fails due to permissions
        WHEN: User triggers the workflow
        THEN: Error notification is shown and browser does not open
        """
        # Arrange: Setup to fail with PermissionError
        parameter_editor._local_filesystem.vehicle_dir = str(vehicle_directory_with_files)
        parameter_editor._local_filesystem.file_parameters = {"01_setup.param": ParDict()}
        fs_any: Any = parameter_editor._local_filesystem
        fs_any.zip_files = MagicMock(side_effect=PermissionError("Permission denied"))
        mock_show_info = MagicMock()
        mock_show_error = MagicMock()

        # Act: Execute workflow
        result = parameter_editor.create_forum_help_zip_workflow(
            show_info=mock_show_info,
            show_error=mock_show_error,
        )

        mock_webbrowser_open_url.assert_not_called()

        # Assert: Workflow failed
        assert result is False

        # Error notification was shown
        mock_show_error.assert_called_once()
        title, message = mock_show_error.call_args[0]
        assert "Zip file creation failed" in title
        assert "file system error" in message
        assert "Permission denied" in message

        # No success notification
        mock_show_info.assert_not_called()

    def test_workflow_shows_error_on_os_error(
        self,
        parameter_editor: ParameterEditor,
        vehicle_directory_with_files: Path,
        mock_webbrowser_open_url: MagicMock,
    ) -> None:
        """
        Workflow shows error when OS error occurs.

        GIVEN: A scenario where zip creation fails due to OS error
        WHEN: User triggers the workflow
        THEN: Error notification is shown and browser does not open
        """
        # Arrange: Setup to fail with OSError
        parameter_editor._local_filesystem.vehicle_dir = str(vehicle_directory_with_files)
        parameter_editor._local_filesystem.file_parameters = {"01_setup.param": ParDict()}
        fs_any: Any = parameter_editor._local_filesystem
        fs_any.zip_files = MagicMock(side_effect=OSError("No space left on device"))
        mock_show_info = MagicMock()
        mock_show_error = MagicMock()

        # Act: Execute workflow
        result = parameter_editor.create_forum_help_zip_workflow(
            show_info=mock_show_info,
            show_error=mock_show_error,
        )

        mock_webbrowser_open_url.assert_not_called()

        # Assert: Workflow failed
        assert result is False

        # Error notification was shown with appropriate message
        mock_show_error.assert_called_once()
        title, message = mock_show_error.call_args[0]
        assert "Zip file creation failed" in title
        assert "file system error" in message
        assert "No space left on device" in message

        # No success notification
        mock_show_info.assert_not_called()

    def test_workflow_notification_contains_zip_path_and_instructions(
        self,
        parameter_editor: ParameterEditor,
        vehicle_directory_with_files: Path,
        mock_webbrowser_open_url: MagicMock,
    ) -> None:
        """
        Workflow notification contains zip file path and upload instructions.

        GIVEN: A successful zip creation
        WHEN: User views the notification
        THEN: Notification shows zip path and forum upload instructions
        """
        # Arrange: Setup mocks
        setup_zip_mock(
            parameter_editor,
            vehicle_directory_with_files,
            {
                "01_first_setup.param": {},
            },
        )
        mock_show_info = MagicMock()
        mock_show_error = MagicMock()

        # Act: Execute workflow
        result = parameter_editor.create_forum_help_zip_workflow(
            show_info=mock_show_info,
            show_error=mock_show_error,
        )

        mock_webbrowser_open_url.assert_called_once_with("https://discuss.ardupilot.org")

        # Assert: Workflow completed successfully
        assert result is True

        # Notification contains required information
        title, notification_message = mock_show_info.call_args[0]

        assert "Zip file successfully created" in title
        assert "MyDrone" in notification_message  # Vehicle name in filename
        assert "UTC.zip" in notification_message  # Timestamp format
        assert "ArduPilot support forum" in notification_message
        assert ".bin" in notification_message  # Flight log mention

        # Browser verification handled above via mock_webbrowser_open_url
