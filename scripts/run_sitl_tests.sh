#!/bin/bash
#
# SITL Testing Script for ArduPilot Methodic Configurator
# This script helps set up and run SITL tests for local development
#
# This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator
#
# SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>
#
# SPDX-License-Identifier: GPL-3.0-or-later

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
ARDUPILOT_DIR="${ARDUPILOT_DIR:-$HOME/ardupilot-sitl}"
SITL_BINARY="${ARDUPILOT_DIR}/ardupilot/build/sitl/bin/arducopter"

echo -e "${GREEN}ArduPilot SITL Testing Setup${NC}"
echo "================================="

# Check if ArduPilot SITL is available
check_sitl() {
    # First check for downloaded SITL
    if [ -f "$PROJECT_ROOT/sitl/arducopter" ]; then
        echo -e "${GREEN}✓ Downloaded ArduCopter SITL found at: $PROJECT_ROOT/sitl/arducopter${NC}"
        export SITL_BINARY="$PROJECT_ROOT/sitl/arducopter"
        return 0
    # Then check for locally built SITL
    elif [ -f "$SITL_BINARY" ]; then
        echo -e "${GREEN}✓ Locally built ArduCopter SITL found at: $SITL_BINARY${NC}"
        return 0
    else
        echo -e "${RED}✗ ArduCopter SITL not found${NC}"
        echo -e "${YELLOW}Run '$0 download' to download SITL from ArduPilot website, or build locally and set ARDUPILOT_DIR${NC}"
        return 1
    fi
}

# Setup SITL for testing
setup_sitl() {
    echo "Setting up SITL environment..."

    # Create SITL cache directory if it doesn't exist
    mkdir -p "$PROJECT_ROOT/sitl-cache"

    # Handle downloaded SITL
    if [ -f "$PROJECT_ROOT/sitl/arducopter" ]; then
        export SITL_BINARY="$PROJECT_ROOT/sitl/arducopter"
        cp "$PROJECT_ROOT/sitl/arducopter" "$PROJECT_ROOT/sitl-cache/"
        # Download default parameters if not already present
        if [ ! -f "$PROJECT_ROOT/sitl/copter.parm" ]; then
            curl -L -o "$PROJECT_ROOT/sitl/copter.parm" https://raw.githubusercontent.com/ArduPilot/ardupilot/master/Tools/autotest/default_params/copter.parm
        fi
        cp "$PROJECT_ROOT/sitl/copter.parm" "$PROJECT_ROOT/sitl-cache/"
        echo -e "${GREEN}✓ Downloaded SITL binary and config copied to cache${NC}"
    # Handle locally built SITL
    elif [ -f "$SITL_BINARY" ]; then
        export SITL_BINARY="$SITL_BINARY"
        cp "$SITL_BINARY" "$PROJECT_ROOT/sitl-cache/"
        cp "${ARDUPILOT_DIR}/ardupilot/Tools/autotest/default_params/copter.parm" "$PROJECT_ROOT/sitl-cache/"
        echo -e "${GREEN}✓ Locally built SITL binary and config copied to cache${NC}"
    fi
}

# Run SITL tests
run_sitl_tests() {
    echo "Running SITL integration tests..."

    cd "$PROJECT_ROOT"

    # Set environment variable for SITL binary
    export SITL_BINARY="$SITL_BINARY"

    # Run SITL tests including signing integration tests
    python -m pytest tests/test_backend_flightcontroller_sitl.py \
        tests/bdd_signing_sitl_integration.py \
        -v \
        --tb=short \
        --capture=no \
        -x
}

# Clean up SITL processes
cleanup_sitl() {
    echo "Cleaning up SITL processes..."

    # Kill any running SITL processes
    pkill -f arducopter || true

    # Remove SITL cache
    rm -rf "$PROJECT_ROOT/sitl-cache"

    echo -e "${GREEN}✓ Cleanup completed${NC}"
}

# Download ArduCopter SITL from official firmware server
download_sitl() {
    echo "Downloading ArduCopter SITL from official firmware server..."

    # Create SITL directory
    mkdir -p "$PROJECT_ROOT/sitl"

    # Download SITL binary and metadata
    if curl -L -o "$PROJECT_ROOT/sitl/arducopter" https://firmware.ardupilot.org/Copter/latest/SITL_x86_64_linux_gnu/arducopter; then
        curl -L -o "$PROJECT_ROOT/sitl/firmware-version.txt" https://firmware.ardupilot.org/Copter/latest/SITL_x86_64_linux_gnu/firmware-version.txt
        curl -L -o "$PROJECT_ROOT/sitl/git-version.txt" https://firmware.ardupilot.org/Copter/latest/SITL_x86_64_linux_gnu/git-version.txt

        # Make executable
        chmod +x "$PROJECT_ROOT/sitl/arducopter"

        # Set environment variable
        export SITL_BINARY="$PROJECT_ROOT/sitl/arducopter"

        echo -e "${GREEN}✓ ArduCopter SITL downloaded successfully${NC}"
        if [ -f "$PROJECT_ROOT/sitl/git-version.txt" ] && [ -s "$PROJECT_ROOT/sitl/git-version.txt" ]; then
            echo "SITL version: $(cat "$PROJECT_ROOT/sitl/git-version.txt")"
        fi
        if [ -f "$PROJECT_ROOT/sitl/firmware-version.txt" ] && [ -s "$PROJECT_ROOT/sitl/firmware-version.txt" ]; then
            echo "Firmware version: $(cat "$PROJECT_ROOT/sitl/firmware-version.txt")"
        fi
        return 0
    else
        echo -e "${RED}✗ Failed to download ArduCopter SITL${NC}"
        return 1
    fi
}

# Main script logic
case "${1:-help}" in
    "check")
        check_sitl
        ;;
    "download")
        download_sitl
        ;;
    "setup")
        if check_sitl; then
            setup_sitl
        fi
        ;;
    "test")
        if check_sitl; then
            setup_sitl
            run_sitl_tests
        fi
        ;;
    "download-test")
        if download_sitl; then
            setup_sitl
            run_sitl_tests
        fi
        ;;
    "cleanup")
        cleanup_sitl
        ;;
    "help"|*)
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  check        - Check if SITL is available (downloaded or locally built)"
        echo "  download     - Download ArduCopter SITL from official ArduPilot firmware server"
        echo "  setup        - Set up SITL for testing (copy to cache)"
        echo "  test         - Run SITL integration tests"
        echo "  download-test- Download SITL and run tests in one command"
        echo "  cleanup      - Clean up SITL processes and cache"
        echo "  help         - Show this help message"
        echo ""
        echo "Environment variables:"
        echo "  ARDUPILOT_DIR - Path to ArduPilot directory for locally built SITL (default: \$HOME/ardupilot-sitl)"
        echo ""
        echo "Examples:"
        echo "  $0 download     # Download SITL from ArduPilot website"
        echo "  $0 download-test # Download and test in one command"
        echo "  $0 check        # Check if SITL is available"
        echo "  ARDUPILOT_DIR=/path/to/ardupilot $0 test  # Use locally built SITL"
        ;;
esac
