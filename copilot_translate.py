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
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

import aiohttp  # pylint: disable=import-error


@dataclass
class CompletionChoice:
    """
    Represents a single completion choice from the Copilot API response.

    Attributes:
        text: The completed text returned by Copilot

    """

    text: str


@dataclass
class CompletionResponse:
    """
    Contains the response data from a Copilot API completion request.

    Attributes:
        choices: List of completion choices returned by the API

    """

    choices: list[CompletionChoice]


class CopilotClient:  # pylint: disable=too-few-public-methods
    """Simple GitHub Copilot API client."""

    api_key: str
    headers: dict[str, str]

    def __init__(self) -> None:
        self.api_key = os.getenv("GITHUB_COPILOT_TOKEN", "")
        if not self.api_key:
            msg = "GITHUB_COPILOT_TOKEN environment variable not set"
            raise ValueError(msg)

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "OpenAI-Organization": "github-copilot",
            "X-Request-Id": str(uuid.uuid4()),
            "VScode-SessionId": str(uuid.uuid4()),
            "VScode-MachineId": "methodic-configurator",
            "Editor-Version": "vscode/1.85.0",
            "Editor-Plugin-Version": "copilot/1.138.0",
            "User-Agent": "GitHubCopilotChat/0.9",
        }

    async def complete(self, prompt: str) -> CompletionResponse:
        """Get completion from Copilot API."""
        endpoint = "https://api.githubcopilot.com/chat/completions"

        payload = {
            "model": "gpt-4",
            "messages": [
                {"role": "system", "content": "You are a translator assistant."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
            "n": 1,
            "stream": False,
        }

        try:
            async with (
                aiohttp.ClientSession() as session,
                session.post(endpoint, headers=self.headers, json=payload) as response,
            ):
                if response.status != 200:
                    error_text = await response.text()
                    logging.error("API Error: %s - %s", response.status, error_text)
                    msg = f"API request failed with status {response.status}: {error_text}"
                    raise ValueError(msg)

                data = await response.json()
                if "choices" not in data:
                    msg = f"Unexpected API response format: {data}"
                    raise ValueError(msg)

                return CompletionResponse(
                    choices=[CompletionChoice(text=choice["message"]["content"]) for choice in data["choices"]]
                )

        except aiohttp.ClientError as e:
            logging.error("Network error: %s", str(e))
            msg = "Network error occurred"
            raise ValueError(msg) from e


class CopilotTranslator:  # pylint: disable=too-few-public-methods
    """Handles translations using GitHub Copilot's completion features."""

    def __init__(self, to_lang: str) -> None:
        self.client: CopilotClient = CopilotClient()
        self.to_lang: str = to_lang
        self.retries: int = 3

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
    entries: list[tuple[int, str]] = []
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
    parser: argparse.ArgumentParser = argparse.ArgumentParser()
    parser.add_argument("--lang-code", default="zh_CN")
    parser.add_argument("--source-base-pattern", default="missing_translations_")
    parser.add_argument("--output-file", default="missing_translations.txt")
    args: argparse.Namespace = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    try:
        # Initialize translator
        translator: CopilotTranslator = CopilotTranslator(args.lang_code)

        source_pattern: str = f"{args.source_base_pattern}{args.lang_code}*.txt"
        # Find and process all chunk files
        source_files: list[Path] = find_source_files(source_pattern)
        if not source_files:
            msg = f"No files found matching {source_pattern}"
            raise FileNotFoundError(msg)

        # Process each chunk and collect translations
        all_translations: list[tuple[int, str]] = []
        for source_file in source_files:
            logging.info("Processing %s", source_file)
            entries: list[tuple[int, str]] = read_source_file(source_file)
            chunk_translations: list[tuple[int, str]] = await translate_entries(translator, entries)
            all_translations.extend(chunk_translations)

        # Write combined translations
        write_translations(args.output_file, all_translations)
        logging.info("Successfully translated %d strings to %s", len(all_translations), args.output_file)

    except Exception as e:
        logging.error("Translation failed: %s", str(e))
        raise


if __name__ == "__main__":
    asyncio.run(main())
