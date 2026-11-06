# GNSS interference log analysis

The GPS subsystem in the existing log-analysis report checks receiver interference indicators,
GPS consistency and inertial motion. Availability is determined from the log's actual fields,
so a missing receiver-specific message does not prevent checks supported by other data.

Receiver indications are evidence of what a receiver reported. Consistency discrepancies can
also result from sensor faults, multipath, timing errors or estimator problems. These checks
cannot establish malicious intent or exclude a sophisticated, consistent spoofing signal.

## Available evidence

| Source | Interpretation |
| --- | --- |
| `AERG.Jam`, `AERG.Spf` | 1: no indication; 2: warning; 3: critical, according to the saved ArduPilot message metadata. |
| `ILB5.GSS` | 1: no indication; 2: spoofing indicated; 3: multiple spoofing indicated. Both indication codes produce warnings. |
| `ILB5.GJS` | 1: no indication; 3: jamming indicated with no fix. Code 2 is retained as unknown because the inspected source does not establish its meaning. |
| `UBX1.jamInd` | Diagnostic indicator, with larger values suggesting interference; no verified universal attack threshold. |
| `GPS`, `GPA` | Fix, quality changes, position/velocity consistency and GPS clock progression. |
| `IMU`, `ATT`, optional `VIBE` | Specific force transformed into NED and corrected for gravity, compared with short GPS velocity changes. |
| `XKF3/4`, `XKFS`, or `NKF3/4` | Lane-specific innovations, acceptance ratios, position resets, faults and timeouts. GPS attribution requires navigation-source metadata. |

Zero, undocumented and invalid receiver statuses never establish healthy operation.
Recovery is reported only when a known healthy status follows a warning without a timestamp gap.
Event end times identify the last observed sample; they do not imply recovery after missing data.

## Multiple receivers and EKF lanes

GPS and GPA records use `I`; u-blox diagnostics use `Instance`; EKF lanes use `C`.
Each receiver and each EKF lane is evaluated separately, including secondary receivers and lanes.
Findings retain these identities. A source without an instance field remains unidentified and
cannot be combined with a particular receiver's evidence.

`XKFS.SS` selects the applicable timestamped `EK3_SRCn_POSXY` and `EK3_SRCn_VELXY`
parameters. `XKFS.GI` identifies the lane's selected receiver when logged. `PI` identifies
the primary lane. All EKF events split at changes in primary activity and include `active_primary`.
Innovation, timeout and GPS-check events also split at changes in source set or receiver;
their evidence includes the selected receiver when known. Fault and position-reset events
retain lane-level attribution.
EKF2 GPS attribution uses the logged `EK2_GPS_TYPE`. EKF3 velocity attribution also
checks timestamped `EK3_SRC_OPTIONS`: when `FuseAllVelocities` (bit 0) is enabled,
GPS velocity configured in any source set remains eligible. Velocity innovations
may combine GPS and other configured velocity sources and are not attributed solely to GPS.
EKF innovations remain GPS-aided evidence.
Coverage for logged fault, quality, reset and timeout fields reports how many samples
were evaluated. Samples without a usable GPS navigation source are skipped; missing or
stale `XKFS.SS` can prevent EKF3 source selection unless GPS velocity fusion is enabled
across source sets.

Timeout warnings retain only the position and velocity bits whose lane navigation
sources use GPS, and include both the raw timeout mask and the GPS-relevant mask.
The raw timeout evidence combines all bits observed within each interval using bitwise OR.
Height, magnetometer, airspeed and drag timeout bits do not create GNSS warnings;
unused sensors can remain timed out during normal operation.
When the lane's filter status and fault bits identify initialization, pre-aiding GPS-check
and timeout states and the `NOT_INITIALISED` fault bit are treated as startup context.
Other fault bits remain warnings even before aiding. Position resets before or at the first
observed aided state are also startup context; later resets remain warnings. Aiding is
remembered through subsequent outages within each boot. Without initialization evidence,
an outage at the beginning of a partial log retains its ordinary warning behavior.

The inertial comparison uses each healthy IMU independently. Continuous inertial segments
are indexed by start time and integrated axes are stored contiguously, so each GPS comparison
does not scan or copy the entire inertial history. Reversed GPS or IMU boot epochs cannot be aligned
unambiguously and are excluded from the inertial comparison. A warning requires disagreement
with every available healthy IMU at every tested latency. GPS course describes velocity direction;
it is not compared directly with vehicle yaw.

## Numerical checks and limits

These diagnostic limits are conservative implementation choices, tested with synthetic scenarios.
They are not calibrated probabilities or certified attack-detection thresholds.

