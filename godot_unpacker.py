#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Godot 引擎解包工具 - 轻量级一键解包与资源还原

功能:
  unpack   - 解包 PCK/EXE 文件
  restore  - 转换资源并还原项目结构
  full     - 完整流程 (解包 + 转换 + 还原)
  images   - 一键提取所有图片
  audio    - 一键提取所有音频
  info     - 显示 PCK 文件信息

用法:
  python godot_unpacker.py full game.pck -o output/
  python godot_unpacker.py images "unpack data/" -o images/
  python godot_unpacker.py audio "unpack data/" -o audio/
  python godot_unpacker.py info game.pck
"""

import sys
import os
import time
import argparse
from pathlib import Path

# 确保能导入同目录模块
sys.path.insert(0, str(Path(__file__).parent))

from pck_reader import PCKReader
from resource_converter import convert_resource, detect_resource_type
from project_restorer import ProjectRestorer, extract_all_images, extract_all_audio


def format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / 1024 / 1024:.1f} MB"
    else:
        return f"{size_bytes / 1024 / 1024 / 1024:.2f} GB"


def print_progress(current, total, path, success, error=None):
    pct = (current + 1) * 100 // total if total > 0 else 100
    status = "OK" if success else f"FAIL: {error}"
    # 截断长路径
    display_path = path if len(path) <= 60 else "..." + path[-57:]
    sys.stdout.write(f"\r[{pct:3d}%] ({current + 1}/{total}) {display_path:<60s}")
    sys.stdout.flush()


def print_restore_progress(current, total, path, status):
    pct = (current + 1) * 100 // total if total > 0 else 100
    display_path = path if len(path) <= 55 else "..." + path[-52:]
    sys.stdout.write(f"\r[{pct:3d}%] ({current + 1}/{total}) {status:<8s} {display_path:<55s}")
    sys.stdout.flush()


def print_extract_progress(current, total, path, success):
    pct = (current + 1) * 100 // total if total > 0 else 100
    tag = "OK" if success else "FAIL"
    display_path = path if len(path) <= 55 else "..." + path[-52:]
    sys.stdout.write(f"\r[{pct:3d}%] ({current + 1}/{total}) [{tag:4s}] {display_path:<55s}")
    sys.stdout.flush()


# ============================================================
# 命令: info
# ============================================================
def cmd_info(args):
    reader = PCKReader(args.input)
    if not reader.open():
        return 1
    print(reader.get_info())

    # 统计文件类型
    ext_counts = {}
    for entry in reader.entries:
        ext = Path(entry.path).suffix.lower()
        ext_counts[ext] = ext_counts.get(ext, 0) + 1

    print("文件类型分布:")
    for ext, count in sorted(ext_counts.items(), key=lambda x: -x[1])[:15]:
        print(f"  {ext or '(无后缀)':<25s} {count:>6d}")
    if len(ext_counts) > 15:
        print(f"  ... 还有 {len(ext_counts) - 15} 种类型")
    return 0


# ============================================================
# 命令: unpack
# ============================================================
def cmd_unpack(args):
    reader = PCKReader(args.input)
    if not reader.open():
        return 1

    print(reader.get_info())
    print(f"输出目录: {args.output}")
    print()

    start = time.time()
    success = reader.extract_all(args.output, callback=print_progress)
    elapsed = time.time() - start

    print()
    print(f"\n解包完成: {success}/{len(reader.entries)} 个文件 ({elapsed:.1f}s)")
    return 0


# ============================================================
# 命令: restore
# ============================================================
def cmd_restore(args):
    project_dir = args.input
    output_dir = args.output or (str(project_dir) + "_restored")

    print(f"项目目录: {project_dir}")
    print(f"输出目录: {output_dir}")
    print()

    restorer = ProjectRestorer(project_dir)

    print("扫描 .import 映射文件...")
    count = restorer.scan_imports()
    print(f"找到 {count} 个映射")

    if count == 0:
        print("未找到 .import 文件，无法还原")
        return 1

    # 统计类型
    type_counts = {}
    for m in restorer.mappings:
        type_counts[m.importer] = type_counts.get(m.importer, 0) + 1
    print("资源类型分布:")
    for imp, cnt in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {imp:<25s} {cnt:>6d}")
    print()

    print("开始转换与还原...")
    start = time.time()
    stats = restorer.restore_all(output_dir, callback=print_restore_progress)
    elapsed = time.time() - start

    print()
    print(f"\n还原完成 ({elapsed:.1f}s):")
    print(f"  图片转换: {stats['images_converted']}")
    print(f"  音频转换: {stats['audio_converted']}")
    print(f"  其他转换: {stats['other_converted']}")
    print(f"  跳过/原样复制: {stats['skipped']}")
    print(f"  失败: {stats['failed']}")

    if args.cleanup:
        print("\n清理冗余文件...")
        removed = restorer.cleanup(output_dir)
        print(f"已清理 {removed} 个冗余项")

    return 0


# ============================================================
# 命令: full
# ============================================================
def cmd_full(args):
    input_path = Path(args.input)
    output_dir = args.output or (input_path.stem + "_unpacked")

    # Step 1: 解包 PCK
    print("=" * 70)
    print("Step 1: 解包 PCK 文件")
    print("=" * 70)

    reader = PCKReader(str(input_path))
    if not reader.open():
        return 1

    print(reader.get_info())

    unpack_dir = os.path.join(output_dir, "_raw")
    print(f"解包到: {unpack_dir}")
    print()

    start = time.time()
    success = reader.extract_all(unpack_dir, callback=print_progress)
    elapsed = time.time() - start
    print(f"\n解包: {success}/{len(reader.entries)} ({elapsed:.1f}s)")

    # Step 2: 还原项目结构
    print()
    print("=" * 70)
    print("Step 2: 转换资源并还原项目结构")
    print("=" * 70)

    restore_dir = os.path.join(output_dir, "restored")

    restorer = ProjectRestorer(unpack_dir)
    count = restorer.scan_imports()
    print(f"找到 {count} 个 .import 映射")

    if count > 0:
        start2 = time.time()
        stats = restorer.restore_all(restore_dir, callback=print_restore_progress)
        elapsed2 = time.time() - start2

        print(f"\n还原完成 ({elapsed2:.1f}s):")
        print(f"  图片: {stats['images_converted']}, 音频: {stats['audio_converted']}")
        print(f"  其他: {stats['other_converted']}, 跳过: {stats['skipped']}, 失败: {stats['failed']}")
    else:
        print("未找到 .import 文件 (可能是 Godot 3 项目或已是原始文件)")

    # 复制未被 import 映射覆盖的文件
    print("\n复制非导入资源文件...")
    copied = _copy_non_imported(unpack_dir, restore_dir)
    print(f"已复制 {copied} 个文件")

    total_elapsed = time.time() - start
    print()
    print("=" * 70)
    print(f"全部完成! 总耗时: {total_elapsed:.1f}s")
    print(f"还原后的项目: {restore_dir}")
    print("=" * 70)
    return 0


def _copy_non_imported(src_dir: str, dst_dir: str) -> int:
    """复制非导入文件（脚本、场景、配置等）到还原目录"""
    src = Path(src_dir)
    dst = Path(dst_dir)
    copied = 0
    skip_dirs = {".godot"}
    skip_exts = {".import", ".remap"}

    for root, dirs, files in os.walk(src):
        # 跳过 .godot 目录
        rel_root = Path(root).relative_to(src)
        parts = rel_root.parts
        if parts and parts[0] in skip_dirs:
            continue

        for fname in files:
            if any(fname.endswith(ext) for ext in skip_exts):
                continue

            rel_path = rel_root / fname
            dst_path = dst / rel_path

            # 如果目标文件不存在（即未被 restore 覆盖），则复制
            if not dst_path.exists():
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    src_path = Path(root) / fname
                    dst_path.write_bytes(src_path.read_bytes())
                    copied += 1
                except OSError:
                    pass

    return copied


# ============================================================
# 命令: images
# ============================================================
def cmd_images(args):
    project_dir = args.input
    output_dir = args.output or "extracted_images"

    print(f"项目目录: {project_dir}")
    print(f"输出目录: {output_dir}")
    print()

    start = time.time()
    stats = extract_all_images(project_dir, output_dir, callback=print_extract_progress)
    elapsed = time.time() - start

    print()
    print(f"\n图片提取完成 ({elapsed:.1f}s):")
    print(f"  总数: {stats['total']}")
    print(f"  成功: {stats['success']}")
    print(f"  失败: {stats['failed']}")
    return 0


# ============================================================
# 命令: audio
# ============================================================
def cmd_audio(args):
    project_dir = args.input
    output_dir = args.output or "extracted_audio"

    print(f"项目目录: {project_dir}")
    print(f"输出目录: {output_dir}")
    print()

    start = time.time()
    stats = extract_all_audio(project_dir, output_dir, callback=print_extract_progress)
    elapsed = time.time() - start

    print()
    print(f"\n音频提取完成 ({elapsed:.1f}s):")
    print(f"  总数: {stats['total']}")
    print(f"  成功: {stats['success']}")
    print(f"  失败: {stats['failed']}")
    return 0


# ============================================================
# 主入口
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="Godot 引擎解包工具 - 轻量级 PCK 解包与资源还原",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s info game.pck                      # 查看 PCK 信息
  %(prog)s unpack game.pck -o output/          # 解包 PCK
  %(prog)s restore "unpack data/" -o restored/ # 转换并还原项目
  %(prog)s full game.pck -o output/            # 完整流程
  %(prog)s images "unpack data/" -o images/    # 提取所有图片
  %(prog)s audio "unpack data/" -o audio/      # 提取所有音频
  %(prog)s full game.exe -o output/            # 从 EXE 中提取
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="操作命令")

    # info
    p_info = subparsers.add_parser("info", help="显示 PCK 文件信息")
    p_info.add_argument("input", help="PCK 或 EXE 文件路径")

    # unpack
    p_unpack = subparsers.add_parser("unpack", help="解包 PCK 文件")
    p_unpack.add_argument("input", help="PCK 或 EXE 文件路径")
    p_unpack.add_argument("-o", "--output", default="unpacked", help="输出目录 (默认: unpacked)")

    # restore
    p_restore = subparsers.add_parser("restore", help="转换资源并还原项目结构")
    p_restore.add_argument("input", help="已解包的项目目录")
    p_restore.add_argument("-o", "--output", help="输出目录 (默认: <input>_restored)")
    p_restore.add_argument("--cleanup", action="store_true", help="清理 .import/.remap 和 .godot 缓存")

    # full
    p_full = subparsers.add_parser("full", help="完整流程: 解包 + 转换 + 还原")
    p_full.add_argument("input", help="PCK 或 EXE 文件路径")
    p_full.add_argument("-o", "--output", help="输出目录")

    # images
    p_images = subparsers.add_parser("images", help="一键提取所有图片")
    p_images.add_argument("input", help="已解包的项目目录")
    p_images.add_argument("-o", "--output", default="extracted_images", help="输出目录")

    # audio
    p_audio = subparsers.add_parser("audio", help="一键提取所有音频")
    p_audio.add_argument("input", help="已解包的项目目录")
    p_audio.add_argument("-o", "--output", default="extracted_audio", help="输出目录")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    print()
    print("=" * 70)
    print("  Godot Unpacker - 轻量级解包与资源还原工具")
    print("=" * 70)
    print()

    commands = {
        "info": cmd_info,
        "unpack": cmd_unpack,
        "restore": cmd_restore,
        "full": cmd_full,
        "images": cmd_images,
        "audio": cmd_audio,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main() or 0)
