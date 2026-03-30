#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Godot 4 图片资源提取工具 (通用版)
从任何Godot 4项目的.ctex文件中提取图片资源

使用方法:
    python extract_godot_images.py [项目路径]
    
    如果不指定项目路径，则使用当前目录
    
示例:
    python extract_godot_images.py C:\\MyGame
    python extract_godot_images.py "D:\\Godot Projects\\MyGame"
    python extract_godot_images.py  # 使用当前目录
"""

import os
import sys
import struct
import shutil
import argparse
from pathlib import Path


def find_godot_project(project_path):
    """查找Godot项目目录"""
    project_path = Path(project_path).resolve()
    
    # 检查是否是有效的Godot项目
    if (project_path / "project.godot").exists():
        return project_path
    
    # 如果没有project.godot，检查是否有.godot目录
    if (project_path / ".godot").exists():
        return project_path
    
    return None


def find_imported_files(project_path):
    """查找所有导入的资源文件"""
    imported_dir = project_path / ".godot" / "imported"
    
    if not imported_dir.exists():
        print(f"❌ 错误: 找不到导入目录: {imported_dir}")
        print("   请确保项目已经用Godot 4编辑器打开过（生成导入缓存）")
        return [], []
    
    # 查找.ctex文件（纹理）
    ctex_files = list(imported_dir.glob("*.ctex"))
    
    # 查找.sample文件（音频）
    sample_files = list(imported_dir.glob("*.sample"))
    
    return ctex_files, sample_files


def extract_webp_from_ctex(ctex_path, output_dir):
    """从.ctex文件中提取图片，保持原始文件扩展名"""
    try:
        with open(ctex_path, 'rb') as f:
            data = f.read()
        
        # 搜索WebP签名 (RIFF)
        webp_sig = b'RIFF'
        pos = 0
        
        while True:
            pos = data.find(webp_sig, pos)
            if pos == -1:
                break
            
            # 检查是否是有效的WebP文件
            if pos + 12 <= len(data):
                # RIFF头后面应该是WEBP
                if data[pos+8:pos+12] == b'WEBP':
                    # 读取文件大小
                    size = struct.unpack('<I', data[pos+4:pos+8])[0]
                    
                    # 确保不超出数据范围
                    if pos + size + 8 <= len(data):
                        webp_data = data[pos:pos+size+8]
                        
                        # 生成输出文件名 - 保持原始扩展名
                        file_name = ctex_path.name
                        # 从文件名提取原始名称（移除UUID和.ctex后缀）
                        if '-' in file_name:
                            # 格式: originalname.ext-uuid.ctex
                            original_name = file_name.split('-')[0]
                        else:
                            original_name = file_name.replace('.ctex', '')
                        
                        # 如果没有扩展名，添加.webp
                        if '.' not in original_name:
                            original_name += '.webp'
                        
                        output_path = Path(output_dir) / original_name
                        
                        # 保存文件
                        with open(output_path, 'wb') as out_f:
                            out_f.write(webp_data)
                        
                        return True, output_path.name
            
            pos += 1
        
        return False, "未找到WebP数据"
        
    except Exception as e:
        return False, str(e)


def clean_filename(filename):
    """清理文件名，移除不安全的字符"""
    # 移除或替换不安全的字符
    unsafe_chars = '<>:"/\\|?*'
    for char in unsafe_chars:
        filename = filename.replace(char, '_')
    return filename


def extract_images(project_path, output_path=None):
    """主提取函数"""
    project_path = Path(project_path).resolve()
    
    # 验证项目路径
    godot_project = find_godot_project(project_path)
    if not godot_project:
        print(f"❌ 错误: 找不到有效的Godot项目: {project_path}")
        print("   请确保目录包含 project.godot 文件或 .godot 目录")
        return False
    
    print(f"✓ 找到Godot项目: {godot_project}")
    
    # 设置输出目录
    if output_path:
        output_dir = Path(output_path).resolve()
    else:
        output_dir = godot_project / "extracted_images"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"✓ 输出目录: {output_dir}")
    print()
    
    # 查找导入文件
    ctex_files, sample_files = find_imported_files(godot_project)
    
    if not ctex_files and not sample_files:
        print("⚠ 未找到任何导入的资源文件")
        return False
    
    print(f"找到 {len(ctex_files)} 个纹理文件 (.ctex)")
    print(f"找到 {len(sample_files)} 个音频文件 (.sample)")
    print()
    
    # 提取图片
    print("=" * 70)
    print("开始提取图片资源...")
    print("=" * 70)
    
    success_count = 0
    failed_count = 0
    failed_files = []
    
    for i, ctex_file in enumerate(ctex_files, 1):
        success, result = extract_webp_from_ctex(ctex_file, output_dir)
        
        if success:
            print(f"[{i}/{len(ctex_files)}] ✓ {result}")
            success_count += 1
        else:
            print(f"[{i}/{len(ctex_files)}] ❌ {ctex_file.name}: {result}")
            failed_count += 1
            failed_files.append(ctex_file.name)
    
    # 总结
    print()
    print("=" * 70)
    print("提取完成!")
    print("=" * 70)
    print(f"成功: {success_count}/{len(ctex_files)} 个文件")
    print(f"失败: {failed_count}/{len(ctex_files)} 个文件")
    
    if failed_files:
        print()
        print("失败的文件:")
        for fname in failed_files[:5]:
            print(f"  - {fname}")
        if len(failed_files) > 5:
            print(f"  ... 还有 {len(failed_files) - 5} 个")
    
    print()
    print(f"提取的图片保存在: {output_dir}")
    print()
    
    # 列出提取的文件
    extracted_files = list(output_dir.glob("*"))
    if extracted_files:
        print(f"目录中的文件 ({len(extracted_files)} 个):")
        for f in sorted(extracted_files)[:10]:
            print(f"  - {f.name}")
        if len(extracted_files) > 10:
            print(f"  ... 还有 {len(extracted_files) - 10} 个文件")
    
    return True


def main():
    # 设置命令行参数
    parser = argparse.ArgumentParser(
        description='从Godot 4项目中提取图片资源',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=r"""
示例:
  %(prog)s                          # 使用当前目录
  %(prog)s C:\MyGame               # 指定项目路径
  %(prog)s "D:\Godot Projects\Game"  # 路径包含空格时用引号
  %(prog)s . -o ./output            # 指定输出目录
        """
    )
    
    parser.add_argument(
        'project_path',
        nargs='?',
        default='.',
        help='Godot项目路径 (默认: 当前目录)'
    )
    
    parser.add_argument(
        '-o', '--output',
        dest='output_path',
        help='输出目录路径 (默认: 项目目录/extracted_images)'
    )
    
    parser.add_argument(
        '-v', '--version',
        action='version',
        version='%(prog)s 1.0 - Godot 4 Image Extractor'
    )
    
    args = parser.parse_args()
    
    # 显示欢迎信息
    print()
    print("=" * 70)
    print("Godot 4 图片资源提取工具")
    print("=" * 70)
    print()
    
    # 执行提取
    success = extract_images(args.project_path, args.output_path)
    
    if success:
        print()
        print("✅ 提取成功完成!")
    else:
        print()
        print("❌ 提取失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
