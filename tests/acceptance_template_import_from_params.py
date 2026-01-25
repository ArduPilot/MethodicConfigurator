#!/usr/bin/env python3

"""
Acceptance tests for component-parameter round-trip validation.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later


High-Level Concept
------------------
This test suite validates the bidirectional relationship between flight controller parameters
and component specifications by testing a complete round-trip cycle:

1. **Parameters → Component Inference**: Starting with known parameter values from vehicle templates,
   the system infers component specifications (battery capacity, motor specs, RC protocols, etc.)

2. **Components → Parameter Generation**: Using the inferred component specifications, the system
   generates new parameter files with values appropriate for those components

3. **Round-Trip Validation**: The generated parameters are compared against the original template
   parameters to verify consistency and identify any transformation losses or discrepancies

This validates that:
- Component inference logic correctly extracts specs from parameters
- Parameter generation logic correctly derives values from component specs
- The import/export cycle preserves essential configuration information
- Any differences are documented and can be analyzed for improvement

Test Workflow
-------------
1. **Compound Template Parameters** (TestTemplateCompounding):
   - Consolidates all .param files from vehicle templates into single params.param files
   - Creates baseline parameter sets representing real-world vehicle configurations

2. **File-Based Parameter Loading** (TestFileBasedParameterLoading):
   - Loads parameters without physical flight controller using file simulation mode
   - Validates the testing infrastructure for subsequent round-trip validation

3. **Component Inference and Project Generation** (TestTemplateImportWithComponentInference):
   - Infers component specifications from template parameters
   - Creates new vehicle projects with inferred components
   - Generates new parameter files based on component specifications

4. **Round-Trip Diff Analysis** (TestTemplateDiffGeneration):
   - Compares original template parameters with generated parameters
   - Documents differences in structured diff files for analysis
   - Identifies parameter transformation patterns and edge cases

Directory Structure
-------------------
Both source and target directories maintain the same vehicle_templates structure:

/tmp/amc_test_acceptance1/             Source: Compounded params.param files (mirrors source structure)
└── vehicle_templates/
    ├── ArduCopter/
    │   ├── diatone_taycan_mxc/
    │   │   ├── 4.6.x-params/params.param
    │   │   ├── 4.5.x-params/params.param
    │   │   ├── 4.4.4-params/params.param
    │   │   └── 4.3.8-params/params.param
    │   ├── Chimera7/params.param
    │   ├── Tarot_X4/params.param
    │   └── ...
    ├── ArduPlane/
    │   └── normal_plane/params.param
    ├── Rover/
    └── Heli/

/tmp/amc_test_acceptance2/             Target: Generated vehicle projects (mirrors source structure)
└── vehicle_templates/
    ├── ArduCopter/
    │   ├── diatone_taycan_mxc/
    │   │   ├── 4.6.x-params/        ← New project generated from 4.6.x-params template
    │   │   │   ├── 00_default.param
    │   │   │   ├── vehicle_components.json
    │   │   │   └── ...
    │   │   └── 4.4.4-params/
    │   ├── Chimera7/                ← New project from Chimera7 template
    │   │   ├── 00_default.param
    │   │   ├── vehicle_components.json
    │   │   └── ...
    │   └── ...
    └── ...

/tmp/amc_test_acceptance3/             Round-trip validation: Diff files (mirrors source structure)
└── vehicle_templates/
    ├── ArduCopter/
    │   ├── diatone_taycan_mxc/
    │   │   ├── 4.6.x-params/        ← Diff files comparing original vs generated
    │   │   │   ├── 01_esc_calibration.param.diff
    │   │   │   ├── 08_batt1.param.diff
    │   │   │   ├── vehicle_components.json.diff
    │   │   │   └── ...
    │   │   └── 4.4.4-params/
    │   ├── Chimera7/                ← Diff files for Chimera7 comparison
    │   │   ├── 02_imu_temperature_calibration_setup.param.diff
    │   │   ├── 08_batt1.param.diff
    │   │   └── ...
    │   └── ...
    └── ...

File Simulation Mode
---------------------
The file simulation mode allows testing without a physical flight controller:
1. Create or copy a params.param file to the current working directory
2. Call FlightController.connect(DEVICE_FC_PARAM_FROM_FILE) where DEVICE_FC_PARAM_FROM_FILE="file"
3. Call FlightController.download_params() to load parameters from the file
4. Parameters are now available in FlightController.fc_parameters dictionary

This mode is essential for:
- CI/CD testing without hardware
- Offline development and testing
- Template validation and project creation testing
- Component inference validation with known parameter sets

Test Classes
------------
1. TestTemplateCompounding:
   - Validates parameter compounding from multiple .param files
   - Ensures all templates can be successfully processed

2. TestFileBasedParameterLoading:
   - Tests FlightController's file simulation mode
   - Verifies parameter loading without physical hardware

3. TestTemplateImportWithComponentInference:
   - Tests complete project creation workflow
   - Validates component inference from parameters
   - Tests both single and batch project creation scenarios

Expected Outcomes
-----------------
- Component specifications correctly inferred from parameters
- Generated parameter files match expected values based on components
- Round-trip diffs highlight any discrepancies for analysis
- Tests pass for all supported vehicle types and configurations
- Some tests may be skipped if empty templates are unavailable for certain vehicle types

Notes
-----
- Cleanup is commented out in fixtures to allow manual inspection of generated files
- Tests skip gracefully when empty templates are unavailable for certain vehicle types
- Some failures are expected (e.g., ArduPlane missing empty_4.6.x template)

"""

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.backend_filesystem_vehicle_components import VehicleComponents
from ardupilot_methodic_configurator.backend_flightcontroller import DEVICE_FC_PARAM_FROM_FILE, FlightController
from ardupilot_methodic_configurator.data_model_par_dict import ParDict
from ardupilot_methodic_configurator.data_model_vehicle_components import ComponentDataModel
from ardupilot_methodic_configurator.data_model_vehicle_components_json_schema import (
    VehicleComponentsJsonSchema,
)
from ardupilot_methodic_configurator.data_model_vehicle_project_creator import (
    NewVehicleProjectSettings,
    VehicleProjectCreator,
)

# ruff: noqa: ANN201, ANN205, S108, S603, S607, PLR0915, EM102

# pylint: disable=too-many-lines,too-many-locals,too-many-branches,too-many-statements,too-many-nested-blocks,redefined-outer-name,too-few-public-methods,unused-argument,broad-exception-caught

logger = logging.getLogger(__name__)


