---
name: ibuildnet-dev
description: >-
  Use when working in the iBuildNet desktop repository and you need to build it, work out
  which unit-test projects your change touches, run only those, or prove that a test really
  pins a behaviour by mutating the code - and whenever you need the repository's own notes:
  where the entry points are, which projects are in no solution, the module acronyms, and the
  code-style rules review keeps flagging. Wraps MSBuild and vstest with every known trap
  handled, so reach for it before typing a raw MSBuild command.
---

# iBuildNet developer loop: build, affected tests, mutation check, repository notes

## When to use / when not to

- Use when: building `iBuilding_2010.sln` or one project on a developer machine; deciding which
  test assemblies a diff touches; running a test fixture; checking that a test goes red when the
  behaviour it claims to pin is broken; orienting in the repository (entry points, layout,
  acronyms, style rules).
- Do not use when: the question is about Sidekick's own verification layers (`sidekick-verify`),
  merging develop into a task branch (`ibuildnet-merge-develop`), or reviewing a PR
  (`pr-self-review` / `pr-review`).

## Why wrappers instead of the raw commands

The correct incantations for this repository are long, and each has a trap that fails
*quietly*: a bare `.csproj` build that "succeeds" while writing to a bogus path and leaving
`bin\Debug` stale; a test run killed by `/Platform:x86` because the GdalBin natives are x64-only;
a mutation that is never reverted. The scripts under `scripts/` discover MSBuild and vstest
through `vswhere`, read the project list straight out of the solution file, and encode those
traps, so they work on any machine, edition and checkout path.

They find the repository from where they are run: `$env:IBUILDNET_ROOT` when set, otherwise the
git top level of the current directory. Run them from inside the checkout, or set the variable.

## Steps

1. **Build.** `scripts\build.ps1` builds the solution as `Debug|Any CPU` and prints only errors
   plus the outcome; `-Project iBuilding.BLL` builds one project *with `SolutionDir` supplied*;
   `-Restore` does a cache-only restore first; `-Full` shows MSBuild's own output. On success it
   reports when `iBuildNet.exe` was last written - **exit code 0 is not proof of a useful build;
   that timestamp is.**
2. **Find what to test.** `scripts\affected.ps1` maps your changed files (against
   `origin/develop`, or `-Against HEAD` for uncommitted work) to the projects that own them and
   then to the test projects whose names say they cover those. It is a naming map, not a call
   graph: treat the output as the floor, and read the projects it found *no* test for.
3. **Run only those.** `scripts\test.ps1 -Changed`, or a named assembly with an optional
   `-Filter "FullyQualifiedName~Antenna"`. Every test project writes to one shared folder,
   `iBuilding\iBuilding.UITest\bin\Debug`, so runs pick assemblies from there; a name not found
   there almost always means "not built", and the error says so and gives the build command.
4. **Prove a test claim.** Before writing "test X pins behaviour Y", run `scripts\mutate.ps1`
   with `-Find`/`-Replace` on the source line, the project to rebuild and the test to run.
   **KILLED** means the test went red and the claim holds; **SURVIVED** means the test stayed
   green while the behaviour changed - strengthen the test, never soften the claim. The original
   bytes are restored in a `finally`, MD5-checked, and the working tree is verified with git.
5. **Orient.** `references/repo-notes.md` is the repository briefing: running tests and the two
   traps that make a test read the wrong value, where things live (entry points, projects in no
   solution, other-repository domains, acronyms), worktrees instead of branch switches, and the
   code-style rules review flags. `references/ARCHITECTURE.md` walks one request through the
   application: stack, entry points, the two script paths, the data flow.

## Traps

- **`$(SolutionDir)` is undefined when a bare `.csproj` is built**, so output lands in a
  per-project `iBuilding.UI\bin\Debug` and the real one stays stale with no error. Build the
  solution, or pass `-p:SolutionDir=C:/path/iBuildNet/iBuilding/` (forward slashes, trailing
  slash). `build.ps1 -Project` does this for you.
- **Never pass `/Platform:x86` to vstest.** The run dies with a native load failure that reads
  like a test bug. `test.ps1` never passes `/Platform`.
- **Duplicate-compile errors (`CS0111`)** mean a nested `iBuilding.UITest` directory was created
  under another project's output; delete the nested directories and rebuild.
- **A running `iBuildNet.exe` locks `bin\Debug`.** MSBuild then fails with MSB3027/MSB3021 on
  every DLL the app has loaded. Close the app (its main window, so unsaved work prompts) before
  building.
- **`git rev-parse --show-toplevel` from a worktree returns that worktree**, which is what you
  want: each worktree keeps its own warm `bin\Debug`, and `driver.json` / `sdk-test` are already
  worktree-scoped.
- **These are layers 1 and 2 of verification only.** The C# compile gates for the Sidekick tool
  bodies and the live `sdk-test` gate need a running application and are *skipped rather than
  failed* when a prerequisite is missing; see `sidekick-verify`.

## Supporting resources

- `scripts/_common.ps1` - repository discovery, `vswhere` lookups, the solution's project map.
- `scripts/build.ps1`, `scripts/affected.ps1`, `scripts/test.ps1`, `scripts/mutate.ps1` - the
  four steps above; each has a comment header with its parameters.
- `references/repo-notes.md` - the repository briefing (tests, layout, worktrees, code style,
  git rules).
- `references/ARCHITECTURE.md` - the desktop application's architecture, traced through one
  request.
