# Translate the user interface

## Adding a translation

To add a new translation language to the Ardupilot Methodic Configurator, follow the steps below.
This process involves creating a new language folder in the locale directory and generating the necessary translation files.
You will use the `create_pot_file.py` script to extract the strings that need translation and create a `.pot` file, which serves as a template for the translation.

### 1. Set Up Your Local Code Repository

If not done already navigate to a directory where you want to checkout the git repository and execute:

```cmd
git clone https://github.com/ArduPilot/MethodicConfigurator.git
cd MethodicConfigurator
```

On windows do:

```cmd
.\SetupDeveloperPC.bat
.\install_msgfmt.bat
.\install_wsl.bat
```

On Linux and macOS do:

```bash
./SetupDeveloperPC.sh
```

### 2. Create a New Language Directory

Navigate to the `locale` directory inside your project:

```bash
cd ardupilot_methodic_configurator/locale
```

Create a new folder for the language you want to add. The name of the folder should follow the standard language code format (e.g., de for German, fr for French).

```bash
mkdir <language_code>
```

For example, to add support for German:

```bash
mkdir de
```

Add the language to the end of the `LANGUAGE_CHOICES` array in the `ardupilot_methodic_configurator/internationalization.py` file.

For example, to add support for German:

```python
LANGUAGE_CHOICES = ["en", "zh_CN", "pt", "de", "it", "ja"]
```

Add it also to the test on `tests\test_internationalization.py` file:

```python
    def test_language_choices(self) -> None:
        expected_languages = ["en", "zh_CN", "pt", "de", "it", "ja"]
        assert expected_languages == LANGUAGE_CHOICES
```

and `.vscode\tasks.json` file:

```json
            "description": "Select language code:",
            "options": ["all", "zh_CN", "pt", "de", "it", "ja"],
```

and add the language as `Natural Language ::` to the `classifiers` array in the `ardupilot_methodic_configurator/pyproject.toml` file.

### 3. Create a New PO File

Inside your newly created language directory, create a new `.po` file using the `.pot` template:

```bash
cd de
mkdir LC_MESSAGES
cp ../ardupilot_methodic_configurator.pot LC_MESSAGES/ardupilot_methodic_configurator.po
```

### 4. Bulk translate the strings (optional)

You can bootstrap your translation using translation services that translate full files.
To do so navigate to the project root and issue:

```bash
cd ..\..\..
python extract_missing_translations.py --lang-code=de
```

It will store the result of the bulk translations into n `missing_translations_de[_n].txt` file(s).

Now translate that file(s), or feed it to on-line translation service.
Put all missing translations into a single `missing_translations_de.txt`
Once done, insert the translations into the `.po` file:

```bash
python insert_missing_translations.py --lang-code=de
```

### 5. Translate the Strings

Open the `ardupilot_methodic_configurator.po` file in a text editor or a specialist translation tool (e.g., [Poedit](https://poedit.net/)).
You will see the extracted strings, which you can begin translating.

Each entry will look like this:

```text
msgid "Original English String"
msgstr ""
```

Fill in the `msgstr` lines with your translations:

```text
msgid "Original English String"
msgstr "Translated String"
```

### 6. Compile the PO File

Once you have completed your translations, you will need to compile the `.po` file into a binary `.mo` file. This can be done using the command:

On windows:

```bash
python create_mo_files.py
```

On Linux or macOS:

```bash
python3 create_mo_files.py
```

Make sure you have `msgfmt` installed, which is part of the *GNU gettext* package.
On windows use the `.\install_msgfmt.bat` command.

### 7. Test the New Language

Add it to the `[Languages]` and `[Icons]` sections of the `windows/ardupilot_methodic_configurator.iss` file.

```text
[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "zh_CN"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "pt"; MessagesFile: "compiler:Languages\Portuguese.isl"
Name: "de"; MessagesFile: "compiler:Languages\German.isl"
...

```

With the new `.mo` file created, you should ensure the software correctly loads the new language.
Update the software's configuration to set the desired language and run the application to test your translations.

### 8. Review and Refine

Once the new language is running in the software, review the translations within the application for clarity and correctness.
Make adjustments as needed in the `.po` file and recompile to an `.mo` file.

Following these steps should enable you to successfully add support for any new translation language within the Ardupilot Methodic Configurator.

## Update an existing translation

There is a [github action to automatically update the translations using AI](https://github.com/ArduPilot/MethodicConfigurator/tree/master/.github/workflows/i18n-extract.yml).
To manually update an existing translation do the following steps:

### 1. Install Poedit and open the .po and pot files

Install [Poedit v3.5.2 or greater](https://poedit.net/download) on your PC.

Open the existing `.po` file for your language.
Either [download the file from the locale directory in github.com](https://github.com/ArduPilot/MethodicConfigurator/tree/master/ardupilot_methodic_configurator/locale)
or if you have a local git checkout of `ardupilot_methodic_configurator/locale` use it.

![Open .po file](images/Poedit_01.png)

Here is an example for the italian translation:

![Select .po file](images/Poedit_02.png)

Update the translation by importing the latest `.pot` file.

![Update translation from .pot file](images/Poedit_03.png)

Either [download the file from the locale directory in github.com](https://github.com/ArduPilot/MethodicConfigurator/tree/master/ardupilot_methodic_configurator/locale)
or if you have a local git checkout of `ardupilot_methodic_configurator/locale` use it.

![Select .pot file](images/Poedit_04.png)

Validate the translation

![Validate translation](images/Poedit_05.png)

### 2. Update and improve each translation string

Search the table for strings that have not been translated yet and translate them.
Update and improve each translation string.

Save the result and either send the `.po` file to the team,
or create a gitlab Pull request with the changes to the `.po` file.
The github [robot will automatically convert that `.po` file into a `.mo` file](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/update_mo_files.yml)
and create an [*ArduPilot methodic configurator* installer](https://github.com/ArduPilot/MethodicConfigurator/actions/workflows/windows_build.yml)
that you can use to test the translations.
