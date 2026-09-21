# 分层与放置(评审桌面版/限界上下文时判"这算不算泄漏")

审 `iBuilding.UI` / `iBuilding.BLL` / `*.Domain` / `*.Persistence` 这类改动时读这一份。
判断一个新公共类型放对没有、一个新引用算不算泄漏。

## 一眼看完

- **"哪个上下文拥有这个概念"排在"哪一层"前面。**
- 外部消费方只绑 `*.Application.Contracts` 和 `*.Domain.Shared`。**绝不绑 `*.Domain`。**
- `Domain.Shared` 是依赖轻的原语 **加上宿主实现的 port**。**不放任何带业务行为的东西。**
- **程序集不等于命名空间。** 只有文件所在的项目才说明它在哪个程序集。
- Application **绝不**依赖 Persistence。组合根负责接具体实现。
- **放一个新公共类型之前,先枚举它的消费方。**
- 发明一个 port 之前,先查聚合是不是已经带着那份数据。

---

## 限界上下文与程序集

上下文:**Prediction、Measurement、WSM、Network、Cellular Optimization、Layout**。

| 程序集 | 角色 |
|---|---|
| `*.Domain` | 聚合、实体、值对象、仓储接口、领域服务、计算器 |
| `*.Domain.Shared` | 依赖轻的原语,**加上宿主实现的 port** |
| `*.Application` | 用例编排 |
| `*.Application.Contracts` | **只有**接口和 DTO |
| `*.Persistence` | 仓储实现、类型化行、mapper |
| `iBuilding.BLL`、`iBuilding.UI` | **外部消费方。只能用 Contracts 和 Domain.Shared。** |

> **`iBuilding.BLL` 绝不引用 `*.Domain`。没有例外,永远。**
> 用户原话:*"no more exceptions and never assume there has more exceptions. never anti-pattern."*
> 以及 *"We spent a lot of effort to hide Domain from outside…"*

## 严格的外部消费规则

| 层 | 可以消费 |
|---|---|
| UI | Application.Contracts、Domain.Shared |
| 宿主 / 外部消费方 | Application.Contracts、Domain.Shared |
| Application | Domain、Domain.Shared、Application.Contracts |
| Domain | **只有** Domain.Shared |
| Persistence | Domain、Domain.Shared |
| 组合根 | 全部 |

外部消费方**绝不**引用聚合、仓储接口、上下文句柄、行类型、任何具体的 Persistence 类型。
一个用例需要领域数据时,**Application 面暴露一个返回 DTO 或共享值类型的方法**。
**那个方法不存在,那就是要补的缺口**——伸手进 Domain 不是答案。

Contracts 程序集**只有接口和 DTO,绝不放服务实现**。"要不要把实现 X 挪到 Contracts"的答案几乎总是
**不要**:给 Contracts 扩一个正确的接口,实现留在 Application。**发现自己在往 Contracts 搬实现,
通常意味着上游有分层违规。**

**字段镜像表列的"持久化形状的共享类型"**,即使放在共享程序集里也仍然是一股味道。标记待清理,不要扩大。

## 放一个新公共类型

新建一个公共类型、或者把一个类型放宽到 public 时,**第一步是枚举每一个会消费它的程序集**。然后放进
**引用图能覆盖全部消费方的最小那个程序集**。

| 类型形状 | 家 |
|---|---|
| 外部消费方看得见的值对象/record/DTO/标识符 | `Domain.Shared` |
| 聚合、聚合状态、只被 Domain 消费的仓储 port | `Domain` |
| 为外部调用方声明的服务接口或 DTO | `Application.Contracts` |
| 服务实现、领域 port 实现 | `Application` |
| 持久化实现、类型化行、hydration 扩展 | `Persistence` |

> **出事经过**:一个 record 第一次被放进 `Domain`。一个外部消费方用了它,于是被迫产生泄漏。正确的家
> 是共享程序集——**同一个命名空间,更小的程序集**。评审的指示写的是"把这个 record 引入 Domain",
> 被**照字面执行**了,没人先查引用图。
>
> **评审关于类型该住哪里的指示是"建议",要先对着分层规则核过再照做。**

## Port:谁实现,谁消费

