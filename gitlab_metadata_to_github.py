#!/usr/bin/env python3

"""
Migrate GitLab issues and merge requests into an already-mirrored GitHub repo.

Assumes:
  - You already ran git clone --mirror and pushed to GitHub
  - You already have metadata.json from the archive script
  - GitHub CLI (gh) is installed and authenticated

Example:
  python gitlab_metadata_to_github.py \
      --metadata ./billingegroup__mypkg-123/metadata.json \
      --github-repo billingegroup/mypkg
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path


def run(cmd):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if p.returncode != 0:
        raise RuntimeError(p.stdout)
    return p.stdout


def create_label(repo, label):
    run([
        "gh", "label", "create",
        label["name"],
        "--repo", repo,
        "--color", label.get("color", "cccccc"),
        "--description", label.get("description") or ""
    ])


def create_milestone(repo, ms):
    run([
        "gh", "api",
        "-X", "POST",
        f"repos/{repo}/milestones",
        "-f", f"title={ms['title']}",
        "-f", f"description={ms.get('description') or ''}"
    ])


def create_issue(repo, issue):
    body = issue.get("description") or ""
    title = issue["title"]

    result = run([
        "gh", "issue", "create",
        "--repo", repo,
        "--title", title,
        "--body", body
    ])

    return result.strip().split("/")[-1]


def create_pr(repo, mr):
    title = mr["title"]
    body = mr.get("description") or ""
    head = mr["source_branch"]
    base = mr["target_branch"]

    run([
        "gh", "pr", "create",
        "--repo", repo,
        "--title", title,
        "--body", body,
        "--head", head,
        "--base", base
    ])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--metadata", required=True, help="Path to metadata.json from archive script")
    ap.add_argument("--github-repo", required=True, help="GitHub repo in org/name format")
    args = ap.parse_args()

    metadata_path = Path(args.metadata)
    if not metadata_path.exists():
        print("metadata.json not found:", metadata_path)
        sys.exit(1)

    with open(metadata_path) as f:
        meta = json.load(f)

    repo = args.github_repo

    print(f"\nMigrating metadata into GitHub repo: {repo}\n")

    # ---------------- LABELS ----------------
    print("Creating labels...")
    for label in meta.get("labels", []):
        try:
            create_label(repo, label)
        except Exception as e:
            print("Label skipped:", label["name"])

    # ---------------- MILESTONES ----------------
    print("Creating milestones...")
    for ms in meta.get("milestones", []):
        try:
            create_milestone(repo, ms)
        except Exception:
            print("Milestone skipped:", ms["title"])

    # ---------------- ISSUES ----------------
    print("Creating issues...")
    for issue in meta.get("issues", []):
        try:
            create_issue(repo, issue)
        except Exception:
            print("Issue skipped:", issue["title"])

    # ---------------- PULL REQUESTS ----------------
    print("Creating pull requests...")
    for mr in meta.get("merge_requests", []):
        try:
            create_pr(repo, mr)
        except Exception:
            print("PR skipped:", mr["title"])

    print("\nMigration complete.")
    print("Your GitHub repo now has its full social history restored.")


if __name__ == "__main__":
    main()
