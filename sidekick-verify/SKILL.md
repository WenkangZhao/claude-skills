---
name: sidekick-verify
description: >-
  Use when a change in the Sidekick stack has to be proven rather than assumed:
  "验证一下这个改动", "这个改完要跑什么测试", "怎么测", before pushing or updating a PR in
  pleiades-ms-ai-orchestrator / -tool-engine / -code-engine, after editing a tool body, a
  skill record, the docs corpus, a cookbook part or the Command API itself, and whenever a
  coverage claim is about to be written into a PR description. Picks the cheapest layer
  that can actually prove the claim - unit tests, the contract linter, the two C# compile
  gates, the live-app sdk-test gate, the local code engine, or a recorded session replay -
  gives the exact command, and says what a green result does and does not mean. Use it even
  when the change looks trivial: the layer that would catch it is usually not the cheap one.
---

# 验证 Sidekick 的改动：先选层，再跑命令

## 什么时候用 / 什么时候不用

- 用：改了 Sidekick 四个仓库（orchestrator / tool-engine / code-engine / iBuildNet 的
  Command API 与语料）里的任何东西，要在推 PR 前证明它；要往 PR 描述里写"某某被覆盖了"。
- 不用：只改了注释或文档且没有读者依赖它（说清楚跳过原因即可）；要证明"撤掉修复测试会红"
  用 `mutation-verify`；要审 diff 用 `pr-self-review`。

## 一句话的取舍

四层像体检：抽血（秒级单测）→ 拍片（不开机的静态合同检查）→ 试装（零件能不能装进真机）
→ 上机路试（真应用真工程跑一圈）。越往下越慢越真。**别越级**（改了脚本体只跑 Python 单测
等于没测），**也别跳级**（为一个参数拼写错误开应用是浪费半小时）。

## 第 0 步：先查这台机器能跑到第几层

```
python scripts/verify_env.py            # 秒级
python scripts/verify_env.py --collect  # 顺便数一遍每个服务的用例数
```

它最后一行直接给出"这台机器现在能跑到第几层"。其中最值钱的一项是 `driver.json`：它不只看
文件在不在，还**真去连那个端口**，所以能区分 LIVE 和 STALE——上周留下的那份文件和活着的
应用长得一模一样，直到连接被拒。第 3、4 层缺东西时**会 skip 而不是 fail**，不先查就跑很容易
把"跳过了"当成"过了"。

## 改了什么跑什么

| 改动 | 跑这些 | 最低必须到第几层 |
|---|---|---|
| orchestrator 的循环 / 策略 / 记忆 / 会话 | 对应的 `tests/test_*.py`；行为改了就再录一条轨迹 replay | 1（+replay） |
| 工具定义、skill、参数、`consumes` | `test_tool_contracts.py` + `test_tool_registry.py` | 2 |
| `tool_bodies/*.cs` | ScriptGate（或 compile-check）+ `sdk-test --domain <对应域>` | 3，写操作到 4 |
| 语料 / cookbook / XML 注释 | `local_code_engine/ask.py`；要数字才 `eval/loop.py` | 4 |
| Command API 本身 | `sdk-test --domain` + `eval/preflight_only.py` | 4 |
| code-engine 提示词 / 结构化输出 | code-engine 的 pytest | 1 |

## 第 1 层 · 纯 Python 单测（几秒，什么都不用准备）

三个服务各自带 venv。**必须用仓库自己的 `.venv\Scripts\python.exe`**，系统 Python 里没有
pytest。

```
cd <repos>\pleiades-ms-ai-orchestrator
.venv\Scripts\python.exe -m pytest tests -q
.venv\Scripts\python.exe -m pytest tests/test_poll_client_job.py -q    # 只跑相关的

cd <repos>\pleiades-ms-ai-tool-engine
.venv\Scripts\python.exe -m pytest tests -q

cd <repos>\pleiades-ms-ai-code-engine
.venv\Scripts\python.exe -m pytest tests -q
```

规矩是**只跑受影响的文件或程序集**，不是每次全量——全量扫会把所有人训练成跳过这一步。

## 第 2 层 · 合同静态检查（不用应用，不用 key）

`tool-engine/validator.py` 按元数据 lint 每一条 ToolRecord，不认名字，所以现在和将来的工具
都被覆盖。它抓的是那类**运行时才炸、甚至静默失败**的错：`consumes` 少一个字母，附件悄悄
丢了；skill 的 `tools:` 拼错，pin 阶段跳过，playbook 跑到一半断掉。

