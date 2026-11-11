# 篇章衔接样稿（编辑判断夹具）

本目录的中英文短稿供规则维护和人工复测使用。下文逐组列出审阅预期和具体问题。`generation/` 提供原始材料、合格范文及过度外推的反例。`heldout/` 收录规则对照演练和另写的短运维纪要复测，其范围见该目录说明。

自动化测试核对样稿、关键数值和符合 `finding_schema: 2` 的分类标签。评估编辑判断还需用独立稿件记录漏报和误报。`heldout/` 中的开关柜纪要复测由熟悉规则的复测者完成；线扫相机稿供规则对照练习。

依据材料起草时，同一批情境不得引入这些错误。例如，材料只提供空载测量时，生成的摘要和结论不得写成“所有工况”；材料只有时间先后时，不得为求通顺而写成因果。最小反例见 `generation/`。

机器可读的金标准见同目录 `gold.json`。建议的【大类｜具体问题】须与[审阅判据](../../../references/review-protocol.md#批注分类)中的六类一致。可执行检查见[篇章衔接审阅](../../../references/coherence-review.md)。

## 金标准

### 01-theme-jump-extrapolation

- 样稿：`01-theme-jump-extrapolation.zh.md`、`01-theme-jump-extrapolation.en.md`
- 判断：应标。【篇章与逻辑｜主题跳跃且由部件计时外推系统指标】后句主题换成未经测量的完整系统，又用“因此”宣称已经满足 20 ms 时限。中英文夹具与教学例使用同一组指标，不得写成吞吐量与毫秒时限错配。
- 英文批注时的具体问题：Theme shift used to extrapolate a system metric from component timing

### 02-juxtaposition-clear-relation

- 样稿：`02-juxtaposition-clear-relation.zh.md`、`02-juxtaposition-clear-relation.en.md`
- 判断：不应标。数量与前后变化并置且无连接词，但关系可还原为同一试点的不同方面；不得因缺少“因此”而标注。样稿不含空泛评价。数值仅作结构示意。

### 03-misused-therefore

- 样稿：`03-misused-therefore.zh.md`、`03-misused-therefore.en.md`
- 判断：应标。【篇章与逻辑｜把时间先后写成因果】材料只有先后，没有对照或机制。
- 英文批注时的具体问题：Temporal sequence written as causation

### 04-abstract-interval-sign

- 样稿：`04-abstract-interval-sign.zh.md`、`04-abstract-interval-sign.en.md`
- 判断：应标。【事实与技术｜摘要与正文的区间符号相反】同期、同一批测点、同一正方向的垂直形变速率被写成正区间和负区间。并列两个区间，请作者核实。
- 英文批注时的具体问题：Abstract and body use opposite interval signs

### 05-figure-body-value

- 样稿：`05-figure-body-value.zh.md`、`05-figure-body-value.en.md`
- 判断：应标。【事实与技术｜正文与图中的相关系数值不一致】图 3 中处理 B 的相关系数绝对值为 0.73，正文写成 0.72，两处均按相同方法保留两位小数。并列位置，请作者核实原始计算。
- 英文批注时的具体问题：Correlation values in the body and the figure disagree

### 06-dropped-noload-qualifier

- 样稿：`06-dropped-noload-qualifier.zh.md`、`06-dropped-noload-qualifier.en.md`
- 判断：应标。【篇章与逻辑｜后文丢掉了仍然有效的限定】第 3 节只测了空载工况。整机最大实测时延 7.2 ms 低于 8 ms 的验收限值，足以说明本次空载试验达标；第 5 节将结论扩大到没有测量记录的其他工况。
- 英文批注时的具体问题：Later text drops a still-valid qualifier

### 07-secondary-as-main-conclusion

- 样稿：`07-secondary-as-main-conclusion.zh.md`、`07-secondary-as-main-conclusion.en.md`
- 判断：应标。【篇章与逻辑｜结论改换了所回答的问题】主指标为整机时延，摘要与结论却把编码器耗时写成系统性能显著提升；即使两处措辞一致，也要标。至少应标换题，不能只把“显著提升”标成文风。
- 英文批注时的具体问题：Conclusion answers a different question from the declared primary endpoint

### 08-theme-not-baton-but-clear

- 样稿：`08-theme-not-baton-but-clear.zh.md`、`08-theme-not-baton-but-clear.en.md`
- 判断：不应标。对比标记加上已知对象，节标题已预告测量对象；主题位置不像“完美接力”，但论断清楚，不得因句首未重复上一句句末原词而标注。

### 09-group-value-swap

- 样稿：`09-group-value-swap.zh.md`、`09-group-value-swap.en.md`
- 判断：应标。【事实与技术｜中英文摘要的组别数值对调】中文摘要与正文为甲 12 ms、乙 18 ms，英文摘要写成甲 18 ms、乙 12 ms。并列两处摘要与正文，请作者用原始记录裁定，不得擅自改数。
- 英文批注时的具体问题：Group values are swapped between the Chinese and English abstracts

### 10-methods-packaging-aside

- 样稿：`10-methods-packaging-aside.zh.md`、`10-methods-packaging-aside.en.md`
- 判断：应标。【篇章与逻辑｜方法段混入无功能的包装说明】包装箱尺寸和瓦楞材质与电流、电压测量没有已知联系，读者无法还原它在方法中的作用。应标出该句，不要发明它与试验的关系。
- 英文批注时的具体问题：Methods section inserts an unrelated packaging aside

### 11-table-backed-abstract

- 样稿：`11-table-backed-abstract.zh.md`、`11-table-backed-abstract.en.md`
- 判断：不应标。结果段引用表 1，表中给出 0.726，摘要按约定写成 0.73。样本工况、指标和展示精度均能对上。
