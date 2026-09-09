# -*- coding: utf-8 -*-
"""Azure DevOps pull-request helper for reviews.

    python ado_pr.py fetch <prId>                     print title, branches, description, every thread
    python ado_pr.py post  <prId> threads.json [--dry] open inline threads (and a summary thread)
    python ado_pr.py reply <prId> replies.json [--dry] reply into existing threads, optionally set status

threads.json:  [{"file": "/iBuilding/path/File.cs", "line": 44, "content": "..."},
                {"file": null, "content": "## Review summary ..."}]
replies.json:  [{"thread": 511409, "content": "...", "status": "fixed"}]   status optional:
               active | fixed | wontFix | closed | pending

Organisation, project and repository come from ADO_ORG_URL / ADO_PROJECT / ADO_REPO or the
defaults below. The PAT is read from the iBuildNet settings file (key AZURE_DEVOPS_PAT) or
from the AZURE_DEVOPS_PAT environment variable. Nothing is posted with --dry.
"""
import base64
import json
import os
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

ORG = os.environ.get("ADO_ORG_URL", "https://ranplan.visualstudio.com")
PROJECT = os.environ.get("ADO_PROJECT", "iBuildNet")
REPO = os.environ.get("ADO_REPO", "iBuildNet")
SETTINGS = os.environ.get(
    "ADO_SETTINGS_FILE",
    os.path.expanduser(r"~\source\repos\iBuildNet\iBuilding\.claude\settings.local.json"))
STATUS_CODES = {"active": 1, "fixed": 2, "wontFix": 3, "closed": 4, "pending": 6}


def pat():
    token = os.environ.get("AZURE_DEVOPS_PAT")
    if not token and os.path.exists(SETTINGS):
        settings = json.load(open(SETTINGS, encoding="utf-8"))
        token = settings.get("AZURE_DEVOPS_PAT") or settings.get("env", {}).get("AZURE_DEVOPS_PAT")
    if not token:
        sys.exit("no PAT: set AZURE_DEVOPS_PAT or put it in " + SETTINGS)
    return token


def call(method, url, body=None):
    auth = base64.b64encode((":" + pat()).encode()).decode()
    headers = {"Authorization": "Basic " + auth, "Content-Type": "application/json"}
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req) as response:
        return json.load(response)


def base(pr_id):
    return f"{ORG}/{PROJECT}/_apis/git/repositories/{REPO}/pullRequests/{pr_id}"


def fetch(pr_id):
    pr = call("GET", base(pr_id) + "?api-version=7.1")
    print("TITLE:", pr["title"])
    print("SRC:", pr["sourceRefName"], "->", pr["targetRefName"], "STATUS:", pr["status"])
    print("HEAD:", pr["lastMergeSourceCommit"]["commitId"])
    print("DESCRIPTION:\n" + (pr.get("description") or ""))
    print("=" * 70)
    for thread in call("GET", base(pr_id) + "/threads?api-version=7.1")["value"]:
        if thread.get("isDeleted"):
            continue
        comments = [c for c in thread.get("comments", [])
                    if not c.get("isDeleted") and c.get("commentType") != "system"]
        if not comments:
            continue
        context = thread.get("threadContext") or {}
        where = f"{context.get('filePath')}:{(context.get('rightFileStart') or {}).get('line')}"
        print(f"THREAD {thread['id']} status={thread.get('status')} {where}")
        for comment in comments:
            print(f"  -- [{comment['id']}] {comment['author']['displayName']} {comment['publishedDate'][:16]}:")
            print("     " + (comment.get("content") or "").replace("\n", "\n     "))
        print("-" * 70)


def post(pr_id, path, dry):
    for item in json.load(open(path, encoding="utf-8")):
        body = {"comments": [{"parentCommentId": 0, "content": item["content"], "commentType": 1}],
                "status": 1}
        if item.get("file"):
            body["threadContext"] = {
                "filePath": item["file"],
                "rightFileStart": {"line": item["line"], "offset": 1},
                "rightFileEnd": {"line": item["line"], "offset": 1},
            }
        label = f"{item.get('file')}:{item.get('line')} ({len(item['content'])} chars)"
        if dry:
            print("DRY", label)
            print("   " + item["content"][:300].replace("\n", "\n   "))
            continue
        result = call("POST", base(pr_id) + "/threads?api-version=7.1", body)
        print("POSTED thread", result["id"], label)


def reply(pr_id, path, dry):
    for item in json.load(open(path, encoding="utf-8")):
        thread_id = item["thread"]
        if dry:
            print("DRY reply to", thread_id, "->", item.get("status"), f"({len(item['content'])} chars)")
            continue
        call("POST", base(pr_id) + f"/threads/{thread_id}/comments?api-version=7.1",
             {"content": item["content"], "parentCommentId": 1, "commentType": 1})
        if item.get("status"):
            call("PATCH", base(pr_id) + f"/threads/{thread_id}?api-version=7.1",
                 {"status": STATUS_CODES[item["status"]]})
        print("REPLIED", thread_id, item.get("status") or "")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    command, pr = sys.argv[1], sys.argv[2]
    dry = "--dry" in sys.argv
    if command == "fetch":
        fetch(pr)
    elif command == "post":
        post(pr, sys.argv[3], dry)
    elif command == "reply":
        reply(pr, sys.argv[3], dry)
    else:
        sys.exit(__doc__)
