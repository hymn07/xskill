"""
annotate_tweets.py - 动态标注 CLI 工具（完全重构版）

使用方法:
  # 首次使用，定义新的标注 Schema
  python annotate_tweets.py --define "帮我判断每个推文的情感，有没有创业信号，总结推文内容" --limit 20
  
  # 使用已有 Schema 继续标注
  python annotate_tweets.py --schema investment_signal --limit 50
  
  # 列出所有 Schema
  python annotate_tweets.py --list-schemas
  
  # 标注后自动导出
  python annotate_tweets.py --schema my_schema --export
"""

import asyncio
import argparse
import sys
from dotenv import load_dotenv

load_dotenv()

from core.schema_generator import SchemaGenerator
from core.annotator import DynamicAnnotator
from core.storage_manager import StorageManager


async def main():
    parser = argparse.ArgumentParser(description='动态推文标注系统')
    
    # 定义新 Schema
    parser.add_argument('--define', type=str, help='用自然语言定义新的标注需求')
    
    # 使用已有 Schema
    parser.add_argument('--schema', type=str, help='使用已有 Schema 名称')
    
    # 列出所有 Schema
    parser.add_argument('--list-schemas', action='store_true', help='列出所有已保存的 Schema')
    
    # 标注参数
    parser.add_argument('--limit', type=int, default=None, help='最多标注数量')
    parser.add_argument('--author', type=str, default=None, help='只标注特定作者')
    parser.add_argument('--batch-size', type=int, default=10, help='每批处理数量')
    
    # 导出选项
    parser.add_argument('--export', action='store_true', help='标注完成后导出 Excel')
    
    args = parser.parse_args()
    
    sm = StorageManager()
    
    # 1. 列出 Schemas
    if args.list_schemas:
        print("\n" + "=" * 60)
        print("📋 已保存的标注 Schema")
        print("=" * 60)
        
        schemas = sm.list_schemas()
        
        if not schemas:
            print("\n⚠️  尚未创建任何 Schema")
            print("\n💡 使用 --define 创建新 Schema:")
            print('   python annotate_tweets.py --define "你的标注需求"')
        else:
            for idx, schema_info in enumerate(schemas, 1):
                print(f"\n{idx}. {schema_info['schema_name']}")
                print(f"   描述: {schema_info['description']}")
                print(f"   创建时间: {schema_info['created_at']}")
        
        return
    
    # 2. 定义新 Schema
    if args.define:
        print("\n" + "=" * 60)
        print("🧠 正在理解您的标注需求...")
        print("=" * 60)
        print(f"\n用户需求: {args.define}")
        
        generator = SchemaGenerator()
        
        try:
            schema = await generator.generate_from_user_intent(args.define)
            
            print("\n✅ Schema 生成成功:")
            print(f"   名称: {schema['schema_name']}")
            print(f"   描述: {schema['description']}")
            print(f"   字段数: {len(schema['fields'])}")
            
            print("\n📝 字段详情:")
            for field in schema['fields']:
                type_info = field['type']
                if field['type'] == 'enum':
                    type_info += f" {field['values']}"
                elif field['type'] in ['integer', 'float'] and 'range' in field:
                    type_info += f" {field['range']}"
                
                print(f"   - {field['display_name']} ({field['name']}): {type_info}")
            
            # 保存 Schema
            sm.save_schema(schema)
            
            # 确保数据库有对应列
            sm.ensure_schema_columns(schema)
            
            print(f"\n✅ Schema '{schema['schema_name']}' 已保存并可使用")
            print(f"\n💡 现在可以使用此 Schema 进行标注:")
            print(f"   python annotate_tweets.py --schema {schema['schema_name']} --limit 20")
            
            # 询问是否立即标注
            if args.limit or input("\n是否立即开始标注？(y/n): ").lower() == 'y':
                print("\n开始标注...")
                await run_annotation(schema, sm, args)
            
        except Exception as e:
            print(f"\n❌ Schema 生成失败: {e}")
            sys.exit(1)
        
        return
    
    # 3. 使用已有 Schema 标注
    if args.schema:
        schema = sm.load_schema(args.schema)
        
        if not schema:
            print(f"\n❌ Schema '{args.schema}' 不存在")
            print("\n💡 使用 --list-schemas 查看所有可用 Schema")
            sys.exit(1)
        
        await run_annotation(schema, sm, args)
        return
    
    # 4. 没有指定任何操作
    parser.print_help()


