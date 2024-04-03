# -*- mode: python -*-
# spec file for pyinstaller to build ardupilot_methodic_configurator for windows
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

MethodicConfiguratorAny = Analysis(['ardupilot_methodic_configurator.py'],
             pathex=[os.path.abspath('.')],
             # for some unknown reason these hidden imports don't pull in
             # all the needed pieces, so we also import them in ardupilot_methodic_configurator.py
             hiddenimports=['packaging', 'packaging.version', 'packaging.specifiers',
                            'pkg_resources.py2_warn'] + collect_submodules('MethodicConfigurator.modules') + 
                            collect_submodules('pymavlink'),
             datas= [ ('modules\\ardupilot_methodic_configurator_map\\data\\*.*', 'MethodicConfigurator\\modules\\ardupilot_methodic_configurator_map\\data' ),
                      ('modules\\ardupilot_methodic_configurator_joystick\\joysticks\\*.*', 'MethodicConfigurator\\modules\\ardupilot_methodic_configurator_joystick\\joysticks' )],
             hookspath=None,
             runtime_hooks=None,
             excludes= ['FixTk', 'tcl', 'tk', '_tkinter', 'tkinter', 'Tkinter'])
# MERGE( (MethodicConfiguratorAny, 'ardupilot_methodic_configurator', 'ardupilot_methodic_configurator') )
MethodicConfigurator_pyz = PYZ(MethodicConfiguratorAny.pure)
MethodicConfigurator_exe = EXE(MethodicConfigurator_pyz,
          MethodicConfiguratorAny.scripts,
          exclude_binaries=True,
          name='ardupilot_methodic_configurator.exe',
          debug=False,
          strip=None,
          upx=True,
          console=True )
MethodicConfigurator_coll = COLLECT(MethodicConfigurator_exe,
               MethodicConfiguratorAny.binaries,
               MethodicConfiguratorAny.zipfiles,
               MethodicConfiguratorAny.datas,
               strip=None,
               upx=True,
               name='ardupilot_methodic_configurator')
