# Components and FC connections editor usage

Here you should enter information about you vehicle components and their respective connection to the flight controller.

Most optional information fields are only visible in `normal` GUI complexity mode.

All components have **optional** information about the product itself:

![product](images\blog\component_editor_product.png)

The URL can be used to store a link to a datasheet or a link to a shop product page.

Some components have **optional** information about their firmware:

![firmware](images\blog\component_editor_firmware.png)

All components have an **optional** notes field.

## Flight Controller

![flight controller](images\blog\component_editor_flight_controller.png)

Some information, if available, is automatically filed in by the software as seen in the example above.

## Frame

![frame](images\blog\component_editor_frame.png)

The minimum take off weight and the maximum take off weight in Kilo are entered here.
If you have variable payload configure the vehicle at the minimum take off weight.
Only after completely tuned can you add the additional payload.

## Battery Monitor

All supported connection types and their corresponding protocols are:

| Connection Type | Protocol |
|----------------|----------|
| `None` | `Disabled` |
| `Analog` | `Analog Voltage Only` |
| `Analog` | `Analog Voltage and Current` |
| `Analog` | `FuelLevelAnalog` |
| `Analog` | `Synthetic Current and Analog Voltage` |
| `I2C1`–`I2C4` | `Solo` |
| `I2C1`–`I2C4` | `Bebop` |
| `I2C1`–`I2C4` | `SMBus-Generic` |
| `I2C1`–`I2C4` | `FuelFlow` |
| `I2C1`–`I2C4` | `SMBUS-SUI3` |
| `I2C1`–`I2C4` | `SMBUS-SUI6` |
| `I2C1`–`I2C4` | `NeoDesign` |
| `I2C1`–`I2C4` | `SMBus-Maxell` |
| `I2C1`–`I2C4` | `Generator-Elec` |
| `I2C1`–`I2C4` | `Generator-Fuel` |
| `I2C1`–`I2C4` | `Rotoye` |
| `I2C1`–`I2C4` | `MPPT` |
| `I2C1`–`I2C4` | `INA2XX` |
| `I2C1`–`I2C4` | `LTC2946` |
| `I2C1`–`I2C4` | `EFI` |
| `I2C1`–`I2C4` | `AD7091R5` |
| `CAN1`–`CAN2` | `DroneCAN-BatteryInfo` |
| `PWM` | `FuelLevelPWM` |
| `SPI` | `INA239_SPI` |
| `other` | `ESC` |
| `other` | `Sum Of Selected Monitors` |
| `other` | `Torqeedo` |
| `other` | `Scripting` |

It is strongly recommended to use a battery monitor.
But if you do not have one select `none` in the flight controller connection:

![battery monitor none](images\blog\component_editor_battery_monitor_none.png)

If your battery monitor has an analog connection to the FC, select `analog` and one of the possible protocols:

![battery monitor analog](images\blog\component_editor_battery_monitor_analog.png)

If your battery monitor has an I2C connection to the FC, select the I2C bus and one of the possible protocols:

![battery monitor i2c](images\blog\component_editor_battery_monitor_i2c.png)

If your battery monitor has a CAN connection to the FC, select the CAN bus:

![battery monitor can](images\blog\component_editor_battery_monitor_can.png)

If your battery monitor has a SPI connection to the FC, select the SPI bus:

![battery monitor spi](images\blog\component_editor_battery_monitor_spi.png)

If your battery monitor has a PWM connection to the FC, select the PWM:

![battery monitor pwm](images\blog\component_editor_battery_monitor_pwm.png)

Otherwise select `other` and one of the possible protocols:

![battery monitor other](images\blog\component_editor_battery_monitor_other.png)

## Battery

![battery](images\blog\component_editor_battery.png)

Select the correct battery chemistry, doing so will automatically set typical voltage thresholds for that battery chemistry.

Afterwords you should tweak the voltage thresholds to meet your requirements.

- `Volt per cell max` - PID values will only scale when below this voltage
- `Volt per cell arm` - vehicle will only arm if battery voltage is above this threshold
- `Volt per cell low` - first failsafe level gets triggered when below this value
- `Volt per cell crit` - second failsafe level gets triggered when below this value
- `Volt per cell min` - PID values will only scale when above this voltage

