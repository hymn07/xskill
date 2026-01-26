# XSkill 快速参考

## 🎯 一句话总结

**XSkill = Twitter 情报自动化 + 智能标注 + 投研报告生成**

## 🚀 最常用的 3 个命令

```bash
# 1. 查询博主动态（自动补全缺失数据 + 生成报告）
python main.py "马斯克最近一周"

# 2. 更新账号池（监控 Zara 推荐列表）
python main.py --update-accounts

# 3. 即时标注分析（无状态，不写数据库）
python main.py "看看A开头博主在讨论什么主题"
```

## 🤖 AI 决策树

```
用户请求
  │
  ├─ 包含博主名字？
  │   ├─ 是 → 使用 QueryEngine 识别
  │   │        → 检查数据缺口
  │   │        → 抓取缺失数据
  │   │        → 导出 Excel
  │   └─ 否 → 继续判断
  │
  ├─ 包含"标注"/"判断"/"看讨论"？
  │   └─ 是 → 触发无状态标注流程
  │            → SchemaGenerator 生成 Schema
  │            → DynamicAnnotator 标注
  │            → Exporter 导出（external_data）
  │
  ├─ 包含"分析"/"信号"/"趋势"？
  │   └─ 是 → 触发 AnalysisGenerator
  │            → 生成元提示词
  │            → 产出深度报告
  │
  ├─ 包含"更新"/"新博主"/"zara"？
  │   └─ 是 → 调用 Discoverer
  │            → 监控推荐列表
  │            → 提醒新增账号
  │
  └─ 包含"导出"/"报告"？
      └─ 是 → 直接调用 Exporter
               → 生成 Excel
```

## 📝 代码模板

### 模板 1: 基础查询

```python
from main import XSkillAgent

agent = XSkillAgent()
result = await agent.run_pipeline(
    query="马斯克最近一周",
    export=True,
    analyze=True
)
```

### 模板 2: 无状态标注

```python
from core.schema_generator import SchemaGenerator
from core.annotator import DynamicAnnotator
from core.exporter import Exporter

# 1. 生成 Schema
schema_gen = SchemaGenerator()
schema = await schema_gen.generate_from_user_intent(
    "分析推文的主题、情感和投资价值"
)

# 2. 无状态标注
annotator = DynamicAnnotator(schema=schema)
annotated_data = await annotator.annotate_all(
    author=["elonmusk"],
    max_tweets=50
)

# 3. 导出（关键：使用 external_data）
exporter = Exporter()
exporter.export_to_excel(
    author=["elonmusk"],
    external_data=annotated_data  # 不从数据库读取
)
```

### 模板 3: 账号监控

```python
from core.discoverer import AccountDiscoverer

disc = AccountDiscoverer()
new_count, new_accounts = disc.fetch_and_update()

if new_count > 0:
    print(f"🚨 发现 {new_count} 个新博主：")
    for acc in new_accounts:
        print(f"  • {acc['name']} (@{acc['screen_name']})")
```

## ⚡ 关键概念速查

| 概念 | 说明 | 示例 |
|-----|------|-----|
| **三级识别** | 精确→模糊→LLM | "马斯克" → @elonmusk |
| **时间缝隙** | 只抓缺失区间 | 请求[1.1-1.30]，已有[1.5-1.20]，只抓[1.1-1.4]和[1.21-1.30] |
| **无状态标注** | 标注不写数据库 | 标注结果只在内存和Excel，数据库保持干净 |
| **元提示词** | AI生成分析标准 | "创业信号" → AI自动生成融资/产品/团队等维度 |
| **external_data** | 导出内存数据 | 绕过数据库，直接导出标注后的数据 |

## 🎨 输出示例

### Excel 报告字段

**原始字段**：
- 作者、内容、发布时间
- 点赞数、转发数、评论数、阅读量
- 原文链接（可点击）

**标注字段**（仅在使用标注功能时）：
- 主题分类、情感倾向
- 重要性评分、关键词

### Markdown 分析报告

```markdown
# AI领域创业信号分析

## 📊 数据概览
- 时间范围: 2024-01-01 至 2024-01-31
- 推文总数: 156 条
- 覆盖博主: 12 位

## 🔥 重点发现
1. OpenAI 发布 GPT-5 预告
2. Anthropic 完成 C 轮融资
3. ...

## 📈 趋势分析
...
```

## ⚠️ 注意事项

1. **API Key 必需**：需要配置 `OPENROUTER_API_KEY`
2. **标注不持久化**：无状态标注的结果不会写入数据库
3. **时间默认值**：不指定时间时使用最近7天
4. **批量处理**：标注时每批处理 10-15 条推文

## 🔗 相关文件

- 完整文档: `SKILL.md`
- 测试示例: `test_mock.py`
- 项目需求: `需求.md`
- 重构说明: `walkthrough.md`