| Check | Limit or prerequisite |
| --- | --- |
| Receiver and GPS event continuity | Finite, increasing boot timestamps with gaps at most 2 seconds; slow u-blox diagnostics use the bounded cadence rule below. |
| u-blox indicator rise | Exceeds a preceding median by `max(20, 6 * MAD)` indicator counts; at least five preceding samples. The baseline covers at least 5 seconds and expands with the observed diagnostic cadence. Continuity allows three median sample intervals, bounded to 2-15 seconds. Constant or slowly rising interference can be missed. |
| GPS clock | GPS-week/time-of-week progression differs from boot-time progression by more than 1 second over a window up to 5 seconds. Week rollover and frozen timestamps are accounted for. |
| Horizontal position/velocity | Position displacement differs from trapezoidal velocity integration by more than `max(10 m, 3 * sum of endpoint HAcc)`. Longitude wrap is accounted for. |
| Altitude/vertical velocity | Relative altitude changes are compared with down-positive vertical velocity; tolerance is `max(10 m, 3 * sum of endpoint VAcc)`. Requires `GPA.VV`. |
| GPS quality | Satellite count falls below half a preceding median of at least eight satellites, or HDOP exceeds both 3 and four times its preceding median. Sustained for at least 0.5 seconds. |
| GPS/IMU motion | Velocity-change residual exceeds `3 m/s + 3 * sum of endpoint SAcc`, sustained for at least 0.5 seconds. GPS intervals span 0.1 to 2 seconds. |
| Inertial continuity | IMU gaps at most 0.2 seconds and attitude gaps at most 0.25 seconds; invalid or unhealthy samples break integration. |
| Rotation and clipping | Rotation rate below 0.5 rad/s; logged accelerometer clipping transitions are excluded. Higher rates need explicit lever-arm correction. |
| Latency | GPA sample-arrival timestamps are used when consistent. A positive logged receiver delay up to 500 ms is applied; otherwise six candidate delays from 0 to 500 ms are tested. This bounded comparison is conservative, not a latency measurement. |
| Vertical motion | Evaluated only when `GPA.VV` confirms receiver vertical velocity availability. |
| EKF innovation | Acceptance ratio greater than 1 for at least 0.5 seconds, using the lane's GPS navigation source. |

Missing accuracy fields use the stated absolute tolerance floors. Missing prerequisites reduce
reported coverage; they are never reported as a passing consistency check. Raw IMU bias,
low-rate logging and GPS-aided attitude can limit independent validation. The report exposes
the measured residuals and thresholds in finding tooltips and structured evidence.

Overlapping u-blox indicator rises and fix loss on the same identified receiver produce a
suspected-jamming finding. Overlapping inertial and position/velocity discrepancies produce
a suspected-spoofing-or-GPS-fault finding. Correlation does not upgrade these into proof of an attack.
Correlation is skipped if relevant sensor timestamps reverse, because boot epochs cannot be
matched reliably.

## Source verification and validation

Implementation was checked against the local ArduPilot revision
`92b0cd788ec29406f26c6f9c31d5ceedbd1cc538`:

- [GPS message fields and units](https://github.com/ArduPilot/ardupilot/blob/92b0cd788ec29406f26c6f9c31d5ceedbd1cc538/libraries/AP_GPS/LogStructure.h)
- [GPS logging and sample-arrival timing](https://github.com/ArduPilot/ardupilot/blob/92b0cd788ec29406f26c6f9c31d5ceedbd1cc538/libraries/AP_GPS/AP_GPS.cpp)
- [Inertial Labs raw status and transition handling](https://github.com/ArduPilot/ardupilot/blob/92b0cd788ec29406f26c6f9c31d5ceedbd1cc538/libraries/AP_ExternalAHRS/AP_ExternalAHRS_InertialLabs.cpp)
- [EKF3 lane, sensor-selection and innovation logging](https://github.com/ArduPilot/ardupilot/blob/92b0cd788ec29406f26c6f9c31d5ceedbd1cc538/libraries/AP_NavEKF3/AP_NavEKF3_Logging.cpp)

Source eligibility and timeout corrections were also verified against local revision
`ed3795bcb8b5fafa3ab88eb1af295391006e04cd`:

- [EKF navigation source eligibility and FuseAllVelocities](https://github.com/ArduPilot/ardupilot/blob/ed3795bcb8b5fafa3ab88eb1af295391006e04cd/libraries/AP_NavEKF/AP_NavEKF_Source.cpp)
- [EKF3 initial timeout states](https://github.com/ArduPilot/ardupilot/blob/ed3795bcb8b5fafa3ab88eb1af295391006e04cd/libraries/AP_NavEKF3/AP_NavEKF3_core.cpp)

[Aeron PLX external AHRS implementation](https://github.com/ArduPilot/ardupilot/blob/902f7ffb/libraries/AP_ExternalAHRS/AP_ExternalAHRS_Aeron_plx.cpp)
defines the Aeron fields and statuses. Support is field-gated and does not assume a firmware
release boundary. Inertial Labs text
transitions reference previous spoofing status
in some branches; the analyzer uses numeric `ILB5` records directly.

Tests use real in-memory `LogData` columns and schemas to verify receiver decoding, gaps,
recovery, multiple receivers and lanes, source changes, gravity/frame conversion, normal turns,
latency, uncertainty, synthetic discrepancies and report serialization. A local ordinary flight
log is also useful for parser integration and performance checks, but has no attack ground truth.
