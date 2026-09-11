# -*- coding: utf-8 -*-
"""Where is my work right now - every active PR, in one call.

    python ado_status.py                      my active PRs in the default project/repo
    python ado_status.py --all                everyone's active PRs
    python ado_status.py --repo X --project Y another repository
    python ado_status.py --json               machine-readable

Answers the question a session opens with - which PRs are mine, how many review threads are
still unanswered, did the validation build pass, which work item is attached - and answers it
in one place instead of six round trips that each have to be remembered.

Unresolved thread counts are the number that matters: an "active" thread is one nobody has
replied to or closed, which is exactly the list that blocks a merge.

Organisation, project and repository come from ADO_ORG_URL / ADO_PROJECT / ADO_REPO or the
defaults below; the PAT from AZURE_DEVOPS_PAT or the iBuildNet settings file. Read-only -
this script never writes.
"""
import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

ORG = os.environ.get("ADO_ORG_URL", "https://ranplan.visualstudio.com")
PROJECT = os.environ.get("ADO_PROJECT", "iBuildNet")
REPO = os.environ.get("ADO_REPO", "iBuildNet")
SETTINGS = os.environ.get(
    "ADO_SETTINGS_FILE",
    os.path.expanduser(r"~\source\repos\iBuildNet\iBuilding\.claude\settings.local.json"))

API = "api-version=7.1-preview.1"


def pat():
    token = os.environ.get("AZURE_DEVOPS_PAT")
    if not token and os.path.exists(SETTINGS):
        settings = json.load(open(SETTINGS, encoding="utf-8"))
        token = (settings.get("AZURE_DEVOPS_PAT")
                 or settings.get("env", {}).get("AZURE_DEVOPS_PAT"))
    if not token:
        sys.exit("no PAT: set AZURE_DEVOPS_PAT or put it in " + SETTINGS)
    return token


def get(url):
    auth = base64.b64encode((":" + pat()).encode()).decode()
    request = urllib.request.Request(url, headers={"Authorization": "Basic " + auth})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:300]
        sys.exit("HTTP {} on {}\n{}".format(exc.code, url, body))


def me():
    """Who the PAT belongs to, as (id, email).

    Best effort: the endpoint is preview and not enabled everywhere, so a failure here
    degrades to 'show everyone' rather than stopping the report. `displayName` and
    `uniqueName` come back empty against this organisation, but the descriptor carries the
    sign-in address after a backslash, which is what PR authorship is recorded under.
    """
    try:
        user = get(ORG + "/_apis/connectionData?api-version=7.1-preview").get("authenticatedUser", {})
    except SystemExit:
        return None, None
    descriptor = user.get("descriptor") or ""
    email = descriptor.rsplit("\\", 1)[-1] if "\\" in descriptor else (user.get("uniqueName") or "")
    return user.get("id"), email.lower()


def is_mine(pr, identity):
    """Match on either identity field. Filtering server-side with searchCriteria.creatorId
    looked tidier, but when the id shape does not match it returns an empty list rather than
    an error - a status report that quietly says 'you have no work' is worse than none."""
    ident, email = identity
    author = pr.get("createdBy", {})
    if ident and author.get("id") == ident:
        return True
    unique = (author.get("uniqueName") or "").lower()
    return bool(email) and unique == email


def base(project, repo):
    return "{}/{}/_apis/git/repositories/{}".format(ORG, urllib.parse.quote(project), repo)


def pull_requests(project, repo):
    url = base(project, repo) + "/pullrequests?searchCriteria.status=active&$top=100&" + API
    return get(url).get("value", [])


def threads(project, repo, pr_id):
    url = "{}/pullRequests/{}/threads?{}".format(base(project, repo), pr_id, API)
    return get(url).get("value", [])


def work_items(project, repo, pr_id):
    url = "{}/pullRequests/{}/workitems?{}".format(base(project, repo), pr_id, API)
    try:
        return [w.get("id") for w in get(url).get("value", [])]
    except SystemExit:
        return []


