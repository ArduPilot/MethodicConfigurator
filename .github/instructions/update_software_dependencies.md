<!--
SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
-->

# Adding or Updating Software Dependencies

This document describes the full workflow for adding a new dependency or updating an existing one in the
ArduPilot Methodic Configurator project.
It is intended for both human contributors and AI agents.

All steps must be completed in order for the project to remain REUSE-compliant and its dependency
credits to stay accurate and up to date.

## Overview

```text
pyproject.toml  →  credits/CREDITS.md  →  credits/update_credits_licenses.py
    →  run script to download license files  →  REUSE.toml
```

---

## Step 1 — Add the dependency to `pyproject.toml`

Add the package to the appropriate section of `pyproject.toml`:

- Runtime dependency → `[project] dependencies`
- Development tooling → `[project.optional-dependencies] dev`
- CI-only → `[project.optional-dependencies] ci_headless_tests`

Pin the exact version (use `==`).
For packages sensitive to the Python runtime version, use environment markers (e.g., `python_version < '3.10'`).

---

## Step 2 — Update `credits/CREDITS.md`

Add a row to the appropriate table in `credits/CREDITS.md`:

- **Direct** runtime or GUI dependencies → "It directly uses:" table
- **Indirect** (transitive) dependencies → "It indirectly uses:" table

Each row must have:

| Column   | Content                                                      |
|----------|--------------------------------------------------------------|
| Software | Markdown link to project homepage                            |
| License  | Markdown link to the license URL on the project's repository |

The author name (e.g., "by Mark Pointing") must be included in the Software column whenever
it is known and the dependency is from an individual contributor rather than an organisation.

Example row for a direct dependency:

```markdown
| [simpleeval](https://github.com/danthedeckie/simpleeval) | [MIT License](https://github.com/danthedeckie/simpleeval/blob/main/LICENCE) |
```

---

## Step 3 — Update `credits/update_credits_licenses.py`

Add the new package to the correct list in `credits/update_credits_licenses.py`:

- `direct_dependencies` — for packages listed in the direct-use table
- `indirect_dependencies` — for packages listed in the indirect-use table

Each entry is a dict with two keys:

```python
{"name": "<PackageName>", "license_url": "<raw-URL-to-license-file>"}
```

Rules for the URL:

- Use a **raw** URL that serves the plain-text license (e.g., `https://raw.githubusercontent.com/...`)
- The filename at the end of the URL determines the downloaded file's suffix
  (e.g., `…/main/LICENCE` → `<PackageName>-LICENCE`)
- For packages hosted on Mozilla's site (MPL-2.0) provide `https://mozilla.org/MPL/2.0/` and the
  download function will use a fixed HTML filename automatically (see `Scrollable_TK_frame`,
  `Python_Tkinter_ComboBox`)

---

## Step 4 — Run the download script

Execute the script from the `credits/` directory.
It reads both lists and downloads each license file:

```bash
cd credits
python update_credits_licenses.py
```

The script saves each file as `<PackageName>-<license-filename>` in the current directory.
Check the output log to confirm all downloads succeeded.
Re-run if any fail due to network errors.

---

## Step 5 — Add entries to `REUSE.toml`

For each newly downloaded license file, append an `[[annotations]]` block to `REUSE.toml`
with the correct path, copyright notice, and SPDX license identifier.

### Finding the copyright holder

1. Open the downloaded license file (e.g., `credits/simpleeval-LICENCE`).
2. Look for a line starting with `Copyright` or `©` at the top.
3. If the license file contains no copyright notice, use the project author name from the
   corresponding entry in `credits/CREDITS.md` or the package's repository.

### Choosing the SPDX identifier

Use the canonical [SPDX license list](https://spdx.org/licenses/).
Common mappings:

| License text says                  | SPDX-License-Identifier |
|------------------------------------|-------------------------|
| MIT License                        | `MIT`                   |
| Apache License, Version 2.0        | `Apache-2.0`            |
| BSD 2-Clause                       | `BSD-2-Clause`          |
| BSD 3-Clause                       | `BSD-3-Clause`          |
| Mozilla Public License 2.0         | `MPL-2.0`               |
| GNU General Public License v3      | `GPL-3.0-or-later`      |
| GNU Lesser GPL v3                  | `LGPL-3.0-or-later`     |
| Python Software Foundation License | `PSF-2.0`               |
| MIT-CMU License (Pillow)           | `MIT-CMU`               |

If no standard SPDX identifier exists (e.g., Inno Setup proprietary license), use a
`LicenseRef-` identifier (e.g., `LicenseRef-Inno-Setup`) and place the license text in
`LICENSES/LicenseRef-Inno-Setup.txt`.

### Example `REUSE.toml` block

```toml
[[annotations]]
path = "credits/simpleeval-LICENCE"
SPDX-FileCopyrightText = "Copyright (c) 2013 Daniel Fairhead"
SPDX-License-Identifier = "MIT"
```

For files that have no copyright notice at all (e.g., the Apache 2.0 generic license text at
`argparse_check_range-LICENSE-2.0`), credit the known package author:

```toml
[[annotations]]
path = "credits/argparse_check_range-LICENSE-2.0"
SPDX-FileCopyrightText = "Dmitriy Kovalev"
SPDX-License-Identifier = "Apache-2.0"
```

---

## Step 6 — Verify REUSE compliance

```bash
reuse lint
```

All reported errors must be resolved before committing.
Common errors and fixes:

| Error                                    | Fix                                                              |
|------------------------------------------|------------------------------------------------------------------|
| `credits/<file>: no license identifier`  | Add the `SPDX-License-Identifier` to the REUSE.toml annotation   |
| `credits/<file>: no copyright notice`    | Add `SPDX-FileCopyrightText` to the REUSE.toml annotation        |
| `Missing license file LICENSES/<ID>.txt` | Add the license text to `LICENSES/` when using `LicenseRef-` IDs |

---

## Step 7 — Run pre-commit checks

```bash
pre-commit run --all
```

All hooks must pass (ruff, pylint, mypy, reuse, etc.) before pushing.

---

## Summary checklist

- [ ] `pyproject.toml` — dependency added with pinned version
- [ ] `credits/CREDITS.md` — row added to the correct table
- [ ] `credits/update_credits_licenses.py` — entry added to the correct list
- [ ] License file downloaded (`cd credits && python update_credits_licenses.py`)
- [ ] `REUSE.toml` — `[[annotations]]` block added for each new license file
- [ ] `reuse lint` passes
- [ ] `pre-commit run --all` passes
