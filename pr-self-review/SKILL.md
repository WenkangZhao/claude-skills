---
name: pr-self-review
description: >-
  Use before pushing any PR or any round of review fixes, and whenever the user asks "why
  did the reviewer find this and we did not" or "which comments are real". Reviews the
  WHOLE diff against the merge base the way an external senior reviewer does - consequences
  in files you never touched, tests that stay green when the fix is reverted, comments that
  contradict the final code, invariants a fix quietly changed - and produces a findings
  table with severities instead of a feeling of readiness. Also governs how to fix review
  comments without breeding the next round: triage into four tiers, minimal change, no
  "longer-term" suggestions, reply-and-decline explicitly. Make sure to use this even when
  the user only says "push it" or "fix the comments".
---

# 像外部评审一样审自己的 PR

## 什么时候用 / 什么时候不用

- 用：推 PR 之前；推任何一轮"修评审意见"之前（修评审意见产生的代码同样是新代码）；
  用户问"为什么又这么多 comment"、"哪些是真问题"的时候。
- 不用：审别人的 PR（用 `pr-review`，它多了拉取和回帖）；只改了一行文案且没有读者依赖它。

## 为什么我们自己总发现不了

三个 PR、九轮外部评审，每轮 20–30 条，几乎没有一条是事实错误。回头看，漏掉的从来不是
"写错的那一行"，而是下面六件事。自审就是把这六件事逐一做成动作。

| 我们做的 | 评审做的 | 结果 |
|---|---|---|
| 看自己改过的文件 | 看整个 diff 对 merge base 的**后果**：谁读这个值、谁依赖旧行为 | 依赖方在没动过的文件里，全漏 |
| 测自己刚写的修复（直接调 helper、最简夹具） | 问"把修复那几行撤掉，哪个测试会红"、"夹具有没有产生缺陷的那个形状" | 我们的测试撤掉修复照样绿 |
| 用写代码的那双眼看自己写的注释 | 拿注释对最终代码逐句核 | 注释说反的、单位写错的，全漏 |
| 绿了就停 | 从"什么必须成立"出发，找它不成立的地方 | 隐含约束被改掉没人知道 |
| 对着评论指的那一行打补丁 | 问这个补丁改变了哪个约束、还有谁靠着它 | 每轮修复带进下一轮 1/3 的评论 |
| 所有评论一视同仁全修 | 分级；潜在/不可达/措辞的记录不改 | 改动面越大，下一轮越多 |

一句话：**我们验证的是自己设计的行为；评审检查的是我们没设计的部分。**

## 步骤

### 0. 先冻结范围

写下这轮允许改什么。修评审意见时只修评论点名的缺陷，用能保住约束的最小改动。不做
"顺手重构"、不加日志通道、不加选项、不接受评审的"长远建议"。**删掉**没人用的代码可以
（那是减法）。范围外的东西回复说明并开 follow-up，不默默不动：默默不动下一轮还会出现。

### 1. 拿到完整 diff，不是你记得的改动

```
git fetch origin <target>
git merge-base HEAD origin/<target>          # 记下 merge base
git diff --stat <base>..HEAD
git diff <base>..HEAD -- <file>              # 逐文件读，包括测试、文档、csproj、cookbook
```

读的是 diff 加上它周围的调用者，不是脑子里的改动清单。上一轮改过的文件这轮也要重读：
上一轮修复带进来的缺陷就在那里。

### 2. 对每处行为改动做"依赖方枚举"

对 diff 里每一个改变了含义的值、标志、计数单位、开关、键：

```
grep -rn "<名字>" --include=*.cs --include=*.md .    # 所有读者，包括测试和文档
```

对每个读者写一句"新含义对它意味着什么"。要找的是**两个读者极性相反**（一个按条目数、
一个按 prediction 数；一个假设组内 cell 全开、一个允许单个关）。这一步找到的是 BLOCKER。

### 3. 约束句

每处修复先写一句约束："组内只要有一个 cell 激活，`Included` 必为真"、"报表显示的损耗和
计算提交的损耗是同一个数"。然后：

- grep 这句话涉及的每个代码点，确认每个点都保持它；
- 两个代码点必须一致的地方，加一个让不一致**发声**的东西（assert / throw / 类型），
  不是靴子里的注释。

### 4. 每个测试问三句

1. 把修复那几行精确还原，这个测试会红吗？会才算钉住。用 `mutation-verify` 跑，别凭感觉。
2. 夹具的形状是产生缺陷的形状吗？`source_template_index` 全是 0、`arrays.npz` 建成目录、
   断言一个不可能出现的子串，这些测试永远绿。
3. 它走的是产品入口还是你刚抽出来的 helper？只测 helper 的测试测不到接线。

