# Command line completion for the Ardupilot Methodic Configurator PowerShell scripts

# This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

# SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

# SPDX-License-Identifier: GPL-3.0-or-later

using namespace System.Management.Automation

Register-ArgumentCompleter -CommandName @(
    'ardupilot_methodic_configurator',
    'extract_param_defaults',
    'annotate_params',
    'param_pid_adjustment_update',
    'extract_missing_translations',
    'insert_translations'
) -ScriptBlock {
    param($commandName, $parameterName, $wordToComplete, $commandAst, $fakeBoundParameters)

    switch ($commandName) {
        'ardupilot_methodic_configurator' {
            @(
                '--help',
                '--version',
                '--device',
                '--reboot-time',
                '--vehicle-type',
                '--vehicle-dir',
                '--n',
                '--allow-editing-template-files',
                '--skip-component-editor',
                '--skip-check-for-updates',
                '--loglevel',
                '--language'
            ) -like "$wordToComplete*"

            # Additional completions for specific parameters
            if ($fakeBoundParameters.ContainsKey('--vehicle-type')) {
                @('AP_Periph', 'AntennaTracker', 'ArduCopter', 'ArduPlane', 'ArduSub', 'Blimp', 'Heli', 'Rover', 'SITL') -like "$wordToComplete*"
            }
            if ($fakeBoundParameters.ContainsKey('--loglevel')) {
                @('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL') -like "$wordToComplete*"
            }
            if ($fakeBoundParameters.ContainsKey('--language')) {
                @('en', 'zh_CN', 'pt', 'de', 'it') -like "$wordToComplete*"
            }
        }
        'extract_missing_translations' {
            @(
                '--help',
                '--lang-code',
                '--output-file',
                '--max-translations'
            ) -like "$wordToComplete*"

            if ($fakeBoundParameters.ContainsKey('--lang-code')) {
                @('en', 'zh_CN', 'pt', 'de', 'it') -like "$wordToComplete*"
            }
        }
        'insert_translations' {
            @(
                '--help',
                '--lang-code',
                '--input-file',
                '--output-file'
            ) -like "$wordToComplete*"

            if ($fakeBoundParameters.ContainsKey('--lang-code')) {
                @('en', 'zh_CN', 'pt', 'de', 'it') -like "$wordToComplete*"
            }
        }
        'extract_param_defaults' {
            @(
                '--help',
                '--format',
                '--sort',
                '--version',
                '--sysid',
                '--compid',
                '--type'
            ) -like "$wordToComplete*"

            if ($fakeBoundParameters.ContainsKey('--format')) {
                @('missionplanner', 'mavproxy', 'qgcs') -like "$wordToComplete*"
            }
            if ($fakeBoundParameters.ContainsKey('--sort')) {
                @('none', 'missionplanner', 'mavproxy', 'qgcs') -like "$wordToComplete*"
            }
            if ($fakeBoundParameters.ContainsKey('--type')) {
                @('defaults', 'values', 'non_default_values') -like "$wordToComplete*"
            }
        }
        'annotate_params' {
            @(
                '--help',
                '--delete-documentation-annotations',
                '--firmware-version',
                '--sort',
                '--vehicle-type',
                '--max-line-length',
                '--verbose',
                '--version'
            ) -like "$wordToComplete*"

            if ($fakeBoundParameters.ContainsKey('--sort')) {
                @('none', 'missionplanner', 'mavproxy') -like "$wordToComplete*"
            }
            if ($fakeBoundParameters.ContainsKey('--vehicle-type')) {
                @('AP_Periph', 'AntennaTracker', 'ArduCopter', 'ArduPlane', 'ArduSub', 'Blimp', 'Heli', 'Rover', 'SITL') -like "$wordToComplete*"
            }
        }
        'param_pid_adjustment_update' {
            @(
                '--help',
                '--directory',
                '--adjustment_factor',
                '--version'
            ) -like "$wordToComplete*"

            if ($fakeBoundParameters.ContainsKey('--directory')) {
                # Return directory paths for completion
                Get-ChildItem -Directory | Select-Object -ExpandProperty Name
            }
            if ($fakeBoundParameters.ContainsKey('--adjustment_factor')) {
                # Suggest common adjustment factor values in valid range
                @('0.1', '0.2', '0.3', '0.4', '0.5', '0.6', '0.7', '0.8') -like "$wordToComplete*"
            }
        }
        'mavftp' {
            # Main commands
            if (-not $fakeBoundParameters.Count) {
                @(
                    'get',
                    'getparams',
                    'put',
                    'list',
                    'mkdir',
                    'rmdir',
                    'rm',
                    'rename',
                    'crc'
                ) -like "$wordToComplete*"
            }

            # Global options
            @(
                '--help',
                '--baudrate',
                '--device',
                '--source-system',
                '--loglevel',
                '--debug',
                '--pkt_loss_tx',
                '--pkt_loss_rx',
                '--max_backlog',
                '--burst_read_size',
                '--write_size',
                '--write_qsize',
                '--idle_detection_time',
                '--read_retry_time',
                '--retry_time'
            ) -like "$wordToComplete*"

            # Parameter-specific completions
            if ($fakeBoundParameters.ContainsKey('--debug')) {
                @('0', '1', '2') -like "$wordToComplete*"
            }
            if ($fakeBoundParameters.ContainsKey('--loglevel')) {
                @('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL') -like "$wordToComplete*"
            }
        }
    }
}