async def run_annotation(schema: dict, sm: StorageManager, args):
    """执行标注流程"""
    print("\n" + "=" * 60)
    print("🏷️  开始标注")
    print("=" * 60)
    
    # 初始化标注器
    annotator = DynamicAnnotator(
        schema=schema,
        storage_manager=sm,
        batch_size=args.batch_size
    )
    
    # 执行标注
    result = await annotator.annotate_all(
        max_tweets=args.limit,
        author=args.author
    )
    
    # 显示结果
    print("\n" + "=" * 60)
    print("📊 标注完成")
    print("=" * 60)
    print(f"Schema: {result.get('schema_name', 'N/A')}")
    print(f"总计: {result['total']} 条")
    print(f"成功: {result['annotated']} 条")
    print(f"批次: {result.get('batches', 0)} 个")
    if result['total'] > 0:
        print(f"成功率: {result['annotated']/result['total']*100:.1f}%")
    
    # 导出 Excel
    if args.export and result['annotated'] > 0:
        print("\n📤 正在导出带标注的数据...")
        
        from core.exporter import Exporter
        exporter = Exporter(storage_manager=sm)
        
        # 使用新方法导出带标注数据
        filepath = export_with_schema(exporter, schema, args.author)
        
        if filepath:
            print(f"✅ 导出完成: {filepath}")


def export_with_schema(exporter, schema: dict, author: str = None) -> str:
    """根据 Schema 导出已标注数据"""
    import sqlite3
    import pandas as pd
    from pathlib import Path
    from datetime import datetime
    
    # 获取已标注数据
    conn = sqlite3.connect(exporter.sm.db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 使用第一个字段判断是否已标注
    first_field = schema['fields'][0]['name']
    query = f"SELECT * FROM content WHERE {first_field} IS NOT NULL"
    params = []
    
    if author:
        query += " AND author = ?"
        params.append(author)
    
    query += " ORDER BY publish_time DESC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        print("⚠️ 没有已标注的数据")
        return None
    
    tweets = [dict(row) for row in rows]
    df = pd.DataFrame(tweets)
    
    # 列映射
    columns_mapping = {
        'author': '作者',
        'text': '内容',
        'publish_time': '发布时间',
    }
    
    # 添加 Schema 字段
    for field in schema['fields']:
        columns_mapping[field['name']] = field['display_name']
    
    # 添加互动数据
    columns_mapping.update({
        'like_count': '点赞数',
        'retweet_count': '转发数',
        'reply_count': '评论数',
        'view_count': '阅读量',
        'url': '原文链接',
    })
    
    # 确保列存在
    for col in columns_mapping.keys():
        if col not in df.columns:
            df[col] = None
    
    # 重命名
    df.rename(columns=columns_mapping, inplace=True)
    
    # 排序
    preferred_order = ['作者', '内容', '发布时间']
    # 添加 Schema 字段
    preferred_order += [field['display_name'] for field in schema['fields']]
    # 添加其他字段
    preferred_order += ['点赞数', '转发数', '评论数', '阅读量', '原文链接']
    
    final_cols = [col for col in preferred_order if col in df.columns]
    df = df[final_cols].copy()
    
    # 生成文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{schema['schema_name']}_annotated_{timestamp}.xlsx"
    filepath = exporter.output_dir / filename
    
    # 导出
    df.to_excel(filepath, index=False, engine='openpyxl')
    
    # 添加超链接
    exporter._add_hyperlinks(filepath, df)
    
    print(f"   共 {len(df)} 条已标注记录")
    
    return str(filepath)


if __name__ == "__main__":
    asyncio.run(main())
