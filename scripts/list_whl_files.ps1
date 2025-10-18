#!/usr/bin/env pwsh

# This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

# SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

# SPDX-License-Identifier: GPL-3.0-or-later

$ErrorActionPreference = "Stop"

# Resolve repo root (parent of 'scripts' folder)
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

# Paths
$VenvDir    = Join-Path $Root ".venv"
$ActivatePs = Join-Path $VenvDir "Scripts\Activate.ps1"
$PyExe      = Join-Path $VenvDir "Scripts\python.exe"
$DistDir    = Join-Path $Root "dist"
$ExtractDir = Join-Path $DistDir "wheel_from_pypi"
$PkgName    = "ardupilot_methodic_configurator"
$Version    = "2.0.3"

function Ensure-Venv {
    if (-not (Test-Path $ActivatePs)) {
        Write-Host "Virtual env not found. Creating one..."
        py -m venv $VenvDir
        if (-not (Test-Path $ActivatePs)) { throw "Failed to create virtual environment at $VenvDir" }
    }
}

function Activate-Venv {
    try {
        . $ActivatePs
    } catch {
        Write-Warning "Failed to run Activate.ps1 (ExecutionPolicy?). Falling back to manual activation."
        $env:VIRTUAL_ENV = $VenvDir
        $venvBin = Join-Path $VenvDir "Scripts"
        if ($env:PATH -notlike "$venvBin*") { $env:PATH = "$venvBin;$env:PATH" }
    }
}

function Test-Pip {
    $pipPkg = Join-Path $VenvDir "Lib\site-packages\pip"
    if (Test-Path $pipPkg) { return $true }
    $pipDistInfo = Get-ChildItem (Join-Path $VenvDir "Lib\site-packages") -Filter "pip-*.dist-info" -ErrorAction SilentlyContinue
    return ($pipDistInfo -ne $null)
}

function Ensure-Pip {
    # Try ensurepip first (safe if pip already present)
    & $PyExe -m ensurepip --upgrade | Out-Null

    if (Test-Pip) { return }

    Write-Host "ensurepip did not install pip. Falling back to get-pip.py..."
    $getPip = Join-Path $env:TEMP "get-pip.py"
    Invoke-WebRequest -UseBasicParsing -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile $getPip
    & $PyExe $getPip
    Remove-Item $getPip -ErrorAction SilentlyContinue

    if (-not (Test-Pip)) { throw "Unable to install pip in the virtual environment." }
}

# 1) Ensure and activate venv
Ensure-Venv
Activate-Venv

# 2) Ensure pip exists (skip pip upgrade to avoid hangs)
Ensure-Pip

# Make pip fully non-interactive and quiet
$env:PIP_NO_INPUT = "1"
$env:PIP_DISABLE_PIP_VERSION_CHECK = "1"

# 3) Prepare dist dirs
New-Item -ItemType Directory -Force -Path $DistDir | Out-Null
Remove-Item -Recurse -Force $ExtractDir -ErrorAction SilentlyContinue

# 4) Download the wheel using venv's pip
& $PyExe -m pip download "$PkgName==$Version" --no-deps --no-color --disable-pip-version-check -q -d $DistDir
if ($LASTEXITCODE -ne 0) { throw "pip download failed with exit code $LASTEXITCODE" }

# 5) Find the downloaded wheel
$whl = Get-ChildItem "$DistDir\$PkgName-$Version-*.whl" | Select-Object -First 1
if (-not $whl) { throw "Wheel not found in $DistDir. Did the download fail?" }

# 6) List wheel contents without extracting
try { Add-Type -AssemblyName System.IO.Compression.FileSystem -ErrorAction SilentlyContinue } catch {}
Write-Host "`n--- Listing entries inside the wheel ---"
$zip = [System.IO.Compression.ZipFile]::OpenRead($whl.FullName)
$zip.Entries | ForEach-Object { $_.FullName }
$zip.Dispose()

# 7) Extract using .NET (works with .whl)
[System.IO.Compression.ZipFile]::ExtractToDirectory($whl.FullName, $ExtractDir)

# 8) Show useful parts of the extracted wheel
Write-Host "`n--- Top level extracted ---"
Get-ChildItem -Recurse $ExtractDir | Select-Object -ExpandProperty FullName

Write-Host "`n--- Package data under $PkgName/ ---"
Get-ChildItem -Recurse (Join-Path $ExtractDir $PkgName) -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName

Write-Host "`n--- data_files under .data/data (if any) ---"
Get-ChildItem -Recurse (Join-Path $ExtractDir "*.data\data\*") -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName
