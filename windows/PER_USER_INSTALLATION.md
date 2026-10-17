<!-- SPDX-FileCopyrightText: 2026 ArduPilot methodic configurator developers -->
<!-- SPDX-License-Identifier: GPL-3.0-or-later -->

# Windows per-user installation handoff

## Scope and path contract

This work targets the official ArduPilot Methodic Configurator **v4.5.6** source
(`ardupilot_methodic_configurator/__init__.py`). Both the installer and runtime
need changes: the installer must put the executable, templates, shortcuts, and
optional PATH entry in the selected scope; the Python runtime must then find the
same templates without trying to create or write to machine-wide configuration
directories.

| Mode | How to select it | Expected locations and effects |
| --- | --- | --- |
| Per-user (default) | No override, or explicitly `/CURRENTUSER` | No admin install requirement; `{autopf}`, `{autoappdata}`, and `{autodesktop}` resolve to the current user's locations. The app's settings, vehicles, and templates are under roaming `APPDATA`. PATH changes are user-scoped. |
| All users (explicit) | `/ALLUSERS` | Administrative installation; auto constants resolve to machine-wide locations. The machine PATH task is available only in admin install mode. Use only with authorized administrator approval. |

`PrivilegesRequired=lowest` makes the ordinary install non-elevated.
`PrivilegesRequiredOverridesAllowed=commandline` enables `/CURRENTUSER` and
`/ALLUSERS`. `UsePreviousPrivileges=no` means do not rely on a prior install to
select scope: pass `/ALLUSERS` when intentionally upgrading a machine install.
The Inno Setup `auto` constants select their user or common counterpart based
on install mode. In per-user mode, `{autoappdata}` is the user's roaming
Application Data directory (`%APPDATA%`). That matches the runtime's
`user_config_dir(".ardupilot_methodic_configurator", appauthor=False,
roaming=True)` call in
`ardupilot_methodic_configurator/backend_filesystem_program_settings.py`.
Runtime discovery prefers the user's installed templates, then reads existing
shared templates without creating a shared configuration directory, and
otherwise uses packaged templates.

In-app updates explicitly pass `/CURRENTUSER` or `/ALLUSERS` according to the
running executable's `installation-scope.ini` marker. Older installations
without a valid marker retain machine scope when their executable directory
matches the application's HKLM uninstall record in either registry view.
A separate machine installation does not change a user copy's update scope.
Source and unregistered installations default to `/CURRENTUSER`.

Relevant primary documentation:

