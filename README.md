# claude-skills

My custom skills repository for Claude Code CLI agent.

个人跨项目通用的 Claude Code skill 放这里；只对某个仓库有意义的 skill 放那个仓库自己的
`.claude/skills/`，团队共享的放公司 ADO 的 `claude-skills` 库。

## 布局

```
<skill-name>/SKILL.md      # 每个 skill 一个目录，入口固定叫 SKILL.md
<skill-name>/scripts/      # 可选：配套脚本
<skill-name>/references/   # 可选：参考资料
_template/                 # 新 skill 的起点，下划线开头的目录不会被接线
link.cmd                   # 把本库所有 skill 接进 Claude Code 的发现目录
```

## 本机接线

Claude Code 只扫描 `%USERPROFILE%\.claude\skills`（那里是公司库的工作副本），
所以本库的 skill 通过目录 junction 挂进去：

```
link.cmd
```

新加 skill 后重跑一次即可。脚本同时把挂进去的名字写进公司库工作副本的
`.git/info/exclude`（只影响本机），保证公司库的 `git status` 不被个人 skill 弄脏。

## 写新 skill

1. 复制 `_template` 为新目录，目录名 = skill 名（kebab-case）。
2. frontmatter 的 `description` 第一句写"什么时候用"——它决定 Claude 会不会想起这个 skill。
3. 正文写给完全不知道上下文的下一个人：先说做什么、为什么，再给步骤和陷阱。
4. 跑 `link.cmd`，提交推送。
