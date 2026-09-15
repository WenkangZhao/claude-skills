---
name: ibuildnet-merge-develop
description: >-
  Use when an iBuildNet feature branch needs the latest develop: "把 develop 合并到这个分支",
  "解决一下冲突", "这个分支太旧了", "merge develop", before opening a PR that is hundreds of
  commits behind, or when a build fails on code the branch never touched. Runs the team's
  flow - cut a task branch off the feature branch, merge develop into the TASK branch,
  resolve there, then PR the task branch back into the feature branch - so the feature
  branch is never the place a conflict is fought, and the merge gets reviewed like any other
  change. Also covers how to tell a union conflict from a real one, which this repository's
  conflicts almost always are.
---

# Merge develop into an iBuildNet feature branch

## When to use / when not to

- Use when: a feature branch (`feature/PBI…`) is behind develop and needs catching up.
- Do not use when: merging a finished task branch back into its feature branch with no
  develop involved (that is an ordinary PR), or for a repository that is not iBuildNet -
  the flow is the same shape but the conflict patterns below are specific to this one.

## Why a task branch and not the feature branch directly

Merging develop straight into `feature/PBI115643` puts a few hundred commits and every
conflict resolution into the branch other people are basing work on, with no review step.
The team's flow keeps that off the feature branch:

```
develop ─────────────────────────┐
                                 ▼
feature/PBI115643 ──► TaskNNNNNN ──(merge develop, resolve here)──► PR back into feature
```

The task branch is disposable. If the merge goes wrong, delete it and start again; the
feature branch never moved.

## Steps

### 1. Cut the task branch from the feature branch

```
git fetch origin develop feature/PBI115643
git switch feature/PBI115643 && git pull --ff-only
git switch -c Task117314            # the work item id, no prefix - match `git branch -a`
```

The branch name convention here is the bare work-item id (`Task117314`), not
`task/117314`. Check `git for-each-ref refs/heads` if unsure.

### 2. Get the working tree out of the way first

A merge refuses to start if it would overwrite a file you have modified, and it will not
tell you in advance which. Find out before you begin:

```
git diff --name-only Task117314...origin/develop | grep -Ff <(git diff --name-only)
```

Anything that comes back is a collision. If the modifications are unrelated to the merge -
notes, local tooling, docs you were writing - stash them by **explicit path** so they stay
out of the merge commit, and restore them afterwards:

```
git stash push -m "unrelated work, not part of the develop merge" CLAUDE.md .gitignore
```

Untracked files do not block a merge unless develop adds a file at the same path. Check
that too when the tree is full of them:

```
git diff --name-only --diff-filter=A Task117314...origin/develop
```

### 3. Merge and read the conflict list before touching anything

```
git merge origin/develop --no-edit
git diff --name-only --diff-filter=U
for f in $(git diff --name-only --diff-filter=U); do echo "$(grep -c '^<<<<<<<' "$f")  $f"; done
```

The hunk count per file tells you where the real work is. A file with one hunk is almost
always a list both sides appended to.

### 4. Resolve - and expect unions, not disagreements

**In this repository, nearly every conflict is both sides adding to the same list.** A
feature branch adds a domain, develop adds a different one, and they land on the same line.
The resolution is to keep both, and the danger is picking a side out of habit.

The same addition usually surfaces in six or eight places at once, and missing one of them
compiles but misbehaves. When one branch adds a domain, expect it in all of these:

| Where | What it looks like |
| --- | --- |
| `Ranplan.SDK.Catalog/Domain.cs` | the `Domain` enum |
| `Ranplan.SDK.Catalog/ScriptCatalog.cs` | the string -> enum switch |
| `Ranplan.SDK.Catalog/TagDirectives.cs` | the `@domain` tag parser |
| `Ranplan.SDK.TestRunner/Cli.cs` | the `--domain` help text |
| `docs-domain-overrides-command-api.json` | two lists: DTO namespaces and service types |
| `eval/loop.py` | the domain -> AiDocs-domain map |
| `SDK.Api/IProjectServices.cs` | the service property |
| `PluginSDK.Runtime/Services/ProjectServices.cs` | field, constructor line, property - three hunks |
| `PluginSDK.Runtime/Automation/ScriptCompiler.cs` | the pre-imported DTO usings |
| `PluginSDK.Tests/Automation/RevertibilityAnnotationTests.cs` | the asserted service list |

Two things decide ordering, and both are stated in the code rather than guessable:

- **The `Domain` enum is ordered deliberately** - `TestSession` runs cases in enum order and
  `PluginSDK` must stay last, which develop's own comment says. Append before it.
- **Some lists are alphabetical** (`RevertibilityAnnotationTests`), some are grouped by
  concern (`IProjectServices`). Read the neighbours rather than appending at the end.

For a JSON list, the union needs a comma on the line that used to be last. Parse the file
before staging it:

```
python -c "import json;json.load(open('<path>',encoding='utf-8'));print('ok')"
python -m py_compile <path.py>
```

### 5. When a conflict is NOT a union

Occasionally both sides edited prose that describes behaviour - a help string, a README
line. Then the question is not "which side" but **what does the merged code actually do**.
Go and read it.

