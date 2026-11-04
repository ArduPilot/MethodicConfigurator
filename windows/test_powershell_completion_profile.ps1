# Verify profile registration preserves existing profile bytes and can be removed.
# SPDX-FileCopyrightText: 2026 ArduPilot Methodic Configurator contributors
# SPDX-License-Identifier: GPL-3.0-or-later
param([string]$Helper = (Join-Path $PSScriptRoot 'powershell_completion_profile.ps1'))
$ErrorActionPreference = 'Stop'
$directory = Join-Path ([IO.Path]::GetTempPath()) ('amc-profile-test-' + [guid]::NewGuid())
[void][IO.Directory]::CreateDirectory($directory)
try {
    $module = "C:\Example's path\completion.psm1"
    $encodings = @([Text.Encoding]::Unicode, [Text.Encoding]::BigEndianUnicode, [Text.Encoding]::UTF8, [Text.Encoding]::ASCII)
    foreach ($encoding in $encodings) {
        $file = Join-Path $directory ($encoding.WebName + '.ps1')
        [IO.File]::WriteAllText($file, "# Existing profile`r`n", $encoding)
        $before = [Convert]::ToBase64String([IO.File]::ReadAllBytes($file))
        & $Helper -Action Register -ModulePath $module -ProfilePaths $file
        $once = [Convert]::ToBase64String([IO.File]::ReadAllBytes($file))
        & $Helper -Action Register -ModulePath $module -ProfilePaths $file
        if ([Convert]::ToBase64String([IO.File]::ReadAllBytes($file)) -ne $once) { throw 'Registration is not idempotent.' }
        & $Helper -Action Remove -ModulePath $module -ProfilePaths $file
        if ([Convert]::ToBase64String([IO.File]::ReadAllBytes($file)) -ne $before) { throw 'Profile content was not preserved.' }
    }
    $new = Join-Path $directory 'new-profile.ps1'
    & $Helper -Action Register -ModulePath $module -ProfilePaths $new
    & $Helper -Action Remove -ModulePath $module -ProfilePaths $new
    if (Test-Path -LiteralPath $new) { throw 'Empty created profile was not removed.' }
    $bad = Join-Path $directory 'broken-profile.ps1'
    [IO.File]::WriteAllText($bad, '# BEGIN ArduPilot Methodic Configurator completion')
    $failed = $false
    try { & $Helper -Action Register -ModulePath $module -ProfilePaths $bad } catch { $failed = $true }
    if (-not $failed) { throw 'Malformed markers were accepted.' }
    if ([IO.File]::ReadAllText($bad) -ne '# BEGIN ArduPilot Methodic Configurator completion') { throw 'Malformed profile was changed.' }
    $foreign = Join-Path $directory 'foreign-profile.ps1'
    $owned = Join-Path $directory 'owned-profile.ps1'
    & $Helper -Action Register -ModulePath 'C:\Other installation\completion.psm1' -ProfilePaths $foreign
    & $Helper -Action Register -ModulePath $module -ProfilePaths $owned
    $foreignBefore = [Convert]::ToBase64String([IO.File]::ReadAllBytes($foreign))
    $failed = $false
    try { & $Helper -Action Register -ModulePath $module -ProfilePaths $foreign } catch {
        if ($_.Exception.Message -notlike '*belongs to another installation*') { throw }
        $failed = $true
    }
    if (-not $failed) { throw 'Registration replaced a foreign completion block.' }
    & $Helper -Action Remove -ModulePath $module -ProfilePaths @($foreign, $owned)
    if ([Convert]::ToBase64String([IO.File]::ReadAllBytes($foreign)) -ne $foreignBefore) { throw 'Foreign profile was changed.' }
    if (Test-Path -LiteralPath $owned) { throw 'A later owned profile was not cleaned up.' }
    Write-Output 'Profile registration tests passed.'
} finally {
    $resolved = [IO.Path]::GetFullPath($directory)
    $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\')
    if ([IO.Path]::GetDirectoryName($resolved) -ne $tempRoot -or -not [IO.Path]::GetFileName($resolved).StartsWith('amc-profile-test-')) {
        throw 'Refusing to remove an unexpected test directory.'
    }
    [IO.Directory]::Delete($resolved, $true)
}
