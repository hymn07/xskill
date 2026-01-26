"""
storage_manager.py - 存储管理与时间缝隙补全

核心职责:
1. 维护 SQLite 数据库 (raw_content.db)
2. 管理时间覆盖日志 (manifest.json)
3. 计算数据缺口并合并区间
"""

import json
import os
import sqlite3
from datetime import datetime, timedelta
from typing import List, Tuple, Optional, Union
from pathlib import Path


class StorageManager:
    """存储管理器：维护 SQLite 数据库与时间窗口覆盖日志"""
    
    def __init__(self, data_dir: str = None):
        if data_dir is None:
            data_dir = Path(__file__).parent.parent / "data"
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.db_path = self.data_dir / "raw_content.db"
        self.manifest_path = self.data_dir / "manifest.json"
        
        self._init_database()
        self._init_manifest()
    
    def _init_database(self):
        """初始化 SQLite 数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建表 (包含新字段)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS content (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tweet_id TEXT UNIQUE,
                author TEXT NOT NULL,
                text TEXT,
                publish_time TEXT,
                url TEXT,
                platform TEXT DEFAULT 'twitter',
                is_retweet INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                
                -- 新增字段
                like_count INTEGER DEFAULT 0,
                retweet_count INTEGER DEFAULT 0,
                reply_count INTEGER DEFAULT 0,
                quote_count INTEGER DEFAULT 0,
                view_count INTEGER DEFAULT 0,
                lang TEXT,
                author_followers INTEGER DEFAULT 0
            )
        ''')
        
        # 创建索引加速查询
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_author ON content(author)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_publish_time ON content(publish_time)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_platform ON content(platform)')
        
        # 创建标注 Schema 元数据表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS annotation_schemas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                schema_name TEXT UNIQUE NOT NULL,
                description TEXT,
                fields_json TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        
        # 尝试迁移（针对旧表结构）
        self._migrate_database()
        
    def _migrate_database(self):
        """迁移数据库结构"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        columns_to_add = [
            ("like_count", "INTEGER DEFAULT 0"),
            ("retweet_count", "INTEGER DEFAULT 0"),
            ("reply_count", "INTEGER DEFAULT 0"),
            ("quote_count", "INTEGER DEFAULT 0"),
            ("view_count", "INTEGER DEFAULT 0"),
            ("lang", "TEXT"),
            ("author_followers", "INTEGER DEFAULT 0")
        ]
        
        try:
            # 获取现有列
            cursor.execute("PRAGMA table_info(content)")
            existing_columns = {row[1] for row in cursor.fetchall()}
            
            for col_name, col_type in columns_to_add:
                if col_name not in existing_columns:
                    print(f"🔧 正在迁移数据库，添加列: {col_name}")
                    cursor.execute(f"ALTER TABLE content ADD COLUMN {col_name} {col_type}")
            
            conn.commit()
        except Exception as e:
            print(f"数据库迁移警告: {e}")
        finally:
            conn.close()
    
    def _init_manifest(self):
        """初始化时间覆盖日志"""
        if not self.manifest_path.exists():
            with open(self.manifest_path, 'w', encoding='utf-8') as f:
                json.dump({}, f)
    
    def _load_manifest(self) -> dict:
        """加载 manifest.json"""
        if not self.manifest_path.exists():
            return {}
        with open(self.manifest_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _save_manifest(self, manifest: dict):
        """保存 manifest.json"""
        with open(self.manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
    
    def save_tweets(self, tweets: List[dict]) -> int:
        """
        保存推文到数据库
        
        Args:
            tweets: 推文列表
            
        Returns:
            成功插入的数量
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        inserted = 0
        for tweet in tweets:
            try:
                # 提取 metrics
                metrics = tweet.get('metrics', {})
                metadata = tweet.get('metadata', {})
                
                cursor.execute('''
                    INSERT OR REPLACE INTO content 
                    (tweet_id, author, text, publish_time, url, platform, is_retweet,
                     like_count, retweet_count, reply_count, quote_count, view_count, lang, author_followers)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    tweet.get('content_id') or tweet.get('tweet_id'), # 兼容两种 key
                    tweet.get('author'),
                    tweet.get('text'),
                    tweet.get('publish_time') or tweet.get('created_at'),
                    tweet.get('url'),
                    tweet.get('platform', 'twitter'),
                    1 if tweet.get('is_retweet') else 0,
                    
                    # 新字段
                    metrics.get('likes', 0),
                    metrics.get('retweets', 0),
                    metrics.get('replies', 0),
                    metrics.get('quotes', 0),
                    metrics.get('views', 0),
                    tweet.get('lang', ''),
                    metadata.get('author_followers', 0)
                ))
                if cursor.rowcount > 0:
                    inserted += 1
            except sqlite3.Error as e:
                print(f"Error inserting tweet {tweet.get('content_id')}: {e}")
        
        conn.commit()
        conn.close()
        return inserted
    
    # ==================== Schema 管理方法 ====================
    
    def save_schema(self, schema: dict):
        """
        保存标注 Schema 到元数据表
        
        Args:
            schema: Schema 定义字典
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO annotation_schemas (schema_name, description, fields_json)
                VALUES (?, ?, ?)
            ''', (
                schema['schema_name'],
                schema.get('description', ''),
                json.dumps(schema['fields'], ensure_ascii=False)
            ))
            conn.commit()
            print(f"✅ Schema '{schema['schema_name']}' 已保存")
        except Exception as e:
            print(f"❌ 保存 Schema 失败: {e}")
        finally:
            conn.close()
    
    def load_schema(self, schema_name: str) -> dict:
        """
        加载标注 Schema
        
        Args:
            schema_name: Schema 名称
            
        Returns:
            Schema 定义字典，如果不存在返回 None
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT schema_name, description, fields_json
            FROM annotation_schemas
            WHERE schema_name = ?
        ''', (schema_name,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return {
            'schema_name': row[0],
            'description': row[1],
            'fields': json.loads(row[2])
        }
    
    def list_schemas(self) -> list:
        """
        列出所有已保存的 Schema
        
        Returns:
            Schema 名称和描述的列表
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT schema_name, description, created_at
            FROM annotation_schemas
            ORDER BY created_at DESC
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        return [{
            'schema_name': row[0],
            'description': row[1],
            'created_at': row[2]
        } for row in rows]
    
    def get_column_names(self) -> set:
        """
        获取 content 表的所有列名
        
        Returns:
            列名集合
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("PRAGMA table_info(content)")
        columns = {row[1] for row in cursor.fetchall()}
        
        conn.close()
        return columns
    
    def get_tweets(
        self, 
        author: Union[str, List[str], None] = None, 
        start_date: str = None, 
        end_date: str = None,
        keyword: str = None,
        limit: int = None
    ) -> List[dict]:
        """
        从数据库检索推文
        
        Args:
            author: 作者 screen_name (支持单个字符串或列表)
            start_date: 起始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            keyword: 全文搜索关键词
            limit: 返回数量限制
            
        Returns:
            推文列表
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT * FROM content WHERE 1=1"
        params = []
        
        if author:
            if isinstance(author, list):
                if author:
                    placeholders = ', '.join(['?'] * len(author))
                    query += f" AND author IN ({placeholders})"
                    params.extend(author)
            else:
                query += " AND author = ?"
                params.append(author)
        
        if start_date:
            query += " AND publish_time >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND publish_time <= ?"
            params.append(end_date + "T23:59:59")
        
        if keyword:
            query += " AND text LIKE ?"
            params.append(f"%{keyword}%")
        
        query += " ORDER BY publish_time DESC"
        
        if limit:
            query += f" LIMIT {limit}"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    # ==================== 核心: 时间缝隙算法 ====================
    
    def get_missing_ranges(
        self, 
        handle: str, 
        start_date: str, 
        end_date: str
    ) -> List[Tuple[str, str]]:
        """
        计算指定时间区间内缺失的数据范围
        
        这是系统的核心算法，负责比对用户请求的时间区间与已存储区间，
        返回真正需要爬取的缺失片段。
        
        Args:
            handle: 博主的 screen_name
            start_date: 请求的起始日期 (YYYY-MM-DD)
            end_date: 请求的结束日期 (YYYY-MM-DD)
            
        Returns:
            缺失区间列表，如 [("2024-01-01", "2024-01-04"), ("2024-01-21", "2024-01-30")]
        
        Example:
            用户请求 [1.1, 1.30]
            本地已有 [1.5, 1.20]
            返回 [(1.1, 1.4), (1.21, 1.30)]
        """
        manifest = self._load_manifest()
        
        # 获取该博主已存储的区间列表
        stored_ranges = manifest.get(handle, [])
        
        if not stored_ranges:
            # 没有任何存储，返回完整请求区间
            return [(start_date, end_date)]
        
        # 转换为日期对象便于计算
        req_start = datetime.strptime(start_date, "%Y-%m-%d")
        req_end = datetime.strptime(end_date, "%Y-%m-%d")
        
        # 将已存储区间排序
        stored = []
        for rng in stored_ranges:
            s = datetime.strptime(rng[0], "%Y-%m-%d")
            e = datetime.strptime(rng[1], "%Y-%m-%d")
            stored.append((s, e))
        stored.sort(key=lambda x: x[0])
        
        # 计算缺口
        missing = []
        current = req_start
        
        for s_start, s_end in stored:
            # 如果当前指针已经超过请求结束，停止
            if current > req_end:
                break
            
            # 存储区间在请求区间之前，跳过
            if s_end < current:
                continue
            
            # 存储区间在请求区间之后，记录缺口到存储开始
            if s_start > current:
                gap_end = min(s_start - timedelta(days=1), req_end)
                if gap_end >= current:
                    missing.append((
                        current.strftime("%Y-%m-%d"),
                        gap_end.strftime("%Y-%m-%d")
                    ))
            
            # 更新当前指针到已存储区间结束的下一天
            current = max(current, s_end + timedelta(days=1))
        
        # 检查尾部缺口
        if current <= req_end:
            missing.append((
                current.strftime("%Y-%m-%d"),
                req_end.strftime("%Y-%m-%d")
            ))
        
        return missing
    
    def merge_intervals(self, intervals: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
        """
        合并重叠的时间区间
        
        Args:
            intervals: 区间列表，每个元素为 (start_date, end_date)
            
        Returns:
            合并后的区间列表
        
        Example:
            输入: [("2024-01-01", "2024-01-10"), ("2024-01-08", "2024-01-20")]
            输出: [("2024-01-01", "2024-01-20")]
        """
        if not intervals:
            return []
        
        # 转换为日期对象
        date_intervals = []
        for start, end in intervals:
            s = datetime.strptime(start, "%Y-%m-%d")
            e = datetime.strptime(end, "%Y-%m-%d")
            date_intervals.append((s, e))
        
        # 按起始日期排序
        date_intervals.sort(key=lambda x: x[0])
        
        merged = [date_intervals[0]]
        
        for current_start, current_end in date_intervals[1:]:
            last_start, last_end = merged[-1]
            
            # 如果当前区间与上一个重叠或相邻（差1天也算相邻）
            if current_start <= last_end + timedelta(days=1):
                # 合并
                merged[-1] = (last_start, max(last_end, current_end))
            else:
                # 不重叠，新增
                merged.append((current_start, current_end))
        
        # 转回字符串格式
        return [(s.strftime("%Y-%m-%d"), e.strftime("%Y-%m-%d")) for s, e in merged]
    
    def update_manifest(self, handle: str, new_range: Tuple[str, str]):
        """
        更新 manifest.json，添加新抓取的时间范围并合并
        
        Args:
            handle: 博主的 screen_name
            new_range: 新抓取的区间 (start_date, end_date)
        """
        manifest = self._load_manifest()
        
        existing = manifest.get(handle, [])
        # 转换为元组列表
        existing = [tuple(r) for r in existing]
        existing.append(new_range)
        
        # 合并区间
        merged = self.merge_intervals(existing)
        
        manifest[handle] = merged
        self._save_manifest(manifest)
    
    def get_coverage(self, handle: str) -> List[Tuple[str, str]]:
        """获取某博主的已覆盖时间区间"""
        manifest = self._load_manifest()
        return manifest.get(handle, [])


# ==================== 测试代码 ====================
if __name__ == "__main__":
    sm = StorageManager()
    
    # 测试区间合并
    intervals = [
        ("2024-01-01", "2024-01-10"),
        ("2024-01-08", "2024-01-20"),
        ("2024-01-25", "2024-01-30")
    ]
    merged = sm.merge_intervals(intervals)
    print(f"合并结果: {merged}")
    # 预期: [("2024-01-01", "2024-01-20"), ("2024-01-25", "2024-01-30")]
    
    # 测试缺口计算
    sm.update_manifest("test_user", ("2024-01-05", "2024-01-20"))
    gaps = sm.get_missing_ranges("test_user", "2024-01-01", "2024-01-30")
    print(f"缺口区间: {gaps}")
    # 预期: [("2024-01-01", "2024-01-04"), ("2024-01-21", "2024-01-30")]
