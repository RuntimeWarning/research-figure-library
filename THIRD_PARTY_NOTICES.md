# 第三方素材说明

项目代码的 MIT 许可不替代素材的原始许可。

## 可公开分发的图标

- **IconPark**：官方 `@icon-park/svg@1.4.2`，采用 Apache-2.0。保留 Bytedance 的原始版权与许可文本。本站将官方图形按 multi-color 主题导出，使用深灰、蓝、白、青四种颜色；去除四个内容完全相同的别名后收录 2,654 个 SVG。原始源包不包含独立 NOTICE 文件。
- **Tabler Icons**：官方 `@tabler/icons@3.49.0`，采用 MIT。只收录 outline 系列的 5,184 个 SVG，保留原始几何与 `currentColor`。页面可以为下载版本指定颜色。
- **Microsoft Fluent Emoji**：官方仓库固定版本 `1ffb34c752ecf5d402f04cfb4b392c77f57c54bc`，采用 MIT。精选 265 个独立 Color SVG；保留 Microsoft 的版权与许可文本。
- **Phosphor Icons**：官方 `@phosphor-icons/core@2.1.1`，采用 MIT。精选 487 个 Duotone SVG，原样保留 `currentColor` 与透明图层；同一图标不重复收录其他字重。下载包的 SHA-512 完整性和逐项 SVG 的 SHA-256 已核对。

完整原文见 `dist/licenses/`，逐项来源见 `dist/data.json` 和 `dist/sources.csv`。README 的图标预览是以上图标的排版展示。

## 原创架构示意图

`dist/assets/architectures/` 中的 SVG 由本项目独立绘制，使用本项目 MIT 许可。它们根据论文事实概括数据流、关键模块和连接关系，没有复刻原论文插图的版式。来源论文仍应在学术使用中引用；示意图不代表逐层可执行实现。

生成脚本见 `scripts/generate_architectures.py`，逐图来源见素材索引。单独分发 SVG 时请保留 `dist/licenses/original-architectures-LICENSE.txt` 中的许可与版权声明。

## 论文配图

109 项配图包括原有的 90 项模块、局部图元、频谱、小波子带和特征纹理，以及新增的 19 项经典架构原论文图。它们不是本项目原创图形。原论文或代码仓库采用某种许可，不应自动推定所有论文插图、示例数据和第三方画面具有相同授权。

当前没有将这 109 项统一声明为已获得公开再分发授权。图像仅保存在本地忽略目录 `dist/assets/papers/`；公开构建不复制这些文件，并把对应记录变为来源卡片。来源、图号、裁剪/导出说明和已有的许可备注继续保留。

如果后续逐项核实某张图的再分发许可，应记录许可原文链接、作者、来源与修改说明，再明确加入公开构建的许可清单。