- Inno Setup [`PrivilegesRequired`](https://jrsoftware.org/ishelp/index.php?topic=setup_privilegesrequired),
  [`PrivilegesRequiredOverridesAllowed`](https://jrsoftware.org/ishelp/index.php?topic=setup_privilegesrequiredoverridesallowed),
  and [`UsePreviousPrivileges`](https://jrsoftware.org/ishelp/index.php?topic=setup_usepreviousprivileges).
- Inno Setup [constants](https://jrsoftware.org/ishelp/index.php?topic=consts),
  including the `auto`, `userappdata`, `autopf`, and `autodesktop` constants.
- platformdirs [`user_config_dir`](https://platformdirs.readthedocs.io/en/latest/api.html#platformdirs.user_config_dir)
  and its [Windows path behavior](https://platformdirs.readthedocs.io/en/latest/platforms.html#windows).
- PyInstaller [spec-file `EXE` options](https://pyinstaller.org/en/stable/spec-files.html);
  `windows/ardupilot_methodic_configurator.spec` explicitly sets
  `uac_admin=False` and `uac_uiaccess=False`.

## Signing and installer build

The existing Windows build is defined in
`.github/workflows/build_windows_macos.yml`: it builds the frozen application,
then compiles the Inno Setup script and uploads the installer artifact.
An unsigned local test installer was built on October 16, 2026; see the
verification status below. The workflow was not dispatched and no artifact
was uploaded to GitHub. End-to-end installation remains untested.

If a publisher has an approved signing identity and signing process:

1. After PyInstaller has produced
   `ardupilot_methodic_configurator/dist/ardupilot_methodic_configurator/ardupilot_methodic_configurator.exe`,
   sign that application EXE **before** compiling the installer. Verify its
   signature using the publisher's approved verification command.
2. Optionally register an Inno Setup sign tool at compile time and define
   `MyAppSignTool` to its name. The existing conditional in
   `windows/ardupilot_methodic_configurator.iss` then activates
   `SignTool={#MyAppSignTool}` and `SignedUninstaller=yes`, allowing Inno Setup
   to sign the setup and uninstaller. The compiler options are `/S<name>=<sign
   command>` and `/DMyAppSignTool=<name>` (alongside the version define and
   script path); see the official [ISCC command-line reference](https://jrsoftware.org/ishelp/index.php?topic=compilercmdline),
   [`SignTool` directive](https://jrsoftware.org/ishelp/index.php?topic=setup_signtool),
   and [`SignedUninstaller`](https://jrsoftware.org/ishelp/index.php?topic=setup_signeduninstaller).
   Supply the real signing command and timestamp service through the
   organization-approved build environment. Do not put private keys,
   passwords, or credentials in this repository, script, or command history.

Signing and per-user installation do not bypass enterprise controls such as
EPM, AppLocker, or WDAC. Do not remove Mark-of-the-Web, disable security
controls, or work around administrator policy. A certificate or signing
service is **not assumed to be available**.

## Uninstall scope preservation

Inno Setup's [`IsAdminInstallMode` reference](https://jrsoftware.org/ishelp/index.php?topic=isxfunc_isadmininstallmode)
states that its uninstaller result depends on current administrative
privileges. The installer therefore records its original scope and installing
username in `{app}\installation-scope.ini`. The PATH uninstall helper reads
this record instead of inferring scope from current privileges, and restores
the original user/system PATH selection from the matching uninstall registry
entry.

An elevated uninstall under the same installing account still selects that
account's HKCU record for a per-user installation. If the record is missing,
or a per-user uninstaller is run as a different account, PATH cleanup is
conservatively skipped rather than modifying the wrong account's environment.
For per-user PATH cleanup, run uninstall as the installing user.
The marker entries/file are removed during uninstall.

The regression suite checks this source contract, but does not execute a real
elevated Windows uninstaller. That remains part of the VM checklist below.
INI entries use the documented `uninsdeleteentry` and
`uninsdeletesectionifempty` flags; the dedicated marker file is removed by
`[UninstallDelete]`, because `[INI]` has no `uninsdeletefileifempty` flag.

## Python builds with embedded Tcl/Tk data

The Windows PyInstaller spec also accepts `AMC_TCL_TK_ROOT`, an optional
directory containing matching `tcl*` and `tk*` library directories with
`init.tcl` and `tk.tcl`. Without the variable it uses the build Python's
standard `tcl` directory, as before. Both data directories are explicitly
collected into `_tcl_data` and `_tk_data`.

The local test-build Python 3.14.8 from uv uses Tcl/Tk 9.0 with embedded
zipfs libraries. Its DLLs contain ZIP archives named `tcl_library/` and
`tk_library/`. The build helper extracts those same-runtime libraries into
an isolated build directory and sets `AMC_TCL_TK_ROOT`; it does not modify
the Python installation or mix Tcl/Tk versions. This extra step is not
needed when the normal Python distribution provides unpacked library data.

## Verification status: October 16, 2026

- The **13-test regression
  suite** passed, including the compiler-corrected marker cleanup contract:
  `Ran 13 tests ... OK`, exit status 0. Earlier sandbox TEMP failures were
  resolved by an approved run outside the sandbox with isolated workspace
  TEMP/TMP directories.
- PyInstaller **6.20.0** with hooks **2026.6** successfully built the Windows
  x64 application using Python **3.14.8**, uv **0.12.23** and the pinned
  Windows dependencies. The workflow's Python patch version is 3.14.6,
  so this is not a byte-for-byte reproduction of its environment.
- Frozen plugin/log-analysis module verification passed. Both Tcl/Tk
  library entry files were present. The frozen `--validate-plugins` and
  fixture `--validate-bin-log` commands returned 0. An empty log was
  rejected with a nonempty message and no traceback, as required by CI.
- Inno Setup **6.7.1** successfully compiled
  `ardupilot_methodic_configurator_4.5.6_windows_user_test_setup.exe`.
  A temporary build-drive mapping avoided Windows source-path length
  limits; the mapping was removed afterward. The compiler emitted a
  non-fatal hint about the existing `IsTaskSelected` compatibility name.
- Inspection of both the setup and application PE manifests found
  `requestedExecutionLevel="asInvoker"` and `uiAccess="false"`.
  The test installer is **unsigned** (`NotSigned`).

The source patch was checked against isolated copies of the official v4.5.6
files with `git apply --check`; this checks patch applicability, **not**
application or installer behavior. Focused existing pytest tests, Ruff and
full pre-commit checks have not been completed here. The installer itself
was **not executed**: installation, GUI startup, upgrade, uninstall,
hardware behavior and enterprise-policy acceptance remain untested.
No complete application test-suite result or signed release is claimed.

Run the narrow regressions in the publisher's approved development environment:

```powershell
$env:TEMP = Join-Path $PWD ".verification-temp"
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Path $env:TEMP -Force | Out-Null
python -m unittest discover -s tests -p test_windows_user_installation.py -v
```

Before merging, also run the repository's normal pytest/pre-commit checks and
compile the installer through the existing Windows build workflow.

## Clean standard-user VM checklist

1. Use a disposable, clean Windows VM and a standard user with no admin
   credentials. Keep an independent backup/snapshot of any test profile data.
2. Install with `/CURRENTUSER`; verify there is no elevation prompt, the EXE is
   under the user's Programs location, shortcuts are user-scoped, templates
   are in `%APPDATA%\.ardupilot_methodic_configurator\vehicle_templates`, and
   the app can load them and start.
3. Create test settings and a user vehicle under
   `%APPDATA%\.ardupilot_methodic_configurator`; upgrade in the same scope.
   Verify settings and user vehicles remain intact and bundled templates are
   refreshed without deleting the application root.
4. Uninstall the per-user copy; verify its shortcuts/program files are removed
   while the user's settings and vehicles remain. Also verify only the
   selected user PATH entry is removed, including the elevated-uninstaller
   regression described above.
5. On a separate VM or snapshot, test `/ALLUSERS` with authorized administrator
   credentials. Confirm elevation, shared install/template locations, optional
   system PATH behavior, upgrade, and uninstall. Do not treat this as evidence
   that the standard-user path bypasses or satisfies enterprise policy.