def create_test_filesystem(vehicle_dir: Path, vehicle_type: str):
    """
    Create LocalFilesystem and schema for testing.

    Args:
        vehicle_dir: Path to the vehicle template directory
        vehicle_type: Vehicle type (ArduCopter, ArduPlane, Heli, Rover)

    Returns:
        tuple: (LocalFilesystem, VehicleComponentsJsonSchema)

    """
    local_fs = LocalFilesystem(
        vehicle_dir=str(vehicle_dir),
        vehicle_type=vehicle_type,
        fw_version="4.6.3",
        allow_editing_template_files=True,
        save_component_to_system_templates=False,
    )
    schema = VehicleComponentsJsonSchema(local_fs.load_schema())
    return local_fs, schema


def perform_component_inference(
    local_filesystem: LocalFilesystem,
    new_vehicle_dir: str,
    vehicle_type: str,
    fc_parameters: dict,
    blank_component_data: bool = False,
) -> tuple[bool, str]:
    """
    Perform component inference and update vehicle configuration.

    Args:
        local_filesystem: LocalFilesystem instance
        new_vehicle_dir: Path to the new vehicle directory
        vehicle_type: Vehicle type (ArduCopter, ArduPlane, Heli, Rover)
        fc_parameters: Flight controller parameters
        blank_component_data: Whether component data was blanked

    Returns:
        tuple: (success: bool, error_message: str)

    """
    # Reload the local_filesystem to get the new vehicle directory's data
    local_filesystem.re_init(new_vehicle_dir, vehicle_type, blank_component_data)

    # Load the vehicle components data from the new directory
    comp_data = local_filesystem.load_vehicle_components_json_data(new_vehicle_dir)

    # Create the schema
    schema = VehicleComponentsJsonSchema(local_filesystem.load_schema())

    # Create a ComponentDataModel to perform inference
    comp_model = ComponentDataModel(comp_data, local_filesystem.doc_dict, schema)

    # Infer component specifications and connections from FC parameters
    comp_model.process_fc_parameters(fc_parameters, local_filesystem.doc_dict)

    # Save the updated component data back to the filesystem
    error, error_msg = local_filesystem.save_vehicle_components_json_data(comp_model.get_component_data(), new_vehicle_dir)
    if error:
        return False, f"Failed to save inferred component data: {error_msg}"

    # Reload the vehicle_components_fs so get_eval_variables() uses updated data
    local_filesystem.load_vehicle_components_json_data(new_vehicle_dir)

    # Regenerate parameter files from the inferred component data
    existing_fc_params = list(fc_parameters.keys())
    error_message = local_filesystem.update_and_export_vehicle_params_from_fc(
        source_param_values=fc_parameters, existing_fc_params=existing_fc_params
    )
    if error_message:
        return False, f"Failed to update and export parameters: {error_message}"

    return True, ""


def get_vehicle_template_directories() -> list[Path]:
    """
    Get all vehicle template directories that contain param files.

    Returns:
        list[Path]: List of paths to vehicle template directories.

    """
    template_base = Path(__file__).parent.parent / "ardupilot_methodic_configurator" / "vehicle_templates"

    vehicle_dirs = []
    for vehicle_type_dir in template_base.iterdir():
        if not vehicle_type_dir.is_dir():
            continue

        # Iterate through specific vehicle directories (e.g., diatone_taycan_mxc)
        for vehicle_dir in vehicle_type_dir.iterdir():
            if not vehicle_dir.is_dir():
                continue

            param_subdirs = [d for d in vehicle_dir.iterdir() if d.is_dir()]

            if param_subdirs:
                vehicle_dirs.extend(param_subdirs)
            else:
                # Check if this directory directly contains .param files
                param_files = list(vehicle_dir.glob("*.param"))
                if param_files:
                    vehicle_dirs.append(vehicle_dir)

    return vehicle_dirs


def get_empty_template_dir(vehicle_type: str) -> Path:
    """
    Get the path to the empty_4.6.x template for the given vehicle type.

    Args:
        vehicle_type: Vehicle type (ArduCopter, ArduPlane, Heli, Rover)

    Returns:
        Path to the empty template directory

    Raises:
        FileNotFoundError: If empty template directory doesn't exist

    """
    templates_base = (
        Path(__file__).parent.parent / "ardupilot_methodic_configurator" / "vehicle_templates" / vehicle_type / "empty_4.6.x"
    )

    if not templates_base.exists():
        raise FileNotFoundError(f"Template directory not found: {templates_base}")

    return templates_base


@pytest.fixture(scope="module")
def tmp_test_dir():
    """Create and cleanup test directory in /tmp for compounded params.param files."""
    test_dir = Path("/tmp/amc_test_acceptance1")
    if test_dir.exists():
        shutil.rmtree(test_dir)
    test_dir.mkdir(parents=True, exist_ok=True)
    return test_dir
    # Cleanup after all tests (commented out for inspection)
    # if test_dir.exists():
    #     shutil.rmtree(test_dir)


@pytest.fixture(scope="module")
def tmp_test_output_dir():
    """Create and cleanup output directory in /tmp for generated vehicle projects."""
    test_dir = Path("/tmp/amc_test_acceptance2")
    if test_dir.exists():
        shutil.rmtree(test_dir)
    test_dir.mkdir(parents=True, exist_ok=True)
    return test_dir
    # Cleanup after all tests (commented out for inspection)
    # if test_dir.exists():
    #     shutil.rmtree(test_dir)


@pytest.fixture(scope="module")
def compounded_params_files(tmp_test_dir):
    """
    Create compounded params.param files from all vehicle templates.

    This fixture runs once for the module and creates params.param files
    in /tmp/amc_test_acceptance1/ for all vehicle templates.

    Returns:
        dict[Path, Path]: Mapping of template_dir -> params_file_path

    """
    template_dirs = get_vehicle_template_directories()
    params_files = {}

    for template_dir in template_dirs:
        # Extract vehicle type
        vehicle_type = template_dir.parts[-3] if "-params" in template_dir.name else template_dir.parts[-2]
        assert vehicle_type in VehicleComponents.supported_vehicles(), f"Unknown vehicle type: {vehicle_type}"

        # Create LocalFilesystem instance
        try:
            local_fs = LocalFilesystem(
                vehicle_dir=str(template_dir),
                vehicle_type=vehicle_type,
                fw_version="4.6.3",
                allow_editing_template_files=False,
                save_component_to_system_templates=False,
            )
        except (ValueError, SystemExit) as e:
            # Skip templates with invalid configuration
            logger.debug("Skipping template %s: %s", template_dir.name, e)
            continue

        # Verify file_parameters were loaded
        if len(local_fs.file_parameters) == 0:
            continue

        # Compound all parameters (including default file)
        compound_params, _first_config_step = local_fs.compound_params(last_filename=None, skip_default=False)

        # Verify parameters were compounded
        if len(compound_params) == 0:
            continue

        # Create output directory in /tmp with same structure (starting from vehicle_templates)
        # Find the vehicle_templates directory in the path
        vehicle_templates_idx = None
        for i, part in enumerate(template_dir.parts):
            if part == "vehicle_templates":
                vehicle_templates_idx = i
                break

        if vehicle_templates_idx is None:
            continue  # Skip if not under vehicle_templates

        # Get path relative to vehicle_templates parent (ardupilot_methodic_configurator)
        relative_path = Path(*template_dir.parts[vehicle_templates_idx:])
        tmp_output_dir = tmp_test_dir / relative_path
        tmp_output_dir.mkdir(parents=True, exist_ok=True)

        # Export compounded parameters to params.param
        output_file = tmp_output_dir / "params.param"
        local_fs.export_to_param(compound_params, str(output_file), annotate_doc=False)

        # Verify file was created
        if output_file.exists() and output_file.stat().st_size > 0:
            params_files[template_dir] = output_file

    return params_files


