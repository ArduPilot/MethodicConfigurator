"""
Manages program settings at the filesystem level.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

# from sys import exit as sys_exit
from contextlib import suppress as contextlib_suppress
from dataclasses import dataclass
from glob import glob as glob_glob
from importlib.resources import files as importlib_files
from json import dump as json_dump
from json import load as json_load
from logging import debug as logging_debug
from logging import error as logging_error
from os import makedirs as os_makedirs
from os import path as os_path
from os import sep as os_sep
from pathlib import Path
from platform import system as platform_system
from re import escape as re_escape
from re import match as re_match
from re import sub as re_sub
from typing import Any, Optional, Union

from platformdirs import site_config_dir, user_config_dir

from ardupilot_methodic_configurator import _


@dataclass(frozen=True)
class UsagePopupWindowDefinition:
    """Definition for a registered UsagePopupWindow."""

    description: str


USAGE_POPUP_WINDOWS: dict[str, UsagePopupWindowDefinition] = {
    # Element insertion order determines the order in which they appear in the settings and About dialogs
    "workflow_explanation": UsagePopupWindowDefinition(
        description=_("General AMC workflow"),
    ),
    "component_editor": UsagePopupWindowDefinition(
        description=_("Component editor window introduction"),
    ),
    "component_editor_validation": UsagePopupWindowDefinition(
        description=_("Component editor window data validation"),
    ),
    "parameter_editor": UsagePopupWindowDefinition(
        description=_("Parameter file editor and uploader window"),
    ),
    "bitmask_parameter_editor": UsagePopupWindowDefinition(
        description=_("Bitmask parameter editor usage window"),
    ),
    "only_changed_get_uploaded": UsagePopupWindowDefinition(
        description=_("Only changed parameters get upload explanation"),
    ),
}


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
    def _get_settings_defaults(cls) -> dict[str, Union[int, bool, str, float, dict, list]]:
        """
        Get the default settings dictionary with dynamically computed paths.

        Returns:
            dict: Default settings with all paths properly computed

        """
        # Define default settings directly - no need for deep copying
        settings_directory = cls._user_config_dir()

        return {
            "Format version": 1,
            "display_usage_popup": dict.fromkeys(USAGE_POPUP_WINDOWS, True),
            "connection_history": [],
            "directory_selection": {
                "template_dir": os_path.join(cls.get_templates_base_dir(), "ArduCopter", "empty_4.6.x"),
                "new_base_dir": os_path.join(settings_directory, "vehicles"),
                "vehicle_dir": os_path.join(settings_directory, "vehicles"),
            },
            "auto_open_doc_in_browser": True,
            "annotate_docs_into_param_files": False,
            "gui_complexity": "simple",  # simple or normal
            # Motor test settings
            "motor_test": {
                "duration": 2,  # Default test duration in seconds
                "throttle_pct": 10,  # Default throttle percentage (10%)
            },
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
        """Get the application icon path, with fallback options."""
        try:
            package_path = importlib_files("ardupilot_methodic_configurator")
        except (ImportError, FileNotFoundError):
            # Fallback: try to find icon relative to the script
            package_path = Path(os_path.dirname(os_path.abspath(__file__)))

        icon_path = str(package_path / "images" / "ArduPilot_icon.png")
        if os_path.exists(icon_path):
            return icon_path
        # If no icon found, return empty string (GUI will handle the error)
        return ""

    @staticmethod
    def application_logo_filepath() -> str:
        package_path = importlib_files("ardupilot_methodic_configurator")
        return str(package_path / "images" / "ArduPilot_logo.png")

    @staticmethod
    def workflow_image_filepath() -> str:
        package_path = importlib_files("ardupilot_methodic_configurator")
        return str(package_path / "images" / "AMC_general_workflow.png")

    @staticmethod
    def what_gets_uploaded_image_filepath() -> str:
        package_path = importlib_files("ardupilot_methodic_configurator")
        return str(package_path / "images" / "what_gets_uploaded.png")

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
        Check if a name contains only alphanumeric characters, underscores, hyphens, dots and the OS directory separator.

        This function is designed to ensure that the directory name does not contain characters that are
        invalid for directory names in many operating systems. It does not guarantee that the name
        is valid in all contexts or operating systems, as directory name validity can vary.

        Args:
          dir_name (str): The directory name to check.

        Returns:
          bool: True if the directory name matches the allowed pattern, False otherwise.

        """
        # Include os.sep and dot in the pattern
        pattern = r"^[\w" + re_escape(os_sep) + ".-]+$"
        return re_match(pattern, dir_name) is not None

    @staticmethod
    def _user_config_dir() -> str:
        user_config_directory = user_config_dir(
            ".ardupilot_methodic_configurator", appauthor=False, roaming=True, ensure_exists=False
        )

        if not os_path.exists(user_config_directory):
            os_makedirs(user_config_directory, exist_ok=True)

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
            ".ardupilot_methodic_configurator", appauthor=False, version=None, multipath=False, ensure_exists=False
        )

        if not os_path.exists(site_config_directory):
            with contextlib_suppress(OSError):
                os_makedirs(site_config_directory, exist_ok=True)

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
            with open(settings_path, encoding="utf-8-sig") as settings_file:
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
        package_path = importlib_files("ardupilot_methodic_configurator")
        logging_debug("current script directory1: %s", package_path)
        if platform_system() == "Windows":
            package_path = Path(ProgramSettings._site_config_dir())
        logging_debug("current script directory2: %s", package_path)

        logging_debug(_("site_directory: %s"), package_path)
        return str(package_path / "vehicle_templates")

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
        settings = ProgramSettings._get_settings_as_dict()
        if ptype in settings.get("display_usage_popup", {}):
            settings["display_usage_popup"][ptype] = value
            ProgramSettings._set_settings_from_dict(settings)
        else:
            logging_error(_("Usage popup type '%s' not found in settings dictionary"), ptype)

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
        Get the filepath for the motor diagram PNG file.

        Args:
            frame_class: ArduPilot frame class (1=QUAD, 2=HEXA, etc.)
            frame_type: ArduPilot frame type (0=PLUS, 1=X, etc.)

        Returns:
            str: Absolute path to the motor diagram PNG file
            str: Error message if multiple or no files found, empty string if no error

        """
        # See https://github.com/ArduPilot/ardupilot_wiki/pull/6215
        # Determine the application directory (where images are stored)
        package_path = importlib_files("ardupilot_methodic_configurator")

        images_dir = package_path / "images" / "motor_diagrams_png"

        # Generate PNG filename based on frame configuration
        filename = f"m_{frame_class:02d}_{frame_type:02d}_*.png"

        # Search for matching PNG file (since exact naming varies)
        matching_files = glob_glob(str(images_dir / filename))

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

    @staticmethod
    def get_connection_history() -> list[str]:
        """
        Get the list of previously used connection strings.

        Returns the connection history from settings, filtering out any invalid entries.
        Only valid string entries are returned.

        Returns:
            List of connection strings in most-recent-first order (up to 10 items).

        """
        settings = ProgramSettings._get_settings_as_dict()
        history = settings.get("connection_history", [])

        if not isinstance(history, list):
            return []

        return [item for item in history if isinstance(item, str)]

    @staticmethod
    def store_connection(connection_string: str) -> None:
        """
        Save a new connection string to history.

        The history maintains up to 10 most recent connections in chronological order.
        If the connection already exists, it's moved to the top of the list.
        Empty strings, whitespace-only strings, and strings longer than 200 characters
        are ignored.

        Args:
            connection_string: The connection string to store (max 200 characters).

        """
        if not connection_string or not connection_string.strip():
            return

        connection_string = connection_string.strip()

        # Reject connection strings that are too long
        if len(connection_string) > 200:
            return

        settings = ProgramSettings._get_settings_as_dict()
        history = settings.get("connection_history", [])

        if connection_string in history:
            history.remove(connection_string)

        history.insert(0, connection_string)

        if len(history) > 10:
            history = history[:10]

        settings["connection_history"] = history
        ProgramSettings._set_settings_from_dict(settings)
