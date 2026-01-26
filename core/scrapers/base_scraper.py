"""
base_scraper.py - 爬虫抽象基类

定义所有平台爬虫的统一接口，方便后续扩展 YouTube、Reddit 等平台
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from datetime import datetime


class BaseScraper(ABC):
    """爬虫基类：定义统一的抓取接口"""
    
    def __init__(self, platform: str):
        self.platform = platform
    
    @abstractmethod
    async def scrape(
        self, 
        handle: str, 
        start_date: str = None, 
        end_date: str = None,
        count: int = 20
    ) -> List[Dict]:
        """
        抓取指定用户在特定时间范围内的内容
        
        Args:
            handle: 用户标识符（如 screen_name）
            start_date: 起始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            count: 最大抓取数量
            
        Returns:
            标准化的内容列表，每条包含:
            {
                "content_id": str,     # 唯一标识符
                "author": str,         # 作者标识
                "text": str,           # 文本内容
                "publish_time": str,   # 发布时间 ISO 格式
                "url": str,            # 原文链接
                "platform": str,       # 平台标识
                "is_retweet": bool,    # 是否转发/转载
                "metadata": dict       # 平台特有元数据
            }
        """
        pass
    
    @abstractmethod
    async def validate_credentials(self) -> bool:
        """验证凭据是否有效"""
        pass
    
    def normalize_content(self, raw_content: Dict) -> Dict:
        """
        将平台特定格式转换为标准格式
        
        子类可以重写此方法处理平台特殊字段
        """
        return {
            "content_id": raw_content.get("id"),
            "author": raw_content.get("author"),
            "text": raw_content.get("text"),
            "publish_time": raw_content.get("publish_time"),
            "url": raw_content.get("url"),
            "platform": self.platform,
            "is_retweet": raw_content.get("is_retweet", False),
            "metadata": raw_content.get("metadata", {})
        }
    
    def filter_by_date(
        self, 
        contents: List[Dict], 
        start_date: str = None, 
        end_date: str = None
    ) -> List[Dict]:
        """按日期过滤内容"""
        if not start_date and not end_date:
            return contents
        
        filtered = []
        for content in contents:
            pub_time = content.get("publish_time", "")
            if not pub_time:
                continue
            
            # 解析发布时间（处理多种格式）
            try:
                if "T" in pub_time:
                    pub_date = datetime.fromisoformat(pub_time.replace("Z", "+00:00"))
                else:
                    pub_date = datetime.strptime(pub_time[:10], "%Y-%m-%d")
            except:
                continue
            
            # 检查日期范围
            if start_date:
                start = datetime.strptime(start_date, "%Y-%m-%d")
                if pub_date.replace(tzinfo=None) < start:
                    continue
            
            if end_date:
                end = datetime.strptime(end_date, "%Y-%m-%d").replace(
                    hour=23, minute=59, second=59
                )
                if pub_date.replace(tzinfo=None) > end:
                    continue
            
            filtered.append(content)
        
        return filtered
