# 第三方来源与许可

本轮中文编辑规则参考以下固定版本，具体采用范围与取舍见 [参考方法](references/editorial-sources.md)。Unbot 的新增例子、行为材料和 Markdown 核对脚本独立编写，未引入上游运行依赖。以下保留参考项目的版权与许可，并区分其继承来源；这些第三方声明不改变各项目自身的授权范围。

## academic-humanizer-zh

来源：[jefeerzhang/academic-humanizer-zh](https://github.com/jefeerzhang/academic-humanizer-zh/tree/0e6931c08154f46d07d70c6de9d6740256a4cdba)，0.6.2。原始许可如下。

MIT License

Copyright (c) 2026 jefeerzhang (https://github.com/jefeerzhang/academic-humanizer-zh)

This fork builds on academic-humanizer by AIScientists-Dev
(https://github.com/AIScientists-Dev/academic-humanizer, MIT; portions Copyright (c) 2026
AIScientists-Dev), "humanizer" by blader (https://github.com/blader/humanizer, MIT), and adopts
standards from ARMS (https://github.com/koaeraser/ARMS). See Acknowledgments in README.md.

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and
associated documentation files (the "Software"), to deal in the Software without restriction,
including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so,
subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED.

## humanizer-zh-next

来源：[Hyacehila/humanizer-zh-next](https://github.com/Hyacehila/humanizer-zh-next/tree/0c3ee9cbba7a54b8ae180554c95a0ff906a7b8fd)，2.1.0。原始许可如下。

MIT License

Copyright (c) 2026 humanizer-zh-next contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## humanizer-zh-next 所列继承来源

下文是该项目在上述提交中的第三方说明，保留其原有采用范围、署名和许可。文中的“本项目”指 humanizer-zh-next，不表示 Unbot 单独引入了其所有分支或全部上游内容。为便于独立分发，维护记录的相对链接已换成该提交的完整链接。

### 上游原始 Third-Party Notices

Humanizer-zh-next 选择性翻译、改编以下 MIT 项目的编辑规则、示例组织和方法。本文件记录本轮采用的固定提交及原始版权；整合范围与取舍见 [上游整合记录](https://github.com/Hyacehila/humanizer-zh-next/blob/0c3ee9cbba7a54b8ae180554c95a0ff906a7b8fd/docs/upstream-sources.md)。

#### blader/humanizer

- Commit: `225a6f39ac85f76ee48dbad772ea4abe4ed6c9d8`（3.1.0）
- 采用范围：通用编辑模式、信息保留、文件模式和处理流程；旧基线为 `1b48564898e999219882660237fde01bf4843a0f`（2.8.2）。
- Copyright (c) 2025 Siqi Chen

#### op7418/Humanizer-zh

- Commit: `f4518a8eab97b8bfebc66a89d34320a89bef6930`
- 采用范围：中文语义与限定保护、反例、行为测试和结构检查的思路；旧基线为 `91f3d394db8419c20d67ebe22a96cf8fee0a404b`。本项目测试和辅助脚本重新实现。
- Copyright (c) 2026 歸藏

#### hardikpandya/stop-slop

- Commit: `8da1f030185bdfe8471220585162991eaeb970e9`
- 采用范围：无信息铺垫、装饰性收尾和抽象行动者的检查。
- Copyright (c) 2025 Hardik Pandya

#### AIScientists-Dev/academic-humanizer

- Commit: `94b88b23703bed7df507acae7d6d5876209a0cdf`（0.3.3）
- 采用范围：承接本项目 1.3.0 的中文学术适配，保留学术语体、数字引用、证据审阅和提案可行性；学术与基金分支重新组织。
- Copyright (c) 2026 AIScientists-Dev
- 保留上游原始致谢：This work builds on "humanizer" by blader (https://github.com/blader/humanizer, MIT) and adopts standards from "ARMS" (https://github.com/koaeraser/ARMS); see the Acknowledgments in README.md.

#### jiji262/humanizer-chinese

- Commit: `1d6c08e10fbfe0e1b36ac784834451c6aae0a92c`（1.0.0）
- 采用范围：中文句法、弱动词、无主句、语域和防假口语，直接融入主 SKILL.md；未复制研究统计、模型指纹或未经材料支持的示例。
- Copyright (c) 2025 Siqi Chen
- Copyright (c) 2026 jiji262 (Chinese localization)

#### coreyhaines31/marketingskills

- Commit: `26f7342b26670e5581b48cd64e9dba3eb8a0c3aa`（copy-editing 2.1.0）
- 采用范围：`skills/copy-editing/` 的分维度审阅方法与证据检查；按本项目保真和体裁范围重写。
- Copyright (c) 2025 Corey Haines

#### deathcats4/scientific-manuscript-editor

- Commit: `9371352cf7153076065421e8686bf1139f61ddc6`（元数据版本 1.9.0，含 2026-10-08 主分支更新）
- 采用范围：科学主张与必要限定、重复防御、学术表达保护、章节限定分布及删句后的论证作用核对；按本项目中文编辑边界改写，教学示例与行为案例重新编写。
- Copyright (c) 2026 deathcats4

以上项目均以 MIT License 发布。未整合的候选和观察性网页不作为 MIT 内容纳入本项目。各项原始版权声明及以下许可文本随分发保留：

---

MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

#### academic-humanizer 的原始许可文本

该上游许可采用较短的免责声明，以下同时保留其原文：

MIT License

Copyright (c) 2026 AIScientists-Dev

This work builds on "humanizer" by blader (https://github.com/blader/humanizer, MIT) and adopts
standards from "ARMS" (https://github.com/koaeraser/ARMS); see the Acknowledgments in README.md.

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and
associated documentation files (the "Software"), to deal in the Software without restriction,
including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so,
subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED.
