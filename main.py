"""
main.py - 智能内容情报 Agent 系统入口

核心职责:
1. 协调各模块完成"意图 -> 数据 -> 结论"的闭环
2. 提供命令行接口和 API 入口
3. 任务编排与用户交互逻辑

使用流程:
1. 身份映射 (QueryEngine)
2. 计算数据缺口 (StorageManager)
3. 调用爬虫 (XScraper)
4. AI 动态分析 (AnalysisGenerator)
5. 导出报告 (Exporter)
"""

import os
import asyncio
import argparse
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from core.discoverer import AccountDiscoverer
from core.query_engine import QueryEngine
from core.storage_manager import StorageManager
from core.exporter import Exporter
from core.scrapers import XScraper
from skills import AnalysisGenerator
from core.schema_generator import SchemaGenerator
from core.annotator import DynamicAnnotator


class XSkillAgent:
    """智能内容情报 Agent 主控类"""
    
    def __init__(self):
        self.discoverer = AccountDiscoverer()
        self.query_engine = QueryEngine(discoverer=self.discoverer)
        self.storage = StorageManager()
        self.exporter = Exporter(storage_manager=self.storage)
        
        # 爬虫需要 auth_token，延迟初始化
        self._scraper = None
        
        # 分析器
        self.analyzer = AnalysisGenerator()
    
    @property
    def scraper(self) -> Optional[XScraper]:
        """延迟初始化爬虫"""
        if self._scraper is None:
            auth_token = os.getenv("TWITTER_AUTH_TOKEN")
            if auth_token:
                self._scraper = XScraper(auth_token=auth_token)
            else:
                print("⚠️ 未配置 TWITTER_AUTH_TOKEN，抓取功能不可用")
        return self._scraper
    
    async def run_pipeline(
        self,
        query: str,
        start_date: str = None,
        end_date: str = None,
        export: bool = True,
        analyze: bool = True
    ) -> dict:
        """
        执行完整的情报获取流程
        
        Args:
            query: 用户查询，如 "马斯克最近一周"
            start_date: 起始日期 (可选，会尝试从 query 解析)
            end_date: 结束日期 (可选)
            export: 是否导出 Excel
            analyze: 是否进行 AI 分析
            
        Returns:
            执行结果字典
        """
        print(f"\n{'='*50}")
        print(f"🚀 开始执行任务: {query}")
        print(f"{'='*50}\n")
        
        result = {
            "query": query,
            "start_time": datetime.now().isoformat(),
            "steps": []
        }
        
        # Step 1: 更新账号池
        print("📡 Step 1: 更新账号池...")
        new_count, _ = self.discoverer.fetch_and_update()
        result["steps"].append({
            "name": "账号发现",
            "new_accounts": new_count
        })
        
        # Step 2: 身份识别
        print("🔍 Step 2: 识别目标...")
        identity = self.query_engine.identify_multiple(query)
        result["steps"].append({
            "name": "身份识别",
            "result": identity
        })
        
        if identity["mode"] == "none":
            print(f"⚠️ {identity['message']}")
            result["error"] = identity['message']
            return result
        
        handles = identity["handles"]
        print(f"✅ 识别到 {len(handles)} 个目标: {', '.join(handles[:5])}{'...' if len(handles) > 5 else ''}")
        
        # Step 3: 解析时间范围
        if not start_date or not end_date:
            parsed_start, parsed_end = self.query_engine.parse_time_range(query)
            start_date = start_date or parsed_start
            end_date = end_date or parsed_end
        
        if not start_date:
            print(f"💡 {self.query_engine.ask_for_time_range()}")
            # 默认使用最近7天
            from datetime import timedelta
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            print(f"   使用默认范围: {start_date} 至 {end_date}")
        
        print(f"📅 时间范围: {start_date} 至 {end_date}")
        
        # Step 4 & 5: 针对每个用户抓取数据
        total_fetched = 0
        all_gaps = []
        
        print("📊 Step 4 & 5: 检查缺口并抓取数据...")
        for handle in handles:
            gaps = self.storage.get_missing_ranges(handle, start_date, end_date)
            if gaps:
                print(f"   [ @{handle} ] 发现 {len(gaps)} 个缺口区间")
                if self.scraper:
                    for gap_start, gap_end in gaps:
                        print(f"      抓取 {gap_start} 至 {gap_end}...")
                        tweets = await self.scraper.scrape(
                            handle, 
                            start_date=gap_start, 
                            end_date=gap_end,
                            count=100
                        )
                        
                        if tweets:
                            save_tweets = [{
                                "tweet_id": t["content_id"],
                                "author": t["author"],
                                "text": t["text"],
                                "created_at": t["publish_time"],
                                "url": t["url"],
                                "is_retweet": t["is_retweet"],
                                "metrics": t.get("metrics", {}),
                                "metadata": t.get("metadata", {})
                            } for t in tweets]
                            
                            saved = self.storage.save_tweets(save_tweets)
                            self.storage.update_manifest(handle, (gap_start, gap_end))
                            total_fetched += saved
                            print(f"      ✅ 保存 {saved} 条推文")
                all_gaps.extend([(handle, g) for g in gaps])
            else:
                print(f"   [ @{handle} ] ✅ 无需抓取")

        result["steps"].append({
            "name": "缺口计算与抓取",
            "total_fetched": total_fetched,
            "gaps_found": len(all_gaps)
        })
        
        # Step 6: 获取全量本地数据
        print("📚 Step 6: 读取本地汇总数据...")
        data = self.storage.get_tweets(
            author=handles,
            start_date=start_date,
            end_date=end_date
        )
        result["data_count"] = len(data)
        print(f"   汇总共 {len(data)} 条数据")
        
        # Step 7: AI 分析 (聚合分析)
        annotated_data = data  # 默认使用原始数据
        
        # 检查是否需要动态标注（基于 query 意图）
        if "标注" in query or "看讨论" in query or "判断" in query:
            print("🏷️  正在进行即时动态标注...")
            schema_gen = SchemaGenerator()
            schema = await schema_gen.generate_from_user_intent(query)
            annotator = DynamicAnnotator(schema=schema, storage_manager=self.storage)
            # 无状态标注，直接获取结果
            annotated_data = await annotator.annotate_all(author=handles)
            print(f"   ✅ 已完成 {len(annotated_data)} 条推文的即时标注")
        
        if analyze and annotated_data:
            print("🧠 Step 8: AI 聚合分析中...")
            analysis = await self.analyzer.analyze(query, annotated_data)
            result["analysis"] = analysis
            
            if analysis.get("highlights"):
                print("   📌 重点发现:")
                for h in analysis["highlights"][:3]:
                    print(f"      • {h}")
            
            # 保存 AI 分析报告为 MD
            if 'error' not in analysis:
                report_path = self.analyzer.save_report(analysis)
                result["analysis_report_path"] = report_path
        
        # Step 9: 导出聚合 Excel
        if export and annotated_data:
            print("📝 Step 9: 导出聚合报告...")
            filepath = self.exporter.export_to_excel(
                author=handles,
                start_date=start_date,
                end_date=end_date,
                external_data=annotated_data
            )
            result["export_path"] = filepath
        
        result["end_time"] = datetime.now().isoformat()
        print(f"\n{'='*50}")
        print("✅ 任务完成!")
        print(f"{'='*50}\n")
        
        return result
    
    def update_accounts(self) -> int:
        """仅更新账号池"""
        new_count, _ = self.discoverer.fetch_and_update()
        return new_count
    
    def list_accounts(self):
        """列出所有账号"""
        accounts = self.discoverer.get_all_accounts()
        print(f"\n📋 账号池共有 {len(accounts)} 个博主:\n")
        for acc in accounts:
            print(f"  • {acc['name']} (@{acc['screen_name']})")
            if acc.get('description'):
                print(f"    {acc['description'][:60]}...")
        print()


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description="智能内容情报 Agent 系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python main.py "马斯克最近一周"
  python main.py "看看 sama 本月发了什么" --no-analyze
  python main.py --update-accounts
  python main.py --list-accounts
        """
    )
    
    parser.add_argument("query", nargs="?", help="查询内容，如 '马斯克最近一周'")
    parser.add_argument("--start", "-s", help="起始日期 (YYYY-MM-DD)")
    parser.add_argument("--end", "-e", help="结束日期 (YYYY-MM-DD)")
    parser.add_argument("--no-export", action="store_true", help="不导出 Excel")
    parser.add_argument("--no-analyze", action="store_true", help="不进行 AI 分析")
    parser.add_argument("--update-accounts", action="store_true", help="仅更新账号池")
    parser.add_argument("--list-accounts", action="store_true", help="列出所有账号")
    
    args = parser.parse_args()
    
    agent = XSkillAgent()
    
    if args.update_accounts:
        new = agent.update_accounts()
        print(f"✅ 账号池更新完成，新增 {new} 个博主")
        return
    
    if args.list_accounts:
        agent.list_accounts()
        return
    
    if not args.query:
        parser.print_help()
        return
    
    # 执行主流程
    result = asyncio.run(agent.run_pipeline(
        query=args.query,
        start_date=args.start,
        end_date=args.end,
        export=not args.no_export,
        analyze=not args.no_analyze
    ))
    
    if result.get("error"):
        print(f"❌ 执行失败: {result['error']}")
    else:
        if result.get("export_path"):
            print(f"📁 Excel 报告: {result['export_path']}")
        if result.get("analysis_report_path"):
            print(f"📝 AI 分析报告: {result['analysis_report_path']}")


if __name__ == "__main__":
    main()
