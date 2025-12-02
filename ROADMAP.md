# Roadmap

This document outlines the planned development directions for the ArduPilot
Methodic Configurator project.
Our goal is to provide comprehensive, automated
configuration assistance for ArduPilot users across all vehicle types.

## Current Focus Areas

### Improved Automation

We are actively working to enhance automation in key configuration areas:

#### ESC Configuration

- **Goal**: Develop intelligent ESC (Electronic Speed Controller) configuration wizards
- **Benefits**: Reduce manual parameter tuning, minimize setup errors, optimize performance

#### Notch Filter Configuration

- **Goal**: Automated notch filter setup for vibration dampening and noise reduction
- **Benefits**: Improved flight stability, automatic frequency detection, reduced pilot workload

## Future Vehicle Support Expansion

Currently, the ArduPilot Methodic Configurator primarily supports ArduCopter.
We plan to extend support to additional ArduPilot vehicle types:

### Planned Vehicle Support

- **ArduPlane** (fixed-wing aircraft)
- **Rover** (ground vehicles)
- **Helicopter** (rotary-wing aircraft)
- **ArduSub** (submarine vehicles)
- **Boat** (surface water vehicles)
- **Blimp** (lighter-than-air vehicles)

### Implementation Approach

- Create vehicle-specific configuration templates
- Develop vehicle-appropriate parameter sets
- Add vehicle-specific automation features
- Ensure compatibility with ArduPilot's vehicle-specific firmware

## How You Can Help

We need contributors to help realize this roadmap! Here's how you can get involved:

### For Vehicle Support Expansion

- Expertise in specific vehicle types (planes, rovers, helicopters, etc.)
- Knowledge of vehicle-specific ArduPilot parameters
- Testing capabilities for target vehicles

### Getting Started

1. Review our [Contributing Guide](https://github.com/ArduPilot/MethodicConfigurator/blob/master/CONTRIBUTING.md)
2. Check existing [GitHub Issues](https://github.com/ArduPilot/MethodicConfigurator/issues)
   for related tasks
3. Submit [Pull Requests](https://github.com/ArduPilot/MethodicConfigurator/pulls)
   with your improvements

## Timeline

- **Q4 2025**: Complete ESC configuration automation prototype
- **Q1 2026**: Release notch filter automation tools
- **Q2 2026**: Add ArduPlane support
- **Q3-Q4 2026**: Extend support to Rover and Helicopter
- **2027**: Complete support for remaining vehicle types

*Note: Timeline is indicative and depends on contributor availability and project priorities.*

## Reached Milestones

- 2025.11.26 - 83% of [Gold OSS best practices](https://www.bestpractices.dev/en/projects/9101?criteria_level=2) reached
- 2025.11.25 - [91% test coverage](https://coveralls.io/builds/76659097)
- 2025.11.22 - 100 Github stars
- 2025.11.06 - [Motor test plugin](https://github.com/ArduPilot/MethodicConfigurator/releases/tag/v2.7.2)
- 2025.10.05 - [80% test coverage](https://coveralls.io/builds/75828379)
- 2025.09.25 - Added [download last flight log button](https://github.com/ArduPilot/MethodicConfigurator/releases/tag/v2.3.0)
- 2025.09.04 - Added [empty, unopinionated vehicle templates](https://github.com/ArduPilot/MethodicConfigurator/releases/tag/v2.1.0)
- 2025.08.28 - Option to [reset all parameters to their defaults before starting the configuration](https://github.com/ArduPilot/MethodicConfigurator/releases/tag/v2.0.6)
- 2025.07.16 - [YouTube beginners Tutorial](https://www.youtube.com/watch?v=tM8EznlNhgs&list=PL1oa0qoJ9W_89eMcn4x2PB6o3fyPbheA9)
- 2025.06.15 - The tuning guide is the [single most liked post in the ArduPilot forum](https://discuss.ardupilot.org/badges/20/great-topic)
- 2025.04.26 - [First YouTube video Tutorial](https://www.youtube.com/watch?v=47RjQ_GarvE)
- 2025.04.02 - Initial ArduPlane template and support
- 2025.02.20 - [AI powered, ArduPilot trained chatbot](https://gurubase.io/g/ardupilot)
- 2025.01.27 - [40% test coverage](https://coveralls.io/builds/71941955)
- 2024.12.18 - Reached all initially defined project features
- 2024.03.14 - [First public release](https://discuss.ardupilot.org/t/new-ardupilot-methodic-configurator-gui/115038)
- 2023.12.15 - Posted the [tuning guide](https://discuss.ardupilot.org/t/how-to-methodically-configure-and-tune-any-arducopter/110842)

<!-- Gurubase Widget -->
<script async src="https://widget.gurubase.io/widget.latest.min.js"
    data-widget-id="uE4kxEE4LY3ZSyfNsF5bU6gIOnWGTBOL_e16KwDH-0g"
    data-text="Ask AI"
    data-margins='{"bottom": "1rem", "right": "1rem"}'
    data-light-mode="true"
    id="guru-widget-id">
</script>
