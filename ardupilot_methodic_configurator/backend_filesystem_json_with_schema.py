"""
Manages JSON files at the filesystem level.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from json import JSONDecodeError
from json import dumps as json_dumps
from json import load as json_load

# from logging import warning as logging_warning
# from sys import exit as sys_exit
from logging import debug as logging_debug
from logging import error as logging_error
from os import path as os_path
from typing import Any, Union

from jsonschema import ValidationError, validate, validators

from ardupilot_methodic_configurator import _


class FilesystemJSONWithSchema:
    """Load and save data from a JSON file."""

    def __init__(self, json_filename: str, schema_filename: str) -> None:
        self.json_filename = json_filename
        self.schema_filename = schema_filename
        self.data: Union[None, dict[str, Any]] = None
        self.schema: Union[None, dict[Any, Any]] = None

    def load_schema(self) -> dict:
        """
        Load the JSON schema.

        :return: The schema as a dictionary
        """
        if self.schema is not None:
            return self.schema

        # Determine the location of the schema file
        schema_path = os_path.join(os_path.dirname(__file__), self.schema_filename)

        try:
            with open(schema_path, encoding="utf-8") as file:
                loaded_schema: dict[Any, Any] = json_load(file)

                # Validate the schema itself against the JSON Schema meta-schema
                try:
                    # Get the Draft7Validator class which has the META_SCHEMA property
                    validator_class = validators.Draft7Validator
                    meta_schema = validator_class.META_SCHEMA

                    # Validate the loaded schema against the meta-schema
                    validate(instance=loaded_schema, schema=meta_schema)
                    logging_debug(_("Schema file '%s' is valid."), schema_path)
                except Exception as e:  # pylint: disable=broad-exception-caught
                    logging_error(_("Schema file '%s' is not a valid JSON Schema: %s"), schema_path, str(e))

                self.schema = loaded_schema
            return self.schema
        except FileNotFoundError:
            logging_error(_("Schema file '%s' not found."), schema_path)
        except JSONDecodeError:
            logging_error(_("Error decoding JSON schema from file '%s'."), schema_path)
        return {}

    def validate_json_against_schema(self, data: dict) -> tuple[bool, str]:
        """
        Validate data against the schema.

        :param data: data to validate
        :return: A tuple of (is_valid, error_message)
        """
        schema = self.load_schema()
        if not schema:
            return False, _("Could not load validation schema")

        try:
            validate(instance=data, schema=schema)
            return True, ""
        except ValidationError as e:
            return False, f"{_('Validation error')}: {e.message}"

    def load_json_data(self, data_dir: str) -> dict[Any, Any]:
        data: dict[Any, Any] = {}
        filepath = os_path.join(data_dir, self.json_filename)
        try:
            with open(filepath, encoding="utf-8") as file:
                data = json_load(file)

            # Validate the loaded data against the schema
            is_valid, error_message = self.validate_json_against_schema(data)
            if not is_valid:
                logging_error(_("Invalid JSON file '%s': %s"), filepath, error_message)
                # We still return the data even if invalid for debugging purposes
        except FileNotFoundError:
            # Normal users do not need this information
            logging_debug(_("File '%s' not found in %s."), self.json_filename, data_dir)
        except JSONDecodeError:
            logging_error(_("Error decoding JSON data from file '%s'."), filepath)
        self.data = data
        return data

    def save_json_data(self, data: dict, data_dir: str) -> tuple[bool, str]:  # noqa: PLR0911 # pylint: disable=too-many-return-statements
        """
        Save the data to a JSON file.

        :param data: The data to save
        :param data_dir: The directory to save the file in
        :return: A tuple of (error_occurred, error_message)
        """
        # Validate before saving

        is_valid, error_message = self.validate_json_against_schema(data)
        if not is_valid:
            msg = _("Cannot save invalid JSON data: {}").format(error_message)
            logging_error(msg)
            return True, msg

        filepath = os_path.join(data_dir, self.json_filename)
        try:
            with open(filepath, "w", encoding="utf-8", newline="\n") as file:
                json_str = json_dumps(data, indent=4)
                # Strip the last newline to avoid double newlines
                # This is to ensure compatibility with pre-commit's end-of-file-fixer
                file.write(json_str.rstrip("\n") + "\n")
        except FileNotFoundError:
            msg = _("Directory '{}' not found").format(data_dir)
            logging_error(msg)
            return True, msg
        except PermissionError:
            msg = _("Permission denied when writing to file '{}'").format(filepath)
            logging_error(msg)
            return True, msg
        except IsADirectoryError:
            msg = _("Path '{}' is a directory, not a file").format(filepath)
            logging_error(msg)
            return True, msg
        except OSError as e:
            msg = _("OS error when writing to file '{}': {}").format(filepath, str(e))
            logging_error(msg)
            return True, msg
        except TypeError as e:
            msg = _("Type error when serializing data to JSON: {}").format(str(e))
            logging_error(msg)
            return True, msg
        except ValueError as e:
            msg = _("Value error when serializing data to JSON: {}").format(str(e))
            logging_error(msg)
            return True, msg
        except Exception as e:  # pylint: disable=broad-exception-caught
            # Still have a fallback for truly unexpected errors
            msg = _("Unexpected error saving data to file '{}': {}").format(filepath, str(e))
            logging_error(msg)
            return True, msg

        return False, ""
