# claude-skills

My custom skills repository for Claude Code CLI agent.

Personal, cross-project skills live here. Skills that only make sense inside one
repository belong in that repository's own `.claude/skills/`; team-shared skills belong
in the team's skill repository.

## Layout

```
<skill-name>/SKILL.md      # one directory per skill; the entry point is always SKILL.md
<skill-name>/scripts/      # optional: supporting scripts
<skill-name>/references/   # optional: reference material
_template/                 # starting point for a new skill; underscore-prefixed dirs are never linked
link.cmd                   # junctions every skill here into Claude Code's discovery directory
```

## Wiring up a machine

Claude Code only scans `%USERPROFILE%\.claude\skills` (on my machines that directory is
the team repository's working copy), so this repository's skills are junctioned in:

```
link.cmd
```

Run it from PowerShell or Explorer (Git Bash mangles the arguments), and rerun it after
adding a skill. The script also writes the linked names into the team clone's
`.git\info\exclude` (local-only), so personal skills never dirty the team repository's
`git status`.

## Writing a new skill

1. Copy `_template` to a new directory; the directory name is the skill name (kebab-case).
2. The frontmatter `description` must open with when to use it - that sentence is what
   decides whether Claude ever thinks of the skill.
3. Write the body for someone with zero context: what it does and why first, then the
   steps and the traps.
4. Run `link.cmd`, commit, push. (Or use the `skill-creator` skill, which also covers
   description tuning, evals and packaging.)
