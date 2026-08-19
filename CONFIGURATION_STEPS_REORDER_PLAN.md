# Configuration Steps Reorder Plan

## Current State

As of the current worktree:

- Staged: `backend_filesystem_migration.py` with format version `2`, the v1-to-v2 parameter split, and new-file creation logic.
- Implemented: the focused migration regression test, including step 03
   ownership for `INS_ACC*_CALTEMP` and cleanup of the legacy file.
- Staged: `param_reorder.py` changes. Review this mapping against the current filenames before running it.
- Implemented in `empty_4.6.x`: the five populated files:
  - `14_accelerometer_calibration.param`
  - `15_accelerometer_level.param`
  - `16_compass_calibration.param`
  - `17_flight_modes.param`
  - `18_servo_outputs.param`
- Implemented: `level_calibration` and `servo_out` plugins, including plugin
  registration, schema entries, tuning-guide instructions, SPDX headers, and
  focused data-model and Tkinter-view tests.
- Implemented: servo-output recommendations use the selected FC-to-ESC
  connection as the first output bank. **Main Out** uses outputs 1–8 before
  continuing at AIO outputs 9–14; **AIO** uses outputs 9–14 before continuing
  at Main Out outputs 1–8.
- Not yet updated: `configuration_steps_*.json`, templates other than the
   `empty_4.6.x` ArduCopter template, README, and final references. The
   ArduCopter tuning guide is partially updated and intentionally retains the
   current filenames outside section 6.8 until the reorder script is run.
- Unrelated untracked files are present and must not be included accidentally:
   `00_default.param`, `complete.param`, `manual_override.md`, and the
   `Holybro_X500/gfg.bin` file.

## Plan

1. **Ownership map: complete.**
   - Compare every parameter in `14_mp_setup_mandatory_hardware.param` with the existing configuration-step files.
   - Move `INS_ACC*_CALTEMP` to step 03, not step 14.
   - Move accelerometer scaling and `INS_USE*` to step 14.
   - Move `AHRS_TRIM_X/Y` to step 15 and `COMPASS_*` to step 16.
   - Move `FLTMODE1-6` to step 17.
   - Move RC limits/trims to step 07 and `SERVO*_FUNCTION` to step 18.
   - Delete `FRAME_TYPE` and the remaining obsolete parameters from the
     legacy file; step 20 handles frame type indirectly.

2. **Prepare the configuration-step transformation; do not edit JSON by hand yet.**
   - `param_reorder.py` rewrites `configuration_steps_ArduCopter.json`, so it must own the sequence update.
   - Verify whether the script can create the five new step entries with their required metadata; currently it expects the new step keys to exist before it updates `old_filenames`.
   - Extend the script's sequence transformation if necessary, including insertion after `13_initial_atc.param`, metadata, phase starts, and later-step renumbering.
   - Keep the JSON file untouched until the script can generate the complete change, then review its output rather than manually editing it.
   - Apply the same reordered-step rules to ArduCopter, ArduPlane, Heli, and
     Rover for now. Maintain one unified transformation and metadata set across
     vehicle types; record any later vehicle-specific exception explicitly.

3. **Complete the migration definition: implemented.**
    - `VEHICLE_COMPONENTS_FORMAT_VERSION = 2` and the v1-to-v2 rules are present.
    - Migration creates all five destination files, preserves existing values,
       moves the owned parameters, and deletes obsolete residual parameters.
    - The old mandatory-hardware file is unlinked when no parameters remain.
    - After all move/add/delete work, migration restores any missing file named
      by the current vehicle's configuration steps from the matching empty
      firmware template. Template lookup reuses
      `VehicleProjectCreator.template_dir_for_bin_import()` so firmware `4.6.3`
      resolves to `empty_4.6.x`; existing project files are never overwritten.
    - The restoration regression test covers a missing configuration-step file
      and a `4.6.3` firmware version.
    - The full migration test module passes (`50 passed`); rerun after later JSON
       and template changes.

4. **Finish the empty 4.6.x template: parameter split complete.**
    - The five new files contain defaults from the legacy template.
    - RC defaults are in `07_remote_controller_controller.param`; servo
       functions are in `18_servo_outputs.param`.
    - `FRAME_TYPE` and accelerometer temperature defaults are no longer in the
       legacy file; temperature defaults are in step 03.
    - Re-run template uniqueness and prefix checks after the JSON reorder removes
       the temporary duplicate numeric prefixes.

5. **Run the scripted sequence and filename reorder.**
   - Review the `param_reorder.py` mappings against the current filenames, including `66_everyday_use.param`.
   - Run the script only after its sequence transformation can generate the five new JSON entries and the complete reordered sequence.
   - Ensure mappings use current names, including `66_everyday_use.param`, rather than historical names.
   - Run:
     `python .github/skills/configuration-steps-reorder/scripts/param_reorder.py`
   - Review all renames, `.pdef.xml` renames, JSON `old_filenames`, Python/Markdown references, and tuning-guide validation output.
   - Do not include unrelated untracked files in the result.

6. **Update documentation.**
   - Update `TUNING_GUIDE_ArduCopter.md` section numbers, anchors, and links for the new calibration and flight-mode steps.
   - Compare and update the ArduPlane, Heli, and Rover tuning guides only where their configuration sequences include the new steps.
   - Update `README.md`, `USERMANUAL.md`, and any other direct references to the old mandatory-hardware or later filenames.
   - Verify that each vehicle configuration JSON points to its own tuning guide.

7. **Validate the complete change.**
   - Run focused migration tests, including the step-03 temperature-calibration preservation case.
   - Run template integrity tests for unique parameters, valid prefixes, monotonic ordering, and schema validity.
   - Run `git diff --check`, Ruff, type checks configured by the project, and the complete migration test module.
   - Run the full pytest suite.
   - Review `git status`, staged and unstaged diffs, and the final list of renamed/created/deleted files.

8. **Stage only task files and review before committing.**
   - Stage the configuration JSON changes, migration changes, test changes, new template files, reorder results, and documentation updates.
   - Leave the unrelated untracked files untouched.
   - Make separate commits if the repository workflow requires the configuration/migration, reorder, template, and documentation phases to be reviewed independently.
