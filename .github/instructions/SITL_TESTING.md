# SITL Testing Setup

This document describes how to set up and run integration tests using ArduPilot SITL (Software In The Loop) for testing the `backend_flightcontroller.py` module.

## Overview

SITL testing provides real MAVLink communication validation instead of mocked tests.
This ensures the flight controller backend works correctly with actual ArduPilot firmware.

## Architecture

The SITL testing setup consists of:

1. **Direct Download**: Tests download pre-built ArduCopter SITL binaries directly from the official ArduPilot firmware server (`firmware.ardupilot.org`)
2. **Pytest Fixtures**: Session-scoped SITLManager class manages SITL process lifecycle
3. **TCP Connection**: SITL runs on TCP port 5760 with MAVLink protocol
4. **Parameter Configuration**: SITL uses `sitl/copter.parm` with battery monitoring enabled

## Prerequisites

### For CI/CD (GitHub Actions)

- No additional setup required - SITL binaries are downloaded automatically during tests

### For Local Development

#### Download Pre-built SITL (Recommended)

Download the latest pre-built SITL binary directly from the official ArduPilot firmware server:

```bash
./scripts/run_sitl_tests.sh download
```

This downloads ArduCopter SITL from `https://firmware.ardupilot.org/Copter/latest/SITL_x86_64_linux_gnu/arducopter`

## Usage

### CI/CD Testing

SITL tests run automatically in GitHub Actions when SITL artifacts are available. The test workflow:

1. Downloads the latest SITL artifact
2. Extracts and sets up SITL binary
3. Runs tests marked with `@pytest.mark.sitl`
4. Falls back to mocked tests if SITL is unavailable

### Local Development

Use the provided script for local SITL testing. You can either download pre-built SITL or use a locally built version:

#### Using Downloaded SITL (Recommended)

```bash
# Download ArduCopter SITL from official firmware server
./scripts/run_sitl_tests.sh download

# Download and run tests in one command
./scripts/run_sitl_tests.sh download-test

# Check if downloaded SITL is available
./scripts/run_sitl_tests.sh check
```

#### Using Locally Built SITL

```bash
# Set up environment for locally built SITL
export ARDUPILOT_DIR="$HOME/ardupilot-sitl"

# Check if locally built SITL is available
./scripts/run_sitl_tests.sh check

# Set up SITL for testing
./scripts/run_sitl_tests.sh setup

# Run SITL integration tests
./scripts/run_sitl_tests.sh test
```

#### General Commands

```bash
# Clean up SITL processes and cache
./scripts/run_sitl_tests.sh cleanup

# Show help
./scripts/run_sitl_tests.sh help
```

### Manual Testing

Run specific SITL tests:

```bash
# Run all SITL tests
python -m pytest tests/test_backend_flightcontroller_sitl.py -v

# Run only SITL tests (skip if SITL unavailable)
python -m pytest -m sitl -v

# Run SITL tests or fallback to mocked tests
python -m pytest -m "sitl or not sitl" -v
```

## Test Coverage

SITL tests cover:

- **Real MAVLink Connection**: Validates actual protocol communication on TCP port 5760
- **Parameter Management**: Download, set, and verify parameters with real firmware
- **Motor Testing**: Test motor commands against actual ArduPilot firmware
- **Battery Monitoring**: Test battery status reporting with enabled monitoring
- **Frame Information**: Validate vehicle configuration queries

## Implementation Details

### SITL Configuration

SITL runs with the following command line parameters:

```bash
arducopter --model quad --home "40.071374,-105.229930,1440,0" --defaults sitl/copter.parm --sysid 1 --speedup 10
```

### Connection Details

- **Protocol**: MAVLink over TCP
- **Port**: 5760
- **Connection String**: "tcp:127.0.0.1:5760"
- **Vehicle Type**: ArduCopter (Quadcopter)
- **System ID**: 1

### Parameter Requirements

Some tests require specific parameters to be set in `sitl/copter.parm`:

- `BATT_MONITOR = 4` (Analog voltage and current)
- `BATT_VOLT_PIN = 1`
- `BATT_CURR_PIN = 2`
- `BATT_VOLT_MULT = 10.0`
- `BATT_AMP_PERVOLT = 17.0`

## Configuration

### Environment Variables

- `SITL_BINARY`: Path to ArduCopter SITL binary (auto-detected in CI)
- `ARDUPILOT_DIR`: Path to ArduPilot directory for local development

### Test Markers

- `@pytest.mark.sitl`: Marks tests requiring SITL
- Tests automatically skip if SITL is unavailable

## Troubleshooting

### SITL Not Found

- **For downloaded SITL**: Run `./scripts/run_sitl_tests.sh download` to download from ArduPilot website
- **For locally built SITL**: Ensure ArduPilot is built with `./waf configure --board=sitl && ./waf copter`
- Check `ARDUPILOT_DIR` environment variable for locally built SITL
- Verify SITL binary exists at expected path

### Connection Failures

- SITL may take time to start - tests include startup delays
- Check for port conflicts on TCP port 5760
- Verify MAVLink heartbeat detection
- Ensure connection string format is "tcp:127.0.0.1:5760"

### Test Timeouts

- SITL tests are slower than mocked tests
- Increase timeout values if needed
- Check system performance for SITL simulation

## Benefits

1. **Real Validation**: Tests actual MAVLink protocol implementation
2. **Regression Detection**: Catches firmware compatibility issues
3. **CI/CD Integration**: Automated testing with pre-built artifacts
4. **Development Flexibility**: Local testing with fallback to mocks
5. **Cost Efficiency**: Monthly builds reduce CI resource usage

## Future Enhancements

- Multiple vehicle types (ArduPlane, Rover, etc.)
- SITL version pinning for reproducible tests
- Performance optimization for faster test execution
- Multi-SITL instance testing for complex scenarios
