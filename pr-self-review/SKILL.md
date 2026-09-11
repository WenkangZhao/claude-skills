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
- **说"某个门/夹具覆盖了 X"的句子**：打开那个门的 csproj / 配置看它到底跑在哪个目标上。
  "parity gates run the same fixtures against both targets"——DiffAcoParity 只有 `net8.0`。
- **说"生产环境走的是 Y 不是 X"的句子**：集成之后重读。README 写"production sidesteps
  AntennaLookup"时适配器还没接进来，接进来之后 `DiffAcoAdapter` 就在 new AntennaLookup。
- **让 agent "先问用户再做"的指令**：surface 上必须有一个字段能判断那个条件。"Ask the user
  before promoting if the project has one"——DTO 里没有任何字段区分向导自己的配置和脚本建的。

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
- **发布点之后的折叠**：gate 脚本 / 报表里每个 `Output(outcome)`、`Publish`、`Save` 之后
  还有没有往 outcome 里折叠的检查。往脚本里追加检查时先找发布点，追加在它上面；同目录
  兄弟脚本的顺序就是规范（`run-and-apply-optimisation.cs` 对，`list-optimisation-configs.cs` 错）。
- **同一个值的第二份字段**：`Route2iSinrInputs.NoiseFloorDbm` 与 `SinrHead` 里的 floor。
  信号是"默认值恰好等于刚删掉的硬编码常量（-95）"。修法是删掉第二份、从持有者读，不是加校验。
- **循环体里不依赖循环变量的重算**：闭包每次迭代调用、但只依赖外层状态的表（ChannelSweep
  的 G 只依赖 rsrp/universe/active）。提出去按 key 缓存，缓存要有上界，并说明是部分缓解。
- **并行数组的长度守卫**：按 stride 索引的数组（`allowed[cell * channels + v]`）错长度不会越界、
  只会静默读到别的行；入口处按 `cells * nChannels` 校验，测试用错一格的长度。
- **配置里的 `0` 有两种读法，实现必须挑一个、并让另一种读法不成立**。`interval_s: 0` 是
  "立刻看一次"，`heartbeat_s: 0` 是"不要心跳"——两个 0 意思相反。没写守卫时它们都会滑向
  "无限"那一侧：`0 * 1.5` 永远是 0，退避再也长不起来；`elapsed - last_said >= 0` 每一拍都真，
  本来用来关掉播报的设置反而让它每拍都播。**形状**：凡是 0 会进乘法或进 `>=` 比较的配置项，
  都要问一遍"这个 0 读成哪一种"，并让另一种在代码里显式不成立。
- **只在构造函数里赋值的字段**：`grep -n "_name = "` 对比读取次数；`_cells` 这类编译器不报。
- **宽泛的 `except Exception`**：看被吞掉的类型里有没有上游刻意设为致命的（`DomainScopeError`），
  只捕获"尚未生成"那一类。
- **删凭据文件时 grep 同一个值**：`.nuget/NuGet.Config` 删了，`ContinuousIntegration/NuGet.Config`
  还带同一个 key 和 PAT；注释里"不把秘密写回仓库"就成了假话。跨系统的那份回复说明 + 记 owner 动作。
- **场景元数据的跨域副作用**：`scenarios.yaml` 的 `commands:` 列表决定它进哪个域的 pass；
  把顺带的读命令声明上去会把优化场景算进 Annotation 的 N。
- **手拼 JSON 的两半**：转义之外还有**数字格式**。`ToString("F2")` 走当前区域设置，
  逗号小数（de/fr/es/pt/ru）直接让整个信封不是合法 JSON，下游解析失败、`data` 为空。
  凡是手拼 JSON 的文件，`grep 'ToString("F'` 和 `grep 'J('` 要一起做。
- **同一个结论算两遍**：一处给人看、一处喂给不可逆操作（`best_job_id` → apply）。
  提上去算一次、两处读，并且测试断言"只算了一次"（`body.count(...) == 1`）。
- **"公共前缀相等"不是"相等"**：会把超集判成同集，而且结果依赖元素顺序。
- **空 `catch {}`**：把"读失败"变成"没有"，而后者往往是**建议**，会把用户支使去做
  已经做过的事。至少把 `ex.Message` 记进一个 `unreadable` 列表并在输出里区分两者。
- **精确匹配 `return` 第一个命中**：歧义分支永远走不到。收集全部再判断。
- **生成物的源在别的仓库**：cookbook/corpus 这类要改在源仓库，否则下次重新生成就没了；
  源分支受保护时单独开 PR，并让下游的 stamp 指向那个已推送的提交。

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
   - **先确认评论引用的代码存在**。`grep` 评论里的那个字符串，不是看行号。评审（尤其是
     AI 评审）会引用一段本分支根本没有的代码：58258 的 timeout 那条给出了一个 `"observation":`
     字典和 `timeout_s:.0f`，而 `grep -n '"observation"'` 在 `orchestrator.py` 只有另外两处
     无关的命中。这时**修意图、不照抄建议**——它给的替换文案是写给用户看的，实际那段字符串是
     给模型读的，照抄反而更弱——回复里用 grep 结果说明，并贴出真正在跑的那几行。
   - **评审给的机制解释也要核**，因为机制决定修法。"零 interval 会 busy-spin 把 CPU 跑满"是错的：
     每一轮都 `await` 了一次客户端往返，上限是宿主的响应时间。真正的代价是每次轮询都让宿主在 UI
     线程上重新编译一次状态脚本——认清这一点，floor 就该加在**退避的乘法**上而不是第一次 sleep 上。
   - **查可达性要追到数据通道**，不是"看起来能配"。`poll` 块能不能由用户自建工具传进来，答案在
     `registry.py` 的 `ToolRecord.from_dict` 里：它逐字段列举，没有 `poll`，所以只有仓库内
     `tool_defs.py` 能设，而两处都是 `5 / 20 / 900`。→ 四档（产品不可达），但**照修**：
     下一个 `poll` 块一定是复制这两个之一写出来的，把陷阱留在原地等于留给下一个人。
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