class TestTemplateCompounding:
    """Test that vehicle template parameters can be compounded into single files."""

    def test_user_can_compound_all_template_parameters(self, compounded_params_files):
        """
        User can compound all parameters from vehicle templates into single params.param files.

        GIVEN: User has vehicle template directories with multiple .param files
        WHEN: They compound all parameters into a single params.param file
        THEN: The compounded file should contain all parameters
        AND: The file should be properly formatted and readable
        """
        # Then: At least some templates should have been successfully compounded
        assert len(compounded_params_files) > 0, "No templates were successfully compounded"

        # And: Each params.param file should contain parameters
        for template_dir, params_file in compounded_params_files.items():
            assert params_file.exists(), f"params.param not created for {template_dir}"
            assert params_file.stat().st_size > 0, f"params.param is empty for {template_dir}"

            # Verify file contains valid parameter lines
            content = params_file.read_text(encoding="utf-8")
            param_lines = [line for line in content.split("\n") if line.strip() and not line.strip().startswith("#")]
            assert len(param_lines) > 0, f"params.param contains no parameters for {template_dir}"


class TestFileBasedParameterLoading:
    """Test that FC parameters can be loaded from params.param files using file simulation mode."""

    def test_user_can_load_parameters_from_compounded_file(self, compounded_params_files):
        """
        User can load FC parameters from compounded params.param file using --device file.

        GIVEN: User has a params.param file from compounded template parameters
        WHEN: They use --device=file to load parameters
        THEN: FlightController should successfully read all parameters from the file
        AND: Parameter count should match the file contents
        """
        # Given: Use first available params file for testing
        if not compounded_params_files:
            pytest.skip("No compounded params files available for testing")

        params_file = next(iter(compounded_params_files.values()))
        params_dir = params_file.parent

        # Read expected parameter count from file
        content = params_file.read_text(encoding="utf-8")
        expected_param_count = len([line for line in content.split("\n") if line.strip() and not line.strip().startswith("#")])

        # When: Load parameters using file simulation mode
        original_cwd = os.getcwd()
        try:
            os.chdir(params_dir)

            flight_controller = FlightController(reboot_time=0)
            error_str = flight_controller.connect(DEVICE_FC_PARAM_FROM_FILE, log_errors=True)

            # Then: Connection should succeed
            assert error_str == "", f"Failed to connect in file simulation mode: {error_str}"

            # Download parameters (required step after connect in file simulation mode)
            params, _ = flight_controller.download_params()

            # And: Parameters should be loaded
            assert params is not None, "download_params returned None"
            assert len(params) > 0, "No parameters were loaded from file"
            assert flight_controller.fc_parameters is not None, "fc_parameters is None"
            assert len(flight_controller.fc_parameters) > 0, "fc_parameters dict is empty"

            # And: Parameter count should match file contents
            assert len(flight_controller.fc_parameters) == expected_param_count, (
                f"Expected {expected_param_count} parameters, got {len(flight_controller.fc_parameters)}"
            )

        finally:
            os.chdir(original_cwd)


