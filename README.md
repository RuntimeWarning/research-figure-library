<p align="center"><img src="dist/favicon.svg" width="76" alt="研图标志"></p>

<h1 align="center">研图 · Figure Atlas</h1>

<p align="center">论文图元素材库</p>

从 110 篇经典深度学习论文的插图里，把特征张量、注意力矩阵、卷积核、Token 序列、气象场、点云这些**图元**逐个分离出来。矢量图元保留论文原始路径，可以直接改色、改尺寸，拼进你自己的模型结构图。另附 289 张按原样裁剪的论文原图和 28,102 个开源科研图标。每一项都标明出处论文、页码、作者与许可。

[在线检索](https://runtimewarning.github.io/research-figure-library/) · [GitHub 仓库](https://github.com/RuntimeWarning/research-figure-library) · [完整来源清单](dist/sources.csv)

![研图首页](docs/screenshot-home.jpg)

## 素材规模

| 集合 | 数量 | 说明 |
| --- | ---: | --- |
| **论文图元** | **391** | 来自 110 篇论文插图的可复用元素，237 个为可编辑矢量 SVG，其余按论文嵌入位图的原始分辨率导出 |
| 论文原图 | 289 | 来自 227 篇论文（1997–2025），覆盖 21 个方向；按原样裁剪，不重绘、不改色 |
| 科研图标 | 28,102 | 10 个开源图标集，统一为 20 个中文分类，可按图标集筛选 |
| **合计** | **28,782** | 每项素材在 `dist/sources.csv` 中列出文件、来源、许可与 SHA-256 |

### 图元分类

![论文图元](docs/screenshot-elements.jpg)

| 分类 | 数量 | 例子 |
| --- | ---: | --- |
| 张量与特征图 | 87 | 三维特征张量、扁平张量、多通道特征堆叠、特征平面、三维体素网格（Earthformer、V-Net、ACmix、SENet） |
| 气象与地球数据 | 41 | 全球温度场与风场（Pangu-Weather、ClimaX）、三维气象场立方体（FengWu）、雷达回波与降水场（CasCast、PreDiff、LDCast、DGMR）、台风路径 |
| 卷积核与采样 | 40 | 3×3 卷积核、空洞卷积感受野、可变形采样网格、图像分块、窗口划分 |
| 图像与点云 | 39 | 彩色深度点云、室内场景点云、体素化模型、CT/MRI 分割、语义分割掩码 |
| 热图与特征图 | 31 | 自注意力热图（DINO）、有效感受野（SegFormer、WTConv）、光流颜色编码、边缘响应图 |
| 矩阵与注意力图 | 30 | 全注意力、因果、稀疏、滑动窗口与轴向注意力掩码，相似度矩阵 |
| Token 与向量 | 26 | Token 序列、权重条、通道向量、多变量 Token（iTransformer、ViLT） |
| 符号与箭头 | 26 | 加法、乘法、求和、激活等运算符号，弧形、分流、空心箭头 |
| 网络与图结构 | 20 | 全连接层、注意力连接、扩张因果卷积、图神经网络、嵌入空间 |
| 曲线与信号 | 19 | 时间序列、GAN 分布曲线、动力学轨迹、频谱三维曲面 |
| 噪声、频谱与小波 | 17 | 扩散噪声、随机噪声纹理、位置编码相似度、小波子带 |
| 模块与结构块 | 15 | LSTM 与 GRU 单元、残差块、编码器梯形、U-Net 特征图条 |

图元的提取方法：在每篇论文 PDF 中定位架构类插图，把相互连接的矢量路径分组，只取这一组路径重新绘制成独立的 SVG 与透明 PNG（不带文字和相邻图形）；插图中嵌入的位图按原始分辨率导出。候选共 3,300 多个，经逐张目检保留 361 个，加上早期整理的 30 个；过小、模糊、带色标或几乎用不到的都已删除。

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
- **分类与筛选**：图元 12 类、论文原图 21 个方向、图标 20 类；可只看矢量图元、完整架构图、可改色图标或科研常用图标。
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

本项目自行编写的检索页面、构建脚本与数据整理采用 [MIT](LICENSE) 许可。第三方素材**不在**本项目 MIT 许可范围内：

- **图标**保留各自的开源许可，许可原文在 [`dist/licenses/`](dist/licenses/)。Bioicons 中 CC BY 图标须按条目注明作者，作者与许可显示在详情页和 `sources.csv` 中。
- **论文图元与原图**的版权属于原作者或出版方。每项的许可按论文在 arXiv 上的选择记录：680 项中 553 项为 arXiv 非独占分发许可，61 项为 CC BY 4.0，另有 CC BY-SA、CC BY-NC-SA、CC BY-NC-ND、CC0 及出版方版权等，详情页会标出 NC（非商业）与 ND（禁止改编）等限制。本仓库收录这些图元和原图用于学术检索与介绍；在论文、课件或出版物中使用时，请引用原论文，并按原许可或出版方规定取得授权。
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
│       ├── elements/             # 论文图元 PNG / SVG 与 thumbs/ 缩略图
│       ├── papers/               # 论文原图 PNG / SVG / PDF 与 thumbs/ 缩略图
│       └── icons/<图标集>/        # 按图标集分目录的 SVG
├── pipeline/                     # 素材构建流程（需要 PyMuPDF 等，见 requirements.txt）
│   ├── papers/                   # 论文清单、下载、裁剪与元数据
│   ├── elements/                 # 图元候选提取（candidates.py）、人工筛选清单与构建
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
python pipeline/elements/candidates.py  # 从全部论文插图中提取图元候选，生成 .cache/elements/ 核对图
python pipeline/elements/build.py     # 按 elements.json 的筛选结果生成图元
python pipeline/icons/fetch.py        # 下载固定版本的图标源包
python pipeline/icons/build.py        # 清洗、分类并写入 dist/assets/icons/
python pipeline/catalog.py            # 生成 data.json 与 sources.csv
python scripts/validate.py --hashes   # 校验
```

- **新增图元**：运行 `candidates.py` 后在核对图中挑选，把候选编号写入 `pipeline/elements/elements.json`（可指定类型与名称），再运行 `build.py`。
- **新增论文图**：在 `pipeline/papers/papers.json` 加入 arXiv 编号，在 `figures.json` 加入图号、中文名、分类与说明，依次运行上面的论文步骤，并查看核对图确认裁剪无误。
- **改进图标中文名**：在 `pipeline/icons/zh_terms.tsv` 增加“英文词 / 中文”对照，可用第三列限定图标集，然后重新运行图标构建。
- 所有 SVG 在构建时去除脚本、事件属性、外部引用与编辑器元数据；`validate.py` 会再次检查。

推送到 `main` 后，GitHub Actions 会运行校验并把 `dist/` 部署到 GitHub Pages（仓库 **Settings → Pages → Source** 选择 **GitHub Actions**）。
