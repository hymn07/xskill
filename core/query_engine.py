"""
query_engine.py - 三级身份识别路由

核心职责:
1. 精确匹配 - accounts.json 直接查询
2. 模糊匹配 - 使用 thefuzz 库进行字符串相似度计算
3. LLM 语义判定 - 调用 OpenRouter API 解析用户意图

支持从自然语言中识别博主身份和时间区间
"""

import os
import re
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, List
from pathlib import Path

import requests
from thefuzz import fuzz, process

from .discoverer import AccountDiscoverer


class QueryEngine:
    """查询引擎：三级递进式身份识别与意图解析"""
    
    def __init__(
        self, 
        discoverer: AccountDiscoverer = None,
        openrouter_api_key: str = None,
        fuzzy_threshold: int = 70
    ):
        self.discoverer = discoverer or AccountDiscoverer()
        self.fuzzy_threshold = fuzzy_threshold
        
        # OpenRouter API 配置
        self.api_key = openrouter_api_key or os.getenv("OPENROUTER_API_KEY")
        self.api_base = "https://openrouter.ai/api/v1/chat/completions"
        self.model = "anthropic/claude-3-haiku"  # 默认使用 Haiku，性价比高
    
    def identify(self, query: str) -> Dict:
        """
        三级递进式身份识别
        
        Args:
            query: 用户查询，如 "马斯克"、"elonmusk"、"Elon Musk"
            
        Returns:
            {
                "status": "found" | "fuzzy_match" | "llm_identified" | "new_account" | "not_found",
                "handle": str or None,
                "account": dict or None,
                "confidence": float,
                "message": str
            }
        """
        accounts = self.discoverer.get_all_accounts()
        
        if not accounts:
            return {
                "status": "not_found",
                "handle": None,
                "account": None,
                "confidence": 0,
                "message": "账号池为空，请先运行账号发现"
            }
        
        # Level 1: 精确匹配
        result = self._exact_match(query, accounts)
        if result:
            return {
                "status": "found",
                "handle": result["screen_name"],
                "account": result,
                "confidence": 1.0,
                "message": f"精确匹配到: @{result['screen_name']}"
            }
        
        # Level 2: 模糊匹配
        result, score = self._fuzzy_match(query, accounts)
        if result and score >= self.fuzzy_threshold:
            return {
                "status": "fuzzy_match",
                "handle": result["screen_name"],
                "account": result,
                "confidence": score / 100,
                "message": f"模糊匹配到: @{result['screen_name']} (相似度: {score}%)"
            }
        
        # Level 3: LLM 语义判定
        if self.api_key:
            llm_result = self._llm_identify(query, accounts)
            if llm_result:
                return llm_result
        
        # 未找到 - 可能是新账号
        return {
            "status": "new_account",
            "handle": self._guess_handle(query),
            "account": None,
            "confidence": 0.3,
            "message": f"未在名单中找到，这可能是一个新账号"
        }
    
    def _exact_match(self, query: str, accounts: List[Dict]) -> Optional[Dict]:
        """精确匹配"""
        query_lower = query.lower().strip()
        query_clean = query_lower.lstrip('@')
        
        for acc in accounts:
            # 匹配 screen_name
            if acc.get('screen_name', '').lower() == query_clean:
                return acc
            # 匹配 name
            if acc.get('name', '').lower() == query_lower:
                return acc
        
        return None
    
    def _fuzzy_match(self, query: str, accounts: List[Dict]) -> Tuple[Optional[Dict], int]:
        """模糊匹配"""
        query_lower = query.lower().strip()
        
        # 构建候选列表
        candidates = []
        for acc in accounts:
            candidates.append((acc.get('name', ''), acc))
            candidates.append((acc.get('screen_name', ''), acc))
        
        if not candidates:
            return None, 0
        
        # 使用 thefuzz 进行匹配
        names = [c[0] for c in candidates]
        best_match = process.extractOne(query_lower, names, scorer=fuzz.ratio)
        
        if best_match:
            matched_name, score, idx = best_match[0], best_match[1], names.index(best_match[0])
            return candidates[idx][1], score
        
        return None, 0
    
    def _llm_identify(self, query: str, accounts: List[Dict]) -> Optional[Dict]:
        """使用 OpenRouter LLM 进行语义识别"""
        
        # 构建账号列表描述
        account_list = "\n".join([
            f"- {acc.get('name', 'Unknown')} (@{acc.get('screen_name', '')}): {acc.get('description', '')[:100]}"
            for acc in accounts[:50]  # 限制数量避免 token 过多
        ])
        
        prompt = f"""你是一个身份识别助手。用户输入了一个查询词，请判断它指的是下面名单中的哪个人。

用户查询: "{query}"

已知账号名单:
{account_list}

请回复:
1. 如果能确定是名单中的某人，回复 JSON: {{"found": true, "screen_name": "xxx", "confidence": 0.9}}
2. 如果查询像是一个 Twitter/X 用户名但不在名单中，回复: {{"found": false, "is_new_account": true, "guessed_handle": "xxx"}}
3. 如果完全无法判断，回复: {{"found": false, "is_new_account": false}}

只回复 JSON，不要其他内容。"""

        try:
            response = requests.post(
                self.api_base,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 200
                },
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            content = result['choices'][0]['message']['content'].strip()
            
            # 解析 LLM 返回的 JSON
            import json
            llm_result = json.loads(content)
            
            if llm_result.get('found'):
                screen_name = llm_result.get('screen_name')
                account = self.discoverer.get_account_by_handle(screen_name)
                if account:
                    return {
                        "status": "llm_identified",
                        "handle": screen_name,
                        "account": account,
                        "confidence": llm_result.get('confidence', 0.8),
                        "message": f"LLM 识别为: @{screen_name}"
                    }
            
            if llm_result.get('is_new_account'):
                return {
                    "status": "new_account",
                    "handle": llm_result.get('guessed_handle'),
                    "account": None,
                    "confidence": 0.5,
                    "message": "LLM 判断这是一个名单外的新账号"
                }
                
        except Exception as e:
            print(f"⚠️ LLM 识别失败: {e}")
        
        return None
    
    def _guess_handle(self, query: str) -> Optional[str]:
        """尝试从查询中猜测 handle"""
        # 移除 @ 符号
        clean = query.strip().lstrip('@')
        
        # 如果看起来像用户名（无空格，字母数字下划线）
        if re.match(r'^[a-zA-Z0-9_]+$', clean):
            return clean
        
        return None
    
    # ==================== 时间解析 ====================
    
    def parse_time_range(self, query: str) -> Tuple[Optional[str], Optional[str]]:
        """
        从自然语言中解析时间区间
        
        Args:
            query: 用户查询，如 "最近一周"、"一月份"、"从1月1号到15号"
            
        Returns:
            (start_date, end_date) 格式为 YYYY-MM-DD，如果无法解析则返回 (None, None)
        """
        today = datetime.now()
        
        # 常见时间表达式匹配
        patterns = {
            r'最近(\d+)天': lambda m: (today - timedelta(days=int(m.group(1))), today),
            r'最近一周': lambda m: (today - timedelta(days=7), today),
            r'最近一个月': lambda m: (today - timedelta(days=30), today),
            r'本周': lambda m: (today - timedelta(days=today.weekday()), today),
            r'本月': lambda m: (today.replace(day=1), today),
            r'上周': lambda m: (
                today - timedelta(days=today.weekday() + 7),
                today - timedelta(days=today.weekday() + 1)
            ),
            r'上个月': lambda m: (
                (today.replace(day=1) - timedelta(days=1)).replace(day=1),
                today.replace(day=1) - timedelta(days=1)
            ),
            r'(\d{1,2})月(\d{1,2})日?[到至-](\d{1,2})日?': lambda m: (
                today.replace(month=int(m.group(1)), day=int(m.group(2))),
                today.replace(month=int(m.group(1)), day=int(m.group(3)))
            ),
            r'(\d{1,2})月份?': lambda m: (
                today.replace(month=int(m.group(1)), day=1),
                (today.replace(month=int(m.group(1)) + 1, day=1) - timedelta(days=1)) 
                if int(m.group(1)) < 12 
                else today.replace(month=12, day=31)
            ),
        }
        
        for pattern, handler in patterns.items():
            match = re.search(pattern, query)
            if match:
                try:
                    start, end = handler(match)
                    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
                except:
                    pass
        
        # 无法解析
        return None, None
    
    def ask_for_time_range(self) -> str:
        """生成询问时间范围的提示"""
        return "老板，您想看哪个时间段的分析？可以说「最近一周」「本月」或「1月1日到15日」"
    
    def identify_multiple(self, query: str) -> dict:
        """
        识别多个用户或"全部"
        
        Args:
            query: 用户查询，如 "看一下全部的"、"a和b的"、"a和b和c的"
            
        Returns:
            {
                "mode": "all" | "multiple" | "single",
                "handles": [用户名列表] or [],
                "message": 提示信息
            }
        """
        # 检查 "全部" "所有"
        if any(keyword in query for keyword in ["全部", "所有", "all", "everyone"]):
            all_accounts = self.discoverer.get_all_accounts()
            if not all_accounts:
                return {
                    "mode": "none",
                    "handles": [],
                    "message": "账号池为空，请先更新账号池"
                }
            
            handles = [acc['screen_name'] for acc in all_accounts]
            return {
                "mode": "all",
                "handles": handles,
                "message": f"已选择所有 {len(handles)} 个账号"
            }
        
        # 检查是否有 "和" "、" "," 等分隔符，表示多个用户
        import re
        # 分割查询词，支持更多分隔符和英文 "and"
        parts = re.split(r'[,，、和\s]+|and', query, flags=re.IGNORECASE)
        # 过滤空字符串和更广泛的停用词
        stop_words = {
            '看', '一下', '的', '查询', '显示', '导出', '分析', '最近', '本月', '本周', 
            '帖子', '推文', '动态', '关于', '总结', '生成', '报告', '博主', ''
        }
        potential_names = [p.strip() for p in parts if p.strip() and p.strip().lower() not in stop_words]
        
        if len(potential_names) > 1:
            # 多个用户，逐个识别
            handles = []
            failed = []
            
            for name in potential_names:
                result = self.identify(name)
                if result['status'] in ['found', 'fuzzy_match', 'llm_identified']:
                    handles.append(result['handle'])
                else:
                    failed.append(name)
            
            if len(handles) > 1:
                message = f"已识别 {len(handles)} 个用户: {', '.join(handles)}"
                if failed:
                    message += f" (未找到: {', '.join(failed)})"
                
                return {
                    "mode": "multiple",
                    "handles": list(set(handles)), # 去重
                    "message": message
                }

        # Fallback: 如果正则匹配没找到多个，或者只识别出一个，但查询语句看着像多个
        # 使用 LLM 重新判定整个查询中提到的所有博主
        if self.api_key and any(keyword in query.lower() for keyword in ["和", "与", "及", "and", ",", "，"]):
            llm_handles = self._llm_identify_multiple(query)
            if len(llm_handles) > 0:
                return {
                    "mode": "multiple",
                    "handles": llm_handles,
                    "message": f"LLM 识别到 {len(llm_handles)} 个用户: {', '.join(llm_handles)}"
                }
        
        # 单个用户
        result = self.identify(query)
        if result['status'] in ['found', 'fuzzy_match', 'llm_identified']:
            return {
                "mode": "single",
                "handles": [result['handle']],
                "message": f"识别为: @{result['handle']}"
            }
        else:
            return {
                "mode": "none",
                "handles": [],
                "message": result.get('message', '未找到匹配的用户')
            }

    def _llm_identify_multiple(self, query: str) -> List[str]:
        """使用 LLM 从查询中提取所有匹配的 handle"""
        accounts = self.discoverer.get_all_accounts()
        account_list = "\n".join([
            f"- {acc.get('name', 'Unknown')} (@{acc.get('screen_name', '')}): {acc.get('description', '')[:60]}"
            for acc in accounts[:100]
        ])
        
        prompt = f"""你是一个推特账号识别专家。请从用户查询中提取出所有正在被提及的博主。
用户查询: "{query}"

候选名单:
{account_list}

请根据名单识别出查询中提到的所有 screen_name（即以 @ 开头的那个标识符）。
只需返回一个 JSON 数组，包含所有识别出的 screen_name（不带 @ 符号）。
例如: ["elonmusk", "karpathy"]
如果没有找到，返回空数组 []。
不要输出任何解释说明。"""

        try:
            response = requests.post(
                self.api_base,
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 300
                },
                timeout=30
            )
            response.raise_for_status()
            content = response.json()['choices'][0]['message']['content'].strip()
            import json
            handles = json.loads(content)
            if isinstance(handles, list):
                # 验证 handle 是否真的存在于名单中
                valid_handles = [h for h in handles if self.discoverer.get_account_by_handle(h)]
                return valid_handles
        except Exception as e:
            print(f"⚠️ LLM 多用户识别失败: {e}")
        return []


# ==================== 测试代码 ====================
if __name__ == "__main__":
    engine = QueryEngine()
    
    # 测试身份识别
    test_queries = ["马斯克", "elonmusk", "Elon", "@yishan"]
    for q in test_queries:
        result = engine.identify(q)
        print(f"查询 '{q}': {result['status']} - {result['message']}")
    
    # 测试时间解析
    time_queries = ["最近一周", "本月", "1月5日到20日", "上个月"]
    for q in time_queries:
        start, end = engine.parse_time_range(q)
        print(f"时间 '{q}': {start} 到 {end}")
