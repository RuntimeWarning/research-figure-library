"""Unified Chinese categories for every icon pack."""
from __future__ import annotations

CATEGORIES = [
    "智能与计算", "数据与存储", "网络与云", "通信与社交", "图表与统计", "数学与符号", "箭头与流程",
    "形状与布局", "科学与实验", "生物与医学", "自然与环境", "地理与交通", "设备与硬件", "界面与操作",
    "文档与编辑", "媒体与影像", "人物与表情", "商业与金融", "生活与物品", "品牌标识",
]

# Research figures most often need these; they make up the "featured" view.
CORE = {"智能与计算", "数据与存储", "网络与云", "图表与统计", "数学与符号", "箭头与流程", "形状与布局",
        "科学与实验", "生物与医学", "自然与环境", "设备与硬件"}

# Categories of the original IconPark, Tabler, Fluent Emoji and Phosphor selections.
LEGACY = {
    "形状与层叠": "形状与布局", "系统与操作": "界面与操作", "数学与运算": "数学与符号", "箭头与流程": "箭头与流程",
    "设备与工具": "设备与硬件", "品牌与标识": "品牌标识", "编辑": "文档与编辑", "天气与地理": "自然与环境",
    "视觉与成像": "媒体与影像", "文档与存储": "数据与存储", "设计与布局": "形状与布局", "数据与网络": "网络与云",
    "信号与图表": "图表与统计", "地图与定位": "地理与交通", "硬件": "设备与硬件", "文字与排版": "文档与编辑",
    "购物与商品": "商业与金融", "食品": "生活与物品", "箭头方向": "箭头与流程", "抽象图形": "形状与布局",
    "食物与饮品": "生活与物品", "办公文档": "文档与编辑", "交通旅游": "地理与交通", "交通工具": "地理与交通",
    "建筑与场景": "地理与交通", "表情": "人物与表情", "体育运动": "生活与物品", "通信与消息": "通信与社交",
    "品牌": "品牌标识", "设备与硬件": "设备与硬件", "基础几何": "形状与布局", "游戏": "生活与物品",
    "运动": "生活与物品", "货币": "商业与金融", "服饰": "生活与物品", "建筑": "地理与交通",
    "电商财产": "商业与金融", "音视频媒体": "媒体与影像", "医疗健康": "生物与医学", "手势动作": "人物与表情",
    "智能与计算": "智能与计算", "医疗与健康": "生物与医学", "字母符号": "数学与符号", "其它": "生活与物品",
    "文档与文件": "文档与编辑", "动物": "自然与环境", "数据图表": "图表与统计", "科学与实验": "科学与实验",
    "基础": "界面与操作", "开发与编程": "智能与计算", "化妆美妆": "生活与物品", "母婴儿童": "人物与表情",
    "用户人名": "人物与表情", "多媒体音乐": "媒体与影像", "链接": "网络与云", "自然与植物": "自然与环境",
    "交通与城市": "地理与交通", "洗护标记": "生活与物品", "通用符号": "数学与符号", "符号标识": "数学与符号",
    "图像与摄影": "媒体与影像", "文件与数据": "数据与存储", "交流沟通": "通信与社交", "工具与能源": "设备与硬件",
    "计算机": "智能与计算", "数学与计算": "数学与符号", "星座": "生活与物品", "美颜调整": "媒体与影像",
    "生活": "生活与物品", "数据与存储": "数据与存储", "工业": "设备与硬件", "徽章": "界面与操作",
    "图表时间与安全": "图表与统计", "能源 & 生命": "科学与实验", "天气与气象": "自然与环境",
    "通信与视听": "通信与社交", "植物与地貌": "自然与环境", "性别": "人物与表情", "时间日期": "界面与操作",
    "手势": "人物与表情", "安全 & 防护": "界面与操作", "电路与电气": "设备与硬件", "科研与医疗": "科学与实验",
    "扩展与插件": "界面与操作", "版本与分支": "智能与计算", "地球与空间": "自然与环境", "几何图形": "形状与布局",
    "天气与水文": "自然与环境", "天气": "自然与环境", "逻辑运算": "数学与符号", "计算与人工智能": "智能与计算",
    "测量 & 试验": "科学与实验", "界面组件": "界面与操作", "数据": "数据与存储", "数字符号": "数学与符号",
    "图表与可视化": "图表与统计",
}

