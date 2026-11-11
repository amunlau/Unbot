"""Validate editorial categories and render the label shown on each finding."""

FINDING_SCHEMA = 2
CATEGORIES = {
    "style": ("AI味与文风", "Formulaic wording and style"),
    "logic": ("篇章与逻辑", "Logic and coherence"),
    "format": ("格式与排版", "Formatting and layout"),
    "language": ("文字与语法", "Language and grammar"),
    "technical": ("事实与技术", "Factual and technical accuracy"),
    "evidence": ("依据待核", "Evidence to verify"),
}


def review_findings(manifest):
    """Yield each locator and its display text, retaining unversioned comments."""
    versioned = "finding_schema" in manifest
    version = manifest.get("finding_schema")
    if versioned and (type(version) is not int or version != FINDING_SCHEMA):
        raise ValueError(f"不支持的 finding_schema（应为整数 {FINDING_SCHEMA}）。")
    language = manifest.get("review_language", "zh")
    if language not in ("zh", "en"):
        raise ValueError("review_language 应为 zh 或 en。")
    findings = manifest.get("findings")
    if not isinstance(findings, list):
        raise ValueError("findings 应为数组。")

    for number, item in enumerate(findings, 1):
        if not isinstance(item, dict):
            raise ValueError(f"第 {number} 条意见须为对象。")
        body = item.get("comment")
        if not isinstance(body, str) or not body.strip():
            raise ValueError(f"第 {number} 条意见须有非空 comment。")
        if not versioned and "category" not in item and "issue" not in item:
            yield item, body
            continue
        category = item.get("category")
        if not isinstance(category, str) or category not in CATEGORIES:
            raise ValueError(f"第 {number} 条意见的 category 应为 {', '.join(CATEGORIES)} 之一。")
        issue = item.get("issue")
        if not isinstance(issue, str) or not issue.strip() or len(issue.strip().splitlines()) != 1:
            raise ValueError(f"第 {number} 条意见的 issue 须用一行文字指明具体问题。")
        issue = issue.strip()
        zh, en = CATEGORIES[category]
        if issue.casefold() in (category, zh.casefold(), en.casefold()):
            raise ValueError(f"第 {number} 条意见的 issue 须说明该类别下的具体问题。")
        label = f"【{zh}｜{issue}】" if language == "zh" else f"[{en} | {issue}]"
        yield item, f"{label} {body.strip()}"
