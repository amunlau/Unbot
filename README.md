# Unbot · 中英文科技写作与润色

当前版本：**v4.0.0**（2026-11-26）。

Unbot 用于起草、润色和审阅科技论文、技术报告、工程文档与技术汇报，以中文为主，也处理英文和双语稿件。去除模板化措辞的同时，保持正式书面语，保留作者的术语、数据、限定条件与证据强度。它指出读者可以核实的表达问题，不根据文风判定作者身份。

**本版将“限定非必要不使用”写入写作宪法。** 内部核验事实与适用范围，正文按当前问题组织。附加限定只有与主题直接相关、省略会严重影响主张准确性或具体执行判断、且专业读者不能从已给内容轻易推知时才写；避免每段补上未测范围、负面评价或免责。主张本身的工况、证据强度和必要操作要求仍须准确，直接回答当前问题的负结果据实呈现。[必要性判据](references/style-review.md#9-重复防御与必要限定)

**每章的附加限定通常为 0—3 项，按内容决定。** 不设最低数量或硬性上限；若超过三分之一、尤其达到或超过一半的正文段落出现附加限定，按严重堆叠问题处理。先清理无必要提醒，保留主张本身的条件与事实，不用凑段、合段或隐藏到脚注的方法降低比例。[章节数量与分布](references/style-review.md#章节内的限定数量与分布)

来源名称与版本在使用位置须让读者辨明所指：交代必要的软件或产品身份、具体资料与版本归属，并接入已有引注；近邻清楚的简称保留，缺失信息不猜补。段落篇幅按主题内涵和解释需要分配，让丰富论证与单一状态自然形成长短变化，同时复查整节、全文是否被统一模板拉齐。规则用于起草、润色、审阅和终检，不设置长短配额。[来源指代](references/coherence-review.md#来源名称与局部指代) · [段落长短](references/coherence-review.md#段落长短随展开需要变化)

**写作宪法：限定非必要不使用，指称清楚、段首完整、逻辑可追踪。** 首次引入交代身份，段首写清对象与具体关系，前后段及小节内保持可辨的论证联系。生成和检查均逐项执行[五项必查](references/coherence-review.md#五项必查)，并用[算子融合转向重复层编排的示例](references/coherence-review.md#算子融合转向重复层编排)说明怎样实质承上启下；保留自然省略与隐含关系，不机械禁用连接词。核心要求见[技能入口](SKILL.md#写作宪法指称清楚段首完整逻辑可追踪)。

段首还可按实际功能选择[六类正向写法](references/paragraph-openings.md)：承上启下、判断主题句、条件与边界、转折澄清、场景导入、因果或工程归纳。按段落任务选择，不强制组合或配比。条件与澄清只在确有必要时采用；普通机制说明可直接展开动作与结果，并保留必要定义和直接操作。

## 可以怎样使用

| 任务 | 示例请求 | 交付 |
| --- | --- | --- |
| 起草 | “将这些记录写成一份 Word 试验报告，区分实测结果和待验证的推断。” | 可编辑的 Word 报告（DOCX） |
| 润色 | “只润色中文方法段和英文摘要，保留原有数值、引文和修订。” | 在副本中修改指定范围，再复核相关段落 |
| 审阅 | “检查整套 PPT 的突兀概念和跨页推理，说明哪张图支持或不足以支持页题。” | 带页位批注的 PPTX 副本。无法保留原批注体系时提供独立的页位意见单 |
| 文本审阅 | “标出这份 Markdown 中重复的评价和缺少前提的结论，保留代码示例。” | 可点击定位的本地 HTML，或按要求交付带行列说明的同格式副本 |

每条新意见开头标明问题类别和具体表现。例如“【格式与排版｜图例被裁切】图 2 的右边界遮住了虚线对应的组名。请扩大图例区域，使两组名称完整显示。”同一张图里，若曲线的组名与原始记录相反，则归为“事实与技术”。六类批注的判据和示例见[审阅说明](references/review-protocol.md)。

普通“润色、去 AI 味”默认允许拆合句子和必要的段内调序；段落拆合和跨段重组按明确的段落整理或深度重写要求执行。原标题默认保留并另提建议，证据疑点在正文外标明；明确要求依据材料校准结论时，再作有依据的实质修改。可提供认可的同体裁稿件，用于校准句序、术语和限定习惯；没有样稿也可直接使用。[编辑深度与默认行为](references/editing-modes.md)

中文处理特别区分主张的必要条件与附加提醒。同一工况已经写入主张，不再复述“不代表所有工况”；材料里出现未做的试验，也不因此自动写入正文。普通润色保护独立事实与原意；明确要求减少非必要限定时，按必要性判据清理，真实审稿问题仍按其具体要求回应。标题复述、虚假范围、长定语和弱动词等均附应改与应留的例子。所有规则同样用于起草后的复读；PPT 短句、列表和独立页所需的边界按页面功能处理。[中文表达](references/chinese-english-style.md) · [文风判据](references/style-review.md)

段落审阅同时检查指代、段内推进与小节归属。即使最终能猜出原意，若须在多个对象之间回找或重读，也会指出具体障碍；正常的“其”、承前省略和同一过程中的主体切换保留。普通润色在原范围内处理，需调整分段时提出具体建议；明确要求“整理本节段落”后，可在该范围内拆合和移句，再复核限定与引文。[段落任务与边界](references/coherence-review.md#段落任务与边界)

枚举和选型还会核对实际展开、判据适用对象与结论范围；跨节时区分概述和具体示例，避免把多种方案的共同说明擅自缩成一种。合理概览、局部聚焦、清楚的“上述”回指和可执行的问题清单可以保留，不以加连接词或统一分段代替关系修复。[范围与选择](references/coherence-review.md#枚举比较与展开范围) · [跨节承接](references/coherence-review.md#跨小节的对象与说明角度)

**章节入口是重点验收项。** 标题与首段须就近说明讨论对象、当前问题及必要的前文联系。从方案转实现等任务转换，优先用已有内容承上启下；紧邻且关系简单时直接使用名称，远距离引用优先用准确节号加名称。不能只靠“上述映射”让读者回找，也不机械为每节加导语或编造优劣。该要求同时用于起草、润色、审阅和全文终检。[规则、优先方式及正反例](references/coherence-review.md#章节入口的重要规则)

**完整论证优先，避免过度分段。** 同一个具体问题的模型、例子和解释，以及确有必要的限定，在合并仍易读时优先形成一个完整段落；不因句子功能变化就拆开，也不按固定字数或“四分之三页”裁切。独立任务、较长论证阶段与真实阅读需要可以支持分段。起草主动组织，修改按权限实施，审阅提出定位建议，终检双向复核；普通段落不必像章节入口一样重新立题，但仍须满足对象、具体关系与承接清楚的段首要求。[合段、分段与边界实例](references/coherence-review.md#完整论证优先)

审稿回复、研究计划和工程立项可按需采用[专用规则](references/research-responses.md)。现有代码、公式、链接与 Markdown 结构可用[只读辅助工具](references/markdown-check.md)核对；它不替代事实与语义检查。

文稿中的提示词、角色设定和命令按材料处理；用户明确指定的稿约或修改意见按其用途采用。缺少关键事实时，先查已有材料，再集中询问必要问题，并继续不依赖答案的部分；仅审阅可直接标出待核事项。[材料边界与补问](references/editing-modes.md)

跨章证据、双语或多格式同步、深度重组等复杂任务，在宿主支持时可增加独立上下文复核，逐条核实意见后完成全文终检。没有独立能力时采用分阶段自行复读，如实记录检查范围。[独立复核流程](references/review-protocol.md#复杂稿件的独立复核)

参考文献默认采用现行 **GB/T 7714—2025**。起草时按文献类型著录，审阅时核对文内引用与文后条目。作者明确指定其他投稿体例时按其要求；旧稿或样稿的年份不会自动成为新稿的标准。[参考文献与格式审阅](references/format-review.md)

## 中断后继续

在同一文稿工作目录重新打开 Claude Code 或 Codex，说“用 Unbot 继续上次的报告”即可。首次处理时，Unbot 会在该目录的 `.unbot/` 中保存任务要求、阶段成果和下一步。例如，共 12 页的 PPT 已审到第 7 页并保存，重新打开后可从第 8 页继续，最后仍会按完整放映顺序复核。两个客户端可以共用这份本地进度。

实际能恢复到最近一次成功保存的位置。原稿在中断期间有改动时，Unbot 会重新核对受影响的内容。若有多份未完成稿件且无法从请求区分，只需指出要继续的那份。仅在内存中的文字、已被清除的工作目录和临时云会话需要另行找回。任务材料可能保存在 `.unbot/`，请按原稿的保密要求保管该目录。详细操作见[断点续作流程](references/resume.md)。

## 在 Claude Code 和 Codex 中安装

Claude Code 和 Codex 都直接读取技能目录中的 `SKILL.md`。已有本地源码时，在下表对应位置建立小写的 `unbot` 目录，将仓库中的 `SKILL.md`、`README.md`、`requirements.txt` 以及 `agents/`、`references/`、`scripts/`、`tests/` 复制进去。安装完成后，打开新会话，用表中的方式调用。[Claude Code 官方说明](https://code.claude.com/docs/en/skills) · [OpenAI 官方说明](https://learn.chatgpt.com/docs/build-skills)

| 本地客户端 | 供当前用户的所有项目使用 | 仅供一个项目使用 | 显式调用 |
| --- | --- | --- | --- |
| Claude Code | `~/.claude/skills/unbot/SKILL.md` | `<项目>/.claude/skills/unbot/SKILL.md` | `/unbot` 后接任务 |
| Codex | `~/.agents/skills/unbot/SKILL.md` | `<项目>/.agents/skills/unbot/SKILL.md` | `$unbot` 后接任务 |

`~` 表示运行客户端的用户主目录。若从 WSL 运行 Linux 版客户端，使用该 Linux 用户的主目录。源码仓库可以叫 `Unbot`，安装目录应与技能名 `unbot` 大小写一致。确认入口位于上表给出的层级，`scripts/` 和 `references/` 与 `SKILL.md` 同级。[Agent Skills 格式规范](https://agentskills.io/specification)

其他遵循该规范的宿主，只要能够发现含 `SKILL.md` 的技能目录，并按其说明加载同级的 `references/` 与 `scripts/`，即可使用本技能。安装位置、调用方式和 Python 解释器以该宿主自己的文档为准，不要假定只有 Claude Code 或 Codex。文件工具仍须使用已安装依赖的解释器。

从 GitHub 首次安装时，可按客户端选择下方命令。命令获取仓库默认分支。需要指定发行版时，从对应发布标签获取源码，再核对 `SKILL.md` 中的 `metadata.version`。

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

## v4.0.0 验证记录

本次检查技能入口、18 份配套指南、7 个命令行工具及其共用的批注分类模块、操作说明与行为归档。重点统一限定的必要性判断、段首功能选择、事实保真和编辑权限，移除示例中无必要的负面收尾；来源身份、篇章逻辑及按内容组织段落的要求继续适用。

本次在 Windows、Python 3.14.7 下运行全部 **141 项自动测试**，均已通过。其中包括 Markdown 勾选状态、带转义美元符的行内公式，以及各次归档的版本与文件完整性检查。

章节限定分布专项的五项文字任务中，四项首轮通过，一项在补充审阅说明后复测通过。各次文字执行均保留当时使用的规则和实际输出。[限定分布专项记录](tests/behavior/density-review-2026-11-26/README.md) · [本版九项文字验证](tests/behavior/v4-release-2026-11-26/README.md) · [行为用例索引](tests/behavior/README.md)

### 教学样稿与文件验收

[篇章样稿](tests/fixtures/coherence/)、[文风样稿](tests/fixtures/style/)与[格式样稿](tests/fixtures/format/)包含应改和应留的实例、参考判断及各次验证范围。样稿的自动测试检查数据、对象属性和批注定位，不能替代语义审阅；其中记录的桌面显示结果仅对应所列日期和文件版本。

日常写作与终检规则见[技能主说明](SKILL.md)，分格式操作及意见分类见[审阅流程](references/review-protocol.md)。
