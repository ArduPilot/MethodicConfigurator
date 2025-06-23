#!/usr/bin/env -S uv run --script

# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "beautifulsoup4",
#     "requests",
# ]
# ///

"""
Outputs URLs of ArduPilot documentation pages.

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import logging
import time
from os import environ as os_environ
from typing import Union
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag

# Define the URL where to start crawling
URL = "https://ardupilot.org/ardupilot/"
USERNAME = "your_username"  # Replace with actual username if needed
PASSWORD = ""  # Replace with actual password if needed

# Crawls and outputs only URLs that start with:
ALLOWED_DOMAINS = (
    "ardupilot.org/ardupilot/",
    "ardupilot.org/copter/",
    "ardupilot.org/plane/",
    "ardupilot.org/rover/",
    "www.ardusub.com/",
    "ardupilot.org/blimp/",
    "ardupilot.org/antennatracker/",
    "ardupilot.org/planner/",
    "ardupilot.org/mavproxy/",
    "ardupilot.org/dev/",
    "ardupilot.github.io/MethodicConfigurator/",
    "mavlink.io/en/",
    "docs.cubepilot.org/",
    "doc.cuav.net/",
    "docs.holybro.com/",
)

URL_BLACKLIST = [
    "https://mavlink.io/en/messages/ASLUAV.html",
    "https://mavlink.io/en/messages/AVSSUAS.html",
    "https://mavlink.io/en/messages/all.html",
    "https://mavlink.io/en/messages/csAirLink.html",
    "https://mavlink.io/en/messages/dialects.html",
    "https://mavlink.io/en/messages/icarous.html",
    "https://mavlink.io/en/messages/matrixpilot.html",
    "https://mavlink.io/en/messages/paparazzi.html",
    "https://mavlink.io/en/messages/python_array_test.html",
    "https://mavlink.io/en/messages/test.html",
    "https://mavlink.io/en/messages/uAvionix.html",
    "https://mavlink.io/en/messages/ualberta.html",
]

URL_BLACKLIST_PREFIXES = ["https://docs.cubepilot.org/user-guides/~/changes/", "zh-hans", "doc.cuav.net/tutorial"]


# pylint: disable=duplicate-code
def get_env_proxies() -> Union[dict[str, str], None]:
    proxies_env = {
        "http": os_environ.get("HTTP_PROXY") or os_environ.get("http_proxy"),
        "https": os_environ.get("HTTPS_PROXY") or os_environ.get("https_proxy"),
        "no_proxy": os_environ.get("NO_PROXY") or os_environ.get("no_proxy"),
    }
    # Remove None values
    proxies_dict: dict[str, str] = {k: v for k, v in proxies_env.items() if v is not None}
    # define as None if no proxies are defined in the OS environment variables
    proxies = proxies_dict or None
    if proxies:
        logging.info("Proxies: %s", proxies)
    else:
        logging.debug("Proxies: %s", proxies)
    return proxies


# pylint: enable=duplicate-code


def remove_duplicates(visited_urls: set[str]) -> set[str]:
    # if the URL is https:// and the same URL exists as http://, remove the https:// URL from the list
    urls_to_remove = set()
    for url in visited_urls:
        if url.startswith("https://") and f"http://{url[8:]}" in visited_urls:
            urls_to_remove.add(url)
    visited_urls -= urls_to_remove

    # if visited URLs end in "/index.html", and the same URL without "/index.html" or without "index.html" is in the list,
    # remove the one with "/index.html" from the list
    urls_to_remove = set()
    for url in visited_urls:
        if url.endswith("/index.html") and (url[:-11] in visited_urls or url[:-10] in visited_urls):
            urls_to_remove.add(url)
    visited_urls -= urls_to_remove

    # if visited URLs end in "/", and the same URL without "/" is in the list, remove the one with "/" from the list
    urls_to_remove = set()
    for url in visited_urls:
        if url.endswith("/") and url[:-1] in visited_urls:
            urls_to_remove.add(url)
    visited_urls -= urls_to_remove

    # if visited URLs end in "common-*.html", and the file URL exists in with base URL http://ardupilot.org/copter/docs/,
    # remove it from the list
    urls_to_remove = set()
    for url in visited_urls:
        if "/common-" in url and url.endswith(".html"):
            filename = url.split("/")[-1]
            copter_url = f"http://ardupilot.org/copter/docs/{filename}"
            if copter_url in visited_urls and url != copter_url:
                urls_to_remove.add(url)
    visited_urls -= urls_to_remove

    return visited_urls


def find_all_links(soup: BeautifulSoup, current_url: str, visited_urls: set[str], urls_to_visit: set[str]) -> set[str]:
    for link in soup.find_all("a", href=True):
        if not isinstance(link, Tag):
            continue

        href = link.attrs.get("href")

        if not isinstance(href, str):
            continue

        full_url = urljoin(current_url, href)

        if not isinstance(full_url, str):
            continue

        # Remove anchor from URL
        parsed_url = urlparse(full_url)

        clean_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"

        # Skip image files
        if parsed_url.path.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".svg", ".bmp", "_images")):
            continue

        # Check if URL matches allowed domains
        if (
            any(domain in clean_url for domain in ALLOWED_DOMAINS)
            and clean_url not in visited_urls
            and clean_url not in urls_to_visit
            and all(domain not in clean_url for domain in URL_BLACKLIST_PREFIXES)
        ):
            urls_to_visit.add(clean_url)

    return urls_to_visit


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    start_time = time.time()

    visited_urls = set()
    broken_urls = set()
    urls_to_visit = {URL}
    proxies = get_env_proxies()

    # Set up authentication if credentials provided
    auth = (USERNAME, PASSWORD) if USERNAME and PASSWORD else None

    session = requests.Session()
    if auth:
        session.auth = auth
    if proxies:
        session.proxies = proxies

    while urls_to_visit:
        current_url = urls_to_visit.pop()

        if current_url in visited_urls or current_url in broken_urls:
            continue

        try:
            logging.info("Crawling: %s", current_url)
            response = session.get(current_url, timeout=30)
            response.raise_for_status()

            visited_urls.add(current_url)

            # Parse HTML
            soup = BeautifulSoup(response.text, "html.parser")

            urls_to_visit = find_all_links(soup, current_url, visited_urls, urls_to_visit)

        except (requests.RequestException, requests.Timeout) as e:
            logging.error("Network error crawling %s: %s", current_url, str(e))
            broken_urls.add(current_url)
            visited_urls.discard(current_url)
        except (KeyError, ValueError) as e:
            logging.error("URL processing error for %s: %s", current_url, str(e))
            broken_urls.add(current_url)
            visited_urls.discard(current_url)
    output_urls(visited_urls, broken_urls, start_time)


def output_urls(visited_urls: set[str], broken_urls: set[str], start_time: float) -> None:
    # Write all html URLs to file
    raw_pages = len(visited_urls)
    with open("gurubase.io_url_list_raw.txt", "w", encoding="utf-8") as f:
        f.writelines(f"{url}\n" for url in sorted(visited_urls))  # Output to file

    visited_urls -= set(URL_BLACKLIST)
    dedup_urls = remove_duplicates(visited_urls)

    # Write de-duplicated URLs to file and terminal
    with open("gurubase.io_url_list.txt", "w", encoding="utf-8") as f:
        for url in sorted(dedup_urls):
            print(url)  # Output to terminal # noqa: T201
            f.write(f"{url}\n")  # Output to file

    # Write broken URLs to file
    with open("gurubase.io_broken_urls_list.txt", "w", encoding="utf-8") as f:
        for url in sorted(broken_urls):
            f.write(f"{url}\n")

    duration_mins = (time.time() - start_time) / 60
    pages_per_min = raw_pages / duration_mins

    logging.info("\nCrawling Statistics:")
    msg = f"{raw_pages} pages crawled in {duration_mins:.2f} minutes ({pages_per_min:.2f} pages/min)"
    logging.info(msg)
    msg = f"De-duplicated pages: {len(dedup_urls)}"
    logging.info(msg)
    msg = f"Broken URLs found: {len(broken_urls)}"
    logging.info(msg)


if __name__ == "__main__":
    main()  # Call the main function
