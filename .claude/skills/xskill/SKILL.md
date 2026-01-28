---
name: xskill
description: |
  Twitter/X 智能情报分析系统。调用此 Skill 完成：抓取 Twitter 博主推文、动态标注分析、生成投研报告、导出 Excel。
  
  **激活关键词**: 推文, 博主, Twitter, X, 马斯克, sama, karpathy, 情报, 标注, 分析, 导出, 研报
---

# XSkill - Twitter 智能情报系统

> 核心能力：**抓取推文 → 智能标注 → 投研分析 → Excel 导出**

---

## 快速决策树

```
用户请求
    │
    ├─ 包含"博主/推文/Twitter" + 时间范围？
    │   └─ 是 → 调用 run_pipeline() 完整流程
    │
    ├─ 仅需"导出/Excel"？
    │   └─ 是 → 直接调用 Exporter
    │
    ├─ 需要"标注/分析主题/情感"？
    │   └─ 是 → SchemaGenerator + DynamicAnnotator + Exporter
    │
    ├─ 需要"研报/深度分析"？
    │   └─ 是 → AnalysisGenerator
    │
    └─ "更新账号/新博主"？
        └─ 是 → AccountDiscoverer.fetch_and_update()
```

---

## 核心入口

### 方式一：命令行（推荐）

```bash
# 完整情报流程
python main.py "马斯克最近一周的动态"

# 指定时间范围
python main.py "sama的推文" --start 2026-01-01 --end 2026-01-31

# 仅导出
python main.py "karpathy" --no-analyze

# 账号管理
python main.py --update-accounts
python main.py --list-accounts
```

### 方式二：代码调用

```python
from main import XSkillAgent

agent = XSkillAgent()
result = await agent.run_pipeline(
    query="sama和karpathy最近在讨论什么",
    start_date="2026-01-15",
    end_date="2026-01-25",
    export=True,
    analyze=True
)

# 输出路径
print(result.get("export_path"))      # Excel 文件
print(result.get("report_path"))      # Markdown 研报
```

---

## 模块调用指南

### 1. 身份识别 + 时间解析

用户可能说 "elon"、"musk"、"马斯克"、"Elon Musk"，系统统一识别为 `elonmusk`。

```python
from core.query_engine import QueryEngine

engine = QueryEngine()

# 各种输入方式都能识别
engine.identify("马斯克")    # → {"handle": "elonmusk", "status": "llm_identified"}
engine.identify("elon")      # → {"handle": "elonmusk", "status": "fuzzy_match"}
engine.identify("musk")      # → {"handle": "elonmusk", "status": "fuzzy_match"}
engine.identify("elonmusk")  # → {"handle": "elonmusk", "status": "found"}

# 批量识别
result = engine.identify_multiple("看看马斯克和karpathy")
# {"mode": "multiple", "handles": ["elonmusk", "karpathy"]}

# 时间解析
start, end = engine.parse_time_range("最近一周")
# ("2026-01-19", "2026-01-26")
```

### 2. 存储与缺口补全

避免重复抓取，只拉取缺失数据。

```python
from core.storage_manager import StorageManager

sm = StorageManager()

# 计算需要抓取的时间段
gaps = sm.get_missing_ranges("elonmusk", "2026-01-01", "2026-01-30")
# [("2026-01-01", "2026-01-04"), ("2026-01-21", "2026-01-30")]

# 查询已存推文
tweets = sm.get_tweets(
    author="sama", 
    start_date="2026-01-01", 
    end_date="2026-01-15"
)
```

### 3. 动态标注（无状态）

**核心特性**：标注结果只在内存，不污染原始数据库。

```python
from core.schema_generator import SchemaGenerator
from core.annotator import DynamicAnnotator

# 1. 从自然语言生成标注 Schema
schema_gen = SchemaGenerator()
schema = await schema_gen.generate_from_user_intent(
    "分析推文的情感倾向、是否涉及AI、商业价值评分1-5"
)

# 2. 执行标注
annotator = DynamicAnnotator(schema=schema, batch_size=10)
annotated_data = await annotator.annotate_all(
    author=["sama", "karpathy"],
    max_tweets=100
)

# annotated_data 包含原始字段 + 标注字段
# 数据库不会被修改！
```

**Schema 格式示例**：
```json
{
  "schema_name": "vc_signal",
  "description": "投资信号分析",
  "fields": [
    {"name": "sentiment", "type": "enum", "values": ["positive", "neutral", "negative"]},
    {"name": "ai_related", "type": "boolean"},
    {"name": "signal_score", "type": "integer", "range": [1, 5]}
  ]
}
```