```
cd <repos>\pleiades-ms-ai-tool-engine
.venv\Scripts\python.exe -m pytest tests/test_tool_contracts.py -q
.venv\Scripts\python.exe -m pytest tests/test_tool_registry.py -q
```

同一个 linter 还挂在 `registry.save()`（error 级别直接拒绝保存用户自建工具）和 LLM 写工具的
自纠正回路上，所以这里绿基本等于线上也过。

## 第 3 层 · C# 编译门（要 iBuildNet 的 Debug 产物，不用开应用）

`tool_bodies/*.cs` 是 Sidekick 真正执行的东西，两道门：

| 门 | 是什么 | 命令 |
|---|---|---|
| `tools/csbody-compile-check` | **仿照**宿主的 Roslyn 门（包装模板、引用集、AUTO001 允许名单三件事是复制过来的，会漂移） | `pytest tests/test_csharp_bodies_compile.py -v` |
| `tools/ScriptGate` | **就是**宿主——从 Ranplan 构建里加载内部的 `ScriptCompiler`，不会漂移 | 先 `dotnet build tools/ScriptGate`，再 `pytest tests/test_script_gate.py -v` |

有构建就优先信 ScriptGate；仿照那个的价值是把报错行号还原到 body 自己的坐标上。
优化相关的脚本体另有 `tests/test_optimisation_bodies_compile.py`。

DLL 的找法是 `RANPLAN_COMMAND_API_DLL` → `IBUILDNET_ROOT` → 任何**并排**摆着、有
`iBuilding/iBuilding.UI/bin/Debug` 结构的目录（按构建布局匹配，不按文件夹名）。找不到就
退出 2、测试如实 skip。

## 第 4 层 · 真应用（开着 iBuildNet，带检测许可）

一次性前提：`iBuilding_2010.sln` 建 Debug（DriverServer 已是原生项目，没有单独部署步骤），
用 `--devlicense=auto` 启动应用并打开工程。应用**启动时**在 exe 旁边写 `driver.json`
（host/port/token），下面所有工具都靠它找路。

**A. `sdk-test` — 唯一的硬正确性信号。** 脚本在真应用里跑，再由独立的 Plugin-SDK oracle
判对错，所以能区分"跑挂了"（GATE FAIL）和"跑完了但答案不对"（INCORRECT）。

```
dotnet build StandaloneUtilities/Ranplan.SDK.Tools/Ranplan.SDK.Tools.slnx -c Debug
sdk-test list --domain Bsm                                  # 先看选中了什么，不执行
sdk-test run --attach --domain Workspace --format table
```

不加 `--domain` 就是 Command-API 门 = Bsm + NetworkModeling + Workspace。**按域跑，别整套
扫**：一个 `PluginSDK/` 脚本弄脏共享状态会连累后面所有不相干的脚本。退出码 0 全过 / 1 有
失败 / 2 参数错或选空了。`--launch` 要用仓库里那份 baseline 工程
（`TestSuite\BaselineProjects\Project12\Project12.ibpx`），别指向个人副本——每台机器对着
同一个文件，一行结果才在哪里都是同一个意思。

**B. `eval/preflight_only.py` — 零模型调用的 checker 编译门。**

```
python -m eval.preflight_only --domain Optimisation --project "<绝对路径>\eval\fixtures\Project12.ibpx"
```

把每个 checker 和一个空操作拼起来跑一遍，抓三件事：编译不过的、抛异常的、以及**对着没动过
的工程也报 `Correct = true` 的写 checker**（那种 checker 什么都没测）。它测不到的另一半是
"这个 checker 到底能不能 PASS"——两个方向都失败看起来和真实的可编写性缺口一模一样，所以新
checker 要手写一个正确动作让它绿过一次再信它。

**C. `local_code_engine` — 改语料/文档后最快的验证。**

```
cd StandaloneUtilities\Ranplan.SDK.Tools\local_code_engine
python ask.py "把 3 楼所有天线列出来" --run          # 生成 C# 并在运行中的应用里执行
python ask.py --fix bad.cs --error "CS0246: ..." --run   # 修复模式，验证报错回路
python serve.py                                      # 让自己那台 iBuildNet 的聊天面板连本机
python sync_engine.py                                # 确认本地这份引擎没落后于线上
```

省掉"发语料 → 部署 → 独占共享环境"那一圈。注意只有 **Automation 模式**走 code engine，
Auto 模式走 orchestrator。

