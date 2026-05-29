#!/usr/bin/env pwsh

# This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

# SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

# SPDX-License-Identifier: GPL-3.0-or-later

Get-ChildItem -Path "ardupilot_methodic_configurator\vehicle_templates" -Recurse -Filter "vehicle_components.json" | ForEach-Object { (Get-Content $_.FullName -Raw) -replace '"Format version": 1', '"Format version": 0' | Set-Content $_.FullName -NoNewline }
