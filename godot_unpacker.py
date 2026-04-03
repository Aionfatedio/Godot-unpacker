"""
Godot 引擎解包工具

功能:
  unpack   - 解包 PCK/EXE 文件
  restore  - 转换资源并还原项目结构
  full     - 解包并转换
  images   - 提取所有图片
  audio    - 提取所有音频
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

def cmd_info(args):
    reader = PCKReader(args.input)
    if not reader.open():
        return 1
    print(reader.get_info())

    ext_counts = {}
    for entry in reader.entries:
        ext = Path(entry.path).suffix.lower()
        ext_counts[ext] = ext_counts.get(ext, 0) + 1

    print("文件类型:")
    for ext, count in sorted(ext_counts.items(), key=lambda x: -x[1])[:15]:
        print(f"  {ext or '':<25s} {count:>6d}")
    if len(ext_counts) > 15:
        print(f"  ... 等 {len(ext_counts) - 15} 种类型")
    return 0

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


def cmd_restore(args):
    project_dir = args.input
    output_dir = args.output or (str(project_dir) + "_restored")

    print(f"游戏目录: {project_dir}")
    print(f"输出目录: {output_dir}")
    print()

    restorer = ProjectRestorer(project_dir)

    count = restorer.scan_imports()
    print(f"扫描到 {count} 个映射")

    if count == 0:
        return 1

    type_counts = {}
    for m in restorer.mappings:
        type_counts[m.importer] = type_counts.get(m.importer, 0) + 1
    print("资源类型:")
    for imp, cnt in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {imp:<25s} {cnt:>6d}")
    print()

    print("开始转换...")
    start = time.time()
    stats = restorer.restore_all(output_dir, callback=print_restore_progress)
    elapsed = time.time() - start

    print()
    print(f"\n解包完成 ({elapsed:.1f}s):")
    print(f"  图片转换: {stats['images_converted']}")
    print(f"  音频转换: {stats['audio_converted']}")
    print(f"  其他转换: {stats['other_converted']}")
    print(f"  跳过/原样复制: {stats['skipped']}")
    print(f"  失败: {stats['failed']}")

    if args.cleanup:
        removed = restorer.cleanup(output_dir)
        print(f"已清理 {removed} 个冗余项")

    return 0

def cmd_full(args):
    input_path = Path(args.input)
    output_dir = args.output or (input_path.stem + "_unpacked")

    print("=" * 70)
    print("解包文件")
    print("=" * 70)

    reader = PCKReader(str(input_path))
    if not reader.open():
        return 1, None

    print(reader.get_info())

    unpack_dir = os.path.join(output_dir, "_raw")
    print(f"解包到: {unpack_dir}")
    print()

    start = time.time()
    success = reader.extract_all(unpack_dir, callback=print_progress)
    elapsed = time.time() - start
    print(f"\n解包: {success}/{len(reader.entries)} ({elapsed:.1f}s)")

    print()
    print("=" * 70)
    print("转换文件")
    print("=" * 70)

    restore_dir = os.path.join(output_dir, "_resource")

    restorer = ProjectRestorer(unpack_dir)
    count = restorer.scan_imports()

    if count > 0:
        start2 = time.time()
        stats = restorer.restore_all(restore_dir, callback=print_restore_progress)
        elapsed2 = time.time() - start2

        print(f"\n转换完成 ({elapsed2:.1f}s):")
        print(f"  图片: {stats['images_converted']}, 音频: {stats['audio_converted']}")
        print(f"  其他: {stats['other_converted']}, 跳过: {stats['skipped']}, 失败: {stats['failed']}")
    else:
        print("ERROR：NOT FOUND .IMPORT FILES.")

    copied = _copy_non_imported(unpack_dir, restore_dir)

    total_elapsed = time.time() - start
    print()
    print("=" * 70)
    print(f"全部完成 总耗时: {total_elapsed:.1f}s")
    print("=" * 70)
    return 0, restore_dir


def _copy_non_imported(src_dir: str, dst_dir: str) -> int:
    src = Path(src_dir)
    dst = Path(dst_dir)
    copied = 0
    skip_dirs = {".godot"}
    skip_exts = {".import", ".remap"}

    for root, dirs, files in os.walk(src):
        rel_root = Path(root).relative_to(src)
        parts = rel_root.parts
        if parts and parts[0] in skip_dirs:
            continue

        for fname in files:
            if any(fname.endswith(ext) for ext in skip_exts):
                continue

            rel_path = rel_root / fname
            dst_path = dst / rel_path

            if not dst_path.exists():
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    src_path = Path(root) / fname
                    dst_path.write_bytes(src_path.read_bytes())
                    copied += 1
                except OSError:
                    pass

    return copied

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

def cmd_folder(folder_path: str):
    folder = Path(folder_path).resolve()

    if not folder.is_dir():
        print(f"[错误] 不是有效的文件夹: {folder}")
        return 1

    print(f"扫描文件夹: {folder}")
    print()

    valid_files = []
    for f in sorted(folder.iterdir()):
        if not f.is_file():
            continue
        if f.suffix.lower() not in ('.pck', '.exe'):
            continue
        reader = PCKReader(str(f))
        if reader.open():
            valid_files.append((f, reader))

    if not valid_files:
        print("错误: 未找到包含有效 PCK 数据的 .pck 或 .exe 文件")
        print("")
        return 1

    print(f"检测到 ({len(valid_files)} 个 Godot 文件):")
    print("-" * 50)
    for filepath, reader in valid_files:
        print(f"  [{filepath.name}]")
        for line in reader.get_info().strip().splitlines():
            print(f"    {line}")

        ext_counts = {}
        for entry in reader.entries:
            ext = Path(entry.path).suffix.lower()
            ext_counts[ext] = ext_counts.get(ext, 0) + 1
        top_exts = sorted(ext_counts.items(), key=lambda x: -x[1])[:8]
        parts = []
        for ext, count in top_exts:
            name = ext if ext else ""
            parts.append(f"{name}({count})")
        print(f"    文件类型: {', '.join(parts)}")
        print()

    print("-" * 50)
    try:
        choice = input("是否进行完整解包? [Enter] 继续 / 其他任意键退出: ")
    except (EOFError, KeyboardInterrupt):
        print("\n已取消")
        return 0

    if choice.strip() != "":
        print("已取消")
        return 0

    print()

    output_base = str(folder / "_unpacked")
    last_restore_dir = None

    for filepath, reader in valid_files:
        if len(valid_files) > 1:
            output_dir = os.path.join(output_base, filepath.stem)
        else:
            output_dir = output_base

        print()
        print("=" * 70)
        print(f"正在解包: {filepath.name}")
        print("=" * 70)

        args = argparse.Namespace(input=str(filepath), output=output_dir)
        result, restore_dir = cmd_full(args)
        if result != 0:
            print(f"警告: {filepath.name} 解包失败")
        else:
            last_restore_dir = restore_dir

    final_output = Path(output_base).resolve()
    if final_output.exists():
        try:
            os.startfile(str(final_output))
        except (OSError, AttributeError):
            import subprocess
            try:
                subprocess.run(["explorer", str(final_output)], check=False)
            except FileNotFoundError:
                print(f"Path: {final_output}")

    return 0


def main():
    if len(sys.argv) == 2 and os.path.isdir(sys.argv[1]):
        print()
        print("=" * 70)
        print("  Godot Unpacker  ")
        print("=" * 70)
        print()
        return cmd_folder(sys.argv[1])

    parser = argparse.ArgumentParser(
        description="Godot 引擎解包工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s "C:\\Games\\MyGame\\"                   # 解包
  %(prog)s info game.pck                      # 查看 PCK 信息
  %(prog)s unpack game.pck -o output/          # 解包 PCK
  %(prog)s restore "unpack data/" -o restored/ # 转换并还原项目
  %(prog)s full game.pck -o output/            # 解包并转换
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
    p_unpack.add_argument("-o", "--output", default="unpacked", help="输出目录 (默认: *_unpacked)")

    # restore
    p_restore = subparsers.add_parser("restore", help="转换资源并还原项目结构")
    p_restore.add_argument("input", help="已解包的项目目录")
    p_restore.add_argument("-o", "--output", help="输出目录 (默认: <input>_restored)")
    p_restore.add_argument("--cleanup", action="store_true", help="清理 .import/.remap 和 .godot 缓存")

    # full
    p_full = subparsers.add_parser("full", help="解包并转换")
    p_full.add_argument("input", help="PCK 或 EXE 文件路径")
    p_full.add_argument("-o", "--output", help="输出目录")

    # images
    p_images = subparsers.add_parser("images", help="提取所有图片")
    p_images.add_argument("input", help="已解包的项目目录")
    p_images.add_argument("-o", "--output", default="extracted_images", help="输出目录")

    # audio
    p_audio = subparsers.add_parser("audio", help="提取所有音频")
    p_audio.add_argument("input", help="已解包的项目目录")
    p_audio.add_argument("-o", "--output", default="extracted_audio", help="输出目录")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    print()
    print("=" * 70)
    print("  Godot Unpacker  ")
    print("=" * 70)
    print()

    commands = {
        "info": cmd_info,
        "unpack": cmd_unpack,
        "restore": cmd_restore,
        "full": lambda args: cmd_full(args)[0],
        "images": cmd_images,
        "audio": cmd_audio,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main() or 0)
