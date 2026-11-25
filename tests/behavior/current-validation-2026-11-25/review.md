# v3.3.0 逐项复核

日期：2026-11-25。对象为当前技能目录。规则与工具分别由独立上下文只读检查，主执行者核对依据、完成修改并检查相互引用。版本保持 3.3.0。

## 文件覆盖

| 文件 | 核对内容与结论 |
| --- | --- |
| `SKILL.md` | 任务模式、编辑权限、交付、保真与全文终检相容；整理文档导航。 |
| `references/editing-modes.md` | 标准润色、结构授权、单项撤销、引文核验范围及作者样稿校准一致。 |
| `references/professional-writing.md` | 起草选材、证据职责、工程状态、限字和局部重建的条件清楚。 |
| `references/style-review.md` | 修正无内容强调的判据，保护操作位置的必要重复警示；强调样式按实际用途判断。 |
| `references/chinese-english-style.md` | 数值归属、语态、施事、条件和双语边界一致，未确认错误。 |
| `references/coherence-review.md` | 分段、章节入口、比较范围、引文绑定与结构权限相容；将依赖会话的标题改为直接描述示例。 |
| `references/genre-examples.md` | 逐例核对数值、研究状态及编辑范围，未确认信息增删错误。 |
| `references/research-responses.md` | 实际意见、作者立场、完成状态和计划边界一致。 |
| `references/review-protocol.md` | 六类意见、覆盖说明、零项结果和独立复核流程一致；更新验证导航。 |
| `references/resume.md` | 命令、模式、路径、附件、恢复回执和完成流程与脚本一致。 |
| `references/word-authoring.md` | 新稿和复杂旧稿分流、JSON 示例、生成范围及页面核验要求准确。 |
| `references/word-review.md` | 批注定位、保护范围、复杂对象和失败处理与实现一致。 |
| `references/pptx-review.md` | 页级批注、对象定位、现代批注处理及放映路径说明与实现一致。 |
| `references/presentation-workflow.md` | 现场讲解与单独分发的阅读条件一致，不将备注等同于观众已知内容。 |
| `references/markdown-check.md` | 结构类别、编码、授权选项、返回码和解析限制与工具一致。 |
| `references/format-review.md` | 编号、引用、题注、可见性及配色判断按模板和实际用途执行；参考文献标准现行状态复核无须变更。 |
| `references/writing-evidence.md` | 研究结论与编辑用途有范围区分；更新验证链接，未把既有研究记作本轮重新评测。 |
| `references/detection-evidence.md` | 群体研究与单句判断、定位方式与标准实现范围区分清楚。 |
| `scripts/checkpoint.py` | 输入指纹、版本冲突、保存、恢复及交付核验与文档一致。 |
| `scripts/write_docx.py` | 内容块、表格、样式、题名属性及新文件写入与文档一致。 |
| `scripts/review_docx.py` | 可批注区间、修订与域、上下标、引文定位及反读未发现新增错误。 |
| `scripts/review_pptx.py` | 编辑页序、放映、隐藏对象、备注、批注保护及反读未发现新增错误。 |
| `scripts/review_text.py` | 编码、指纹、跨行定位、重叠拒绝与输出保护未发现新增错误。 |
| `scripts/review_classification.py` | 类别、旧清单兼容和必填项与接口说明一致。 |
| `scripts/check_literals.py` | 数值及指定片段计数的能力边界明确，没有宣称完成语义核验。 |
| `scripts/check_markdown_structure.py` | 八类结构、扫描限制、授权类别及退出码与文档一致。 |
| `README.md` | 更新当前文件布局、验证入口和版本说明，删除失效导航。 |
| `requirements.txt`、`agents/openai.yaml` | 依赖与代码用途、展示描述与入口行为一致。 |
| `tests/fixtures/`、`tests/test_*.py` | 教学例与程序验证范围分开；现有文件工具测试保持不变，执行记录用包内摘要检查。 |

## 规则修正

此前把“需要强调的是”等没有带来新条件的表达直接判为无内容强调。这会与真实警示、重点区分和审稿回应的保留要求冲突。例如，禁令已经在安全条件中定义，操作前再次提醒仍可能帮助执行者避免错误。

当前判据要求同时确认没有信息增量，也不承担必要警示、重点区分或真实回应，才提出删除；同步调整共用约束。不为措辞设禁用表，也不因有强调词而自动保留整句。实际任务 A、B 分别检查应留与应删情形，结果见[验证说明](README.md)。

## 运行与外部资料范围

接口审查实际运行 7 项顶层帮助、14 项子命令帮助，均返回 0；8 个脚本通过 Python 3.9 AST 语法解析。实际解释器为 Python 3.14.7，语法检查不等于 Python 3.9 实机验证。

本日查询[国家标准信息公共服务平台](https://std.samr.gov.cn/gb/search/gbDetailedCNF?id=4507EFE13D37CB6AE06397BE0A0A601F)，GB/T 7714—2025 状态为现行，实施日期为 2026-07-01。另核对 Google 的[夸张断言](https://developers.google.com/style/excessive-claims)与[语气](https://developers.google.com/style/tone)页面，与文档中所述适用范围相符。没有据此声称重新核验全部外部研究或标准全文。

完整程序测试、实际文字任务、文档链接和版本检查分别记录在[验证说明](README.md)及 [checks.json](checks.json)。本轮未进行 Office 显示、Linux、客户端识别或真实长稿验收。
