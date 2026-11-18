# 参考方法与取舍

下表记录本 Skill 参考的方法及采用版本。前 11 项来自初始参考库，后两项于 2026-11-18 补充。链接锁定所读版本，便于追溯原方法；Unbot 可以独立使用。科技文本的取舍依据是原材料、学科惯例和文档功能。

| 参考项目 | 在 Unbot 中如何使用 |
| --- | --- |
| [01 · Humanizer](https://github.com/keez97/humanizer/tree/2d9a116fa9caee2c3466a7c7d419cbe02b35a470) | 分别检查篇章结构、句法和用词；从同类样稿校准作者的术语与人称。句长分布、主观反应和有意制造的瑕疵不作为编辑目标。 |
| [02 · Humanizer-ZH](https://github.com/op7418/Humanizer-zh/tree/f4518a8eab97b8bfebc66a89d34320a89bef6930) | 中文逐句判断套语是否承担限定、过渡或归属功能。对已足够清楚的句子采用原文，保护文件结构和作者立场。 |
| [03 · AI Writing Humanizer](https://github.com/ZaynJarvis/ai-writing-humanizer/tree/7e9a8096b8cb2dadbca7ffde41dc0efc4c8a4b60) | 先定位问题，再删去多余表达；需要补明指代或衔接时，只使用原材料。终稿按语义复核，不按命中项数验收。 |
| [04 · Academic Humanizer](https://github.com/ashgreat/humanizer/tree/952c8a138e29eb2cbe637b8ae8e9f6c6e2f6d627) | 让测量对象、具体方法或研究结果承载句意，将空泛的名词串还原为动作。其归纳基于特定学科的英文对照稿，第一人称、被动语态、破折号等仍按目标期刊和上下文处理。 |
| [05 · Structural Humanizer](https://github.com/NulightJens/humanizer-stack/tree/13f5c023189d428ffba726c75886ca1fd0dcba65/skills/structural-humanizer) | 逐段辨认论证功能，清理模板化铺垫和无信息小结。论文摘要中的必要重复、标准章节顺序和工程条文的并列结构应予保留。 |
| [06 · AI-Tell Detector](https://github.com/aragossa/ai-tell-detector/tree/70ab3b39699c196b0217dd266928f036193ba24f) | 只审稿时指出具体位置、句子、成因和修法；交稿前重新读终稿。外观规整、分项数量或个别高频词，都不足以单独判定表达有问题。 |
| [07 · Chinese De-AI Writing](https://github.com/tangwenwen-md/chinese-de-ai-writing/tree/d4e602910b706db71d7534945a9fdd4f9a5d9017) | 结合中文语境判断虚泛的翻转、冒号引导和评价句。保留信息主次、引文归属和警示的醒目程度；“闭环控制”等词在其技术语境中正常使用。 |
| [08 · Natural Writing](https://github.com/yyx20202020/natural-writing-skill/tree/71af993050cc0885eee98c2b421a965e7fde2b43) | 按诊断、润色或起草区分任务；分别核对可按原样匹配的片段和必须结合上下文判断的语义。相同数字互换组别、否定范围变化，都需要逐句查。 |
| [09 · Work Humanizer](https://github.com/phuryn/work-humanizer/tree/0a9065791d021f3dda695f3887cb2ae4c0eacbcf) | 双向检查信息：原文的条件和承诺在成稿中应有对应，成稿中的解释和细节在材料中应有依据。由笔记起草时保留作者的推理，改为正式书面表达。 |
| [10 · De-Slop](https://github.com/isatimur/de-slop/tree/4349a8af4116d6f02b38d62f4b19e66108c4aada) | 区分无信息套话、可以改清楚的实质论断，以及需要作者补证据的判断。前者可删，中者改写，后者标明缺口，避免把不确定的论断处理成确定事实。 |
| [11 · STE Plain Writing](https://github.com/Ryuketsukami/ste-plain-writing/tree/1052bef674ce17bef9b71a815152c6747585c168) | 工程说明使用通行词，统一对象名称，将条件与对应操作放在一起。明确责任已知的主体，保留适当的被动语态和规范效力；不将技术英语的固定句长套用于论文或中文。 |
| [12 · academic-humanizer-zh 0.6.2](https://github.com/jefeerzhang/academic-humanizer-zh/tree/0e6931c08154f46d07d70c6de9d6740256a4cdba) | 按实际功能保护学术惯例，观察作者样稿的句法、限定位置与节首写法，保留综述中的真实分歧、定义条件和方案权衡。改用自拟科技例子；不采用注入人味、词频或句长配额、人称和标点禁令，不移植其错误范例及数字保护脚本。 |
| [13 · humanizer-zh-next 2.1.0](https://github.com/Hyacehila/humanizer-zh-next/tree/0c3ee9cbba7a54b8ae180554c95a0ff906a7b8fd) | 细化中文弱动词、长定语、未知施事和概念区别；合并同层限定与重复免责，保留独立条件、负结果和真实回应；补标题复述、假范围、伪洞察和重复收尾。按体裁与编辑深度处理，独立实现 Markdown 辅助核对。通用随笔、营销口语和局部扩读规则不替代 Unbot 的科技书面语及全文终检。 |

## 本轮整合的落点与边界

- [编辑深度与证据边界](editing-modes.md)：普通润色与主张校准分开，结构调整、标题修改、证据移入、作者样稿和交付形式有明确默认值。
- [中文表达](chinese-english-style.md)、[文风审阅](style-review.md)与[分文体例子](genre-examples.md)：原规则合并补强，使用应改与应留的对照，按词句的作用判断；不建立机械禁词清零流程。
- [篇章衔接](coherence-review.md)与[审稿回复及研究计划](research-responses.md)：保留定义、前提、推理及研究状态，通用提案逻辑按需使用；具体资助项目的格式按当期实际要求核对。
- [Markdown 核对](markdown-check.md)：借鉴按类别检查原样材料的思路，脚本独立实现。结构和数量一致仍不能保证组别、步骤、否定及引用归属正确。

逐项回查初始参考库后，进一步细化了三项已有方法：借鉴 Humanizer-ZH 的材料与操作指令区分，将其推广到正文、批注、备注及恢复附件；借鉴 AI-Tell Detector 的独立终稿复核，明确复杂任务的触发情形、必要原始证据、只读意见与无独立能力时的处理；借鉴 Work Humanizer 的针对性补问，将其收束为科技稿中的关键事实缺口，不移植访谈口吻或固定提问数量。实现分别见[编辑边界](editing-modes.md)、[复核流程](review-protocol.md#复杂稿件的独立复核)与[续作记录](resume.md)。

新规则的文字和教学例按 Unbot 用途重新编写。两个项目的部分范例存在添加统计阈值、概念不等义替换或新增研究设计的问题，不能整体作为合格改稿移入。来源附带测试通过也不证明中文写作效果；本项目分别记录程序验证与实际执行的行为检查，不宣称提升比例、作者身份识别或跨模型保证。

本轮参考项目及其所列上游的版权许可见[第三方说明](../THIRD_PARTY_NOTICES.md)。该记录用于来源追溯，不是运行时依赖。
