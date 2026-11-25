# 范围、选择与跨节承接：行为验证

本组材料用于检查枚举与实际展开、判据与适用对象、概述与具体示例之间的关系，同时保护合理概览、承前省略、普通回指和有效清单。运行规则见[篇章衔接审阅](../../../../references/coherence-review.md)。这些材料是维护时的回归资源，不要求处理普通文稿时加载。

本组保留章节入口要求强化之前的冻结规则与评阅。此后用户明确将入口定位和任务承接列为重要项目要求，新增规则与复测见[章节入口验证](../section-entries/README.md)；不要将本组原有评阅分歧作为放行模糊节首的最新标准，原始输出不追溯改写。

## 输入与执行方法

[cases.json](cases.json)保存 8 项开发任务和 2 项独立编写的留出任务，含原始请求、材料及评阅要点。开发任务使用用户例子或明确标明的合成材料；留出任务由未读取技能、开发例子及预期答案的另一执行者编写。评阅要点与执行输入分开保存，行为执行者只获得请求、材料及对应版本的技能文件。

旧版为提交 `07f1cf8d1dfe1dba269b99d6246507520190b08e`（v3.1.0），新版首轮为本次修改的冻结快照。8 项开发任务各执行旧、新版一次，2 项留出任务仅执行新版；复核后微调两处规则并冻结最终快照，再复测 4 项开发任务，共 10 种任务、22 份实际输出。首轮规则冻结后，维护者才读取留出任务；最终微调后的任务不再称为未见测试。所有行为任务均要求输出文字，没有实际改写 Office 文件，也没有验证例子中的 GPU 技术事实。

首轮同一版本内，五项原例任务由一个执行会话依次处理，三项补充任务由另一会话处理，留出任务使用第三个会话；最终四项复测再使用一个新会话。不是每项任务都使用全新上下文。执行会话未指定模型覆盖，沿用宿主默认模型；工具未提供可记录的精确模型版本和采样参数。本组不支持跨模型效果结论。

[runtime-snapshots.json](runtime-snapshots.json)保存基线、首轮新版及最终规则的 `SKILL.md` 与 17 份 `references/*.md` 的逐文件 SHA-256、集合摘要和原始输出摘要。集合摘要计算方式：相对 POSIX 路径排序，每项连接 `路径 + NUL + 文件SHA-256`，各项以 LF 分隔且末尾不加 LF，再对 UTF-8 字节计算 SHA-256。README、测试资料及执行结果不属于运行规则摘要。

清单原有字段保留执行时的原始字节摘要，指向历史规则，不随当前技能更新。提交前补充的 `archive_lf_sha256` 覆盖本组输入、全部输出和评阅材料，用于 Git 归档或跨系统检出后的内容校验。其 `archive_hash_method` 为 `sha256-crlf-to-lf-v1`：只将 CRLF 转为 LF 后计算 SHA-256，不裁剪空白、不补末尾换行、不改正文。仓库 `.gitattributes` 会规范化文本换行，因此归档摘要可能与原始字节摘要不同；这不表示重新执行了行为任务。[归档完整性测试](../../../test_behavior_archives.py)校验覆盖范围、归档内容和历史规则集合摘要，不将旧快照与当前规则比较。

## 任务与原始输出

| 任务 | 检查重点 | 旧版 | 新版 |
| --- | --- | --- | --- |
| gpu-review | 通信概览、局部比较、判据与末句范围 | [输出](results/baseline/gpu-review.md) | [输出](results/candidate/gpu-review.md) |
| mapping-review | 总述三种映射与一种教学示例的范围 | [输出](results/baseline/mapping-review.md) | [输出](results/candidate/mapping-review.md) |
| gpu-polish | 保持标题与两段，只作普通润色 | [输出](results/baseline/gpu-polish.md) | [输出](results/candidate/gpu-polish.md) |
| gpu-structure | 已授权的小节内段落整理 | [输出](results/baseline/gpu-structure.md) | [输出](results/candidate/gpu-structure.md) |
| mapping-polish | 作者已明确总述与例示时的保真润色 | [输出](results/baseline/mapping-polish.md) | [输出](results/candidate/mapping-polish.md) |
| boundary-review | 24 个独立片段，含 10 个正常反例 | [输出](results/baseline/boundary-review.md) | [输出](results/candidate/boundary-review.md) |
| material-draft | 从无序材料组织概览、局部比较与过程 | [输出](results/baseline/material-draft.md) | [输出](results/candidate/material-draft.md) |
| montage-review | PPT 可见路径、调序后指代、中英文结论 | [输出](results/baseline/montage-review.md) | [输出](results/candidate/montage-review.md) |
| coherence_holdout_review_environment | 现场采样的项目覆盖、条件及示例范围 | — | [输出](results/candidate/coherence_holdout_review_environment.md) |
| coherence_holdout_draft_inspection | 工程检验选型、时间估算与试验过程 | — | [输出](results/candidate/coherence_holdout_draft_inspection.md) |

