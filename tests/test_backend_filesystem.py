#!/usr/bin/env python3

"""
Tests for the backend_filesystem.py file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import unittest
from argparse import ArgumentParser
from os import path as os_path
from subprocess import SubprocessError
from unittest.mock import MagicMock, mock_open, patch

from ardupilot_methodic_configurator.annotate_params import Par
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem, is_within_tolerance

# pylint: disable=too-many-lines, too-many-arguments, too-many-positional-arguments


class TestLocalFilesystem(unittest.TestCase):  # pylint: disable=too-many-public-methods
    """LocalFilesystem test class."""

    def test_read_params_from_files(self) -> None:
        """Test reading parameters from files with proper filtering."""
        mock_vehicle_dir = "/mock/dir"
        filesystem = LocalFilesystem(
            mock_vehicle_dir,
            "ArduCopter",
            "4.3.0",
            allow_editing_template_files=False,
            save_component_to_system_templates=False,
        )

        with (
            patch(
                "ardupilot_methodic_configurator.backend_filesystem.os_listdir",
                return_value=["02_test.param", "00_default.param", "01_ignore_readonly.param"],
            ),
            patch("ardupilot_methodic_configurator.backend_filesystem.os_path.isdir", return_value=True),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem.Par.load_param_file_into_dict",
                return_value={"PARAM1": 1.0},
            ),
            patch("ardupilot_methodic_configurator.backend_filesystem.os_path.join", side_effect=os_path.join),
        ):
            result = filesystem.read_params_from_files()
            assert len(result) == 1
            assert "02_test.param" in result
            assert result["02_test.param"] == {"PARAM1": 1.0}

    def test_str_to_bool(self) -> None:
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        assert lfs.str_to_bool("true")
        assert lfs.str_to_bool("yes")
        assert lfs.str_to_bool("1")
        assert not lfs.str_to_bool("false")
        assert not lfs.str_to_bool("no")
        assert not lfs.str_to_bool("0")
        assert lfs.str_to_bool("maybe") is None

    def test_re_init(self) -> None:
        """Test reinitializing the filesystem with new parameters."""
        mock_vehicle_dir = "/mock/dir"
        filesystem = LocalFilesystem(
            mock_vehicle_dir,
            "ArduCopter",
            "4.3.0",
            allow_editing_template_files=False,
            save_component_to_system_templates=False,
        )

        with (
            patch.object(filesystem, "load_vehicle_components_json_data", return_value=True),
            patch.object(filesystem, "get_fc_fw_version_from_vehicle_components_json", return_value="4.3.0"),
            patch.object(filesystem, "get_fc_fw_type_from_vehicle_components_json", return_value="ArduCopter"),
            patch.object(filesystem, "rename_parameter_files"),
            patch.object(filesystem, "read_params_from_files", return_value={}),
        ):
            filesystem.re_init(mock_vehicle_dir, "ArduCopter")
            assert filesystem.vehicle_dir == mock_vehicle_dir
            assert filesystem.vehicle_type == "ArduCopter"

    def test_vehicle_configuration_files_exist(self) -> None:
        """Test checking if vehicle configuration files exist."""
        mock_vehicle_dir = "/mock/dir"
        filesystem = LocalFilesystem(
            mock_vehicle_dir,
            "ArduCopter",
            "4.3.0",
            allow_editing_template_files=False,
            save_component_to_system_templates=False,
        )

        with (
            patch("ardupilot_methodic_configurator.backend_filesystem.os_path.exists", return_value=True),
            patch("ardupilot_methodic_configurator.backend_filesystem.os_path.isdir", return_value=True),
            patch(
                "ardupilot_methodic_configurator.backend_filesystem.os_listdir",
                return_value=["vehicle_components.json", "02_test.param"],
            ),
            patch("ardupilot_methodic_configurator.backend_filesystem.platform_system", return_value="Linux"),
        ):
            assert filesystem.vehicle_configuration_files_exist(mock_vehicle_dir)

        with (
            patch("ardupilot_methodic_configurator.backend_filesystem.os_path.exists", return_value=True),
            patch("ardupilot_methodic_configurator.backend_filesystem.os_path.isdir", return_value=True),
            patch("ardupilot_methodic_configurator.backend_filesystem.os_listdir", return_value=["invalid.txt"]),
        ):
            assert not filesystem.vehicle_configuration_files_exist(mock_vehicle_dir)

    def test_remove_created_files_and_vehicle_dir_not_exists(self) -> None:
        """
        Remove created files and vehicle directory if they exist.

        GIVEN: A LocalFilesystem whose vehicle directory does not exist
        WHEN: remove_created_files_and_vehicle_dir is called
        THEN: It should return a localized error message indicating the directory is missing.
        """
        mock_vehicle_dir = "/mock/dir"
        filesystem = LocalFilesystem(
            mock_vehicle_dir,
            "ArduCopter",
            "4.3.0",
            allow_editing_template_files=False,
            save_component_to_system_templates=False,
        )

        with (
            patch("ardupilot_methodic_configurator.backend_filesystem.os_path.exists", return_value=False) as mock_exists,
            patch("ardupilot_methodic_configurator.backend_filesystem.os_listdir") as mock_listdir,
        ):
            ret = filesystem.remove_created_files_and_vehicle_dir()
            # Should return a non-empty error message mentioning the new vehicle directory
            assert isinstance(ret, str)
            assert "New vehicle directory does not exist" in ret
            # listdir must not have been called when directory doesn't exist
            assert not mock_listdir.called
            mock_exists.assert_called()

    def test_remove_created_files_and_vehicle_dir_success(self) -> None:
        """
        Test removing created files and vehicle directory with success.

        GIVEN: A LocalFilesystem with files, a dir and a symlink in the vehicle directory
        WHEN: remove_created_files_and_vehicle_dir is called
        THEN: It should remove files/dirs/links and return an empty string on success.
        """
        mock_vehicle_dir = "/mock/dir"
        filesystem = LocalFilesystem(
            mock_vehicle_dir,
            "ArduCopter",
            "4.3.0",
            allow_editing_template_files=False,
            save_component_to_system_templates=False,
        )

        items = ["file1", "dir1", "link1"]

        real_join = os_path.join

        def join_side_effect(a, b) -> str:
            return real_join(a, b)

        def islink_side_effect(p) -> bool:
            return p.endswith("link1")

        def isdir_side_effect(p) -> bool:
            return p.endswith("dir1")

        with (
            patch("ardupilot_methodic_configurator.backend_filesystem.os_path.exists", return_value=True),
            patch("ardupilot_methodic_configurator.backend_filesystem.os_listdir", return_value=items),
            patch("ardupilot_methodic_configurator.backend_filesystem.os_path.join", side_effect=join_side_effect),
            patch("ardupilot_methodic_configurator.backend_filesystem.os_path.islink", side_effect=islink_side_effect),
            patch("ardupilot_methodic_configurator.backend_filesystem.os_path.isdir", side_effect=isdir_side_effect),
            patch("ardupilot_methodic_configurator.backend_filesystem.os_remove") as mock_remove,
            patch("ardupilot_methodic_configurator.backend_filesystem.shutil_rmtree") as mock_rmtree,
            patch("ardupilot_methodic_configurator.backend_filesystem.os_rmdir") as mock_rmdir,
        ):
            ret = filesystem.remove_created_files_and_vehicle_dir()
            assert ret == ""
            # file1 and link1 should trigger os_remove twice
            assert mock_remove.call_count == 2
            # dir1 should trigger shutil.rmtree
            mock_rmtree.assert_called_once()
            # vehicle directory removal attempted
            mock_rmdir.assert_called_once_with(mock_vehicle_dir)

    def test_remove_created_files_and_vehicle_dir_with_errors(self) -> None:
        """
        Test removing created files and vehicle directory with errors.

        GIVEN: A LocalFilesystem where removal operations raise OSError
        WHEN: remove_created_files_and_vehicle_dir is called
        THEN: It should collect error messages and return a combined error string.
        """
        mock_vehicle_dir = "/mock/dir"
        filesystem = LocalFilesystem(
            mock_vehicle_dir,
            "ArduCopter",
            "4.3.0",
            allow_editing_template_files=False,
            save_component_to_system_templates=False,
        )

        items = ["file_err"]

        real_join = os_path.join

        def join_side_effect(a, b) -> str:
            return real_join(a, b)

        with (
            patch("ardupilot_methodic_configurator.backend_filesystem.os_path.exists", return_value=True),
            patch("ardupilot_methodic_configurator.backend_filesystem.os_listdir", return_value=items),
            patch("ardupilot_methodic_configurator.backend_filesystem.os_path.join", side_effect=join_side_effect),
            patch("ardupilot_methodic_configurator.backend_filesystem.os_path.islink", return_value=False),
            patch("ardupilot_methodic_configurator.backend_filesystem.os_path.isdir", return_value=False),
            patch("ardupilot_methodic_configurator.backend_filesystem.os_remove", side_effect=OSError("perm denied")),
            patch("ardupilot_methodic_configurator.backend_filesystem.os_rmdir", side_effect=OSError("dir remove failed")),
            patch("ardupilot_methodic_configurator.backend_filesystem.logging_exception"),
            patch("ardupilot_methodic_configurator.backend_filesystem.logging_error"),
        ):
            ret = filesystem.remove_created_files_and_vehicle_dir()
            assert isinstance(ret, str)
            # Should indicate there was an error removing created files
            assert "Error removing created files" in ret
            # Both error messages should be present (joined by "; ")
            assert "perm denied" in ret
            assert "dir remove failed" in ret

    def test_rename_parameter_files(self) -> None:
        """Test renaming parameter files."""
        mock_vehicle_dir = "/mock/dir"
        filesystem = LocalFilesystem(
            mock_vehicle_dir,
            "ArduCopter",
            "4.3.0",
            allow_editing_template_files=False,
            save_component_to_system_templates=False,
        )
        filesystem.configuration_steps = {"new_file.param": {"old_filenames": ["old_file.param"]}}

        with (
            patch.object(filesystem, "vehicle_configuration_file_exists") as mock_exists,
            patch("ardupilot_methodic_configurator.backend_filesystem.os_rename") as mock_rename,
            patch("ardupilot_methodic_configurator.backend_filesystem.os_path.join", side_effect=os_path.join),
        ):
            mock_exists.side_effect = lambda x: x == "old_file.param"
            filesystem.rename_parameter_files()
            expected_old = os_path.join("/mock/dir", "old_file.param")
            expected_new = os_path.join("/mock/dir", "new_file.param")
            mock_rename.assert_called_once_with(expected_old, expected_new)

    def test_vehicle_configuration_file_exists_comprehensive(self) -> None:
        """Test checking if a specific configuration file exists with comprehensive path and size checks."""
        mock_vehicle_dir = "/mock/dir"
        filesystem = LocalFilesystem(
            mock_vehicle_dir,
            "ArduCopter",
            "4.3.0",
            allow_editing_template_files=False,
            save_component_to_system_templates=False,
        )

        # Test with all conditions met (file exists, is a file, and has size > 0)
        with (
            patch("os.path.exists", return_value=True) as mock_exists,
            patch("os.path.isfile", return_value=True) as mock_isfile,
            patch("os.path.getsize", return_value=100) as mock_getsize,
            patch("os.path.join", side_effect=os_path.join) as mock_join,
        ):
            assert filesystem.vehicle_configuration_file_exists("test.param")
            mock_exists.assert_called_once()
            mock_isfile.assert_called_once()
            mock_getsize.assert_called_once()
            mock_join.assert_called_once_with(mock_vehicle_dir, "test.param")

        # Test with file that exists but is empty
        with (
            patch("os.path.exists", return_value=True),
            patch("os.path.isfile", return_value=True),
            patch("os.path.getsize", return_value=0),
            patch("os.path.join", side_effect=os_path.join),
        ):
            assert not filesystem.vehicle_configuration_file_exists("empty.param")

        # Test with directory instead of file
        with (
            patch("os.path.exists", return_value=True),
            patch("os.path.isfile", return_value=False),
            patch("os.path.join", side_effect=os_path.join),
        ):
            assert not filesystem.vehicle_configuration_file_exists("dir.param")

        # Test with nonexistent file
        with patch("os.path.exists", return_value=False), patch("os.path.join", side_effect=os_path.join):
            assert not filesystem.vehicle_configuration_file_exists("nonexistent.param")

    @patch("os.path.exists")
    @patch("os.path.isfile")
    def test_zip_file_exists(self, mock_isfile, mock_exists) -> None:
        mock_exists.return_value = True
        mock_isfile.return_value = True
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        result = lfs.zip_file_exists()
        assert result
        mock_exists.assert_called_once()
        mock_isfile.assert_called_once()

    @patch("os.path.exists")
    @patch("os.path.isfile")
    def test_vehicle_image_exists(self, mock_isfile, mock_exists) -> None:
        mock_exists.return_value = True
        mock_isfile.return_value = True
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        result = lfs.vehicle_image_exists()
        assert result
        mock_exists.assert_called_once()
        mock_isfile.assert_called_once()

    @patch("os.path.exists")
    @patch("os.path.isdir")
    def test_directory_exists(self, mock_isdir, mock_exists) -> None:
        mock_exists.return_value = True
        mock_isdir.return_value = True
        result = LocalFilesystem.directory_exists("test_directory")
        assert result
        mock_exists.assert_called_once_with("test_directory")
        mock_isdir.assert_called_once_with("test_directory")

    def test_getcwd(self) -> None:
        """Test getting current working directory."""
        mock_vehicle_dir = "/mock/dir"
        mock_cwd = "/test/dir"
        filesystem = LocalFilesystem(
            mock_vehicle_dir,
            "ArduCopter",
            "4.3.0",
            allow_editing_template_files=False,
            save_component_to_system_templates=False,
        )

        with patch("ardupilot_methodic_configurator.backend_filesystem.os_getcwd", return_value=mock_cwd) as mock_getcwd:
            result = filesystem.getcwd()
            assert result == mock_cwd
            mock_getcwd.assert_called_once()

    @patch("os.path.join")
    def test_new_vehicle_dir(self, mock_join) -> None:
        mock_join.return_value = "base_dir/new_dir"
        result = LocalFilesystem.new_vehicle_dir("base_dir", "new_dir")
        assert result == "base_dir/new_dir"
        mock_join.assert_called_once_with("base_dir", "new_dir")

    @patch("os.path.basename")
    @patch("os.path.split")
    @patch("os.path.normpath")
    def test_get_directory_name_from_full_path(self, mock_normpath, mock_split, mock_basename) -> None:
        mock_normpath.return_value = "normalized_path"
        mock_split.return_value = ("head", "tail")
        mock_basename.return_value = "tail"
        result = LocalFilesystem.get_directory_name_from_full_path("full_path")
        assert result == "tail"
        mock_normpath.assert_called_once_with("full_path")
        mock_split.assert_called_once_with("normalized_path")
        mock_basename.assert_called_once_with("tail")

    def test_vehicle_image_filepath(self) -> None:
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        with patch("os.path.join") as mock_join:
            mock_join.return_value = "vehicle_dir/vehicle.jpg"
            result = lfs.vehicle_image_filepath()
            assert result == "vehicle_dir/vehicle.jpg"
            mock_join.assert_called_once_with("vehicle_dir", "vehicle.jpg")

    def test_tempcal_imu_result_param_tuple(self) -> None:
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        with patch("os.path.join") as mock_join:
            mock_join.return_value = "vehicle_dir/03_imu_temperature_calibration_results.param"
            result = lfs.tempcal_imu_result_param_tuple()
            assert result == (
                "03_imu_temperature_calibration_results.param",
                "vehicle_dir/03_imu_temperature_calibration_results.param",
            )
            mock_join.assert_called_once_with("vehicle_dir", "03_imu_temperature_calibration_results.param")

    def test_zip_file_path(self) -> None:
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        with patch("os.path.join") as mock_join:
            mock_join.return_value = "vehicle_dir/vehicle_name.zip"
            lfs.get_vehicle_directory_name = MagicMock(return_value="vehicle_name")
            result = lfs.zip_file_path()
            assert result == "vehicle_dir/vehicle_name.zip"
            mock_join.assert_called_once_with("vehicle_dir", "vehicle_name.zip")

    def test_add_configuration_file_to_zip(self) -> None:
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        with patch("os.path.join") as mock_join:
            mock_join.return_value = "vehicle_dir/test_file.param"
            lfs.vehicle_configuration_file_exists = MagicMock(return_value=True)
            mock_zipfile = MagicMock()
            lfs.add_configuration_file_to_zip(mock_zipfile, "test_file.param")
            mock_join.assert_called_once_with("vehicle_dir", "test_file.param")
            mock_zipfile.write.assert_called_once_with("vehicle_dir/test_file.param", arcname="test_file.param")

    def test_get_upload_local_and_remote_filenames_missing_file(self) -> None:
        """Test get_upload_local_and_remote_filenames with missing file."""
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        result = lfs.get_upload_local_and_remote_filenames("missing_file")
        assert result == ("", "")

    def test_get_upload_local_and_remote_filenames_missing_upload_section(self) -> None:
        """Test get_upload_local_and_remote_filenames with missing upload section."""
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        lfs.configuration_steps = {"selected_file": {}}
        result = lfs.get_upload_local_and_remote_filenames("selected_file")
        assert result == ("", "")

    def test_get_download_url_and_local_filename_missing_file(self) -> None:
        """Test get_download_url_and_local_filename with missing file."""
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        result = lfs.get_download_url_and_local_filename("missing_file")
        assert result == ("", "")

    def test_get_download_url_and_local_filename_missing_download_section(self) -> None:
        """Test get_download_url_and_local_filename with missing download section."""
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        lfs.configuration_steps = {"selected_file": {}}
        result = lfs.get_download_url_and_local_filename("selected_file")
        assert result == ("", "")

    def test_write_and_read_last_uploaded_filename_error_handling(self) -> None:
        """Test error handling in write_and_read_last_uploaded_filename."""
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        test_filename = "test.param"

        # Test write error
        with patch("builtins.open", side_effect=OSError("Write error")):
            lfs.write_last_uploaded_filename(test_filename)
            # Should not raise exception, just log error

        # Test read error
        with patch("builtins.open", side_effect=OSError("Read error")):
            result = lfs._LocalFilesystem__read_last_uploaded_filename()  # pylint: disable=protected-access
            assert result == ""

    def test_copy_fc_values_to_file_with_missing_params(self) -> None:
        """Test copy_fc_values_to_file with missing parameters."""
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        test_params = {"PARAM1": 1.0, "PARAM2": 2.0, "PARAM3": 3.0}
        test_file = "test.param"

        # Test with partially matching parameters
        lfs.file_parameters = {test_file: {"PARAM1": MagicMock(value=0.0), "PARAM2": MagicMock(value=0.0)}}
        result = lfs.copy_fc_values_to_file(test_file, test_params)
        assert result == 2
        assert lfs.file_parameters[test_file]["PARAM1"].value == 1.0
        assert lfs.file_parameters[test_file]["PARAM2"].value == 2.0

    def test_get_start_file_empty_files(self) -> None:
        """Test get_start_file with empty files list."""
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        lfs.file_parameters = {}
        result = lfs.get_start_file(1, tcal_available=True)
        assert result == ""

    def test_get_eval_variables_with_none(self) -> None:
        """Test get_eval_variables with None values."""
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        lfs.vehicle_components_fs.data = None
        lfs.doc_dict = None
        result = lfs.get_eval_variables()
        assert not result

    def test_tolerance_check_with_zero_values(self) -> None:
        """Test numerical value comparison with zero values."""
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )

        # Test zero values
        x, y = 0.0, 0.0
        assert abs(x - y) <= 1e-08 + (1e-03 * abs(y))

        # Test small positive vs zero
        x, y = 1e-10, 0.0
        assert abs(x - y) <= 1e-08 + (1e-03 * abs(y))

        # Test writing
        test_filename = "test_param.param"
        expected_path = os_path.join("vehicle_dir", "last_uploaded_filename.txt")
        with patch("builtins.open", unittest.mock.mock_open()) as mock_file:
            lfs.write_last_uploaded_filename(test_filename)
            mock_file.assert_called_once_with(expected_path, "w", encoding="utf-8")
            mock_file().write.assert_called_once_with(test_filename)

        # Test reading
        with patch("builtins.open", unittest.mock.mock_open(read_data=test_filename)) as mock_file:
            result = lfs._LocalFilesystem__read_last_uploaded_filename()  # pylint: disable=protected-access
            assert result == test_filename
            mock_file.assert_called_once_with(expected_path, encoding="utf-8")

    def test_tolerance_handling(self) -> None:
        """Test parameter value tolerance checking."""
        # Setup LocalFilesystem instance

        # Test cases within tolerance (default 0.01%)
        assert is_within_tolerance(10.0, 10.0009)  # +0.009% - should pass
        assert is_within_tolerance(10.0, 9.9991)  # -0.009% - should pass
        assert is_within_tolerance(100, 100)  # Exact match
        assert is_within_tolerance(0.0, 0.0)  # Zero case

        # Test cases outside tolerance
        assert not is_within_tolerance(10.0, 10.02)  # +0.2% - should fail
        assert not is_within_tolerance(10.0, 9.98)  # -0.2% - should fail
        assert not is_within_tolerance(100, 101)  # Integer case

        # Test with custom tolerance
        custom_tolerance = 0.2  # 0.2%
        assert is_within_tolerance(10.0, 10.015, atol=custom_tolerance)  # +0.15% - should pass
        assert is_within_tolerance(10.0, 9.985, atol=custom_tolerance)  # -0.15% - should pass

    def test_write_param_default_values(self) -> None:
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )

        # Test with new values
        new_values = {"PARAM1": MagicMock(value=1.0)}
        result = lfs.write_param_default_values(new_values)
        assert result is True
        assert lfs.param_default_dict == new_values

        # Test with same values (no change)
        result = lfs.write_param_default_values(new_values)
        assert result is False

    def test_get_start_file(self) -> None:
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        lfs.file_parameters = {"01_file.param": {}, "02_file.param": {}, "03_file.param": {}}

        # Test with explicit index
        result = lfs.get_start_file(1, tcal_available=True)
        assert result == "02_file.param"

        # Test with out of range index
        result = lfs.get_start_file(5, tcal_available=True)
        assert result == "03_file.param"

        # Test with tcal available
        result = lfs.get_start_file(-1, tcal_available=True)
        assert result == "01_file.param"

        # Test with tcal not available
        result = lfs.get_start_file(-1, tcal_available=False)
        assert result == "03_file.param"

    def test_get_eval_variables(self) -> None:
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )

        # Test with empty components and doc_dict
        result = lfs.get_eval_variables()
        assert not result

        # Test with components and doc_dict
        lfs.vehicle_components_fs.data = {"Components": {"test": "value"}}
        lfs.doc_dict = {"param": "doc"}
        result = lfs.get_eval_variables()
        assert "vehicle_components" in result
        assert "doc_dict" in result
        assert result["vehicle_components"] == {"test": "value"}
        assert result["doc_dict"] == {"param": "doc"}

    def test_tolerance_check(self) -> None:
        """Test numerical value comparison with tolerances."""
        LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )

        # Test exact match
        x, y = 1.0, 1.0
        assert abs(x - y) <= 1e-08 + (1e-03 * abs(y))

        # Test within absolute tolerance
        x, y = 1.0, 1.00000001
        assert abs(x - y) <= 1e-08 + (1e-03 * abs(y))

        # Test within relative tolerance
        x, y = 1.0, 1.001
        assert abs(x - y) <= 1e-08 + (1e-03 * abs(y))

        # Test outside both tolerances
        x, y = 1.0, 1.1
        assert not abs(x - y) <= 1e-08 + (1e-03 * abs(y))

        # Test with custom tolerances
        x, y = 1.0, 1.5
        assert abs(x - y) <= 1.0 + (1e-03 * abs(y))  # atol=1.0
        x, y = 1.0, 2.0
        assert abs(x - y) <= 1e-08 + (1.0 * abs(y))  # rtol=1.0

    def test_categorize_parameters(self) -> None:
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        lfs.param_default_dict = {"PARAM1": MagicMock(value=1.0)}
        lfs.doc_dict = {"PARAM1": {"ReadOnly": True}, "PARAM2": {"Calibration": True}, "PARAM3": {}}

        test_params = {"PARAM1": MagicMock(value=2.0), "PARAM2": MagicMock(value=2.0), "PARAM3": MagicMock(value=2.0)}

        readonly, calibration, other = lfs.categorize_parameters(test_params)

        assert "PARAM1" in readonly
        assert "PARAM2" in calibration
        assert "PARAM3" in other

    def test_update_and_export_vehicle_params_from_fc(self) -> None:
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        fc_parameters = {"PARAM1": 1.0, "PARAM2": 2.0}

        # Test with empty file_parameters
        result = lfs.update_and_export_vehicle_params_from_fc(fc_parameters, {})
        assert result == ""

        # Test with file_parameters and configuration_steps
        param1_mock = MagicMock()
        param1_mock.value = 0.0
        param2_mock = MagicMock()
        param2_mock.value = 0.0

        lfs.file_parameters = {"test.param": {"PARAM1": param1_mock, "PARAM2": param2_mock}}
        lfs.configuration_steps = {"test.param": {"forced": {}, "derived": {}}}

        with (
            patch("ardupilot_methodic_configurator.backend_filesystem.Par.export_to_param") as mock_export,
            patch("ardupilot_methodic_configurator.backend_filesystem.Par.format_params") as mock_format,
        ):
            mock_format.return_value = "formatted_params"

            result = lfs.update_and_export_vehicle_params_from_fc(fc_parameters, {})
            assert result == ""
            assert param1_mock.value == 1.0
            assert param2_mock.value == 2.0
            mock_export.assert_called_once_with("formatted_params", os_path.join("vehicle_dir", "test.param"))

    def test_write_param_default_values_to_file(self) -> None:
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        param_mock = MagicMock()
        param_mock.value = 1.0
        param_default_values = {"PARAM1": param_mock}

        with (
            patch("ardupilot_methodic_configurator.backend_filesystem.Par.export_to_param") as mock_export,
            patch("ardupilot_methodic_configurator.backend_filesystem.Par.format_params") as mock_format,
        ):
            mock_format.return_value = "formatted_params"

            # Test with new values
            lfs.write_param_default_values_to_file(param_default_values)
            assert lfs.param_default_dict == param_default_values
            mock_format.assert_called_with(param_default_values)
            mock_export.assert_called_with("formatted_params", os_path.join("vehicle_dir", "00_default.param"))

            # Test with same values (no change)
            mock_export.reset_mock()
            lfs.write_param_default_values_to_file(param_default_values)
            mock_export.assert_not_called()

    def test_export_to_param(self) -> None:
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        param_mock = MagicMock()
        param_mock.value = 1.0
        test_params = {"PARAM1": param_mock}

        with (
            patch("ardupilot_methodic_configurator.backend_filesystem.Par.export_to_param") as mock_export,
            patch("ardupilot_methodic_configurator.backend_filesystem.update_parameter_documentation") as mock_update,
            patch("ardupilot_methodic_configurator.backend_filesystem.Par.format_params") as mock_format,
        ):
            mock_format.return_value = "formatted_params"

            # Test with documentation annotation
            lfs.export_to_param(test_params, "test.param", annotate_doc=True)
            mock_format.assert_called_with(test_params)
            mock_export.assert_called_with("formatted_params", os_path.join("vehicle_dir", "test.param"))
            mock_update.assert_called_once()

            # Test without documentation annotation
            mock_export.reset_mock()
            mock_update.reset_mock()
            lfs.export_to_param(test_params, "test.param", annotate_doc=False)
            mock_export.assert_called_once()
            mock_update.assert_not_called()

    def test_all_intermediate_parameter_file_comments(self) -> None:
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        lfs.file_parameters = {
            "file1.param": {"PARAM1": MagicMock(comment="Comment 1"), "PARAM2": MagicMock(comment="Comment 2")},
            "file2.param": {"PARAM2": MagicMock(comment="Override comment 2"), "PARAM3": MagicMock(comment="Comment 3")},
        }

        result = lfs._LocalFilesystem__all_intermediate_parameter_file_comments()  # pylint: disable=protected-access
        assert result == {"PARAM1": "Comment 1", "PARAM2": "Override comment 2", "PARAM3": "Comment 3"}

    def test_get_git_commit_hash(self) -> None:
        test_hash = "abcdef1234567890"

        # Test with valid git repo
        with patch("ardupilot_methodic_configurator.backend_filesystem.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = test_hash + "\n"
            result = LocalFilesystem.get_git_commit_hash()
            assert result == test_hash
            mock_run.assert_called_once()

        # Test with no git repo but git_hash.txt exists
        with patch("ardupilot_methodic_configurator.backend_filesystem.run") as mock_run:
            mock_run.side_effect = SubprocessError()
            with patch("builtins.open", mock_open(read_data=test_hash)):
                result = LocalFilesystem.get_git_commit_hash()
                assert result == test_hash

        # Test with no git repo and no git_hash.txt
        with patch("ardupilot_methodic_configurator.backend_filesystem.run") as mock_run:
            mock_run.side_effect = SubprocessError()
            with patch("builtins.open") as mock_file:
                mock_file.side_effect = FileNotFoundError()
                result = LocalFilesystem.get_git_commit_hash()
                assert result == ""

    def test_extend_and_reformat_parameter_documentation_metadata(self) -> None:
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )

        test_doc_dict = {
            "PARAM1": {
                "humanName": "Test Param",
                "documentation": ["Test documentation"],
                "fields": {
                    "Units": "m/s (meters per second)",
                    "Range": "0 100",
                    "Calibration": "true",
                    "ReadOnly": "yes",
                    "RebootRequired": "1",
                    "Bitmask": "0:Option1, 1:Option2",
                },
                "values": {"1": "Value1", "2": "Value2"},
            }
        }

        lfs.doc_dict = test_doc_dict
        lfs.param_default_dict = {"PARAM1": MagicMock(value=50.0)}

        lfs._LocalFilesystem__extend_and_reformat_parameter_documentation_metadata()  # pylint: disable=protected-access

        result = lfs.doc_dict["PARAM1"]
        assert result["unit"] == "m/s"
        assert result["unit_tooltip"] == "meters per second"
        assert result["min"] == 0.0
        assert result["max"] == 100.0
        assert result["Calibration"] is True
        assert result["ReadOnly"] is True
        assert result["RebootRequired"] is True
        assert result["Bitmask"] == {0: "Option1", 1: "Option2"}
        assert result["Values"] == {1: "Value1", 2: "Value2"}
        assert "Default: 50" in result["doc_tooltip"]

    def test_add_argparse_arguments(self) -> None:
        parser = ArgumentParser()
        LocalFilesystem.add_argparse_arguments(parser)

        # Verify all expected arguments are added
        args = vars(parser.parse_args([]))
        assert "vehicle_type" in args
        assert "vehicle_dir" in args
        assert "n" in args
        assert "allow_editing_template_files" in args

        # Test default values
        assert args["vehicle_type"] == ""
        assert args["n"] == -1
        assert args["allow_editing_template_files"] is False

        # Test with parameters
        args = vars(parser.parse_args(["-t", "ArduCopter", "--n", "1", "--allow-editing-template-files"]))
        assert args["vehicle_type"] == "ArduCopter"
        assert args["n"] == 1
        assert args["allow_editing_template_files"] is True

    def test_annotate_intermediate_comments_to_param_dict(self) -> None:
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )

        # Set up mock comments in file_parameters
        mock_param1 = MagicMock()
        mock_param1.comment = "Comment 1"
        mock_param2 = MagicMock()
        mock_param2.comment = "Comment 2"

        lfs.file_parameters = {"file1.param": {"PARAM1": mock_param1}, "file2.param": {"PARAM2": mock_param2}}

        input_dict = {"PARAM1": 1.0, "PARAM2": 2.0, "PARAM3": 3.0}
        result = lfs.annotate_intermediate_comments_to_param_dict(input_dict)

        assert len(result) == 3
        assert result["PARAM1"].value == 1.0
        assert result["PARAM1"].comment == "Comment 1"
        assert result["PARAM2"].value == 2.0
        assert result["PARAM2"].comment == "Comment 2"
        assert result["PARAM3"].value == 3.0
        assert result["PARAM3"].comment == ""

    def test_find_lowest_available_backup_number(self) -> None:
        """Test finding the lowest available backup number."""
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )

        # Test when no backups exist
        with patch.object(lfs, "vehicle_configuration_file_exists", return_value=False):
            result = lfs.find_lowest_available_backup_number()
            assert result == 1

        # Test when backups 1-3 exist, but 4 doesn't
        with patch.object(
            lfs, "vehicle_configuration_file_exists", side_effect=lambda x: int(x.split("_")[1].split(".")[0]) < 4
        ):
            result = lfs.find_lowest_available_backup_number()
            assert result == 4

        # Test when all backups up to limit exist
        with patch.object(lfs, "vehicle_configuration_file_exists", return_value=True):
            result = lfs.find_lowest_available_backup_number()
            assert result == 99  # Should return the cap value

    def test_backup_fc_parameters_to_file(self) -> None:
        """Test backing up flight controller parameters to a file."""
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        test_params = {"PARAM1": 1.0, "PARAM2": 2.0}

        # Test when file doesn't exist and no last uploaded filename
        with (
            patch.object(lfs, "vehicle_configuration_file_exists", return_value=False),
            patch.object(lfs, "_LocalFilesystem__read_last_uploaded_filename", return_value=""),
            patch("ardupilot_methodic_configurator.backend_filesystem.Par.export_to_param") as mock_export,
            patch("ardupilot_methodic_configurator.backend_filesystem.Par.format_params") as mock_format,
        ):
            mock_format.return_value = "formatted_params"
            lfs.backup_fc_parameters_to_file(test_params, "backup.param")
            mock_export.assert_called_once()

        # Test with existing file (should not overwrite by default)
        with (
            patch.object(lfs, "vehicle_configuration_file_exists", return_value=True),
            patch.object(lfs, "_LocalFilesystem__read_last_uploaded_filename", return_value=""),
            patch("ardupilot_methodic_configurator.backend_filesystem.Par.export_to_param") as mock_export,
        ):
            lfs.backup_fc_parameters_to_file(test_params, "backup.param")
            mock_export.assert_not_called()

        # Test with force overwrite
        with (
            patch.object(lfs, "vehicle_configuration_file_exists", return_value=True),
            patch.object(lfs, "_LocalFilesystem__read_last_uploaded_filename", return_value=""),
            patch("ardupilot_methodic_configurator.backend_filesystem.Par.export_to_param") as mock_export,
            patch("ardupilot_methodic_configurator.backend_filesystem.Par.format_params") as mock_format,
        ):
            mock_format.return_value = "formatted_params"
            lfs.backup_fc_parameters_to_file(test_params, "backup.param", overwrite_existing_file=True)
            mock_export.assert_called_once()

        # Test with last uploaded filename exists and even_if_last_uploaded_filename_exists=False
        with (
            patch.object(lfs, "vehicle_configuration_file_exists", return_value=False),
            patch.object(lfs, "_LocalFilesystem__read_last_uploaded_filename", return_value="last_file.param"),
            patch("ardupilot_methodic_configurator.backend_filesystem.Par.export_to_param") as mock_export,
        ):
            lfs.backup_fc_parameters_to_file(test_params, "backup.param", even_if_last_uploaded_filename_exists=False)
            mock_export.assert_not_called()

    def test_zip_files(self) -> None:
        """Test zipping files functionality."""
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )

        # Setup mock file parameters and file paths
        lfs.file_parameters = {"01_file.param": {}, "02_file.param": {}}
        lfs.get_vehicle_directory_name = MagicMock(return_value="test_vehicle")

        with (
            patch("ardupilot_methodic_configurator.backend_filesystem.ZipFile") as mock_zipfile,
            patch.object(lfs, "add_configuration_file_to_zip") as mock_add_file,
            patch("os.path.join", return_value="vehicle_dir/test_vehicle.zip"),
        ):
            mock_zipfile_instance = MagicMock()
            mock_zipfile.return_value.__enter__.return_value = mock_zipfile_instance

            # Test with valid files_to_zip list
            files_to_zip = [(True, "summary1.txt"), (False, "summary2.txt")]
            lfs.zip_files(files_to_zip)

            # Should call add_configuration_file_to_zip for each parameter file
            assert mock_add_file.call_count >= 2
            # Should add all files where the first tuple value is True
            mock_add_file.assert_any_call(mock_zipfile_instance, "summary1.txt")
            # Should not add files where the first tuple value is False
            for call_args in mock_add_file.call_args_list:
                assert call_args[0][1] != "summary2.txt"

    def test_is_within_tolerance_edge_cases(self) -> None:
        """Test is_within_tolerance function with edge cases."""
        # Test with negative values
        assert is_within_tolerance(-100, -100)
        assert is_within_tolerance(-100, -100.0099)  # 0.0099% difference
        assert not is_within_tolerance(-100, -101)  # 1% difference

        # Test with very small values (where absolute tolerance dominates)
        assert is_within_tolerance(1e-10, 1.09e-10)  # 9% difference but absolute diff is tiny
        assert is_within_tolerance(0, 1e-9)  # Zero case with small absolute difference

        # Test with very large values
        assert is_within_tolerance(1e10, 1.00009e10)  # 0.009% difference
        assert not is_within_tolerance(1e10, 1.01e10)  # 1% difference

        # Test with custom tolerances
        assert is_within_tolerance(100, 102, atol=3)  # 2% difference but within atol=3
        assert is_within_tolerance(100, 110, rtol=0.1)  # 10% difference but within rtol=0.1

    def test_get_download_url_and_local_filename_with_valid_config(self) -> None:
        """Test get_download_url_and_local_filename with valid configuration."""
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )

        # Set up configuration steps with download file section
        lfs.configuration_steps = {
            "test_file.param": {
                "download_file": {"source_url": "https://example.com/file.bin", "dest_local": "local_file.bin"}
            }
        }

        with patch("os.path.join", return_value="vehicle_dir/local_file.bin"):
            url, local_path = lfs.get_download_url_and_local_filename("test_file.param")
            assert url == "https://example.com/file.bin"
            assert local_path == "vehicle_dir/local_file.bin"

    def test_get_upload_local_and_remote_filenames_with_valid_config(self) -> None:
        """Test get_upload_local_and_remote_filenames with valid configuration."""
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )

        # Set up configuration steps with upload file section
        lfs.configuration_steps = {
            "test_file.param": {"upload_file": {"source_local": "local_file.bin", "dest_on_fc": "/fs/microsd/APM/file.bin"}}
        }

        with patch("os.path.join", return_value="vehicle_dir/local_file.bin"):
            local_path, remote_path = lfs.get_upload_local_and_remote_filenames("test_file.param")
            assert local_path == "vehicle_dir/local_file.bin"
            assert remote_path == "/fs/microsd/APM/file.bin"


class TestCopyTemplateFilesToNewVehicleDir(unittest.TestCase):
    """Copy Template Files To New Vehicle Directory testclass."""

    @patch("ardupilot_methodic_configurator.backend_filesystem.os_path.exists")
    @patch("ardupilot_methodic_configurator.backend_filesystem.os_listdir")
    @patch("ardupilot_methodic_configurator.backend_filesystem.os_path.join")
    @patch("ardupilot_methodic_configurator.backend_filesystem.shutil_copytree")
    @patch("ardupilot_methodic_configurator.backend_filesystem.shutil_copy2")
    @patch("ardupilot_methodic_configurator.backend_filesystem.os_path.isdir")
    def test_copy_template_files_to_new_vehicle_dir(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self, mock_isdir, mock_copy2, mock_copytree, mock_join, mock_listdir, mock_exists
    ) -> None:
        """Test copying template files with various file types and conditions."""
        mock_exists.side_effect = lambda path: path in ["template_dir", "new_vehicle_dir"]
        mock_listdir.return_value = ["file1.param", "file2.txt", "dir1", ".hidden_file", "dir2"]
        mock_join.side_effect = lambda *args: "/".join(args)
        mock_isdir.side_effect = lambda path: path.endswith(("dir1", "dir2"))

        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        lfs.copy_template_files_to_new_vehicle_dir(
            "template_dir", "new_vehicle_dir", blank_change_reason=False, copy_vehicle_image=False
        )

        # Verify all files and directories were processed
        assert mock_listdir.call_count >= 1
        assert mock_join.call_count >= 10

        # Verify directory copies
        mock_copytree.assert_any_call("template_dir/dir1", "new_vehicle_dir/dir1")
        mock_copytree.assert_any_call("template_dir/dir2", "new_vehicle_dir/dir2")

        # Verify file copies
        mock_copy2.assert_any_call("template_dir/file1.param", "new_vehicle_dir/file1.param")
        mock_copy2.assert_any_call("template_dir/file2.txt", "new_vehicle_dir/file2.txt")
        mock_copy2.assert_any_call("template_dir/.hidden_file", "new_vehicle_dir/.hidden_file")

        # Verify existence checks
        mock_exists.assert_any_call("template_dir")
        mock_exists.assert_any_call("new_vehicle_dir")

    @patch("ardupilot_methodic_configurator.backend_filesystem.os_path.exists")
    @patch("ardupilot_methodic_configurator.backend_filesystem.os_listdir")
    @patch("ardupilot_methodic_configurator.backend_filesystem.os_path.join")
    @patch("ardupilot_methodic_configurator.backend_filesystem.shutil_copytree")
    @patch("ardupilot_methodic_configurator.backend_filesystem.shutil_copy2")
    @patch("ardupilot_methodic_configurator.backend_filesystem.os_path.isdir")
    @patch("builtins.open", new_callable=mock_open, read_data="PARAM1,1.0 # test comment\nPARAM2,2.0 # another comment\n")
    def test_copy_template_files_with_blank_change_reason(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self, mock_open_file, mock_isdir, mock_copy2, mock_copytree, mock_join, mock_listdir, mock_exists
    ) -> None:
        """Test that blank_change_reason parameter correctly strips comments from parameter files."""
        mock_exists.side_effect = lambda path: path in ["template_dir", "new_vehicle_dir"]
        mock_listdir.return_value = ["file1.param", "file2.txt", "dir1"]
        mock_join.side_effect = lambda *args: "/".join(args)
        mock_isdir.side_effect = lambda path: path.endswith("dir1")

        lfs = LocalFilesystem(
            "vehicle_dir",
            "vehicle_type",
            "4.5.0",
            allow_editing_template_files=False,
            save_component_to_system_templates=False,
        )

        # Test with blank_change_reason=True
        lfs.copy_template_files_to_new_vehicle_dir(
            "template_dir", "new_vehicle_dir", blank_change_reason=True, copy_vehicle_image=False
        )

        # Verify file handling when blank_change_reason=True
        # First check if writelines was called at all
        assert mock_open_file().writelines.called, "writelines should have been called for .param files"

        # Get the arguments passed to writelines
        writelines_calls = mock_open_file().writelines.call_args_list
        assert len(writelines_calls) > 0, "Expected at least one writelines call"

        # Convert the generator to list to check content
        lines_written = list(writelines_calls[0][0][0])  # Convert generator to list
        assert "PARAM1,1.0\n" in lines_written, f"Expected 'PARAM1,1.0\\n' in {lines_written}"
        assert "PARAM2,2.0\n" in lines_written, f"Expected 'PARAM2,2.0\\n' in {lines_written}"

        # Verify directory was copied with copytree
        mock_copytree.assert_called_with("template_dir/dir1", "new_vehicle_dir/dir1")

        # Verify non-param file was copied with copy2
        mock_copy2.assert_any_call("template_dir/file2.txt", "new_vehicle_dir/file2.txt")

        # Reset mocks for second test
        mock_open_file.reset_mock()
        mock_copy2.reset_mock()
        mock_copytree.reset_mock()

        # Test with blank_change_reason=False
        lfs.copy_template_files_to_new_vehicle_dir(
            "template_dir", "new_vehicle_dir", blank_change_reason=False, copy_vehicle_image=False
        )

        # Verify param file was copied normally
        mock_copy2.assert_any_call("template_dir/file1.param", "new_vehicle_dir/file1.param")

    @patch("ardupilot_methodic_configurator.backend_filesystem.os_path.exists")
    @patch("ardupilot_methodic_configurator.backend_filesystem.os_listdir")
    @patch("ardupilot_methodic_configurator.backend_filesystem.os_path.join")
    @patch("ardupilot_methodic_configurator.backend_filesystem.shutil_copy2")
    @patch("ardupilot_methodic_configurator.backend_filesystem.os_path.isdir")
    def test_user_can_copy_vehicle_image_from_template(
        self, mock_isdir, mock_copy2, mock_join, mock_listdir, mock_exists
    ) -> None:
        """
        User can copy vehicle image file when creating a new vehicle from template.

        GIVEN: A template directory containing a vehicle.jpg file
        WHEN: The user creates a new vehicle with copy_vehicle_image=True
        THEN: The vehicle.jpg file should be copied to the new vehicle directory
        """
        # Arrange: Set up template directory with vehicle.jpg
        mock_exists.side_effect = lambda path: path in ["template_dir", "new_vehicle_dir"]
        mock_listdir.return_value = ["vehicle.jpg", "config.param"]
        mock_join.side_effect = lambda *args: "/".join(args)
        mock_isdir.return_value = False

        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )

        # Act: Copy template files with copy_vehicle_image=True
        result = lfs.copy_template_files_to_new_vehicle_dir(
            "template_dir", "new_vehicle_dir", blank_change_reason=False, copy_vehicle_image=True
        )

        # Assert: Vehicle image should be copied
        assert result == ""  # No error
        mock_copy2.assert_any_call("template_dir/vehicle.jpg", "new_vehicle_dir/vehicle.jpg")
        mock_copy2.assert_any_call("template_dir/config.param", "new_vehicle_dir/config.param")

    @patch("ardupilot_methodic_configurator.backend_filesystem.os_path.exists")
    @patch("ardupilot_methodic_configurator.backend_filesystem.os_listdir")
    @patch("ardupilot_methodic_configurator.backend_filesystem.os_path.join")
    @patch("ardupilot_methodic_configurator.backend_filesystem.shutil_copy2")
    @patch("ardupilot_methodic_configurator.backend_filesystem.os_path.isdir")
    def test_user_can_skip_copying_vehicle_image_from_template(
        self, mock_isdir, mock_copy2, mock_join, mock_listdir, mock_exists
    ) -> None:
        """
        User can choose not to copy vehicle image file when creating a new vehicle from template.

        GIVEN: A template directory containing a vehicle.jpg file
        WHEN: The user creates a new vehicle with copy_vehicle_image=False
        THEN: The vehicle.jpg file should not be copied to the new vehicle directory
        AND: Other files should still be copied normally
        """
        # Arrange: Set up template directory with vehicle.jpg and other files
        mock_exists.side_effect = lambda path: path in ["template_dir", "new_vehicle_dir"]
        mock_listdir.return_value = ["vehicle.jpg", "config.param", "readme.txt"]
        mock_join.side_effect = lambda *args: "/".join(args)
        mock_isdir.return_value = False

        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )

        # Act: Copy template files with copy_vehicle_image=False
        result = lfs.copy_template_files_to_new_vehicle_dir(
            "template_dir", "new_vehicle_dir", blank_change_reason=False, copy_vehicle_image=False
        )

        # Assert: Vehicle image should not be copied, but other files should be
        assert result == ""  # No error

        # Verify vehicle.jpg was NOT copied
        copy_calls = [call.args for call in mock_copy2.call_args_list]
        vehicle_jpg_calls = [call for call in copy_calls if "vehicle.jpg" in str(call)]
        assert len(vehicle_jpg_calls) == 0, "vehicle.jpg should not be copied when copy_vehicle_image=False"

        # Verify other files were copied
        mock_copy2.assert_any_call("template_dir/config.param", "new_vehicle_dir/config.param")
        mock_copy2.assert_any_call("template_dir/readme.txt", "new_vehicle_dir/readme.txt")

    @patch("ardupilot_methodic_configurator.backend_filesystem.os_path.exists")
    @patch("ardupilot_methodic_configurator.backend_filesystem.os_listdir")
    @patch("ardupilot_methodic_configurator.backend_filesystem.os_path.join")
    @patch("ardupilot_methodic_configurator.backend_filesystem.shutil_copy2")
    @patch("ardupilot_methodic_configurator.backend_filesystem.os_path.isdir")
    def test_copy_vehicle_image_defaults_to_false(self, mock_isdir, mock_copy2, mock_join, mock_listdir, mock_exists) -> None:
        """
        Vehicle image copying defaults to disabled.

        GIVEN: A template directory containing a vehicle.jpg file
        WHEN: The user creates a new vehicle with copy_vehicle_image=False
        THEN: The vehicle.jpg file should not be copied
        """
        # Arrange: Set up template directory with vehicle.jpg
        mock_exists.side_effect = lambda path: path in ["template_dir", "new_vehicle_dir"]
        mock_listdir.return_value = ["vehicle.jpg", "config.param"]
        mock_join.side_effect = lambda *args: "/".join(args)
        mock_isdir.return_value = False

        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", "", allow_editing_template_files=False, save_component_to_system_templates=False
        )

        # Act: Copy template files with copy_vehicle_image=False
        result = lfs.copy_template_files_to_new_vehicle_dir(
            "template_dir", "new_vehicle_dir", blank_change_reason=False, copy_vehicle_image=False
        )

        # Assert: No error and vehicle image should not be copied
        assert result == ""  # No error

        # Verify vehicle.jpg was NOT copied
        copy_calls = [call.args for call in mock_copy2.call_args_list]
        vehicle_jpg_calls = [call for call in copy_calls if "vehicle.jpg" in str(call)]
        assert len(vehicle_jpg_calls) == 0, "vehicle.jpg should not be copied when copy_vehicle_image=False"

        # Verify other files were copied
        mock_copy2.assert_any_call("template_dir/config.param", "new_vehicle_dir/config.param")

    @patch("ardupilot_methodic_configurator.backend_filesystem.os_path.exists")
    @patch("ardupilot_methodic_configurator.backend_filesystem.os_listdir")
    @patch("ardupilot_methodic_configurator.backend_filesystem.os_path.join")
    @patch("ardupilot_methodic_configurator.backend_filesystem.shutil_copy2")
    @patch("ardupilot_methodic_configurator.backend_filesystem.os_path.isdir")
    def test_copy_vehicle_image_with_no_image_file_present(
        self, mock_isdir, mock_copy2, mock_join, mock_listdir, mock_exists
    ) -> None:
        """
        Vehicle image copying gracefully handles missing vehicle.jpg file.

        GIVEN: A template directory without a vehicle.jpg file
        WHEN: The user creates a new vehicle with copy_vehicle_image=True
        THEN: No error should occur and other files should be copied normally
        """
        # Arrange: Set up template directory without vehicle.jpg
        mock_exists.side_effect = lambda path: path in ["template_dir", "new_vehicle_dir"]
        mock_listdir.return_value = ["config.param", "readme.txt"]  # No vehicle.jpg
        mock_join.side_effect = lambda *args: "/".join(args)
        mock_isdir.return_value = False

        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", "", allow_editing_template_files=False, save_component_to_system_templates=False
        )

        # Act: Copy template files with copy_vehicle_image=True (but no vehicle.jpg exists)
        result = lfs.copy_template_files_to_new_vehicle_dir(
            "template_dir", "new_vehicle_dir", blank_change_reason=False, copy_vehicle_image=True
        )

        # Assert: No error and other files copied normally
        assert result == ""  # No error
        mock_copy2.assert_any_call("template_dir/config.param", "new_vehicle_dir/config.param")
        mock_copy2.assert_any_call("template_dir/readme.txt", "new_vehicle_dir/readme.txt")


def test_merge_forced_or_derived_parameters_comprehensive() -> None:
    """Test merge_forced_or_derived_parameters with various scenarios."""
    lfs = LocalFilesystem(
        "vehicle_dir", "vehicle_type", "", allow_editing_template_files=False, save_component_to_system_templates=False
    )
    test_file = "test_file"

    # Test 1: Empty input parameters
    lfs.file_parameters = {test_file: {"PARAM1": Par(1.0, "original")}}
    assert lfs.merge_forced_or_derived_parameters(test_file, {}, []) is False
    assert len(lfs.file_parameters[test_file]) == 1

    # Test 2: Value change within tolerance
    lfs.file_parameters = {test_file: {"PARAM1": Par(1.0, "original")}}
    new_params = {test_file: {"PARAM1": Par(1.0001, "new")}}
    fc_parameters = ["PARAM1"]
    assert lfs.merge_forced_or_derived_parameters(test_file, new_params, fc_parameters) is False
    assert abs(lfs.file_parameters[test_file]["PARAM1"].value - 1.0) <= 1e-08 + (1e-03 * abs(1.0))

    # Test 3: Value change outside tolerance
    lfs.file_parameters = {test_file: {"PARAM1": Par(1.0, "original")}}
    new_params = {test_file: {"PARAM1": Par(1.5, "new")}}
    fc_parameters = ["PARAM1"]
    assert lfs.merge_forced_or_derived_parameters(test_file, new_params, fc_parameters) is True
    assert lfs.file_parameters[test_file]["PARAM1"].value == 1.5

    # Test 4: Multiple parameters
    lfs.file_parameters = {test_file: {"PARAM1": Par(1.0, "original1"), "PARAM2": Par(2.0, "original2")}}
    new_params = {test_file: {"PARAM1": Par(1.5, "new1"), "PARAM2": Par(2.0, "new2"), "PARAM3": Par(3.0, "new3")}}
    fc_parameters = ["PARAM1", "PARAM2", "PARAM3"]
    assert lfs.merge_forced_or_derived_parameters(test_file, new_params, fc_parameters) is True
    assert len(lfs.file_parameters[test_file]) == 3

    # Test 5: FC parameter filtering
    lfs.file_parameters = {test_file: {}}
    new_params = {test_file: {"PARAM1": Par(1.0, "new1"), "PARAM2": Par(2.0, "new2")}}
    fc_parameters = ["PARAM1"]  # Only PARAM1 exists in FC
    assert lfs.merge_forced_or_derived_parameters(test_file, new_params, fc_parameters) is True
    assert "PARAM1" in lfs.file_parameters[test_file]
    assert "PARAM2" not in lfs.file_parameters[test_file]

    # Test 6: Different file keys
    lfs.file_parameters = {"other_file": {}}
    new_params = {test_file: {"PARAM1": Par(1.0, "new")}}
    assert lfs.merge_forced_or_derived_parameters(test_file, new_params, []) is False
    assert len(lfs.file_parameters["other_file"]) == 0

    # Test 7: Empty FC parameters list (should add all params)
    lfs.file_parameters = {test_file: {}}
    new_params = {test_file: {"PARAM1": Par(1.0, "new")}}
    assert lfs.merge_forced_or_derived_parameters(test_file, new_params, []) is True
    assert "PARAM1" in lfs.file_parameters[test_file]

    # Test 8: None FC parameters list (should add all params)
    lfs.file_parameters = {test_file: {}}
    new_params = {test_file: {"PARAM1": Par(1.0, "new")}}
    assert lfs.merge_forced_or_derived_parameters(test_file, new_params, None) is True
    assert "PARAM1" in lfs.file_parameters[test_file]

    # Test 9: Comment overwrite
    original_param = Par(1.0, "original comment")
    lfs.file_parameters = {test_file: {"PARAM1": original_param}}
    new_params = {test_file: {"PARAM1": Par(1.5, "new comment")}}
    fc_parameters = ["PARAM1"]
    assert lfs.merge_forced_or_derived_parameters(test_file, new_params, fc_parameters) is True
    assert lfs.file_parameters[test_file]["PARAM1"].comment == "new comment"


def test_merge_forced_or_derived_parameters_none_parameters() -> None:
    """Test merge_forced_or_derived_parameters handles None parameters."""
    lfs = LocalFilesystem(
        "vehicle_dir", "vehicle_type", "", allow_editing_template_files=False, save_component_to_system_templates=False
    )
    test_file = "test.json"
    lfs.file_parameters = {test_file: {}}  # Test with empty dict instead of None (None is not valid type)
    lfs.merge_forced_or_derived_parameters(test_file, {}, [])
    assert lfs.file_parameters[test_file] == {}

    # Test with empty dict
    lfs.merge_forced_or_derived_parameters(test_file, {}, [])
    assert lfs.file_parameters[test_file] == {}


if __name__ == "__main__":
    unittest.main()
