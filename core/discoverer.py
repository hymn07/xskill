"""
discoverer.py - 账号发现引擎

核心职责:
1. 监控 Zara 推荐页面 (https://zara.faces.site/ai)
2. 增量识别新增博主
3. 只增不减策略保留历史数据
4. 新博主提醒功能

基于原 zara.py 的 AccountDiscoverer 类重构
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from pathlib import Path

import requests
from bs4 import BeautifulSoup


class AccountDiscoverer:
    """账号发现器：负责爬取页面并维护增量账号池"""
    
    def __init__(
        self, 
        target_url: str = "https://zara.faces.site/ai", 
        data_dir: str = None
    ):
        self.target_url = target_url
        
        if data_dir is None:
            data_dir = Path(__file__).parent.parent / "data"
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.accounts_path = self.data_dir / "accounts.json"
        
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
    
    def _load_accounts(self) -> List[Dict]:
        """加载现有账号池"""
        if self.accounts_path.exists():
            with open(self.accounts_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    
    def _save_accounts(self, accounts: List[Dict]):
        """保存账号池"""
        with open(self.accounts_path, 'w', encoding='utf-8') as f:
            json.dump(accounts, f, ensure_ascii=False, indent=2)
    
    def fetch_and_update(self) -> Tuple[int, List[Dict]]:
        """
        从目标网页爬取博主信息并更新本地账号池
        
        Returns:
            (new_count, new_accounts): 新增数量和新增账号列表
        """
        # 1. 加载现有库
        accounts = self._load_accounts()
        existing_urls = {a['url'] for a in accounts}
        
        # 2. 爬取目标网页
        try:
            resp = requests.get(self.target_url, headers=self.headers, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"❌ 爬取失败: {e}")
            return 0, []
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # 3. 解析博主卡片 (匹配 div 结构)
        new_accounts = []
        cards = soup.find_all('div', class_='bg-white rounded-2xl')
        
        for card in cards:
            link_tag = card.find('a', href=True)
            if not link_tag:
                continue
                
            url = link_tag['href']
            
            # 跳过已存在的
            if url in existing_urls:
                continue
            
            # 解析博主信息
            name = card.find('strong').text.strip() if card.find('strong') else "Unknown"
            paragraphs = card.find_all('p')
            desc = paragraphs[-1].text.strip() if paragraphs else ""
            
            # 从 URL 提取用户名 (如 x.com/username 或 twitter.com/username)
            screen_name = self._extract_screen_name(url)
            
            new_account = {
                "name": name,
                "screen_name": screen_name,
                "url": url,
                "description": desc,
                "source": "张咋啦推荐",
                "discovered_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            accounts.append(new_account)
            new_accounts.append(new_account)
            existing_urls.add(url)
        
        # 4. 保存 (只增不减)
        if new_accounts:
            self._save_accounts(accounts)
            self._print_new_accounts_alert(new_accounts)
        
        return len(new_accounts), new_accounts
    
    def _extract_screen_name(self, url: str) -> str:
        """从 URL 中提取用户名"""
        # 处理各种格式: x.com/user, twitter.com/user, x.com/user?s=20
        try:
            path = url.split('/')[-1]
            screen_name = path.split('?')[0]
            return screen_name if screen_name else "unknown"
        except:
            return "unknown"
    
    def _print_new_accounts_alert(self, new_accounts: List[Dict]):
        """打印新增博主提醒"""
        print("\n" + "=" * 50)
        print("🚨 发现张 Zara 推荐名单更新！")
        print("=" * 50)
        for acc in new_accounts:
            print(f"  ✨ 新增关注: {acc['name']} (@{acc['screen_name']})")
            if acc['description']:
                print(f"     简介: {acc['description'][:50]}...")
        print("=" * 50 + "\n")
    
    def get_all_accounts(self) -> List[Dict]:
        """获取所有账号"""
        return self._load_accounts()
    
    def get_account_by_handle(self, screen_name: str) -> Optional[Dict]:
        """根据 screen_name 获取账号信息"""
        accounts = self._load_accounts()
        for acc in accounts:
            if acc.get('screen_name', '').lower() == screen_name.lower():
                return acc
        return None
    
    def get_account_by_name(self, name: str) -> Optional[Dict]:
        """根据名称获取账号信息"""
        accounts = self._load_accounts()
        for acc in accounts:
            if name.lower() in acc.get('name', '').lower():
                return acc
        return None
    
    def add_manual_account(
        self, 
        screen_name: str, 
        name: str = None, 
        url: str = None,
        description: str = ""
    ) -> Dict:
        """手动添加账号"""
        accounts = self._load_accounts()
        
        # 检查是否已存在
        for acc in accounts:
            if acc.get('screen_name', '').lower() == screen_name.lower():
                print(f"⚠️ 账号 @{screen_name} 已存在")
                return acc
        
        new_account = {
            "name": name or screen_name,
            "screen_name": screen_name,
            "url": url or f"https://x.com/{screen_name}",
            "description": description,
            "source": "手动添加",
            "discovered_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        accounts.append(new_account)
        self._save_accounts(accounts)
        print(f"✅ 已添加账号: @{screen_name}")
        
        return new_account
    
    def search_accounts(self, query: str) -> List[Dict]:
        """搜索账号（模糊匹配名称和描述）"""
        accounts = self._load_accounts()
        query_lower = query.lower()
        
        results = []
        for acc in accounts:
            if (query_lower in acc.get('name', '').lower() or
                query_lower in acc.get('screen_name', '').lower() or
                query_lower in acc.get('description', '').lower()):
                results.append(acc)
        
        return results


# ==================== 测试代码 ====================
if __name__ == "__main__":
    discoverer = AccountDiscoverer()
    
    # 更新账号池
    new_count, new_accounts = discoverer.fetch_and_update()
    print(f"本次更新：新增 {new_count} 个博主")
    
    # 显示所有账号
    all_accounts = discoverer.get_all_accounts()
    print(f"账号池共有 {len(all_accounts)} 个博主")
