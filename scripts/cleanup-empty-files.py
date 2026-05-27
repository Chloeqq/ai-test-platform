#!/usr/bin/env python3
"""
清理脚本 - 删除空文件和空目录
用途：清理项目中的骨架文件，减少维护负担
"""

import os
import sys
from pathlib import Path
from datetime import datetime

# 项目根目录
REPO_ROOT = Path(__file__).resolve().parents[2]

# 需要排除的目录（不删除这些目录下的空文件）
EXCLUDE_DIRS = {
    '.git',
    '.venv',
    '__pycache__',
    'node_modules',
    '.pytest_cache',
    'allure-results',
    'test-results',
    'artifacts',
}

# 需要排除的文件模式
EXCLUDE_PATTERNS = {
    '.gitignore',
    '.env',
    '.env.example',
    'README.md',
    'requirements.txt',
    'pytest.ini',
}

def is_excluded(path: Path) -> bool:
    """检查路径是否在排除列表中"""
    for part in path.parts:
        if part in EXCLUDE_DIRS:
            return True
    if path.name in EXCLUDE_PATTERNS:
        return True
    return False

def find_empty_files(root: Path) -> list[Path]:
    """查找所有空文件"""
    empty_files = []
    for file_path in root.rglob('*.py'):
        if is_excluded(file_path):
            continue
        if file_path.stat().st_size == 0:
            empty_files.append(file_path)
    return empty_files

def find_empty_dirs(root: Path) -> list[Path]:
    """查找所有空目录"""
    empty_dirs = []
    for dir_path in sorted(root.rglob('*'), reverse=True):
        if is_excluded(dir_path):
            continue
        if dir_path.is_dir() and not any(dir_path.iterdir()):
            empty_dirs.append(dir_path)
    return empty_dirs

def main():
    print(f"🔍 扫描项目：{REPO_ROOT}")
    print("=" * 60)
    
    # 查找空文件
    print("\n📄 查找空 Python 文件...")
    empty_files = find_empty_files(REPO_ROOT)
    print(f"   发现 {len(empty_files)} 个空文件")
    
    # 查找空目录
    print("\n📁 查找空目录...")
    empty_dirs = find_empty_dirs(REPO_ROOT)
    print(f"   发现 {len(empty_dirs)} 个空目录")
    
    if not empty_files and not empty_dirs:
        print("\n✅ 没有需要清理的内容")
        return 0
    
    # 生成报告
    report_file = REPO_ROOT / "reports" / f"cleanup-report-{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
    report_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(f"清理报告 - {datetime.now().isoformat()}\n")
        f.write("=" * 60 + "\n\n")
        
        f.write(f"项目根目录：{REPO_ROOT}\n\n")
        
        if empty_files:
            f.write(f"空文件 ({len(empty_files)} 个):\n")
            f.write("-" * 60 + "\n")
            for file_path in empty_files:
                rel_path = file_path.relative_to(REPO_ROOT)
                f.write(f"  {rel_path}\n")
            f.write("\n")
        
        if empty_dirs:
            f.write(f"空目录 ({len(empty_dirs)} 个):\n")
            f.write("-" * 60 + "\n")
            for dir_path in empty_dirs:
                rel_path = dir_path.relative_to(REPO_ROOT)
                f.write(f"  {rel_path}\n")
            f.write("\n")
    
    print(f"\n📊 报告已生成：{report_file}")
    
    # 询问是否删除
    print("\n⚠️  是否删除这些文件？(y/n): ", end='')
    # 如果是非交互模式，直接删除
    if len(sys.argv) > 1 and sys.argv[1] == '--force':
        confirm = 'y'
        print('y (自动确认)')
    else:
        confirm = input().strip().lower()
    
    if confirm != 'y':
        print("\n❌ 已取消")
        return 0
    
    # 删除空文件
    print("\n🗑️  删除空文件...")
    deleted_files = 0
    for file_path in empty_files:
        try:
            file_path.unlink()
            deleted_files += 1
            if deleted_files % 50 == 0:
                print(f"   已删除 {deleted_files}/{len(empty_files)} 个文件")
        except Exception as e:
            print(f"   ❌ 无法删除 {file_path}: {e}")
    
    print(f"   ✅ 已删除 {deleted_files} 个空文件")
    
    # 删除空目录
    print("\n🗑️  删除空目录...")
    deleted_dirs = 0
    for dir_path in empty_dirs:
        try:
            dir_path.rmdir()
            deleted_dirs += 1
            if deleted_dirs % 20 == 0:
                print(f"   已删除 {deleted_dirs}/{len(empty_dirs)} 个目录")
        except Exception as e:
            print(f"   ❌ 无法删除 {dir_path}: {e}")
    
    print(f"   ✅ 已删除 {deleted_dirs} 个空目录")
    
    # 更新报告
    with open(report_file, 'a', encoding='utf-8') as f:
        f.write("\n清理结果:\n")
        f.write("-" * 60 + "\n")
        f.write(f"删除空文件：{deleted_files}/{len(empty_files)}\n")
        f.write(f"删除空目录：{deleted_dirs}/{len(empty_dirs)}\n")
        f.write(f"完成时间：{datetime.now().isoformat()}\n")
    
    print("\n" + "=" * 60)
    print("✅ 清理完成!")
    print(f"📄 详细报告：{report_file}")
    return 0

if __name__ == '__main__':
    sys.exit(main())
