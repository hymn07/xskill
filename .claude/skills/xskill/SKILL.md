---
name: xskill
description: |\
  智能内容情报 Agent 系统 - 专为 VC 投资研究设计的自动化情报中控台。
  
  **自动触发场景**：
  - 查询 Twitter/X 博主动态（"看看马斯克最近说了什么"）
  - 分析投资信号、创业动态（"分析AI领域的创业信号"）
  - 导出投研数据到 Excel（"导出本月数据"）
  - 监控 Zara 推荐名单更新（"有没有新博主"）
  - 即时标注分析推文（"标注这些推文的情感和主题"）
  
  **触发关键词**: xskill, 情报, 推文, 博主, 分析, 投研, 数据, zara, 标注, 创业信号
---

# XSkill - 智能内容情报 Agent 系统

## 🎯 系统定位

这是一个专为 VC 投资研究设计的**自动化情报中控台**，能够：
- 自动发现和监控 KOL 账号
- 智能补全历史数据缺口
- 即时标注和分析推文内容
- 生成投研级别的 Excel 报告

## 📁 项目结构

```
xskill/
├── core/                    # 核心模块
│   ├── discoverer.py        # 账号发现引擎（监控 Zara 推荐列表）
│   ├── query_engine.py      # 三级身份识别路由
│   ├── storage_manager.py   # 存储管理与时间缝隙补全
│   ├── schema_generator.py  # 🆕 动态 Schema 生成器
│   ├── annotator.py         # 🆕 无状态标注引擎
│   ├── exporter.py          # Excel 导出工具
│   └── scrapers/            # 爬虫引擎包
│       ├── base_scraper.py  # 爬虫抽象基类
│       └── x_scraper.py     # Twitter/X 平台实现
├── skills/
│   └── analysis_generator.py # 元提示词分析工厂
├── data/
│   ├── accounts.json        # 账号池
│   ├── manifest.json        # 时间覆盖日志
│   └── raw_content.db       # SQLite 数据仓库（只存原始推文）
├── main.py                  # 🚀 系统入口（推荐使用）
└── test_mock.py             # 无状态架构验证测试
```

## 🚦 何时使用 XSkill

### 场景 1: 查询博主动态

**用户请求示例**：
- "看看马斯克最近一周发了什么"
- "sama 本月有什么新动态"
- "查看 A 开头的博主最近在讨论什么"

**系统行为**：
```python
# 推荐：使用 main.py 完整流程
python main.py "马斯克最近一周"

# 或者代码调用
from main import XSkillAgent
agent = XSkillAgent()
result = await agent.run_pipeline(
    query="马斯克最近一周",
    export=True,
    analyze=True
)
```

**输出**：
- Excel 报告（包含推文、互动数据、超链接）
- AI 分析报告（Markdown 格式）

### 场景 2: 投研分析

**用户请求示例**：
- "分析 AI 领域的创业信号"
- "看看具身智能相关的投资动态"
- "这些博主最近在讨论什么前沿话题"

**系统行为**：
```python
# main.py 会自动触发分析
python main.py "分析AI领域的创业信号" --start 2024-01-01 --end 2024-01-31

# 内部流程：
# 1. 识别相关博主
# 2. 检查数据缺口并抓取
# 3. 调用 AnalysisGenerator 生成深度报告
# 4. 导出 Excel + Markdown 报告
```

### 场景 3: 即时标注分析 ⭐ NEW

**用户请求示例**：
- "标注这些推文的主题和情感"
- "看看 A 开头博主的讨论热度"
- "判断这些推文的投资价值"

**关键特性**：
- ✅ **无状态标注** - 标注结果不写数据库，只在内存中
- ✅ **灵活维度** - 每次查询可以有不同的标注标准
- ✅ **即时生成** - 根据查询意图动态生成标注 Schema