### 5. 注释和文档对最终代码逐句核

改完代码后重读这轮**碰过的每条注释、doc、cookbook、README**，对着最终代码问"这句现在
还是真的吗"。特别查：

- 说"X 也这么做"的句子（"the unit the Command API counts in"）：去 X 那里看一眼；
- 描述回退/跳过行为的句子（"skips any row already populated"）；
- `<paramref>`、`<see cref>` 指向已改名的东西；
- 文档里的范围、默认值和校验器是否一致（cookbook 说 0–100，校验器要求 ≥1）。

### 6. 维护类扫描（变异测试到不了的维度）

- **生命周期**：每个新建或增长的对象（缓存、快照、预载列表），谁在哪些出口释放（成功、
  取消、抛出、从未开始）。
- **回退语义**：每个 fallback 在失败时报的是"没有"、"零"还是"上一次的值"；报表和计算
  两侧的回退是否同一个。
- **同一件事的两份实现**（报表 vs 计算、API vs 路由、包内 vs 包外）：有没有一个测试把
  两边的答案放在一起比。
- **多副本身份**：同一物理对象导出多份（多源模板、多 MIMO 路径）时，选择规则以哪一份
  为准，另一份的计划落到哪里。
- **方向与制式**：上行/下行、TDD/FDD 是否都有用例；headline 场景是不是只测了一个方向。
- **可观测性**：新缓存、新阈值、新拒绝有没有一行日志或计数说明它起了作用、代价多少。
- **编译外的一致性**：BOM + CRLF、16 行版权头、`InternalsVisibleTo`、每个动过的程序集
  的测试都跑过（`git diff --name-only` 按程序集分组）。

### 7. 产出：一张评审表，不是一句"我检查过了"

| # | 严重度 | 发现 | 位置 |
|---|---|---|---|
| 1 | 🔴 BLOCKER | 会写坏用户数据 / 删用户对象 / 提交错误结果 | file:line |
| 2 | 🟠 CRITICAL | 错误答案但不写坏数据；安全网失效 | |
| 3 | 🟡 MAJOR | 真问题但影响有限；测试撤掉修复不红 | |
| 4 | 🔵 MINOR | 文案、注释、命名、不可达路径 | |

每条带：证据（file:line，引用代码）、失败场景（具体输入 → 具体错误输出）、修法。
写不出失败场景的不是发现。表里没有条目再推。

## 收到评审意见之后

1. **逐条核实**，对着代码不对着描述。评审也会错，但要用证据反驳，不用感觉。
2. **分四档**：
   - 一档：写坏数据/错误答案 → 修；
   - 二档：真问题、影响有限、十行以内 → 修；
   - 三档：撤掉修复不会红的测试 → 修钉住一档的那几条，其余 follow-up；
   - 四档：潜在（无调用方）、产品不可达、纯措辞、历史遗留 → 回复原因 + follow-up，不改代码。
     没人用的方法评审要求加固时，**删掉**比加固对。
3. **每个修复先红再绿**：先写会红的端到端测试并亲眼看它红，再改代码。
4. **修完跑第 2、5、6 步**：修复改了哪个约束，谁还靠着它，注释还对不对。
5. **和评审约定合并线**：BLOCKER/CRITICAL 清零，MAJOR 修或挂工作项，MINOR/NIT 作者裁量。
   不约定，全量重读永远能产出十条 MINOR。
6. **回复每一条**：修了的说改在哪、哪个测试钉住；没修的说为什么和 follow-up 编号。
   用 `pr-review` 的 `scripts/ado_pr.py reply` 批量回。

## 陷阱（每条对应一次真实事故）

- 给每个 cell 加独立开关修了一条 CRITICAL，却打破了"组启用则所有 cell 都开"这个没写出来的
  约束，三处依赖它的代码没跟着改：1 BLOCKER + 2 CRITICAL，会删用户已有的 AP。
- 把 KPI 计数改成按 prediction 算，选择逻辑还是取第一条，而且注释说"API 也按 prediction 数"
  是错的：两条准则的 prediction 被放行，只优化了一条。
- 修复和测试一起写、只跑一次绿：夹具全是 `source_template_index = 0`，缺陷的形状根本没进测试。
- `Assert.Catch<Exception>` 之后写 `outcome == null ||`：永远真的断言。
- 把 `arrays.npz` 建成目录来"制造失败"：`File.Exists` 对目录为假，回滚路径从未进入。
- 评审标 MAJOR 的 `Equals` 没有任何调用方：加固它是扩展，删掉它才是修复。

## 相关

- `mutation-verify`：第 4 步的执行工具。
- `pr-review`：同一套眼光用在别人的 PR 上，含 ADO 拉取/回帖脚本。
