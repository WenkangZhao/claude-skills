# C# 房规(评审时"这算不算违规"的依据)

审桌面版(`iBuilding.UI` / `iBuilding.BLL` / `*.Domain` …)和其它 C# 仓库时读这一份。

**两个来源。** **房规**是这里的评审会挑的东西,两者冲突时房规赢。**公司规范**是已批准的文档,
可执行的条目带着章节号内联在下面。纯偏好、或者代码库明显已经走过去的,不收录。

> 这里只写"什么算违规"。**定级**(BLOCKER/CRITICAL/MAJOR/MINOR/NIT)按 `SKILL.md` 的校准表:
> 风格不一致通常是 MINOR,**除非项目已经把它确立成约定**——下面这些就是已确立的,所以它们是真发现,
> 不落进"项目没确立成约定的风格偏好,不要提"那一条。

## 一眼看完

- 每个控制流块都带大括号,**包括单行的 guard clause**。
- 单元测试**只用 `Assert.That`**,绝不用 FluentAssertions。
- 每个 `.cs` 都是 **UTF-8 带 BOM + CRLF**。Markdown / 脚本 / JSON **不带 BOM**。
- **绝不新增 `global using`。**
- 不要用类型自己所在限界上下文命名空间的某一段来给它命名。

---

## 1. 每个控制流块都带大括号

`if` / `else` / `for` / `foreach` / `while` 即使语言允许省略也要带,**单语句体和 guard clause 也要**。

```csharp
if (x == null)
{
    throw new ArgumentNullException(nameof(x));
}
```

**为什么**:公司规范 §2.2 *"Always use braces when optional"*,而且这里的评审**每次都挑**——
一轮里两个没括号的单行 `if`,下一轮一个 guard clause。

**怎么用**:**只对你自己写的那些行**要求,即使周围的 legacy 代码没带。**legacy 的单行不是照抄的
许可证**,但也不要为了这个去重排没动过的 legacy 行。

> 我们已有的相关记忆:`feedback_cs_block_formatting`(单行 `if (x) return;` 禁止,展开成两行 +
> 空行)——同一条规则的我们这边的措辞。

## 2. 单元测试只用 `Assert.That`

```csharp
Assert.That(x, Is.EqualTo(y));   // 不写 x.Should().Be(y)
```

**为什么**:团队约定,统一到约束模型上。**没有比"一致"更深的理由,所以它的作用域是我们自己的仓库。**
不是去重写一个已经用别的写法的第三方或继承来的项目的理由——**在哪个项目里就跟哪个项目已有的做法走**,
我们的仓库里用这条。

## 3. `.cs` 是 UTF-8 带 BOM + CRLF

> **永远。** 产品仓库里每个 `.cs` 都必须以 BOM 字节 `EF BB BF` 开头,并且用 CRLF。少任何一个,
> 编辑器打开时会报 *"The file was loaded in a wrong encoding: 'UTF-8'"*,然后有人手工去修。

**作用域只有 `.cs`。** 这些仓库里的 Markdown / 脚本 / JSON **不带 BOM**。一个默认加 BOM 的修复
脚本会多走一个文件,在某个 markdown 的 diff 第 1 行留下一字节的改动。

**工具行为要补偿**:

| 工具 | 行为 |
|---|---|
| `Write` | Windows 上默认 **不带 BOM + LF**。这样新建的每个 `.cs` 都违规,除非事后修 |
| `Edit` | 保留源文件的编码和行尾,所以编辑一个已经正确的文件是安全的。但**再多次 Edit 也修不好一个当初 `Write` 出来就没 BOM 的文件** |
| `Read` | 透明地剥掉 BOM,也不显示行尾模式,所以**光看它的输出看不出状态** |

`Write` 过 `.cs` 之后验证并修复:

```powershell
$bytes  = [System.IO.File]::ReadAllBytes($path)
$hasBom = $bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF
$text   = [System.IO.File]::ReadAllText($path)
if ($text -match "(?<!`r)`n") { $text = $text -replace "(?<!`r)`n", "`r`n" }
if (-not $hasBom) { [System.IO.File]::WriteAllText($path, $text, [System.Text.UTF8Encoding]::new($true)) }
```

> **不要让一次编码整理给一个仓库本来就不带 BOM 的文件加上 BOM。** 先查:
> `git show <ref>:<path> | head -c 3`。

**两个会给出假读数的陷阱**:

- **不要用"工作区 vs 仓库里的 blob"来查行尾。** 这些仓库 `core.autocrlf=true`,所以 **blob 永远
  是 LF、工作副本永远是 CRLF**。那个比较会对每个文件都报 LF,读起来像到处漂移,于是被忽略——而它
  曾经对四个真被压平的文件给出过全清。**要么和同目录里一个没动过的邻居比,要么直接断言标准。**
  最便宜的信号:`git status` 会对**恰好是出问题的那些文件**警告
  *"LF will be replaced by CRLF the next time Git touches it"*。
- **Python 修补脚本会静默压平 CRLF**,除非用 `newline=""` 读。用 `encoding="utf-8-sig"` 打开会
  启用通用换行,内存里每个 `\r\n` 都变成 `\n`,写回去就是 LF。**永远用 `newline=""` 读,先探出
  文件自己的约定,再按它拼多行搜索模式。**

只改编码的提交是可以的,一样走提交门。

## 4. 不要新增 `global using`

任何项目都不要加。所有地方都用显式的文件级 `using`。

**为什么**:团队不喜欢,而且要求把早先引入的都删掉。这符合"显式导入"的整体偏好——**读者应该能从一个
文件的 import 块看出它依赖什么**。

**怎么用**:编辑一个曾经靠 global using 的文件时,把显式 `using` 加到那个文件里。如果某个文件引用了
一个类型却好像不需要 `using` 就能编译,去查那个项目里是不是还留着 `GlobalUsings.cs`。

## 5. 不要用上下文命名空间的一段给类型命名

不要把一个类型命名成它自己所在限界上下文命名空间的某个片段(命名空间里已经有 `Calculations`,
类型就别再叫 `Calculation…` 去重复它)。

## 6. 我们自己已有的、不在上面的

评审时这些同样算"已确立的约定",违反了是真发现,不是风格偏好:

| 约定 | 记忆 |
|---|---|
| 新 `.cs` 要 16 行 Ranplan 版权块,首行 `//  **`(两个空格) | `feedback_copyright_header_format` |
| 已 `using` 的命名空间不写全限定名 | `feedback_no_redundant_fqn` |
| 不为了对齐补空格(声明、`=`、参数、字典字面量) | `feedback_no_tabular_alignment` |
| `[NotNull]`/`[CanBeNull]` 单独一行,不内联 | `feedback_jetbrains_annotation_placement` |
| 多行三元 `?` `:` 放在续行**开头**;链式用 4 空格缩进 | `feedback_cs_ternary_formatting` |
| `///` 里只用纯 ASCII(不要 HTML 实体、不要非 ASCII 标点);普通 `//` 可以用破折号 | `feedback_xmldoc_ascii_only` |
| 注释不写分支名、任务号、"以前是怎样"的迁移叙事 | `feedback_comments_describe_behaviour` |
| 新测试默认 `Given_When_Then` 命名 + arrange/act/assert 分块 | `feedback_test_naming_given_when_then` |
| 避免全局/静态状态(`Project.Current`、ThreadStatic、单例服务定位器、`AppConst`) | `feedback_no_global_state` |
| 用户可见消息必须覆盖五语资源 | `feedback_ui_messages_must_localize` |

## 来源

`working-standard` 仓库 `memory/ranplan/rules/csharp.md`,加上我们自己的记忆条目。
