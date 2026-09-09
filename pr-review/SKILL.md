---
name: pr-review
description: >-
  Use whenever the user asks to review a pull request (an Azure DevOps PR link, "帮忙
  review 一下这个 PR", "按高级工程师的标准 review", "inline comment"), or to re-review a PR
  after fixes, even if they only paste the link. Pulls the PR, its description and existing
  threads from ADO, reads the WHOLE diff against the merge base plus the callers behind it,
  verifies every candidate finding against source (never against the description), posts
  inline threads in the team's severity format (🔴 BLOCKER / 🟠 CRITICAL / 🟡 MAJOR /
  🔵 MINOR, evidence with file:line, failure scenario, fix) and one summary thread with a
  verdict table and a "checked and sound" section. Never duplicates an existing thread.
---

# 审别人的 PR

## 什么时候用 / 什么时候不用

- 用：用户给出 ADO PR 链接要 review；要在 PR 上 inline 评论；一轮修复后要复审。
- 不用：审自己的 PR（用 `pr-self-review`）；用户只想要一段口头印象而不发评论（那也照第 1–5
  步核，只是不发）。

## 目标

产出的是**能被核实的发现**，不是印象。每条发现都带：在哪（file:line）、为什么错（引用
代码，不引用描述）、什么输入会出什么错、怎么修。写不出失败场景的不发。

## 步骤

### 1. 拉 PR

```
python scripts/ado_pr.py fetch <prId>          # 标题、分支、描述、所有线程（含状态和回复）
git fetch origin <source> <target>
git merge-base origin/<source> origin/<target>
git diff --stat <base> origin/<source>
```

PAT 从 `iBuilding/.claude/settings.local.json` 的 `AZURE_DEVOPS_PAT` 读（或环境变量）。
已有线程要记下编号和结论：**不重复别人已经提过的**，总结里可以引用。

### 2. 读完整 diff，再读 diff 背后的调用者

逐文件 `git diff <base> origin/<source> -- <file>`。生产代码、测试、csproj、cookbook、
README 都读。然后对 diff 里每个新方法、每个改了签名或语义的方法：

```
git grep -n "<名字>" origin/<source> -- '*.cs'
```

找它的调用者和它替代的旧路径。**重问题几乎都在 diff 没碰的文件里**：报表侧的读取 vs
计算侧的读取、Command API 的计数 vs 路由的计数、读回时跳过的模板 vs 写入时的每格开关。

### 3. 逐个候选发现核实

- 打开源码看那一行，不信 PR 描述和注释里的说法；
- 对"X 也这么做"的说法去 X 处核（描述说"API 按 prediction 计数"，去 `DescribeKpis` 数）；
- 构造具体失败场景：设备形状 + 输入 + 两侧各算出什么数；
- 判断可达性：产品路径能到吗，还是只有工具/测试能到；
- 判断是否本 PR 引入：`git blame` 或对比 merge base；历史问题降一级并注明。

核不出失败场景的候选丢掉。核实过程里发现描述和代码不一致，本身就是一条。

### 4. 必查清单

- **同一件事的两份实现**：报表 vs 计算，API vs 路由，包内 vs 包外，UI vs 服务。两边选链路
  /算计数/回退的规则是否逐字一致；有没有一个测试把两边放一起比。
- **计数单位与选择单位**：门槛按什么数（条目/prediction/文件/成功打开），后面的选择按什么取。
- **多副本身份**：同一物理对象导出多份（多源模板、多 MIMO 路径、多设备模板）时选择规则
  以哪份为准，其它副本的计划去了哪。
- **回退语义**：失败时报"没有"、"零"还是"上一次的值"；fail open 还是 fail closed；
  两侧回退是否一致。
