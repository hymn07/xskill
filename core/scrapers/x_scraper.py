"""
x_scraper.py - Twitter/X 平台爬虫实现

基于 twikit 库，支持 Auth Token 认证和日期过滤
整合自原 zara.py 中的 TwitterScraper 类
"""

import os
import asyncio
from typing import List, Dict, Optional
from datetime import datetime, timedelta

from twikit import Client

from .base_scraper import BaseScraper


class XScraper(BaseScraper):
    """Twitter/X 爬虫：利用 Auth Token 抓取推文"""
    
    def __init__(
        self, 
        auth_token: str = None, 
        ct0: str = None,
        language: str = 'en-US'
    ):
        super().__init__(platform="twitter")
        
        self.auth_token = auth_token or os.getenv("TWITTER_AUTH_TOKEN")
        self.ct0 = ct0 or os.getenv("TWITTER_CT0")
        
        if not self.auth_token:
            raise ValueError("需要提供 auth_token 或设置 TWITTER_AUTH_TOKEN 环境变量")
        
        self.client = Client(language)
        self.cookies = {
            'auth_token': self.auth_token,
            'ct0': self.ct0 if self.ct0 else 'dummy_ct0'
        }
        self._cookies_set = False
    
    async def _ensure_cookies(self):
        """确保 cookies 已设置"""
        if not self._cookies_set:
            #print(f"DEBUG: Setting Cookies: auth_token={self.cookies.get('auth_token')}, ct0={self.cookies.get('ct0')}")
            self.client.set_cookies(self.cookies)
            self._cookies_set = True
    
    async def scrape(
        self, 
        handle: str, 
        start_date: str = None, 
        end_date: str = None,
        count: int = 20,
        max_retries: int = 2,
        base_delay: float = 30.0
    ) -> List[Dict]:
        """
        抓取指定用户的推文 (使用 search_tweet 替代 get_user_tweets 以支持更灵活的时间过滤)
        
        Rate Limiting:
            - 遇到 429 错误时重试 2 次 (30s → 60s)
            - 每次请求前添加随机延迟 (3-5秒)
        """
        await self._ensure_cookies()
        
        # 构造查询语句 from:user since:YYYY-MM-DD until:YYYY-MM-DD
        query = f"from:{handle}"
        
        # 使用传入的 start_date，如果没有则默认最近30天，确保 query 完整
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        query += f" since:{start_date}"
        
        # until 参数处理：如果不传，默认包含今天（直到明天）
        if not end_date:
            end_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        
        # 注意：search_tweet 的 until 是不包含的
        query += f" until:{end_date}"
        
        print(f"🔍 执行搜索: {query}")
        
        # 重试逻辑
        import random
        from twikit.errors import TooManyRequests
        
        for attempt in range(max_retries + 1):
            try:
                # 每次请求前添加随机延迟，避免过于频繁
                if attempt > 0 or hasattr(self, '_last_request_time'):
                    delay = random.uniform(3.0, 5.0)
                    await asyncio.sleep(delay)
                
                self._last_request_time = datetime.now()
                
                # 使用 search_tweet (product='Latest' 按时间排序)
                tweets = await self.client.search_tweet(query, product='Latest', count=count)
                
                # 转换为标准格式
                results = []
                if tweets:
                    for tweet in tweets:
                        # 尝试解析 URL
                        try:
                            url = f"https://x.com/{handle}/status/{tweet.id}"
                        except:
                            url = ""
                        
                        # 尝试安全获取属性
                        favorite_count = getattr(tweet, 'favorite_count', 0)
                        retweet_count = getattr(tweet, 'retweet_count', 0)
                        reply_count = getattr(tweet, 'reply_count', 0)
                        quote_count = getattr(tweet, 'quote_count', 0) # 新增引用数
                        view_count = getattr(tweet, 'view_count', 0)
                        if view_count is None: view_count = 0
                        lang = getattr(tweet, 'lang', '')
                        
                        # 获取作者信息 (tweet.user 属性)
                        user_name = handle
                        followers_count = 0
                        if hasattr(tweet, 'user'):
                             user_name = getattr(tweet.user, 'name', handle)
                             followers_count = getattr(tweet.user, 'followers_count', 0)

                        content = {
                            "content_id": tweet.id,
                            "author": handle,
                            "author_name": user_name,
                            "text": tweet.text,
                            "publish_time": self._parse_twitter_time(tweet.created_at), # twikit 返回的是格式化好的时间字符串
                            "url": url,
                            "platform": "twitter",
                            "metrics": {
                                "likes": favorite_count,
                                "retweets": retweet_count,
                                "replies": reply_count,
                                "quotes": quote_count,
                                "views": view_count,
                            },
                            "lang": lang,
                            "is_retweet": str(tweet.text).startswith("RT @"), # 简单判断
                            "metadata": {
                                "raw_created_at": str(tweet.created_at),
                                "author_followers": followers_count
                            }
                        }
                        results.append(content)
                
                # 二次日期过滤（双重保险，且 search_tweet 有时不精准）
                # 注意：filter_by_date 需要与 publish_time 格式匹配
                # 这里 publish_time 是 twikit 的字符串，filter_by_date 内部会解析
                if start_date or end_date:
                    # 传入简单的日期字符串用于比较
                    results = self.filter_by_date(results, start_date, end_date)
                
                return results
                
            except TooManyRequests as e:
                if attempt < max_retries:
                    # 指数退避: 30s → 60s
                    wait_time = base_delay * (2 ** attempt)
                    
                    # 尝试从响应头获取重置时间
                    if hasattr(e, 'headers') and e.headers:
                        reset_time = e.headers.get('x-rate-limit-reset')
                        if reset_time:
                            try:
                                reset_dt = datetime.fromtimestamp(int(reset_time))
                                wait_time = max(wait_time, (reset_dt - datetime.now()).total_seconds() + 5)
                            except:
                                pass
                    
                    print(f"⏳ 触发速率限制，等待 {wait_time:.0f} 秒后重试 (第 {attempt + 1}/{max_retries} 次)...")
                    await asyncio.sleep(wait_time)
                else:
                    print(f"❌ 抓取 @{handle} 失败: 达到最大重试次数 ({max_retries})")
                    return []
                    
            except Exception as e:
                print(f"❌ 抓取 @{handle} 失败: {e}")
                import traceback
                traceback.print_exc()
                return []
        
        return []
    
    async def validate_credentials(self) -> bool:
        """验证 Twitter 凭据是否有效"""
        await self._ensure_cookies()
        
        try:
            # 尝试获取自己的信息作为验证
            me = await self.client.get_user_by_screen_name("twitter")
            return me is not None
        except Exception as e:
            print(f"❌ 凭据验证失败: {e}")
            return False
    
    def _parse_twitter_time(self, twitter_time) -> str:
        """
        解析 Twitter 时间格式
        
        Twitter 返回格式如: "Sat Jan 20 10:30:00 +0000 2024"
        """
        if isinstance(twitter_time, datetime):
            return twitter_time.isoformat()
        
        if isinstance(twitter_time, str):
            try:
                # 尝试标准 Twitter 格式
                dt = datetime.strptime(
                    twitter_time, 
                    "%a %b %d %H:%M:%S %z %Y"
                )
                return dt.isoformat()
            except:
                pass
            
            # 尝试 ISO 格式
            try:
                dt = datetime.fromisoformat(twitter_time.replace("Z", "+00:00"))
                return dt.isoformat()
            except:
                pass
        
        # 无法解析，返回当前时间
        return datetime.now().isoformat()
    
    async def get_user_info(self, handle: str) -> Optional[Dict]:
        """获取用户详细信息"""
        await self._ensure_cookies()
        
        try:
            user = await self.client.get_user_by_screen_name(handle)
            return {
                "id": user.id,
                "name": user.name,
                "screen_name": user.screen_name,
                "description": getattr(user, 'description', ''),
                "followers_count": getattr(user, 'followers_count', 0),
                "following_count": getattr(user, 'following_count', 0),
                "verified": getattr(user, 'verified', False)
            }
        except Exception as e:
            print(f"❌ 获取用户信息失败: {e}")
            return None


# ==================== 兼容性别名 ====================
# 保持与原 zara.py 的兼容
TwitterScraper = XScraper


# ==================== 测试代码 ====================
if __name__ == "__main__":
    import asyncio
    
    async def test():
        # 需要设置环境变量: TWITTER_AUTH_TOKEN
        scraper = XScraper()
        
        # 验证凭据
        valid = await scraper.validate_credentials()
        print(f"凭据有效: {valid}")
        
        if valid:
            # 抓取示例
            tweets = await scraper.scrape("elonmusk", count=5)
            print(f"获取到 {len(tweets)} 条推文")
            for t in tweets[:2]:
                print(f"  - {t['text'][:50]}...")
    
    asyncio.run(test())