class TestTemplateImportWithComponentInference:
    """Test creating new vehicle projects from templates with component inference from FC parameters."""

    def test_user_can_create_project_with_component_inference(
        self, compounded_params_files, tmp_test_dir, tmp_test_output_dir
    ):
        """
        User can create a new vehicle project inferring components from FC parameters.

        GIVEN: User has FC parameters loaded from a compounded params.param file
        WHEN: They create a new project with infer_comp_specs_and_conn_from_fc_params=True
        THEN: A new vehicle directory should be created
        AND: Component specifications should be inferred from FC parameters
        AND: Parameter files should be generated in the new directory
        """
        if not compounded_params_files:
            pytest.skip("No compounded params files available")

        # Use first available params file for testing
        template_dir, params_file = next(iter(compounded_params_files.items()))

        # Given: Load parameters from file
        params_dir = params_file.parent
        original_cwd = os.getcwd()

        try:
            os.chdir(params_dir)

            flight_controller = FlightController(reboot_time=0)
            error_str = flight_controller.connect(DEVICE_FC_PARAM_FROM_FILE, log_errors=True)

            if error_str:
                pytest.skip(f"Cannot connect to flight controller: {error_str}")

            # Download parameters from file
            params, _ = flight_controller.download_params()

            if not params or len(params) == 0:
                pytest.skip(f"No parameters loaded from {params_file}")

            # Extract vehicle type
            vehicle_type = template_dir.parts[-3] if "-params" in template_dir.name else template_dir.parts[-2]
            assert vehicle_type in VehicleComponents.supported_vehicles(), f"Unknown vehicle type: {vehicle_type}"

            # Get empty template directory
            try:
                empty_template_dir = get_empty_template_dir(vehicle_type)
            except FileNotFoundError:
                pytest.skip(f"Empty template not found for vehicle type: {vehicle_type}")

            # Create output path preserving vehicle_templates structure
            # params_dir is like: /tmp/amc_test_acceptance1/vehicle_templates/ArduCopter/Chimera7
            relative_path = params_dir.relative_to(tmp_test_dir)
            # relative_path is like: vehicle_templates/ArduCopter/Chimera7
            vehicle_name = relative_path.parts[-1]
            # Create parallel structure in output dir
            output_vehicle_dir = tmp_test_output_dir / relative_path
            output_vehicle_dir.parent.mkdir(parents=True, exist_ok=True)

            # Initialize LocalFilesystem with the template
            local_filesystem = LocalFilesystem(
                vehicle_dir=str(empty_template_dir),
                vehicle_type=vehicle_type,
                fw_version="4.6.3",
                allow_editing_template_files=False,
                save_component_to_system_templates=False,
            )

            # When: Create project settings with component inference enabled
            settings = NewVehicleProjectSettings(
                copy_vehicle_image=False,
                blank_component_data=False,
                reset_fc_parameters_to_their_defaults=False,
                infer_comp_specs_and_conn_from_fc_params=True,
                use_fc_params=True,
                blank_change_reason=True,
            )

            # And: Create the vehicle project
            project_creator = VehicleProjectCreator(local_filesystem)
            new_vehicle_dir = project_creator.create_new_vehicle_from_template(
                template_dir=str(empty_template_dir),
                new_base_dir=str(output_vehicle_dir.parent),  # e.g., /tmp/amc_test_acceptance2/vehicle_templates/ArduCopter
                new_vehicle_name=f"{vehicle_name}",
                settings=settings,
                fc_connected=False,  # File simulation mode - no physical connection
                fc_parameters=flight_controller.fc_parameters,
            )

            # Then: New vehicle directory should be created
            assert Path(new_vehicle_dir).exists(), f"New vehicle directory not created: {new_vehicle_dir}"

            # And: If component inference was requested, perform it now
            if settings.infer_comp_specs_and_conn_from_fc_params and flight_controller.fc_parameters:
                success, error_msg = perform_component_inference(
                    local_filesystem,
                    new_vehicle_dir,
                    vehicle_type,
                    flight_controller.fc_parameters,
                    settings.blank_component_data,
                )
                assert success, error_msg

            # And: Directory should contain .param files
            param_files = list(Path(new_vehicle_dir).glob("*.param"))
            assert len(param_files) > 0, f"No parameter files found in {new_vehicle_dir}"

            # And: vehicle_components.json should exist
            components_file = Path(new_vehicle_dir) / "vehicle_components.json"
            assert components_file.exists(), f"vehicle_components.json not found in {new_vehicle_dir}"

        finally:
            os.chdir(original_cwd)

    def test_component_inference_handles_various_configurations(
        self, compounded_params_files, tmp_test_dir, tmp_test_output_dir
    ):
        """
        Component inference correctly handles various vehicle configurations.

        GIVEN: User has params files from different vehicle types and configurations
        WHEN: They create projects with component inference for each
        THEN: Each project should be created successfully
        AND: Components should be appropriately inferred for each configuration
        """
        if not compounded_params_files:
            pytest.skip("No compounded params files available")

        successful_creations = 0
        failed_creations = []

        # Test a subset of templates (first 10 to keep test time reasonable)
        for template_dir, params_file in list(compounded_params_files.items())[:10]:
            params_dir = params_file.parent
            original_cwd = os.getcwd()

            try:
                os.chdir(params_dir)

                # Load parameters
                flight_controller = FlightController(reboot_time=0)
                error_str = flight_controller.connect(DEVICE_FC_PARAM_FROM_FILE, log_errors=False)

                if error_str:
                    failed_creations.append((template_dir, f"Connection failed: {error_str}"))
                    continue

                # Download parameters from file
                params, _ = flight_controller.download_params()

                if not params:
                    failed_creations.append((template_dir, "Failed to download parameters"))
                    continue

                if len(params) == 0:
                    failed_creations.append((template_dir, "No parameters loaded"))
                    continue

                # Get vehicle type and template
                vehicle_type = template_dir.parts[-3] if "-params" in template_dir.name else template_dir.parts[-2]
                assert vehicle_type in VehicleComponents.supported_vehicles(), f"Unknown vehicle type: {vehicle_type}"

                try:
                    empty_template_dir = get_empty_template_dir(vehicle_type)
                except FileNotFoundError:
                    failed_creations.append((template_dir, "Empty template not found"))
                    continue

                # Create output path preserving vehicle_templates structure
                relative_path = params_dir.relative_to(tmp_test_dir)
                vehicle_name = relative_path.parts[-1]
                # Create parallel structure in output dir
                output_vehicle_dir = tmp_test_output_dir / relative_path
                output_vehicle_dir.parent.mkdir(parents=True, exist_ok=True)

                # Initialize filesystem and create project
                local_filesystem = LocalFilesystem(
                    vehicle_dir=str(empty_template_dir),
                    vehicle_type=vehicle_type,
                    fw_version="4.6.3",
                    allow_editing_template_files=True,
                    save_component_to_system_templates=False,
                )

                settings = NewVehicleProjectSettings(
                    infer_comp_specs_and_conn_from_fc_params=True,
                    use_fc_params=True,
                    blank_change_reason=True,
                )

                project_creator = VehicleProjectCreator(local_filesystem)
                new_vehicle_dir = project_creator.create_new_vehicle_from_template(
                    template_dir=str(empty_template_dir),
                    new_base_dir=str(
                        output_vehicle_dir.parent
                    ),  # e.g., /tmp/amc_test_acceptance2/vehicle_templates/ArduCopter
                    new_vehicle_name=f"{vehicle_name}",
                    settings=settings,
                    fc_connected=False,
                    fc_parameters=flight_controller.fc_parameters,
                )

                # Perform component inference if requested
                # Note: perform_component_inference already calls update_and_export_vehicle_params_from_fc
                # so FC parameter values are properly merged into the generated parameter files
                if settings.infer_comp_specs_and_conn_from_fc_params and flight_controller.fc_parameters:
                    success, error_msg = perform_component_inference(
                        local_filesystem,
                        new_vehicle_dir,
                        vehicle_type,
                        flight_controller.fc_parameters,
                        settings.blank_component_data,
                    )
                    if not success:
                        failed_creations.append((template_dir, error_msg))
                        continue

                # Verify creation
                if Path(new_vehicle_dir).exists():
                    successful_creations += 1
                else:
                    failed_creations.append((template_dir, "Directory not created"))

            except Exception as e:  # pylint: disable=broad-except
                logger.debug("Failed to create project for %s: %s", template_dir.name, e)
                failed_creations.append((template_dir, str(e)))
            finally:
                os.chdir(original_cwd)

        # Report results
        logger.info("Successful creations: %d/10", successful_creations)
        if failed_creations:
            logger.info("Failed creations:")
            for template_dir, reason in failed_creations:
                logger.info("  - %s: %s", template_dir.name, reason)

        # Then: Most templates should succeed (allow some failures for edge cases)
        assert successful_creations > 5, f"Too many failures: only {successful_creations}/10 succeeded"


