---
name: debug-root-cause
description: >-
  Use whenever something is broken and the cause is not yet proven: a failing test, a red
  build, a crash, a wrong number on screen, "为什么会这样", "这个 bug 怎么回事", a PR gate
  that went red, or an exception pasted into the chat. Drives the investigation from
  symptom to a proven causal chain before any code changes, separates "my change broke it"
  from "it was already broken", and ends with a minimal fix pinned by a test that goes red
  when the fix is reverted. Use it even when the user only says "fix this" or "看看这个
  报错" - especially then, because the tempting first guess is what costs the afternoon.
---

# Debug by proving the mechanism, not by pattern-matching the symptom

## When to use / when not to

- Use when: a symptom exists and the cause does not. Failing test, red pipeline, wrong
  output, crash, "it worked yesterday", an exception with a stack trace.
- Do not use when: the cause is already proven and only the fix is left; or the task is a
  feature, not a defect. Reviewing a diff for latent bugs is `pr-self-review`, not this.

## Why this exists

The expensive debugging failures are not "the fix was hard". They are:

- fixing the first thing that *looks* like the known failure, and shipping a change that
  addressed nothing;
- chasing a red build that was red before the branch existed;
- "fixing" a stale build output by editing source;
- a fix that works, with a test that would still pass if the fix were deleted.

Every step below exists to make one of those impossible.

## Steps

### 1. Get the exact symptom, in text

Copy the real error, the real failing assertion, the real value. Not a paraphrase and not
what it "usually means". If the user pasted a screenshot of a number, find the code that
prints that number before theorising about it.

Write one sentence: **what is observed** vs **what was expected**. If you cannot write
that sentence, you do not yet have a bug report, and the next step is to ask for or
produce one.

### 2. Reproduce at the smallest scope that still fails

Run the one test, not the suite. Open the one project, not the solution. A reproduction is
what makes a later "it's fixed" mean anything; without one, you are guessing twice.

If it will not reproduce, that is itself the finding, and the split is:

- **environment vs code** - stale build output, a cached package, a missing licence, an
  out-of-date dependency copied into `bin/`. Rebuild the *specific* thing and retry before
  reading any source.
- **data vs code** - a project file, a fixture, a recorded session the user has and you
  do not.

### 3. Establish whether this branch caused it

Never skip this. A red gate is not evidence that your change is guilty.

```
git log --oneline <merge-base>..HEAD        # what this branch actually added
git stash && <run the failing thing>        # does it fail with the changes parked?
git checkout <merge-base> -- <suspect file> # or narrow file by file
```

Run the same failing thing on a clean target branch. If it fails identically there, the
finding is "pre-existing on develop", it belongs in the report, and the fix decision is
the user's, not yours.

### 4. Prove the mechanism before changing anything

Name, with file:line evidence, the place where the value first becomes wrong and where the
wrong value came from. Write the chain out:

```
UI shows 0 dB
  <- ReportBuilder reads Losses[cableId]            (Report/Builder.cs:212)
  <- the dictionary is keyed by jumper id           (Model/Cable.cs:88)
  <- the writer keys it by trunk id                 (Calc/LossWriter.cs:140)
```

The chain is done when each arrow is a line you have read, not a line you assume exists.
Two habits do most of the work here:

- **Read the source of the thing you are assuming**, especially provider and DTO shapes.
  "It returns an empty list when nothing matches" is a claim about someone else's code;
  open it.
- **Follow the value, not the control flow.** Most wrong answers are a wrong key, a wrong
  unit, a wrong default or a swallowed failure - not a wrong branch.

### 5. Distrust the resemblance

A symptom that matches a known failure may have a different cause, and the known cause is
the one you will find first because you are looking for it. Before acting on "this is the
usual X", find the evidence that only X would produce. Two live examples:

- a wall of red compile tests in the tool engine is *usually* stale SDK DLLs in
  `bin/Debug`, not a regression - but "usually" is not a diagnosis, so check the DLL
  timestamp;
- an empty result is often a swallowed exception rather than a genuinely empty answer;
  `catch {}` turns "I could not read it" into "there is nothing", and the two lead to
  opposite fixes.

### 6. Fix in the layer that owns the defect

The fix goes where the wrong value is produced, not where it is noticed. A workaround in
the consumer leaves the same bug for the next consumer, and the code now has two truths.
If the root cause is in a dependency you also own, fix it there and take the version bump;
say so explicitly if that makes the change bigger than the user expected.

Keep the change minimal and do not bundle a refactor with it. A defect fix that also
tidies three things cannot be reverted cleanly when it turns out to be wrong.

### 7. Pin it with a test that would have caught it

The test must fail on the code as it was. Write it first, watch it go red against the
unfixed code, then fix. If that order is impossible, revert the fix afterwards and confirm
the red - `mutation-verify` exists for exactly this and takes a minute.

Check the fixture has **the shape that produces the defect**: if the bug needs two source
templates, a fixture with one will pass either way and pins nothing.

### 8. Report what you found, not just what you changed

Say the mechanism in one or two sentences, say what is fixed, and say plainly anything you
could not verify or deliberately left alone (pre-existing failures, environment problems,
a second defect found on the way).

## Traps

- **Stale outputs lie.** Build succeeded, tests unchanged, nothing updated - because the
  output went to a bogus path or the DLL was never rebuilt. Confirm a fresh timestamp on
  the artefact you are actually running before believing any result.
- **`exit 0` is not proof.** A piped command reports the pipe's status; a gate script that
  prints its outcome before the last five checks reports PASS with five failures behind it.
- **The first green run after a change proves nothing** if you never saw it red.
- **A "transient" that repeats is a bug.** Re-running until green is how a real defect gets
  shipped with a sticker on it.
- **Two things are broken more often than feels fair.** When the fix only half works, stop
  and re-derive the chain rather than stacking a second guess on the first.

## Related

- `mutation-verify` - the mechanical way to prove a test pins the fix.
- `pr-self-review` - once fixed, before pushing: what else shares the constraint you just
  changed.
