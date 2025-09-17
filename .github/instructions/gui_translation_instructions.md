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

1. **Update POT template**: Execute `python create_pot_file.py` in the project root directory.
   This extracts all translatable strings from the source code and updates the `.pot` template file.

1. **Merge new strings**: Execute `python merge_pot_file.py` in the project root directory.
   This merges new strings from the updated `.pot` file into all existing `.po` files, adding new untranslated entries.

1. **Extract missing translations**: Execute `python extract_missing_translations.py` in the project root directory.
   The script automatically detects all existing languages and creates/updates `missing_translations_<lang_code>.txt` files in the root directory.

1. **Translate strings in-place**: Open each `missing_translations_<lang_code>.txt` file and **directly replace** the English text with the target language translation.
   Follow the translation guidelines defined below.

   **CRITICAL**: Do NOT create new files. You must edit the original `missing_translations_<lang_code>.txt` files in-place.
   The translation files contain lines in the format `line_number:English text`.
   You must replace the English text with the translated text, keeping the line number and colon exactly as they are.

   Example:

   ```text
   Before: 3614:Copy vehicle image from template
   After:  3614:Copiar imagem do veículo do modelo
   ```

   **Do NOT do this**:
   - Creating files with names like `missing_translations_<lang_code>_translated.txt`
   - Changing the line numbers
   - Removing the colon separator

1. **Insert translations**: Execute `python insert_missing_translations.py` in the project root directory.
   The script automatically processes all language files and inserts the translated strings into their respective `.po` files in `ardupilot_methodic_configurator/locale/<lang_code>/LC_MESSAGES/`.

   **Note**: The script processes all languages in a single run, so you only need to execute it once after translating all language files.

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
  - Use "ficheiro" instead of "arquivo" for "file"
  - Use formal register appropriate for technical documentation
  - Follow Portuguese spelling reform standards
  - While "você" is acceptable, consider more formal alternatives when appropriate

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
