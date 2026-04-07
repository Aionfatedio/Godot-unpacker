# Godot Unpacker
[English](README.md)  **简体中文**

Godot 引擎 `.pck` / `.exe` 解封包脚本，支持 **Godot 3**（PCK v1）和 **Godot 4**（PCK v2）。

## 功能

- 从 .pck 或 .exe 文件的 PCK 数据中提取资源文件
- 支持将 Godot 格式转换为通用格式：
  - `.ctex`（GST2）/ `.stex`（GDST）&rarr; `.png` / `.webp`
  - `.oggvorbisstr`（RSRC）&rarr; `.ogg`
  - `.sample`（RSRC AudioStreamWAV）&rarr; `.wav`（支持 IMA-ADPCM 解码）
- 支持提取图片或音频资源
- 可通过 .import 映射文件重建原始目录结构

> 实验性支持 PCK v3（Godot 4.5+）

## 快速开始

```bash
git clone https://github.com/Aionfatedio/Godot-unpacker.git
cd Godot-unpacker

# 传入游戏文件夹
python godot_unpacker.py "C:\Games\GodotGame\"
# 传入游戏pck文件
python godot_unpacker.py full game.pck -o output/
```

### 环境要求

- Python 3.8+

## 使用

```bash
python godot_unpacker.py "path/to/godot/game/"
```

**输出结构：**

```
*_unpacked/
  _raw/         # Godot 原始格式文件
  _resource/    # 还原后的项目资源（已转换为通用格式）
```

### 子命令

#### `info` — 查看 PCK 信息

```bash
python godot_unpacker.py info game.pck
```

显示 PCK 版本、Godot 引擎版本、文件数量、总大小及文件类型分布。

#### `unpack` — 原始提取

```bash
python godot_unpacker.py unpack game.pck -o output/
```

将 PCK 中的所有文件执行提取，不做格式转换。

#### `full` — 转换提取

```bash
python godot_unpacker.py full game.pck -o output/
python godot_unpacker.py full game.exe -o output/
```

将 PCK 中的所有文件提取后执行转换，并还原项目结构。

#### `restore` — 原始转换

```bash
python godot_unpacker.py restore "_raw/" -o restored/
python godot_unpacker.py restore "_raw/" --cleanup
```

对已解包项目目录的原始提取文件进行资源转换和结构还原。`--cleanup` 参数会清理 `.import` / `.remap` 文件和 `.godot` 缓存目录。

#### `images` — 提取全部图片

```bash
python godot_unpacker.py images "_raw/" -o images/
```

提取转换所有图片资源（texture / image 类型）

#### `audio` — 提取全部音频

```bash
python godot_unpacker.py audio "_raw/" -o audio/
```

提取转换所有音频资源（OGG Vorbis / WAV / MP3 类型）

## 使用示例

**查看 PCK 信息：**

```
$ python godot_unpacker.py info game.pck

PCK 版本: 2
Godot 版本: 4.3.0
文件数量: 1523
总大小: 245.8 MB

文件类型分布:
  .ctex                       892
  .import                     446
  .ogg                         85
  .tres                        42
  ...
```

**解包：**

```
$ python godot_unpacker.py "C:\Games\SomeGodotGame\"

扫描文件夹: C:\Games\SomeGodotGame

检测到 Godot 引擎游戏 (2 个有效文件):
--------------------------------------------------
  [game.pck]
    PCK 版本: 2
    Godot 版本: 4.3.0
    文件数量: 1523
    总大小: 245.8 MB
    文件类型: .ctex(892), .import(446), .ogg(85), .tres(42)

  [game.exe]
    PCK 版本: 2
    Godot 版本: 4.3.0
    ...
--------------------------------------------------
进行完整解包? [Enter] 
```

## 项目结构

```
godot_unpacker.py       # CLI 入口
pck_reader.py           # PCK 解析
resource_converter.py   # 格式转换（CTEX、STEX、OGG、WAV、RSRC）
project_restorer.py     # 结构还原
```

## 许可证

MIT
