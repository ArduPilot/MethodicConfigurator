# Motor Diagrams Update Instructions

This document provides AI-assisted instructions for updating the ArduPilot motor diagram SVG files in the ArduPilot Methodic Configurator.

## Overview

The ArduPilot Methodic Configurator includes motor diagram SVG files that help users understand the correct motor order and rotation for their vehicle frame type.
These diagrams are sourced from the official ArduPilot documentation at <https://ardupilot.org/copter/docs/connect-escs-and-motors.html>.

## Automated Update Process

The `scripts/download_motor_diagrams.py` script automatically downloads all motor diagram SVG files from the ArduPilot documentation.
This script is run periodically via GitHub Actions to keep the diagrams up to date.

## Manual Update Instructions

### Prerequisites

1. **Working Directory**: Ensure you're in the project root directory
2. **Network Access**: Internet connection required to download SVG files
3. **File Permissions**: Write access to `ardupilot_methodic_configurator/images/` directory

### Step-by-Step Process

1. **Run the Download Script**:

   ```bash
   python scripts/download_motor_diagrams.py
   ```

2. **Verify Downloads**: Check that all SVG files are present in `ardupilot_methodic_configurator/images/`

3. **Update Script if Needed**: If new motor diagrams are added to the ArduPilot documentation:
   - Visit <https://ardupilot.org/copter/docs/connect-escs-and-motors.html>
   - Identify new SVG diagram URLs in the format `https://ardupilot.org/copter/_images/m_*.svg`
   - Add the new SVG filenames to the `motor_diagrams` list in `scripts/download_motor_diagrams.py`

### AI Assistant Guidelines

When tasked with updating motor diagrams:

1. **Check Current State**:
   - Verify existing SVG files in `ardupilot_methodic_configurator/images/`
   - Check the current `motor_diagrams` list in the download script

2. **Fetch Latest Documentation**:
   - Use web scraping tools to examine <https://ardupilot.org/copter/docs/connect-escs-and-motors.html>
   - Extract all motor diagram SVG URLs from the page
   - Compare with the current list to identify new diagrams

3. **Update Script**:
   - Add any new SVG filenames to the `motor_diagrams` list
   - Maintain the existing categorization (QUAD, HEXA, OCTO, etc.)
   - Preserve the comment structure for clarity

4. **Download and Verify**:
   - Run the updated script to download new diagrams
   - Verify all downloads completed successfully
   - Check file sizes and integrity

## File Structure

```text
ardupilot_methodic_configurator/
├── images/
│   ├── ArduPilot_icon.png
│   ├── ArduPilot_logo.png
│   ├── m_01_00_quad_plus.svg
│   ├── m_01_01_quad_x.svg
│   ├── ... (all motor diagram SVGs)
│   └── m_14_01_deca_x_and_cw_x.svg
└── ...

scripts/
├── download_motor_diagrams.py
└── ...
```

## Motor Diagram Categories

The motor diagrams are categorized by frame type:

- **QUAD FRAMES** (m_01_*): Standard quadcopter configurations
- **HEXA FRAMES** (m_02_*): Hexacopter configurations  
- **OCTO FRAMES** (m_03_*): Octocopter configurations
- **OCTO QUAD FRAMES** (m_04_*): Octo-quad configurations
- **Y6 FRAMES** (m_05_*): Y6 configurations
- **TRICOPTER FRAMES** (m_07_*): Tricopter configurations
- **BICOPTER FRAMES** (m_10_*): Bicopter configurations
- **DODECAHEXA FRAMES** (m_12_*): 12-motor configurations
- **DECA FRAMES** (m_14_*): 10-motor configurations

## Integration with GUI

The downloaded SVG files are used by the motor test sub-application to display the correct motor layout diagram based on the
selected FRAME_CLASS and FRAME_TYPE parameters. The mapping between frame parameters and SVG files follows the ArduPilot convention:

- Frame class determines the base type (1=QUAD, 2=HEXA, 3=OCTO, etc.)
- Frame type determines the specific configuration (0=PLUS, 1=X, etc.)
- SVG filename format: `m_{frame_class:02d}_{frame_type:02d}_{description}.svg`

## Testing

After updating motor diagrams:

1. **Visual Verification**: Open SVG files to ensure they display correctly
2. **GUI Testing**: Test the motor test sub-application to verify diagrams display properly
3. **Size Check**: Ensure file sizes are reasonable (typically 5-50KB for SVG files)
4. **Python Code Linting**: Run `ruff check scripts/download_motor_diagrams.py` to ensure Python code quality
5. **Markdown Linting**: Use `npx markdownlint-cli2` or similar tools for markdown file validation (do not use ruff for markdown files)

## Troubleshooting

### Common Issues

1. **Download Failures**:
   - Check network connectivity
   - Verify ArduPilot documentation URLs are still valid
   - Check for rate limiting or access restrictions

2. **Missing Diagrams**:
   - Ensure all diagram URLs are included in the script
   - Check for new diagrams added to ArduPilot documentation

3. **File Corruption**:
   - Re-download affected files
   - Verify SVG file integrity by opening in a viewer

### Error Handling

The download script includes error handling for:

- Network connectivity issues
- Invalid URLs or missing files
- File system write permissions
- URL security validation (only HTTPS URLs allowed)

## Maintenance Schedule

- **Automated**: GitHub Actions runs the update script weekly
- **Manual Review**: Check for new ArduPilot releases quarterly
- **Code Review**: Review script updates when ArduPilot documentation structure changes

## Related Files

- `scripts/download_motor_diagrams.py`: Main download script
- `.github/workflows/update_motor_diagrams.yml`: CI/CD automation
- `windows/ardupilot_methodic_configurator.iss`: Windows installer configuration
- `ardupilot_methodic_configurator/frontend_tkinter_motor_test.py`: GUI integration
- `ARCHITECTURE_motor_test.md`: Motor test sub-application architecture

---

This document should be updated whenever the motor diagram update process or ArduPilot documentation structure changes.
