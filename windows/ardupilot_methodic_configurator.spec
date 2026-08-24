# -*- mode: python -*-
# spec file for pyinstaller to build ardupilot_methodic_configurator for windows

from PyInstaller.utils.hooks import collect_submodules
import certifi
import os
from pathlib import Path
import sys


def _find_tcl_tk_library(directory: Path, prefix: str) -> Path:
    """Return the Tcl/Tk library directory shipped with the build Python."""
    library_file = "init.tcl" if prefix == "tcl" else "tk.tcl"
    candidates = sorted(
        (path for path in directory.glob(f"{prefix}*") if path.is_dir() and (path / library_file).is_file()),
        reverse=True,
    )
    if not candidates:
        raise SystemExit(f"Could not find {prefix} library data below {directory}")
    return candidates[0]


# Set both variables before PyInstaller analyses tkinter so its built-in hook
# collects the library data into _tcl_data and _tk_data. Without this, the
# frozen application contains the DLLs but fails during the tkinter runtime hook.
tcl_root = Path(sys.base_prefix) / "tcl"
os.environ["TCL_LIBRARY"] = str(_find_tcl_tk_library(tcl_root, "tcl"))
os.environ["TK_LIBRARY"] = str(_find_tcl_tk_library(tcl_root, "tk"))

# Path to certifi's CA bundle
certifi_cacert = certifi.where()
datas = [(certifi_cacert, "certifi")]

ardupilot_methodic_configuratorAny = Analysis(['__main__.py'],
             pathex=[os.path.abspath('.')],
             # for some unknown reason these hidden imports don't pull in
             # all the needed pieces, so we also import them in __main__.py
             hiddenimports=['packaging', 'packaging.version', 'packaging.specifiers'] +
                            collect_submodules('ardupilot_methodic_configurator.modules') +
                            collect_submodules('pymavlink'),
             datas=datas,
             hookspath=None,
             runtime_hooks=None)

ardupilot_methodic_configurator_pyz = PYZ(ardupilot_methodic_configuratorAny.pure)

ardupilot_methodic_configurator_exe = EXE(ardupilot_methodic_configurator_pyz,
          ardupilot_methodic_configuratorAny.scripts,
          exclude_binaries=True,
          name='ardupilot_methodic_configurator.exe',
          debug=False,
          strip=None,
          upx=True,
          console=True)

ardupilot_methodic_configurator_coll = COLLECT(ardupilot_methodic_configurator_exe,
               ardupilot_methodic_configuratorAny.binaries,
               ardupilot_methodic_configuratorAny.zipfiles,
               ardupilot_methodic_configuratorAny.datas,
               strip=None,
               upx=True,
               name='ardupilot_methodic_configurator')