MDI = {
    "Home Automation": "生活与物品", "Files / Folders": "数据与存储", "Alpha / Numeric": "数学与符号",
    "Date / Time": "界面与操作", "Arrow": "箭头与流程", "Food / Drink": "生活与物品", "Banking": "商业与金融",
    "Text / Content / Format": "文档与编辑", "Gaming / RPG": "生活与物品", "Account / User": "人物与表情",
    "Alert / Error": "界面与操作", "Automotive": "地理与交通", "Weather": "自然与环境", "Settings": "界面与操作",
    "Lock": "界面与操作", "Cellphone / Phone": "设备与硬件", "Sport": "生活与物品", "Math": "数学与符号",
    "Navigation": "地理与交通", "Agriculture": "自然与环境", "Shopping": "商业与金融",
    "Geographic Information System": "地理与交通", "Developer / Languages": "智能与计算",
    "Video / Movie": "媒体与影像", "Transportation + Road": "地理与交通", "Battery": "设备与硬件",
    "Music": "媒体与影像", "Photography": "媒体与影像", "Shape": "形状与布局", "Database": "数据与存储",
    "People / Family": "人物与表情", "Nature": "自然与环境", "Medical / Hospital": "生物与医学",
    "Audio": "媒体与影像", "Transportation + Other": "地理与交通", "Places": "地理与交通",
    "Device / Tech": "设备与硬件", "Edit / Modify": "文档与编辑", "Science": "科学与实验", "Holiday": "生活与物品",
    "Form": "界面与操作", "Cloud": "网络与云", "Animal": "自然与环境", "Printer": "设备与硬件",
    "Currency": "商业与金融", "Hardware / Tools": "设备与硬件", "Transportation + Flying": "地理与交通",
    "View": "界面与操作", "Drawing / Art": "媒体与影像", "Emoji": "人物与表情", "Notification": "界面与操作",
    "Vector": "形状与布局", "Clothing": "生活与物品", "Religion": "生活与物品", "Color": "媒体与影像",
    "Tooltip": "界面与操作", "Health / Beauty": "生物与医学", "Transportation + Water": "地理与交通",
    "Arrange": "形状与布局", "Social Media": "通信与社交", "Sport / Outdoor": "生活与物品",
}

CARBON = {
    "Controls": "界面与操作", "Formatting": "文档与编辑", "Navigation": "箭头与流程", "Operations": "界面与操作",
    "Toggle": "界面与操作", "AI": "智能与计算", "App catalogue": "网络与云", "Commerce": "商业与金融",
    "Health": "生物与医学", "Research": "科学与实验", "Alphanumeric": "数学与符号", "Data": "图表与统计",
    "File": "文档与编辑", "Status": "界面与操作", "Systems": "网络与云", "Senses": "人物与表情",
    "User": "人物与表情", "Time": "界面与操作", "Travel": "地理与交通", "Weather": "自然与环境",
    "Technology": "设备与硬件", "Instruments": "科学与实验",
}

PICTOGRAMS = {
    "Action": "界面与操作", "AI": "智能与计算", "Blockchain": "网络与云", "Building structure": "地理与交通",
    "Cities": "地理与交通", "Cloud": "网络与云", "Controls": "界面与操作", "Data analytics": "图表与统计",
    "Data storage": "数据与存储", "Design and development": "智能与计算", "Device interaction": "设备与硬件",
    "Education": "生活与物品", "Electronics": "设备与硬件", "File": "文档与编辑", "Finance": "商业与金融",
    "Government": "生活与物品", "Healthcare": "生物与医学", "Home": "生活与物品", "Industry": "设备与硬件",
    "Internet of Things": "网络与云", "Life Science": "科学与实验", "Lifestyle": "生活与物品",
    "Location": "地理与交通", "Manufacturing": "设备与硬件", "Networking": "网络与云", "People": "人物与表情",
    "Quantum": "科学与实验", "Public service": "生活与物品", "Retail": "商业与金融", "Security": "界面与操作",
    "Sports": "生活与物品", "Status": "界面与操作", "Strategy": "商业与金融", "Supply chain": "商业与金融",
    "Sustainability": "自然与环境", "Systems": "网络与云", "Time": "界面与操作", "Transportation": "地理与交通",
    "watsonx": "智能与计算", "Weather": "自然与环境", "Workplace": "商业与金融",
}

HEALTH = {
    "typography": "数学与符号", "shapes": "形状与布局", "emotions": "人物与表情", "vehicles": "地理与交通",
    "places": "地理与交通", "graphs": "图表与统计", "objects": "生活与物品", "nutrition": "生活与物品",
    "exercise": "生活与物品",
}  # everything else in Health Icons is medical

BIOICONS = {
    "Animals": "自然与环境", "Plants_Algae": "自然与环境", "General_items": "科学与实验",
    "Lab_apparatus": "科学与实验", "Chemistry": "科学与实验", "Safety_symbols": "科学与实验",
    "Procedures": "科学与实验", "Imaging": "科学与实验", "Molecular_modelling": "科学与实验",
    "Nanotechnology": "科学与实验", "Scientific_graphs": "图表与统计", "Machine_Learning": "智能与计算",
    "Computer_hardware": "智能与计算", "Chemo-_and_Bioinformatics": "智能与计算", "People-Other": "人物与表情",
}  # everything else in Bioicons is biology and medicine