### 4. 数据导出

```python
from core.exporter import Exporter

exp = Exporter()

# 直接从数据库导出
exp.export_to_excel(
    author="sama",
    start_date="2026-01-01",
    end_date="2026-01-15"
)

# 导出带标注的数据（使用内存数据）
exp.export_to_excel(
    author=["sama", "karpathy"],
    external_data=annotated_data  # 关键参数
)
```

### 5. 研报生成

```python
from skills import AnalysisGenerator

gen = AnalysisGenerator()
report = await gen.analyze(
    query="AI编程工具赛道的投资机会",
    data=tweets
)

# 保存研报
gen.save_report(report)  # → reports/analysis_20260125.md
```

---

## 典型工作流

### 工作流 A：完整情报收集

```
用户："分析karpathy这个月在关注什么"

1. QueryEngine.identify("karpathy") → "karpathy"
2. QueryEngine.parse_time_range("这个月") → ("2026-01-01", "2026-01-31")
3. StorageManager.get_missing_ranges() → 计算缺口
4. XScraper.scrape() → 抓取缺失数据
5. StorageManager.save_tweets() → 入库
6. AnalysisGenerator.analyze() → 生成研报
7. Exporter.export_to_excel() → 导出 Excel
```

### 工作流 B：仅标注分析

```
用户："对最近的推文进行情感分析和主题分类"

1. SchemaGenerator.generate_from_user_intent() → 生成 Schema
2. DynamicAnnotator.annotate_all() → 批量标注（内存）
3. Exporter.export_to_excel(external_data=...) → 导出带标注的 Excel
```

### 工作流 C：标注 + 研报（完整产出）

```
用户："分析马斯克最近一周的推文，标注情感和主题，产出报告"

1. QueryEngine.identify("马斯克") → "elonmusk"
2. QueryEngine.parse_time_range("最近一周") → ("2026-01-19", "2026-01-26")
3. StorageManager.get_missing_ranges() → 计算缺口
4. XScraper.scrape() → 抓取缺失数据
5. SchemaGenerator.generate_from_user_intent("情感和主题") → 生成 Schema
6. DynamicAnnotator.annotate_all() → 批量标注（内存）
7. AnalysisGenerator.analyze() → 生成研报
8. Exporter.export_to_excel(external_data=...) → 导出带标注的 Excel
9. gen.save_report() → 保存 Markdown 研报

产出：
  - exports/20260126_elonmusk.xlsx（含标注字段）
  - reports/analysis_20260126.md（深度研报）
```

### 工作流 D：仅导出

```
用户："导出sama的推文到Excel"

1. QueryEngine.identify("sama") → "sama"
2. Exporter.export_to_excel(author="sama") → 直接导出
```

---

## 目录结构

```
xskill/
├── main.py                 # 主入口，优先使用
├── core/
│   ├── query_engine.py     # 身份识别 + 时间解析
│   ├── storage_manager.py  # SQLite 存储 + 缺口计算
│   ├── schema_generator.py # 自然语言 → 标注 Schema
│   ├── annotator.py        # 动态 LLM 标注
│   ├── exporter.py         # Excel 导出
│   ├── discoverer.py       # Zara 账号发现
│   └── scrapers/           # Twitter 爬虫
│       └── x_scraper.py
├── skills/
│   └── analysis_generator.py  # 研报生成
├── data/
│   ├── accounts_level1.json    # 一级账号池（Zara Zhang 直接推荐）
│   ├── accounts_level2.json    # 二级账号池（Zara 推荐的人推荐的）
│   ├── manifest.json           # 时间覆盖日志
│   └── raw_content.db          # SQLite 推文数据库
├── exports/                # Excel 输出目录
└── reports/                # Markdown 研报目录
```

---

## 环境变量

```bash
# .env 文件
OPENROUTER_API_KEY=sk-or-v1-...  # LLM 调用
TWITTER_AUTH_TOKEN=...           # Twitter 认证
TWITTER_CT0=...                  # Twitter 认证
```

---

## 注意事项

1. **无状态标注**：`DynamicAnnotator` 的结果不会写入数据库，必须通过 `external_data` 参数传给 Exporter
2. **优先用 main.py**：自动处理模块编排，除非有特殊需求才直接调用模块
3. **时间范围**：不指定时默认最近 7 天
4. **批量处理**：标注时推荐 `batch_size=10`，避免 token 超限
