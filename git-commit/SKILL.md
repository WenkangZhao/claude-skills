---
name: git-commit
description: >-
  Use whenever the user asks to commit or push work - "commit 一下", "提交", "push it",
  "把这些改动提交了", "帮我写个 commit message", or after they have verified a change and
  want it recorded. Stages explicit paths (never `git add -A`, because a secrets file has
  been one wildcard away from an unrewritable push), writes the message in the shape this
  repository already uses, keeps Claude/Co-Authored-By watermarks out, and checks the
  branch before committing. Use it even for a one-line change - the damage from a bad
  `add` or a wrong branch has nothing to do with how big the diff was.
---

# Commit the way this repository already commits

## When to use / when not to

- Use when: the user asks for a commit or a push, or asks for a commit message.
- Do not use when: the user has not asked. Editing files is not permission to commit; they
  verify first, then say so. If a change is finished and uncommitted, say it is ready and
  stop there.

## Steps

### 1. Look before staging

```
git status --short
git branch --show-current
git diff --stat
```

Three things to settle before anything is staged:

- **Am I on a branch I may commit to?** Not `develop`, not `main`, not a shared
  integration branch. If HEAD is on one of those, create the task branch first and say so.
- **Is every changed file mine to commit?** Local settings files, temporary harness
  hacks, generated output and scratch notes show up here. Anything you did not deliberately
  change is a question for the user, not a file to sweep in.
- **Did an unrelated change ride along?** Split it into its own commit rather than hiding
  it inside this one.

### 2. Stage explicit paths, never `-A`

```
git add path/one.cs path/two.cs tests/OneTests.cs
```

`git add -A` / `git add .` are off the table, and not as a style preference. A settings
file holding a personal access token sat one wildcard away from being committed, and the
server refuses force-push, so a leak cannot be rewritten out of history afterwards. The
cost of typing paths is seconds; the cost of the other thing is a rotated credential and
an incident.

Then confirm what is actually staged:

```
git diff --cached --name-only
```

### 3. Run the tests that this change can break

Only the affected fixtures or assemblies, not the whole suite - a full sweep on every
commit trains everyone to skip it. Group the staged files by project and run those. If the
change is comments or documentation only, say you are skipping tests and why.

### 4. Write the message in the repository's own shape

Read what the repository does before inventing a format:

```
git log --format='%s%n%n%b---' -8
```

Match it. Most of these repositories use a **subject line that states what the change
does**, in plain words, optionally with a short domain prefix the repo already uses - then
a blank line, then **one paragraph** explaining what changed and why it had to change.

What the paragraph is for: the reader a year from now who is asking why this line is the
way it is. What it is not for: review narrative, mutation-testing evidence, test counts,
self-assessment, a bulleted summary of files touched. Those belong in the PR description
or nowhere.

Never append a Claude Code, "Generated with", or `Co-Authored-By` footer. These repos'
history does not carry one, and a team-visible commit is the wrong place to discover a
preference. If a session-level setting says otherwise, follow the user's standing
instruction and tell them the setting disagreed.

**Multi-line messages go through a file, not a heredoc.** Shell heredocs mangle
backslashes and quotes in ways that are invisible until the message is already in history:

```
# write the message with the Write tool, then:
git commit -F /path/to/message.txt
```

### 5. Commit, then look at what you made

```
git show --stat HEAD
```

Confirm the file list is exactly what you intended and the message renders as subject +
paragraph.

### 6. Push only the branch you are on

```
git push origin <branch>
```

Never force-push a shared branch; on Azure DevOps it is usually refused anyway, which
means a bad push is fixed by another commit rather than by rewriting. If the push is
rejected as non-fast-forward, fetch and merge deliberately - do not reach for `--force`.

If a pull request follows, that is `pr-self-review`'s job first: the diff gets read as an
external reviewer would read it before it goes in front of one.

## Traps

- **Amending after a push** is a rewrite. If it is already pushed, add a commit.
- **"I'll just commit the whole directory"** is `add -A` wearing a different hat.
- **A commit message written from the plan** describes what you meant to do. Write it from
  `git diff --cached`, which is what you actually did.
- **Staging a file you only read** happens with editor-formatted saves; check
  `git diff --cached` for whitespace-only noise before committing.
- **Committing on the branch you happened to be on** is the most common way work lands on
  `develop`. Step 1 exists for this.

## Related

- `pr-self-review` - run before opening or updating a PR.
- `pr-review` - reviewing someone else's PR, with the ADO scripts.
