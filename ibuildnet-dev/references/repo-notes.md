# iBuildNet repository notes

What an agent opening the iBuildNet desktop repository has to be told, beyond the build
instructions its own `CLAUDE.md` carries: how the tests are run and the two ways one reads a
wrong value, where things live, why a worktree beats a branch switch, and the code-style
rules review keeps flagging. The build/test wrappers are in `../scripts/`.

## Running the unit tests

Most module test projects (`iBuilding.BLL.Test`, `iBuilding.UITest`, …) share one output directory: **`iBuilding/iBuilding.UITest/bin/Debug`**. Run `vstest` from there, against the assembly you changed — not the whole tree.

- **Never pass `/Platform:x86`** — the GdalBin natives are x64-only and the run dies with a load failure that looks like a test bug.
- Building a test `.csproj` directly needs `-p:SolutionDir=...` for the same reason as Gotcha 1.
- Duplicate-compile errors (`CS0111`, the same type twice) mean a nested `iBuilding.UITest` directory was created under another project's output — delete those nested dirs and rebuild.
- **Do not run tests automatically after an edit.** Report that the change is ready and wait; the author decides when a run is worth the minutes.

Two traps that make a test read the wrong value rather than fail honestly:

- **NSubstitute: a setter call on a mocked property overrides a prior `.Returns()`.** If you stub a property and then run `LoadSettings()` — or any init that writes to it — the test reads what the init wrote, not your stub. Re-stub *after* the write.
- **Resolve shared services, don't `new` them.** The bc-mdm `MaterialLibraryServiceFactory` is registered as a singleton, so `ServiceLocator.Provider.GetService<IMaterialLibraryServiceFactory>()` is the canonical way to get one; a hand-built factory quietly gets its own state.

## Where things live

`iBuilding_2010.sln` holds 124 projects. Two things about the layout waste the most time when they are not known up front:

- **Some projects in this repository are in NO solution file.** `iBuilding/RanplanWireless.Sdk.Prediction.*` and `iBuilding/RanplanWireless.Sdk.CellularOptimization.*` are real source here, but appear in neither `iBuilding_2010.sln` nor `iBuildNetTools.sln` — they build and publish as packages, and the app consumes the published package (Prediction 2.5.11). So "the IDE does not show it" and "grep finds it" are both true at once.
- **Other domains genuinely live in other repositories** and arrive as `RanplanWireless.Sdk.*` packages: ProjectStore, MDM (material data — the `bc-mdm` repo), SDM, Rendering, Annotations, LinkBudget, Security, glTF. A data-loss or schema gap that originates there is fixed **there**, never worked around on the iBuildNet side.

Entry points, in the order the outside world reaches them:

| What | Where |
| --- | --- |
| Process entry, variant selection, licence gate | `iBuilding.UI/Program.cs:163` (licence at `:248`) |
| Startup sequence: DriverServer, main form, message loop | `iBuilding.UI/Startup/Runners/DefaultVariantRunner.cs:68` |
| Static application object (main form, panels, `OpenFile`) | `iBuilding.UI/DOM/iBuilding.cs:110` |
| Domain root, `Project.Current` | `iBuilding.BLL/Project.cs:97` / `:198` |
| Command API surface (what automation scripts receive) | `RanplanWireless.Professional.SDK.Api/IScriptContext.cs` |
| Command API implementation (six domain services + revert log) | `iBuilding.PluginSDK.Runtime/Services/ProjectServices.cs:52` |
| Sidekick chat host bridge / controller | `iBuilding.UI/Sidekick/SidekickHostBridge.cs`, `SidekickController.cs` |

Module acronyms, because the directory name and the SDK package name do not always mean the same layer: **BSM** = building structure modelling (2D plan editing mirrored into 3D); **SD_LD** = system design / layout design (contains NSD, the network system diagram); **SDM** = system design model; **DBM** = the device and material library UI (the material *data* itself moved to the MDM packages).

## Switching branches costs a full rebuild — use a worktree instead

124 projects means every branch switch invalidates the build. A worktree per long-lived branch
keeps a warm `bin\Debug` for each, and the pieces that care about *which* build they are
talking to are already worktree-scoped by design: `driver.json` is written beside the running
`iBuildNet.exe`, and `sdk-test` resolves the one build sitting above its own output (override
with `IBUILDNET_EXE`).

```bash
git worktree list                                    # what already exists
git worktree add ../iBuildNet-develop develop        # a second checkout on develop
```

The cost is disk: each worktree carries its own `bin`/`obj`. Remove one with
`git worktree remove <path>`; never just delete the folder, or git keeps the registration.

## Code style

These are the rules review keeps flagging. They are conventions of this codebase, not general C# advice.

**New files.** Every new `.cs` file carries the full 16-line Ranplan copyright block (`//  **` — two spaces on the first line), saved as UTF-8 **with BOM** and **CRLF**. A 5-line abbreviated header is not the house style.

**Naming and layout.**
- Test methods are `Given_When_Then`, with arrange/act/assert blocks; omit a section only when it is genuinely empty.
- No redundant fully-qualified names: if the namespace is already `using`-ed at the top of the file, use the short type name. Scan the using block first.
- **No tabular alignment.** Never pad with extra spaces to line up declarations, `=` signs, call arguments or dictionary literals into columns — one space after the token. Some legacy material-UI files carry that style for historical reasons; do not copy it into new code.
- `[NotNull]` / `[CanBeNull]` go on their own line above the declaration, never inline.
- No single-line `if (x) return;` — expand to two lines plus a blank one. Blank line before a closing block and after a guard; `try`/`catch` always multi-line.
- A multi-line ternary puts `?` and `:` at the **start** of the continuation lines; a chained ternary indents by 4 spaces rather than aligning to the `?`.

**Comments and docs.**
- `///` XML docs are **ASCII only** — no HTML entities (`&#8211;`), no curly quotes, no en/em dashes. Plain `//` comments may use them.
- Comments describe behaviour on its own terms. They must not name branches (`develop`, `feature/X`), work items (`Task115025`, `PBI-114391`), or tell a migration story ("this used to do X"). Git log and the PR description are the right home for that context.

**Design.**
- No new global or static state: avoid `Project.Current`, `[ThreadStatic]`, singleton service locators and `AppConst` in new code. Prefer constructor injection or threading the value through explicitly.
- Every user-visible message must exist in all five language resources. Grep the resource key to confirm it exists before using it; legacy UnitDisplay strings are fetched through `LoadLegacyUnitDisplayString`, and any fallback text must match the legacy wording word for word.
- Every bug fix ships with a unit test that covers it, written before the commit. Reviewers (including Copilot) flag missing coverage, and the test is what stops the regression coming back.

**Git.**
- **Never `git add -A` or `git add .`** — stage explicit paths. `iBuilding/.claude/settings.local.json` holds a personal access token and is not covered by the root-anchored ignore rule; Azure DevOps denies force-push, so a leak cannot be rewritten out of history afterwards.
- Do not commit without being asked. Finishing an edit is not permission to commit — the author verifies first.
- Commit messages are a subject line plus one paragraph saying what the change does. No review narrative, no test counts, no `Co-Authored-By` or "Generated with" footer: this repository's history does not carry one.
- PR descriptions follow the team's shape: two sections, **Summary** and **Notes**, with paragraph-style bullets grouped by logical change, each naming concrete identifiers (file, class, method) so a reviewer can navigate. Keep the whole thing under roughly 2000 characters — cut the verification appendix and the per-test enumeration; an unread description is worse than a short one.
