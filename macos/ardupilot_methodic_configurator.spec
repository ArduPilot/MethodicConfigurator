# -*- mode: python -*-
# spec file for pyinstaller to build ardupilot_methodic_configurator for macOS

from PyInstaller.utils.hooks import collect_data_files, collect_submodules
import certifi
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PACKAGE_ROOT = os.path.join(PROJECT_ROOT, "ardupilot_methodic_configurator")


def _read_version() -> str:
    version_file = os.path.join(PACKAGE_ROOT, "__init__.py")
    with open(version_file, encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("__version__"):
                return line.split("=", 1)[1].strip().strip("\"'")
    return "0.0.0"


version = _read_version()

certifi_cacert = certifi.where()

datas = [(certifi_cacert, "certifi")]

git_hash_path = os.path.join(PROJECT_ROOT, "git_hash.txt")
if os.path.exists(git_hash_path):
    datas.append((git_hash_path, "ardupilot_methodic_configurator"))

datas += collect_data_files("ardupilot_methodic_configurator")

hidden_imports = [
    "packaging",
    "packaging.version",
    "packaging.specifiers",
] + collect_submodules("ardupilot_methodic_configurator.modules") + collect_submodules("pymavlink")

analysis = Analysis(
    [os.path.join(PACKAGE_ROOT, "__main__.py")],
    pathex=[PROJECT_ROOT, PACKAGE_ROOT],
    hiddenimports=hidden_imports,
    datas=datas,
    hookspath=None,
    runtime_hooks=None,
)

pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    exclude_binaries=True,
    name="ardupilot_methodic_configurator",
    debug=False,
    strip=False,
    upx=True,
    console=False,
)

coll = COLLECT(
    exe,
    analysis.binaries,
    analysis.zipfiles,
    analysis.datas,
    strip=False,
    upx=True,
    name="ardupilot_methodic_configurator",
)

icon_path = os.path.join(PROJECT_ROOT, "macos", "ArduPilotMethodicConfigurator.icns")
if not os.path.exists(icon_path):
    icon_path = None

app = BUNDLE(
    coll,
    name="ArduPilot Methodic Configurator.app",
    icon=icon_path,
    bundle_identifier="org.ardupilot.methodicconfigurator",
    info_plist={
        "CFBundleName": "ArduPilot Methodic Configurator",
        "CFBundleDisplayName": "ArduPilot Methodic Configurator",
        "CFBundleShortVersionString": version,
        "CFBundleVersion": version,
        "NSHighResolutionCapable": True,
    },
)
