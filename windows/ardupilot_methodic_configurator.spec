# -*- mode: python -*-
# spec file for pyinstaller to build ardupilot_methodic_configurator for windows

from PyInstaller.utils.hooks import collect_submodules
import certifi
import os

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