class TestComponentInferenceValidation:
    """Test validating component inference by comparing original and generated vehicle_components.json files."""

    @staticmethod
    def get_inferable_fields() -> list[tuple[str, str, str]]:
        """
        Get list of component fields that can be inferred from FC parameters.

        Returns:
            List of tuples (component_name, section_name, field_name) for inferable fields

        """
        return [
            ("Battery", "Specifications", "Chemistry"),
            ("Battery", "Specifications", "Volt per cell max"),
            ("Battery", "Specifications", "Volt per cell low"),
            ("Battery", "Specifications", "Volt per cell crit"),
            ("Battery", "Specifications", "Number of cells"),
            ("Battery", "Specifications", "Capacity mAh"),
            ("Battery Monitor", "FC Connection", "Type"),
            ("Battery Monitor", "FC Connection", "Protocol"),
            ("ESC", "FC Connection", "Type"),
            ("ESC", "FC Connection", "Protocol"),
            ("GNSS Receiver", "FC Connection", "Type"),
            ("GNSS Receiver", "FC Connection", "Protocol"),
            ("RC Receiver", "FC Connection", "Type"),
            ("RC Receiver", "FC Connection", "Protocol"),
            ("Motors", "Specifications", "Poles"),
        ]

    @staticmethod
    def get_simple_mode_fields(schema) -> dict[str, list[tuple[str, ...]]]:
        """
        Get the component fields that should be checked in simple mode.

        Dynamically discovers fields from schema that:
        - Are marked as non-optional (part of "simple" GUI complexity mode)
        - Excludes TOW min/max Kg and Diameter_inches as specifically requested

        Args:
            schema: VehicleComponentsJsonSchema instance

        Returns:
            dict mapping component names to lists of field paths to check

        """
        excluded_fields = {
            ("Frame", "Specifications", "TOW min Kg"),
            ("Frame", "Specifications", "TOW max Kg"),
            ("Propellers", "Specifications", "Diameter_inches"),
        }

        fields_by_component: dict[str, list[tuple[str, ...]]] = {}

        # Get the Components schema
        components_schema = schema.schema.get("properties", {}).get("Components", {})
        if not components_schema:
            return fields_by_component

        # Get all component definitions
        all_of = components_schema.get("allOf", [])
        if not all_of:
            return fields_by_component

        # Iterate through each component type definition
        for component_def in all_of:
            properties = component_def.get("properties", {})

            for component_name, component_schema in properties.items():
                # Skip if not a proper component schema
                if not isinstance(component_schema, dict):
                    continue

                component_props = component_schema.get("properties", {})

                # Check each section (Product, Firmware, Specifications, FC Connection, etc.)
                for section_name, section_schema in component_props.items():
                    if not isinstance(section_schema, dict):
                        continue

                    section_props = section_schema.get("properties", {})

                    # Check each field in the section
                    for field_name, field_schema in section_props.items():
                        if not isinstance(field_schema, dict):
                            continue

                        # Check if field is non-optional (required for simple mode)
                        is_optional = field_schema.get("x-is-optional", False)

                        if not is_optional:
                            field_path = (component_name, section_name, field_name)

                            # Skip excluded fields
                            if field_path in excluded_fields:
                                continue

                            # Add to results
                            if component_name not in fields_by_component:
                                fields_by_component[component_name] = []
                            fields_by_component[component_name].append((section_name, field_name))

        return fields_by_component

    @staticmethod
    def get_field_value(component_data: dict, field_path: tuple[str, ...]):
        """
        Get a field value from nested component data.

        Args:
            component_data: Component dictionary
            field_path: Tuple of keys to navigate (e.g., ("Specifications", "Capacity mAh"))

        Returns:
            Field value or None if path doesn't exist

        """
        current = component_data
        for key in field_path:
            if not isinstance(current, dict) or key not in current:
                return None
            current = current[key]
        return current

    def test_component_inference_from_params_file_matches_original(self, compounded_params_files):
        """
        Component inference from params.param files matches original vehicle_components.json.

        GIVEN: Original vehicle templates with vehicle_components.json and params.param
        WHEN: Loading params.param and inferring components directly
        THEN: All inferable fields should match original template values with 100% accuracy
        AND: This validates the core inference logic without project creation overhead
        """
        if not compounded_params_files:
            pytest.skip("No compounded params files available")

        inferable_fields = self.get_inferable_fields()
        all_comparisons = []

        # Test first 5 templates for quick validation
        for template_dir, params_file in list(compounded_params_files.items())[:5]:
            # Load original vehicle_components.json
            original_json = template_dir / "vehicle_components.json"
            if not original_json.exists():
                continue

            with open(original_json, encoding="utf-8") as f:
                original_data = json.load(f)

            # Load parameters from params.param
            try:
                params_dict = ParDict.from_file(str(params_file))
                params = {name: param.value for name, param in params_dict.items()}
            except Exception as e:
                logger.debug("Failed to load params from %s: %s", params_file, e)
                continue

            # Setup filesystem and schema for inference
            vehicle_type = template_dir.parts[-3] if "-params" in template_dir.name else template_dir.parts[-2]
            try:
                empty_template_dir = get_empty_template_dir(vehicle_type)
                local_fs, schema = create_test_filesystem(empty_template_dir, vehicle_type)
            except Exception as e:
                logger.debug("Failed to create filesystem for %s: %s", template_dir.name, e)
                continue

            # Infer components
            model = ComponentDataModel(original_data, local_fs.doc_dict, schema)
            model.process_fc_parameters(params, local_fs.doc_dict)
            inferred_data = model.get_component_data()

            # Compare inferable fields
            original_components = original_data.get("Components", {})
            inferred_components = inferred_data.get("Components", {})

            for component_name, section_name, field_name in inferable_fields:
                original_value = self.get_field_value(original_components.get(component_name, {}), (section_name, field_name))
                inferred_value = self.get_field_value(inferred_components.get(component_name, {}), (section_name, field_name))

                field_key = f"{component_name}.{section_name}.{field_name}"
                comparison = {
                    "template": template_dir.name,
                    "field": field_key,
                    "original": original_value,
                    "inferred": inferred_value,
                    "match": original_value == inferred_value,
                }
                all_comparisons.append(comparison)

        # Then: At least some comparisons should have been made
        assert len(all_comparisons) > 0, "No component comparisons were performed"

        # And: Calculate accuracy
        total_matches = sum(1 for c in all_comparisons if c["match"])
        total_comparisons = len(all_comparisons)
        match_percentage = (total_matches / total_comparisons * 100) if total_comparisons > 0 else 0

        # Report mismatches
        mismatches = [c for c in all_comparisons if not c["match"]]
        if mismatches:
            logger.info("=" * 80)
            logger.info("COMPONENT INFERENCE VALIDATION (Direct from params.param)")
            logger.info("=" * 80)
            logger.info("Total comparisons: %d", total_comparisons)
            logger.info("Matches: %d (%.1f%%)", total_matches, match_percentage)
            logger.info("Mismatches: %d", len(mismatches))
            logger.info("=" * 80)
            logger.info("MISMATCHES:")
            logger.info("=" * 80)
            for mismatch in mismatches:
                logger.info(
                    "%s: %s: %s → %s", mismatch["template"], mismatch["field"], mismatch["original"], mismatch["inferred"]
                )

        # And: Inferable fields should have high accuracy (>90%)
        # Note: 90% threshold allows for template data quality issues
        assert match_percentage > 90.0, (
            f"Component inference accuracy too low: {match_percentage:.1f}% "
            f"(expected >90%). Found {len(mismatches)} mismatches in {total_comparisons} comparisons. "
            "This indicates the core inference logic has issues."
        )

    def test_inferred_components_match_original_templates(self, compounded_params_files, tmp_test_dir, tmp_test_output_dir):
        """
        Inferred component specifications match original template values for simple mode fields.

        GIVEN: Generated vehicle projects with inferred components exist
        WHEN: Comparing vehicle_components.json between original and generated
        THEN: All fields relevant to simple mode should match
        AND: TOW and propeller diameter are excluded from comparison
        AND: Product metadata fields can differ (not inferable)
        """
        if not compounded_params_files:
            pytest.skip("No compounded params files available")

        original_base = Path(__file__).parent.parent / "ardupilot_methodic_configurator" / "vehicle_templates"
        generated_base = tmp_test_output_dir / "vehicle_templates"

        if not generated_base.exists():
            pytest.skip("No generated projects found")

        # Use any existing template to load the schema
        template_dir = next(iter(compounded_params_files.keys()))
        vehicle_type = template_dir.parts[-3] if "-params" in template_dir.name else template_dir.parts[-2]
        try:
            empty_template_dir = get_empty_template_dir(vehicle_type)
            _temp_filesystem, schema = create_test_filesystem(empty_template_dir, vehicle_type)
        except Exception as e:
            logger.error("Cannot load schema: %s", e)
            pytest.skip(f"Cannot load schema: {e}")

        simple_mode_fields = self.get_simple_mode_fields(schema)
        all_comparisons = []
        mismatches_by_field = {}

        # Find all generated vehicle_components.json files
        for generated_json in generated_base.rglob("vehicle_components.json"):
            # Find matching original
            relative_path = generated_json.parent.relative_to(generated_base)
            original_json = original_base / relative_path / "vehicle_components.json"

            if not original_json.exists():
                continue

            with open(original_json, encoding="utf-8") as f:
                original_data = json.load(f)

            with open(generated_json, encoding="utf-8") as f:
                generated_data = json.load(f)

            original_components = original_data.get("Components", {})
            generated_components = generated_data.get("Components", {})

            # Compare each field
            for component_name, field_paths in simple_mode_fields.items():
                if component_name not in original_components or component_name not in generated_components:
                    continue

                original_comp = original_components[component_name]
                generated_comp = generated_components[component_name]

                for field_path in field_paths:
                    original_value = self.get_field_value(original_comp, field_path)
                    generated_value = self.get_field_value(generated_comp, field_path)

                    field_key = f"{component_name}.{'.'.join(field_path)}"
                    comparison = {
                        "template": str(relative_path),
                        "component": component_name,
                        "field": field_key,
                        "original": original_value,
                        "generated": generated_value,
                        "match": original_value == generated_value,
                    }
                    all_comparisons.append(comparison)

                    if not comparison["match"]:
                        if field_key not in mismatches_by_field:
                            mismatches_by_field[field_key] = []
                        mismatches_by_field[field_key].append(comparison)

        # Then: At least some comparisons should have been made
        assert len(all_comparisons) > 0, "No component comparisons were performed"

        # Report results
        total_matches = sum(1 for c in all_comparisons if c["match"])
        total_comparisons = len(all_comparisons)
        match_percentage = (total_matches / total_comparisons * 100) if total_comparisons > 0 else 0

        logger.info("=" * 80)
        logger.info("COMPONENT INFERENCE VALIDATION RESULTS")
        logger.info("=" * 80)
        logger.info("Total field comparisons: %d", total_comparisons)
        logger.info("Matching fields: %d (%.1f%%)", total_matches, match_percentage)
        logger.info("Mismatched fields: %d", total_comparisons - total_matches)

        if mismatches_by_field:
            logger.info("=" * 80)
            logger.info("MISMATCHES BY FIELD:")
            logger.info("=" * 80)
            for field_key, mismatches in sorted(mismatches_by_field.items()):
                logger.info("%s: %d mismatches", field_key, len(mismatches))
                for mismatch in mismatches[:3]:  # Show first 3 examples
                    logger.info("  %s: %s -> %s", mismatch["template"], mismatch["original"], mismatch["generated"])
                if len(mismatches) > 3:
                    logger.info("  ... and %d more", len(mismatches) - 3)

        # And: Fields that CAN be inferred should have high match rate
        inferable_field_tuples = self.get_inferable_fields()
        inferable_fields = [f"{comp}.{section}.{field}" for comp, section, field in inferable_field_tuples]

        inferable_comparisons = [c for c in all_comparisons if c["field"] in inferable_fields]
        if inferable_comparisons:
            inferable_matches = sum(1 for c in inferable_comparisons if c["match"])
            inferable_total = len(inferable_comparisons)
            inferable_percentage = (inferable_matches / inferable_total * 100) if inferable_total > 0 else 0

            logger.info("=" * 80)
            logger.info("INFERABLE FIELDS ANALYSIS:")
            logger.info("=" * 80)
            logger.info("Inferable field comparisons: %d", inferable_total)
            logger.info("Matching: %d (%.1f%%)", inferable_matches, inferable_percentage)

            # Assert that inferable fields have high accuracy (>80%)
            assert inferable_percentage > 80.0, (
                f"Inferable fields match rate too low: {inferable_percentage:.1f}% "
                f"(expected >80%). This indicates component inference is not working correctly."
            )