- **宿主实现的 port 必须住在 `Domain.Shared`**,因为宿主只引用那一个程序集。**所以有些动词名的
  port 合法地待在那里**——把一个宿主实现的 port 报成泄漏,是在让作者去挪一个规则要求它留下的类型。
- **在上下文内部实现、只被 Application 或 Persistence 消费的 port**,是上下文内部的,放 `Domain`
  并标 `internal`。Domain 对 Application、Persistence 及其测试项目授了 `InternalsVisibleTo`,
  所以 internal 就够,**公共面增加为零**。

> **不要重复的错误**:一个上下文内部的 reader port 和它的工厂被**放进 `Domain.Shared` 并且是 public**,
> 原因是抄了兄弟的放置、并且被相同的命名空间骗了。

**程序集不等于命名空间,具体到这里**:`*.Domain.Shared` 和 `*.Domain` **都**把
`<RootNamespace>` 设成 `…Domain`,所以一个 `…Domain.Calculations.Ports` 的命名空间
**完全说明不了它在哪个程序集**。只有文件所在的项目能说明。

## 判泄漏之前先问三个问题

1. **谁实现、谁消费?**(宿主实现的 port 在 `Domain.Shared` 是合法的)
2. **消费方集合是什么?**(放进覆盖全部消费方的**最小**程序集)
3. **是不是移动?**(`git mv` 进共享程序集**也是一次放置决定**,和新文件一样判)

进入 `Domain.Shared` 的这几类是**泄漏**,即使外部消费方合法地引用那个程序集:
Persistence 或 Domain 实现的接口、动词很重的行为契约、仓储形状的类型。

## Persistence 和 Domain 正在走向 internal

长期目标是 `*.Persistence` 和 `*.Domain` 变成 internal,只通过更高层的 SDK 外观消费。
**今天往那两个项目加的任何公共面都是将来要还的债。**

**怎么用**:优先**直接往 Domain 接口上加方法**,而不是在 Persistence 新建公共扩展类——Domain 接口
方法是稳定的,Persistence 侧的扩展是临时面。BLL 需要从一个 Domain 接口导航到一个类型化的
Persistence 类型时,**优先在调用点内联 cast**,而不是新建一个公共 Persistence 扩展。

## 包白名单

`RanplanWireless.Sdk.CommonTypes` 是那个被广泛白名单化的横切库。

`*.Domain` 程序集**本身可以**带第三方依赖(它已经引用了引擎 SDK,给它加一个数值库是对的,不是违规)。
**"依赖轻"这个约束只属于 `Domain.Shared`。** 这一条被错误地泛化过一次。

## 过渡类型

外部消费方还需要、但已排期删除的 strangler-fig 类型,住在 `Domain.Shared` 里一个标记过的
`Transitional\` 目录,每个带一条 `<remarks>` 点名**删除它的那个任务**。

> 在这些标记里点名任务,是"代码里不写内部流程"那条规则的**唯一、用户明确授予的例外**。

## 发明 port 之前先查聚合

加一个视图或一个取外部数据的 port 之前,**先查聚合是不是已经带着它**——一组只读视图曾经正是因为这个
而属于过度设计,数据本来就在已 hydrate 的聚合上。

---

## 评审时怎么用这一份

1. diff 里**新增的 `.cs`** 在 `*.Domain/` 或 `*.Persistence/` 下 → 逐个顶层 public 类型当作
   放置候选。
2. 每个候选 **grep 类型名(全词)**,走到最近的外层 `.csproj`,**建出消费方集合**。命中太多就按目录
   收窄,**并在报告里说明收窄过**。
3. 对着上面的放置表判。
4. **新增的 `using`**:外部消费方文件里指向某个上下文 `Domain`/`Persistence` 命名空间的,是发现。
5. **新增的 `<ProjectReference>`** 指向 `*.Domain.csproj` / `*.Persistence.csproj` 的,是发现。

**这份判不了的**:引用闭包(一个消费项目的传递引用到底能不能真绑上那个 Domain 程序集)、合并继承来的
文件、以及"这个新文件是不是真的声明了顶层 public 类型"。**在报告里说出来,不要让它读起来像等价物。**

## 来源

`working-standard` 仓库 `memory/universal/architecture.md` + `memory/ranplan/rules/ddd.md`
(那边还有一个 pre-commit hook 和一份 `ddd-carveouts.json` 豁免清单,我们这边没有)。
