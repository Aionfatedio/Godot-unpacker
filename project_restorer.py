import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional
from resource_converter import convert_resource


@dataclass
class ImportMapping:
    original_path: str    
    imported_path: str    
    importer: str         
    resource_type: str    


class ProjectRestorer:
    def __init__(self, project_dir: str):
        self.project_dir = Path(project_dir)
        self.mappings: List[ImportMapping] = []
        self.stats = {
            "images_converted": 0,
            "audio_converted": 0,
            "other_converted": 0,
            "failed": 0,
            "skipped": 0,
        }

    def scan_imports(self) -> int:
        self.mappings = []

        for root, dirs, files in os.walk(self.project_dir):
            for fname in files:
                if fname.endswith(".import"):
                    fpath = Path(root) / fname
                    mapping = self._parse_import_file(fpath)
                    if mapping:
                        self.mappings.append(mapping)

        return len(self.mappings)

    def scan_remaps(self) -> Dict[str, str]:
        remaps = {}
        for root, dirs, files in os.walk(self.project_dir):
            for fname in files:
                if fname.endswith(".remap"):
                    fpath = Path(root) / fname
                    remap = self._parse_remap_file(fpath)
                    if remap:
                        remaps[fname] = remap
        return remaps

    def _parse_import_file(self, path: Path) -> Optional[ImportMapping]:
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None

        importer = ""
        resource_type = ""
        imported_path = ""

        in_remap = False
        for line in content.splitlines():
            line = line.strip()
            if line == "[remap]":
                in_remap = True
                continue
            if line.startswith("[") and line.endswith("]"):
                in_remap = False
                continue

            if not in_remap:
                continue

            if line.startswith("importer="):
                importer = line.split("=", 1)[1].strip().strip('"')
            elif line.startswith("type="):
                resource_type = line.split("=", 1)[1].strip().strip('"')
            elif line.startswith("path="):
                imported_path = line.split("=", 1)[1].strip().strip('"')
            elif line.startswith("path.") and not imported_path:
                imported_path = line.split("=", 1)[1].strip().strip('"')

        if not imported_path:
            return None

        rel = path.relative_to(self.project_dir)
        original_rel = str(rel).replace("\\", "/")
        if original_rel.endswith(".import"):
            original_rel = original_rel[: -len(".import")]
        original_path = "res://" + original_rel

        return ImportMapping(
            original_path=original_path,
            imported_path=imported_path,
            importer=importer,
            resource_type=resource_type,
        )

    def _parse_remap_file(self, path: Path) -> Optional[str]:
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None

        for line in content.splitlines():
            line = line.strip()
            if line.startswith("path="):
                return line.split("=", 1)[1].strip().strip('"')
        return None

    def _res_to_local(self, res_path: str) -> Path:
        if res_path.startswith("res://"):
            rel = res_path[6:]
        else:
            rel = res_path
        return self.project_dir / rel.replace("/", os.sep)

    def restore_all(self, output_dir: Optional[str] = None, callback=None) -> dict:
        if output_dir:
            out_base = Path(output_dir)
        else:
            out_base = self.project_dir

        total = len(self.mappings)

        for i, mapping in enumerate(self.mappings):
            if mapping.original_path.startswith("res://"):
                rel = mapping.original_path[6:]
            else:
                rel = mapping.original_path
            out_path = out_base / rel.replace("/", os.sep)

            status = self._restore_single(mapping, out_path)

            if callback:
                callback(i, total, rel, status)

        return self.stats

    def _restore_single(self, mapping: ImportMapping, out_path: Path) -> str:
        imported_local = self._res_to_local(mapping.imported_path)

        if not imported_local.exists():
            self.stats["skipped"] += 1
            return "跳过(文件不存在)"

        try:
            data = imported_local.read_bytes()
        except OSError:
            self.stats["failed"] += 1
            return "读取失败"

        result = convert_resource(data, out_path.suffix)

        if result:
            ext, converted_data = result
            final_path = out_path

            final_path.parent.mkdir(parents=True, exist_ok=True)

            try:
                final_path.write_bytes(converted_data)
            except OSError:
                self.stats["failed"] += 1
                return "写入失败"

            if mapping.importer in ("texture", "image"):
                self.stats["images_converted"] += 1
            elif mapping.importer in ("oggvorbisstr", "wav", "mp3"):
                self.stats["audio_converted"] += 1
            else:
                self.stats["other_converted"] += 1

            return "已转换"
        else:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                out_path.write_bytes(data)
            except OSError:
                self.stats["failed"] += 1
                return "写入失败"

            self.stats["skipped"] += 1
            return "复制"

    def cleanup(self, target_dir: Optional[str] = None):
        base = Path(target_dir) if target_dir else self.project_dir
        removed = 0
        for root, dirs, files in os.walk(base):
            for fname in files:
                if fname.endswith(".import") or fname.endswith(".remap"):
                    fpath = Path(root) / fname
                    try:
                        fpath.unlink()
                        removed += 1
                    except OSError:
                        pass

        imported_dir = base / ".godot" / "imported"
        if imported_dir.exists():
            import shutil
            try:
                shutil.rmtree(imported_dir)
                removed += 1
            except OSError:
                pass

        exported_dir = base / ".godot" / "exported"
        if exported_dir.exists():
            import shutil
            try:
                shutil.rmtree(exported_dir)
                removed += 1
            except OSError:
                pass

        return removed

