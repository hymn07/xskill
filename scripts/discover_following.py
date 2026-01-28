"""
discover_following.py - 二级关注发现脚本

功能：
1. 读取 accounts_level1.json 中的一级账号
2. 获取每个账号的 Twitter following 列表
3. 去重并合并标签
4. 更新 accounts_level2.json

使用：
    python scripts/discover_following.py --max-accounts 3 --max-following 20 --dry-run
"""

import os
import sys
import json
import asyncio
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Set
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.scrapers.x_scraper import XScraper


class FollowingDiscoverer:
    """二级关注发现器"""
    
    def __init__(self, data_dir: str = None):
        if data_dir is None:
            data_dir = Path(__file__).parent.parent / "data"
        self.data_dir = Path(data_dir)
        self.level1_accounts_path = self.data_dir / "accounts_level1.json"
        self.level2_accounts_path = self.data_dir / "accounts_level2.json"
        self.progress_path = self.data_dir / "following_discovery_progress.json"
        self.stats_path = self.data_dir.parent / "exports" / "following_discovery_stats.xlsx"
        self.scraper = XScraper()
        self.stats = {}  # {screen_name: {following_count: int, discovered_at: str}}
    
    def _load_level1_accounts(self) -> List[Dict]:
        """加载一级账号池"""
        if self.level1_accounts_path.exists():
            with open(self.level1_accounts_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    
    def _load_level2_accounts(self) -> List[Dict]:
        """加载二级账号池"""
        if self.level2_accounts_path.exists():
            with open(self.level2_accounts_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    
    def _save_level2_accounts(self, accounts: List[Dict]):
        """保存二级账号池（原子性写入）"""
        temp_path = self.level2_accounts_path.with_suffix('.tmp')
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(accounts, f, ensure_ascii=False, indent=2)
        temp_path.replace(self.level2_accounts_path)
    
    def _load_progress(self) -> Dict:
        """加载进度"""
        if self.progress_path.exists():
            with open(self.progress_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"processed": [], "last_update": None}
    
    def _save_progress(self, progress: Dict):
        """保存进度"""
        with open(self.progress_path, 'w', encoding='utf-8') as f:
            json.dump(progress, f, ensure_ascii=False, indent=2)
    
    def _normalize_source(self, source) -> List[str]:
        """规范化 source 字段为列表"""
        if isinstance(source, list):
            return source
        elif isinstance(source, str):
            return [source]
        else:
            return []
    
    async def discover_from_following(
        self,
        max_accounts: int = None,
        max_following_per_account: int = 10000,
        dry_run: bool = False
    ):
        """
        从一级账号的 following 列表中发现二级账号
        
        Args:
            max_accounts: 最多处理多少个一级账号（None = 全部）
            max_following_per_account: 每个账号最多获取多少个 following
            dry_run: 是否为试运行（不写入文件）
        """
        print("=" * 60)
        print("🚀 开始二级关注发现")
        print("=" * 60)
        
        # 1. 加载一级账号
        primary_accounts = self._load_level1_accounts()
        
        if max_accounts:
            primary_accounts = primary_accounts[:max_accounts]
        
        print(f"📊 一级账号数量: {len(primary_accounts)}")
        print(f"📊 每个账号获取 following 数: {max_following_per_account}")
        print(f"📊 预计总耗时: ~{len(primary_accounts) * 0.5:.1f} 分钟\n")
        
        # 2. 加载进度
        progress = self._load_progress()
        processed_handles = set(progress.get("processed", []))
        
        # 3. 收集所有二级账号
        all_following = {}  # {screen_name: {info, sources: []}}
        
        for idx, account in enumerate(primary_accounts, 1):
            screen_name = account['screen_name']
            
            # 跳过已处理的
            if screen_name in processed_handles:
                print(f"⏭️  [{idx}/{len(primary_accounts)}] 跳过已处理: @{screen_name}")
                continue
            
            print(f"\n🔍 [{idx}/{len(primary_accounts)}] 正在获取 @{screen_name} 的 following...")
            
            try:
                following_list = await self.scraper.get_user_following(
                    screen_name,
                    count=None  # None = 获取全部
                )
                
                print(f"   ✅ 获取到 {len(following_list)} 个 following")
                
                # 处理每个 following
                source_tag = f"{screen_name}推荐"
                new_in_this_batch = 0
                for user in following_list:
                    user_screen_name = user['screen_name']
                    
                    # 跳过一级账号自己
                    if user_screen_name in [acc['screen_name'] for acc in primary_accounts]:
                        continue
                    
                    if user_screen_name in all_following:
                        # 去重：添加新标签
                        if source_tag not in all_following[user_screen_name]['sources']:
                            all_following[user_screen_name]['sources'].append(source_tag)
                    else:
                        # 新账号
                        all_following[user_screen_name] = {
                            'name': user['name'],
                            'screen_name': user_screen_name,
                            'url': user['url'],
                            'description': user.get('description', ''),
                            'sources': [source_tag],
                            'followers_count': user.get('followers_count', 0),
                            'verified': user.get('verified', False)
                        }
                        new_in_this_batch += 1
                
                print(f"   📊 本批次新增 {new_in_this_batch} 个账号")
                
                # 记录统计信息
                self.stats[screen_name] = {
                    'following_count': len(following_list),
                    'new_accounts': new_in_this_batch,
                    'discovered_at': datetime.now().isoformat()
                }
                
                # 更新进度
                processed_handles.add(screen_name)
                progress['processed'] = list(processed_handles)
                progress['last_update'] = datetime.now().isoformat()
                progress['total_discovered'] = len(all_following)
                
                if not dry_run:
                    # 保存进度文件
                    self._save_progress(progress)
                    
                    # 🔥 增量保存：每处理完一个账号就保存到 accounts_level2.json
                    print(f"   💾 增量保存中...")
                    self._merge_accounts(all_following)
                    print(f"   ✅ 已保存，当前总计 {len(all_following)} 个二级账号")
                
            except Exception as e:
                print(f"   ❌ 处理失败: {e}")
                continue
        
        # 4. 统计信息
        print("\n" + "=" * 60)
        print("📊 发现统计")
        print("=" * 60)
        print(f"总发现账号数: {len(all_following)}")
        
        multi_source = [acc for acc in all_following.values() if len(acc['sources']) > 1]
        print(f"多标签账号数: {len(multi_source)}")
        
        has_bio = [acc for acc in all_following.values() if acc['description']]
        print(f"有简介账号数: {len(has_bio)}")
        
        verified = [acc for acc in all_following.values() if acc['verified']]
        print(f"认证账号数: {len(verified)}")
        
        # 显示多标签示例
        if multi_source:
            print(f"\n多标签示例（前5个）:")
            for acc in multi_source[:5]:
                print(f"  • @{acc['screen_name']}: {', '.join(acc['sources'])}")
        
        # 5. 导出统计数据到 Excel
        if not dry_run and self.stats:
            print(f"\n📊 导出统计数据到 Excel...")
            self._export_stats()
        
        # 6. 最终总结（已通过增量保存完成）
        if not dry_run:
            print("\n✅ 所有数据已通过增量保存写入 accounts_level2.json")
        else:
            print("\n⚠️  试运行模式，未写入文件")
        
        print("=" * 60)
    
    def _export_stats(self):
        """导出统计数据到 Excel"""
        import pandas as pd
        
        # 转换统计数据为 DataFrame
        stats_data = []
        for screen_name, info in self.stats.items():
            stats_data.append({
                '用户名': screen_name,
                '获取的following数量': info['following_count'],
                '新增账号数': info['new_accounts'],
                '获取时间': info['discovered_at']
            })
        
        df = pd.DataFrame(stats_data)
        
        # 确保目录存在
        self.stats_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 保存到 Excel
        df.to_excel(self.stats_path, index=False, engine='openpyxl')
        print(f"   ✅ 统计数据已保存: {self.stats_path}")
    
    
    def _merge_accounts(self, new_following: Dict[str, Dict]):
        """合并新账号到 accounts_level2.json"""
        accounts = self._load_level2_accounts()
        existing_handles = {acc['screen_name']: acc for acc in accounts}
        
        added_count = 0
        updated_count = 0
        
        for screen_name, info in new_following.items():
            if screen_name in existing_handles:
                # 已存在：合并 source 标签
                existing = existing_handles[screen_name]
                existing_sources = self._normalize_source(existing.get('source', []))
                new_sources = info['sources']
                
                # 合并去重
                merged_sources = list(set(existing_sources + new_sources))
                existing['source'] = merged_sources
                existing['updated_at'] = datetime.now().isoformat()
                
                # 更新 description（如果之前为空）
                if not existing.get('description') and info.get('description'):
                    existing['description'] = info['description']
                
                updated_count += 1
            else:
                # 新账号
                new_account = {
                    "name": info['name'],
                    "screen_name": screen_name,
                    "url": info['url'],
                    "description": info['description'],
                    "source": info['sources'],
                    "discovered_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat()
                }
                accounts.append(new_account)
                added_count += 1
        
        self._save_level2_accounts(accounts)
        print(f"   新增: {added_count} 个账号")
        print(f"   更新: {updated_count} 个账号")


async def main():
    parser = argparse.ArgumentParser(description="二级关注发现脚本")
    parser.add_argument("--max-accounts", type=int, default=None,
                        help="最多处理多少个一级账号（默认全部）")
    parser.add_argument("--max-following", type=int, default=50,
                        help="每个账号最多获取多少个 following（默认50）")
    parser.add_argument("--dry-run", action="store_true",
                        help="试运行模式，不写入文件")
    
    args = parser.parse_args()
    
    discoverer = FollowingDiscoverer()
    await discoverer.discover_from_following(
        max_accounts=args.max_accounts,
        max_following_per_account=args.max_following,
        dry_run=args.dry_run
    )


if __name__ == "__main__":
    asyncio.run(main())
