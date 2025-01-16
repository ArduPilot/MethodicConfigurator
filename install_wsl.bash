#!/usr/bin/env bash

# This script should run in a ubuntu 22.04 or newer running inside WSL2 on a Windows PC
# It configures the WSL2 virtual machine to run the linters required in the project
#
# This script is automatically called from the SetupDeveloperPC.bat and should not be called directly

sudo apt-get update

sudo apt install unzip shellcheck

npm install --global markdown-link-check@3.13.6

shellcheck --version
npm list -g markdown-link-check
