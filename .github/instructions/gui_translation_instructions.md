# GUI Translation Instructions for ArduPilot Methodic Configurator

> **See also**: [GitHub Copilot repository instructions](../copilot-instructions.md) for general project context.

This document provides step-by-step instructions for AI-assisted update of existing ArduPilot Methodic Configurator GUI translations.

## Prerequisites

1. **Local git repository**: Working in a local git checkout (files are under version control - no backup needed)
1. **Development dependencies**: Install all required translation tools:

```bash
uv pip install .[dev]
```

1. **Translation Tool (optional)**: [Poedit](https://poedit.net/download) v3.5.2+ for visual editing of `.po` files

## Overview

The ArduPilot Methodic Configurator uses GNU gettext for internationalization.
All user-facing strings are wrapped with `_()` function calls and extracted into `.pot` template files,
then translated into language-specific `.po` files, which are compiled into binary `.mo` files used by the application.

## AI-Assisted Translation Workflow

### For Updating Existing Languages

1. **Extract missing translations**: Execute `python extract_missing_translations.py` in the project root directory.
   The script automatically detects all existing languages and creates/updates `missing_translations_<lang_code>.txt` files in the root directory.

1. **Translate strings**: Open each `missing_translations_<lang_code>.txt` file and translate the strings from English to the target language.
   Follow the translation guidelines defined below.

1. **Insert translations**: Execute `python insert_missing_translations.py` in the project root directory.
   The script automatically processes all language files and inserts the translated strings into their respective `.po` files in `ardupilot_methodic_configurator/locale/<lang_code>/LC_MESSAGES/`.

1. **Compile and validate**: Execute `python create_mo_files.py` in the project root directory.
   This compiles the `.po` files into binary `.mo` files and performs partial validation of the translation files.

1. **Test translations**: Run the application with your language to verify the translations appear correctly in the GUI.

## Translation Guidelines

### String Formatting

- **Preserve placeholders**: Keep `{variable_name}` placeholders intact
- **Context matters**: Consider the UI context when translating
- **Length considerations**: Some languages are more verbose - ensure UI layout accommodates longer text

### Quality Assurance

1. **Consistency**: Use consistent terminology throughout
2. **Context**: Understand where strings appear in the GUI
3. **Testing**: Always test translations in the actual application
4. **Cultural adaptation**: Adapt to local conventions, not just literal translation

### Language-Specific Guidelines

- **Portuguese (pt)**: Use European Portuguese (Portugal) conventions, not Brazilian Portuguese
  - Prefer "transferir" over "baixar" for "download"
  - Use formal register appropriate for technical documentation
  - Follow Portuguese spelling reform standards

### Technical Considerations

- **Encoding**: Files must be UTF-8 encoded
- **Line endings**: Use appropriate line endings for your platform
- **Special characters**: Ensure proper handling of accented characters and special symbols

## Troubleshooting

### Common Issues

- **Script not found**: Ensure you're running commands from the project root directory
- **Permission errors**: On Linux/macOS, you may need to use `python3` instead of `python`
- **Missing .po files**: The language must already exist - this workflow only updates existing translations
- **Encoding issues**: Ensure your text editor saves files as UTF-8
- **Validation errors**: The `create_mo_files.py` script performs basic validation and will report syntax errors in `.po` files

### File Locations

- **Source files**: `missing_translations_<lang_code>.txt` (project root)
- **Translation files**: `ardupilot_methodic_configurator/locale/<lang_code>/LC_MESSAGES/ardupilot_methodic_configurator.po`
- **Compiled files**: `ardupilot_methodic_configurator/locale/<lang_code>/LC_MESSAGES/ardupilot_methodic_configurator.mo`

## Support

- **Documentation**: See [ARCHITECTURE.md](../ARCHITECTURE.md) for detailed technical information