## 第 8 步：改完之后，预演下一轮评审

改完不是结束。对每处改动，用评审的眼光问三个问题，把答案写下来再推：

1. **这个改动保住的约束，还有哪些地方共享它？** grep 出全部，不是评论点到的那一处。
   同名解析改了 `OpenConfig`，就要看复用循环、列表、拒绝文案、cookbook；上行判定改了分类器，
   就要看它的输入在哪一步被折叠、宿主有没有现成的清单。
2. **这个改动引入了什么新分支？** 每个"兜底/补救"分支都要问：它在没有折叠目标时做的是什么？
   "全关则全开"其实是在换设备。凡是补救分支，优先改成拒绝。
3. **布尔表达式改了，真值表写了没？** 把 `A || B` 改成兜底时，要同时问"否定断言会不会漏过"
   和"肯定断言会不会被骗过"。oracle 的 `IsNamedFile || Read...Named` 修了一个方向，打开了另一个。

再加两条硬规则：
- **找宿主的权威，不要发明第四份规则**。上行类型的判断在代码库里已经有 `PredictionTypeExtensions.IsUplink`，
  resolver 里有一份字符串规则，我又在分类器里写了第三份，还是在名字被 `KindOf` 折叠之后判断的。
- **不接受"生产环境才生效"的分支**。评审建议 `max(0.5, interval) if not is_test_env else interval`：
  一条只在生产走的路径，就是测试覆盖不到的路径，而它恰恰是出事的那条。把修复做成两边同一条路
  （floor 加在退避上，第一次 sleep 仍然尊重 0），测试跑的就是生产跑的。
- **测试驱动产品序列，不驱动自己搭的状态**。"同名优先创建副本"的测试直接 stub 出两份同名文件，
  没有走 `PromoteOptimisationConfigCommand`；第二条测试撤掉修复照样绿。改用真正的命令构造状态，
  再断言每个读者看到的东西。

## 陷阱（每条对应一次真实事故）

- 第 26 轮，23 条里 18 条是第 24 轮修复的后果，评审一句话概括：每个修复都改在评论指向的那一行，
  没有改在共享同一约束的兄弟位置。改 `OpenConfig` 漏了复用循环（CRITICAL）、列表（CRITICAL）、
  拒绝文案、cookbook；改 `SinrTuning` 漏了上一行的 `ChannelTuning`；改桌面默认漏了 200 行外的
  注释和 RF cache 提示；把 DTO 事实搬进 summary 把互相矛盾的两句一起送进了提示词。
- 跨模板"折叠"是为了让约束成立而发明的机制：它漏了同样按键控的频道，漏了站点开关，
  "全关则全开"会把 A 设备装到路由选了 B 的位置。正确答案是让向量提交路由选的那个模板，
  折叠、补救、空名匹配三个问题一起消失。
- 上行判定写在 `Classify` 里，而 `KindOf` 已经把 `NRSRSRSRP` 折成了 `"rsrp"`：读到了折叠代码，
  仍然在折叠后判断。"按构造显然"的测试没有一条用真实枚举值驱动。
- 给每个 cell 加独立开关修了一条 CRITICAL，却打破了"组启用则所有 cell 都开"这个没写出来的
  约束，三处依赖它的代码没跟着改：1 BLOCKER + 2 CRITICAL，会删用户已有的 AP。
- 把 KPI 计数改成按 prediction 算，选择逻辑还是取第一条，而且注释说"API 也按 prediction 数"
  是错的：两条准则的 prediction 被放行，只优化了一条。
- 修复和测试一起写、只跑一次绿：夹具全是 `source_template_index = 0`，缺陷的形状根本没进测试。
- `Assert.Catch<Exception>` 之后写 `outcome == null ||`：永远真的断言。
- 把 `arrays.npz` 建成目录来"制造失败"：`File.Exists` 对目录为假，回滚路径从未进入。
- 评审标 MAJOR 的 `Equals` 没有任何调用方：加固它是扩展，删掉它才是修复。
- Bing Xia 轮（12 条）里两条是前几轮修复带出来的：往 gate 脚本追加检查时没找发布点，五个
  检查折叠在 `Output(outcome)` 之后，域里唯一的 Correctness gate 五个断言失败也报 PASS
  （BLOCKER）；上一轮给 promote 加的"项目已有配置就先问"是一句 surface 上无法判断的指令。
  两条的共同点：改的是文本（脚本尾部、doc 里的一句话），没有回头看这段文本依赖的机制。
- 同一轮，评审引用 README 说"production 走 AntennaPatternInterpolator"要我照抄进注释：
  去代码里核，`DiffAcoAdapter.cs:305` 在 new AntennaLookup。评审也会被过时文档带偏，改注释
  前先 grep 代码，再把 README 一起改，否则下一轮就是"注释和 README 矛盾"。
- 评审引用了一段不存在的代码（58258 的 timeout 那条），如果照着"改"就会去改一个没有的地方，
  或者把现有文案换成更差的一版。三十秒的 `grep` 能挡住整轮返工。
- 修复脚本用 bash heredoc 写 Python 时 `\\n` 被解成真换行、`'` 让 heredoc 提前结束：多行
  文件用 Write 工具，不用 heredoc。

## 相关

- `mutation-verify`：第 4 步的执行工具。
- `pr-review`：同一套眼光用在别人的 PR 上，含 ADO 拉取/回帖脚本。