A real example: both branches described the runner's default domain selection, each naming
its own domains. Neither was right after the merge, because `ScriptCatalog.Filter` selects
*everything except* `PluginSDK` - and had done all along, so the pre-merge text on the
feature branch was already understating it. Resolving to either side would have committed a
false statement. Resolve to the code.

### 6. Stage explicitly, commit, and say what the conflicts were

```
git add <each resolved path>          # never -A: the tree is full of unrelated untracked files
git diff --name-only --diff-filter=U  # empty = all resolved
git status --short | grep '^??'       # confirm what is deliberately NOT going in
git commit -F <message file>
```

The merge message is worth writing properly, because it is the only place the resolution is
explained. Subject `Merge develop into TaskNNNNNN`, then one paragraph: how far behind the
branch was, what shape the conflicts were, and any resolution that was a judgement rather
than a union.

### 7. Build before pushing - and restore first if you changed branch

A merge that does not compile is worse than no merge - it looks done. A union resolution
that dropped one of the ten sites compiles on nine of them and fails on the tenth, which is
exactly the failure this step catches.

```
.\buildTools\dev\build.ps1 -Restore
```

**Pass `-Restore` whenever you have switched branch since the last build**, which this flow
guarantees you have - the task branch, possibly a detour, then back. `obj\project.assets.json`
holds the dependency graph of whichever branch was checked out when it was written, and a
merge that adds or moves a project reference invalidates it. The failure does not look like a
stale cache: a whole solution's worth of projects report

```
NU1105: Unable to find project information for '...\RanplanWireless.DiffAco.Core.csproj'
```

with zero C# errors, which reads as a broken merge. One cache-only restore clears all of it.
By hand that is `-t:Restore -p:RestoreSources=` before a no-`-restore` build; the empty
`RestoreSources` is what makes it safe, because NuGet then resolves from the local cache or
fails cleanly instead of fetching a wrong version.

**Read the exit code directly, not the last line of output.** A shell pipeline reports its
own status, so a build that failed can be followed by `[exited with code 0]`:

```
MSYS2_ARG_CONV_EXCL='*' "$MSB" ... > build.log 2>&1; echo "EXIT=$?"
grep -cE ': error' build.log
```

Then run the tests for the assemblies whose files you resolved, not the whole suite.

### 7b. Separate an inherited failure from one you caused

A 400-commit merge usually brings failing tests with it, and the question is never "are
there failures" but "are they mine". Guessing either way is wrong: claiming they are
inherited without evidence hides a real break, and claiming the merge broke them sends
somebody after a bug that was already on develop.

Two checks settle it, and both are cheap:

```
git diff --quiet HEAD^2 HEAD -- <file> && echo "identical to develop"
git show HEAD^1:<test file> | grep -c "<the failing test>"
```

`HEAD^1` is the branch as it was, `HEAD^2` is develop. A file byte-identical to develop's
version cannot have been changed by your resolution, and a test that did not exist on
`HEAD^1` arrived with the merge. If both hold and nothing you resolved is on that call path,
say so in the PR **with the commands**, so a reviewer can check rather than take your word.

### 8. Push and PR the task branch back into the feature branch

```
git push -u origin Task117314
python <pr-review>/scripts/ado_pr.py create Task117314 feature/PBI115643 pr.json --dry
python <pr-review>/scripts/ado_pr.py create Task117314 feature/PBI115643 pr.json
```

`pr.json` is `{"title": ..., "description": ..., "work_items": [117314]}`. Branch names go
in bare - the script adds `refs/heads/`, because getting that wrong is answered with a 404
that names neither branch. Listing the work item links the PR to it in the same call.

The PR target is the **feature branch**, never develop. Say in the description that it is a
develop catch-up, how many commits, and list the conflicts with their resolutions - a
reviewer approving a 500-commit diff is really only reviewing those.

## Traps

- **Merging into the feature branch directly.** Then the conflict resolution is unreviewed,
  and a bad resolution is on the branch everyone else builds on.
- **`git add -A` after a merge.** iBuildNet working trees carry local notes, tooling and
  generated files; a merge commit is the easiest place to sweep one in unnoticed.
- **Picking a side because the hunk is small.** A one-line conflict in this repository is
  almost always two people appending to the same list.
- **Resolving the enum without reading the comment.** `PluginSDK` last is load-bearing.
- **Stashing with a bare `git stash`.** It takes everything, including modifications you
  wanted in the merge. Name the paths.
- **Pushing before building.** The union that missed one site is invisible until then.
- **Reading `NU1105` as a broken merge.** Switching branch invalidates the restore graph, and
  the result is dozens of projects failing to find one project - with no compile error
  anywhere. Restore, then judge.
- **Believing the last line of the build output.** `[exited with code 0]` is the shell's
  status, not MSBuild's. Capture `$?` directly.
- **Calling a test failure inherited because it looks unrelated.** It usually is, but say it
  only after `git diff HEAD^2 HEAD` on the file comes back empty.
- **Assuming the pre-merge text was right.** When both sides edited a description, the merge
  is the moment to check it against the code; it is often the first time anyone has.

## Related

- `git-commit` - staging discipline and the message shape used here.
- `pr-self-review` - read the diff before the PR, including a merge diff.
- `pr-review` - `scripts/ado_pr.py` for creating the PR and replying to threads.
