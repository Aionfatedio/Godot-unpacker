# Godot Unpacker
[简体中文](README_CN.md)

Godot Engine `.pck` / `.exe` unpacking script, supporting **Godot 3** (PCK v1) and **Godot 4** (PCK v2).

## Features

- **PCK Unpacking** — Extract all data from `.pck` or `.exe` file PCK data
- **Format Conversion** — Automatically convert Godot-proprietary formats to common formats:
  - `.ctex` (GST2) / `.stex` (GDST) → `.png` / `.webp`
  - `.oggvorbisstr` (RSRC) → `.ogg`
  - `.sample` (RSRC AudioStreamWAV) → `.wav` (supports IMA-ADPCM decoding)
- **Batch Extraction** — Extract only image or audio resources
- **Project Structure Restoration** — Reconstruct original directory structures via `.import` mapping files

### Supported Formats

> **Experimental support for PCK v3 (Godot 4.5+)**

| **Godot Format** | **Magic Number** | **Description**                          | **Output Format** |
| ---------------- | ---------------- | ---------------------------------------- | ----------------- |
| PCK v1           | `GDPC`           | Godot 3 Resource Pack                    | Extracted files   |
| PCK v2           | `GDPC`           | Godot 4 Resource Pack                    | Extracted files   |
| CTEX             | `GST2`           | Godot 4 CompressedTexture2D              | `.png` / `.webp`  |
| STEX             | `GDST`           | Godot 3 StreamTexture                    | `.png` / `.webp`  |
| RSRC (OGG)       | `RSRC`           | AudioStreamOggVorbis / OggPacketSequence | `.ogg`            |
| RSRC (WAV)       | `RSRC`           | AudioStreamWAV / AudioStreamSample       | `.wav`            |
| Embedded PCK     | —                | PCK data appended to the end of `.exe`   | Auto-detected     |

## Quick Start

```bash
git clone https://github.com/Aionfatedio/Godot-unpacker.git
cd Godot-unpacker

# game folder
python godot_unpacker.py "C:\Games\GodotGame\"
# game pck file
python godot_unpacker.py full game.pck -o output/
```

### Environmental Requirements

- Python 3.8+

## Usage

```bash
python godot_unpacker.py "path/to/godot/game/"
```

Pass in the game path; the tool will automatically scan for `.pck` / `.exe` files and execute unpacking after confirmation.

**Output Structure:**

```
*_unpacked/
  _raw/         # Godot original format files
  _resource/    # Restored project resources (converted to common formats)
```

### Subcommands

#### `info` — View PCK Information

```bash
python godot_unpacker.py info game.pck
```

Displays PCK version, Godot engine version, file count, total size, and file type distribution.

#### `unpack` — Raw Extraction

```bash
python godot_unpacker.py unpack game.pck -o output/
```

Extracts all files from the PCK without format conversion.

#### `full` — Converted Extraction

```bash
python godot_unpacker.py full game.pck -o output/
python godot_unpacker.py full game.exe -o output/
```

Extracts all files from the PCK, performs conversion, and restores the project structure.

#### `restore` — Original Conversion

```bash
python godot_unpacker.py restore "_raw/" -o restored/
python godot_unpacker.py restore "_raw/" --cleanup
```

Performs resource conversion and structure restoration on raw extracted files from an already unpacked project directory. The `--cleanup` parameter will clean up `.import` / `.remap` files and the `.godot` cache directory.

#### `images` — Extract All Images

```bash
python godot_unpacker.py images "_raw/" -o images/
```

Extracts and converts all image resources (texture / image types).

#### `audio` — Extract All Audio

```bash
python godot_unpacker.py audio "_raw/" -o audio/
```

Extracts and converts all audio resources (OGG / WAV / MP3 types).

## Project Structure

- `godot_unpacker.py` — CLI Entry
- `pck_reader.py` — PCK Parsing
- `resource_converter.py` — Format Conversion (CTEX, STEX, OGG, WAV, RSRC)
- `project_restorer.py` — Structure Restoration

## License

MIT

