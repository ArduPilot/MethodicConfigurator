# https://github.com/kislyuk/argcomplete/tree/main/contrib#powershell-support
#
# SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>
#
# SPDX-License-Identifier: GPL-3.0-or-later

# Import this module from your PowerShell profile to enable tab completion.
$commands = @(
    'ardupilot_methodic_configurator',
    'extract_param_defaults',
    'annotate_params',
    'param_pid_adjustment_update',
    'mavftp',
    'amc_mavftp',
    'amc_parameter_compare_and_upload',
    'amc_parameter_export',
    'amc_mavlink_inspector',
    'amc_firmware_upload'
)

Register-ArgumentCompleter -Native -CommandName $commands -ScriptBlock {
    param($wordToComplete, $commandAst, $cursorPosition)

    $variables = @(
        'ARGCOMPLETE_USE_TEMPFILES', '_ARGCOMPLETE_STDOUT_FILENAME', 'COMP_LINE',
        'COMP_POINT', '_ARGCOMPLETE', '_ARGCOMPLETE_SUPPRESS_SPACE',
        '_ARGCOMPLETE_IFS', '_ARGCOMPLETE_SHELL'
    )
    $previous = @{}
    $present = @{}
    foreach ($name in $variables) {
        $present[$name] = Test-Path -LiteralPath "Env:$name"
        if ($present[$name]) { $previous[$name] = (Get-Item -LiteralPath "Env:$name").Value }
    }
    $completionFile = New-TemporaryFile
    try {
        $line = $commandAst.Extent.Text
        $point = $cursorPosition - $commandAst.Extent.StartOffset
        if ($point -gt $line.Length) { $line = $line.PadRight($point) }
        $env:ARGCOMPLETE_USE_TEMPFILES = '1'
        $env:_ARGCOMPLETE_STDOUT_FILENAME = $completionFile.FullName
        $env:COMP_LINE = $line
        $env:COMP_POINT = [string]$point
        $env:_ARGCOMPLETE = '1'
        $env:_ARGCOMPLETE_SUPPRESS_SPACE = '0'
        $env:_ARGCOMPLETE_IFS = "`n"
        $env:_ARGCOMPLETE_SHELL = 'powershell'

        $commandName = $commandAst.GetCommandName()
        & $commandName 2>$null | Out-Null
        Get-Content -LiteralPath $completionFile.FullName | ForEach-Object {
            [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_)
        }
    } finally {
        Remove-Item -LiteralPath $completionFile.FullName -ErrorAction SilentlyContinue
        foreach ($name in $variables) {
            if ($present[$name]) {
                Set-Item -LiteralPath "Env:$name" -Value $previous[$name]
            } else {
                Remove-Item -LiteralPath "Env:$name" -ErrorAction SilentlyContinue
            }
        }
    }
}
