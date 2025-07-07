"""
Manages program settings at the filesystem level.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

# from sys import exit as sys_exit
import glob
import sys
from json import dump as json_dump
from json import load as json_load
from logging import debug as logging_debug
from logging import error as logging_error
from os import makedirs as os_makedirs
from os import path as os_path
from os import sep as os_sep
from platform import system as platform_system
from re import escape as re_escape
from re import match as re_match
from re import sub as re_sub
from typing import Any, Optional, Union

from platformdirs import site_config_dir, user_config_dir

from ardupilot_methodic_configurator import _


class ProgramSettings:
    """
    A class responsible for managing various settings related to the ArduPilot Methodic Configurator.

    This includes handling paths for icons, logos, and directories for storing vehicle configurations,
    templates, and user preferences. It also manages the creation of new vehicle directories and
    validation of directory names according to specific rules.
    """

    def __init__(self) -> None:
        pass

    @classmethod
    def _get_settings_defaults(cls) -> dict[str, Union[int, bool, str, float, dict]]:
        """
        Get the default settings dictionary with dynamically computed paths.

        Returns:
            dict: Default settings with all paths properly computed

        """
        # Define default settings directly - no need for deep copying
        settings_directory = cls._user_config_dir()

        return {
            "Format version": 1,
            "display_usage_popup": {
                "component_editor": True,
                "parameter_editor": True,
            },
            "directory_selection": {
                "template_dir": os_path.join(cls.get_templates_base_dir(), "ArduCopter", "diatone_taycan_mxc", "4.5.x-params"),
                "new_base_dir": os_path.join(settings_directory, "vehicles"),
                "vehicle_dir": os_path.join(settings_directory, "vehicles"),
            },
            "auto_open_doc_in_browser": True,
            "annotate_docs_into_param_files": False,
            "gui_complexity": "simple",  # simple or normal
            # Motor test settings
            "motor_test_duration": 2.5,  # Default test duration in seconds
            "motor_test_throttle_pct": 10,  # Default throttle percentage (10%)
        }

    @staticmethod
    def _recursive_merge_defaults(settings: dict[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
        """
        Recursively merge default values into settings dictionary.

        This handles nested dictionaries properly and is much cleaner than manual checking.

        Args:
            settings: Existing settings dictionary
            defaults: Default values to merge in

        Returns:
            dict: Settings with all defaults applied

        """
        for key, default_value in defaults.items():
            if key not in settings:
                settings[key] = default_value
            elif isinstance(default_value, dict) and isinstance(settings[key], dict):
                # Recursively merge nested dictionaries
                settings[key] = ProgramSettings._recursive_merge_defaults(settings[key], default_value)
        return settings

    @staticmethod
    def _get_settings_as_dict() -> dict[str, Any]:
        settings_path = os_path.join(ProgramSettings._user_config_dir(), "settings.json")
        settings = ProgramSettings._load_settings_from_file(settings_path)
        # fallback to default values if settings are not defined in the json file
        return ProgramSettings._recursive_merge_defaults(settings, ProgramSettings._get_settings_defaults())

    @staticmethod
    def application_icon_filepath() -> str:
        script_dir = os_path.dirname(os_path.abspath(__file__))
        return os_path.join(script_dir, "images", "ArduPilot_icon.png")

    @staticmethod
    def application_logo_filepath() -> str:
        script_dir = os_path.dirname(os_path.abspath(__file__))
        return os_path.join(script_dir, "images", "ArduPilot_logo.png")

    @staticmethod
    def create_new_vehicle_dir(new_vehicle_dir: str) -> str:
        # Check if the new vehicle directory already exists
        if os_path.exists(new_vehicle_dir):
            return _("Directory already exists, choose a different one")
        try:
            # Create the new vehicle directory
            os_makedirs(new_vehicle_dir, exist_ok=True)
        except OSError as e:
            logging_error(_("Error creating new vehicle directory: %s"), e)
            return str(e)
        return ""

    @staticmethod
    def valid_directory_name(dir_name: str) -> bool:
        """
        Check if a name contains only alphanumeric characters, underscores, hyphens and the OS directory separator.

        This function is designed to ensure that the directory name does not contain characters that are
        invalid for directory names in many operating systems. It does not guarantee that the name
        is valid in all contexts or operating systems, as directory name validity can vary.

        Args:
          dir_name (str): The directory name to check.

        Returns:
          bool: True if the directory name matches the allowed pattern, False otherwise.

        """
        # Include os.sep in the pattern
        pattern = r"^[\w" + re_escape(os_sep) + "-]+$"
        return re_match(pattern, dir_name) is not None

    @staticmethod
    def _user_config_dir() -> str:
        user_config_directory = user_config_dir(
            ".ardupilot_methodic_configurator", appauthor=False, roaming=True, ensure_exists=True
        )

        if not os_path.exists(user_config_directory):
            error_msg = _("The user configuration directory '{user_config_directory}' does not exist.")
            raise FileNotFoundError(error_msg.format(**locals()))
        if not os_path.isdir(user_config_directory):
            error_msg = _("The path '{user_config_directory}' is not a directory.")
            raise NotADirectoryError(error_msg.format(**locals()))

        return user_config_directory

    @staticmethod
    def _site_config_dir() -> str:
        site_config_directory = site_config_dir(
            ".ardupilot_methodic_configurator", appauthor=False, version=None, multipath=False, ensure_exists=True
        )

        if not os_path.exists(site_config_directory):
            error_msg = _("The site configuration directory '{site_config_directory}' does not exist.")
            raise FileNotFoundError(error_msg.format(**locals()))
        if not os_path.isdir(site_config_directory):
            error_msg = _("The path '{site_config_directory}' is not a directory.")
            raise NotADirectoryError(error_msg.format(**locals()))

        return site_config_directory

    @staticmethod
    def _load_settings_from_file(settings_path: str) -> dict[str, Any]:
        """
        Load settings from the specified file path.

        Returns:
            dict: Loaded settings or empty dict if file doesn't exist

        """
        try:
            with open(settings_path, encoding="utf-8") as settings_file:
                loaded_settings: dict[str, Any] = json_load(settings_file)
                return loaded_settings
        except FileNotFoundError:
            # If the file does not exist, it will be created later
            return {}

    @staticmethod
    def _set_settings_from_dict(settings: dict) -> None:
        settings_path = os_path.join(ProgramSettings._user_config_dir(), "settings.json")

        with open(settings_path, "w", encoding="utf-8") as settings_file:
            json_dump(settings, settings_file, indent=4)

    @staticmethod
    def _normalize_path_separators(path: str) -> str:
        """
        Normalize path separators for the current platform.

        Args:
            path: Path to normalize

        Returns:
            str: Path with normalized separators

        """
        # Regular expression pattern to match single backslashes
        pattern = r"(?<!\\)\\(?!\\)|(?<!/)/(?!/)"
        # Replacement string
        replacement = r"\\" if platform_system() == "Windows" else r"/"
        return re_sub(pattern, replacement, path)

    @staticmethod
    def store_recently_used_template_dirs(template_dir: str, new_base_dir: str) -> None:
        settings = ProgramSettings._get_settings_as_dict()

        # Update the settings with the new values
        settings["directory_selection"].update(
            {
                "template_dir": ProgramSettings._normalize_path_separators(template_dir),
                "new_base_dir": ProgramSettings._normalize_path_separators(new_base_dir),
            }
        )

        ProgramSettings._set_settings_from_dict(settings)

    @staticmethod
    def store_template_dir(relative_template_dir: str) -> None:
        settings = ProgramSettings._get_settings_as_dict()

        template_dir = os_path.join(ProgramSettings.get_templates_base_dir(), relative_template_dir)

        # Update the settings with the new values
        settings["directory_selection"].update({"template_dir": ProgramSettings._normalize_path_separators(template_dir)})

        ProgramSettings._set_settings_from_dict(settings)

    @staticmethod
    def store_recently_used_vehicle_dir(vehicle_dir: str) -> None:
        settings = ProgramSettings._get_settings_as_dict()

        # Update the settings with the new values
        settings["directory_selection"].update({"vehicle_dir": ProgramSettings._normalize_path_separators(vehicle_dir)})

        ProgramSettings._set_settings_from_dict(settings)

    @staticmethod
    def get_templates_base_dir() -> str:
        current_script_dir = os_path.dirname(os_path.abspath(__file__))
        if platform_system() == "Windows":
            site_directory = ProgramSettings._site_config_dir()
        else:
            logging_debug("current script directory: %s", current_script_dir)
            site_directory = current_script_dir

        logging_debug(_("site_directory: %s"), site_directory)
        return os_path.join(site_directory, "vehicle_templates")

    @staticmethod
    def get_recently_used_dirs() -> tuple[str, str, str]:
        settings_directory = ProgramSettings._user_config_dir()
        vehicles_default_dir = os_path.join(settings_directory, "vehicles")
        if not os_path.exists(vehicles_default_dir):
            os_makedirs(vehicles_default_dir, exist_ok=True)

        settings = ProgramSettings._get_settings_as_dict()
        template_dir = settings["directory_selection"].get("template_dir")
        new_base_dir = settings["directory_selection"].get("new_base_dir")
        vehicle_dir = settings["directory_selection"].get("vehicle_dir")

        return template_dir, new_base_dir, vehicle_dir

    @staticmethod
    def display_usage_popup(ptype: str) -> bool:
        display_usage_popup_settings = ProgramSettings._get_settings_as_dict().get("display_usage_popup", {})
        return bool(display_usage_popup_settings.get(ptype, True))

    @staticmethod
    def set_display_usage_popup(ptype: str, value: bool) -> None:
        if ptype in {"component_editor", "parameter_editor"}:
            settings = ProgramSettings._get_settings_as_dict()
            settings["display_usage_popup"][ptype] = value
            ProgramSettings._set_settings_from_dict(settings)

    @staticmethod
    def get_setting(setting: str) -> Optional[Union[int, bool, str, float]]:
        settings = ProgramSettings._get_settings_as_dict()
        setting_parts = setting.split("/")
        for part in setting_parts:
            if part in settings:
                settings = settings[part]
            else:
                logging_error(_("Setting '%s' not found in settings dictionary"), setting)
                return None
        if isinstance(settings, (int, bool, str, float)):
            return settings
        return None

    @staticmethod
    def set_setting(setting: str, value: Union[bool, str, float]) -> None:
        settings = ProgramSettings._get_settings_as_dict()
        setting_parts = setting.split("/")

        # Handle hierarchical setting paths (e.g., "directory_selection/template_dir")
        if len(setting_parts) > 1:
            current = settings
            # Navigate to the nested dictionary, except for the last part
            for i, part in enumerate(setting_parts[:-1]):
                if part not in current or not isinstance(current[part], dict):
                    logging_error(
                        _("Cannot set nested setting '%s': parent path '%s' not found or not a dictionary"),
                        setting,
                        "/".join(setting_parts[: i + 1]),
                    )
                    return
                current = current[part]

            # Set the value at the final level
            last_part = setting_parts[-1]
            if last_part in current:
                current[last_part] = value
                ProgramSettings._set_settings_from_dict(settings)
            else:
                logging_error(_("Setting path '%s' not found in settings dictionary"), setting)
        # Handle simple (non-hierarchical) setting
        elif setting in settings:
            settings[setting] = value
            ProgramSettings._set_settings_from_dict(settings)
        else:
            logging_error(_("Setting '%s' not found in settings dictionary"), setting)

    # Motor Test Settings

    @staticmethod
    def motor_diagram_filepath(frame_class: int, frame_type: int) -> tuple[str, str]:
        """
        Get the filepath for the motor diagram SVG file.

        Args:
            frame_class: ArduPilot frame class (1=QUAD, 2=HEXA, etc.)
            frame_type: ArduPilot frame type (0=PLUS, 1=X, etc.)

        Returns:
            str: Absolute path to the motor diagram SVG file
            str: Error message if multiple or no files found, empty string if no error

        """
        # See https://github.com/ArduPilot/ardupilot_wiki/pull/6215
        # Determine the application directory (where images are stored)
        if getattr(sys, "frozen", False):
            # Running as compiled executable
            application_path = os_path.dirname(sys.executable)
        else:
            # Running as script
            application_path = os_path.dirname(os_path.dirname(os_path.abspath(__file__)))

        images_dir = os_path.join(application_path, "ardupilot_methodic_configurator", "images")

        # Generate SVG filename based on frame configuration
        filename = f"m_{frame_class:02d}_{frame_type:02d}_*.svg"

        # Search for matching SVG file (since exact naming varies)
        matching_files = glob.glob(os_path.join(images_dir, filename))

        err_msg = (
            ""
            if len(matching_files) == 1
            else _("Multiple motor diagrams found for class %d and type %d") % (frame_class, frame_type)
        )

        if matching_files:
            if err_msg:
                logging_error(err_msg)
            return matching_files[0], err_msg  # Return first match

        # If not found, return empty string
        err_msg = _("Motor diagram not found for class %d and type %d") % (frame_class, frame_type)
        logging_error(err_msg)
        return "", err_msg

    @staticmethod
    def motor_diagram_exists(frame_class: int, frame_type: int) -> bool:
        """
        Check if a motor diagram exists for the given frame configuration.

        Args:
            frame_class: ArduPilot frame class
            frame_type: ArduPilot frame type

        Returns:
            bool: True if diagram exists, False otherwise

        """
        filepath, _error_msg = ProgramSettings.motor_diagram_filepath(frame_class, frame_type)
        return filepath != "" and os_path.exists(filepath)
