#!/usr/bin/env python3

'''
Based on https://pagure.io/github-release-stats/blob/master/f/get_release_stats.py by Clement Verna

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

(C) 2024 Amilcar do Carmo Lucas

SPDX-License-Identifier:    GPL-3
'''

import itertools
import re

from operator import itemgetter

from github import Github


def compute_average(issues_date):
    sum_of_issues = sum(days for _issue, days in issues_date)

    if len(issues_date):
        return sum_of_issues / len(issues_date)
    return sum_of_issues

def main():
    api_token = None
    gh = Github(api_token)

    repo = gh.get_repo("ArduPilot/MethodicConfigurator")

    last_5_releases = itertools.islice(repo.get_releases(), 5)
    overall_issues = []
    unique_issues = set()
    for release in last_5_releases:
        release = repo.get_release(release.id)
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

        print(f"{release.title} ({release_date})")
        print("---------------------------------")
        if issues_date:
            print(f"Number of issues : {len(issues_date)}")
            print(f"Days to release issue (Average) : {compute_average(issues_date)}")
            print(f"Days to release issue (Maximun) : {max(issues_date,key=itemgetter(1))[1]}")
            print(f"Days to release issue (Minimun) : {min(issues_date,key=itemgetter(1))[1]}")

        total_downloads = sum(asset.download_count for asset in release.get_assets())
        print(f"Total downloads : {total_downloads}")

        print("---------------------------------\n")
        # print(issues_date)
    if overall_issues:
        print(f"Average of days to release an issue over 5 releases : {sum(overall_issues)/len(overall_issues)}")


if __name__ == "__main__":

    main()
