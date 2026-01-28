#!/usr/bin/env python3
import json
import os

def is_first_level_account(account):
    """
    判断账号是否是一级账号（Zara Zhang直接推荐的）
    """
    source = account.get('source', '')
    
    # source可能是字符串或数组
    if isinstance(source, str):
        return source == "Zara Zhang"
    elif isinstance(source, list):
        return "Zara Zhang" in source
    
    return False

def split_accounts():
    # 文件路径
    accounts_file = '/Users/hym/Desktop/jinqiu/github/xskill/data/accounts.json'
    first_level_file = '/Users/hym/Desktop/jinqiu/github/xskill/data/accounts_level1.json'
    second_level_file = '/Users/hym/Desktop/jinqiu/github/xskill/data/accounts_level2.json'
    
    # 读取账号数据
    print(f"Reading accounts from: {accounts_file}")
    with open(accounts_file, 'r', encoding='utf-8') as f:
        all_accounts = json.load(f)
    
    # 分离一级和二级账号
    first_level_accounts = []
    second_level_accounts = []
    
    for account in all_accounts:
        if is_first_level_account(account):
            first_level_accounts.append(account)
        else:
            second_level_accounts.append(account)
    
    # 保存一级账号
    print(f"\nWriting {len(first_level_accounts)} first-level accounts to: {first_level_file}")
    with open(first_level_file, 'w', encoding='utf-8') as f:
        json.dump(first_level_accounts, f, ensure_ascii=False, indent=2)
    
    # 保存二级账号
    print(f"Writing {len(second_level_accounts)} second-level accounts to: {second_level_file}")
    with open(second_level_file, 'w', encoding='utf-8') as f:
        json.dump(second_level_accounts, f, ensure_ascii=False, indent=2)
    
    # 备份原文件
    backup_file = accounts_file + '.backup'
    print(f"\nBacking up original file to: {backup_file}")
    with open(backup_file, 'w', encoding='utf-8') as f:
        json.dump(all_accounts, f, ensure_ascii=False, indent=2)
    
    # 用二级账号替换原accounts.json
    print(f"Replacing {accounts_file} with second-level accounts")
    with open(accounts_file, 'w', encoding='utf-8') as f:
        json.dump(second_level_accounts, f, ensure_ascii=False, indent=2)
    
    # 打印统计信息
    print("\n" + "="*50)
    print("Summary:")
    print(f"Total accounts: {len(all_accounts)}")
    print(f"First-level (Zara Zhang): {len(first_level_accounts)}")
    print(f"Second-level (others): {len(second_level_accounts)}")
    print("\nFiles created:")
    print(f"  - {first_level_file}")
    print(f"  - {second_level_file} (also replaced original accounts.json)")
    print(f"  - {backup_file} (backup of original)")
    print("="*50)

if __name__ == "__main__":
    split_accounts()
