<p align="center"><img src="dist/favicon.svg" width="76" alt="研图标志"></p>

<h1 align="center">研图 · Figure Atlas</h1>

<p align="center">论文配图图元库</p>

画模型结构图时最常用的那些小元素——特征图、张量、卷积核、Token、注意力掩码、网络模块、运算符、箭头、雷达回波——按**同一套等轴测风格和 8 种配色**画好，共 290 个。拼在一起就是一张风格统一的模型图；每个都是可编辑 SVG，**CC0 授权**，论文、课件和商用都可以直接用，无需署名。另附 289 张按原样裁剪的经典论文原图和 28,102 个开源科研图标。

[在线检索](https://runtimewarning.github.io/research-figure-library/) · [GitHub 仓库](https://github.com/RuntimeWarning/research-figure-library) · [完整来源清单](dist/sources.csv)

![研图首页](docs/screenshot-home.jpg)

## 素材规模

| 集合 | 数量 | 说明 |
| --- | ---: | --- |
| **原创图元** | **290** | 统一风格的通用配图元素，全部为可编辑 SVG + 透明 PNG，CC0 1.0 |
| 论文原图 | 289 | 来自 216 篇论文（1997–2025），覆盖 21 个方向；按原样裁剪，不重绘、不改色 |
| 科研图标 | 28,102 | 10 个开源图标集，统一为 20 个中文分类，可按图标集筛选 |
| **合计** | **28,681** | 每项素材在 `dist/sources.csv` 中列出文件、来源、许可与 SHA-256 |

### 图元

![原创图元](docs/screenshot-elements.jpg)

| 分类 | 数量 | 内容 |
| --- | ---: | --- |
| 特征图 | 61 | 6×6 / 4×4 / 3×3 特征图（普通与高亮）、热力特征图、对角 / 渐变 / 环形响应图、下采样与上采样阶段序列 |
| 卷积与采样 | 37 | 卷积运算示意（卷积核窗口投影到输出）、3×3 / 5×5 / 1×1 卷积核、最大 / 平均池化、空洞卷积、感受野、图像分块、上采样、深度可分离卷积、输入图像、分割掩码、深度图、检测框 |
| 张量与通道 | 34 | 三维张量 3×3×3、扁平张量、高通道张量、多通道堆叠、RGB 三通道、通道拼接 |
| 网络层与模块 | 32 | Conv、BatchNorm、ReLU、Attention、Multi-Head Attention、MLP、LayerNorm、Softmax、Embedding 等 18 种带标签模块，编码器 / 解码器梯形，残差单元，全连接网络，单个神经元 |
| 运算符与箭头 | 32 | 加、乘、逐元素乘、Sigmoid、ReLU、拼接、求和、Softmax 运算符，右 / 下 / 双向 / 折线箭头 |
| Token 与向量 | 31 | Token 序列、带分类 Token 的序列、多模态 Token、特征向量（横 / 竖）、嵌入矩阵、Q / K / V |
| 注意力与矩阵 | 24 | 全注意力、因果、滑动窗口、空洞窗口、分块局部、全局 + 局部、跨步稀疏注意力掩码，注意力热图，相似度矩阵，Token 间注意力连接 |
| 信号与噪声 | 16 | 时间序列面板、多变量时间序列、高斯噪声、逐步加噪序列、频谱柱状图、小波四子带 |
| 时空与气象 | 12 | 地球经纬网格、地球与云团、雷达回波图、雷达回波时间序列、全球温度场、时空张量 |
| 图与点云 | 11 | 图结构、邻居聚合示意、点云、嵌入空间聚类 |

单色元素提供 8 种配色（蓝、青、橙、紫、绿、珊瑚红、石墨灰、琥珀黄），可以按颜色搭配出层次。SVG 里每个面、每个格子都是独立图形：在 PowerPoint、Illustrator、Inkscape 或 draw.io 中可以直接改色、增删格子、改尺寸，模块上的文字也可直接编辑。

所有图元由 [`pipeline/elements/generate.py`](pipeline/elements/generate.py) 用同一个正交相机和配色表生成（绘图工具见 [`style.py`](pipeline/elements/style.py)），因此新增元素也会保持一致的风格。

### 论文原图覆盖的方向

![论文原图按方向浏览](docs/screenshot-papers.jpg)

| 方向 | 代表模型 |
| --- | --- |
| 卷积网络与轻量化 | LeNet-5、AlexNet、VGG、GoogLeNet / Inception v3–v4、ResNet、ResNeXt、DenseNet、Xception、SENet、MobileNet v1–v3、ShuffleNet、EfficientNet、ConvNeXt、RepVGG、HRNet、GhostNet |
| 注意力模块 | CBAM、ECA、Coordinate Attention、Non-local、GCNet、SKNet、BAM、Triplet Attention、DANet、Attention Gate |
| 视觉 Transformer | ViT、Swin、DeiT、PVT、MLP-Mixer、CvT、MobileViT、PoolFormer、CoAtNet、MaxViT、Vision Mamba |
| 检测与分割 | R-CNN 系列、YOLO、SSD、RetinaNet、FPN、DETR、Deformable DETR、FCOS、RT-DETR、Grounding DINO、FCN、U-Net / UNet++ / 3D U-Net / V-Net、DeepLabv3+、PSPNet、SegFormer、Mask2Former、SAM / SAM 2、TransUNet、Swin-Unet、UNETR |
| 序列、语言与大模型 | Seq2Seq、Bahdanau 注意力、Transformer、BERT、GPT-3、T5、BART、XLNet、Transformer-XL、Longformer、MoE、Switch Transformer、LoRA、Adapter、Prefix-Tuning、InstructGPT、RAG、FlashAttention、Mamba、RWKV、RetNet |
| 生成与扩散 | GAN、cGAN、DCGAN、pix2pix、CycleGAN、StyleGAN 1–2、VAE、VQ-VAE、VQGAN、Glow、RealNVP、DDPM、DDIM、Score SDE、Latent Diffusion、ControlNet、DiT、unCLIP、Consistency Models |
| 自监督与多模态 | SimCLR、MoCo、BYOL、SimSiam、Barlow Twins、DINO、BEiT、MAE、CLIP、BLIP / BLIP-2、LLaVA、Flamingo、ViLT |
| 时空、气象与时间序列 | ConvLSTM、TrajGRU、PredRNN、PhyDNet、SimVP、Earthformer、DGMR、SmaAt-UNet、LDCast、PreDiff、CasCast、DiffCast、FourCastNet、Pangu-Weather、GraphCast、FengWu、FuXi、ClimaX、MetNet、Informer、Autoformer、FEDformer、PatchTST、TimesNet、iTransformer、DLinear、TCN、WaveNet、N-BEATS、TFT、DeepAR |
| 图、三维与其他 | GCN、GAT、GraphSAGE、Graphormer、DCRNN、STGCN、Graph WaveNet、PointNet / PointNet++、DGCNN、VoxelNet、NeRF、3D Gaussian Splatting、FNO、GFNet、WTConv、SRCNN、SRGAN、ESRGAN、Restormer、RAFT、PWC-Net、CapsNet、Neural ODE、STN、MAML |

### 图标集

| 图标集 | 数量 | 风格 | 许可 |
| --- | ---: | --- | --- |
| [Material Design Icons](https://pictogrammers.com/library/mdi/) | 7,188 | 实心，可改色 | Apache-2.0 |
| [Tabler Icons](https://tabler.io/icons) | 5,184 | 线性，可改色 | MIT |
| [Fluent System Icons](https://github.com/microsoft/fluentui-system-icons) | 3,095 | 线性 2,896 + 彩色 199 | MIT |
| [IconPark](https://github.com/bytedance/IconPark) | 2,654 | 多色 | Apache-2.0 |
| [Carbon Icons](https://carbondesignsystem.com/elements/icons/library/) | 2,505 | 实心，可改色 | Apache-2.0 |
| [Bioicons](https://bioicons.com) | 2,282 | 生物与实验插图 | CC0 / CC BY 3.0 / CC BY 4.0 / MIT（逐项，含作者） |
| [Fluent Emoji](https://github.com/microsoft/fluentui-emoji) | 1,587 | 彩色拟物 | MIT |
| [Carbon Pictograms](https://carbondesignsystem.com/elements/pictograms/library/) | 1,485 | 线描插画，可改色 | Apache-2.0 |
| [Phosphor Icons](https://phosphoricons.com) | 1,432 | 双色，可改色 | MIT |
| [Health Icons](https://healthicons.org) | 690 | 医疗实心，可改色 | MIT |

品牌标志、IBM 产品图标与国旗表情不收录；同一图标只收录一种字重。Fluent Emoji 的中文名称来自 Unicode CLDR，其余图标的中文名由 `pipeline/icons/zh_terms.tsv` 词表生成，英文原名始终保留，可直接用英文检索。

## 功能

- **一个搜索框**：搜索中文名、英文名、模型简称、作者、原文图注和标签；`U-Net`、`unet`、`UNet` 都能命中。按 `/` 聚焦搜索框。
- **分类与筛选**：图元 10 类、论文原图 21 个方向、图标 20 类；可只看完整架构图、附矢量文件的原图、可改色图标或科研常用图标。
- **论文原图详情**：原文图注、论文主页、直达原文 PDF 对应页、作者与许可；一键复制 BibTeX 或引用文本；下载 PNG，以及可用时的 SVG / PDF。
- **图标改色与导出**：单色图标可在网格中统一改色，详情页可选色后下载 SVG、复制 SVG 代码，或导出 256–2048 px 的透明 PNG。
- **收藏与分享**：收藏保存在当前浏览器；搜索条件写入网址，详情页可用 `#素材编号` 直接分享。
- **浅色 / 深色主题**，桌面与手机布局，全部为静态文件，无需后端或前端构建工具。

![论文原图详情](docs/screenshot-detail.jpg)

![图标检索与改色](docs/screenshot-icons.jpg)

## 本地使用

只需要 Python 3.9 或更新版本，不依赖第三方包。

```bash
git clone https://github.com/RuntimeWarning/research-figure-library.git
cd research-figure-library
python scripts/serve.py
```

Windows 可直接双击根目录的 **`启动检索.cmd`**。浏览器打开 <http://127.0.0.1:8766/>，终端窗口关闭或按 `Ctrl+C` 后服务停止；端口被占用时运行 `python scripts/serve.py --port 8767`。请通过本地服务访问，直接双击 `dist/index.html` 会因浏览器的本地文件限制而无法加载索引。

## 论文原图是如何得到的

1. `pipeline/papers/fetch.py` 按 `papers.json` 中的 arXiv 编号下载固定版本的 PDF，并通过 arXiv API 与 OAI-PMH 记录标题、作者、版本和作者选择的许可。
2. `pipeline/papers/extract.py` 在 PDF 中定位图注（"Figure 3:"、"Table 1:" 等），自动排除正文、页眉页脚和图注本身，只取图形区域；个别排版特殊的图在 `figures.json` 中给出手工裁剪框。
3. 每张图导出 300 dpi PNG（以内嵌位图为主的图按原生分辨率渲染）、WebP 缩略图；矢量图在渲染逐像素比对一致时另存 SVG，紧凑时另存单页 PDF。
4. `pipeline/papers/catalog.py` 读取原文图注并合并元数据。每张原图都经过目检核对，确认没有带入正文、页眉或相邻的图。

裁剪只改变画幅，不重绘、不改色、不增删图中内容。早期由本项目手工绘制的 21 张架构示意图已全部删除，由对应论文的原图替代。

## 使用须知与许可

本项目自行编写的检索页面、构建脚本与数据整理采用 [MIT](LICENSE) 许可；**原创图元**（`dist/assets/elements/`）采用 [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/deed.zh-hans)，可自由使用、修改、商用，无需署名。第三方素材**不在**上述许可范围内：

- **图标**保留各自的开源许可，许可原文在 [`dist/licenses/`](dist/licenses/)。Bioicons 中 CC BY 图标须按条目注明作者，作者与许可显示在详情页和 `sources.csv` 中。
- **论文原图**的版权属于原作者或出版方。每张图的许可按论文在 arXiv 上的选择记录：289 张中 229 张为 arXiv 非独占分发许可，35 张为 CC BY 4.0，另有 CC BY-SA、CC BY-NC-SA、CC BY-NC-ND、CC0 及出版方版权等，详情页会标出 NC（非商业）与 ND（禁止改编）等限制。本仓库收录这些原图用于学术检索与介绍；在论文、课件或出版物中使用时，请引用原论文，并按原许可或出版方规定取得授权。
- 如果你是论文作者或权利人，希望调整或移除某张图，请[提交 Issue](https://github.com/RuntimeWarning/research-figure-library/issues)，我们会尽快处理。

详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 项目结构

```text
research-figure-library/
├── dist/                         # 发布到 GitHub Pages 的静态站点
│   ├── index.html · style.css · app.js · favicon.svg · og-image.jpg（分享卡片）
│   ├── data.json                 # 页面索引：论文原图记录 + 图标表
│   ├── sources.csv               # 每项素材的文件、来源、作者、许可与 SHA-256
│   ├── licenses/                 # 各图标集的许可原文
│   └── assets/
│       ├── elements/             # 原创图元 SVG / PNG 与 thumbs/ 缩略图
│       ├── papers/               # 论文原图 PNG / SVG / PDF 与 thumbs/ 缩略图
│       └── icons/<图标集>/        # 按图标集分目录的 SVG
├── pipeline/                     # 素材构建流程（需要 PyMuPDF 等，见 requirements.txt）
│   ├── papers/                   # 论文清单、下载、裁剪与元数据
│   ├── elements/                 # 原创图元：style.py 绘图工具，generate.py 元素清单与生成
│   ├── icons/                    # 图标下载、清洗、分类、中文名词表
│   └── catalog.py                # 生成 dist/data.json 与 dist/sources.csv
├── scripts/
│   ├── serve.py                  # 本地检索服务（仅标准库）
│   └── validate.py               # 索引、文件、SVG 安全与哈希校验（仅标准库）
├── docs/                         # README 截图
└── .github/workflows/pages.yml   # 校验后部署 GitHub Pages
```

## 更新素材

```bash
pip install -r pipeline/requirements.txt
python pipeline/papers/fetch.py       # 下载论文 PDF 与元数据（缓存在 .cache/）
python pipeline/papers/extract.py     # 裁剪 figures.json 中的图，生成 .cache/papers/qa/ 核对图
python pipeline/papers/catalog.py     # 合并论文原图元数据
python pipeline/elements/generate.py  # 生成全部原创图元（SVG、PNG、缩略图）
python pipeline/icons/fetch.py        # 下载固定版本的图标源包
python pipeline/icons/build.py        # 清洗、分类并写入 dist/assets/icons/
python pipeline/catalog.py            # 生成 data.json 与 sources.csv
python scripts/validate.py --hashes   # 校验
```

- **新增图元**：在 `generate.py` 的 `build_specs()` 中用 `add(...)` 登记，复用 `style.py` 的 `slab`、`cube`、`extrude`、`disc` 等绘图函数，再运行 `generate.py`。
- **新增论文图**：在 `pipeline/papers/papers.json` 加入 arXiv 编号，在 `figures.json` 加入图号、中文名、分类与说明，依次运行上面的论文步骤，并查看核对图确认裁剪无误。
- **改进图标中文名**：在 `pipeline/icons/zh_terms.tsv` 增加“英文词 / 中文”对照，可用第三列限定图标集，然后重新运行图标构建。
- 所有 SVG 在构建时去除脚本、事件属性、外部引用与编辑器元数据；`validate.py` 会再次检查。

推送到 `main` 后，GitHub Actions 会运行校验并把 `dist/` 部署到 GitHub Pages（仓库 **Settings → Pages → Source** 选择 **GitHub Actions**）。