def latest_build(project, pr_id):
    """The validation build runs against refs/pull/<id>/merge; filtering by that branch is
    far more reliable than the policy-evaluation endpoint, which needs a double-encoded
    artifact id and answers 400 as readily as 404."""
    url = ("{}/{}/_apis/build/builds?branchName=refs/pull/{}/merge"
           "&$top=1&queryOrder=queueTimeDescending&api-version=7.1-preview.7").format(
        ORG, urllib.parse.quote(project), pr_id)
    try:
        builds = get(url).get("value", [])
    except SystemExit:
        return None
    if not builds:
        return None
    b = builds[0]
    return {"number": b.get("buildNumber"),
            "status": b.get("status"),
            "result": b.get("result")}


def summarise(project, repo, pr, want_build):
    pr_id = pr.get("pullRequestId")
    all_threads = threads(project, repo, pr_id)

    active = 0
    for t in all_threads:
        if t.get("isDeleted"):
            continue
        # A thread with no status at all is a plain comment, not a review finding.
        status = t.get("status")
        if status in ("active", "pending"):
            active += 1

    row = {
        "id": pr_id,
        "title": pr.get("title", "").strip(),
        "author": pr.get("createdBy", {}).get("displayName", ""),
        "source": (pr.get("sourceRefName") or "").replace("refs/heads/", ""),
        "target": (pr.get("targetRefName") or "").replace("refs/heads/", ""),
        "draft": bool(pr.get("isDraft")),
        "merge": pr.get("mergeStatus"),
        "threads_total": len([t for t in all_threads if not t.get("isDeleted")]),
        "threads_open": active,
        "work_items": work_items(project, repo, pr_id),
        "url": "{}/{}/_git/{}/pullrequest/{}".format(ORG, urllib.parse.quote(project), repo, pr_id),
    }
    if want_build:
        row["build"] = latest_build(project, pr_id)
    return row


def render(rows):
    if not rows:
        print("No active pull requests.")
        return
    for r in rows:
        flags = []
        if r["draft"]:
            flags.append("DRAFT")
        if r["merge"] and r["merge"] != "succeeded":
            flags.append("merge:" + r["merge"])
        head = "PR {}  {}".format(r["id"], r["title"])
        if flags:
            head += "   [" + " ".join(flags) + "]"
        print(head)
        print("   {} -> {}   by {}".format(r["source"], r["target"], r["author"]))

        threads_line = "   threads: {} open of {}".format(r["threads_open"], r["threads_total"])
        if r["threads_open"]:
            threads_line += "   <- these block the merge"
        print(threads_line)

        if "build" in r:
            b = r["build"]
            if not b:
                print("   build:   none found for refs/pull/{}/merge".format(r["id"]))
            else:
                print("   build:   {} {} {}".format(b["number"], b["status"], b["result"] or ""))

        if r["work_items"]:
            print("   items:   " + ", ".join(str(w) for w in r["work_items"]))
        else:
            print("   items:   none attached   <- a PR with no work item")

        print("   " + r["url"])
        print()


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", default=PROJECT)
    parser.add_argument("--repo", default=REPO)
    parser.add_argument("--all", action="store_true", help="not just mine")
    parser.add_argument("--no-build", action="store_true", help="skip the build lookup (faster)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    prs = pull_requests(args.project, args.repo)
    total = len(prs)
    if not args.all:
        identity = me()
        if identity == (None, None):
            print("Could not identify the PAT's owner; showing everyone's PRs.\n")
        else:
            prs = [pr for pr in prs if is_mine(pr, identity)]

    rows = [summarise(args.project, args.repo, pr, not args.no_build) for pr in prs]
    rows.sort(key=lambda r: (-r["threads_open"], r["id"]))

    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
    else:
        scope = "all" if args.all else "mine"
        print("{}/{}  active PRs ({} of {} open in the repo)\n".format(
            args.project, args.repo, scope, total))
        render(rows)


if __name__ == "__main__":
    main()
