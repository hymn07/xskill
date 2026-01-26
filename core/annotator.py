"""
annotator.py - 动态推文标注引擎 (完全重构版)

核心职责:
1. 根据用户提供的 Schema 动态生成标注 Prompt
2. 批量调用 LLM 进行标注
3. 解析结构化返回数据
4. 动态写入数据库对应列
"""

import os
import json
import sqlite3
import asyncio
from typing import List, Dict, Optional, Union
from datetime import datetime

import requests


class DynamicAnnotator:
    """动态标注引擎 - 支持用户自定义任意标注维度"""
    
    def __init__(
        self, 
        schema: dict,
        storage_manager=None,
        openrouter_api_key: str = None,
        model: str = "google/gemini-2.5-flash-preview-09-2025",
        batch_size: int = 10
    ):
        """
        Args:
            schema: 标注 Schema 定义（由 SchemaGenerator 生成或从数据库加载）
            storage_manager: StorageManager 实例
            others: API 配置
        """
        from core.storage_manager import StorageManager
        
        self.schema = schema
        self.storage = storage_manager or StorageManager()
        self.api_key = openrouter_api_key or os.getenv("OPENROUTER_API_KEY")
        self.api_base = "https://openrouter.ai/api/v1/chat/completions"
        self.model = model
        self.batch_size = batch_size
    
    def get_unannotated_tweets(
        self,
        limit: int = None,
        author: Union[str, List[str], None] = None
    ) -> List[Dict]:
        """
        获取需要标注的推文（无状态模式）
        
        Args:
            limit: 最多返回数量
            author: 可选，单个作者或作者列表
            
        Returns:
            推文列表
        """
        conn = sqlite3.connect(self.storage.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 无状态模式下，获取所有符合条件的推文进行标注
        # ✅ 关键修复：只获取标准字段，避免获取到数据库中可能存在的旧标注字段
        clean_fields = [
            'tweet_id', 'author', 'text', 'publish_time', 'url', 
            'platform', 'is_retweet', 'like_count', 'retweet_count', 
            'reply_count', 'quote_count', 'view_count', 'lang', 
            'author_followers'
        ]
        fields_str = ", ".join(clean_fields)
        
        query = f"SELECT {fields_str} FROM content WHERE 1=1"
        params = []
        
        if author:
            if isinstance(author, list):
                placeholders = ', '.join(['?'] * len(author))
                query += f" AND author IN ({placeholders})"
                params.extend(author)
            else:
                query += " AND author = ?"
                params.append(author)
        
        if limit:
            query += f" LIMIT {limit}"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    async def annotate_batch(self, tweets: List[Dict]) -> List[Dict]:
        """
        批量标注推文
        
        Args:
            tweets: 推文列表
            
        Returns:
            标注结果列表
        """
        if not tweets:
            return []
        
        # 动态生成 Prompt
        prompt = self._generate_annotation_prompt(tweets)
        
        # 调用 LLM
        try:
            response = await self._call_llm(prompt)
            # 解析 JSON
            annotations = self._parse_annotations(response)
            
            return annotations
            
        except Exception as e:
            print(f"❌ 批量标注失败: {e}")
            return []
    
    def _generate_annotation_prompt(self, tweets: List[Dict]) -> str:
        """根据 Schema 动态生成标注 Prompt"""
        # 准备推文列表
        tweet_list = []
        for idx, tweet in enumerate(tweets, 1):
            author = tweet.get('author', 'Unknown')
            text = tweet.get('text', '')
            time = tweet.get('publish_time', '')[:10]
            
            tweet_list.append(f"{idx}. [@{author} {time}]: \"{text[:200]}\"")
        
        tweets_text = "\n".join(tweet_list)
        
        # 动态构建字段说明
        field_descriptions = []
        for field in self.schema['fields']:
            desc_parts = [
                f"{idx + 1}. **{field['name']}** ({field['display_name']}):"
            ]
            
            # 类型说明
            if field['type'] == 'integer':
                if 'range' in field:
                    desc_parts.append(f"整数 {field['range'][0]}-{field['range'][1]}")
                else:
                    desc_parts.append("整数")
            elif field['type'] == 'float':
                if 'range' in field:
                    desc_parts.append(f"浮点数 {field['range'][0]}-{field['range'][1]}")
                else:
                    desc_parts.append("浮点数")
            elif field['type'] == 'boolean':
                desc_parts.append("布尔值 (true/false)")
            elif field['type'] == 'enum':
                values_str = ", ".join(field['values'])
                desc_parts.append(f"枚举值 [{values_str}]")
            elif field['type'] == 'text':
                desc_parts.append("文本")
            
            # 字段说明
            if 'description' in field:
                desc_parts.append(f"- {field['description']}")
            
            field_descriptions.append(" ".join(desc_parts))
        
        fields_text = "\n".join(field_descriptions)
        
        # 生成示例
        example_annotation = {
            "id": 1
        }
        for field in self.schema['fields']:
            if field['type'] == 'integer':
                example_annotation[field['name']] = field.get('range', [1, 5])[1]
            elif field['type'] == 'boolean':
                example_annotation[field['name']] = True
            elif field['type'] == 'enum':
                example_annotation[field['name']] = field['values'][0]
            elif field['type'] == 'float':
                example_annotation[field['name']] = 3.5
            else:
                example_annotation[field['name']] = "示例文本"
        
        example_json = json.dumps(example_annotation, ensure_ascii=False, indent=2)
        
        prompt = f"""你是专业的内容分析师。请对以下 {len(tweets)} 条推文进行"{self.schema['description']}"标注。

标注维度：
{fields_text}

推文列表：
{tweets_text}

请以 **纯 JSON 数组格式** 返回，不要有任何其他文字。每个元素对应一条推文，格式：

[
{example_json},
  ...
]

重要提示：
- id 字段对应推文序号（1, 2, 3...）
- 所有字段都必须填写
- 枚举值必须严格匹配给定选项
- 整数/浮点数必须在指定范围内"""
        
        return prompt
    
    async def _call_llm(self, prompt: str, max_tokens: int = 3000) -> str:
        """调用 OpenRouter API"""
        if not self.api_key:
            raise ValueError("未配置 OPENROUTER_API_KEY")
        
        try:
            response = requests.post(
                self.api_base,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/xskill",
                    "X-Title": "XSkill Dynamic Annotator"
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": max_tokens
                },
                timeout=180
            )
            response.raise_for_status()
            
            result = response.json()
            return result['choices'][0]['message']['content']
            
        except Exception as e:
            raise Exception(f"LLM 调用失败: {str(e)}")
    
    def _parse_annotations(self, response: str) -> List[Dict]:
        """解析 LLM 返回的 JSON"""
        try:
            import re
            
            # 查找第一个 [ 到最后一个 ]
            match = re.search(r'\[.*\]', response, re.DOTALL)
            if not match:
                raise ValueError("未找到 JSON 数组")
            
            json_text = match.group()
            annotations = json.loads(json_text)
            
            return annotations
            
        except Exception as e:
            print(f"❌ JSON 解析失败: {e}")
            print(f"原始响应: {response[:500]}")
            return []
    
    def save_annotations(self, tweets: List[Dict], annotations: List[Dict]) -> int:
        """
        动态保存标注结果到数据库
        
        Args:
            tweets: 原始推文列表
            annotations: 标注结果列表（按 id 索引）
            
        Returns:
            成功更新的数量
        """
        conn = sqlite3.connect(self.storage.db_path)
        cursor = conn.cursor()
        
        updated = 0
        
        # 创建 id -> annotation 的映射
        ann_map = {ann['id']: ann for ann in annotations}
        
        # 动态构建 UPDATE SQL
        field_names = [field['name'] for field in self.schema['fields']]
        set_clause = ", ".join([f"{name} = ?" for name in field_names])
        
        for idx, tweet in enumerate(tweets, 1):
            tweet_id = tweet.get('tweet_id')
            if not tweet_id:
                continue
            
            # 获取对应的标注
            ann = ann_map.get(idx)
            if not ann:
                print(f"⚠️ 推文 {tweet_id} 没有对应的标注")
                continue
            
            try:
                # 提取字段值
                values = []
                for field in self.schema['fields']:
                    value = ann.get(field['name'])
                    
                    # 类型转换
                    if field['type'] == 'boolean':
                        value = 1 if value else 0
                    elif field['type'] in ['integer', 'float', 'enum', 'text']:
                        pass  # 保持原样
                    
                    values.append(value)
                
                # 执行更新
                cursor.execute(f'''
                    UPDATE content
                    SET {set_clause}
                    WHERE tweet_id = ?
                ''', values + [tweet_id])
                
                if cursor.rowcount > 0:
                    updated += 1
                    
            except Exception as e:
                print(f"❌ 保存标注失败 (tweet_id={tweet_id}): {e}")
        
        conn.commit()
        conn.close()
        
        return updated
    
    async def annotate_all(
        self, 
        max_tweets: int = None,
        author: str = None
    ) -> List[Dict]:
        """
        标注所有符合条件的推文 (无状态)
        
        Args:
            max_tweets: 最多标注数量
            author: 可选，只标注特定作者
            
        Returns:
            带有标注字段的新列表
        """
        tweets = self.get_unannotated_tweets(limit=max_tweets, author=author)
        
        if not tweets:
            return []
        
        print(f"📋 正在标注 {len(tweets)} 条符合条件的推文...")
        
        annotated_results = []
        batches = [tweets[i:i + self.batch_size] 
                   for i in range(0, len(tweets), self.batch_size)]
        
        for batch_idx, batch in enumerate(batches, 1):
            print(f"🔄 处理批次 {batch_idx}/{len(batches)} ({len(batch)} 条)...")
            
            # 批量获取 AI 标注
            annotations = await self.annotate_batch(batch)
            
            if annotations:
                # 组合数据 (不存数据库)
                ann_map = {ann['id']: ann for ann in annotations}
                for idx, tweet in enumerate(batch, 1):
                    ann = ann_map.get(idx, {})
                    # 合并字段
                    annotated_tweet = tweet.copy()
                    annotated_tweet.update(ann)
                    # 移除 AI 标注中可能带有的 id (标注序号)
                    if 'id' in annotated_tweet and annotated_tweet['id'] != tweet.get('id'):
                        del annotated_tweet['id']
                    
                    annotated_results.append(annotated_tweet)
            
            # 避免 API 限流
            if batch_idx < len(batches):
                await asyncio.sleep(1)
        
        return annotated_results


# ==================== 测试代码 ====================
if __name__ == "__main__":
    async def test():
        # 模拟 Schema
        test_schema = {
            "schema_name": "test_signal",
            "description": "测试信号评估",
            "fields": [
                {
                    "name": "test_score",
                    "display_name": "测试分数",
                    "type": "integer",
                    "range": [1, 5],
                    "description": "测试评分"
                },
                {
                    "name": "test_category",
                    "display_name": "测试分类",
                    "type": "enum",
                    "values": ["类型A", "类型B"],
                    "description": "分类"
                }
            ]
        }
        
        annotator = DynamicAnnotator(schema=test_schema, batch_size=5)
        
        # 测试获取未标注推文
        tweets = annotator.get_unannotated_tweets(limit=5)
        print(f"未标注推文数: {len(tweets)}")
        
        if tweets:
            # 测试标注
            result = await annotator.annotate_all(max_tweets=10)
            print(f"\n标注结果: {result}")
    
    asyncio.run(test())
