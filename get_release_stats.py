#!/usr/bin/env python3

"""
Based on https://pagure.io/github-release-stats/blob/master/f/get_release_stats.py by Clement Verna.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import itertools
import re
from operator import itemgetter

from github import Github  # pylint: disable=import-error


def compute_average(issues_date: list[tuple[int, int]]) -> float:
    sum_of_issues = sum(days for _issue, days in issues_date)

    if len(issues_date):
        return sum_of_issues / len(issues_date)
    return sum_of_issues


def main() -> None:
    api_token = None
    gh = Github(api_token)

    repo = gh.get_repo("ArduPilot/MethodicConfigurator")

    last_5_releases = itertools.islice(repo.get_releases(), 5)
    overall_issues = []
    unique_issues = set()
    for repo_release in last_5_releases:
        release = repo.get_release(repo_release.id)
        # Date of the release
        release_date = release.created_at
        # Find all the issue references in the release notes
        release_issues = re.findall(r"#\d+", release.body)

        issues_date = []
        for issue in release_issues:
            # Remove the # char from the issue number and convert to int
            # then get the issue creation date
            date = repo.get_issue(int(issue[1:])).created_at
            number_days = release_date - date
            if issue not in unique_issues:
                issues_date.append((issue, number_days.days))
                unique_issues.add(issue)
                overall_issues.append(number_days.days)

        print(f"{release.title} ({release_date})")  # noqa: T201
        print("---------------------------------")  # noqa: T201
        if issues_date:
            print(f"Number of issues : {len(issues_date)}")  # noqa: T201
            print(f"Days to release issue (Average) : {compute_average(issues_date)}")  # noqa: T201
            print(f"Days to release issue (Maximun) : {max(issues_date, key=itemgetter(1))[1]}")  # noqa: T201
            print(f"Days to release issue (Minimun) : {min(issues_date, key=itemgetter(1))[1]}")  # noqa: T201

        total_downloads = sum(asset.download_count for asset in release.get_assets())
        print(f"Total downloads : {total_downloads}")  # noqa: T201

        print("---------------------------------\n")  # noqa: T201
        # print(issues_date)
    if overall_issues:
        print(  # noqa: T201
            f"Average of days to release an issue over 5 releases : {sum(overall_issues) / len(overall_issues)}"
        )


if __name__ == "__main__":
    main()