PHOSPHOR = {
    "arrows": "箭头与流程", "commerce": "商业与金融", "communications": "通信与社交", "communication": "通信与社交",
    "design": "形状与布局", "editor": "文档与编辑", "finances": "商业与金融", "games": "生活与物品",
    "health & wellness": "生物与医学", "maps & travel": "地理与交通", "media": "媒体与影像", "nature": "自然与环境",
    "objects": "生活与物品", "office": "文档与编辑", "people": "人物与表情", "system": "界面与操作",
    "technology & development": "智能与计算", "weather": "自然与环境",
}

EMOJI = {
    "Smileys & Emotion": "人物与表情", "People & Body": "人物与表情", "Animals & Nature": "自然与环境",
    "Food & Drink": "生活与物品", "Travel & Places": "地理与交通", "Activities": "生活与物品",
    "Objects": "生活与物品", "Symbols": "数学与符号", "Component": "人物与表情",
}

# Keyword rules for packs without categories (and to refine broad upstream groups).
# Earlier rules win; a rule matches when any of its tokens appears in the icon name.
KEYWORDS = [
    ("图表与统计", "chart graph histogram scatter pie donut analytics dashboard gauge poll sankey treemap "
              "heatmap boxplot candlestick trending statistics"),
    ("智能与计算", "ai brain robot bot cpu chip processor gpu code terminal developer binary algorithm neural "
              "agent agents sparkle sparkles bug git branch commit merge function console braces brackets "
              "machine learning model tensor quantum circuit"),
    ("数据与存储", "database data storage archive folder folders disk harddisk save backup server hdd sd "
              "table drive"),
    ("网络与云", "cloud network wifi router vpn api link globe internet web connect connection connected "
              "plug-in ethernet lan hub antenna satellite broadcast signal cellular bluetooth"),
    ("通信与社交", "chat message mail email inbox send share comment comments forum call phone voicemail "
              "contact contacts conversation people-team social"),
    ("数学与符号", "math sum sigma integral equal equals percent number numeric numbers alpha letter "
              "alphabet pi infinity variable divide multiply multiplication fraction sqrt omega exponent "
              "subscript superscript decimal calculator abacus"),
    ("箭头与流程", "arrow arrows chevron caret flow swap sync refresh undo redo repeat loop direction "
              "forward backward split merge routing redirect transfer"),
    ("形状与布局", "shape shapes square circle triangle hexagon polygon pentagon octagon cube cylinder "
              "cone sphere pyramid layer layers grid layout stack border align distribute frame rectangle "
              "ellipse oval rhombus diamond 3d vector bezier spline dots"),
    ("科学与实验", "flask beaker microscope atom molecule lab beaker test-tube telescope magnet "
              "experiment chemistry physics pipette petri thermometer radioactive biohazard"),
    ("生物与医学", "dna virus bacteria cell cells medical hospital pill pills syringe health stethoscope "
              "tooth teeth bone blood lung lungs kidney liver heart-pulse pulse ambulance doctor nurse "
              "bandage vaccine"),
    ("自然与环境", "weather sun sunny moon rain snow wind storm thunder lightning cloudy fog temperature "
              "tree leaf flower plant water drop fire earth mountain animal paw fish bird bug-ant forest "
              "ocean wave waves sunrise sunset rainbow umbrella tornado hurricane"),
    ("地理与交通", "map location pin navigation compass car bus train airplane plane ship boat bicycle bike "
              "road building city home house route traffic gps vehicle truck rocket"),
    ("设备与硬件", "device laptop desktop phone mobile tablet monitor keyboard mouse printer battery usb "
              "hdmi tv speaker headphones watch sensor tool tools wrench hammer screwdriver"),
    ("媒体与影像", "image images photo picture video film movie music audio play pause stop record camera "
              "mic microphone volume color palette brush paint draw drawing"),
    ("文档与编辑", "document text paragraph font bold italic underline strikethrough list note notes "
              "clipboard book page pen pencil edit write attach attachment paperclip copy paste cut print "
              "file files"),
    ("人物与表情", "person people user users account face emoji emotion smile hand body man woman child "
              "baby group team"),
    ("商业与金融", "money cash coin coins bank wallet currency dollar euro cart shopping store shop "
              "receipt invoice payment business briefcase savings"),
    ("界面与操作", "settings add delete close dismiss check search filter lock unlock key shield bell alert "
              "info help menu toggle eye view zoom calendar clock time timer bookmark star flag tag panel "
              "window tab app apps select cursor checkbox radio button"),
]
KEYWORD_SETS = [(cat, set(words.split())) for cat, words in KEYWORDS]


def by_keywords(tokens, default="界面与操作"):
    tokens = set(tokens)
    for category, words in KEYWORD_SETS:
        if tokens & words:
            return category
    return default
