# MAVLink Signing Backend (Phase 1)

## Overview

This document describes the implementation of the **MAVLink Message Signing** backend for the ArduPilot Methodic Configurator.

This enhancement adds a secure key management and signing layer to **authenticate** communication between the Ground Control Software (GCS) and Flight Controller (FC). It ensures that MAVLink messages are cryptographically signed and verified, preventing message tampering, spoofing, and unauthorized control.

**Important**: MAVLink signing provides **authentication and integrity**, not encryption. Messages are signed but remain readable. This prevents unauthorized control while maintaining performance.

This is **Phase 1** of a multi-stage security feature rollout — it introduces the complete backend infrastructure required for secure message signing, without any frontend or UI changes.

---

## Key Features

### Secure Key Storage
- Uses the OS keyring (Windows Credential Manager, macOS Keychain, Linux Secret Service)
- AES-256 encrypted file fallback if keyring is unavailable
- Machine-specific encryption for file storage
- File permissions set to 0600 (owner read/write only) on Unix systems

### Cryptographic Security
- HMAC-SHA-256 message signing (not encryption)
- Timestamp-based replay protection
- Per-vehicle key isolation
- Password-protected key import/export (PBKDF2HMAC with 100,000 iterations)
- Cryptographically secure key generation using `secrets.token_bytes(32)`

### Non-Breaking Integration
- Fully backward compatible with existing configurations
- No impact on communication flow unless signing is explicitly enabled
- Modular, testable, and isolated components
- Optional feature - disabled by default

---

## What MAVLink Signing Does (and Doesn't Do)

### ✅ What It Provides

- **Authentication**: Verifies messages come from a trusted source
- **Integrity**: Detects if messages have been tampered with
- **Replay Protection**: Prevents old messages from being replayed
- **Authorization**: Only trusted GCS can send commands

### ❌ What It Does NOT Provide

- **Encryption**: Message content is NOT hidden (messages are readable)
- **Confidentiality**: Eavesdroppers can read message content
- **Privacy**: Traffic patterns and message types are visible

**Why?** MAVLink signing focuses on preventing unauthorized control, not eavesdropping. This design choice maintains performance while providing the security most drone operations need.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    User Application                          │
│              (Python API or Future GUI)                      │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────┐
│              Backend Components (Phase 1)                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  SigningKeyStore                                            │
│  • Generate 32-byte keys                                    │
│  • Store in OS keyring or encrypted file                   │
│  • Export/import with password protection                  │
│  • Manage keys for multiple vehicles                       │
│                                                              │
│  SigningConfig                                              │
│  • Configuration data model                                 │
│  • Validation logic                                         │
│  • Serialization/deserialization                           │
│                                                              │
│  FlightController (extended)                                │
│  • setup_signing() method                                   │
│  • Integration with pymavlink                               │
│  • Status monitoring                                        │
│                                                              │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────┐
│                  Existing Infrastructure                     │
│  • pymavlink (MAVLink library)                              │
│  • Flight Controller (ArduPilot firmware 4.4.0+)           │
└─────────────────────────────────────────────────────────────┘
```

---

## File Locations

| Component | File Path | Description |
|-----------|-----------|-------------|
| **Key Management** | `ardupilot_methodic_configurator/backend_signing_keystore.py` | Core key generation, storage, encryption, and management |
| **Configuration Model** | `ardupilot_methodic_configurator/data_model_signing_config.py` | Configuration schema, validation, and serialization |
| **FC Integration** | `ardupilot_methodic_configurator/backend_flightcontroller.py` | MAVLink signing integration (modified) |
| **Unit Tests - Keystore** | `tests/test_signing_keystore.py` | 15 test cases for key storage system |
| **Unit Tests - Config** | `tests/test_signing_config.py` | 15 test cases for configuration validation |
| **Installation Script** | `install_signing_dependencies.sh` | Automated dependency installation |
| **Dependencies** | `pyproject.toml` | Updated with cryptography and keyring |

---

## Installation

### Install Dependencies

```bash
# Option 1: Use the installation script (recommended)
./install_signing_dependencies.sh

# Option 2: Manual installation
pip install cryptography>=41.0.0 keyring>=24.0.0
```

### Required Packages

- **cryptography** (>=41.0.0) - For encryption/decryption and HMAC
- **keyring** (>=24.0.0) - For OS keyring access
- **Standard library**: secrets, hashlib, json, pathlib, logging

---

## Testing

### Quick Verification

Run the standalone tests to verify the implementation:

```bash
# Test 1: Key storage system
python ardupilot_methodic_configurator/backend_signing_keystore.py

# Test 2: Configuration validation
python ardupilot_methodic_configurator/data_model_signing_config.py
```

### Expected Output

#### Test 1: Keystore
```
INFO:root:Using OS keyring for signing key storage
DEBUG:root:Generated new 32-byte signing key
Generated key: c53297f5038ea3c1e16309fa8e75f5adab63383db28045769a0af998c778ec34
✓ Stored key for test_vehicle_001
✓ Retrieved key matches original
Vehicles with keys: ['test_vehicle_001']
✓ Exported key (239 bytes)
✓ Imported key for test_vehicle_001
✓ All tests passed!
```

#### Test 2: Configuration
```
Default config:
MAVLink signing disabled

Default config valid: True

Enabled config:
MAVLink signing enabled for vehicle: my_drone_001
Unsigned messages will be rejected
Timestamp tolerance: 60000 ms

Enabled config valid: True

Serialized:
{'enabled': True, 'vehicle_id': 'my_drone_001', ...}

Restored config:
MAVLink signing enabled for vehicle: my_drone_001
...

Invalid config valid: False
Error: Vehicle ID is required when signing is enabled
```

### Unit Tests (with pytest)

```bash
# Run all signing tests
python -m pytest tests/test_signing_keystore.py tests/test_signing_config.py -v

# Run individually
python -m pytest tests/test_signing_keystore.py -v
python -m pytest tests/test_signing_config.py -v
```

### What The Tests Verify

**Keystore Tests:**
- ✅ Key generation (cryptographically secure)
- ✅ Key storage (OS keyring or encrypted file)
- ✅ Key retrieval (correct key returned)
- ✅ Key deletion (proper cleanup)
- ✅ Key export (password-protected encryption)
- ✅ Key import (decryption and restoration)
- ✅ Multi-vehicle support (key isolation)
- ✅ Persistence (keys survive across instances)

**Configuration Tests:**
- ✅ Default values (safe defaults)
- ✅ Validation logic (catches invalid configs)
- ✅ Serialization (save to JSON)
- ✅ Deserialization (load from JSON)
- ✅ Edge cases (empty vehicle_id, negative timeouts, etc.)

---
