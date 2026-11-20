#!/usr/bin/env -S uv run --script

# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "beautifulsoup4",
#     "httpx2",
# ]
# ///

"""
Outputs URLs of ArduPilot documentation pages.

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import logging
import time
from urllib.parse import urljoin, urlparse

import httpx2
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


def _drop_https_when_http_exists(urls: set[str]) -> set[str]:
    """Drop https:// URLs whose http:// twin is present, to keep the shorter/older form."""
    return {url for url in urls if not (url.startswith("https://") and f"http://{url[8:]}" in urls)}


def _drop_index_html_duplicates(urls: set[str]) -> set[str]:
    """Drop .../index.html URLs when the directory URL (with or without trailing /) is present."""
    return {url for url in urls if not (url.endswith("/index.html") and (url[:-11] in urls or url[:-10] in urls))}


def _drop_trailing_slash_duplicates(urls: set[str]) -> set[str]:
    """Drop URLs ending in / when the slash-less variant is already present."""
    return {url for url in urls if not (url.endswith("/") and url[:-1] in urls)}


def _drop_common_vs_copter_duplicates(urls: set[str]) -> set[str]:
    """Drop /common-*.html URLs when the same file is reachable under /copter/docs/."""
    kept: set[str] = set()
    for url in urls:
        if "/common-" in url and url.endswith(".html"):
            filename = url.split("/")[-1]
            copter_url = f"http://ardupilot.org/copter/docs/{filename}"
            if copter_url in urls and url != copter_url:
                continue
        kept.add(url)
    return kept


def remove_duplicates(visited_urls: set[str]) -> set[str]:
    """Return a copy of the URL set with four classes of duplicates removed (see helpers above)."""
    url_set = set(visited_urls)
    url_set = _drop_https_when_http_exists(url_set)
    url_set = _drop_index_html_duplicates(url_set)
    url_set = _drop_trailing_slash_duplicates(url_set)
    return _drop_common_vs_copter_duplicates(url_set)


_IMAGE_PATH_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".bmp", "_images")


def _clean_url(full_url: str) -> str:
    """Strip the query string and fragment from a URL."""
    parsed = urlparse(full_url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def _is_link_of_interest(clean_url: str, visited_urls: set[str], urls_to_visit: set[str]) -> bool:
    if urlparse(clean_url).path.lower().endswith(_IMAGE_PATH_SUFFIXES):
        return False
    if clean_url in visited_urls or clean_url in urls_to_visit:
        return False
    if any(prefix in clean_url for prefix in URL_BLACKLIST_PREFIXES):
        return False
    return any(domain in clean_url for domain in ALLOWED_DOMAINS)


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
        clean_url = _clean_url(full_url)
        if _is_link_of_interest(clean_url, visited_urls, urls_to_visit):
            urls_to_visit.add(clean_url)
    return urls_to_visit


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    start_time = time.time()

    visited_urls = set()
    broken_urls = set()
    urls_to_visit = {URL}

    # Set up authentication if credentials provided
    # These placeholders are intentionally editable constants rather than runtime configuration.
    auth = (USERNAME, PASSWORD) if USERNAME and PASSWORD else None  # ty: ignore[redundant-condition]

    with httpx2.Client(auth=auth, follow_redirects=True) as client:
        while urls_to_visit:
            current_url = urls_to_visit.pop()

            if current_url in visited_urls or current_url in broken_urls:
                continue

            try:
                logging.info("Crawling: %s", current_url)
                response = client.get(current_url, timeout=30)
                response.raise_for_status()

                visited_urls.add(current_url)

                # Parse HTML
                soup = BeautifulSoup(response.text, "html.parser")

                urls_to_visit = find_all_links(soup, current_url, visited_urls, urls_to_visit)

            except (httpx2.HTTPError, httpx2.InvalidURL):
                logging.exception("Network error crawling %s:", current_url)
                broken_urls.add(current_url)
                visited_urls.discard(current_url)
            except (KeyError, ValueError):
                logging.exception("URL processing error for %s:", current_url)
                broken_urls.add(current_url)
                visited_urls.discard(current_url)
    output_urls(visited_urls, broken_urls, start_time)


def output_urls(visited_urls: set[str], broken_urls: set[str], start_time: float) -> None:
    # Write all html URLs to file
    raw_pages = len(visited_urls)
    with open("gurubase.io_url_list_raw.txt", "w", encoding="utf-8", newline="\n") as f:
        f.writelines(f"{url}\n" for url in sorted(visited_urls))  # Output to file

    visited_urls -= set(URL_BLACKLIST)
    dedup_urls = remove_duplicates(visited_urls)

    # Write de-duplicated URLs to file and terminal
    with open("gurubase.io_url_list.txt", "w", encoding="utf-8", newline="\n") as f:
        for url in sorted(dedup_urls):
            print(url)  # Output to terminal # noqa: T201
            f.write(f"{url}\n")  # Output to file

    # Write broken URLs to file
    with open("gurubase.io_broken_urls_list.txt", "w", encoding="utf-8", newline="\n") as f:
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
