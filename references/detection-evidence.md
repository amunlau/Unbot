# 审阅结论能支持到哪一步

查阅日期为 2026-11-10。资料覆盖科研论文、跨语言评测、出版行业博客、工具维护者论坛和标注规范。以下证据用于设计编辑判断，并未用来给 Unbot 校准作者身份分类器。

## 语料趋势与单句判断

Kobak 等分析 2010–2024 年超过 1,500 万篇 PubMed 摘要，观察到部分风格词的总体频率随大语言模型普及而变化。这适合研究群体的写作习惯。一篇专业文章本来就可能使用相同词汇，单句中出现它们并不能给出作者使用工具的概率。Unbot 只在词语影响了本句的精度、信息量或语域时提出修改。[原始论文](https://pubmed.ncbi.nlm.nih.gov/40601754/)

人也会看错。Gao 等让盲评者区分医学期刊原摘要与按题目生成的摘要，评者认出了 68% 的生成摘要，同时将 14% 的原摘要误判为生成文本。研究对象是特定时期的英文医学摘要；这两个数字不能挪用作中文、工程文档或本 Skill 的准确率。审阅时应指出具体用词或推理，而非以“读起来像”作为批注理由。[原始论文](https://pubmed.ncbi.nlm.nih.gov/37100871/)

## 语言、领域和评测条件

- Liang 等报告了多种检测器在非英语母语作者样本上的系统性误报。翻译腔可以作为表达问题讨论，作者的语言背景、词汇简单或句法规整不构成生成来源证据。[作者论文](https://arxiv.org/abs/2304.02819)
- MULTITuDE 包含 11 种语言（含中文）与 8 种多语模型，专门区分训练见过与未见过的语言、模型。RAID 在不同生成器、生成设置和文体上评测检测器，显示测试环境改变会影响可靠性。因此英文校对经验可以提供候选线索，不能直接变成中文阈值。[MULTITuDE](https://aclanthology.org/2023.emnlp-main.616/) · [RAID](https://aclanthology.org/2024.acl-long.674/)
- Weber-Wulff 等比较了多种检测工具，并考察翻译、改写后的输入。产品自己的说明也要求结合具体文本和人的判断。无论某个基准测试成绩如何，Unbot 都没有经过面向用户原稿分布的来源识别验证。[工具比较研究](https://link.springer.com/article/10.1007/s40979-023-00146-z) · [Turnitin 产品说明](https://guides.turnitin.com/hc/en-us/articles/22774058814093-Using-the-AI-Writing-Report)

## 实践中的争议如何转成编辑动作

- 出版业博客对 COPE 论坛讨论的记录强调，处理疑问时应具体说明担心什么，按证据强度采取相称行动。Unbot 将这一经验用于“待核依据”：写清哪项来源或比较条件未能找到，避免给作者动机定性。这是实践讨论，不是误报率研究。[论坛讨论纪要](https://scholarlykitchen.sspnet.org/2025/08/25/from-detection-to-disclosure-key-takeaways-on-ai-ethics-from-copes-forum/)
- LanguageTool 社区讨论过是否应提示句首的 *And* / *But*；具体上下文会改变规则的价值。这类讨论可发现误报案例，不能证明人或模型偏爱某种句式。新增规则应配一条“外形相同、使用合理”的反例。[维护者与使用者讨论](https://forum.languagetool.org/t/bad-style-rules-using-and-and-but-to-start-a-sentence/366)
- MIT EECS Communication Lab 将结果段的写作任务落实为如何从图表或定理读出发现。Unbot 先核对图表能支持哪一句、单位与比较范围是否一致，再考虑简化措辞。这样“显著提升”可以被具体审阅，图注中的必要重复也有了保留依据。[Results 写作指南](https://mitcommlab.mit.edu/eecs/commkit/journal-article-results/)

## 可复查的批注

W3C 区分逐字引文选择与位置选择，同时指出重复引文可能产生多个匹配。Unbot 借鉴这一区分，额外固定源文件字节指纹，同段重复则要求精确偏移；不将一次选择扩展至全部同文位置。Markdown 代码、链接和原始 HTML 有独立语法，因此原文痕迹在审阅视图中按转义后的文字展示。这里只借鉴定位原则，不声称实现整个 Web Annotation 标准。[W3C Web Annotation](https://www.w3.org/TR/annotation-model/#text-quote-selector) · [CommonMark 规范](https://spec.commonmark.org/0.31.2/)
