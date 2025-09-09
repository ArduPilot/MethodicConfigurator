# GitHub Actions AI Inference Prompts

This directory contains prompt templates for automated workflows that use GitHub's AI inference action.

## translate.prompt.yml

Used by the i18n-extract workflow to automatically translate missing translation strings for the ArduPilot Methodic Configurator GUI.

### Features

- Professional technical translation for aviation/drone software
- Preserves placeholders and formatting
- Language-specific guidelines for Portuguese, German, Italian, Japanese, and Chinese
- Maintains consistent terminology
- Preserves line number format required by the translation scripts

### Usage

This prompt is automatically generated and used by the GitHub Actions workflow in
`.github/workflows/i18n-extract.yml` when new translatable strings are detected in the source code.

The workflow:

1. Extracts new strings from source code
2. Merges them into existing .po files
3. Identifies missing translations
4. Uses AI to translate them
5. Inserts translations back into .po files
6. Compiles .mo files
7. Creates a pull request with the changes

### Quality Assurance

While AI translations provide a good starting point, they should always be reviewed by native speakers familiar with:

- Technical aviation terminology
- Cultural context
- User interface conventions
- ArduPilot-specific terminology

The generated pull requests include a note requesting human review before merging.
