#!/usr/bin/env python3

"""
Tests for the backend_filesystem.py file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import unittest
from unittest.mock import MagicMock, patch

from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem


class TestLocalFilesystem(unittest.TestCase):
    """LocalFilesystem test class."""

    @patch("os.path.isdir")
    @patch("os.listdir")
    def test_read_params_from_files(self, mock_listdir, mock_isdir) -> None:
        return
        # Setup
        mock_isdir.return_value = True  # pylint: disable=unreachable
        mock_listdir.return_value = ["00_default.param", "01_ignore_readonly.param", "02_test.param"]
        mock_load_param_file_into_dict = MagicMock()
        mock_load_param_file_into_dict.return_value = {"TEST_PARAM": "value"}
        # pylint: disable=invalid-name
        Par = MagicMock()  # noqa: N806
        # pylint: enable=invalid-name
        Par.load_param_file_into_dict = mock_load_param_file_into_dict

        # Call the method under test
        lfs = LocalFilesystem("vehicle_dir", "vehicle_type", None, allow_editing_template_files=False)
        result = lfs.read_params_from_files()

        # Assertions
        assert result == {"02_test.param": {"TEST_PARAM": "value"}}
        mock_isdir.assert_called_once_with("vehicle_dir")
        mock_listdir.assert_called_once_with("vehicle_dir")
        mock_load_param_file_into_dict.assert_called_once_with("vehicle_dir/02_test.param")
        assert "00_default.param" not in result
        assert "01_ignore_readonly.param" not in result

    def test_str_to_bool(self) -> None:
        lfs = LocalFilesystem("vehicle_dir", "vehicle_type", None, allow_editing_template_files=False)
        assert lfs.str_to_bool("true")
        assert lfs.str_to_bool("yes")
        assert lfs.str_to_bool("1")
        assert not lfs.str_to_bool("false")
        assert not lfs.str_to_bool("no")
        assert not lfs.str_to_bool("0")
        assert lfs.str_to_bool("maybe") is None

    @patch("os.path.isdir")
    @patch("os.listdir")
    @patch("ardupilot_methodic_configurator.backend_filesystem.LocalFilesystem.read_params_from_files")
    @patch("ardupilot_methodic_configurator.backend_filesystem.VehicleComponents.load_vehicle_components_json_data")
    def test_re_init(
        self, mock_load_vehicle_components_json_data, mock_read_params_from_files, mock_listdir, mock_isdir
    ) -> None:
        return
        mock_isdir.return_value = True  # pylint: disable=unreachable
        mock_listdir.return_value = ["00_default.param", "01_ignore_readonly.param", "02_test.param"]
        mock_read_params_from_files.return_value = {"02_test.param": {"TEST_PARAM": "value"}}
        mock_load_vehicle_components_json_data.return_value = True

        lfs = LocalFilesystem("vehicle_dir", "Heli", None, allow_editing_template_files=False)
        lfs.re_init("new_vehicle_dir", "Rover")

        assert lfs.vehicle_dir == "new_vehicle_dir"
        assert lfs.vehicle_type == "Rover"
        mock_isdir.assert_called_once_with("new_vehicle_dir")
        mock_listdir.assert_called_once_with("new_vehicle_dir")
        mock_read_params_from_files.assert_called_once()
        mock_load_vehicle_components_json_data.assert_called_once()
        assert lfs.file_parameters == {"02_test.param": {"TEST_PARAM": "value"}}

    @patch("os.path.exists")
    @patch("os.path.isdir")
    def test_vehicle_configuration_files_exist(self, mock_isdir, mock_exists) -> None:
        return
        mock_isdir.return_value = True  # pylint: disable=unreachable
        mock_exists.return_value = True
        lfs = LocalFilesystem("vehicle_dir", "vehicle_type", None, allow_editing_template_files=False)
        result = lfs.vehicle_configuration_files_exist("vehicle_dir")
        assert result
        mock_isdir.assert_called_once_with("vehicle_dir")
        mock_exists.assert_called_once_with("vehicle_dir")

    @patch("os.rename")
    @patch("os.path.exists")
    def test_rename_parameter_files(self, mock_exists, mock_rename) -> None:
        return
        mock_exists.side_effect = [True, False]  # pylint: disable=unreachable
        lfs = LocalFilesystem("vehicle_dir", "vehicle_type", None, allow_editing_template_files=False)
        lfs.configuration_steps = {"new_file.param": {"old_filenames": ["old_file.param"]}}
        lfs.vehicle_dir = "vehicle_dir"
        lfs.rename_parameter_files()
        mock_exists.assert_any_call("vehicle_dir/old_file.param")
        mock_exists.assert_any_call("vehicle_dir/new_file.param")
        mock_rename.assert_called_once_with("vehicle_dir/old_file.param", "vehicle_dir/new_file.param")

    @patch("os.path.exists")
    @patch("os.path.isfile")
    def test_vehicle_configuration_file_exists(self, mock_isfile, mock_exists) -> None:
        return
        mock_exists.return_value = True  # pylint: disable=unreachable
        mock_isfile.return_value = True
        lfs = LocalFilesystem("vehicle_dir", "vehicle_type", None, allow_editing_template_files=False)
        result = lfs.vehicle_configuration_file_exists("test_file.param")
        assert result
        mock_exists.assert_called_once_with("vehicle_dir/test_file.param")
        mock_isfile.assert_called_once_with("vehicle_dir/test_file.param")

    @patch("os.path.exists")
    @patch("os.path.isfile")
    def test_zip_file_exists(self, mock_isfile, mock_exists) -> None:
        mock_exists.return_value = True
        mock_isfile.return_value = True
        lfs = LocalFilesystem("vehicle_dir", "vehicle_type", None, allow_editing_template_files=False)
        result = lfs.zip_file_exists()
        assert result
        mock_exists.assert_called_once()
        mock_isfile.assert_called_once()

    @patch("os.path.exists")
    @patch("os.path.isfile")
    def test_vehicle_image_exists(self, mock_isfile, mock_exists) -> None:
        mock_exists.return_value = True
        mock_isfile.return_value = True
        lfs = LocalFilesystem("vehicle_dir", "vehicle_type", None, allow_editing_template_files=False)
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

    @patch("os.getcwd")
    def test_getcwd(self, mock_getcwd) -> None:
        return
        mock_getcwd.return_value = "current_directory"  # pylint: disable=unreachable
        result = LocalFilesystem.getcwd()
        assert result == "current_directory"
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
        lfs = LocalFilesystem("vehicle_dir", "vehicle_type", None, allow_editing_template_files=False)
        with patch("os.path.join") as mock_join:
            mock_join.return_value = "vehicle_dir/vehicle.jpg"
            result = lfs.vehicle_image_filepath()
            assert result == "vehicle_dir/vehicle.jpg"
            mock_join.assert_called_once_with("vehicle_dir", "vehicle.jpg")

    def test_tempcal_imu_result_param_tuple(self) -> None:
        lfs = LocalFilesystem("vehicle_dir", "vehicle_type", None, allow_editing_template_files=False)
        with patch("os.path.join") as mock_join:
            mock_join.return_value = "vehicle_dir/03_imu_temperature_calibration_results.param"
            result = lfs.tempcal_imu_result_param_tuple()
            assert result == (
                "03_imu_temperature_calibration_results.param",
                "vehicle_dir/03_imu_temperature_calibration_results.param",
            )
            mock_join.assert_called_once_with("vehicle_dir", "03_imu_temperature_calibration_results.param")

    def test_zip_file_path(self) -> None:
        lfs = LocalFilesystem("vehicle_dir", "vehicle_type", None, allow_editing_template_files=False)
        with patch("os.path.join") as mock_join:
            mock_join.return_value = "vehicle_dir/vehicle_name.zip"
            lfs.get_vehicle_directory_name = MagicMock(return_value="vehicle_name")
            result = lfs.zip_file_path()
            assert result == "vehicle_dir/vehicle_name.zip"
            mock_join.assert_called_once_with("vehicle_dir", "vehicle_name.zip")

    def test_add_configuration_file_to_zip(self) -> None:
        lfs = LocalFilesystem("vehicle_dir", "vehicle_type", None, allow_editing_template_files=False)
        with patch("os.path.join") as mock_join:
            mock_join.return_value = "vehicle_dir/test_file.param"
            lfs.vehicle_configuration_file_exists = MagicMock(return_value=True)
            mock_zipfile = MagicMock()
            lfs.add_configuration_file_to_zip(mock_zipfile, "test_file.param")
            mock_join.assert_called_once_with("vehicle_dir", "test_file.param")
            mock_zipfile.write.assert_called_once_with("vehicle_dir/test_file.param", arcname="test_file.param")

    @patch("requests.get")
    def test_download_file_from_url(self, mock_get) -> None:
        return
        mock_response = MagicMock()  # pylint: disable=unreachable
        mock_response.status_code = 200
        mock_response.content = b"file_content"
        mock_get.return_value = mock_response
        with patch("builtins.open", unittest.mock.mock_open()) as mock_file:
            result = LocalFilesystem.download_file_from_url("http://example.com/file", "local_file")
            assert result
            mock_get.assert_called_once_with("http://example.com/file", timeout=5)
            mock_file.assert_called_once_with("local_file", "wb")
            mock_file().write.assert_called_once_with(b"file_content")

    def test_get_download_url_and_local_filename(self) -> None:
        lfs = LocalFilesystem("vehicle_dir", "vehicle_type", None, allow_editing_template_files=False)
        with patch("os.path.join") as mock_join:
            mock_join.return_value = "vehicle_dir/dest_local"
            lfs.configuration_steps = {
                "selected_file": {"download_file": {"source_url": "http://example.com/file", "dest_local": "dest_local"}}
            }
            result = lfs.get_download_url_and_local_filename("selected_file")
            assert result == ("http://example.com/file", "vehicle_dir/dest_local")
            mock_join.assert_called_once_with("vehicle_dir", "dest_local")

    def test_get_upload_local_and_remote_filenames(self) -> None:
        lfs = LocalFilesystem("vehicle_dir", "vehicle_type", None, allow_editing_template_files=False)
        with patch("os.path.join") as mock_join:
            mock_join.return_value = "vehicle_dir/source_local"
            lfs.configuration_steps = {
                "selected_file": {"upload_file": {"source_local": "source_local", "dest_on_fc": "dest_on_fc"}}
            }
            result = lfs.get_upload_local_and_remote_filenames("selected_file")
            assert result == ("vehicle_dir/source_local", "dest_on_fc")
            mock_join.assert_called_once_with("vehicle_dir", "source_local")


class TestCopyTemplateFilesToNewVehicleDir(unittest.TestCase):
    """Copy Template Files To New Vehicle Directory testclass."""

    @patch("os.path.exists")
    @patch("os.listdir")
    @patch("os.path.join")
    @patch("shutil.copytree")
    @patch("shutil.copy2")
    def test_copy_template_files_to_new_vehicle_dir(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self, mock_copy2, mock_copytree, mock_join, mock_listdir, mock_exists
    ) -> None:
        return
        # Ensure the mock for os.path.exists returns True for both template_dir and new_vehicle_dir
        mock_exists.side_effect = lambda path: path in ["template_dir", "new_vehicle_dir"]  # pylint: disable=unreachable
        # Ensure the mock for os.listdir returns the expected items
        mock_listdir.return_value = ["file1", "dir1"]
        # Simulate os.path.join behavior to ensure paths are constructed as expected
        mock_join.side_effect = lambda *args: "/".join(args)

        # Initialize LocalFilesystem
        lfs = LocalFilesystem("vehicle_dir", "vehicle_type", None, allow_editing_template_files=False)

        # Call the method under test
        lfs.copy_template_files_to_new_vehicle_dir("template_dir", "new_vehicle_dir")

        # Assertions to verify the mocks were called as expected
        mock_listdir.assert_called_once_with("template_dir")
        mock_join.assert_any_call("template_dir", "file1")
        mock_join.assert_any_call("template_dir", "dir1")
        mock_join.assert_any_call("new_vehicle_dir", "file1")
        mock_join.assert_any_call("new_vehicle_dir", "dir1")
        mock_copy2.assert_called_once_with("template_dir/file1", "new_vehicle_dir/file1")
        mock_copytree.assert_called_once_with("template_dir/dir1", "new_vehicle_dir/dir1")
        assert mock_exists.call_count == 2


if __name__ == "__main__":
    unittest.main()
