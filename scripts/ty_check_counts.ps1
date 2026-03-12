#!/usr/bin/env pwsh

# This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

# SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

# SPDX-License-Identifier: GPL-3.0-or-later

ty check |
  Select-String -Pattern 'error','warning' |
  ForEach-Object {
    if ($_ -match '^(?<level>error|warning)\[(?<etype>[^\]]+)\]') {
        [PSCustomObject]@{
            Level      = $matches['level']
            ErrorType  = $matches['etype']
        }
    }
  } |
  Group-Object -Property Level, ErrorType |
  Sort-Object Count -Descending |
  Select-Object Count,
                @{ Name = 'Level';     Expression = { $_.Group[0].Level } },
                @{ Name = 'ErrorType'; Expression = { $_.Group[0].ErrorType } }
