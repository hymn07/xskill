import json
import os
import asyncio
from datetime import datetime
from bs4 import BeautifulSoup
import requests
from twikit import Client

class AccountDiscoverer:
    """账号发现器：负责爬取页面并维护增量账号池"""
    def __init__(self, target_url="https://zara.faces.site/ai", db_path="accounts.json"):
        self.target_url = target_url
        self.db_path = db_path
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36..."}

    def fetch_and_update(self):
        # 1. 加载现有库
        accounts = []
        existing_urls = set()
        if os.path.exists(self.db_path):
            with open(self.db_path, 'r', encoding='utf-8') as f:
                accounts = json.load(f)
                existing_urls = {a['url'] for a in accounts}

        # 2. 爬取目标网页
        resp = requests.get(self.target_url, headers=self.headers)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # 3. 解析博主卡片 (匹配你提供的 div 结构)
        new_count = 0
        cards = soup.find_all('div', class_='bg-white rounded-2xl')
        for card in cards:
            link_tag = card.find('a', href=True)
            if link_tag and link_tag['href'] not in existing_urls:
                name = card.find('strong').text if card.find('strong') else "Unknown"
                desc = card.find_all('p')[-1].text if card.find_all('p') else ""
                url = link_tag['href']
                
                # 提取用户名 (从 x.com/username 中提取)
                screen_name = url.split('/')[-1].split('?')[0]
                
                accounts.append({
                    "name": name,
                    "screen_name": screen_name,
                    "url": url,
                    "description": desc,
                    "source": "张咋啦推荐",
                    "updated_at": datetime.now().isoformat()
                })
                existing_urls.add(url)
                new_count += 1

        # 4. 保存 (只增不减)
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(accounts, f, ensure_ascii=False, indent=2)
        return new_count

class TwitterScraper:
    """推文抓取器：利用 Auth Token 抓取最新内容"""
    def __init__(self, auth_token, ct0=None):
        self.client = Client('en-US')
        # RSSHub 通常只配 auth_token，但 twikit/Twitter API 最好带上 ct0
        self.cookies = {
            'auth_token': auth_token,
            'ct0': ct0 if ct0 else 'provide_a_dummy_or_get_from_browser'
        }

    async def get_latest_tweets(self, screen_name, count=10):
        """抓取特定用户的最新推文，细化到单条推文属性"""
        try:
            # 首次运行需加载 cookies
            self.client.set_cookies(self.cookies)
            user = await self.client.get_user_by_screen_name(screen_name)
            tweets = await self.client.get_user_tweets(user.id, 'Tweets', count=count)
            
            results = []
            for t in tweets:
                results.append({
                    "tweet_id": t.id,
                    "text": t.text,
                    "created_at": t.created_at,
                    "url": f"https://x.com/{screen_name}/status/{t.id}",
                    "author": screen_name,
                    "is_retweet": hasattr(t, 'retweeted_status')
                })
            return results
        except Exception as e:
            print(f"Error fetching {screen_name}: {e}")
            return []

# --- 交付用的 Main 逻辑 ---
async def run_pipeline(auth_token):
    # 步骤 1: 更新账号池
    discoverer = AccountDiscoverer()
    new_acc = discoverer.fetch_and_update()
    print(f"账号池更新：新增 {new_acc} 个博主")

    # 步骤 2: 抓取推文 (示例：前 2 个博主)
    with open('accounts.json', 'r') as f:
        pool = json.load(f)
    
    scraper = TwitterScraper(auth_token)
    all_new_tweets = []
    
    for acc in pool[:2]: # 示例只抓前两个，防止触发风控
        print(f"正在抓取 {acc['name']} 的动态...")
        tweets = await scraper.get_latest_tweets(acc['screen_name'])
        all_new_tweets.extend(tweets)
    
    # 步骤 3: 增量写入 raw_tweets.json (需自行实现去重逻辑)
    print(f"本次共获取 {len(all_new_tweets)} 条推文")