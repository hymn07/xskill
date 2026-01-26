"""
analysis_generator.py - 元提示词分析工厂

核心职责:
1. 理解用户模糊需求
2. 动态生成分析维度和评分标准
3. 结合数据产出深度投研报告

使用 OpenRouter API 调用模型
"""

import os
import json
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path

import requests


class AnalysisGenerator:
    """元提示词分析工厂：动态生成投研分析报告"""
    
    def __init__(
        self, 
        openrouter_api_key: str = None,
        model: str = "google/gemini-2.5-flash-preview-09-2025"
    ):
        self.api_key = openrouter_api_key or os.getenv("OPENROUTER_API_KEY")
        self.api_base = "https://openrouter.ai/api/v1/chat/completions"
        self.model = model
        
        # 加载模板
        self.templates = self._load_templates()
    
    def _load_templates(self) -> str:
        """加载分析模板"""
        template_path = Path(__file__).parent.parent / ".claude" / "skills" / "xskill" / "resources" / "templates.md"
        
        if template_path.exists():
            with open(template_path, 'r', encoding='utf-8') as f:
                return f.read()
        return ""
    
    async def analyze(
        self, 
        query: str, 
        data: List[Dict],
        output_format: str = "markdown"
    ) -> Dict:
        """
        基于用户需求和数据生成分析报告
        
        Args:
            query: 用户的分析需求，如 "具身智能创业信号"
            data: 待分析的内容列表
            output_format: 输出格式 (markdown/json)
            
        Returns:
            {
                "query": str,
                "analysis_prompt": str,  # 动态生成的分析 Prompt
                "report": str,           # 分析报告
                "highlights": list,      # 重点发现
                "generated_at": str
            }
        """
        if not self.api_key:
            return {
                "error": "未配置 OPENROUTER_API_KEY",
                "query": query,
                "generated_at": datetime.now().isoformat()
            }
        
        # Step 1: 生成分析 Prompt（元提示词）
        analysis_prompt = await self._generate_analysis_prompt(query)
        
        # Step 2: 应用分析 Prompt 到数据
        report = await self._apply_analysis(analysis_prompt, data, output_format)
        
        # Step 3: 提取重点
        highlights = await self._extract_highlights(report, query)
        
        return {
            "query": query,
            "analysis_prompt": analysis_prompt,
            "report": report,
            "highlights": highlights,
            "data_count": len(data),
            "generated_at": datetime.now().isoformat()
        }
    
    async def _generate_analysis_prompt(self, query: str) -> str:
        """
        第一阶段：理解用户需求，生成专属分析 Prompt
        
        这是元提示词的核心 - AI 自己设计分析框架
        """
        meta_prompt = f"""你是一位顶级 VC 投资研究专家。用户想要分析: "{query}"

请基于你的专业知识，为这个分析需求设计一套完整的分析框架：

1. **分析维度** (3-5个维度，每个维度说明要关注什么)
2. **评分标准** (1-5分，每个分值的判定条件)
3. **关键词列表** (用于识别相关内容的词汇)
4. **输出格式** (报告应该包含哪些部分)

参考模板:
{self.templates[:2000] if self.templates else '无可用模板'}

请直接输出分析框架，使用 Markdown 格式。"""

        response = await self._call_llm(meta_prompt, max_tokens=1500)
        return response
    
    async def _apply_analysis(
        self, 
        analysis_prompt: str, 
        data: List[Dict],
        output_format: str
    ) -> str:
        """
        第二阶段：应用分析框架到实际数据
        """
        # 准备数据摘要（避免 token 过多）
        data_summary = self._prepare_data_summary(data)
        
        apply_prompt = f"""请根据以下分析框架，对数据进行深度分析。

## 分析框架
{analysis_prompt}

## 待分析数据
共 {len(data)} 条内容:
{data_summary}

## 输出要求
- 格式: {output_format}
- 需要给出具体的洞察和判断
- 引用具体的内容作为证据
- 按重要性排序

请输出完整的分析报告。"""

        response = await self._call_llm(apply_prompt, max_tokens=3000)
        return response
    
    async def _extract_highlights(self, report: str, query: str) -> List[str]:
        """
        第三阶段：从报告中提取核心发现
        """
        extract_prompt = f"""从以下分析报告中提取 3-5 个最重要的发现，每个发现用一句话总结。

报告主题: {query}

报告内容:
{report[:3000]}

请以 JSON 数组格式输出，如: ["发现1", "发现2", "发现3"]"""

        response = await self._call_llm(extract_prompt, max_tokens=500)
        
        try:
            # 尝试解析 JSON
            import re
            match = re.search(r'\[.*\]', response, re.DOTALL)
            if match:
                return json.loads(match.group())
        except:
            pass
        
        return [response]
    
    def _prepare_data_summary(self, data: List[Dict], max_items: int = 100) -> str:
        """准备数据摘要，控制 token 消耗"""
        summaries = []
        
        for item in data[:max_items]:
            author = item.get('author', 'Unknown')
            text = item.get('text', '')[:200]
            time = item.get('publish_time', '')[:10]
            
            summaries.append(f"[@{author} {time}]: {text}")
        
        if len(data) > max_items:
            summaries.append(f"... 还有 {len(data) - max_items} 条内容未显示")
        
        return "\n\n".join(summaries)
    
    async def _call_llm(self, prompt: str, max_tokens: int = 2000) -> str:
        """调用 OpenRouter API"""
        try:
            response = requests.post(
                self.api_base,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/xskill",
                    "X-Title": "XSkill Analysis"
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                    "max_tokens": max_tokens
                },
                timeout=120
            )
            response.raise_for_status()
            
            result = response.json()
            return result['choices'][0]['message']['content']
            
        except Exception as e:
            print(f"❌ LLM 调用失败: {e}")
            return f"分析生成失败: {str(e)}"
    
    async def quick_summary(self, data: List[Dict]) -> str:
        """快速数据摘要（不进行深度分析）"""
        if not data:
            return "没有数据可供分析"
        
        prompt = f"""请对以下 {len(data)} 条社交媒体内容做一个简要总结，包括：
1. 主要话题
2. 情绪倾向
3. 值得关注的信号

数据:
{self._prepare_data_summary(data, max_items=20)}"""

        return await self._call_llm(prompt, max_tokens=800)
    
    def save_report(self, result: dict, output_dir: str = None, filename: str = None) -> str:
        """
        保存分析报告为 Markdown 文件
        
        Args:
            result: analyze() 返回的结果字典
            output_dir: 输出目录，默认为 reports/
            filename: 文件名，默认自动生成
            
        Returns:
            保存的文件路径
        """
        from pathlib import Path
        from datetime import datetime
        
        if output_dir is None:
            output_dir = Path(__file__).parent.parent / "reports"
        else:
            output_dir = Path(output_dir)
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_AI分析报告.md"
        
        filepath = output_dir / filename
        
        # 构建 Markdown 内容
        content = f"""# AI 分析报告

**查询**: {result.get('query', 'N/A')}
**生成时间**: {result.get('generated_at', 'N/A')}
**数据条数**: {result.get('data_count', 0)}

---

{result.get('report', '无')}

---

## 核心发现

"""
        
        highlights = result.get('highlights', [])
        if highlights:
            for i, h in enumerate(highlights, 1):
                content += f"{i}. {h}\n"
        else:
            content += "无"
        
        # 保存文件
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ AI 分析报告已保存: {filepath}")
        return str(filepath)


# ==================== 测试代码 ====================
if __name__ == "__main__":
    import asyncio
    
    async def test():
        generator = AnalysisGenerator()
        
        # 模拟数据
        test_data = [
            {
                "author": "elonmusk",
                "text": "Working on something exciting with humanoid robots...",
                "publish_time": "2024-01-15"
            },
            {
                "author": "sama",
                "text": "AGI could be here sooner than we think",
                "publish_time": "2024-01-14"
            }
        ]
        
        # 测试分析
        result = await generator.analyze("AI 创业信号", test_data)
        print("分析结果:")
        print(result.get('report', '')[:500])
    
    asyncio.run(test())
