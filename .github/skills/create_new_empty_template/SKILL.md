---
name: create-new-empty-template
description: 'Create a new empty vehicle template for a new ArduPilot firmware version. Use when a new firmware release requires a fresh empty template directory under vehicle_templates/, involving flashing firmware, connecting to AMC, creating a project directory, and reviewing all configuration steps to handle renamed or removed parameters.'
---

# Create a New Empty Vehicle Template

When ArduPilot releases a new firmware version, some parameters are renamed, added, or removed.
A new empty template must be created for each firmware version to give users a reliable starting point.

Each of the 300+ supported flight controllers has different hardware capabilities and therefore slightly different parameters and default values.
It is impractical to maintain 300+ empty templates with only minor differences, so we provide a single empty template based on a commonly used flight controller.

## Prerequisites

- A widely used flight controller (e.g., Pixhawk 6C, CubeOrange)
- The latest ArduCopter firmware flashed to that flight controller
- ArduPilot Methodic Configurator (AMC) installed

## Steps

1. **Flash the firmware**: Install the latest ArduCopter firmware on the flight controller.
2. **Reboot the flight controller**: Disconnect and reconnect the USB cable so the FC completes its reboot.
3. **Connect to AMC**: Open AMC and connect to the flight controller.
4. **Create a new project directory**:
   - Click the **"Create a vehicle configuration directory from template"** button at the top of the AMC window.
   - Enable **"Reset flight controller parameters to their defaults"**.
   - Enable **"Use parameter values from connected FC, not from template files"**.
   - Enable **"Blank parameter change reason"**.
   - Choose a *base destination directory* where the project files will be saved (you will move them later).
   - Set the *destination new vehicle name* to e.g. `empty_4.7.x`.
   - Click **"Create a vehicle configuration directory from template"** to generate the project.
5. **Review all configuration steps**: For each step, handle parameters marked in orange (renamed or removed):
   - Click **Add** to add a replacement parameter - verify it serves the same purpose as the old one.
   - Click **Del** to remove the obsolete parameter.
   - Click **Skip** to proceed to the next step; confirm saving changes when prompted.
6. **Move and commit**: After completing all steps, move the generated project directory into `ardupilot_methodic_configurator/vehicle_templates/ArduCopter` and commit it to the repository.