They must obey `Volt per cell crit` < `Volt per cell low` < `Volt per cell arm` < `Volt per cell max`

`Number of cells` is the number of cells connected in series.
For a 6S battery this is 6.

## ESC

Electronic speed controllers have a `FC->ESC Connection` for control of the motor speed and an optional `ESC->FC Telemetry` for telemetry feedback from the ESC to the flight controller.

![esc main out](images\blog\component_editor_esc_main_out.png)

The `FC->ESC Connection` type can be `Main Out`, an `AIO` integrated output, a serial port, or a CAN bus.
The protocol is determined by the `MOT_PWM_TYPE` parameter (e.g. `Normal`, `DShot600`) for PWM outputs,
or the serial/CAN protocol (e.g. `FETtecOneWire`, `DroneCAN`) for digital connections.

The `ESC->FC Telemetry` type and protocol describe the return path:

| Protocol | Type | Notes |
|----------|------|-------|
| `None` | `None` | No telemetry |
| `BDShot` | same as FC->ESC | Bidirectional DShot on the same PWM wire |
| `DroneCAN` | CAN port | Telemetry over CAN bus |
| `ESC Telemetry` | serial port | Dedicated UART telemetry |
| `FETtecOneWire` | serial port | Bidirectional FETtec protocol on the same wire |

![esc telemetry placeholder](images\blog\component_editor_esc_telemetry.png)

## Motors

![motors placeholder](images\blog\component_editor_motors.png)

Enter the number of magnetic **poles** of the motor rotor.
This is the **P** number in the common `nNmP` motor winding notation (e.g. `12N14P` → 14 poles).
The value must be an even integer.
It is used by ArduPilot to calculate the actual motor RPM from the ESC telemetry electrical frequency.

## Propellers

![propellers placeholder](images\blog\component_editor_propellers.png)

Enter the propeller **diameter in inches**.
This value affects automatic PID tuning (AutoTune) and is used for thrust and performance calculations.

## GNSS Receiver

![gnss placeholder](images\blog\component_editor_gnss.png)

Select the FC connection **type** (serial port or CAN bus) and the matching **protocol**:

| Protocol | Connection |
|----------|------------|
| `AUTO` | serial port — auto-detect |
| `uBlox` | serial port |
| `DroneCAN` | CAN bus |
| other | serial port — vendor-specific |

If you do not have a GNSS receiver, select `None` as the connection type.

## RC Controller

![rc controller placeholder](images\blog\component_editor_rc_controller.png)

The hand-held controller used by the pilot.
Enter the manufacturer and model for documentation purposes.
This component has no FC connection — it communicates wirelessly via the RC Transmitter and RC Receiver pair.

## RC Transmitter

![rc transmitter placeholder](images\blog\component_editor_rc_transmitter.png)

The RF transmitter module (may be integrated in the RC Controller or a separate module).
Enter the manufacturer and model for documentation purposes.
This component has no FC connection.

## RC Receiver

![rc receiver placeholder](images\blog\component_editor_rc_receiver.png)

Select the FC connection **type** and **protocol** that match how the receiver is wired to the flight controller:

| Protocol | Connection |
|----------|------------|
| `All` | RCin/SBUS — auto-detect all protocols |
| `PPM` | RCin/SBUS |
| `SBUS` / `SBUS_NI` | RCin/SBUS or serial |
| `DSM` | serial port |
| `CRSF` | serial port |
| `FPORT` | serial port |
| `MAVRadio` | serial port |
| other | serial port — vendor-specific |

If your receiver is connected to a dedicated RC input pin, choose `RCin/SBUS` as the type.
If it is connected to a UART (e.g. CRSF, FPORT, DSM), choose the corresponding serial port.

## Telemetry

![telemetry placeholder](images\blog\component_editor_telemetry.png)

Select the FC connection **type** (serial port or CAN bus) and the matching **protocol**:

| Protocol | Notes |
|----------|-------|
| `MAVLink2` | recommended for most ground stations |
| `MAVLink1` | legacy ground stations |
| `MAVLink High Latency` | satellite / low-bandwidth links |
| `DDS XRCE` | ROS 2 micro-XRCE-DDS bridge |
| other | vendor-specific |

If you do not have a telemetry radio, select `None` as the connection type.