最终规则复测的原始输出另存，不覆盖上表首轮结果：[GPU 审阅](results/final/gpu-review.md)、[映射审阅](results/final/mapping-review.md)、[材料起草](results/final/material-draft.md)、[24 个边界片段](results/final/boundary-review.md)。

## 与调研现象的对应

以下 C01—C18 是本轮调研与用例的对应编号，不是新增批注大类，不写入 `category` 或 `finding_schema`。一项任务可以检查多个现象；覆盖不等于在未知文稿中已经获得检出率。

| 编号 | 现象 | 代表输入 |
| --- | --- | --- |
| C01 | 列举承诺与实际展开不对应 | gpu-review；boundary-review F |
| C02 | 分类、包含、组合或观察维度混淆 | boundary-review A、G |
| C03 | 介绍对象后转入选择，缺少实际联系 | gpu-polish；gpu-structure；material-draft |
| C04 | 判据适用对象与结论范围改变 | gpu-review；boundary-review B |
| C05 | 跨节回指范围不明 | mapping-review；boundary-review C |
| C06 | 对象或说明角度切换未交代 | mapping-polish；material-draft |
| C07 | 将待回答清单当成已完成的分析 | gpu-polish；boundary-review E 为正常清单 |
| C08 | 必要定义或前提晚于使用 | boundary-review H；montage-review A |
| C09 | 话题、动作主体或省略链断裂 | boundary-review I；D、Q 为正常例 |
| C10 | 同名指标的含义、单位或口径漂移 | boundary-review J |
| C11 | 因果、递进或理由关系缺乏支持 | boundary-review K、P |
| C12 | 证据不足以覆盖推论 | boundary-review F、L；montage-review C |
| C13 | 条件、否定、引用或来源归属脱落 | mapping-polish；material-draft；boundary-review M |
| C14 | 标题、段首、正文与结尾的任务错位 | boundary-review N |
| C15 | 独立任务混装、碎裂或插入后不返回 | boundary-review O；S 为合法摘要；gpu-structure |
| C16 | 重复无增量或循环论证 | boundary-review P、V |
| C17 | 图表、符号与可见阅读路径缺口 | montage-review A |
| C18 | 分块、调序或恢复后依赖失效 | montage-review B；仅覆盖调序的文字关系 |

续作事务与文件保真另由既有自动测试检查；本组没有模拟新的断网、关机或文件损坏场景。

## 评阅与限制

逐项对照原材料、授权范围和预先记录的评阅要点，并将两版输出隐去版本身份、交替排列后交由独立会话复核。评阅者只见输入和匿名输出，不见规则、预期答案或标签对应。该安排可减少直接偏向新版，不能消除模型评阅偏差；执行者与评阅者均不是人类受试者。

以原意、条件、论证范围、误报和权限为主要依据，不以意见条数、固定改句、段落数或关键词命中率验收。允许有依据的额外发现、合并同根因，以及不同但等效的组织方法。实际结果、尚存不足与程序检查见[本轮评阅记录](evaluation-2026-11-20.md)。本组材料已用于评阅，后续修改不得继续称其为未见测试；新一轮迁移判断应另备材料。

归档说明：历史规则文件的摘要与原集合 `sha256` 保留；公开的 `files` 仅列运行规则子集，新增 `published_collection_sha256` 只校验该子集，历史执行未重新运行。元数据范围见[行为验证索引](../../README.md)。