**系统行为**：
```python
# 方式 1: 通过 main.py（推荐）
# 当 query 包含 "标注"、"看讨论"、"判断" 等关键词时自动触发
python main.py "看看A开头博主在讨论什么主题"

# 方式 2: 直接使用标注引擎
from core.schema_generator import SchemaGenerator
from core.annotator import DynamicAnnotator
from core.exporter import Exporter

# 生成标注 Schema
schema_gen = SchemaGenerator()
schema = await schema_gen.generate_from_user_intent(
    "分析推文的主题、情感和投资价值"
)

# 无状态标注（不写数据库）
annotator = DynamicAnnotator(schema=schema)
annotated_data = await annotator.annotate_all(
    author=["elonmusk", "sama"],
    max_tweets=50
)

# 导出（使用内存数据）
exporter = Exporter()
exporter.export_to_excel(
    author=["elonmusk", "sama"],
    external_data=annotated_data  # 关键：直接传入内存数据
)
```

**无状态标注架构**：
```
数据库 (raw_content.db)
  ↓ 读取原始推文
DynamicAnnotator.annotate_all()
  ↓ LLM 即时标注（只在内存）
Exporter.export_to_excel(external_data=...)
  ↓ 直接使用内存数据
Excel 报告（包含标注字段）

✅ 数据库保持干净，只存原始推文
✅ 标注结果不持久化，每次可变
```

### 场景 4: 账号监控

**用户请求示例**：
- "Zara 有没有新推荐的博主"
- "更新账号池"
- "列出所有博主"

**系统行为**：
```python
# 更新账号池
python main.py --update-accounts

# 列出所有账号
python main.py --list-accounts

# 或代码调用
from core.discoverer import AccountDiscoverer
disc = AccountDiscoverer()
new_count, new_accounts = disc.fetch_and_update()
# 输出: "🚨 发现 Zara 推荐名单更新：新增 2 位博主"
```

### 场景 5: 数据导出

**用户请求示例**：
- "导出本月数据"
- "生成马斯克的推文报告"

**系统行为**：
```python
from core.exporter import Exporter

exp = Exporter()
filepath = exp.export_to_excel(
    author="elonmusk",
    start_date="2024-01-01",
    end_date="2024-01-31"
)
# 生成: exports/20240131_153045_elonmusk_数据导出.xlsx
# URL 字段自动转换为可点击超链接
```

## 🔑 核心模块详解

### 1. QueryEngine - 三级身份识别

**问题**：用户说"马斯克"，系统需要知道是 `@elonmusk`

**解决方案**：
1. **精确匹配** - 直接查 `accounts.json`
2. **模糊匹配** - 使用 Levenshtein 距离（处理拼写错误）
3. **LLM 判定** - 调用 AI 进行语义理解

```python
from core.query_engine import QueryEngine

engine = QueryEngine()

# 单个博主识别
result = engine.identify("马斯克")
# 返回: {"status": "found", "handle": "elonmusk", ...}

# 批量识别
result = engine.identify_multiple("看看 sama 和马斯克")
# 返回: {"mode": "multiple", "handles": ["sama", "elonmusk"]}

# 时间解析
start, end = engine.parse_time_range("最近一周")
# 返回: ("2024-01-20", "2024-01-27")
```

### 2. StorageManager - 时间缝隙算法 ⭐ 核心

**问题**：用户要 1月1日-30日的数据，但本地已有 5日-20日，如何避免重复抓取？

**解决方案**：时间区间合并算法

```python
from core.storage_manager import StorageManager

sm = StorageManager()

# 计算缺失区间
gaps = sm.get_missing_ranges(
    handle="elonmusk",
    start_date="2024-01-01",
    end_date="2024-01-30"
)
# 返回: [("2024-01-01", "2024-01-04"), ("2024-01-21", "2024-01-30")]

# 保存推文后更新覆盖日志
sm.save_tweets(tweets)
sm.update_manifest("elonmusk", ("2024-01-01", "2024-01-04"))
# manifest.json 自动合并区间
```

**关键特性**：
- ✅ 自动合并重叠区间
- ✅ 避免重复抓取
- ✅ 支持多博主并发

### 3. DynamicAnnotator - 无状态标注引擎 🆕

**核心理念**：标注结果不持久化，每次查询可以有不同的标注维度

