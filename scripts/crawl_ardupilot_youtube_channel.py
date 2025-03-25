#!/usr/bin/python3

"""
Outputs URLs of ArduPilot YouTube videos from the ArduPilot YouTube channel.

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import logging
import time
from os import environ as os_environ
from typing import Union

from requests.auth import HTTPProxyAuth
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait

# Define the URL of the YouTube channel
URL = "https://www.youtube.com/@ardupilot19/videos"
USERNAME = "your_username"  # Replace with actual username if needed
PASSWORD = ""  # Replace with actual password if needed


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
    proxies = proxies_dict if proxies_dict else None
    if proxies:
        logging.info("Proxies: %s", proxies)
    else:
        logging.debug("Proxies: %s", proxies)
    return proxies


# pylint: enable=duplicate-code


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    proxies = get_env_proxies()
    if proxies:
        HTTPProxyAuth(USERNAME, PASSWORD)

    # Setup Firefox in headless mode
    options = Options()
    options.add_argument("--headless")
    driver = webdriver.Firefox(options=options)

    try:
        logging.info("Loading page: %s", URL)
        driver.get(URL)

        # Handle cookie consent dialog
        try:
            logging.info("Looking for cookie consent button")
            wait = WebDriverWait(driver, 10)
            cookie_button = wait.until(ec.element_to_be_clickable((By.CSS_SELECTOR, "button[aria-label='Accept all']")))
            cookie_button.click()
            logging.info("Clicked cookie consent button")
        except Exception as e:  # pylint: disable=broad-exception-caught
            logging.warning("Cookie consent handling failed: %s", e)

        # Wait for content to load initially
        time.sleep(5)  # Increased initial wait

        # Scroll more times to ensure content loads
        for i in range(5):  # Increased scroll iterations
            logging.info("Scrolling iteration %d", i + 1)
            driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")
            time.sleep(3)  # Increased scroll wait

        # Try different selectors for video links
        selectors = [
            "a#video-title",  # Try this selector first
            "a[href*='/watch?v=']",  # More generic selector
            "h3.ytd-grid-video-renderer a",  # Another possible selector
        ]

        video_links = []
        for selector in selectors:
            logging.info("Trying selector: %s", selector)
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            logging.info("Found %d elements with selector %s", len(elements), selector)

            for element in elements:
                href = element.get_attribute("href")
                if href and "watch?v=" in href and href not in video_links:
                    video_links.append(href)
                    logging.info("Found video: %s", href)
                if len(video_links) >= 80:  # gurubase has a limit of 100 videos
                    break

            if len(video_links) >= 80:  # gurubase has a limit of 100 videos
                break

        logging.info("Total unique videos found: %d", len(video_links))

        # Print the video URLs
        for video in video_links:
            print(video)  # noqa: T201

    except Exception as e:  # pylint: disable=broad-exception-caught
        logging.exception("An error occurred: %s", str(e))

    finally:
        driver.quit()


if __name__ == "__main__":
    main()  # Call the main function