**D. `eval/loop.py` — 整域就绪度（最贵，要 Gemini key）。** 五步：sdk-test 正确性 → 重生成
AiDocs 语料 → preflight → LLM 照语料重写同样的场景 → 合成报告。`docs_only` 与
`docs_cookbook` 的差值就是 cookbook 增益。只在要评估文档质量时才动它。

## Replay：orchestrator 最强的回归工具

把一次真实会话的事件日志（模型回复、浏览器回帧、每个下游服务的应答）喂回**真正的 autopilot
循环**——循环、hook、校验、派发、记忆全部真跑——再把回放出的日志和录制的对比。同一份提交进
仓库的日志既是输入又是期望输出。

```
python scripts/replay_session.py --session <id> --url %SIDEKICK_BASE_URL% --save tests/data/trajectories/<name>.jsonl
python scripts/replay_session.py --fixture tests/data/trajectories/<name>.jsonl
```

退出 0 = 复现；1 = 发散并打印差异。不要 LLM、不要引擎、不要 key。
已知限制：按墙钟预算停下来的会话回放不了（回放是瞬时的），会在那一轮发散。

## 绿了代表什么，不代表什么

这一节是这个技能存在的理由——**每一层的绿都有明确的边界，写进 PR 描述前先对一遍**：

- 第 1 层绿：Python 侧的接线对。**不代表**脚本体能编译，更不代表它在真工程上做对了事。
- 第 2 层绿：工具元数据自洽。**不代表**工具真能跑通。
- 第 3 层绿：脚本体能编译、没碰禁用符号。**不代表**它的查询/写入是对的。
- 第 4 层 `sdk-test` 绿：真应用上跑了且 oracle 同意。这是唯一能写"验证过"的信号。
- CI 绿：**第 3、4 层在 CI 上是 skip 不是 fail**（Linux agent 没有 net472 targeting pack，
  也没有 iBuildNet 构建）。CI 绿完全不代表脚本体编译得过。

## 陷阱（每条对应一次真实事故）

- **那批 compile 测试整片红，十有八九是 `bin/Debug` 的 SDK DLL 过期**，不是代码回归。
  单独重建一次 SDK.Api 再看。
- **`driver.json` 是应用启动时写的，不是构建时。** 应用没开、或开的是另一个 worktree 的
  构建，工具就连到过期的那份。`ask.py` 会拿写入时间戳提醒你，`sdk-test --attach` 直接退
  出 2。要挂到别的构建就设 `IBUILDNET_EXE`。
- **没有任何流水线跑 `sdk-test`。** 原来那条 `azure-pipelines-sdk-tools.yml` 从没启用过
  （`trigger: none`），已在 `5c4c34e763d` 删掉。第 3、4 层全靠人手动跑，红了没人替你发现。
- **`PluginSDK` 域不在默认选择里**，而且今天没有任何东西覆盖它——那批脚本驱动的是 legacy
  live-graph 而不是 Command API，还各自假设一份全新夹具（要 `--fixtures-dir`）。
- **preflight 是拿五小时换来的**：有一次整个 Annotation pass "测出" 12% 可编写率，其实是
  所有写 checker 都没编译过，烧了六把 API key 才有人发现。跳过 preflight 省的那几秒不值。
- **`sdk-test` 跑完屏幕上看不到结果是正常的**：门脚本必须把共享工程复原，多数会
  `RevertLastRun` 或声明 `harness:reopen-after`；oracle 在结果还在的时候已经检查过了。
  但 `reopen-after` 会**丢弃附着应用里未保存的工作**，先存盘或挂到一份废弃副本上。
- **`sdk-test list` 用的是和 `run` 一样的过滤器**，不是整个目录。找不到某个脚本先加
  `--domain PluginSDK` 或 `--name`。

## 支持资源

- `scripts/verify_env.py`：一条命令报出这台机器能跑到第几层。
- 各仓库自带的权威文档，改动涉及时直接读，不要凭这份摘要动手：
  `tool-engine/tools/csbody-compile-check/README.md`（两道门的区别与 DLL 解析）、
  `Ranplan.SDK.Tools/Ranplan.SDK.TestRunner/README.md`（全部选项与退出码）、
  `Ranplan.SDK.Tools/eval/README.md`（五步 pass 的跑法）、
  `Ranplan.SDK.Tools/local_code_engine/README.md`（key 的六种给法）、
  `orchestrator/replay.py` 的模块 docstring（对比覆盖什么、忽略什么）。

## 相关

- `mutation-verify`：证明"撤掉修复测试会红"，第 1 层之上的那一步。
- `pr-self-review`：推 PR 前读自己的 diff；这个技能回答的是"读完之后跑什么"。
