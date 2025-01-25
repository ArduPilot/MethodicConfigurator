#!/usr/bin/env python3

"""
Use Copilot to translate multiple source files and combine results.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import argparse
import asyncio
import glob
import logging
from pathlib import Path

from github.copilot import CopilotClient


class CopilotTranslator:  # pylint: disable=too-few-public-methods
    """Handles translations using GitHub Copilot's completion features."""

    def __init__(self, from_lang: str, to_lang: str) -> None:
        self.client = CopilotClient()
        self.from_lang = from_lang
        self.to_lang = to_lang
        self.retries = 3

    async def translate(self, text: str) -> str:
        """Translate text with retries."""
        prompt = f"""
        Translate the following text from english to {self.to_lang}.
        Context: This is a GUI string from ArduPilot Methodic Configurator software.
        Keep technical terms unchanged.
        Original text: {text}
        Translation:"""

        last_error = None
        for attempt in range(self.retries):
            try:
                response = await self.client.complete(prompt)
                if response and response.choices and isinstance(response.choices[0].text, str):
                    return response.choices[0].text.strip()
            except Exception as e:  # noqa: PERF203
                last_error = e
                if attempt < self.retries - 1:
                    await asyncio.sleep(1)
                    continue
                msg = f"Translation failed after {self.retries} attempts"
                raise ValueError(msg) from last_error

        msg = "Unexpected response format from CopilotClient"
        raise ValueError(msg) from None


def find_source_files(base_pattern: str) -> list[Path]:
    """Find all chunk files matching pattern."""
    return sorted(Path(p) for p in glob.glob(base_pattern))


def read_source_file(file_path: Path) -> list[tuple[int, str]]:
    """Read source file and return list of (index, text) tuples."""
    entries = []
    with open(file_path, encoding="utf-8") as f:
        for line in f:
            if ":" in line:
                idx, text = line.strip().split(":", 1)
                entries.append((int(idx), text))
    return entries


async def translate_entries(translator: CopilotTranslator, entries: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Translate all entries in a chunk."""
    translations = []
    for idx, text in entries:
        translation = await translator.translate(text)
        translations.append((idx, translation))
        logging.info("Translated %d: %s → %s", idx, text, translation)
    return translations


def write_translations(filename: str, translations: list[tuple[int, str]]) -> None:
    """Write combined translations to output file."""
    with open(filename, "w", encoding="utf-8") as f:
        for idx, trans in sorted(translations):
            f.write(f"{idx}:{trans}\n")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--to-lang", default="zh_CN")
    parser.add_argument("--source-pattern", default="missing_translation_zh_CN*.txt")
    parser.add_argument("--output-file", default="missing_translations.txt")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    try:
        # Initialize translator
        translator = CopilotTranslator(args.from_lang, args.to_lang)

        # Find and process all chunk files
        source_files = find_source_files(args.source_pattern)
        if not source_files:
            msg = f"No files found matching {args.source_pattern}"
            raise FileNotFoundError(msg)

        # Process each chunk and collect translations
        all_translations = []
        for source_file in source_files:
            logging.info("Processing %s", source_file)
            entries = read_source_file(source_file)
            chunk_translations = await translate_entries(translator, entries)
            all_translations.extend(chunk_translations)

        # Write combined translations
        write_translations(args.output_file, all_translations)
        logging.info("Successfully translated %d strings to %s", len(all_translations), args.output_file)

    except Exception as e:
        logging.error("Translation failed: %s", str(e))
        raise


if __name__ == "__main__":
    asyncio.run(main())
