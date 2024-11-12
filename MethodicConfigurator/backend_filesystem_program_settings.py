#!/usr/bin/env python3

"""
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from json import dump as json_dump
from json import load as json_load

# from sys import exit as sys_exit
from logging import debug as logging_debug
from logging import error as logging_error
from os import makedirs as os_makedirs
from os import path as os_path
from os import sep as os_sep
from platform import system as platform_system
from re import escape as re_escape
from re import match as re_match
from re import sub as re_sub

from platformdirs import site_config_dir, user_config_dir

from MethodicConfigurator import _


class ProgramSettings:
    """
    A class responsible for managing various settings related to the ArduPilot Methodic Configurator.

    This includes handling paths for icons, logos, and directories for storing vehicle configurations,
    templates, and user preferences. It also manages the creation of new vehicle directories and
    validation of directory names according to specific rules.
    """

    def __init__(self):
        pass

    @staticmethod
    def application_icon_filepath():
        script_dir = os_path.dirname(os_path.abspath(__file__))
        return os_path.join(script_dir, "ArduPilot_icon.png")

    @staticmethod
    def application_logo_filepath():
        script_dir = os_path.dirname(os_path.abspath(__file__))
        return os_path.join(script_dir, "ArduPilot_logo.png")

    @staticmethod
    def create_new_vehicle_dir(new_vehicle_dir: str):
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
    def valid_directory_name(dir_name: str):
        """
        Check if a given directory name contains only alphanumeric characters, underscores, hyphens,
        and the OS directory separator.

        This function is designed to ensure that the directory name does not contain characters that are
        invalid for directory names in many operating systems. It does not guarantee that the name
        is valid in all contexts or operating systems, as directory name validity can vary.

        Parameters:
        - dir_name (str): The directory name to check.

        Returns:
        - bool: True if the directory name matches the allowed pattern, False otherwise.
        """
        # Include os.sep in the pattern
        pattern = r"^[\w" + re_escape(os_sep) + "-]+$"
        return re_match(pattern, dir_name) is not None

    @staticmethod
    def __user_config_dir():
        user_config_directory = user_config_dir(".ardupilot_methodic_configurator", False, roaming=True, ensure_exists=True)

        if not os_path.exists(user_config_directory):
            error_msg = _("The user configuration directory '{user_config_directory}' does not exist.")
            raise FileNotFoundError(error_msg.format(**locals()))
        if not os_path.isdir(user_config_directory):
            error_msg = _("The path '{user_config_directory}' is not a directory.")
            raise NotADirectoryError(error_msg.format(**locals()))

        return user_config_directory

    @staticmethod
    def __site_config_dir():
        site_config_directory = site_config_dir(
            ".ardupilot_methodic_configurator", False, version=None, multipath=False, ensure_exists=True
        )

        if not os_path.exists(site_config_directory):
            error_msg = _("The site configuration directory '{site_config_directory}' does not exist.")
            raise FileNotFoundError(error_msg.format(**locals()))
        if not os_path.isdir(site_config_directory):
            error_msg = _("The path '{site_config_directory}' is not a directory.")
            raise NotADirectoryError(error_msg.format(**locals()))

        return site_config_directory

    @staticmethod
    def __get_settings_as_dict():
        settings_path = os_path.join(ProgramSettings.__user_config_dir(), "settings.json")

        settings = {}

        try:
            with open(settings_path, encoding="utf-8") as settings_file:
                settings = json_load(settings_file)
        except FileNotFoundError:
            # If the file does not exist, it will be created later
            pass

        if "Format version" not in settings:
            settings["Format version"] = 1

        if "directory_selection" not in settings:
            settings["directory_selection"] = {}

        if "display_usage_popup" not in settings:
            settings["display_usage_popup"] = {}
        if "component_editor" not in settings["display_usage_popup"]:
            settings["display_usage_popup"]["component_editor"] = True
        if "parameter_editor" not in settings["display_usage_popup"]:
            settings["display_usage_popup"]["parameter_editor"] = True

        return settings

    @staticmethod
    def __set_settings_from_dict(settings):
        settings_path = os_path.join(ProgramSettings.__user_config_dir(), "settings.json")

        with open(settings_path, "w", encoding="utf-8") as settings_file:
            json_dump(settings, settings_file, indent=4)

    @staticmethod
    def __get_settings_config():
        settings = ProgramSettings.__get_settings_as_dict()

        # Regular expression pattern to match single backslashes
        pattern = r"(?<!\\)\\(?!\\)|(?<!/)/(?!/)"

        # Replacement string
        replacement = r"\\" if platform_system() == "Windows" else r"/"
        return settings, pattern, replacement

    @staticmethod
    def store_recently_used_template_dirs(template_dir: str, new_base_dir: str):
        settings, pattern, replacement = ProgramSettings.__get_settings_config()

        # Update the settings with the new values
        settings["directory_selection"].update(
            {
                "template_dir": re_sub(pattern, replacement, template_dir),
                "new_base_dir": re_sub(pattern, replacement, new_base_dir),
            }
        )

        ProgramSettings.__set_settings_from_dict(settings)

    @staticmethod
    def store_template_dir(relative_template_dir: str):
        settings, pattern, replacement = ProgramSettings.__get_settings_config()

        template_dir = os_path.join(ProgramSettings.get_templates_base_dir(), relative_template_dir)

        # Update the settings with the new values
        settings["directory_selection"].update({"template_dir": re_sub(pattern, replacement, template_dir)})

        ProgramSettings.__set_settings_from_dict(settings)

    @staticmethod
    def store_recently_used_vehicle_dir(vehicle_dir: str):
        settings, pattern, replacement = ProgramSettings.__get_settings_config()

        # Update the settings with the new values
        settings["directory_selection"].update({"vehicle_dir": re_sub(pattern, replacement, vehicle_dir)})

        ProgramSettings.__set_settings_from_dict(settings)

    @staticmethod
    def get_templates_base_dir():
        current_dir = os_path.dirname(os_path.abspath(__file__))
        if platform_system() == "Windows":
            site_directory = ProgramSettings.__site_config_dir()
        else:
            site_directory = current_dir
            if "site-packages" in site_directory:
                site_directory = os_path.join(os_path.expanduser("~"), ".local", "MethodicConfigurator")
            elif "dist-packages" in site_directory:
                site_directory = os_path.join("/usr", "local", "MethodicConfigurator")
            else:
                site_directory = site_directory.replace("/MethodicConfigurator", "")

        logging_debug(_("site_directory: %s"), site_directory)
        return os_path.join(site_directory, "vehicle_templates")

    @staticmethod
    def get_recently_used_dirs():
        template_default_dir = os_path.join(
            ProgramSettings.get_templates_base_dir(), "ArduCopter", "diatone_taycan_mxc", "4.5.x-params"
        )

        settings_directory = ProgramSettings.__user_config_dir()
        vehicles_default_dir = os_path.join(settings_directory, "vehicles")
        if not os_path.exists(vehicles_default_dir):
            os_makedirs(vehicles_default_dir, exist_ok=True)

        settings = ProgramSettings.__get_settings_as_dict()
        template_dir = settings["directory_selection"].get("template_dir", template_default_dir)
        new_base_dir = settings["directory_selection"].get("new_base_dir", vehicles_default_dir)
        vehicle_dir = settings["directory_selection"].get("vehicle_dir", vehicles_default_dir)

        return template_dir, new_base_dir, vehicle_dir

    @staticmethod
    def display_usage_popup(ptype: str):
        return ProgramSettings.__get_settings_as_dict()["display_usage_popup"].get(ptype, True)

    @staticmethod
    def set_display_usage_popup(ptype: str, value: bool):
        if ptype in {"component_editor", "parameter_editor"}:
            settings, _, _ = ProgramSettings.__get_settings_config()
            settings["display_usage_popup"][ptype] = value
            ProgramSettings.__set_settings_from_dict(settings)
