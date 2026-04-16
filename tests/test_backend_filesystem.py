#!/usr/bin/env python3

"""
Tests for the backend_filesystem.py file.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tempfile
import unittest
from argparse import ArgumentParser
from os import path as os_path
from subprocess import SubprocessError
from unittest.mock import MagicMock, mock_open, patch

import pytest

from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.data_model_par_dict import Par, ParDict

# pylint: disable=too-many-lines, too-many-arguments, too-many-positional-arguments, protected-access


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
                "ardupilot_methodic_configurator.backend_filesystem.ParDict.load_param_file_into_dict",
                return_value=ParDict({"PARAM1": Par(1.0)}),
            ),
            patch("ardupilot_methodic_configurator.backend_filesystem.os_path.join", side_effect=os_path.join),
        ):
            result = filesystem.read_params_from_files()
            assert len(result) == 1
            assert "02_test.param" in result
            # Compare ParDict object - check it has the expected parameter
            assert isinstance(result["02_test.param"], ParDict)
            assert "PARAM1" in result["02_test.param"]
            assert result["02_test.param"]["PARAM1"].value == 1.0

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

        # Create mock file objects with name attribute
        mock_file1 = MagicMock()
        mock_file1.name = "vehicle_components.json"
        mock_file1.is_file.return_value = True
        mock_file2 = MagicMock()
        mock_file2.name = "02_test.param"
        mock_file2.is_file.return_value = True

        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.is_dir.return_value = True
        mock_path.iterdir.return_value = [mock_file1, mock_file2]

        with (
            patch("ardupilot_methodic_configurator.backend_filesystem.Path", return_value=mock_path),
            patch("ardupilot_methodic_configurator.backend_filesystem.platform_system", return_value="Linux"),
        ):
            assert filesystem.vehicle_configuration_files_exist(mock_vehicle_dir)

        # Test with invalid files
        mock_invalid_file = MagicMock()
        mock_invalid_file.name = "invalid.txt"
        mock_invalid_file.is_file.return_value = True

        mock_path_invalid = MagicMock()
        mock_path_invalid.exists.return_value = True
        mock_path_invalid.is_dir.return_value = True
        mock_path_invalid.iterdir.return_value = [mock_invalid_file]

        with patch("ardupilot_methodic_configurator.backend_filesystem.Path", return_value=mock_path_invalid):
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
            # Should return a non-empty error message mentioning the removed vehicle directory
            assert isinstance(ret, str)
            assert "Vehicle directory to remove does not exist" in ret
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
            mock_file.assert_called_once_with(expected_path, "w", encoding="utf-8", newline="\n")
            mock_file().write.assert_called_once_with(test_filename)

        # Test reading
        with patch("builtins.open", unittest.mock.mock_open(read_data=test_filename)) as mock_file:
            result = lfs._LocalFilesystem__read_last_uploaded_filename()  # pylint: disable=protected-access
            assert result == test_filename
            mock_file.assert_called_once_with(expected_path, encoding="utf-8")

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

    def test_get_start_file_after_final_file_skips_default(self) -> None:
        """
        After the sequence completes, restart skips 00_default.param (see #1507).

        The configuration flow records the last uploaded filename on every step.
        When the user reaches the final step (``53_everyday_use.param``) and
        relaunches the program, ``get_start_file`` should not present the
        read-only ``00_default.param`` snapshot -- that is not an editable
        configuration step.
        """
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        lfs.file_parameters = {
            "00_default.param": {},
            "01_tcal.param": {},
            "02_first_real.param": {},
            "53_everyday_use.param": {},
        }

        # tcal available -> start_file = files[0] = 00_default.param, so we must
        # move off it to the first non-default file.
        with patch.object(lfs, "_LocalFilesystem__read_last_uploaded_filename", return_value="53_everyday_use.param"):
            result = lfs.get_start_file(-1, tcal_available=True)
        assert result != "00_default.param"
        assert result == "01_tcal.param"

        # tcal NOT available -> start_file is already files[2] (first non-tcal
        # editable step), which is the correct wraparound target. The fix must
        # not clobber that by walking forward and landing on 01_tcal.param.
        with patch.object(lfs, "_LocalFilesystem__read_last_uploaded_filename", return_value="53_everyday_use.param"):
            result = lfs.get_start_file(-1, tcal_available=False)
        assert result == "02_first_real.param"

        # When 00_default.param is the only remaining entry, raise rather than
        # silently hand the user a non-editable file to edit.
        lfs.file_parameters = {"00_default.param": {}}
        with (
            patch.object(lfs, "_LocalFilesystem__read_last_uploaded_filename", return_value="00_default.param"),
            pytest.raises(ValueError, match=r"00_default\.param"),
        ):
            lfs.get_start_file(-1, tcal_available=True)

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

        test_params = ParDict({"PARAM1": Par(2.0), "PARAM2": Par(2.0), "PARAM3": Par(2.0)})

        readonly, calibration, ids, other = lfs.categorize_parameters(test_params)

        assert "PARAM1" in readonly
        assert "PARAM2" in calibration
        assert "PARAM3" in other
        assert not ids

    def test_calculate_derived_and_forced_param_changes(self) -> None:
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        # Test with empty file_parameters - returns empty dict
        result = lfs.calculate_derived_and_forced_param_changes([])
        assert not result  # Empty dict means no pending changes

        # Test with file_parameters and configuration steps:
        # Phase 1 must NOT mutate self.file_parameters
        param1 = Par(0.0, None)
        param2 = Par(0.0, None)

        # Create a ParDict instead of a regular dict
        param_dict = ParDict({"PARAM1": param1, "PARAM2": param2})
        lfs.file_parameters = {"test.param": param_dict}
        lfs.configuration_steps = {"test.param": {"forced": {}, "derived": {}}}

        lfs.derived_parameters = {"test.param": {"PARAM1": Par(1.0, None), "PARAM2": Par(2.0, None)}}
        lfs.compute_parameters = MagicMock(return_value="")
        result = lfs.calculate_derived_and_forced_param_changes([])
        # Derived values (1.0, 2.0) differ from loaded values (0.0, 0.0) so pending is non-empty
        assert result  # Non-empty dict means pending changes detected
        assert "test.param" in result
        # Original Par objects in file_parameters must be untouched
        assert param1.value == 0.0  # NOT mutated by Phase 1
        assert param2.value == 0.0  # NOT mutated by Phase 1

        # apply_computed_changes updates file_parameters
        computed = ParDict({"PARAM1": Par(1.0, None), "PARAM2": Par(2.0, None)})
        lfs.apply_computed_changes({"test.param": computed})
        assert lfs.file_parameters["test.param"] is computed

        # save_vehicle_params_to_files writes the current file_parameters to disk
        with (
            patch.object(computed, "export_to_param") as mock_export,
            patch("ardupilot_methodic_configurator.backend_filesystem.ParDict._format_params") as mock_format,
        ):
            mock_format.return_value = "formatted_params"
            lfs.save_vehicle_params_to_files(list(lfs.file_parameters))
            mock_export.assert_called_once_with(os_path.join("vehicle_dir", "test.param"))

    def test_write_param_default_values_to_file(self) -> None:
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        param_mock = MagicMock()
        param_mock.value = 1.0
        # Create a ParDict instead of a regular dict
        param_default_values = ParDict({"PARAM1": param_mock})

        with (
            patch("ardupilot_methodic_configurator.backend_filesystem.ParDict.export_to_param") as mock_export,
        ):
            # Test with new values
            lfs.write_param_default_values_to_file(param_default_values)
            assert lfs.param_default_dict == param_default_values
            mock_export.assert_called_with(os_path.join("vehicle_dir", "00_default.param"))

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
        test_params = ParDict({"PARAM1": param_mock})

        with (
            patch.object(test_params, "export_to_param") as mock_export,
            patch("ardupilot_methodic_configurator.backend_filesystem.update_parameter_documentation") as mock_update,
        ):
            # Test with documentation annotation
            lfs.export_to_param(test_params, "test.param", annotate_doc=True)
            mock_export.assert_called_with(os_path.join("vehicle_dir", "test.param"))
            mock_update.assert_called_once()

            # Test without documentation annotation
            mock_export.reset_mock()
            mock_update.reset_mock()
            lfs.export_to_param(test_params, "test.param", annotate_doc=False)
            mock_export.assert_called_with(os_path.join("vehicle_dir", "test.param"))
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
            patch("ardupilot_methodic_configurator.backend_filesystem.ParDict.export_to_param") as mock_export,
            patch("ardupilot_methodic_configurator.backend_filesystem.ParDict._format_params") as mock_format,
        ):
            mock_format.return_value = "formatted_params"
            lfs.backup_fc_parameters_to_file(test_params, "backup.param")
            mock_export.assert_called_once()

        # Test with existing file (should not overwrite by default)
        with (
            patch.object(lfs, "vehicle_configuration_file_exists", return_value=True),
            patch.object(lfs, "_LocalFilesystem__read_last_uploaded_filename", return_value=""),
            patch("ardupilot_methodic_configurator.backend_filesystem.ParDict.export_to_param") as mock_export,
        ):
            lfs.backup_fc_parameters_to_file(test_params, "backup.param")
            mock_export.assert_not_called()

        # Test with force overwrite
        with (
            patch.object(lfs, "vehicle_configuration_file_exists", return_value=True),
            patch.object(lfs, "_LocalFilesystem__read_last_uploaded_filename", return_value=""),
            patch("ardupilot_methodic_configurator.backend_filesystem.ParDict.export_to_param") as mock_export,
            patch("ardupilot_methodic_configurator.backend_filesystem.ParDict._format_params") as mock_format,
        ):
            mock_format.return_value = "formatted_params"
            lfs.backup_fc_parameters_to_file(test_params, "backup.param", overwrite_existing_file=True)
            mock_export.assert_called_once()

        # Test with last uploaded filename exists and even_if_last_uploaded_filename_exists=False
        with (
            patch.object(lfs, "vehicle_configuration_file_exists", return_value=False),
            patch.object(lfs, "_LocalFilesystem__read_last_uploaded_filename", return_value="last_file.param"),
            patch("ardupilot_methodic_configurator.backend_filesystem.ParDict.export_to_param") as mock_export,
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

    def test_get_download_url_and_local_filename_with_valid_config(self) -> None:
        """Test get_download_url_and_local_filename with valid configuration."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            lfs = LocalFilesystem(
                tmp_dir, "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
            )
            lfs.configuration_steps = {
                "test_file.param": {
                    "download_file": {"source_url": "https://example.com/file.bin", "dest_local": "local_file.bin"}
                }
            }

            url, local_path = lfs.get_download_url_and_local_filename("test_file.param")
            assert url == "https://example.com/file.bin"
            assert local_path == os_path.realpath(os_path.join(tmp_dir, "local_file.bin"))

    def test_get_upload_local_and_remote_filenames_with_valid_config(self) -> None:
        """Test get_upload_local_and_remote_filenames with valid configuration."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            lfs = LocalFilesystem(
                tmp_dir, "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
            )
            lfs.configuration_steps = {
                "test_file.param": {
                    "upload_file": {"source_local": "local_file.bin", "dest_on_fc": "/fs/microsd/APM/file.bin"}
                }
            }

            local_path, remote_path = lfs.get_upload_local_and_remote_filenames("test_file.param")
            assert local_path == os_path.realpath(os_path.join(tmp_dir, "local_file.bin"))
            assert remote_path == "/fs/microsd/APM/file.bin"


class TestPathTraversalPrevention:
    """Tests that file path operations reject path traversal attempts."""

    def test_download_rejects_path_traversal_via_dest_local(self, tmp_path) -> None:
        """
        Path traversal via dest_local is blocked.

        GIVEN: A configuration step with dest_local containing '..' components
        WHEN: get_download_url_and_local_filename is called
        THEN: A ValueError is raised to prevent writing outside vehicle_dir
        """
        lfs = LocalFilesystem(
            str(tmp_path), "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        lfs.configuration_steps = {
            "test.param": {"download_file": {"source_url": "https://example.com/payload", "dest_local": "../../.bashrc"}}
        }

        with pytest.raises(ValueError, match="Path escapes vehicle directory"):
            lfs.get_download_url_and_local_filename("test.param")

    def test_upload_rejects_path_traversal_via_source_local(self, tmp_path) -> None:
        """
        Path traversal via source_local is blocked.

        GIVEN: A configuration step with source_local containing '..' components
        WHEN: get_upload_local_and_remote_filenames is called
        THEN: A ValueError is raised to prevent reading outside vehicle_dir
        """
        lfs = LocalFilesystem(
            str(tmp_path), "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        lfs.configuration_steps = {
            "test.param": {"upload_file": {"source_local": "../../../etc/passwd", "dest_on_fc": "/fs/microsd/file"}}
        }

        with pytest.raises(ValueError, match="Path escapes vehicle directory"):
            lfs.get_upload_local_and_remote_filenames("test.param")

    def test_download_allows_valid_dest_local(self, tmp_path) -> None:
        """
        Valid dest_local paths within vehicle_dir are allowed.

        GIVEN: A configuration step with a safe dest_local filename
        WHEN: get_download_url_and_local_filename is called
        THEN: The resolved path is returned without error
        """
        lfs = LocalFilesystem(
            str(tmp_path), "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        lfs.configuration_steps = {
            "test.param": {"download_file": {"source_url": "https://example.com/file.lua", "dest_local": "script.lua"}}
        }

        url, local_path = lfs.get_download_url_and_local_filename("test.param")
        assert url == "https://example.com/file.lua"
        assert local_path == str(tmp_path / "script.lua")

    def test_download_rejects_absolute_path(self, tmp_path) -> None:
        """
        Absolute dest_local paths are blocked.

        GIVEN: A configuration step with an absolute dest_local path
        WHEN: get_download_url_and_local_filename is called
        THEN: A ValueError is raised
        """
        lfs = LocalFilesystem(
            str(tmp_path), "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        lfs.configuration_steps = {
            "test.param": {
                "download_file": {"source_url": "https://example.com/payload", "dest_local": "/tmp/evil"},  # noqa: S108
            }
        }

        with pytest.raises(ValueError, match="Path escapes vehicle directory"):
            lfs.get_download_url_and_local_filename("test.param")

    def test_download_rejects_dest_local_resolving_to_base_dir(self, tmp_path) -> None:
        """
        dest_local='.' resolves to vehicle_dir itself and is rejected.

        GIVEN: A configuration step with dest_local='.' (resolves to base directory)
        WHEN: get_download_url_and_local_filename is called
        THEN: A ValueError is raised because a directory path is not a valid file target
        """
        lfs = LocalFilesystem(
            str(tmp_path), "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        lfs.configuration_steps = {
            "test.param": {"download_file": {"source_url": "https://example.com/payload", "dest_local": "."}}
        }

        with pytest.raises(ValueError, match="Path escapes vehicle directory"):
            lfs.get_download_url_and_local_filename("test.param")

    def test_download_rejects_symlink_escape(self, tmp_path) -> None:
        """
        Symlink pointing outside vehicle_dir is blocked.

        GIVEN: A symlink inside vehicle_dir that points to an external directory
        WHEN: dest_local references a file through the symlink
        THEN: A ValueError is raised because the resolved path escapes vehicle_dir
        """
        # Create a symlink inside tmp_path pointing outside vehicle_dir
        symlink_path = tmp_path / "escape_link"
        try:
            symlink_path.symlink_to(tempfile.gettempdir())
        except OSError:
            pytest.skip("Cannot create symlinks in this environment")

        lfs = LocalFilesystem(
            str(tmp_path), "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        lfs.configuration_steps = {
            "test.param": {"download_file": {"source_url": "https://example.com/payload", "dest_local": "escape_link/evil"}}
        }

        with pytest.raises(ValueError, match="Path escapes vehicle directory"):
            lfs.get_download_url_and_local_filename("test.param")


class TestTransformParamDict:
    """Unit tests for LocalFilesystem._transform_param_dict (pure in-memory, no filesystem)."""

    def test_blank_change_reason_strips_all_comments(self) -> None:
        """
        Blank-change-reason strips every comment from the parameter dict.

        GIVEN: A ParDict where every parameter has a comment
        WHEN: _transform_param_dict is called with blank_change_reason=True
        THEN: All comments should be None in the result
        """
        params = ParDict({"PARAM1": Par(1.0, "keep me not"), "PARAM2": Par(2.0, "and me too")})
        LocalFilesystem._transform_param_dict(params, blank_change_reason=True, use_fc_params=False, fc_parameters=None)
        assert params["PARAM1"].comment is None
        assert params["PARAM2"].comment is None
        assert params["PARAM1"].value == 1.0
        assert params["PARAM2"].value == 2.0

    def test_blank_change_reason_false_preserves_comments(self) -> None:
        """
        When blank_change_reason is False comments are left untouched.

        GIVEN: A ParDict where parameters have comments
        WHEN: _transform_param_dict is called with blank_change_reason=False
        THEN: Comments should remain unchanged
        """
        params = ParDict({"PARAM1": Par(1.0, "keep me")})
        LocalFilesystem._transform_param_dict(params, blank_change_reason=False, use_fc_params=False, fc_parameters=None)
        assert params["PARAM1"].comment == "keep me"

    def test_use_fc_params_substitutes_differing_values(self) -> None:
        """
        FC values that differ beyond tolerance replace template values.

        GIVEN: A ParDict with PARAM1=1.0
        WHEN: _transform_param_dict is called with use_fc_params=True and fc_parameters={PARAM1: 42.0}
        THEN: PARAM1 value should be 42.0
        """
        params = ParDict({"PARAM1": Par(1.0, "original")})
        LocalFilesystem._transform_param_dict(
            params, blank_change_reason=False, use_fc_params=True, fc_parameters={"PARAM1": 42.0}
        )
        assert params["PARAM1"].value == 42.0
        assert params["PARAM1"].comment == "original"  # comment preserved

    def test_use_fc_params_preserves_within_tolerance_values(self) -> None:
        """
        FC values within tolerance do not replace template values.

        GIVEN: A ParDict with PARAM1=2.0
        WHEN: _transform_param_dict is called with an FC value of 2.000001 (within tolerance)
        THEN: PARAM1 value should remain 2.0
        """
        params = ParDict({"PARAM1": Par(2.0)})
        LocalFilesystem._transform_param_dict(
            params, blank_change_reason=False, use_fc_params=True, fc_parameters={"PARAM1": 2.000001}
        )
        assert params["PARAM1"].value == 2.0

    def test_use_fc_params_does_not_add_params_absent_from_template(self) -> None:
        """
        FC parameters not present in the template are not added.

        GIVEN: A ParDict with only PARAM1
        WHEN: fc_parameters also contains EXTRA_PARAM not in the dict
        THEN: EXTRA_PARAM should not appear in the result
        """
        params = ParDict({"PARAM1": Par(1.0)})
        LocalFilesystem._transform_param_dict(
            params, blank_change_reason=False, use_fc_params=True, fc_parameters={"PARAM1": 5.0, "EXTRA_PARAM": 99.0}
        )
        assert "EXTRA_PARAM" not in params
        assert params["PARAM1"].value == 5.0

    def test_use_fc_params_true_with_none_fc_parameters_leaves_dict_unchanged(self) -> None:
        """
        use_fc_params=True with fc_parameters=None leaves the dict unchanged.

        GIVEN: use_fc_params is True but fc_parameters is None
        WHEN: _transform_param_dict is called
        THEN: No values or comments should be modified
        """
        params = ParDict({"PARAM1": Par(1.0, "comment")})
        LocalFilesystem._transform_param_dict(params, blank_change_reason=False, use_fc_params=True, fc_parameters=None)
        assert params["PARAM1"].value == 1.0
        assert params["PARAM1"].comment == "comment"

    def test_both_transformations_applied_together(self) -> None:
        """
        blank_change_reason and use_fc_params can be applied together in one call.

        GIVEN: A ParDict with PARAM1=1.0 and a comment
        WHEN: _transform_param_dict is called with both blank_change_reason=True and use_fc_params=True
        THEN: The value should be replaced by the FC value AND the comment should be stripped
        """
        params = ParDict({"PARAM1": Par(1.0, "drop this")})
        LocalFilesystem._transform_param_dict(
            params, blank_change_reason=True, use_fc_params=True, fc_parameters={"PARAM1": 7.0}
        )
        assert params["PARAM1"].value == 7.0
        assert params["PARAM1"].comment is None


class TestCopyTemplateFilesToNewVehicleDir(unittest.TestCase):
    """Copy Template Files To New Vehicle Directory testclass."""

    @patch("ardupilot_methodic_configurator.backend_filesystem.os_path.exists")
    @patch("ardupilot_methodic_configurator.backend_filesystem.os_listdir")
    @patch("ardupilot_methodic_configurator.backend_filesystem.os_path.join")
    @patch("ardupilot_methodic_configurator.backend_filesystem.shutil_copytree")
    @patch("ardupilot_methodic_configurator.backend_filesystem.shutil_copy2")
    @patch("ardupilot_methodic_configurator.backend_filesystem.os_path.isdir")
    def test_user_can_copy_mixed_files_and_dirs_without_transformation(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self, mock_isdir, mock_copy2, mock_copytree, mock_join, mock_listdir, mock_exists
    ) -> None:
        """
        Files, subdirectories and hidden files are all copied correctly when no transformation is requested.

        GIVEN: A template directory with a .param file, a text file, two subdirectories and a hidden file
        WHEN: copy_template_files_to_new_vehicle_dir is called with blank_change_reason=False and use_fc_params=False
        THEN: The .param and text files should be copied with shutil_copy2
         AND: The subdirectories should be copied with shutil_copytree
         AND: The hidden file should be copied
         AND: No error string should be returned
        """
        mock_exists.side_effect = lambda path: path in ["template_dir", "new_vehicle_dir"]
        mock_listdir.return_value = ["01_file1.param", "file2.txt", "dir1", ".hidden_file", "dir2"]
        mock_join.side_effect = lambda *args: "/".join(args)
        mock_isdir.side_effect = lambda path: path.endswith(("dir1", "dir2"))

        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        result = lfs.copy_template_files_to_new_vehicle_dir(
            "template_dir", "new_vehicle_dir", blank_change_reason=False, copy_vehicle_image=False
        )

        assert result == ""

        # Verify directory copies
        mock_copytree.assert_any_call("template_dir/dir1", "new_vehicle_dir/dir1")
        mock_copytree.assert_any_call("template_dir/dir2", "new_vehicle_dir/dir2")

        # Verify file copies
        mock_copy2.assert_any_call("template_dir/01_file1.param", "new_vehicle_dir/01_file1.param")
        mock_copy2.assert_any_call("template_dir/file2.txt", "new_vehicle_dir/file2.txt")
        mock_copy2.assert_any_call("template_dir/.hidden_file", "new_vehicle_dir/.hidden_file")

    def test_user_sees_error_when_template_dir_does_not_exist(self) -> None:
        """
        An error string is returned when the template directory does not exist.

        GIVEN: A template directory path that does not exist on the filesystem
        WHEN: copy_template_files_to_new_vehicle_dir is called
        THEN: A non-empty error string should be returned describing the problem
        """
        lfs = LocalFilesystem(
            "vehicle_dir", "vehicle_type", None, allow_editing_template_files=False, save_component_to_system_templates=False
        )
        result = lfs.copy_template_files_to_new_vehicle_dir(
            "/nonexistent/template", "/some/dest", blank_change_reason=False, copy_vehicle_image=False
        )
        assert result != ""
        assert "nonexistent" in result or "exist" in result.lower()

    def test_user_sees_error_when_new_vehicle_dir_does_not_exist(self) -> None:
        """
        An error string is returned when the destination directory does not exist.

        GIVEN: A valid template directory but a destination path that does not exist
        WHEN: copy_template_files_to_new_vehicle_dir is called
        THEN: A non-empty error string should be returned describing the problem
        """
        with tempfile.TemporaryDirectory() as template_dir:
            lfs = LocalFilesystem(
                "vehicle_dir",
                "vehicle_type",
                None,
                allow_editing_template_files=False,
                save_component_to_system_templates=False,
            )
            result = lfs.copy_template_files_to_new_vehicle_dir(
                template_dir, "/nonexistent/dest", blank_change_reason=False, copy_vehicle_image=False
            )
        assert result != ""
        assert "nonexistent" in result or "exist" in result.lower()

    def test_skip_files_and_non_numbered_param_files_are_excluded(self) -> None:
        """
        Known skip-list files and non-numbered .param files are never copied.

        GIVEN: A template directory containing apm.pdef.xml, last_uploaded_filename.txt,
               tempcal_acc.png, tempcal_gyro.png and a non-numbered param file (foo.param)
        WHEN: copy_template_files_to_new_vehicle_dir is called
        THEN: None of those files should appear in the destination directory
        """
        with tempfile.TemporaryDirectory() as template_dir, tempfile.TemporaryDirectory() as new_vehicle_dir:
            skip_items = ["apm.pdef.xml", "last_uploaded_filename.txt", "tempcal_acc.png", "tempcal_gyro.png", "foo.param"]
            for name in skip_items:
                with open(os_path.join(template_dir, name), "w", encoding="utf-8") as f:
                    f.write("content")
            # Add one file that should be copied to verify the function ran
            with open(os_path.join(template_dir, "01_setup.param"), "w", encoding="utf-8") as f:
                f.write("PARAM1,1.0\n")

            lfs = LocalFilesystem(
                "vehicle_dir",
                "vehicle_type",
                None,
                allow_editing_template_files=False,
                save_component_to_system_templates=False,
            )
            result = lfs.copy_template_files_to_new_vehicle_dir(
                template_dir, new_vehicle_dir, blank_change_reason=False, copy_vehicle_image=False
            )

            assert result == ""
            for name in skip_items:
                assert not os_path.exists(os_path.join(new_vehicle_dir, name)), f"{name} should have been skipped"
            # The numbered param file must be present
            assert os_path.exists(os_path.join(new_vehicle_dir, "01_setup.param"))

    def test_copy_template_files_with_blank_change_reason(self) -> None:
        """
        Parameter file comments are stripped when blank_change_reason is True.

        GIVEN: A template .param file with comments on each line and a plain text file
        WHEN: copy_template_files_to_new_vehicle_dir is called with blank_change_reason=True
        THEN: The output .param file should contain parameters with correct values but no comments
         AND: The plain text file should be copied verbatim
        """
        with tempfile.TemporaryDirectory() as template_dir, tempfile.TemporaryDirectory() as new_vehicle_dir:
            # Create test param file with comments in the template
            param_file = os_path.join(template_dir, "01_file1.param")
            with open(param_file, "w", encoding="utf-8") as f:
                f.write("PARAM1,1.0 # test comment\nPARAM2,2.0 # another comment\n")

            # Create a non-param text file
            txt_file = os_path.join(template_dir, "file2.txt")
            with open(txt_file, "w", encoding="utf-8") as f:
                f.write("some content")

            lfs = LocalFilesystem(
                "vehicle_dir",
                "vehicle_type",
                "4.5.0",
                allow_editing_template_files=False,
                save_component_to_system_templates=False,
            )

            result = lfs.copy_template_files_to_new_vehicle_dir(
                template_dir, new_vehicle_dir, blank_change_reason=True, copy_vehicle_image=False
            )
            assert result == ""

            # Output param file must exist and contain correct values but no comments
            output_param = os_path.join(new_vehicle_dir, "01_file1.param")
            assert os_path.exists(output_param)
            with open(output_param, encoding="utf-8") as f:
                content = f.read()
            assert "# test comment" not in content, f"Comment should be stripped, got: {content!r}"
            assert "# another comment" not in content, f"Comment should be stripped, got: {content!r}"
            assert "PARAM1,1" in content, f"Expected PARAM1 value 1, got: {content!r}"
            assert "PARAM2,2" in content, f"Expected PARAM2 value 2, got: {content!r}"

            # Non-param file must be copied verbatim
            output_txt = os_path.join(new_vehicle_dir, "file2.txt")
            assert os_path.exists(output_txt)
            with open(output_txt, encoding="utf-8") as f:
                assert f.read() == "some content"

    def test_copy_template_files_with_use_fc_params(
        self,
    ) -> None:
        """
        FC parameter values replace differing template values; within-tolerance and absent params are unchanged.

        GIVEN: A template .param file with PARAM1=1.0 (comment) and PARAM2=2.0 (no comment)
        WHEN: copy_template_files_to_new_vehicle_dir is called with use_fc_params=True
          AND fc_parameters contains PARAM1=42.0 (different), PARAM2=2.000001 (within tolerance)
          AND fc_parameters also contains EXTRA_PARAM=99.0 (not in template)
        THEN: PARAM1 value should be 42 in output
         AND: PARAM1 comment should be preserved (blank_change_reason is False)
         AND: PARAM2 value should remain 2 (within tolerance)
         AND: EXTRA_PARAM should not appear in the output file
        """
        with tempfile.TemporaryDirectory() as template_dir, tempfile.TemporaryDirectory() as new_vehicle_dir:
            param_file = os_path.join(template_dir, "01_file1.param")
            with open(param_file, "w", encoding="utf-8") as f:
                f.write("PARAM1,1.0 # original comment\nPARAM2,2.0\n")

            lfs = LocalFilesystem(
                "vehicle_dir",
                "vehicle_type",
                "4.5.0",
                allow_editing_template_files=False,
                save_component_to_system_templates=False,
            )

            fc_parameters = {"PARAM1": 42.0, "PARAM2": 2.000001, "EXTRA_PARAM": 99.0}
            result = lfs.copy_template_files_to_new_vehicle_dir(
                template_dir,
                new_vehicle_dir,
                blank_change_reason=False,
                copy_vehicle_image=False,
                use_fc_params=True,
                fc_parameters=fc_parameters,
            )
            assert result == ""

            output_param = os_path.join(new_vehicle_dir, "01_file1.param")
            with open(output_param, encoding="utf-8") as f:
                content = f.read()

            assert "PARAM1,42" in content, f"Expected PARAM1 to be 42, got: {content!r}"
            assert "original comment" in content, f"Expected comment to be preserved, got: {content!r}"
            assert "PARAM2,2" in content, f"Expected PARAM2 to be present, got: {content!r}"
            # PARAM2 is within tolerance so it must not have jumped to 2.000001
            assert "PARAM2,2.000001" not in content, f"PARAM2 should stay at 2, got: {content!r}"
            assert "EXTRA_PARAM" not in content, f"EXTRA_PARAM should not be added, got: {content!r}"

    def test_copy_template_files_with_both_blank_reason_and_fc_params(self) -> None:
        """
        Both blank_change_reason and use_fc_params transformations are applied in a single pass.

        GIVEN: A template .param file with PARAM1=1.0 and a comment
        WHEN: copy_template_files_to_new_vehicle_dir is called with both blank_change_reason=True
          AND use_fc_params=True with fc_parameters containing PARAM1=7.0
        THEN: PARAM1 value should be 7 in output
         AND: The comment should be absent from the output
        """
        with tempfile.TemporaryDirectory() as template_dir, tempfile.TemporaryDirectory() as new_vehicle_dir:
            param_file = os_path.join(template_dir, "01_file1.param")
            with open(param_file, "w", encoding="utf-8") as f:
                f.write("PARAM1,1.0 # drop this comment\n")

            lfs = LocalFilesystem(
                "vehicle_dir",
                "vehicle_type",
                None,
                allow_editing_template_files=False,
                save_component_to_system_templates=False,
            )
            result = lfs.copy_template_files_to_new_vehicle_dir(
                template_dir,
                new_vehicle_dir,
                blank_change_reason=True,
                copy_vehicle_image=False,
                use_fc_params=True,
                fc_parameters={"PARAM1": 7.0},
            )
            assert result == ""

            with open(os_path.join(new_vehicle_dir, "01_file1.param"), encoding="utf-8") as f:
                content = f.read()
            assert "PARAM1,7" in content, f"Expected PARAM1=7, got: {content!r}"
            assert "drop this comment" not in content, f"Comment should be stripped, got: {content!r}"

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
        mock_listdir.return_value = ["vehicle.jpg", "01_config.param"]
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
        mock_copy2.assert_any_call("template_dir/01_config.param", "new_vehicle_dir/01_config.param")

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
        mock_listdir.return_value = ["vehicle.jpg", "01_config.param", "readme.txt"]
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
        mock_copy2.assert_any_call("template_dir/01_config.param", "new_vehicle_dir/01_config.param")
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
        mock_listdir.return_value = ["vehicle.jpg", "01_config.param"]
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
        mock_copy2.assert_any_call("template_dir/01_config.param", "new_vehicle_dir/01_config.param")

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
        mock_listdir.return_value = ["01_config.param", "readme.txt"]  # No vehicle.jpg
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
        mock_copy2.assert_any_call("template_dir/01_config.param", "new_vehicle_dir/01_config.param")
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
