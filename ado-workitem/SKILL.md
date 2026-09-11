---
name: ado-workitem
description: >-
  Use for any Azure DevOps work-item housekeeping: "把这几个 task 改成 done", "PR 没挂
  task 帮我挂上", "创建一个 task", "这个 PBI 下面还有什么没做", setting Time Taken,
  closing the tasks whose PRs merged, or finding the item a piece of work belongs to.
  Reads and writes work items through the REST API with the required custom fields
  already handled - Task Origin, Billable, and Time Taken in HOURS - walks the state
  machine instead of setting an end state that the process rejects, and links pull
  requests with an artifact link derived from the PR itself. Use it whenever a work-item
  id or a board state comes up, even if the user just asks "这个 task 什么状态".
---

# Azure DevOps work items, with the fields the process actually requires

## When to use / when not to

- Use when: creating, finding, linking, or changing the state of work items; auditing a
  PBI's children; closing tasks after PRs merge.
- Do not use when: the task is about the pull request itself - reviewing it, replying to
  threads, updating its description. That is `pr-review` / `pr-self-review`.

## The three things the API will not warn you about

1. **A Task cannot be created in a late state.** Creating one directly as
   `In Pull Request` is rejected with *"contains the value ... that is not in the list of
   supported values"*. The process walks
   `To Do -> In Progress -> In Pull Request -> Done`, so a new item is created in
   `To Do` and then transitioned. `scripts/ado_wi.py` does this walk for you.
2. **`Custom.TimeTaken` is required to close an item, and it is in HOURS.** Closing
   without it fails with `TF401320`. Do not invent a number: ask, or use the team's
   convention if there is one. A PR-sized task here is typically 3.
3. **`Custom.TaskOrigin` and `Custom.Billable` are required on create.** Origin is a
   picklist the API will not enumerate; the values in use are
   `0 - Planned`, `1 - Additional Work Found`, `3 - Manual Round 1`
   (and `4` / `5` for later rounds), `7 - Automation`. Work that came out of a review of
   already-planned work is `1 - Additional Work Found`, not `0 - Planned`.

## Steps

### 1. Find out what you are touching before you touch it

Starting a session, or asked "where is my work" - one call, not six:

```
python scripts/ado_status.py                # my active PRs: open threads, build, work items
python scripts/ado_status.py --all          # everyone's, same repo
ADO_PROJECT=DistributedPlatform ADO_REPO=pleiades-ms-ai-orchestrator python scripts/ado_status.py
```

It counts **open** threads, which is the list that blocks a merge, and names any PR with no
work item attached. The header says "mine of N open in the repo", because a filter that
returns nothing and a repository that has nothing are different answers and the report has to
tell them apart.

Then the item side:

```
python scripts/ado_wi.py show 117263        # fields, parent, PR and commit links
python scripts/ado_wi.py children 115643    # every child with type, state, assignee
python scripts/ado_wi.py find "cookbook"    # title search, most recently changed first
```

`children` on the parent PBI is the fastest way to answer "what is left" and to see how
sibling items are worded, stated and classified - copy their shape rather than inventing
one.

### 2. Creating a task

```
python scripts/ado_wi.py create --title "..." --parent 115643 \
    --origin "1 - Additional Work Found" --description desc.html \
    --state "In Pull Request" --pr 58603 --dry
```

Area path, iteration and assignee are inherited from the parent when not given, which is
almost always what you want - a task in a different iteration to its PBI quietly leaves
the sprint. Run with `--dry` first and read the patch; drop the flag to apply.

The description follows the siblings' shape: **What**, **Why**, **How to test**, as small
HTML blocks. Write it for the person who picks this up in six months, and say where the
work came from if it came from a review thread.

### 3. Linking a pull request

```
python scripts/ado_wi.py link-pr 117263 58603 --repo iBuildNet
```

The link is an `ArtifactLink` named `Pull Request`, and its URL must carry the project and
repository GUIDs. The script reads the PR's own `artifactId` rather than assembling one,
because a hand-built URL that names the wrong project links silently and points nowhere.

For a PR in another project, set the environment first:
`ADO_PROJECT=DistributedPlatform ADO_REPO=pleiades-ms-ai-orchestrator`.

**Do not attach an open PR to a `Done` task.** The board then shows finished work with
unmerged code behind it. If the natural parent task is already closed, create a new task
with origin `1 - Additional Work Found` and link the PR there.

### 4. Changing state

```
python scripts/ado_wi.py state 116922 "In Pull Request"
python scripts/ado_wi.py state 116922 "Done" --time-taken 3
```

Closing a batch after a merge: confirm each PR is actually **completed**, not merely
approved, before closing its task. A task closed on an approved-but-unmerged PR is the
board saying something that is not true.

## Traps

- **Do not guess Time Taken.** It feeds someone's reporting. Ask for the number, or apply
  the convention the user has already stated.
- **A parent link is not a state.** Creating the child under the PBI does not move the
  PBI; if this was the last open child, ask before closing the parent.
- **`System.Parent` is absent from the default field set** in some responses - read
  relations with `$expand=relations` before concluding an item is unparented.
- **The PAT is read from the iBuildNet settings file.** Never echo it, never paste it into
  a script argument, and never stage that settings file.
- **Removed is not Done.** When auditing children, treat `Removed` as "this was dropped",
  and mention it rather than silently counting it as finished.

## Supporting resources

- `scripts/ado_status.py` - every active PR with its open-thread count, validation build and
  attached work items. Read-only; `--all`, `--no-build` and `--json` available.
- `scripts/ado_wi.py` - `show` / `children` / `find` / `create` / `link-pr` / `state`.
  Organisation, project and repository come from `ADO_ORG_URL` / `ADO_PROJECT` /
  `ADO_REPO`; the PAT from `AZURE_DEVOPS_PAT` or the iBuildNet settings file. Every
  writing command takes `--dry`.
- `pr-review/scripts/ado_pr.py` - the pull-request side of the same API.
