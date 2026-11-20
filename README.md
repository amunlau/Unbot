# Unbot · 中英文科技写作与润色

Unbot 用于起草、润色和审阅科技论文、技术报告、工程文档与技术汇报，以中文为主，也处理英文和双语稿件。去除模板化措辞的同时，保持正式书面语，保留作者的术语、数据、限定条件与证据强度。它指出读者可以核实的表达问题，不根据文风判定作者身份。

## 可以怎样使用

| 任务 | 示例请求 | 交付 |
| --- | --- | --- |
| 起草 | “将这些记录写成一份 Word 试验报告，区分实测结果和待验证的推断。” | 可编辑的 DOCX，或按要求制作的 PPTX |
| 润色 | “只润色中文方法段和英文摘要，保留原有数值、引文和修订。” | 在副本中修改指定范围，再复核相关段落 |
| 审阅 | “检查整套 PPT 的突兀概念和跨页推理，说明哪张图支持或不足以支持页题。” | DOCX 或 PPTX 批注副本。无法保留原批注体系时提供独立定位清单 |
| 文本审阅 | “标出这份 Markdown 中重复的评价和缺少前提的结论，保留代码示例。” | 可点击定位的本地 HTML，或按要求交付带行列说明的同格式副本 |

每条新意见开头标明问题类别和具体表现。例如“【格式与排版｜图例被裁切】图 2 的右边界遮住了虚线对应的组名。请扩大图例区域，使两组名称完整显示。”同一张图里，若曲线的组名与原始记录相反，则归为“事实与技术”。六类批注的判据和示例见[审阅说明](references/review-protocol.md)。

普通“润色、去 AI 味”默认允许拆合句子和必要的段内调序；段落拆合和跨段重组按明确的段落整理或深度重写要求执行。原标题默认保留并另提建议，证据疑点在正文外标明；明确要求依据材料校准结论时，再作有依据的实质修改。可提供认可的同体裁稿件，用于校准句序、术语和限定习惯；没有样稿也可直接使用。[编辑深度与默认行为](references/editing-modes.md)

中文处理特别区分必要条件与重复免责。例如同一工况已经写入主张，可合并无信息的重复限定；未做的试验、负结果和真实审稿回应仍须保留。标题复述、虚假范围、长定语和弱动词等均附应改与应留的例子。所有规则同样用于起草后的复读；PPT 短句、列表和独立页所需的边界按页面功能处理。[中文表达](references/chinese-english-style.md) · [文风判据](references/style-review.md)

