# Verify the installed commands in a new PowerShell session with profiles enabled.
# SPDX-FileCopyrightText: 2026 ArduPilot Methodic Configurator contributors
# SPDX-License-Identifier: GPL-3.0-or-later
$ErrorActionPreference = 'Stop'
$app = Join-Path $env:LOCALAPPDATA 'Programs\ardupilot_methodic_configurator'
$manifest = Get-Content -LiteralPath (Join-Path $app '_internal\project_scripts.json') -Raw | ConvertFrom-Json
$names = @($manifest.PSObject.Properties.Name)
if ($names.Count -ne 10) { throw "Expected 10 scripts, got $($names.Count)." }
foreach ($name in $names) {
    $cmd = Get-Command $name -CommandType Application | Select-Object -First 1
    if (-not $cmd.Source.StartsWith($app + '\', [StringComparison]::OrdinalIgnoreCase)) { throw "Unexpected command path for $name" }
    $line = "$name --he"
    $completions = [Management.Automation.CommandCompletion]::CompleteInput($line, $line.Length, $null).CompletionMatches.CompletionText
    if (-not ($completions | Where-Object { $_ -like '--help*' })) { throw "Completion failed for $name" }
}
$line = 'amc_parameter_export --baud'
$completions = [Management.Automation.CommandCompletion]::CompleteInput($line, $line.Length, $null).CompletionMatches.CompletionText
if (-not ($completions | Where-Object { $_ -like '--baudrate*' })) { throw 'Baudrate completion failed.' }
Write-Output "PowerShell $($PSVersionTable.PSVersion): all 10 commands resolve and complete; --baud completes to --baudrate."
