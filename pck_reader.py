import struct
import os
import hashlib
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, BinaryIO

GDPC_MAGIC = b"GDPC"
PCK_HEADER_SIZE = 4 + 4 * 4  


@dataclass
class PCKFileEntry:
    path: str
    offset: int
    size: int
    md5: bytes
    flags: int = 0
    encrypted: bool = False


@dataclass
class PCKHeader:
    pack_version: int
    godot_major: int
    godot_minor: int
    godot_patch: int
    flags: int = 0
    file_base: int = 0
    file_count: int = 0


class PCKReader:
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.header: Optional[PCKHeader] = None
        self.entries: List[PCKFileEntry] = []
        self._pck_offset = 0  

    def open(self) -> bool:
        if not self.file_path.exists():
            print(f"错误: 文件不存在: {self.file_path}")
            return False

        with open(self.file_path, "rb") as f:
            magic = f.read(4)
            if magic == GDPC_MAGIC:
                self._pck_offset = 0
                f.seek(0)
                return self._parse(f)

            pck_off = self._find_embedded_pck(f)
            if pck_off is not None:
                self._pck_offset = pck_off
                f.seek(pck_off)
                return self._parse(f)

        return False

    def _find_embedded_pck(self, f: BinaryIO) -> Optional[int]:
        f.seek(0, 2)
        file_size = f.tell()

        if file_size >= 12:
            f.seek(file_size - 4)
            end_magic = f.read(4)
            if end_magic == GDPC_MAGIC:
                f.seek(file_size - 12)
                pck_size = struct.unpack("<Q", f.read(8))[0]
                pck_start = file_size - 12 - pck_size
                if pck_start >= 0:
                    f.seek(pck_start)
                    if f.read(4) == GDPC_MAGIC:
                        return pck_start

        scan_chunk = 1024 * 1024  
        f.seek(0)
        offset = 0
        while offset < file_size:
            f.seek(offset)
            chunk = f.read(min(scan_chunk + 4, file_size - offset))
            pos = chunk.find(GDPC_MAGIC)
            if pos != -1:
                candidate = offset + pos
                f.seek(candidate)
                test_magic = f.read(4)
                if test_magic == GDPC_MAGIC:
                    pack_ver = struct.unpack("<I", f.read(4))[0]
                    major = struct.unpack("<I", f.read(4))[0]
                    if pack_ver <= 3 and major <= 5:
                        return candidate
            offset += scan_chunk

        return None

    def _parse(self, f: BinaryIO) -> bool:
        try:
            magic = f.read(4)
            if magic != GDPC_MAGIC:
                return False

            pack_version = struct.unpack("<I", f.read(4))[0]
            godot_major = struct.unpack("<I", f.read(4))[0]
            godot_minor = struct.unpack("<I", f.read(4))[0]
            godot_patch = struct.unpack("<I", f.read(4))[0]

            flags = 0
            file_base = 0
            index_offset = None

            if pack_version >= 2:
                flags = struct.unpack("<I", f.read(4))[0]
                file_base = struct.unpack("<Q", f.read(8))[0]

            if pack_version >= 3:
                index_offset = struct.unpack("<Q", f.read(8))[0]

            f.read(16 * 4)

            # PCK v3: 索引表在文件末尾，需要 seek 到索引偏移处
            if index_offset is not None:
                f.seek(index_offset + self._pck_offset)

            file_count = struct.unpack("<I", f.read(4))[0]

            self.header = PCKHeader(
                pack_version=pack_version,
                godot_major=godot_major,
                godot_minor=godot_minor,
                godot_patch=godot_patch,
                flags=flags,
                file_base=file_base,
                file_count=file_count,
            )

            self.entries = []
            for _ in range(file_count):
                path_len = struct.unpack("<I", f.read(4))[0]
                path_bytes = f.read(path_len)
                pad = (4 - path_len % 4) % 4
                if pad:
                    f.read(pad)

                path = path_bytes.decode("utf-8", errors="replace").rstrip("\x00")
                offset = struct.unpack("<Q", f.read(8))[0]
                size = struct.unpack("<Q", f.read(8))[0]
                md5 = f.read(16)

                entry_flags = 0
                if pack_version >= 2:
                    entry_flags = struct.unpack("<I", f.read(4))[0]

                actual_offset = offset + file_base + self._pck_offset

                entry = PCKFileEntry(
                    path=path,
                    offset=actual_offset,
                    size=size,
                    md5=md5,
                    flags=entry_flags,
                    encrypted=bool(entry_flags & 0x01),
                )
                self.entries.append(entry)

            return True

        except (struct.error, OSError) as e:
            print(f"错误: {e}")
            return False

    def extract_all(self, output_dir: str, callback=None) -> int:
        output_path = Path(output_dir)
        success = 0

        with open(self.file_path, "rb") as f:
            total = len(self.entries)
            for i, entry in enumerate(self.entries):
                if entry.encrypted:
                    if callback:
                        callback(i, total, entry.path, False, "已加密")
                    continue

                ok = self._extract_entry(f, entry, output_path)
                success += ok

                if callback:
                    callback(i, total, entry.path, ok, None if ok else "提取失败")

        return success

    def extract_file(self, entry: PCKFileEntry, output_dir: str) -> bool:
        with open(self.file_path, "rb") as f:
            return self._extract_entry(f, entry, Path(output_dir))

    def _extract_entry(self, f: BinaryIO, entry: PCKFileEntry, output_dir: Path) -> bool:
        try:
            rel_path = entry.path
            if rel_path.startswith("res://"):
                rel_path = rel_path[6:]

            out_path = output_dir / rel_path
            out_path.parent.mkdir(parents=True, exist_ok=True)

            f.seek(entry.offset)
            data = f.read(entry.size)

            with open(out_path, "wb") as out_f:
                out_f.write(data)

            return True
        except OSError:
            return False

    def get_info(self) -> str:
        if not self.header:
            return "未打开"
        h = self.header
        enc_count = sum(1 for e in self.entries if e.encrypted)
        total_size = sum(e.size for e in self.entries)
        info = (
            f"PCK 版本: {h.pack_version}\n"
            f"Godot 版本: {h.godot_major}.{h.godot_minor}.{h.godot_patch}\n"
            f"文件数量: {h.file_count}\n"
            f"总大小: {total_size / 1024 / 1024:.1f} MB\n"
        )
        if enc_count:
            info += f"加密文件: {enc_count}\n"
        if self._pck_offset:
            info += f"嵌入偏移: {self._pck_offset:#x}\n"
        return info
