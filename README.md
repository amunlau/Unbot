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

从 GitHub 首次安装时，也可以直接克隆到目标目录。将下方的 `<仓库地址>` 换成项目的克隆地址，按所用客户端选择一条。Windows PowerShell 和 Linux 均可使用。

```sh
git clone "<仓库地址>" "$HOME/.claude/skills/unbot"
git clone "<仓库地址>" "$HOME/.agents/skills/unbot"
```

如需上传到 Claude 网页版，可将上述技能文件放入单独的 `unbot` 文件夹，临时压缩为 ZIP。确认包内入口为 `unbot/SKILL.md`，再在「自定义 → 技能」中上传并启用。[Claude 自定义技能说明](https://support.claude.com/en/articles/12512180-use-skills-in-claude)

## 运行环境与文件验收

直接润色聊天中的段落可由客户端完成。需跨会话续作时，使用可持久写入的文稿目录和带 SQLite 的 Python 3.9 或更高版本。断点、TXT、Markdown 和数字核对工具均使用 Python 标准库。DOCX 和 PPTX 的批注工具使用 `lxml`，普通 Word 新稿使用 `python-docx`，随附的演示文稿测试还需 `python-pptx`。下表以 Python 3.12 或更新版本为例，从含 `requirements.txt` 的技能目录运行。

| 操作 | Windows PowerShell | Linux |
| --- | --- | --- |
| 创建虚拟环境 | `py -3 -m venv .venv` | `python3 -m venv .venv` |
| 安装依赖 | `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` | `./.venv/bin/python -m pip install -r requirements.txt` |
| 运行全部测试 | `.\.venv\Scripts\python.exe -B -X utf8 -m unittest discover -s tests -v` | `./.venv/bin/python -B -X utf8 -m unittest discover -s tests -v` |

客户端运行文件工具时应使用装好依赖的解释器。把各指南示例开头的 `python` 换成该解释器路径即可。工作目录与技能目录不同时，为脚本、输入及输出传入完整路径。可用原稿副本验证一次从提取文字、添加批注到重开文件的全过程。

Windows 上可用 Word 和 PowerPoint 检查原生批注、修订、动画及实际放映顺序。Linux 上可用 LibreOffice Writer 或 Impress 阅读副本，也可在已安装 LibreOffice 的环境运行 `soffice --headless --convert-to pdf --outdir preview "报告.docx"` 导出静态预览。检查中文字体、公式和分页时，应使用交付目标的字体或说明所用替代字体。PDF 适合检查版面。批注线程、修订状态、动画和跳转需在支持相应功能的编辑器中另行核验。[LibreOffice 命令行说明](https://help.libreoffice.org/latest/en-US/text/shared/guide/start_parameters.html)

## 已验证的环境

2026-11-11 的分类批注版本在 Windows 11 和 Ubuntu 24.04（WSL2）上通过全部 46 项测试。桌面 Word 已核对六类中文批注的内容及原句选区，桌面 PowerPoint 已核对英文分类批注及其页内引文。

下表记录 2026-11-10 首次发布版本的本地实测。客户端识别通过在临时项目中加载技能、核对技能名与中文说明进行验证。当时的 42 项测试覆盖文档生成、批注、文本定位、量值核对和断点续作。

| 环境 | 客户端识别 | 文件工具 |
| --- | --- | --- |
| Windows 11 x64 | Claude Code 2.1.321、Codex CLI 0.167.0-alpha.3.2 | Python 3.14.7 通过全部 42 项测试 |
| Ubuntu 26.04.1 x86_64（WSL2） | Linux 原生 Claude Code 2.1.321、Codex CLI 0.167.0 | 此前用 Python 3.14.4 验证过当时的 28 项用例 |
| Ubuntu 24.04.4 x86_64（WSL2） | 本轮在该环境测试文件工具 | Python 3.12.3 通过全部 42 项测试 |

两系统均验证了 `lxml 6.1.3`、`python-docx 1.2.0` 和 `python-pptx 1.0.2` 的组合。Windows 另用 Python 3.12.14 及三项依赖的最低声明版本（5.0.0、1.1.2、1.0.0）运行全部 42 项测试。

跨系统交付另用 Ubuntu 24.04 生成并批注中文 DOCX 和 PPTX，再在 Windows 桌面 Office 中重开。Word 批注准确圈选“12 ms”，PowerPoint 在第 1 页显示了对应工况的意见。Linux 测试使用发行版自身的文件系统，未安装 LibreOffice，其实际显示效果仍需在目标环境核验。客户端识别测试在本地完成，Claude 网页版仅核对了发行包结构。

断点验证包括在保存事务提交前强制终止进程、重新打开后逐字节检查前一批草稿，以及两个会话同时写入时核对版本冲突。多件交付时，若其中一件在验收后被改写，整批任务保持未完成，已有文件保留。另一次从 Windows 转到 Ubuntu 继续审阅 Word，完成后删除成品并从完成记录取回，字节与验收稿一致。桌面 Word 重开后只含一条批注，准确选中“所有工况”。

日常写作与终检规则见[技能主说明](SKILL.md)，分格式操作与测试案例见[审阅流程](references/review-protocol.md)。
