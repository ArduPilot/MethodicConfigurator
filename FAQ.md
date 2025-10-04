# ArduPilot Methodic Configurator - Frequently Asked Questions

This document contains answers to the most commonly asked questions about the ArduPilot Methodic Configurator.

> 💡 **Quick Links**: [User Manual](USERMANUAL.md) | [Quick Start](README.md) | [Use Cases](USECASES.md) | [Support](SUPPORT.md)

## General Questions

**Q: Do I need to be connected to the internet?**

A: Not required for basic operation, but recommended for:

- Downloading parameter documentation automatically
- Checking for software updates
- Accessing online help and support resources

**Q: Can I use this with any ArduPilot vehicle?**

A: Yes, it supports all ArduPilot vehicle types including:

- ArduCopter (multirotors)

But these have no templates nor documentation yet:

- ArduCopter (helicopters)
- ArduPlane (fixed-wing aircraft and VTOL)
- ArduSub (underwater vehicles)
- Rover (ground vehicles, boats)
- ArduPilot Periph (peripheral devices)
- SITL (Software In The Loop simulation)

**Q: How long does the configuration process take?**

A: Typically 30-60 minutes for a complete configuration, depending on:

- Your vehicle's complexity
- Number of components to configure
- Your familiarity with the process
- Whether you read all the documentation (recommended)

**Q: What happens if I lose connection during configuration?**

A: The software creates backup files at each step. You can:

- Reconnect and resume from where you left off
- Restore previous configurations if needed
- Review what was already uploaded using the parameter comparison

**Q: Can I configure multiple vehicles with the same setup?**

A: Yes! This is one of the key benefits:

- Reuse template files across similar vehicles
- Only 3 files are vehicle-instance specific (calibrations)
- All other files can be shared between identical vehicle builds
- Great for commercial manufacturers or fleet operations

## Technical Questions

**Q: What if I make a mistake during configuration?**

A: Multiple safety nets are built in:

- **Backup files**: Every time the software connects to the vehicle it creates a backup on the vehicle project directory
- **Parameter validation**: Invalid values are caught before upload
- **Restore capability**: You can restore previous configurations
- **File editing**: Parameter files are plain text and easily editable
- **Step-by-step approach**: Small changes reduce risk of major errors

**Q: Can I modify parameter files manually?**

A: Absolutely! Parameter files are designed for manual editing:

- **Plain text format**: Use any text editor (Notepad++, VS Code, etc.)
- **Well documented**: Each parameter includes full documentation
- **Commented**: Reasons for each change are included
- **Version control friendly**: Text files work great with Git, etc.

**Q: What's the difference between template and instance-specific parameters?**

A: Parameters are color-coded in the interface:

- **Template parameters**: Can be reused across similar vehicles
- **Instance-specific parameters** (🟨 yellow background): Unique to each vehicle
  - IMU calibrations
  - Compass calibrations
  - Baro calibrations
  - Hardware serial numbers

**Q: Do I need to upload parameters in order?**

A: Yes, the order matters because:

- **Dependencies**: Later parameters may depend on earlier ones
- **Validation**: Some parameters are only available after others are set
- **Safety**: The sequence is designed for safe, incremental configuration
- **Testing**: Allows for test flights between logical groups of changes

**Q: What if my flight controller firmware is different?**

A: The software handles version differences:

- **Automatic adaptation**: Parameters are filtered by firmware version
- **Documentation matching**: Parameter docs match your firmware
- **Missing parameters**: Safely skipped if not available in your firmware
- **Version warnings**: You'll be notified of compatibility issues

**Q: Can I use this for custom flight controller builds?**

A: Yes, as long as they run ArduPilot firmware:

- **Standard ArduPilot**: Works with any standard ArduPilot build
- **Custom parameters**: You can add custom parameters to files
- **Hardware variations**: Component editor handles most hardware differences
- **Firmware modifications**: May require custom parameter documentation

## Workflow Questions

**Q: Can I skip the component editor?**

A: You can skip it with `--skip-component-editor`, but only if:

- **All components configured**: Every component and connection is already set
- **No changes needed**: Your hardware setup hasn't changed
- **Experienced user**: You understand the implications of skipping validation

**Q: What if I need to change something after completion?**

A: Easy to make changes:

- **Re-run specific steps**: Jump to any parameter file with the *current intermediate parameter file* combobox or the `-n` command line option
- **Edit and re-upload**: Modify parameter files and upload changes
- **Component changes**: Re-run component editor if hardware changes
- **Incremental updates**: No need to redo everything

**Q: Can I compare configurations between vehicles?**

A: Yes, several ways:

- **Parameter files**: Compare text files directly
- **Summary files**: Compare the generated summary files
- **Version control**: Use Git to track changes over time
- **Documentation**: Change reasons help understand differences

**Q: Should I reset my flight controller to default parameters before starting?**

A: It depends on your situation:

- **Recommended for new vehicles**: Start with default values to guarantee all parameters have sane baseline values
- **Recommended after major changes**: If you've made significant hardware or configuration changes
- **Not necessary for minor adjustments**: If your vehicle is already operating correctly and you're just making small tweaks
- **Clean slate approach**: Provides the most predictable and documented configuration process

See the [ArduPilot documentation on parameter reset](https://ardupilot.org/copter/docs/common-parameter-reset.html) for instructions.

**Q: Can I use the software without connecting to a flight controller?**

A: Yes! You can work offline to:

- **Review configurations**: Examine existing parameter files
- **Edit parameters**: Modify parameter files using any text editor
- **Compare setups**: Review different vehicle configurations
- **Plan configurations**: Prepare parameter files before connecting hardware
- **Learn the process**: Understand the methodology without hardware

Use the "Skip FC connection, just edit .param files on disk" option when starting the software.

**Q: What do I do after changing a vehicle component?**

A: The steps depend on what you changed:

- **Flight Controller**: Redo all configuration steps
- **Frame/Weight changes**: Redo step 19 and above (tuning-related)
- **RC system changes**: Redo step 05 and RC parts of step 12
- **Telemetry**: Redo step 06
- **Battery/ESC/Motors**: Redo steps 07, 08 and tuning steps (19+)
- **Propellers**: Redo steps 07, 11 and above
- **GNSS receiver**: Redo step 10

The software allows you to jump to specific parameter files, so you don't need to start from scratch.

**Q: How do I create a configuration from an already-working vehicle?**

A: You can clone an existing working configuration:

1. Connect your already-configured flight controller
2. Select a template that resembles your vehicle
3. **Check the `Use parameter values from connected FC, not from template files` option**
4. This creates a configuration based on your current working parameters
5. Follow the component editor to document your setup
6. Great for creating backups or templates for similar vehicles

## Need More Help?

If your question isn't answered here:

1. **Check the User Manual**: [USERMANUAL.md](USERMANUAL.md) has comprehensive documentation
2. **Review Troubleshooting**: The user manual includes detailed troubleshooting sections
3. **Community Support**: Ask on the [ArduPilot Forum](https://discuss.ardupilot.org/)
4. **Report Issues**: Create an issue on [GitHub](https://github.com/ArduPilot/MethodicConfigurator/issues)
5. **Professional Support**: Visit [support options](SUPPORT.md)

---

**Last Updated**: October 2025
**Document Version**: 1.0
**Software Version**: Compatible with ArduPilot Methodic Configurator 2.3.0+
