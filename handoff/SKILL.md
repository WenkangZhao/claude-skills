---
name: handoff
description: >-
  Use when work has to survive a boundary: the user says "写个交接文档", "handover", "我
  要换个 session 继续", "帮我总结一下现在的进度给下一个人", the context window is running
  out mid-task, or someone has just handed work TO us ("现在 handover 给我了"). Produces a
  HANDOFF.md that a stranger can act on - verifiable state (branch, commit, PR, build),
  what is done versus left, the decisions already taken and why, the traps already paid
  for, and the exact command to resume - and, on the receiving side, verifies every claim
  in the document against the repository before acting on it.
---

# Hand work over so the next person does not start again

## When to use / when not to

- Use when: writing a handover for a colleague or a future session, or picking one up.
- Do not use when: the user wants a status update in chat. That is a message, not a
  document - a handoff is for someone who cannot ask you a follow-up question.

## Why the usual handover fails

A handover written from the conversation reads like a diary: what was tried, in the order
it was tried. The person receiving it needs almost none of that. They need **the state of
the world right now**, **what has already been decided**, and **what to do next** - and
they need to be able to check each of those without trusting you, because by the time they
read it the branch has moved.

So write it state-first, evidence-first, and put the narrative last or nowhere.

## Writing a handoff

Put it at the repository root as `HANDOFF.md` (untracked - it is a note between people,
not a repository artefact), and use this shape:

```markdown
# <what this work is> - handoff <date>

## Goal
One paragraph: what "finished" means, in the user's terms. Include the work item / PR ids.

## State you can verify
| what | value |
|---|---|
| branch | feat/poll-client-job @ c392630 |
| PR | 58258, active, 0 behind develop, mergeable |
| build | 0.1.72 succeeded |
| local suite | 371 passed, 2 skipped (2026-09-11) |
Anything a command can confirm goes here with the value it had and when.

## Done
Bullets of finished, verified work - each with the evidence (test name, commit, build).

## Left, in order
Numbered, smallest first where possible, each with its acceptance check.

## Decisions already made - do not reopen
The choice, and the reason, in one line each. This is the section that saves the most
time: without it the next person re-derives the same trade-off and sometimes reverses it.

## Traps already paid for
The things that cost hours and will not be obvious: a switch that must be quoted, a gate
that reports PASS with failures behind it, a merge that silently duplicated a route.

## Resume here
The literal commands to get back to work, from a cold shell.

## Open questions for a human
Only the ones that actually block, each with the options and your recommendation.
```

Two rules about content:

- **Mark what is verified and what is assumed.** "Tests pass" and "tests passed when I ran
  them on Thursday" are different claims. Never launder the second into the first.
- **Include the failed attempts, briefly.** Not as narrative - as a fence. "Splicing the
  corpus by hand looked impossible; there is a sanctioned precedent at `b1537f0`" stops
  the next person spending the same afternoon.

## Receiving a handoff

Treat the document as a hypothesis, not a report. Before doing anything it suggests:

```
git fetch origin && git log --oneline -3 && git status --short
```

Then check, in this order, because each can have changed since it was written:

1. **The branch and commit** named in the document still exist and are still where the
   work is.
2. **The PR** is still active, and read its threads - new comments are the most common
   thing a handoff misses.
3. **The build** state now, not the state recorded.
4. **The claims about the code** - grep for the files, functions and flags it names. A
   handoff that names something which no longer exists is telling you the world moved.

Say out loud which of the document's claims did not hold. That is information the person
who wrote it wanted you to have.

Then re-derive the plan from what you found, not from the document's ordering.

## Traps

- **A handoff that lists files changed** instead of decisions made. The diff already lists
  the files; only you know why.
- **Numbers without dates.** "279 tests pass" is unusable six commits later.
- **Confidence without evidence.** If you did not run it, say you did not run it. The next
  person will trust the document exactly as much as its worst claim deserves.
- **Writing it at the very end, when the context is gone.** Draft it as the work goes and
  keep it current; a handoff reconstructed from memory is where the traps get dropped.
- **Leaving the open question implicit.** If a decision is the user's, it goes in its own
  section with options - buried in a paragraph it will simply be made for them.
