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

from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem


class TestLocalFilesystem(unittest.TestCase):  # pylint: disable=too-many-public-methods
    """LocalFilesystem test class."""

    def test_read_params_from_files(self) -> None:
        """Test reading parameters from files with proper filtering."""
        mock_vehicle_dir = "/mock/dir"
        filesystem = LocalFilesystem(mock_vehicle_dir, "ArduCopter", "4.3.0", allow_editing_template_files=False)

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
        lfs = LocalFilesystem("vehicle_dir", "vehicle_type", None, allow_editing_template_files=False)
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
        filesystem = LocalFilesystem(mock_vehicle_dir, "ArduCopter", "4.3.0", allow_editing_template_files=False)

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
        filesystem = LocalFilesystem(mock_vehicle_dir, "ArduCopter", "4.3.0", allow_editing_template_files=False)

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

    def test_rename_parameter_files(self) -> None:
        """Test renaming parameter files."""
        mock_vehicle_dir = "/mock/dir"
        filesystem = LocalFilesystem(mock_vehicle_dir, "ArduCopter", "4.3.0", allow_editing_template_files=False)
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
        filesystem = LocalFilesystem(mock_vehicle_dir, "ArduCopter", "4.3.0", allow_editing_template_files=False)

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

    def test_getcwd(self) -> None:
        """Test getting current working directory."""
        mock_vehicle_dir = "/mock/dir"
        mock_cwd = "/test/dir"
        filesystem = LocalFilesystem(mock_vehicle_dir, "ArduCopter", "4.3.0", allow_editing_template_files=False)

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

    def test_get_upload_local_and_remote_filenames_missing_file(self) -> None:
        """Test get_upload_local_and_remote_filenames with missing file."""
        lfs = LocalFilesystem("vehicle_dir", "vehicle_type", None, allow_editing_template_files=False)
        result = lfs.get_upload_local_and_remote_filenames("missing_file")
        assert result == ("", "")

    def test_get_upload_local_and_remote_filenames_missing_upload_section(self) -> None:
        """Test get_upload_local_and_remote_filenames with missing upload section."""
        lfs = LocalFilesystem("vehicle_dir", "vehicle_type", None, allow_editing_template_files=False)
        lfs.configuration_steps = {"selected_file": {}}
        result = lfs.get_upload_local_and_remote_filenames("selected_file")
        assert result == ("", "")

    def test_get_download_url_and_local_filename_missing_file(self) -> None:
        """Test get_download_url_and_local_filename with missing file."""
        lfs = LocalFilesystem("vehicle_dir", "vehicle_type", None, allow_editing_template_files=False)
        result = lfs.get_download_url_and_local_filename("missing_file")
        assert result == ("", "")

    def test_get_download_url_and_local_filename_missing_download_section(self) -> None:
        """Test get_download_url_and_local_filename with missing download section."""
        lfs = LocalFilesystem("vehicle_dir", "vehicle_type", None, allow_editing_template_files=False)
        lfs.configuration_steps = {"selected_file": {}}
        result = lfs.get_download_url_and_local_filename("selected_file")
        assert result == ("", "")

    def test_write_and_read_last_uploaded_filename_error_handling(self) -> None:
        """Test error handling in write_and_read_last_uploaded_filename."""
        lfs = LocalFilesystem("vehicle_dir", "vehicle_type", None, allow_editing_template_files=False)
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
        lfs = LocalFilesystem("vehicle_dir", "vehicle_type", None, allow_editing_template_files=False)
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
        lfs = LocalFilesystem("vehicle_dir", "vehicle_type", None, allow_editing_template_files=False)
        lfs.file_parameters = {}
        result = lfs.get_start_file(1, tcal_available=True)
        assert result == ""

    def test_get_eval_variables_with_none(self) -> None:
        """Test get_eval_variables with None values."""
        lfs = LocalFilesystem("vehicle_dir", "vehicle_type", None, allow_editing_template_files=False)
        lfs.vehicle_components = None
        lfs.doc_dict = None
        result = lfs.get_eval_variables()
        assert not result

    def test_tolerance_check_with_zero_values(self) -> None:
        """Test numerical value comparison with zero values."""
        lfs = LocalFilesystem("vehicle_dir", "vehicle_type", None, allow_editing_template_files=False)

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
        from ardupilot_methodic_configurator.backend_filesystem import (  # pylint: disable=import-outside-toplevel
            is_within_tolerance,
        )

        # Test cases within tolerance (default 0.1%)
        assert is_within_tolerance(10.0, 10.009)  # +0.09% - should pass
        assert is_within_tolerance(10.0, 9.991)  # -0.09% - should pass
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
        lfs = LocalFilesystem("vehicle_dir", "vehicle_type", None, allow_editing_template_files=False)

        # Test with empty components and doc_dict
        result = lfs.get_eval_variables()
        assert not result

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
        lfs = LocalFilesystem("vehicle_dir", "vehicle_type", None, allow_editing_template_files=False)
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
        lfs = LocalFilesystem("vehicle_dir", "vehicle_type", None, allow_editing_template_files=False)

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
        lfs = LocalFilesystem("vehicle_dir", "vehicle_type", None, allow_editing_template_files=False)

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

        lfs = LocalFilesystem("vehicle_dir", "vehicle_type", None, allow_editing_template_files=False)
        lfs.copy_template_files_to_new_vehicle_dir("template_dir", "new_vehicle_dir")

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


if __name__ == "__main__":
    unittest.main()
