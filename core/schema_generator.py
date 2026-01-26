"""
schema_generator.py - 从用户自然语言生成标注 Schema

核心职责:
1. 理解用户的标注需求
2. 生成标准化的 Schema 定义（JSON 格式）
3. 验证 Schema 的合法性
"""

import os
import json
import re
from typing import Dict, Optional

import requests


class SchemaGenerator:
    """从用户自然语言需求生成标注 Schema"""
    
    def __init__(
        self,
        openrouter_api_key: str = None,
        model: str = "google/gemini-2.5-flash-preview-09-2025"
    ):
        self.api_key = openrouter_api_key or os.getenv("OPENROUTER_API_KEY")
        self.api_base = "https://openrouter.ai/api/v1/chat/completions"
        self.model = model
    
    async def generate_from_user_intent(self, user_query: str) -> Dict:
        """
        从用户自然语言需求生成标注 Schema
        
        Args:
            user_query: 用户描述的标注需求，如：
                       "我想标注推文的投资价值，包括信号强度1-5分、赛道分类、是否融资"
        
        Returns:
            Schema 定义字典：
            {
                "schema_name": "investment_signal",
                "description": "投资信号评估",
                "fields": [
                    {
                        "name": "signal_strength",
                        "display_name": "信号强度",
                        "type": "integer",
                        "range": [1, 5],
                        "description": "..."
                    },
                    ...
                ]
            }
        """
        prompt = self._build_schema_generation_prompt(user_query)
        
        try:
            response = await self._call_llm(prompt)
            schema = self._parse_schema_from_response(response)
            
            # 验证 Schema
            self._validate_schema(schema)
            
            return schema
            
        except Exception as e:
            raise ValueError(f"Schema 生成失败: {e}")
    
    def _build_schema_generation_prompt(self, user_query: str) -> str:
        """构建 Schema 生成的 Prompt"""
        return f"""你是一位数据标注专家。用户想对推文进行标注，请根据他们的需求设计一套完整的标注 Schema。

用户需求：
"{user_query}"

请生成一个标注 Schema，包含以下内容：

1. **schema_name**: 英文标识符，用下划线连接，如 "investment_signal"
2. **description**: 中文描述，简要说明这个 Schema 的用途
3. **fields**: 字段列表，每个字段包含：
   - name: 英文字段名（小写，下划线连接）
   - display_name: 中文显示名称
   - type: 数据类型，可选值：
     * "integer" - 整数
     * "float" - 浮点数
     * "boolean" - 布尔值
     * "enum" - 枚举（从固定选项中选一个）
     * "text" - 自由文本
   - description: 字段说明
   - 如果是 integer/float 且有范围限制，添加 "range": [min, max]
   - 如果是 enum，添加 "values": ["选项1", "选项2", ...]

**重要**：
- 字段数量控制在 3-6 个
- 优先使用 enum 而不是自由 text（便于后续分析）
- range 和 values 要明确

请以 **纯 JSON 格式** 返回，不要有任何其他文字。格式示例：

{{
  "schema_name": "investment_signal",
  "description": "投资信号评估",
  "fields": [
    {{
      "name": "signal_strength",
      "display_name": "信号强度",
      "type": "integer",
      "range": [1, 5],
      "description": "投资信号的强弱程度，1表示很弱，5表示极强"
    }},
    {{
      "name": "track_category",
      "display_name": "赛道类别",
      "type": "enum",
      "values": ["AI", "Web3", "硬件", "SaaS", "其他"],
      "description": "所属投资赛道"
    }}
  ]
}}"""
    
    async def _call_llm(self, prompt: str, max_tokens: int = 2000) -> str:
        """调用 LLM"""
        if not self.api_key:
            raise ValueError("未配置 OPENROUTER_API_KEY")
        
        try:
            response = requests.post(
                self.api_base,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/xskill",
                    "X-Title": "XSkill Schema Generator"
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": max_tokens
                },
                timeout=120
            )
            response.raise_for_status()
            
            result = response.json()
            return result['choices'][0]['message']['content']
            
        except Exception as e:
            raise Exception(f"LLM 调用失败: {e}")
    
    def _parse_schema_from_response(self, response: str) -> Dict:
        """从 LLM 响应中提取 JSON Schema"""
        # 尝试提取 JSON
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if not match:
            raise ValueError("无法从响应中提取 JSON")
        
        json_text = match.group()
        schema = json.loads(json_text)
        
        return schema
    
    def _validate_schema(self, schema: Dict):
        """验证 Schema 的合法性"""
        required_keys = ['schema_name', 'description', 'fields']
        for key in required_keys:
            if key not in schema:
                raise ValueError(f"Schema 缺少必需字段: {key}")
        
        if not isinstance(schema['fields'], list) or len(schema['fields']) == 0:
            raise ValueError("fields 必须是非空列表")
        
        # 验证字段名合法性
        field_names = set()
        for field in schema['fields']:
            # 检查必需字段
            if 'name' not in field or 'display_name' not in field or 'type' not in field:
                raise ValueError(f"字段定义不完整: {field}")
            
            # 检查字段名重复
            if field['name'] in field_names:
                raise ValueError(f"字段名重复: {field['name']}")
            field_names.add(field['name'])
            
            # 检查字段名格式（只允许字母、数字、下划线）
            if not re.match(r'^[a-z][a-z0-9_]*$', field['name']):
                raise ValueError(f"字段名格式不合法: {field['name']} (只允许小写字母、数字、下划线)")
            
            # 检查类型
            valid_types = ['integer', 'float', 'boolean', 'enum', 'text']
            if field['type'] not in valid_types:
                raise ValueError(f"不支持的类型: {field['type']}")
            
            # 验证 enum 必须有 values
            if field['type'] == 'enum' and 'values' not in field:
                raise ValueError(f"enum 类型字段必须指定 values: {field['name']}")
    
    def schema_to_sql_type(self, field: Dict) -> str:
        """将 Schema 字段类型转换为 SQL 类型"""
        type_mapping = {
            'integer': 'INTEGER',
            'float': 'REAL',
            'boolean': 'INTEGER',  # SQLite 用 0/1
            'enum': 'TEXT',
            'text': 'TEXT'
        }
        return type_mapping.get(field['type'], 'TEXT')


# ==================== 测试代码 ====================
if __name__ == "__main__":
    import asyncio
    
    async def test():
        generator = SchemaGenerator()
        
        # 测试用户需求
        user_query = """
        我想对推文进行投资信号评估，包括：
        1. 信号强度（1-5分）
        2. 赛道分类（AI、Web3、硬件、其他）
        3. 是否提到融资信息
        4. 风险等级（低、中、高）
        """
        
        print("📝 用户需求:")
        print(user_query)
        print("\n🔄 正在生成 Schema...")
        
        schema = await generator.generate_from_user_intent(user_query)
        
        print("\n✅ 生成的 Schema:")
        print(json.dumps(schema, ensure_ascii=False, indent=2))
    
    asyncio.run(test())