```python
from core.annotator import DynamicAnnotator

# 定义标注 Schema（或用 SchemaGenerator 自动生成）
schema = {
    "schema_name": "investment_signal",
    "description": "投资信号分析",
    "fields": [
        {
            "name": "signal_strength",
            "display_name": "信号强度",
            "type": "integer",
            "range": [1, 5],
            "description": "1=无关, 5=强信号"
        },
        {
            "name": "category",
            "display_name": "类别",
            "type": "enum",
            "values": ["融资", "产品", "招聘", "其他"]
        }
    ]
}

# 无状态标注
annotator = DynamicAnnotator(schema=schema, batch_size=10)
annotated_data = await annotator.annotate_all(
    author=["elonmusk"],
    max_tweets=100
)

# annotated_data 是内存中的列表，包含原始字段 + 标注字段
# 数据库不会被修改！
```

**工作流程**：
1. 从数据库读取原始推文
2. 批量调用 LLM 进行标注（每批 10-15 条）
3. 返回带标注的新列表（不写数据库）
4. 导出时使用 `external_data` 参数

### 4. AnalysisGenerator - 元提示词工厂

**问题**：用户说"看看具身智能的创业信号"，如何生成针对性分析？

**解决方案**：AI 自己生成分析标准

```python
from skills.analysis_generator import AnalysisGenerator

gen = AnalysisGenerator()
report = await gen.analyze(
    query="具身智能创业信号",
    data=tweets_data
)

# AI 会自动：
# 1. 理解"具身智能"领域
# 2. 生成分析维度（融资、产品、团队等）
# 3. 定义评分标准
# 4. 提取关键词
# 5. 产出深度报告
```

### 5. Exporter - 投研级 Excel 导出

**特性**：
- ✅ URL 自动转换为超链接
- ✅ 支持外部数据（无状态标注）
- ✅ 自动调整列宽
- ✅ 时间戳文件名

```python
from core.exporter import Exporter

exp = Exporter()

# 方式 1: 从数据库导出
exp.export_to_excel(
    author="elonmusk",
    start_date="2024-01-01",
    end_date="2024-01-31"
)

# 方式 2: 使用外部数据（无状态标注）
exp.export_to_excel(
    author=["elonmusk"],
    external_data=annotated_data  # 直接传入内存数据
)
```

## 🎯 完整使用流程

### 推荐方式：使用 main.py

```bash
# 1. 基础查询
python main.py "马斯克最近一周"

# 2. 指定时间范围
python main.py "sama 的动态" --start 2024-01-01 --end 2024-01-31

# 3. 只导出，不分析
python main.py "elonmusk" --no-analyze

# 4. 只分析，不导出
python main.py "AI创业信号" --no-export

# 5. 更新账号池
python main.py --update-accounts

# 6. 列出所有博主
python main.py --list-accounts
```

### 高级用法：代码集成

```python
from main import XSkillAgent

agent = XSkillAgent()

# 完整流程
result = await agent.run_pipeline(
    query="看看A开头博主在讨论什么",
    start_date="2024-01-01",
    end_date="2024-01-31",
    export=True,
    analyze=True
)

# 检查结果
if result.get("export_path"):
    print(f"Excel: {result['export_path']}")
if result.get("analysis_report_path"):
    print(f"分析: {result['analysis_report_path']}")
```

## 📊 典型任务映射

| 用户请求 | 触发模块 | 输出 |
|---------|---------|------|
| "看看马斯克最近说了啥" | QueryEngine → StorageManager → XScraper → Exporter | Excel 报告 |
| "分析AI领域的创业动态" | AnalysisGenerator → (数据检索) | Markdown 分析报告 |
| "标注这些推文的情感" | SchemaGenerator → DynamicAnnotator → Exporter | 带标注的 Excel |
| "更新博主列表" | Discoverer.fetch_and_update() | 新增账号提醒 |
| "导出本月数据" | StorageManager → Exporter | Excel 报告 |
| "看看A开头博主讨论什么" | QueryEngine → Annotator → Exporter | 带标注分析的 Excel |

