# XSkill

> **Twitter/X 智能情报分析系统** — 抓取推文、动态标注、投研分析、Excel 导出，一条命令搞定。

---

## ✨ 核心能力

| 功能 | 说明 |
|------|------|
| 🔍 **智能抓取** | 自动识别博主（支持中文名/handle/模糊匹配），只抓取缺失时间段的数据 |
| 🏷️ **动态标注** | 用自然语言描述需求，AI 即时生成标注维度并批量分析 |
| 📊 **研报生成** | 自动发现讨论热点、投资信号、趋势共振 |
| 📁 **Excel 导出** | 带超链接、自动列宽的投研级报表 |

---

## 🚀 快速开始

### 安装

```bash
git clone https://github.com/yourname/xskill.git
cd xskill
pip install -r requirements.txt
```

### 配置 `.env`

```bash
OPENROUTER_API_KEY=sk-or-v1-...  # LLM API
TWITTER_AUTH_TOKEN=...           # Twitter 凭据
TWITTER_CT0=...
```

### 运行

```bash
# 基础用法：抓取 + 分析 + 导出
python main.py "karpathy最近一周在讨论什么"

# 指定时间范围
python main.py "sama的推文" --start 2024-01-01 --end 2024-01-31

# 仅导出，跳过分析
python main.py "elonmusk" --no-analyze

# 账号管理
python main.py --update-accounts
python main.py --list-accounts
```

---

## 📖 使用示例

### 1. 智能身份识别

用户可以用任何方式称呼博主，系统自动识别：

```python
from core.query_engine import QueryEngine

engine = QueryEngine()
engine.identify("马斯克")   # → elonmusk
engine.identify("elon")     # → elonmusk  
engine.identify("musk")     # → elonmusk
```

### 2. 日常监控

```bash
python main.py "sama和karpathy这周都在聊什么"
```

**输出**：
- `exports/20260126_sama_karpathy.xlsx` — 推文数据表
- `reports/analysis_20260126.md` — 深度研报

### 3. 标注 + 研报（完整产出）

```bash
python main.py "分析马斯克最近一周的推文，标注情感和主题"
```

系统自动：识别"马斯克"→ elonmusk → 抓取缺失数据 → 生成标注Schema → 批量标注 → 生成研报 → 导出Excel

**产出**：
- `exports/20260126_elonmusk.xlsx`（含 sentiment、topic 等标注字段）
- `reports/analysis_20260126.md`（深度研报）

### 4. 代码调用（高级）

```python
from core.schema_generator import SchemaGenerator
from core.annotator import DynamicAnnotator
from core.exporter import Exporter

# 1. 生成标注 Schema
schema = await SchemaGenerator().generate_from_user_intent(
    "分析情感倾向、是否涉及AI、商业价值1-5分"
)

# 2. 执行标注（结果在内存，不污染数据库）
annotator = DynamicAnnotator(schema=schema)
data = await annotator.annotate_all(author=["sama"], max_tweets=50)

# 3. 导出
Exporter().export_to_excel(external_data=data)
```

---

## 🏗️ 架构

```
用户查询 → QueryEngine(身份识别+时间解析)
              ↓
         StorageManager(计算数据缺口)
              ↓
         XScraper(只抓缺失数据) → 入库
              ↓
         DynamicAnnotator(内存标注) ─或─ AnalysisGenerator(研报)
              ↓
         Exporter(Excel导出)
```

**核心设计原则**：
- **数据库只存原始推文**，标注结果在内存，每次查询可用不同维度
- **时间缺口算法**，避免重复抓取
- **三级身份识别**：精确匹配 → 模糊匹配 → LLM 语义判定

---

## 📁 目录结构

```
xskill/
├── main.py              # 主入口
├── core/
│   ├── query_engine.py  # 身份识别 + 时间解析
│   ├── storage_manager.py  # 存储 + 缺口算法
│   ├── schema_generator.py # 自然语言 → Schema
│   ├── annotator.py     # 动态标注引擎
│   ├── exporter.py      # Excel 导出
│   └── scrapers/        # Twitter 爬虫
├── skills/
│   └── analysis_generator.py  # 研报生成
├── data/
│   ├── accounts.json    # 账号池
│   ├── manifest.json    # 时间覆盖日志
│   └── raw_content.db   # SQLite 数据库
├── exports/             # Excel 输出
└── reports/             # Markdown 研报
```

---

## 🔧 高级用法

### Python API

```python
from main import XSkillAgent

agent = XSkillAgent()
result = await agent.run_pipeline(
    query="马斯克最近的动态",
    start_date="2024-01-01",
    end_date="2024-01-31",
    export=True,
    analyze=True
)

print(result["export_path"])  # Excel 路径
print(result["report_path"])  # 研报路径
```

### 单独使用模块

```python
# 身份识别
from core.query_engine import QueryEngine
engine = QueryEngine()
result = engine.identify("马斯克")  # → {"handle": "elonmusk"}

# 时间解析
start, end = engine.parse_time_range("最近一周")

# 数据查询
from core.storage_manager import StorageManager
tweets = StorageManager().get_tweets(author="sama", start_date="2024-01-01")
```

---

## 📋 依赖

```
twikit        # Twitter 抓取
pandas        # 数据处理
openpyxl      # Excel 导出
beautifulsoup4
thefuzz       # 模糊匹配
requests
python-dotenv
```

---

## License

MIT