- **变量取值范围**：写 `false` 到 `[true,true]` 的变量；`ToDouble` 不看范围。
- **方向与制式**：上行/下行、TDD/FDD；headline 场景是不是只测了一个方向。
- **生命周期**：新缓存/快照谁释放、在哪些出口；键改成对象引用后生命周期是否匹配。
- **测试是否会红**：把修复精确还原，测试会红吗？夹具形状是不是产生缺陷的形状
  （全 0 索引、目录代替文件、断言不可能出现的子串）？是走产品入口还是直接调 helper？
- **描述里的验证数字**：说"338 个用例全过"的程序集有没有改过测试文件；没改就说明不了新行为。
- **注释对最终代码**：说反的、`<paramref>` 指向已改名参数的、cookbook 与校验器矛盾的。
- **编译外**：新文件 BOM + CRLF、16 行版权头；`public const` 跨程序集内联；`Equals` 无
  `IEquatable`/`GetHashCode`。

### 5. 定级

| 标记 | 含义 |
|---|---|
| 🔴 BLOCKER | 写坏用户数据、删用户对象、提交明确错误的结果 |
| 🟠 CRITICAL | 错误答案或安全网失效，但不写坏数据；报表与计算不一致 |
| 🟡 MAJOR | 真问题影响有限；测试撤掉修复不会红；文档与代码矛盾且被模型/用户直接读 |
| 🔵 MINOR | 措辞、注释漂移、产品不可达的陷阱、纯 API 洁癖 |

潜在（无调用方）、产品不可达、历史遗留：**降级并明说**。标高了作者会全修，改动面一大
下一轮更多。

### 6. 发评论

每条 inline 线程的格式（团队已用的样式）：

```
**🟠 CRITICAL — 一句话说清缺陷。**

**Evidence.** file:line 引用代码，说明两处如何不一致。

**Failure scenario.** 具体输入 → 具体错误输出（数值）。

**Fix.** 最小修法；需要的测试一句话。
```

```
python scripts/ado_pr.py post <prId> threads.json --dry   # 先看锚点和长度
python scripts/ado_pr.py post <prId> threads.json
```

`threads.json`：`[{"file": "/iBuilding/...cs", "line": 44, "content": "..."}, {"file": null, "content": "summary"}]`。
文件路径以 `/` 开头、相对仓库根，行号是右侧（新）文件的行号。

### 7. 总结线程

```
## Review summary
**Verdict: approve / request changes.** N CRITICAL · N MAJOR · N MINOR；已有线程 X、Y 仍然成立不重复。
Reviewed against merge base <sha>, all N files, with the callers behind them: <关键调用方>.
| # | Severity | Finding | Where |
**Checked and sound.** 核过没问题的点（additive 改动、夹紧推理、容差共用、生命周期、pin 一致、BOM）。
**Order.** 建议修复顺序，哪条的测试顺便补了哪个缺口。
```

"Checked and sound" 不是客套：它告诉作者哪些不用再自证，也让下一轮评审不重复核。

### 8. 再审（第二轮及以后）

- 先核作者说"已修"的每一条是真修了还是只改了那一行：修复改动了哪个约束、谁还依赖旧行为。
- 上一轮修复带进来的新缺陷单独标出（"consequences of this round's own fix"）。
- 用 `scripts/ado_pr.py fetch` 看已回复状态，只对新东西开线程；作者的回复用
  `scripts/ado_pr.py reply` 批量发。

## 陷阱（每条对应一次真实事故）

- 只读 diff 不读调用者：报表侧用跳线自己的链路选、计算侧用主缆的范围读，两边都在 diff 外相遇。
- 相信描述里的"X 也这么做"：描述说 API 按 prediction 计数，代码按条目计数，方向正好相反。
- 把潜在问题标成 MAJOR：`Equals` 没有调用方却标 MAJOR，作者花一轮加固一个该删的方法。
- 发现没核就发：第一条评论 14 分钟后自己纠正，可信度是评审唯一的资产。

## 支持资源

- `scripts/ado_pr.py`：`fetch` / `post` / `reply`，PAT 与组织地址见文件头。
- `pr-self-review`：同一套眼光用在自己的 PR 上，以及收到评论后怎么分档、怎么修不越界。