def extract_all_images(project_dir: str, output_dir: str, callback=None) -> dict:
    restorer = ProjectRestorer(project_dir)
    count = restorer.scan_imports()

    stats = {"total": 0, "success": 0, "failed": 0}
    out_base = Path(output_dir)
    out_base.mkdir(parents=True, exist_ok=True)

    image_mappings = [m for m in restorer.mappings if m.importer in ("texture", "image")]
    stats["total"] = len(image_mappings)

    for i, mapping in enumerate(image_mappings):
        imported_local = restorer._res_to_local(mapping.imported_path)
        if not imported_local.exists():
            stats["failed"] += 1
            continue

        try:
            data = imported_local.read_bytes()
        except OSError:
            stats["failed"] += 1
            continue

        result = convert_resource(data)
        if result:
            ext, converted = result
            if mapping.original_path.startswith("res://"):
                rel = mapping.original_path[6:]
            else:
                rel = mapping.original_path
            out_path = out_base / rel.replace("/", os.sep)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                out_path.write_bytes(converted)
                stats["success"] += 1
            except OSError:
                stats["failed"] += 1
        else:
            stats["failed"] += 1

        if callback:
            callback(i, stats["total"], mapping.original_path, result is not None)

    return stats


def extract_all_audio(project_dir: str, output_dir: str, callback=None) -> dict:
    restorer = ProjectRestorer(project_dir)
    count = restorer.scan_imports()

    stats = {"total": 0, "success": 0, "failed": 0}
    out_base = Path(output_dir)
    out_base.mkdir(parents=True, exist_ok=True)

    audio_importers = ("oggvorbisstr", "wav", "mp3")
    audio_mappings = [m for m in restorer.mappings if m.importer in audio_importers]
    stats["total"] = len(audio_mappings)

    for i, mapping in enumerate(audio_mappings):
        imported_local = restorer._res_to_local(mapping.imported_path)
        if not imported_local.exists():
            stats["failed"] += 1
            continue

        try:
            data = imported_local.read_bytes()
        except OSError:
            stats["failed"] += 1
            continue

        result = convert_resource(data)
        if result:
            ext, converted = result
            if mapping.original_path.startswith("res://"):
                rel = mapping.original_path[6:]
            else:
                rel = mapping.original_path
            out_path = out_base / rel.replace("/", os.sep)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                out_path.write_bytes(converted)
                stats["success"] += 1
            except OSError:
                stats["failed"] += 1
        else:
            stats["failed"] += 1

        if callback:
            callback(i, stats["total"], mapping.original_path, result is not None)

    return stats
