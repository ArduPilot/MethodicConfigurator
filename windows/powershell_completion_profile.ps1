# Manage PowerShell profile registration for ArduPilot Methodic Configurator.
# SPDX-FileCopyrightText: 2026 ArduPilot Methodic Configurator contributors
# SPDX-License-Identifier: GPL-3.0-or-later
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateSet('Register', 'Remove')][string]$Action,
    [Parameter(Mandatory = $true)][string]$ModulePath,
    [string[]]$ProfilePaths
)

$ErrorActionPreference = 'Stop'
if (-not $ProfilePaths) {
    $ProfilePaths = @($PROFILE.CurrentUserAllHosts)
    $pwsh = Get-Command pwsh.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($pwsh) {
        $modernProfile = & $pwsh.Source -NoProfile -Command '[Console]::Write($PROFILE.CurrentUserAllHosts)'
        if ($LASTEXITCODE -ne 0 -or -not $modernProfile) { throw 'Could not determine the PowerShell 7 profile path.' }
        $ProfilePaths += $modernProfile
    }
}

$begin = '# BEGIN ArduPilot Methodic Configurator completion'
$end = '# END ArduPilot Methodic Configurator completion'
$latin1 = [Text.Encoding]::GetEncoding(28591)
foreach ($profilePath in ($ProfilePaths | Select-Object -Unique)) {
    $exists = [IO.File]::Exists($profilePath)
    if (-not $exists -and $Action -eq 'Remove') { continue }
    [byte[]]$bytes = @()
    if ($exists) { $bytes = [IO.File]::ReadAllBytes($profilePath) }
    # Appended text is ASCII; preserve the original bytes and encoding, including BOM-less legacy files.
    $encoding = [Text.Encoding]::ASCII
    if ($bytes.Length -ge 4 -and $bytes[0] -eq 0xFF -and $bytes[1] -eq 0xFE -and $bytes[2] -eq 0 -and $bytes[3] -eq 0) {
        $encoding = [Text.Encoding]::UTF32
    } elseif ($bytes.Length -ge 4 -and $bytes[0] -eq 0 -and $bytes[1] -eq 0 -and $bytes[2] -eq 0xFE -and $bytes[3] -eq 0xFF) {
        $encoding = New-Object Text.UTF32Encoding($true, $true)
    } elseif ($bytes.Length -ge 2 -and $bytes[0] -eq 0xFF -and $bytes[1] -eq 0xFE) {
        $encoding = [Text.Encoding]::Unicode
    } elseif ($bytes.Length -ge 2 -and $bytes[0] -eq 0xFE -and $bytes[1] -eq 0xFF) {
        $encoding = [Text.Encoding]::BigEndianUnicode
    }
    $raw = $latin1.GetString($bytes)
    $startBytes = $latin1.GetString($encoding.GetBytes("`r`n$begin`r`n"))
    $endBytes = $latin1.GetString($encoding.GetBytes("$end`r`n"))
    $pattern = [regex]::Escape($startBytes) + '.*?' + [regex]::Escape($endBytes)
    $matches = [regex]::Matches($raw, $pattern, [Text.RegularExpressions.RegexOptions]::Singleline)
    $beginBytes = $latin1.GetString($encoding.GetBytes($begin))
    $endMarkerBytes = $latin1.GetString($encoding.GetBytes($end))
    if (([regex]::Matches($raw, [regex]::Escape($beginBytes)).Count -ne $matches.Count) -or
        ([regex]::Matches($raw, [regex]::Escape($endMarkerBytes)).Count -ne $matches.Count) -or $matches.Count -gt 1) {
        throw "Completion markers in profile are malformed: $profilePath"
    }
    $moduleBase64 = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($ModulePath))
    if ($matches.Count) {
        $encodedPath = $latin1.GetString($encoding.GetBytes($moduleBase64))
        if (-not $matches[0].Value.Contains($encodedPath)) {
            if ($Action -eq 'Remove') { continue }
            throw "Completion registration belongs to another installation: $profilePath"
        }
        $raw = $raw.Remove($matches[0].Index, $matches[0].Length)
    }
    if ($Action -eq 'Register') {
        $line = "Import-Module ([Text.Encoding]::Unicode.GetString([Convert]::FromBase64String('$moduleBase64')))"
        $block = "`r`n$begin`r`n$line`r`n$end`r`n"
        $raw += $latin1.GetString($encoding.GetBytes($block))
        $parent = [IO.Path]::GetDirectoryName($profilePath)
        if (-not [IO.Directory]::Exists($parent)) { [void][IO.Directory]::CreateDirectory($parent) }
    }
    if ($raw.Length -eq 0 -and $exists -and $Action -eq 'Remove') {
        [IO.File]::Delete($profilePath)
    } elseif ($Action -eq 'Register' -or $matches.Count) {
        [IO.File]::WriteAllBytes($profilePath, $latin1.GetBytes($raw))
    }
}
