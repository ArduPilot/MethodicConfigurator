#!/bin/bash

# Outputs URLs of ArduPilot README.md pages on GitHub

# This script is used to crawl the ArduPilot GitHub repository for README.md files
# and output the URLs to a file called github_urllist.txt

# SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

# SPDX-License-Identifier: GPL-3.0-or-later

(
  cd ../ardupilot || exit 1
  find . -type f -name "*.md" | sed 's|^\.|https://github.com/ArduPilot/ardupilot/blob/master|' > ../ardupilot_methodic_configurator/github_urllist.txt
)
