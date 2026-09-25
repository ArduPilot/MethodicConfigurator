# Servo Output Functions Sub-application Architecture

## Overview

The Servo Output Functions plugin proposes safe `SERVOx_FUNCTION` assignments
for multicopter motor outputs. It uses the selected FC-to-ESC connection type,
the active `FRAME_CLASS`, ArduPilot motor-layout metadata, and the existing
servo-function assignments.

The plugin only fills outputs that are unset. Existing control-surface,
auxiliary, and motor assignments are preserved.

## Components

```text
User
  │
  ▼
frontend_tkinter_servo_out.py
  │  summary, apply action, and dialogs
  ▼
data_model_servo_out.py
  │  mapping, validation, and parameter-editor updates
  ├── vehicle component data (FC-to-ESC connection type)
  ├── parameter editor (FC and staged SERVOx_FUNCTION values)
  └── AP_Motors_test.json + schema
```

## Recommendation algorithm

1. Resolve the connection output order: Main Out uses outputs 1–14; AIO uses
   outputs 9–14 followed by 1–8.
2. Resolve `FRAME_CLASS`, preferring a valid non-zero staged value and falling
   back to the FC value or `Q_FRAME_CLASS`.
3. Read the motor numbers from the first valid layout for that frame class.
   Layouts for one class vary by frame type and geometry, but share the motor
   number set needed to derive motor function IDs.
4. Walk free outputs in connection order and assign only motor functions that
   are not already present.
5. Report any motors that still have no output when available outputs are
   exhausted.

## Semantic result status

The data model returns a `ServoOutRecommendationStatus` alongside the display
message. The view uses that status—not translated message text—to distinguish
informational outcomes (`NO_CHANGES` and `UNASSIGNED_MOTORS`) from errors.

## Apply behavior

Applying recommendations adds missing parameters to the current step when
needed, updates their values, reports failed parameter names, and preserves any
unassigned-motor warning in the result message.

## Source and tests

- Model: `ardupilot_methodic_configurator/plugins/data_model_servo_out.py`
- View: `ardupilot_methodic_configurator/plugins/frontend_tkinter_servo_out.py`
- Tests: `tests/plugins/test_data_model_servo_out.py` and
  `tests/plugins/test_frontend_tkinter_servo_out.py`
