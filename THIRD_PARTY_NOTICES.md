# 第三方素材说明

本项目代码与数据整理采用 [MIT](LICENSE) 许可，该许可**不替代**下列素材的原始许可。逐项来源、作者、许可与 SHA-256 见 [`dist/sources.csv`](dist/sources.csv)，许可原文见 [`dist/licenses/`](dist/licenses/)。

## 原创图元（不属于第三方素材）

`dist/assets/elements/` 中的 465 个图元由本项目用 `pipeline/elements/` 中的脚本绘制，不含任何第三方图形，采用 [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/)：可自由复制、修改、分发和商用，无需署名。

## 计算机视觉图元所用照片

`dist/assets/vision/` 中的 169 个图元由本项目生成并以 CC0 发布。其中照片类图元基于以下 CC0 / 公有领域照片与医学图像（裁剪、缩放后做分割、检测、加噪、退化、增强等处理），无需署名；为便于追溯，每个图元的详情页与 `sources.csv` 都给出原始照片链接。

| 内容 | Wikimedia Commons 文件 | 作者 | 许可 |
| --- | --- | --- | --- |
| 猫 | [Tabby cat with blue eyes-3336579.jpg](https://commons.wikimedia.org/wiki/File:Tabby_cat_with_blue_eyes-3336579.jpg) | AdinaVoicu | CC0 1.0 |
| 狗 | [Dog resting on the grass.jpg](https://commons.wikimedia.org/wiki/File:Dog_resting_on_the_grass.jpg) | Joselodos | CC0 1.0 |
| 翠鸟 | [Eisvogel kingfisher.jpg](https://commons.wikimedia.org/wiki/File:Eisvogel_kingfisher.jpg) | Frank-2.0 | CC0 1.0 |
| 汽车 | [Auto in car sharing a Livorno.jpg](https://commons.wikimedia.org/wiki/File:Auto_in_car_sharing_a_Livorno.jpg) | Marcxosm | CC0 1.0 |
| 街景 | [Traffic and pedestrians on Calle Velásquez near Catedral San Nicolás de Bari, Barcelona, Venezuela.jpg](https://commons.wikimedia.org/wiki/File:Traffic_and_pedestrians_on_Calle_Velásquez_near_Catedral_San_Nicolás_de_Bari,_Barcelona,_Venezuela.jpg) | Wilfredor | CC0 1.0 |
| 道路 | [Streets in Les Rivières, Quebec City (16).jpg](https://commons.wikimedia.org/wiki/File:Streets_in_Les_Rivières,_Quebec_City_(16).jpg) | Wilfredor | CC0 1.0 |
| 室内 | [Living room (Unsplash).jpg](https://commons.wikimedia.org/wiki/File:Living_room_(Unsplash).jpg) | Jarosław Ceborski | CC0 1.0 |
| 城市航拍 | [Seattle City Aerial View Sounds Peugeot.jpg](https://commons.wikimedia.org/wiki/File:Seattle_City_Aerial_View_Sounds_Peugeot.jpg) | Yourusernamewillbepublic2 | CC0 1.0 |
| 运动人物 | [Walking Rugby.jpg](https://commons.wikimedia.org/wiki/File:Walking_Rugby.jpg) | Back ache | CC0 1.0 |
| 胸部 X 光片 | [Chest Xray PA 3-8-2010.png](https://commons.wikimedia.org/wiki/File:Chest_Xray_PA_3-8-2010.png) | Stillwaterising | CC0 1.0 |
| 脑部 CT | [Computed tomography of human brain - large.png](https://commons.wikimedia.org/wiki/File:Computed_tomography_of_human_brain_-_large.png) | Department of Radiology, Uppsala University Hospital | CC0 1.0 |
| 脑部 MRI | [T1-weighted-MRI.png](https://commons.wikimedia.org/wiki/File:T1-weighted-MRI.png) | Mim.cis | 公有领域 |

另有 7 张来自 [scikit-image 示例数据](https://scikit-image.org/docs/stable/api/skimage.data.html)：宇航员 Eileen Collins（NASA，公有领域）、咖啡杯（Rachel Michetti，CC0）、摄影师（Lav Varshney，CC0）、眼底图像（Mikael Häggström，CC0）、皮肤 H&E 切片（Kilbad，公有领域）、荧光细胞核（David Root，CC0）、小鼠肾组织共聚焦图像（Genevieve Buckley，CC0）。

## 收集的物件

`dist/assets/collected/` 中的 450 个物件来自下列开源图库，保留原许可。逐项的原始文件链接见 `dist/sources.csv` 的 `source_url` 列。

| 来源 | 版本 | 许可 | 收录与处理 | 署名 |
| --- | --- | --- | --- | --- |
| [Fluent Emoji](https://github.com/microsoft/fluentui-emoji)（Microsoft） | 提交 `1ffb34c7` | MIT（Copyright (c) Microsoft Corporation） | 283 个 3D 版 PNG，只裁去透明留白；人物取默认肤色；中文名取自 Unicode CLDR | 3D emoji from Microsoft Fluent Emoji (https://github.com/microsoft/fluentui-emoji), MIT License. |
| [3dicons](https://github.com/realvjy/3dicons)（Vijay Verma） | 提交 `8884d59e`，官方 CDN 的 v1 dynamic 视角 | [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) | 118 个（60 种 × 彩色 / 白色黏土），只裁去透明留白 | 无需署名 |
| [Isoflow isopacks](https://github.com/markmanx/isopacks)（Mark Mankarious） | 提交 `ab717516` | MIT（Copyright 2023 Mark Mankarious） | 34 个 `collections/isoflow` SVG，未改动；未收录含文字的 DNS、支付卡与刷卡机图标 | Isometric icon from Isoflow isopacks by Mark Mankarious (https://github.com/markmanx/isopacks), MIT License. |
| [NN-SVG](https://github.com/alexlenail/NN-SVG)（Alexander LeNail） | 提交 `d72cf124` | MIT（Copyright (c) 2018 Alexander Lenail） | 15 个，由 `pipeline/collected/nnsvg.mjs` 调用 NN-SVG 生成，不带标注 | Drawn with NN-SVG (LeNail, JOSS 2019, https://github.com/alexlenail/NN-SVG), MIT License. |

- MIT 来源的版权声明与许可原文在 `dist/licenses/`（`fluent-emoji-LICENSE.txt`、`isoflow-LICENSE.txt`、`nn-svg-LICENSE.txt`），3dicons 的 CC0 声明在 `3dicons-LICENSE.txt`。

## 论文原图

`dist/assets/papers/` 中的 289 张论文原图取自论文 PDF（个别来自论文的官方代码仓库或文档），按原样裁剪，未重绘、未改色。它们不是本项目的原创作品，版权属于原作者或出版方。

- 每张图对应的论文、作者、出处、arXiv 版本与页码记录在 `dist/data.json` 的 `sources` 中，页面详情可直接打开原文 PDF 对应页。
- 许可按论文在 arXiv 上由作者选择的许可记录：289 张中 229 张为 [arXiv 非独占分发许可](https://arxiv.org/licenses/nonexclusive-distrib/1.0/license.html)（作者保留版权，仅授权 arXiv 分发），35 张为 CC BY 4.0，10 张为 CC BY-NC-ND 4.0，5 张为 CC BY-NC-SA 4.0，3 张为 CC BY-SA 4.0，1 张为 CC0 1.0；其余 6 张来自期刊、会议论文集或官方代码仓库（IEEE、MIT Press、AAAS、NeurIPS 论文集版权，或仓库的 MIT / BSD-3-Clause 许可）。
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