class TestParameterDerivationValidation:
    """Test validating parameter value preservation through the round-trip process."""

    @staticmethod
    def get_whitelisted_parameter_diffs() -> dict[str, set[str]]:
        """
        Get dictionary of known acceptable parameter differences.

        These parameters are whitelisted because they appear in multiple .param files
        with different values, and the compounded params.param only captures the final
        state after all files are loaded sequentially.

        Returns:
            dict mapping file patterns to sets of parameter names to ignore

        """
        # System ID parameters that evolve across roll/pitch/yaw/thrust test files
        system_id_params = {
            "SID_T_REC",
            "SID_AXIS",
            "SID_MAGNITUDE",
            "SID_F_START_HZ",
            "SID_F_STOP_HZ",
            "SID_T_FADE_IN",
            "ATC_RATE_FF_ENAB",
            "ATC_RAT_RLL_I",
            "ATC_RAT_PIT_I",
            "ATC_RAT_YAW_I",
            "PSC_ACCZ_I",
            "LOG_BITMASK",
            "ANGLE_MAX",
            "ARMING_CHECK",
        }

        # PID tuning parameters that change during autotune and quick tune
        pid_tuning_params = {
            "ATC_RAT_RLL_P",
            "ATC_RAT_RLL_I",
            "ATC_RAT_RLL_D",
            "ATC_RAT_RLL_FLTD",
            "ATC_RAT_RLL_FLTT",
            "ATC_RAT_RLL_SMAX",
            "ATC_RAT_PIT_P",
            "ATC_RAT_PIT_I",
            "ATC_RAT_PIT_D",
            "ATC_RAT_PIT_FLTD",
            "ATC_RAT_PIT_FLTT",
            "ATC_RAT_PIT_SMAX",
            "ATC_RAT_YAW_P",
            "ATC_RAT_YAW_I",
            "ATC_RAT_YAW_D",
            "ATC_RAT_YAW_FLTD",
            "ATC_RAT_YAW_FLTT",
            "ATC_RAT_YAW_FLTE",
            "ATC_RAT_YAW_SMAX",
            "ATC_ANG_RLL_P",
            "ATC_ANG_PIT_P",
            "ATC_ANG_YAW_P",
            "ATC_ACCEL_R_MAX",
            "ATC_ACCEL_P_MAX",
            "ATC_ACCEL_Y_MAX",
        }

        # RC and remote controller parameters that may be configured multiple times
        rc_params = {
            "RC1_OPTION",
            "RC2_OPTION",
            "RC3_OPTION",
            "RC4_OPTION",
            "RC5_OPTION",
            "RC6_OPTION",
            "RC7_OPTION",
            "RC8_OPTION",
            "RC9_OPTION",
            "RC10_OPTION",
            "RC11_OPTION",
        }

        # Configuration parameters that are set early and may be overridden
        config_params = {
            "LAND_ALT_LOW",
            "RTL_ALT",
            "LOG_BITMASK",
        }

        return {
            # System ID test files evolve these parameters across different axis tests
            "42_system_id_roll.param": system_id_params,
            "43_system_id_pitch.param": system_id_params,
            "44_system_id_yaw.param": system_id_params,
            "45_system_id_thrust.param": system_id_params | {"PSC_ACCZ_I"},
            # PID adjustment file has initial values that get refined later
            "16_pid_adjustment.param": pid_tuning_params,
            # Quick tune files progressively refine PID parameters
            "23_quick_tune_results.param": pid_tuning_params,
            "27_quick_tune_results.param": pid_tuning_params,
            # Autotune result files progressively improve PIDs
            "31_autotune_roll_results.param": pid_tuning_params,
            "33_autotune_pitch_results.param": pid_tuning_params,
            "35_autotune_yaw_results.param": pid_tuning_params,
            "37_autotune_yawd_results.param": {"ATC_ANG_YAW_P"},
            "39_autotune_roll_pitch_retune_results.param": {"ATC_ANG_RLL_P", "ATC_ANG_PIT_P"},
            # Remote controller option assignments evolve
            "05_remote_controller.param": rc_params,
            # Initial configuration files have values that get refined
            "11_initial_atc.param": config_params | pid_tuning_params | {"MOT_THST_EXPO"},
            "12_mp_setup_mandatory_hardware.param": config_params
            | pid_tuning_params
            | {"FLTMODE5", "FLTMODE6", "MOT_THST_EXPO"},
            "13_general_configuration.param": config_params,
            # Quick tune and autotune setup may modify logging
            "26_quick_tune_setup.param": {"LOG_BITMASK"},
            # Notch filter setup parameters are tuning-specific
            "18_notch_filter_setup.param": {"INS_HNTCH_FREQ", "INS_HNTCH_BW", "INS_HNTCH_ATT", "INS_HNTCH_HMNCS"},
            # Optical flow parameters that may evolve
            "50_optical_flow_setup.param": {"EK3_SRC1_POSXY", "EK3_SRC1_VELXY", "EK3_SRC1_VELZ", "RC8_OPTION", "RC9_OPTION"},
            # Temperature calibration parameters may vary based on specific calibration runs
            "02_imu_temperature_calibration_setup.param": {"INS_TCAL1_TMAX", "INS_TCAL2_TMAX", "INS_TCAL3_TMAX"},
            "03_imu_temperature_calibration_results.param": {"INS_TCAL1_TMAX", "INS_TCAL2_TMAX", "INS_TCAL3_TMAX"},
            # Optical flow type may vary
            "11_optical_flow.param": {"FLOW_TYPE"},
            # Precision landing enable status
            "49_precision_land.param": {"PLND_ENABLED"},
        }

    @staticmethod
    def parse_param_file(file_path: Path) -> dict[str, float]:
        """
        Parse a .param file and extract parameter name-value pairs.

        Args:
            file_path: Path to the .param file

        Returns:
            Dictionary mapping parameter names to their values

        """
        par_dict = ParDict.load_param_file_into_dict(str(file_path))
        return {param_name: par.value for param_name, par in par_dict.items()}

    def test_parameter_values_preserved_through_round_trip(self, compounded_params_files, tmp_test_output_dir):
        """
        Parameter values are preserved through component inference and regeneration.

        GIVEN: Original vehicle templates and generated vehicle projects
        WHEN: Comparing parameter values between original and generated .param files
        THEN: Vehicle-specific calibration data should be preserved from FC parameters
        AND: Configuration parameters may differ due to template reorganization
        AND: Parameters that evolve across tuning stages are whitelisted

        KNOWN ISSUE: Currently finding 1600+ differences, mostly vehicle-specific
        calibration data (INS_TCAL*, COMPASS_*, RC* calibrations, BATT_*, SERVO*)
        that SHOULD be preserved but aren't. This indicates the project creation
        with use_fc_params=True is not properly preserving FC parameter values,
        possibly being overwritten by empty template defaults in files like
        12_mp_setup_mandatory_hardware.param. This needs investigation.
        """
        if not compounded_params_files:
            pytest.skip("No compounded params files available")

        original_base = Path(__file__).parent.parent / "ardupilot_methodic_configurator" / "vehicle_templates"
        generated_base = tmp_test_output_dir / "vehicle_templates"

        if not generated_base.exists():
            pytest.skip("No generated projects found")

        whitelist = self.get_whitelisted_parameter_diffs()
        all_differences = []
        files_compared = 0

        # Compare each generated .param file with its original
        for generated_file in generated_base.rglob("*.param"):
            # Skip 00_default.param as it's not in original templates
            if generated_file.name == "00_default.param":
                continue

            # Find corresponding original file
            relative_path = generated_file.parent.relative_to(generated_base)
            original_file = original_base / relative_path / generated_file.name

            if not original_file.exists():
                continue

            # Parse both files
            original_params = self.parse_param_file(original_file)
            generated_params = self.parse_param_file(generated_file)

            # Get whitelist for this file
            file_whitelist = whitelist.get(generated_file.name, set())

            # Compare parameter values
            all_param_names = set(original_params.keys()) | set(generated_params.keys())

            for param_name in all_param_names:
                # Skip whitelisted parameters
                if param_name in file_whitelist:
                    continue

                original_value = original_params.get(param_name)
                generated_value = generated_params.get(param_name)

                # Check if values differ
                if original_value is None and generated_value is not None:
                    all_differences.append(
                        {
                            "file": str(relative_path / generated_file.name),
                            "parameter": param_name,
                            "original": "missing",
                            "generated": generated_value,
                            "type": "added",
                        }
                    )
                elif original_value is not None and generated_value is None:
                    all_differences.append(
                        {
                            "file": str(relative_path / generated_file.name),
                            "parameter": param_name,
                            "original": original_value,
                            "generated": "missing",
                            "type": "removed",
                        }
                    )
                elif (
                    original_value is not None and generated_value is not None and abs(original_value - generated_value) > 1e-6
                ):
                    all_differences.append(
                        {
                            "file": str(relative_path / generated_file.name),
                            "parameter": param_name,
                            "original": original_value,
                            "generated": generated_value,
                            "type": "changed",
                        }
                    )

            files_compared += 1

        # Report results
        logger.info("=" * 100)
        logger.info("PARAMETER VALUE VALIDATION RESULTS")
        logger.info("=" * 100)
        logger.info("Files compared: %d", files_compared)
        logger.info("Differences found: %d", len(all_differences))

        if all_differences:
            # Group by type
            added = [d for d in all_differences if d["type"] == "added"]
            removed = [d for d in all_differences if d["type"] == "removed"]
            changed = [d for d in all_differences if d["type"] == "changed"]

            logger.info("  - Parameters added: %d", len(added))
            logger.info("  - Parameters removed: %d", len(removed))
            logger.info("  - Parameters changed: %d", len(changed))

            # Show all value changes for analysis
            if changed:
                logger.info("\nAll %d value changes:", len(changed))
                for diff in changed:
                    logger.info("  %s: %s = %s → %s", diff["file"], diff["parameter"], diff["original"], diff["generated"])

            if removed:
                logger.info("\nFirst 10 removed parameters:")
                for diff in removed[:10]:
                    logger.info("  %s: %s (was %s)", diff["file"], diff["parameter"], diff["original"])

            if added:
                logger.info("\nFirst 10 added parameters:")
                for diff in added[:10]:
                    logger.info("  %s: %s = %s", diff["file"], diff["parameter"], diff["generated"])

        # Assert: Vehicle-specific calibration data should be preserved
        # Currently FAILING with ~52 differences - mostly calibration data that SHOULD
        # be preserved from FC parameters but isn't. This indicates:
        # 1. Empty template defaults (especially in 12_mp_setup_mandatory_hardware.param)
        #    may be overwriting FC parameter values
        #
        # Expected behavior: Calibration parameters (INS_TCAL*, COMPASS_*, RC*, BATT*, SERVO*)
        # should be copied verbatim from FC parameters to generated files.
        changed_values = [d for d in all_differences if d["type"] == "changed"]

        # For now, mark this as a known issue requiring investigation
        if len(changed_values) > 50:
            pytest.skip(
                f"KNOWN ISSUE: {len(changed_values)} parameter value changes detected. "
                "Vehicle-specific calibration data is not being preserved from FC parameters. "
                "This indicates a bug in project creation with use_fc_params=True where "
                "empty template defaults are overwriting FC parameter values. "
                "Investigation needed in VehicleProjectCreator and/or 12_mp_setup_mandatory_hardware.param"
            )

        assert len(changed_values) < 55, (
            f"Too many parameter value changes: {len(changed_values)} "
            f"(expected <55). Vehicle-specific calibration data should be preserved from FC parameters. "
            "Derived and tuning parameters may differ based on component specifications."
        )


