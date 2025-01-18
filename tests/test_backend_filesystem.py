#!/usr/bin/env python3

"""
Tests for the backend_filesystem.py file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import unittest
from os import path as os_path
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

    def test_copy_fc_values_to_file(self) -> None:
        lfs = LocalFilesystem("vehicle_dir", "vehicle_type", None, allow_editing_template_files=False)
        test_params = {"PARAM1": 1.0, "PARAM2": 2.0}
        test_file = "test.param"

        # Test with non-existent file
        result = lfs.copy_fc_values_to_file(test_file, test_params)
        assert result == 0

        # Test with existing file and matching parameters
        lfs.file_parameters = {test_file: {"PARAM1": MagicMock(value=0.0), "PARAM2": MagicMock(value=0.0)}}
        result = lfs.copy_fc_values_to_file(test_file, test_params)
        assert result == 2
        assert lfs.file_parameters[test_file]["PARAM1"].value == 1.0
        assert lfs.file_parameters[test_file]["PARAM2"].value == 2.0

    def test_write_and_read_last_uploaded_filename(self) -> None:
        lfs = LocalFilesystem("vehicle_dir", "vehicle_type", None, allow_editing_template_files=False)
        test_filename = "test.param"

        # Test writing
        expected_path = os_path.join("vehicle_dir", "last_uploaded_filename.txt")
        with patch("builtins.open", unittest.mock.mock_open()) as mock_file:
            lfs.write_last_uploaded_filename(test_filename)
            mock_file.assert_called_once_with(expected_path, "w", encoding="utf-8")
            mock_file().write.assert_called_once_with(test_filename)

        # Test reading
        with patch("builtins.open", unittest.mock.mock_open(read_data=test_filename)) as mock_file:
            result = lfs._LocalFilesystem__read_last_uploaded_filename()
            assert result == test_filename
            mock_file.assert_called_once_with(expected_path, encoding="utf-8")

    def test_write_param_default_values(self) -> None:
        lfs = LocalFilesystem("vehicle_dir", "vehicle_type", None, allow_editing_template_files=False)

        # Test with new values
        new_values = {"PARAM1": MagicMock(value=1.0)}
        result = lfs.write_param_default_values(new_values)
        assert result is True
        assert lfs.param_default_dict == new_values

        # Test with same values (no change)
        result = lfs.write_param_default_values(new_values)
        assert result is False

    def test_get_start_file(self) -> None:
        lfs = LocalFilesystem("vehicle_dir", "vehicle_type", None, allow_editing_template_files=False)
        lfs.file_parameters = {"01_file.param": {}, "02_file.param": {}, "03_file.param": {}}

        # Test with explicit index
        result = lfs.get_start_file(1, True)  # noqa: FBT003
        assert result == "02_file.param"

        # Test with out of range index
        result = lfs.get_start_file(5, True)  # noqa: FBT003
        assert result == "03_file.param"

        # Test with tcal available
        result = lfs.get_start_file(-1, True)  # noqa: FBT003
        assert result == "01_file.param"

        # Test with tcal not available
        result = lfs.get_start_file(-1, False)  # noqa: FBT003
        assert result == "03_file.param"

    def test_get_eval_variables(self) -> None:
        lfs = LocalFilesystem("vehicle_dir", "vehicle_type", None, allow_editing_template_files=False)

        # Test with empty components and doc_dict
        result = lfs.get_eval_variables()
        assert result == {}

        # Test with components and doc_dict
        lfs.vehicle_components = {"Components": {"test": "value"}}
        lfs.doc_dict = {"param": "doc"}
        result = lfs.get_eval_variables()
        assert "vehicle_components" in result
        assert "doc_dict" in result
        assert result["vehicle_components"] == {"test": "value"}
        assert result["doc_dict"] == {"param": "doc"}

    def test_tolerance_check(self) -> None:
        """Test numerical value comparison with tolerances."""
        LocalFilesystem("vehicle_dir", "vehicle_type", None, allow_editing_template_files=False)

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
        lfs = LocalFilesystem("vehicle_dir", "vehicle_type", None, allow_editing_template_files=False)
        lfs.param_default_dict = {"PARAM1": MagicMock(value=1.0)}
        lfs.doc_dict = {"PARAM1": {"ReadOnly": True}, "PARAM2": {"Calibration": True}, "PARAM3": {}}

        test_params = {"PARAM1": MagicMock(value=2.0), "PARAM2": MagicMock(value=2.0), "PARAM3": MagicMock(value=2.0)}

        readonly, calibration, other = lfs.categorize_parameters(test_params)

        assert "PARAM1" in readonly
        assert "PARAM2" in calibration
        assert "PARAM3" in other

    def test_copy_fc_params_values_to_template_created_vehicle_files(self) -> None:
        lfs = LocalFilesystem("vehicle_dir", "vehicle_type", None, allow_editing_template_files=False)
        fc_parameters = {"PARAM1": 1.0, "PARAM2": 2.0}

        # Test with empty file_parameters
        result = lfs.copy_fc_params_values_to_template_created_vehicle_files(fc_parameters)
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

            result = lfs.copy_fc_params_values_to_template_created_vehicle_files(fc_parameters)
            assert result == ""
            assert param1_mock.value == 1.0
            assert param2_mock.value == 2.0
            mock_export.assert_called_once_with("formatted_params", os_path.join("vehicle_dir", "test.param"))

    def test_write_param_default_values_to_file(self) -> None:
        lfs = LocalFilesystem("vehicle_dir", "vehicle_type", None, allow_editing_template_files=False)
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
        lfs = LocalFilesystem("vehicle_dir", "vehicle_type", None, allow_editing_template_files=False)
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
            lfs.export_to_param(test_params, "test.param", True)  # noqa: FBT003
            mock_format.assert_called_with(test_params)
            mock_export.assert_called_with("formatted_params", os_path.join("vehicle_dir", "test.param"))
            mock_update.assert_called_once()

            # Test without documentation annotation
            mock_export.reset_mock()
            mock_update.reset_mock()
            lfs.export_to_param(test_params, "test.param", False)  # noqa: FBT003
            mock_export.assert_called_once()
            mock_update.assert_not_called()

    def test_all_intermediate_parameter_file_comments(self) -> None:
        lfs = LocalFilesystem("vehicle_dir", "vehicle_type", None, allow_editing_template_files=False)
        lfs.file_parameters = {
            "file1.param": {"PARAM1": MagicMock(comment="Comment 1"), "PARAM2": MagicMock(comment="Comment 2")},
            "file2.param": {"PARAM2": MagicMock(comment="Override comment 2"), "PARAM3": MagicMock(comment="Comment 3")},
        }

        result = lfs._LocalFilesystem__all_intermediate_parameter_file_comments()
        assert result == {"PARAM1": "Comment 1", "PARAM2": "Override comment 2", "PARAM3": "Comment 3"}


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