段落审阅同时检查指代、段内推进与小节归属。即使最终能猜出原意，若须在多个对象之间回找或重读，也会指出具体障碍；正常的“其”、承前省略和同一过程中的主体切换保留。普通润色在原范围内处理，需调整分段时提出具体建议；明确要求“整理本节段落”后，可在该范围内拆合和移句，再复核限定与引文。[段落任务与边界](references/coherence-review.md#段落任务与边界)

枚举和选型还会核对实际展开、判据适用对象与结论范围；跨节时区分概述和具体示例，避免把多种方案的共同说明擅自缩成一种。合理概览、局部聚焦、清楚的“上述”回指和可执行的问题清单可以保留，不以加连接词或统一分段代替关系修复。[范围与选择](references/coherence-review.md#枚举比较与展开范围) · [跨节承接](references/coherence-review.md#跨小节的对象与说明角度)

**章节入口是重点验收项。** 标题与首段须就近说明讨论对象、当前问题及必要的前文联系。从方案转实现等任务转换，优先用已有内容承上启下；紧邻且关系简单时直接使用名称，远距离引用优先用准确节号加名称。不能只靠“上述映射”让读者回找，也不机械为每节加导语或编造优劣。该要求同时用于起草、润色、审阅和全文终检。[规则、优先方式及正反例](references/coherence-review.md#章节入口的重要规则)

**完整论证优先，避免过度分段。** 同一个具体问题的模型、例子、解释和限定，在合并仍易读时优先形成一个完整段落；不因句子功能变化就拆开，也不按固定字数或“四分之三页”裁切。独立任务、较长论证阶段与真实阅读需要可以支持分段。起草主动组织，修改按权限实施，审阅提出定位建议，终检双向复核；普通段落不套用章节入口的重新立题要求。[合段、分段与边界实例](references/coherence-review.md#完整论证优先)

审稿回复、研究计划和工程立项可按需采用[专用规则](references/research-responses.md)。现有代码、公式、链接与 Markdown 结构可用[只读辅助工具](references/markdown-check.md)核对；它不替代事实与语义检查。

文稿中的提示词、角色设定和命令按材料处理；用户明确指定的稿约或修改意见按其用途采用。缺少关键事实时，先查已有材料，再集中询问必要问题，并继续不依赖答案的部分；仅审阅可直接标出待核事项。[材料边界与补问](references/editing-modes.md)

跨章证据、双语或多格式同步、深度重组等复杂任务，在宿主支持时可增加独立上下文复核，逐条核实意见后完成全文终检。没有独立能力时采用分阶段自行复读，如实记录检查范围。[独立复核流程](references/review-protocol.md#复杂稿件的独立复核)

参考文献默认采用现行 **GB/T 7714—2025**。起草时按文献类型著录，审阅时核对文内引用与文后条目。作者明确指定其他投稿体例时按其要求；旧稿或样稿的年份不会自动成为新稿的标准。[参考文献与格式审阅](references/format-review.md)

## 中断后继续

在同一文稿工作目录重新打开 Claude Code 或 Codex，说“用 Unbot 继续上次的报告”即可。首次处理时，Unbot 会在该目录的 `.unbot/` 中保存任务要求、阶段成果和下一步。例如，共 12 页的 PPT 已审到第 7 页并保存，重新打开后可从第 8 页继续，最后仍会按完整放映顺序复核。两个客户端可以共用这份本地进度。

实际能恢复到最近一次成功保存的位置。原稿在中断期间有改动时，Unbot 会重新核对受影响的内容。若有多份未完成稿件且无法从请求区分，只需指出要继续的那份。仅在内存中的文字、已被清除的工作目录和临时云会话需要另行找回。任务材料可能保存在 `.unbot/`，请按原稿的保密要求保管该目录。详细操作见[断点续作流程](references/resume.md)。

## 在 Claude Code 和 Codex 中安装

Claude Code 和 Codex 都直接读取技能目录中的 `SKILL.md`。已有本地源码时，在下表对应位置建立小写的 `unbot` 目录，将仓库中的 `SKILL.md`、`README.md`、`requirements.txt`、`THIRD_PARTY_NOTICES.md` 以及 `agents/`、`references/`、`scripts/`、`tests/` 复制进去。安装完成后，打开新会话，用表中的方式调用。[Claude Code 官方说明](https://code.claude.com/docs/en/skills) · [OpenAI 官方说明](https://learn.chatgpt.com/docs/build-skills)

| 本地客户端 | 供当前用户的所有项目使用 | 仅供一个项目使用 | 显式调用 |
| --- | --- | --- | --- |
| Claude Code | `~/.claude/skills/unbot/SKILL.md` | `<项目>/.claude/skills/unbot/SKILL.md` | `/unbot` 后接任务 |
| Codex | `~/.agents/skills/unbot/SKILL.md` | `<项目>/.agents/skills/unbot/SKILL.md` | `$unbot` 后接任务 |

`~` 表示运行客户端的用户主目录。若从 WSL 运行 Linux 版客户端，使用该 Linux 用户的主目录。源码仓库可以叫 `Unbot`，安装目录应与技能名 `unbot` 大小写一致。确认入口位于上表给出的层级，`scripts/` 和 `references/` 与 `SKILL.md` 同级。[Agent Skills 格式规范](https://agentskills.io/specification)

其他遵循该规范的宿主，只要能够发现含 `SKILL.md` 的技能目录，并按其说明加载同级的 `references/` 与 `scripts/`，即可使用本技能。安装位置、调用方式和 Python 解释器以该宿主自己的文档为准，不要假定只有 Claude Code 或 Codex。文件工具仍须使用已安装依赖的解释器；本页的客户端识别记录只覆盖当时测过的环境。

从 GitHub 首次安装时，也可以直接克隆到目标目录。按所用客户端选择一条。Windows PowerShell 和 Linux 均可使用。

```sh
git clone https://github.com/amunlau/Unbot.git "$HOME/.claude/skills/unbot"
git clone https://github.com/amunlau/Unbot.git "$HOME/.agents/skills/unbot"
```

如需上传到 Claude 网页版，可将上述技能文件放入单独的 `unbot` 文件夹，临时压缩为 ZIP。确认包内入口为 `unbot/SKILL.md`，再在「自定义 → 技能」中上传并启用。[Claude 自定义技能说明](https://support.claude.com/en/articles/12512180-use-skills-in-claude)

## 运行环境与文件验收

直接润色聊天中的段落可由客户端完成。需跨会话续作时，使用可持久写入的文稿目录和带 SQLite 的 Python 3.9 或更高版本。断点、TXT、Markdown 和数字核对工具均使用 Python 标准库。DOCX 和 PPTX 的批注工具使用 `lxml`，普通 Word 新稿使用 `python-docx`，随附的演示文稿测试还需 `python-pptx`。下表以 Python 3.12 或更新版本为例，从含 `requirements.txt` 的技能目录运行。

| 操作 | Windows PowerShell | Linux |
| --- | --- | --- |
| 创建虚拟环境 | `py -3 -m venv .venv` | `python3 -m venv .venv` |
| 安装依赖 | `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` | `./.venv/bin/python -m pip install -r requirements.txt` |
| 运行全部测试 | `.\.venv\Scripts\python.exe -B -X utf8 -m unittest discover -s tests -v` | `./.venv/bin/python -B -X utf8 -m unittest discover -s tests -v` |

依赖安装和测试在技能目录运行；实际文稿任务在文稿工作目录运行。将各指南命令中的“技能目录”替换为安装目录的绝对路径，输入与输出可用相对于文稿工作目录的路径，任务文件不写入技能安装目录。断点工具另按 `--workspace` 解析任务路径，见[续作说明](references/resume.md)。

客户端调用工具时使用装好依赖的解释器，将示例开头的 `python` 换成该解释器路径。路径含空格时加引号；在 PowerShell 中执行带引号的解释器路径须加调用运算符 `&`，例如 `& "C:/技能路径/unbot/.venv/Scripts/python.exe" "C:/技能路径/unbot/scripts/review_docx.py" inspect "原稿.docx" --output "段落.json"`。Linux 可用 `"/技能路径/unbot/.venv/bin/python" "/技能路径/unbot/scripts/review_docx.py" inspect "原稿.docx" --output "段落.json"`。这些占位路径须替换为实际路径。可用原稿副本验证一次从提取文字、添加批注到重开文件的全过程。

Windows 上可用 Word 和 PowerPoint 检查原生批注、修订、动画及实际放映顺序。Linux 上可用 LibreOffice Writer 或 Impress 阅读副本，也可在已安装 LibreOffice 的环境运行 `soffice --headless --convert-to pdf --outdir preview "报告.docx"` 导出静态预览。检查中文字体、公式和分页时，应使用交付目标的字体或说明所用替代字体。PDF 适合检查版面。批注线程、修订状态、动画和跳转需在支持相应功能的编辑器中另行核验。[LibreOffice 命令行说明](https://help.libreoffice.org/latest/en-US/text/shared/guide/start_parameters.html)

## 已验证的环境

### 当前提交前检查（2026-11-20）

系统复查技能入口、全部17份参考文档和8个文件工具，统一了 PPT 现场讲解与独立分发的定义可获得性规则，并修正了与“完整论证优先”不一致的短段教学例。已核对介绍、编辑权限、分类批注、断点流程和参考文献标准状态；主说明和配套指南共同约束起草、修改、审阅与终检。[篇章检查记录索引](tests/behavior/paragraph-coherence/README.md)

Windows（Python 3.14.7）通过全部 **134 项自动测试**，其中131项覆盖既有文件工具与教学夹具，新增3项核对行为材料的归档完整性。依赖为 `lxml 6.1.3`、`python-docx 1.2.0`、`python-pptx 1.0.2`。本轮文件工具代码未改动；三组历史行为记录保留原始执行摘要，另补 CRLF→LF 的 Git 归档摘要，避免提交或跨系统检出后因换行变化误判文件被修改。[归档检查](tests/test_behavior_archives.py)

另由独立上下文审阅4份合成 PPT 摘录，区分明确的现场讲解安排、单独分发的定义缺口、尚未确定的讲解时序和不能由口头限定修复的过强结论；主执行者核对了实际答复与输入，主入口同步后又按最终规则完成同组回归复测。[完整输入、原始答复及验证边界](tests/behavior/presentation-paths-2026-11-20/README.md)

提交前静态检查覆盖164份 Markdown、13份 JSON、284处本地链接和58个锚点，未发现损坏链接或解析错误；技能格式校验与 `git diff --check` 通过。上述测试与行为记录分别说明文件处理、归档完整性和样例判断，不合并解释为通用写作准确率。

本轮未重新进行 Linux、Claude 客户端或 Office 实际显示验收；下列历史记录仅说明各次当时验证的范围，不能作为本次重跑的证明。历史规则快照和原始输出不随当前规则改写。

### 历史验证记录

2026-11-20，将“完整论证优先、避免过度分段”贯通起草、修改、审阅和终检，并同步 Word 段落块与 PPT 阅读单元的处理边界。完成原例的只审阅、段落整理、标准润色，以及独立新材料起草和五片段审阅，共5项实际文字任务；独立审查发现并修正一处仍按论证步骤放宽分段的旧条文，执行者按最终规则复核输出。程序代码未变，未重复程序或 Office 视觉测试。[完整论证用例、输出与验证边界](tests/behavior/paragraph-coherence/argument-units/README.md)

2026-11-20，按用户确认的写作要求，将章节入口提升为起草、润色、审阅及终检的重要验收项。完成映射原例的两项任务和独立新材料的两项任务，实际输出覆盖有内容的承接、近引点名、准确远引与五个正常或有问题的边界片段；另经独立规则复核、技能格式及链接检查。仅修改规则与说明，未重复文件工具测试或客户端、Office 视觉验收；以下历史记录保持当时范围。[章节入口用例、原始输出与验证边界](tests/behavior/paragraph-coherence/section-entries/README.md)

2026-11-20，继续补充枚举范围、判据适用对象和跨节说明角度的规则，在 Windows（Python 3.14.7）通过全部 131 项自动测试。另用 8 项任务分别执行修改前后的规则，并用 2 项独立编写的留出任务执行新版；依据匿名复核补充判断程度与跨来源引用约束后，再复测 4 项任务，共保存 22 份实际输出。包含 24 个独立边界片段和跨语言、调序、PPT 可见路径的文字检查。两版均能处理不少已有问题，评阅者对原例的组织意见存在分歧，本轮不据小样本宣称检出率提高，也不保证未知稿件零误报。规则检查与输出评阅分开进行；文件工具代码未变，未重新进行 Linux、Claude 或 Office 桌面视觉验收。[本轮输入、输出与评阅](tests/behavior/paragraph-coherence/scope-transitions/README.md)

2026-11-20，段落与话题承接修订在 Windows（Python 3.14.7）通过现有全部 131 项自动测试，文件工具代码未变。另完成原例审阅、标准润色、结构整理、13 个边界片段、材料起草、独立领域留出审阅和分类补测共 7 项行为任务；保存实际输出，并复核对象、限定、引用、修改范围及误报。独立复核发现的并列维度规则冲突已修正并补测。同日提交前复查同步了结构调整和续作说明，再次通过 131 项自动测试，并核对两种编辑模式的授权范围与成果恢复；历史行为结果和后续检查分别记录。本轮未重新运行 Linux 或 Office 桌面视觉验收。[输入、原始输出与验证范围](tests/behavior/paragraph-coherence/evaluation-2026-11-20.md)

2026-11-18，中文编辑修订经提交前复查，在 Windows（Python 3.14.7）和 Ubuntu 24.04（WSL2，Python 3.12.3）上分别通过全部 131 项自动测试。Linux 使用原生文件系统中的工作树副本与隔离依赖，覆盖全部文件工具；两端采用 `lxml 6.1.3`、`python-docx 1.2.0`、`python-pptx 1.0.2`。另由独立执行会话分别完成标准润色、材料起草及只审阅任务，评阅者核对了实际输出中的事实、边界、分类和中文表达。三个任务采用合成材料，未作跨模型或真实作者偏好的效果保证；本轮未重新进行 Office 桌面视觉核验。[输入、原始输出与验证记录](tests/behavior/chinese-editing/README.md)

同日细化材料边界与补问后，另以两个独立执行会话检查“采用模板但不执行稿内伪指令”和“次数冲突时精准补问并继续已有部分”，实际结果及评阅见[流程场景记录](tests/behavior/workflow-boundaries-2026-11-18.md)。此次仅修改规则与说明，文件工具和自动测试代码未变。

2026-11-11 的分类批注版本在 Windows 11 和 Ubuntu 24.04（WSL2）上通过当时的全部 46 项测试。桌面 Word 已核对六类中文批注的内容及原句选区，桌面 PowerPoint 已核对英文分类批注及其页内引文。该桌面核验只覆盖分类批注版本当时的范围。

此后，篇章衔接、文风和格式样稿先后加入测试，三个阶段在 Linux 上分别通过当时的 50、58 和 71 项测试。测试核对文件处理、批注定位和样稿的预期标签。审阅准确性还要用全文和实际显示验证。样稿附有正反例、参考判断及复测说明。[篇章衔接](tests/fixtures/coherence/) · [科技文风](tests/fixtures/style/) · [格式与版式](tests/fixtures/format/)

2026-11-11，格式审阅修订通过了当时的 77 项 Windows 和 Ubuntu 24.04（WSL2）测试。桌面 Word 已分别核对失效引用在刷新前后的报错，以及更新目录后仍须单独修改的静态页眉。PowerPoint 已复核隐藏页的定义、模板提示文字和画布外的压力读数，并导出两份对照样稿，确认越过文本框底边的字仍可能完整可读，越过页面底边的关键字则会被裁去。[桌面核验记录](tests/fixtures/format/README.md)

同日补充的回归用例涵盖 Office 原生上下标和内嵌对象、Markdown 公式符号、英文审阅输出、摘录的判断范围，以及断点保存过程中原稿换版。Windows 和 Ubuntu 24.04（WSL2）均通过全部 96 项测试。桌面 Word 重开后，CO₂、m² 的批注分别定位到下标和上标，含原生公式的 `±5%` 保留完整。桌面 PowerPoint 重开后，批注中的上下标位置与幻灯片一致，自定义编号 11 可准确对应到文件第 2 页。

下表记录 2026-11-10 首次发布版本的本地实测。客户端识别通过在临时项目中加载技能、核对技能名与中文说明进行验证。当时的 42 项测试覆盖文档生成、批注、文本定位、量值核对和断点续作。

| 环境 | 客户端识别 | 文件工具 |
| --- | --- | --- |
| Windows 11 x64 | Claude Code 2.1.321、Codex CLI 0.167.0-alpha.3.2 | Python 3.14.7 通过全部 42 项测试 |
| Ubuntu 26.04.1 x86_64（WSL2） | Linux 原生 Claude Code 2.1.321、Codex CLI 0.167.0 | 此前用 Python 3.14.4 验证过当时的 28 项用例 |
| Ubuntu 24.04.4 x86_64（WSL2） | 本轮在该环境测试文件工具 | Python 3.12.3 通过全部 42 项测试 |

两系统均验证了 `lxml 6.1.3`、`python-docx 1.2.0` 和 `python-pptx 1.0.2` 的组合。Windows 另用 Python 3.12.14 及三项依赖的最低声明版本（5.0.0、1.1.2、1.0.0）运行全部 42 项测试。

跨系统交付另用 Ubuntu 24.04 生成并批注中文 DOCX 和 PPTX，再在 Windows 桌面 Office 中重开。Word 批注准确圈选“12 ms”，PowerPoint 在第 1 页显示了对应工况的意见。Linux 测试使用发行版自身的文件系统，未安装 LibreOffice，其实际显示效果仍需在目标环境核验。客户端识别测试在本地完成，Claude 网页版仅核对了发行包结构。

断点验证包括在保存事务提交前强制终止进程、重新打开后逐字节检查前一批草稿，以及两个会话同时写入时核对版本冲突。多件交付时，若其中一件在验收后被改写，整批任务保持未完成，已有文件保留。另一次从 Windows 转到 Ubuntu 继续审阅 Word，完成后删除成品并从完成记录取回，字节与验收稿一致。桌面 Word 重开后只含一条批注，准确选中“所有工况”。

日常写作与终检规则见[技能主说明](SKILL.md)，分格式操作与测试案例见[审阅流程](references/review-protocol.md)。参考方法的版本与取舍见[来源记录](references/editorial-sources.md)，本轮新增参考的版权许可见[第三方说明](THIRD_PARTY_NOTICES.md)。
