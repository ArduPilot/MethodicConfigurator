# Add, delete or re-order configuration steps

This workflow primarily targets ArduCopter but the propagation step (step 15) covers other
vehicle types (`configuration_steps_ArduPlane.json`, `configuration_steps_Rover.json`,
`configuration_steps_Heli.json`).

## When to use `old_filenames` vs `backend_filesystem_migration.py`

- **Simple renames only** (no parameter moves, no new files, no deletions): add the old
  filename(s) to the `old_filenames` list of the new entry in `configuration_steps_*.json`.
  No migration code is needed. Skip steps 7–10 in this case.
- **Moving parameters between files, creating new files whose content is not derived from
  existing files, or deleting files entirely**: update `backend_filesystem_migration.py`
  as described in step 2 below.

## Steps

1. Update `ardupilot_methodic_configurator/configuration_steps_ArduCopter.json`:
    - Add new step entries or delete old ones.
    - For simple renames (no renumbering), manually add the old filename(s) to the
      `old_filenames` list of the new entry so existing vehicle projects migrate automatically
      on next launch. Skip steps 7–10 in this case.
    - When renumbering via `param_reorder.py` (steps 7–10), `old_filenames` is updated
      automatically — no manual edit needed here.
1. *(Skip if only simple renames are involved — handled by `old_filenames` above)*
   Update `ardupilot_methodic_configurator/backend_filesystem_migration.py`:
    - Increment `VEHICLE_COMPONENTS_FORMAT_VERSION`.
    - Add `_PARAM_MOVES_Vx_TO_Vy` (x = old version, y = new version) for any parameters
      that move from one file to another.
    - Add `_NEW_FILES_Vx_TO_Vy` for brand-new files whose content is not derived from
      any existing file.
    - Add `_FILES_TO_DELETE_Vx_TO_Vy` for files that are removed from the sequence.
1. Run the linters locally: `ruff format && ruff check --fix && ty check && mypy && pyright`
1. Commit the `configuration_steps_*.json` and `backend_filesystem_migration.py` changes to git.
1. Execute `python ./update_vehicle_templates.py` to propagate the changes across all vehicle
   template directories: it applies any `old_filenames` renames, updates `vehicle_components.json`
   structure, and recomputes and saves derived/forced parameter values.
1. Review the updated vehicle template directories and commit the results to git.
1. *(Skip if no files need renumbering or explicit renaming)*
   Edit the `file_renames` dict in `param_reorder.py` to map each old filename to its new
   filename. If you only need to auto-renumber files to match their position in the JSON
   sequence (e.g., after inserting or deleting a step), `file_renames` can remain empty —
   `param_reorder.py` will renumber based on sequence order automatically.
1. Run the linters locally: `ruff format && ruff check --fix && ty check && mypy && pyright`
1. Commit the `param_reorder.py` changes to git.
1. Execute `python ./param_reorder.py` to rename `.param` and `.pdef.xml` files on disk
   (using `git mv` when tracked), update all filename references in `*.py`, `*.json`, and
   `*.md` files across the repository, and populate `old_filenames` in
   `configuration_steps_ArduCopter.json` automatically. The script also validates that
   every old filename listed in `file_renames` is referenced in each `TUNING_GUIDE_*.md`
   file — check the output for errors if some references were not updated.
1. Review the renamed files and updated references, then commit the results to git.
1. Update `TUNING_GUIDE_ArduCopter.md` — pay special attention to section numbers and
   markdown anchor references that may have changed.
1. Update `ardupilot_methodic_configurator/configuration_steps_ArduCopter.json` to fix
   any cross-references to renamed tuning guide sections.
   Hand edit the "phases" -> "start" numbers to match the new groups.
1. Update `README.md` to reflect any added, removed, or reordered configuration steps.
1. Compare and propagate fixes to other vehicles (ArduPlane, Heli, Rover):
   - Compare `TUNING_GUIDE_ArduCopter.md` with the other vehicle tuning guides and update
     them accordingly.
   - Compare `ardupilot_methodic_configurator/configuration_steps_ArduCopter.json` with
     the other vehicle configuration steps files and update them accordingly.
   - Ensure each vehicle's `TUNING_GUIDE_*.md` retains its vehicle-type-specific content.
   - Ensure each `ardupilot_methodic_configurator/configuration_steps_*.json` references
     its own tuning guide, not the copter's tuning guide.
1. Run `pytest` and confirm all tests pass.
1. Commit all remaining changes to git.
