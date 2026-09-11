# -*- coding: utf-8 -*-
"""Azure DevOps work-item helper.

    python ado_wi.py show     <id>                           fields, parent, links
    python ado_wi.py children <id>                           child items with type/state/title
    python ado_wi.py find     "<text>"                       title search (open items first)
    python ado_wi.py create   --title T --parent P [...]      new Task under a parent
    python ado_wi.py link-pr  <id> <prId> [--repo R]          attach a pull request
    python ado_wi.py state    <id> "<state>" [--time-taken N] walk the state machine

Organisation, project and repository come from ADO_ORG_URL / ADO_PROJECT / ADO_REPO or the
defaults below. The PAT is read from the iBuildNet settings file (key AZURE_DEVOPS_PAT) or
from the AZURE_DEVOPS_PAT environment variable. Nothing is written with --dry.

Two things this encodes that the REST API will not tell you until it rejects you:
a Task cannot be created directly in a late state (the process walks To Do -> In Progress
-> In Pull Request -> Done), and Done requires Time Taken, which is measured in HOURS.
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

# The forward path through the Task process. Creating straight into a later state is
# rejected with "not in the list of supported values", so transitions are walked.
TASK_FLOW = ["To Do", "In Progress", "In Pull Request", "Done"]


def pat():
    token = os.environ.get("AZURE_DEVOPS_PAT")
    if not token and os.path.exists(SETTINGS):
        settings = json.load(open(SETTINGS, encoding="utf-8"))
        token = (settings.get("AZURE_DEVOPS_PAT")
                 or settings.get("env", {}).get("AZURE_DEVOPS_PAT"))
    if not token:
        sys.exit("no PAT: set AZURE_DEVOPS_PAT or put it in " + SETTINGS)
    return token


def call(method, url, body=None, ctype="application/json"):
    auth = base64.b64encode((":" + pat()).encode()).decode()
    headers = {"Authorization": "Basic " + auth, "Content-Type": ctype}
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as response:
            return json.load(response)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        try:
            detail = json.loads(detail).get("message", detail)
        except ValueError:
            pass
        sys.exit(f"HTTP {e.code}: {detail[:800]}")


def wit(path, query=""):
    return f"{ORG}/{PROJECT}/_apis/wit/{path}?api-version=7.1" + (("&" + query) if query else "")


def patch(work_item_id, ops, dry=False):
    if dry:
        print(json.dumps(ops, indent=2, ensure_ascii=False))
        return None
    return call("PATCH", wit(f"workitems/{work_item_id}"), ops, "application/json-patch+json")


def get(work_item_id, expand="relations"):
    return call("GET", wit(f"workitems/{work_item_id}", f"$expand={expand}"))


def name_of(value):
    return value.get("displayName") if isinstance(value, dict) else value


def show(args):
    w = get(args.id)
    f = w["fields"]
    print(f"{w['id']} [{f['System.WorkItemType']}] {f['System.State']}")
    print(f"  {f['System.Title']}")
    print(f"  assigned : {name_of(f.get('System.AssignedTo')) or '-'}")
    print(f"  area     : {f.get('System.AreaPath')}")
    print(f"  iteration: {f.get('System.IterationPath')}")
    print(f"  origin   : {f.get('Custom.TaskOrigin')}   billable: {f.get('Custom.Billable')}"
          f"   time taken (h): {f.get('Custom.TimeTaken')}")
    parent = f.get("System.Parent")
    if parent:
        print(f"  parent   : {parent}")
    for r in w.get("relations", []):
        if r["rel"] == "ArtifactLink":
            print(f"  link     : {r.get('attributes', {}).get('name')} {r['url']}")


def children(args):
    w = get(args.id)
    ids = [r["url"].rsplit("/", 1)[-1] for r in w.get("relations", [])
           if r["rel"] == "System.LinkTypes.Hierarchy-Forward"]
    if not ids:
        print("no children")
        return
    fields = "System.WorkItemType,System.Title,System.State,System.AssignedTo"
    for i in range(0, len(ids), 100):
        batch = ",".join(ids[i:i + 100])
        res = call("GET", wit("workitems", f"ids={batch}&fields={fields}"))
        for c in sorted(res["value"], key=lambda x: x["id"]):
            g = c["fields"]
            who = name_of(g.get("System.AssignedTo")) or "-"
            print(f"  {c['id']} [{g['System.WorkItemType']}] {g['System.State']:<15} "
                  f"{g['System.Title'][:70]}  ({who})")


def find(args):
    text = args.text.replace("'", "''")
    wiql = ("SELECT [System.Id] FROM WorkItems "
            f"WHERE [System.TeamProject] = '{PROJECT}' "
            f"AND [System.Title] CONTAINS '{text}' "
            "ORDER BY [System.ChangedDate] DESC")
    res = call("POST", wit("wiql", "$top=50"), {"query": wiql})
    ids = [str(w["id"]) for w in res.get("workItems", [])]
    if not ids:
        print("nothing matched")
        return
    fields = "System.WorkItemType,System.Title,System.State"
    res = call("GET", wit("workitems", f"ids={','.join(ids[:100])}&fields={fields}"))
    order = {wid: n for n, wid in enumerate(ids)}
    for c in sorted(res["value"], key=lambda x: order.get(str(x["id"]), 0)):
        g = c["fields"]
        print(f"  {c['id']} [{g['System.WorkItemType']}] {g['System.State']:<15} "
              f"{g['System.Title'][:70]}")


def me():
    """The PAT owner, used when no assignee is given. Best effort: connectionData is a
    preview endpoint, and an unassigned task is a far smaller problem than a failed
    create, so a miss here returns None rather than stopping."""
    auth = base64.b64encode((":" + pat()).encode()).decode()
    req = urllib.request.Request(f"{ORG}/_apis/connectionData?api-version=7.1-preview",
                                 headers={"Authorization": "Basic " + auth})
    try:
        with urllib.request.urlopen(req) as response:
            ident = json.load(response).get("authenticatedUser", {})
    except (urllib.error.HTTPError, urllib.error.URLError):
        return None
    return ident.get("properties", {}).get("Account", {}).get("$value") or ident.get("id")


def create(args):
    parent = get(args.parent) if args.parent else None
    pf = parent["fields"] if parent else {}
    ops = [
        {"op": "add", "path": "/fields/System.Title", "value": args.title},
        {"op": "add", "path": "/fields/Custom.TaskOrigin", "value": args.origin},
        {"op": "add", "path": "/fields/Custom.Billable", "value": args.billable},
    ]
    area = args.area or pf.get("System.AreaPath")
    iteration = args.iteration or pf.get("System.IterationPath")
    if area:
        ops.append({"op": "add", "path": "/fields/System.AreaPath", "value": area})
    if iteration:
        ops.append({"op": "add", "path": "/fields/System.IterationPath", "value": iteration})
    assignee = args.assign or me()
    if assignee:
        ops.append({"op": "add", "path": "/fields/System.AssignedTo", "value": assignee})
    if args.description:
        body = open(args.description, encoding="utf-8").read() if os.path.exists(args.description) \
            else args.description
        ops.append({"op": "add", "path": "/fields/System.Description", "value": body})
    if args.priority:
        ops.append({"op": "add", "path": "/fields/Microsoft.VSTS.Common.Priority",
                    "value": args.priority})
    if parent:
        ops.append({"op": "add", "path": "/relations/-", "value": {
            "rel": "System.LinkTypes.Hierarchy-Reverse",
            "url": parent["url"]}})

    if args.dry:
        print(json.dumps(ops, indent=2, ensure_ascii=False))
        return
    w = call("POST", wit(f"workitems/${args.type}"), ops, "application/json-patch+json")
    print(f"created {w['id']} [{args.type}] {w['fields']['System.State']}")
    print(f"  {ORG}/{PROJECT}/_workitems/edit/{w['id']}")
    if args.pr:
        link_pr_by_id(w["id"], args.pr, args.repo, False)
    if args.state and args.state != w["fields"]["System.State"]:
        walk_state(w["id"], args.state, args.time_taken, False)


def pr_artifact_url(pr_id, repo):
    pr = call("GET", f"{ORG}/{PROJECT}/_apis/git/repositories/{repo}/pullRequests/{pr_id}"
                     "?api-version=7.1")
    # The PR's own artifactId already carries the project and repository GUIDs in the
    # encoding the link expects; deriving it by hand is how the link ends up pointing at
    # the wrong project.
    return pr["artifactId"], pr["title"]


def link_pr_by_id(work_item_id, pr_id, repo, dry):
    url, title = pr_artifact_url(pr_id, repo)
    ops = [{"op": "add", "path": "/relations/-", "value": {
        "rel": "ArtifactLink", "url": url, "attributes": {"name": "Pull Request"}}}]
    if patch(work_item_id, ops, dry) is not None:
        print(f"linked PR {pr_id} ({title[:60]}) to {work_item_id}")


def link_pr(args):
    link_pr_by_id(args.id, args.pr, args.repo, args.dry)


def walk_state(work_item_id, target, time_taken, dry):
    current = get(work_item_id, expand="none")["fields"]["System.State"]
    if current == target:
        print(f"{work_item_id} already {target}")
        return
    if current in TASK_FLOW and target in TASK_FLOW:
        i, j = TASK_FLOW.index(current), TASK_FLOW.index(target)
        path = TASK_FLOW[i + 1:j + 1] if j > i else [target]
    else:
        path = [target]
    for step in path:
        ops = [{"op": "add", "path": "/fields/System.State", "value": step}]
        # Time Taken is required to close and is counted in HOURS, so it rides the same
        # patch as the closing transition rather than being set afterwards.
        if step == "Done" and time_taken is not None:
            ops.append({"op": "add", "path": "/fields/Custom.TimeTaken", "value": time_taken})
        w = patch(work_item_id, ops, dry)
        if w is None:
            continue
        print(f"{work_item_id} -> {w['fields']['System.State']}")


def state(args):
    walk_state(args.id, args.state, args.time_taken, args.dry)


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("show"); s.add_argument("id"); s.set_defaults(fn=show)
    s = sub.add_parser("children"); s.add_argument("id"); s.set_defaults(fn=children)
    s = sub.add_parser("find"); s.add_argument("text"); s.set_defaults(fn=find)

    s = sub.add_parser("create")
    s.add_argument("--title", required=True)
    s.add_argument("--parent")
    s.add_argument("--type", default="Task")
    s.add_argument("--origin", default="0 - Planned",
                   help="Task Origin picklist, e.g. '0 - Planned', '1 - Additional Work Found'")
    s.add_argument("--billable", default=False, action="store_true")
    s.add_argument("--area"); s.add_argument("--iteration"); s.add_argument("--assign")
    s.add_argument("--description", help="HTML, or a path to a file containing it")
    s.add_argument("--priority", type=int)
    s.add_argument("--state", help="walk to this state after creating")
    s.add_argument("--time-taken", type=float, dest="time_taken")
    s.add_argument("--pr", help="link this pull request id after creating")
    s.add_argument("--repo", default=REPO)
    s.add_argument("--dry", action="store_true")
    s.set_defaults(fn=create)

    s = sub.add_parser("link-pr")
    s.add_argument("id"); s.add_argument("pr")
    s.add_argument("--repo", default=REPO); s.add_argument("--dry", action="store_true")
    s.set_defaults(fn=link_pr)

    s = sub.add_parser("state")
    s.add_argument("id"); s.add_argument("state")
    s.add_argument("--time-taken", type=float, dest="time_taken")
    s.add_argument("--dry", action="store_true")
    s.set_defaults(fn=state)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
