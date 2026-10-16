# 第三方素材说明

本项目代码与数据整理采用 [MIT](LICENSE) 许可，该许可**不替代**下列素材的原始许可。逐项来源、作者、许可与 SHA-256 见 [`dist/sources.csv`](dist/sources.csv)，许可原文见 [`dist/licenses/`](dist/licenses/)。

## 论文图元与原图

`dist/assets/elements/` 中的 361 个图元和 `dist/assets/papers/` 中的 289 张论文原图、30 个早期图元，均取自论文 PDF（个别来自论文的官方代码仓库或文档）：原图按原样裁剪；矢量图元是从原插图中分离出的一组原始路径，位图图元按嵌入位图的原始分辨率导出，均未重绘、未改色。它们不是本项目的原创作品，版权属于原作者或出版方。

- 每项对应的论文、作者、出处、arXiv 版本与页码记录在 `dist/data.json` 的 `sources` 中，页面详情可直接打开原文 PDF 对应页。
- 许可按论文在 arXiv 上由作者选择的许可记录：图元与原图共 680 项，其中 553 项为 [arXiv 非独占分发许可](https://arxiv.org/licenses/nonexclusive-distrib/1.0/license.html)（作者保留版权，仅授权 arXiv 分发），61 项为 CC BY 4.0，35 项为 CC BY-NC-ND 4.0，13 项为 CC BY-NC-SA 4.0，9 项为 CC BY-SA 4.0，2 项为 CC0 1.0；其余 7 项来自期刊、会议论文集或官方代码仓库（IEEE、MIT Press、AAAS、NeurIPS 论文集版权，或仓库的 MIT / BSD-3-Clause 许可）。
- 本仓库收录这些图，用于学术检索、比较与介绍，并在每一项标明出处。再次使用（论文、课件、出版物等）时，请引用原论文，并按原许可或出版方规定使用：NC 表示仅限非商业用途，ND 表示不得改编，arXiv 非独占许可与出版方版权的图片需要按出版方规定取得授权。arXiv 的说明见 [Reuse of arXiv content](https://info.arxiv.org/help/license/reuse.html)。
- 权利人如希望调整署名或移除某张图，请在 [Issues](https://github.com/RuntimeWarning/research-figure-library/issues) 中说明，我们会尽快处理。

## 图标

| 图标集 | 版本 | 许可 | 收录说明 |
| --- | --- | --- | --- |
| [IconPark](https://github.com/bytedance/IconPark) | `@icon-park/svg` 1.4.2 | Apache-2.0 | 2,654 个，按 multi-color 主题导出，去除 4 个内容完全相同的别名 |
| [Tabler Icons](https://github.com/tabler/tabler-icons) | `@tabler/icons` 3.49.0 | MIT | 5,184 个 outline 图标，保留原始几何与 `currentColor` |
| [Phosphor Icons](https://github.com/phosphor-icons/core) | `@phosphor-icons/core` 2.1.1 | MIT | 1,432 个 Duotone 图标，不含品牌标志 |
| [Fluent Emoji](https://github.com/microsoft/fluentui-emoji) | 提交 `1ffb34c7` | MIT | 1,587 个 Color SVG，默认肤色，不含国旗；中文名取自 Unicode CLDR |
| [Fluent System Icons](https://github.com/microsoft/fluentui-system-icons) | `@fluentui/svg-icons` 1.1.343 | MIT | 2,896 个 Regular 图标与 199 个 Color 图标 |
| [Material Design Icons](https://github.com/Templarian/MaterialDesign-SVG) | `@mdi/svg` 7.4.47 | Apache-2.0（Pictogrammers Free License） | 7,188 个，不含已弃用图标与品牌标志 |
| [Carbon Icons](https://github.com/carbon-design-system/carbon) | `@carbon/icons` 11.90.0 | Apache-2.0 | 2,505 个，不含品牌、IBM 产品与 Watson 标志 |
| [Carbon Pictograms](https://github.com/carbon-design-system/carbon) | `@carbon/pictograms` 12.86.0 | Apache-2.0 | 1,485 个，不含 IBM、Red Hat 与第三方标志 |
| [Health Icons](https://github.com/resolvetosavelives/healthicons) | `healthicons` 2.0.0 | MIT | 690 个 Filled 图标 |
| [Bioicons](https://github.com/duerrsimon/bioicons) | 提交 `d29e766e` | 逐项：CC0 1.0、CC BY 3.0、CC BY 4.0、MIT | 2,282 个；不收录 CC BY-SA、BSD 标志、内嵌位图或超过 300 KB 的文件 |

处理方式：

- 新增图标在构建时去除注释、元数据、编辑器属性、脚本、事件属性与外部引用；单色图标的黑色填充统一改为 `currentColor`，以便页面改色。图形本身未修改。
- **Bioicons 的 CC BY 图标须署名**：每个图标的作者与许可显示在详情页，并列在 `sources.csv` 的 `authors` 与 `license` 列；作者主页见 `dist/licenses/bioicons-LICENSES.txt`。
- 各图标集保留原始版权与许可文本。Material Design Icons 与 Carbon 的 Apache-2.0 许可、Health Icons 与 Fluent 的 MIT 许可等原文均在 `dist/licenses/`。

## 中文名称数据

- Fluent Emoji 的中文名称与关键词来自 [Unicode CLDR](https://cldr.unicode.org/) 注释数据（`cldr-annotations-full` / `cldr-annotations-derived-full` 48.2.0，Unicode License V3）。
- 其余图标的中文名称由本项目词表 `pipeline/icons/zh_terms.tsv` 生成，属于本项目 MIT 许可范围。
