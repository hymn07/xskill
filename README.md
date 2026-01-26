
# XSkill - 智能内容情报 Agent 系统

> 专为 VC 投资研究设计的自动化情报中控台。

---

## 🎯 核心能力与产出物

这是一个帮你自动分析 Twitter/X 科技圈动态的 AI Agent。与其费力手动刷推，不如直接问它。

### 📊 你将得到什么？(Deliverables)

1.  **投研级 Excel 数据表**
    *   包含推文原文、互动数据（赞/转/评）、发布时间。
    *   **AI 智能标注字段**：根据你的提问动态生成。比如你问“分析投资信号”，Excel 里就会多出 `investment_signal_score` 和 `signal_reason` 列。
    *   **纯净数据**：数据库只存事实（Source of Truth），所有主观标注都在 Excel 中，互不污染。

2.  **深度分析研报 (Markdown)**
    *   **趋势总结**：识别多个博主共同关注的“共振信号”。
    *   **机会扫描**：发现 "Under-hyped" 的早期项目或技术。
    *   **投资建议**：基于 VC 视角的 Actionable Insights。

---

## 🗣️ 你可以问什么？(Example Queries)

XSkill 的核心交互方式是**自然语言指令**。

#### 1. 日常监控
> "看看 @amasad 和 @karpathy 最近一周在讨论什么"
> "列出 A 开头的博主最近 3 天的动态"

#### 2. 深度投研
> "分析 AI Agent 领域的创业信号，重点关注编程工具赛道"
> "评估最近一周提到'SaaS 增长'的推文的情感倾向"

#### 3. 数据处理
> "导出 @swyx 本月的所有推文到 Excel，不需要分析"
> "标注这些推文是否涉及'融资'信息，并打分 1-5"

---

## ⚙️ 工作原理 (How it Works)

XSkill 采用 **Intent-Driven Architecture** (意图驱动架构)。你的每一个指令都会触发一条自动化的流水线：

```mermaid
graph LR
    User[用户: "分析AI创业信号..."] -->|1. 理解意图| Agent
    Agent -->|2. 生成 Schema| Schema[JSON Schema: {signal_score, sector}]
    Agent -->|3. 补全数据| Scraper[只能爬虫: 补全时间缺口]
    
    Data[(原始数据)] -->|4. 动态结合| Annotator[AI 标注引擎]
    Schema --> Annotator
    
    Annotator -->|5. 批量推理| Output
    Output -->|6. 交付| Excel[Excel: 原始数据 + 标注列]
    Output -->|6. 交付| Report[Markdown: 深度研报]
```

### 关键机制
*   **Gap Filling (时间缝隙补全)**: 不会每次都傻乎乎地重爬。系统会自动计算你手里已有的数据（如 1号-5号）和你想要的（1号-10号），然后只去抓取缺失的（6号-10号）。高效且安全。
*   **Dynamic Annotation (即时标注)**: 数据库里永远只存干净的原始推文。所有的“情感”、“分类”、“评分”都是根据你当下的需求，由 LLM 即时生成的。这使得一套数据可以被无数个维度反复分析。

---

## 🚦 快速开始

### 1. 安装
```bash
git clone https://github.com/jinqiu/xskill.git
cd xskill
pip install -r requirements.txt
```

### 2. 配置 (.env)
```bash
OPENROUTER_API_KEY=sk-...  # 用于 LLM 分析
TWITTER_AUTH_TOKEN=...     # 用于数据抓取
```

### 3. 运行
```bash
# 场景：分析 AI 编程领域的信号
python main.py "分析 AI Coding 赛道的投资机会" --start 2024-01-01
```

## 📂 目录结构

*   `core/`: 核心引擎（存储、标注、导出）
*   `skills/`: 高级分析能力（研报生成）
*   `data/`: SQLite 数据库与时间日志
*   `exports/`: 产出的 Excel 文件
*   `reports/`: 产出的分析报告

---
*Built for the Agentic Future.*