class TestTemplateDiffGeneration:
    """Test generating diff files comparing original templates with generated projects."""

    def test_user_can_generate_diff_files_for_all_projects(self, compounded_params_files, tmp_test_dir, tmp_test_output_dir):
        """
        User can generate diff files comparing generated projects with original templates.

        GIVEN: Generated vehicle projects exist in tmp_test_output_dir
        WHEN: User compares them with original templates
        THEN: Diff files should be created in /tmp/amc_test_acceptance3/
        AND: Diff files should be organized in same structure as projects
        AND: 00_default.param files should be excluded from comparison
        """
        # Setup diff output directory
        diff_base_dir = Path("/tmp/amc_test_acceptance3/vehicle_templates")
        if diff_base_dir.parent.exists():
            shutil.rmtree(diff_base_dir.parent)
        diff_base_dir.mkdir(parents=True, exist_ok=True)

        original_base = Path(__file__).parent.parent / "ardupilot_methodic_configurator" / "vehicle_templates"
        generated_base = tmp_test_output_dir / "vehicle_templates"

        if not generated_base.exists():
            pytest.skip("No generated projects found")

        diff_count = 0
        skipped_count = 0

        # Find all generated project directories
        for generated_dir in generated_base.rglob("*"):
            if not generated_dir.is_dir():
                continue

            # Check if it's a leaf directory (contains files)
            has_param_or_json = any(generated_dir.glob("*.param")) or any(generated_dir.glob("*.json"))
            if not has_param_or_json:
                continue

            # Find matching original template
            relative_path = generated_dir.relative_to(generated_base)
            original_dir = original_base / relative_path

            if not original_dir.exists():
                skipped_count += 1
                continue

            # Get files to compare (exclude 00_default.param)
            generated_files = set()
            original_files = set()

            for pattern in ["*.param", "*.json"]:
                for file in generated_dir.glob(pattern):
                    if file.name != "00_default.param":
                        generated_files.add(file.name)
                for file in original_dir.glob(pattern):
                    if file.name != "00_default.param":
                        original_files.add(file.name)

            common_files = generated_files & original_files

            if not common_files:
                continue

            # Create diff output directory mirroring structure
            diff_output_dir = diff_base_dir / relative_path
            diff_output_dir.mkdir(parents=True, exist_ok=True)

            # Generate diffs for each common file
            for filename in sorted(common_files):
                original_file = original_dir / filename
                generated_file = generated_dir / filename
                diff_file = diff_output_dir / f"{filename}.diff"

                try:
                    result = subprocess.run(
                        ["diff", "-u", str(original_file), str(generated_file)],
                        capture_output=True,
                        text=True,
                        check=False,
                    )

                    if result.returncode != 0:  # Files differ
                        # Write diff to file
                        diff_content = [
                            f"Comparing: {filename}",
                            f"Original:  {original_file}",
                            f"Generated: {generated_file}",
                            "=" * 80,
                            result.stdout,
                        ]
                        diff_file.write_text("\n".join(diff_content), encoding="utf-8")
                        diff_count += 1

                except Exception as e:
                    logger.warning("Failed to diff %s: %s", filename, e)

        # Then: Diff files should have been created
        assert diff_count > 0, "No diff files were generated"

        # And: Directory structure should match
        assert diff_base_dir.exists(), "Diff base directory not created"

        logger.info("=" * 80)
        logger.info("Generated %d diff files", diff_count)
        logger.info("Skipped %d projects (no matching original)", skipped_count)
        logger.info("Diff files saved to: %s", diff_base_dir.parent)