## 🔧 环境配置

### 必需的环境变量（.env）

```bash
# OpenRouter API（用于 LLM 分析和标注）
OPENROUTER_API_KEY=sk-or-v1-...

# Twitter/X 抓取凭据
TWITTER_AUTH_TOKEN=...
TWITTER_CT0=...
```

### 依赖安装

```bash
pip install -r requirements.txt

# 核心依赖：
# - twikit (Twitter 抓取)
# - pandas (数据处理)
# - openpyxl (Excel 导出)
# - beautifulsoup4 (网页解析)
# - thefuzz (模糊匹配)
# - requests (HTTP 请求)
# - python-dotenv (环境变量)
```

## 💡 最佳实践

### 1. 优先使用 main.py

```python
# ✅ 推荐
python main.py "查询内容"

# ❌ 不推荐（除非有特殊需求）
# 手动调用各个模块
```

### 2. 无状态标注的正确用法

```python
# ✅ 正确：使用 external_data
annotated_data = await annotator.annotate_all(...)
exporter.export_to_excel(external_data=annotated_data)

# ❌ 错误：期望从数据库读取标注
# 标注结果不会写入数据库！
```

### 3. 时间范围查询

```python
# ✅ 推荐：让系统自动解析
python main.py "马斯克最近一周"

# ✅ 也可以：明确指定
python main.py "马斯克" --start 2024-01-01 --end 2024-01-31

# ⚠️ 注意：如果不指定时间，系统会使用默认的最近7天
```

### 4. 批量处理

```python
# ✅ 推荐：使用批量识别
result = engine.identify_multiple("sama 和马斯克")

# ❌ 不推荐：循环单个识别
for name in ["sama", "马斯克"]:
    result = engine.identify(name)
```

## 🚨 常见问题

### Q1: 标注结果为什么不在数据库里？

**A**: 这是设计特性！无状态标注的优势：
- 不同查询可以有不同的标注维度
- 数据库保持干净，只存原始推文
- 标注标准可以随时更新，不需要重新标注全库

### Q2: 如何自定义标注维度？

**A**: 两种方式：

```python
# 方式 1: 让 AI 自动生成
schema = await schema_gen.generate_from_user_intent("你的需求")

# 方式 2: 手动定义
schema = {
    "schema_name": "custom",
    "description": "自定义标注",
    "fields": [...]
}
```

### Q3: 数据库会存储什么？

**A**: 只存储原始推文元数据：
- tweet_id, author, text, publish_time, url
- 互动数据：like_count, retweet_count, reply_count
- 元数据：lang, author_followers

**不存储**：标注结果（sentiment, topic, importance 等）

### Q4: 如何清理旧数据？

**A**: 直接操作数据库：

```python
from core.storage_manager import StorageManager
import sqlite3

sm = StorageManager()
conn = sqlite3.connect(sm.db_path)
cursor = conn.cursor()

# 删除某个作者的数据
cursor.execute("DELETE FROM content WHERE author = ?", ("elonmusk",))
conn.commit()

# 同时更新 manifest.json
manifest = sm._load_manifest()
del manifest["elonmusk"]
sm._save_manifest(manifest)
```

## 🎓 学习资源

- **项目需求文档**: `需求.md` - 了解系统设计理念
- **测试示例**: `test_mock.py` - 无状态架构验证
- **分析模板**: `.claude/skills/xskill/resources/templates.md`
- **完整文档**: `walkthrough.md` - 重构过程和架构说明

## 🔄 版本历史

- **V6** - 无状态标注架构（当前版本）
  - ✅ 标注结果不持久化
  - ✅ 动态 Schema 生成
  - ✅ 支持 external_data 导出

- **V5** - 元分析与数据资产版
  - ✅ 时间缝隙补全算法
  - ✅ 三级身份识别
  - ✅ 元提示词工厂

---

**总结**：XSkill 是一个生产级的投研情报系统，核心优势在于**智能补全**、**无状态标注**和**动态分析**。使用时优先通过 `main.py` 入口，让系统自动编排各模块完成任务。
