import struct
from typing import Optional, Tuple, List, Any

# ============================================================
# Godot 二进制资源格式 (RSRC) 变体类型常量。这些 ID 与运行时 Variant::Type 不同
# ============================================================
VT_NIL = 1
VT_BOOL = 2
VT_INT = 3
VT_FLOAT = 4
VT_STRING = 5
VT_VECTOR2 = 10
VT_RECT2 = 11
VT_VECTOR3 = 12
VT_PLANE = 13
VT_QUATERNION = 14
VT_AABB = 15
VT_BASIS = 16
VT_TRANSFORM3D = 17
VT_TRANSFORM2D = 18
VT_COLOR = 20
VT_NODE_PATH = 22
VT_RID = 23
VT_OBJECT = 24
VT_DICTIONARY = 26
VT_ARRAY = 30
VT_PACKED_BYTE_ARRAY = 31
VT_PACKED_INT32_ARRAY = 32
VT_PACKED_INT64_ARRAY = 33
VT_PACKED_FLOAT32_ARRAY = 34
VT_PACKED_FLOAT64_ARRAY = 35
VT_PACKED_STRING_ARRAY = 36
VT_INT64 = 41
VT_DOUBLE = 42
VT_STRING_NAME = 45
VT_VECTOR2I = 46
VT_RECT2I = 47
VT_VECTOR3I = 48
VT_VECTOR4 = 49
VT_VECTOR4I = 50
VT_PROJECTION = 51

VT_PACKED_INT64_ARRAY_ALT = 48

OBJ_EMPTY = 0
OBJ_EXTERNAL = 1
OBJ_INTERNAL = 2
OBJ_EXTERNAL_INDEX = 3

RESERVED_FIELDS_V2 = 14  # Godot 3 (format_version < 3)
RESERVED_FIELDS_V3 = 11  # Godot 4 (format_version >= 3)

FORMAT_FLAG_NAMED_SCENE_IDS = 1
FORMAT_FLAG_UIDS = 2
FORMAT_FLAG_REAL_IS_DOUBLE = 4
FORMAT_FLAG_SCRIPT_CLASS = 8


_ogg_crc_table = None


def _build_ogg_crc_table():
    global _ogg_crc_table
    _ogg_crc_table = [0] * 256
    for i in range(256):
        r = i << 24
        for _ in range(8):
            if r & 0x80000000:
                r = ((r << 1) ^ 0x04C11DB7) & 0xFFFFFFFF
            else:
                r = (r << 1) & 0xFFFFFFFF
        _ogg_crc_table[i] = r


def ogg_crc(data: bytes) -> int:
    if _ogg_crc_table is None:
        _build_ogg_crc_table()
    crc = 0
    for b in data:
        crc = ((_ogg_crc_table[((crc >> 24) & 0xFF) ^ b]) ^ (crc << 8)) & 0xFFFFFFFF
    return crc

class RSRCParser:
    def __init__(self, data: bytes):
        self.data = data
        self.off = 0
        self.big_endian = False
        self.use_real64 = False
        self.format_version = 0
        self.godot_major = 0
        self.godot_minor = 0
        self.flags = 0
        self.resource_type = ""
        self.strings: List[str] = []
        self.internal_resources: List[Tuple[str, int]] = []

    def _u8(self) -> int:
        v = self.data[self.off]
        self.off += 1
        return v

    def _u32(self) -> int:
        fmt = ">I" if self.big_endian else "<I"
        v = struct.unpack_from(fmt, self.data, self.off)[0]
        self.off += 4
        return v

    def _i32(self) -> int:
        fmt = ">i" if self.big_endian else "<i"
        v = struct.unpack_from(fmt, self.data, self.off)[0]
        self.off += 4
        return v

    def _u64(self) -> int:
        fmt = ">Q" if self.big_endian else "<Q"
        v = struct.unpack_from(fmt, self.data, self.off)[0]
        self.off += 8
        return v

    def _i64(self) -> int:
        fmt = ">q" if self.big_endian else "<q"
        v = struct.unpack_from(fmt, self.data, self.off)[0]
        self.off += 8
        return v

    def _f32(self) -> float:
        fmt = ">f" if self.big_endian else "<f"
        v = struct.unpack_from(fmt, self.data, self.off)[0]
        self.off += 4
        return v

    def _f64(self) -> float:
        fmt = ">d" if self.big_endian else "<d"
        v = struct.unpack_from(fmt, self.data, self.off)[0]
        self.off += 8
        return v

    def _read_string(self) -> str:
        length = self._u32()
        s = self.data[self.off : self.off + length].decode("utf-8", errors="replace")
        self.off += length
        return s.rstrip("\x00")

    def _read_variant(self) -> Any:
        vtype_raw = self._u32()
        vtype = vtype_raw & 0xFFFF

        if vtype == VT_NIL:
            return None

        elif vtype == VT_BOOL:
            return bool(self._u32())

        elif vtype == VT_INT:
            if vtype_raw & 0x10000:  
                return self._i64()
            return self._i32()

        elif vtype == VT_INT64:
            return self._i64()

        elif vtype == VT_FLOAT:
            if vtype_raw & 0x10000:  
                return self._f64()
            return self._f32()

        elif vtype == VT_DOUBLE:
            return self._f64()

        elif vtype in (VT_STRING, VT_STRING_NAME):
            return self._read_string()

        elif vtype == VT_NODE_PATH:
            name_count = self._u32()
            if name_count & 0x80000000:
                name_count &= 0x7FFFFFFF
                subname_count = self._u32()
                flags = self._u32()
                for _ in range(name_count):
                    self._read_string()
                for _ in range(subname_count):
                    self._read_string()
            else:
                subname_count = self._u32()
                flags = self._u32()
                for _ in range(name_count + subname_count):
                    self._read_string()
            return None

        elif vtype == VT_OBJECT:
            obj_type = self._u32()
            if obj_type == OBJ_EMPTY:
                return None
            elif obj_type == OBJ_INTERNAL:
                idx = self._u32()
                return ("internal_ref", idx)
            elif obj_type == OBJ_EXTERNAL:
                ext_type = self._read_string()
                ext_path = self._read_string()
                return ("external_ref", ext_type, ext_path)
            elif obj_type == OBJ_EXTERNAL_INDEX:
                idx = self._u32()
                return ("external_idx", idx)
            return None

        elif vtype == VT_DICTIONARY:
            count = self._u32()
            d = {}
            for _ in range(count):
                k = self._read_variant()
                v = self._read_variant()
                d[k] = v
            return d

        elif vtype == VT_ARRAY:
            count = self._u32()
            return [self._read_variant() for _ in range(count)]

        elif vtype == VT_PACKED_BYTE_ARRAY:
            length = self._u32()
            data = self.data[self.off : self.off + length]
            self.off += length
            self.off += (4 - length % 4) % 4  
            return data

        elif vtype in (VT_PACKED_INT32_ARRAY,):
            count = self._u32()
            vals = [
                struct.unpack_from("<i", self.data, self.off + i * 4)[0]
                for i in range(count)
            ]
            self.off += count * 4
            return vals

        elif vtype in (VT_PACKED_INT64_ARRAY, VT_PACKED_INT64_ARRAY_ALT):
            count = self._u32()
            fmt = ">q" if self.big_endian else "<q"
            vals = [
                struct.unpack_from(fmt, self.data, self.off + i * 8)[0]
                for i in range(count)
            ]
            self.off += count * 8
            return vals

        elif vtype == VT_PACKED_FLOAT32_ARRAY:
            count = self._u32()
            self.off += count * 4
            return []

        elif vtype == VT_PACKED_FLOAT64_ARRAY:
            count = self._u32()
            self.off += count * 8
            return []

        elif vtype == VT_PACKED_STRING_ARRAY:
            count = self._u32()
            return [self._read_string() for _ in range(count)]

        elif vtype == VT_COLOR:
            r, g, b, a = self._f32(), self._f32(), self._f32(), self._f32()
            return (r, g, b, a)

        elif vtype == VT_VECTOR2:
            return (self._f32(), self._f32())

        elif vtype == VT_VECTOR2I:
            return (self._i32(), self._i32())

        elif vtype == VT_VECTOR3:
            return (self._f32(), self._f32(), self._f32())

        elif vtype == VT_VECTOR3I:
            return (self._i32(), self._i32(), self._i32())

        elif vtype == VT_VECTOR4:
            return (self._f32(), self._f32(), self._f32(), self._f32())

        elif vtype == VT_VECTOR4I:
            return (self._i32(), self._i32(), self._i32(), self._i32())

        elif vtype == VT_RECT2:
            return (self._f32(), self._f32(), self._f32(), self._f32())

        elif vtype == VT_RECT2I:
            return (self._i32(), self._i32(), self._i32(), self._i32())

        elif vtype == VT_PLANE:
            return (self._f32(), self._f32(), self._f32(), self._f32())

        elif vtype == VT_QUATERNION:
            return (self._f32(), self._f32(), self._f32(), self._f32())

        elif vtype == VT_AABB:
            return tuple(self._f32() for _ in range(6))

        elif vtype == VT_BASIS:
            return tuple(self._f32() for _ in range(9))

        elif vtype == VT_TRANSFORM2D:
            return tuple(self._f32() for _ in range(6))

        elif vtype == VT_TRANSFORM3D:
            return tuple(self._f32() for _ in range(12))

        elif vtype == VT_PROJECTION:
            return tuple(self._f32() for _ in range(16))

        elif vtype == VT_RID:
            return self._u32()

        else:
            return f"__UNKNOWN_VARIANT_{vtype}__"

    def parse(self) -> dict:
        if self.data[:4] != b"RSRC":
            return {}

        try:
            return self._parse_inner()
        except (struct.error, IndexError, UnicodeDecodeError):
            return {}

    def _parse_inner(self) -> dict:
        self.off = 4
        self.big_endian = bool(self._u32())
        self.use_real64 = bool(self._u32())
        self.godot_major = self._u32()
        self.godot_minor = self._u32()
        self.format_version = self._u32()
        self.resource_type = self._read_string()

        self._u64()

        if self.format_version >= 3:
            self.flags = self._u32()

        if self.flags & FORMAT_FLAG_UIDS:
            self._u64()

        if self.flags & FORMAT_FLAG_SCRIPT_CLASS:
            self._read_string()

        reserved_count = RESERVED_FIELDS_V3 if self.format_version >= 3 else RESERVED_FIELDS_V2
        for _ in range(reserved_count):
            self._u32()

        string_count = self._u32()
        self.strings = []
        for _ in range(string_count):
            self.strings.append(self._read_string())

        ext_count = self._u32()
        for _ in range(ext_count):
            self._read_string() 
            self._read_string()  
            if self.flags & FORMAT_FLAG_UIDS:
                self._u64()

        int_count = self._u32()
        self.internal_resources = []
        for _ in range(int_count):
            path = self._read_string()
            offset = self._u64()
            self.internal_resources.append((path, offset))

        resources = {}
        for res_path, res_offset in self.internal_resources:
            self.off = res_offset
            res_type = self._read_string()
            prop_count = self._u32()

            props = {}
            for _ in range(prop_count):
                if self.off >= len(self.data) - 4:
                    break
                name_idx = self._u32()
                name = (
                    self.strings[name_idx]
                    if name_idx < len(self.strings)
                    else f"_unknown_{name_idx}"
                )
                try:
                    value = self._read_variant()
                except (struct.error, IndexError):
                    break
                props[name] = value

            resources[res_path] = {"type": res_type, "properties": props}

        return resources

def convert_ctex(data: bytes) -> Optional[Tuple[str, bytes]]:
    if len(data) < 56 or data[:4] != b"GST2":
        return None

    pos = 0
    while True:
        pos = data.find(b"RIFF", pos)
        if pos == -1:
            break
        if pos + 12 <= len(data) and data[pos + 8 : pos + 12] == b"WEBP":
            size = struct.unpack_from("<I", data, pos + 4)[0] + 8
            if pos + size <= len(data):
                return (".webp", data[pos : pos + size])
        pos += 1

    png_sig = b"\x89PNG\r\n\x1a\n"
    pos = data.find(png_sig)
    if pos != -1:
        iend = data.find(b"IEND", pos)
        if iend != -1:
            end = iend + 8  
            return (".png", data[pos:end])
        return (".png", data[pos:])

    return None

def convert_stex(data: bytes) -> Optional[Tuple[str, bytes]]:
    if len(data) < 36:
        return None

    png_sig = b"\x89PNG\r\n\x1a\n"
    pos = data.find(png_sig)
    if pos != -1:
        iend = data.find(b"IEND", pos)
        if iend != -1:
            return (".png", data[pos : iend + 8])
        return (".png", data[pos:])

    pos = data.find(b"RIFF")
    if pos != -1 and pos + 12 <= len(data) and data[pos + 8 : pos + 12] == b"WEBP":
        size = struct.unpack_from("<I", data, pos + 4)[0] + 8
        if pos + size <= len(data):
            return (".webp", data[pos : pos + size])

    return None

def _make_ogg_page(
    packets: List[bytes],
    granule: int,
    serial: int,
    seq_no: int,
    bos: bool = False,
    eos: bool = False,
) -> bytes:
    segments = []
    for pkt in packets:
        pkt_len = len(pkt)
        while pkt_len >= 255:
            segments.append(255)
            pkt_len -= 255
        segments.append(pkt_len)

    if len(segments) > 255:
        segments = segments[:255]

    header_type = 0
    if bos:
        header_type |= 0x02
    if eos:
        header_type |= 0x04

    header = b"OggS"
    header += struct.pack("<B", 0)  
    header += struct.pack("<B", header_type)
    header += struct.pack("<q", granule)
    header += struct.pack("<I", serial)
    header += struct.pack("<I", seq_no)
    header += struct.pack("<I", 0)  
    header += struct.pack("<B", len(segments))
    header += bytes(segments)

    body = b"".join(packets)
    page = header + body

    crc_val = ogg_crc(page)
    page = page[:22] + struct.pack("<I", crc_val) + page[26:]
    return page


def convert_oggvorbisstr(data: bytes) -> Optional[bytes]:
    if data[:4] != b"RSRC":
        return None

    try:
        parser = RSRCParser(data)
        resources = parser.parse()
    except Exception:
        return _fallback_ogg_extract(data)

    packet_data = None
    granule_positions = None
    sampling_rate = None

    for res_path, res_info in resources.items():
        if res_info["type"] == "OggPacketSequence":
            props = res_info["properties"]
            packet_data = props.get("packet_data")
            granule_positions = props.get("granule_positions")
            if granule_positions is None:
                granule_positions = props.get("packet_granule_positions")
            sampling_rate = props.get("sampling_rate")

    if not packet_data or not isinstance(packet_data, list):
        return _fallback_ogg_extract(data)

    if packet_data and len(packet_data) > 0:
        first_page = packet_data[0]
        if isinstance(first_page, list) and len(first_page) > 0:
            id_pkt = first_page[0]
            if isinstance(id_pkt, bytes) and len(id_pkt) >= 16 and id_pkt[1:7] == b"vorbis":
                sampling_rate = struct.unpack_from("<I", id_pkt, 12)[0]

    if not isinstance(granule_positions, list):
        granule_positions = [0] * len(packet_data)
        if len(granule_positions) > 0:
            granule_positions[-1] = -1  

    serial = 0x47444F54 
    ogg_data = b""

    for page_idx, page_packets in enumerate(packet_data):
        if not isinstance(page_packets, list):
            continue

        valid_packets = [p for p in page_packets if isinstance(p, bytes) and len(p) > 0]
        if not valid_packets:
            continue

        granule = (
            granule_positions[page_idx]
            if page_idx < len(granule_positions)
            else 0
        )

        bos = page_idx == 0
        eos = page_idx == len(packet_data) - 1

        total_segments = 0
        for pkt in valid_packets:
            total_segments += (len(pkt) // 255) + 1

        if total_segments <= 255:
            page = _make_ogg_page(valid_packets, granule, serial, page_idx, bos, eos)
            ogg_data += page
        else:
            current_packets = []
            current_segments = 0
            sub_seq = page_idx

            for pi, pkt in enumerate(valid_packets):
                pkt_segments = (len(pkt) // 255) + 1
                if current_segments + pkt_segments > 255 and current_packets:
                    page = _make_ogg_page(
                        current_packets,
                        0 if pi < len(valid_packets) - 1 else granule,
                        serial,
                        sub_seq,
                        bos and sub_seq == page_idx,
                        False,
                    )
                    ogg_data += page
                    current_packets = []
                    current_segments = 0
                    sub_seq += 1

                current_packets.append(pkt)
                current_segments += pkt_segments

            if current_packets:
                page = _make_ogg_page(
                    current_packets, granule, serial, sub_seq, False, eos
                )
                ogg_data += page

    return ogg_data if ogg_data else None


def _fallback_ogg_extract(data: bytes) -> Optional[bytes]:
    id_pos = data.find(b"\x01vorbis")
    if id_pos == -1:
        return None

    packets = []
    pos = id_pos

    size_off = id_pos - 4
    if size_off >= 0:
        id_size = struct.unpack_from("<I", data, size_off)[0]
        if 16 < id_size < 256:  
            id_header = data[id_pos : id_pos + id_size]
            packets.append(id_header)

    comment_pos = data.find(b"\x03vorbis", id_pos + 7)
    if comment_pos != -1:
        size_off = comment_pos - 4
        if size_off >= 0:
            c_size = struct.unpack_from("<I", data, size_off)[0]
            if 8 < c_size < 65536:
                packets.append(data[comment_pos : comment_pos + c_size])

    setup_pos = data.find(b"\x05vorbis", comment_pos + 7 if comment_pos != -1 else id_pos + 7)
    if setup_pos != -1:
        size_off = setup_pos - 4
        if size_off >= 0:
            s_size = struct.unpack_from("<I", data, size_off)[0]
            if 8 < s_size < 1048576:
                packets.append(data[setup_pos : setup_pos + s_size])

    if len(packets) < 3:
        return None

    if len(packets[0]) >= 16:
        sampling_rate = struct.unpack_from("<I", packets[0], 12)[0]

    serial = 0x47444F54
    ogg_data = b""
    ogg_data += _make_ogg_page([packets[0]], 0, serial, 0, bos=True)
    ogg_data += _make_ogg_page(packets[1:], 0, serial, 1)

    return ogg_data

WAVE_FORMAT_PCM = 1


def convert_sample(data: bytes) -> Optional[bytes]:
    if data[:4] != b"RSRC":
        return None

    parser = RSRCParser(data)
    resources = parser.parse()

    audio_data = None
    fmt = 0  
    mix_rate = 44100
    stereo = False
    loop_mode = 0
    loop_begin = 0
    loop_end = 0

    for res_path, res_info in resources.items():
        res_type = res_info["type"]
        if res_type in ("AudioStreamWAV", "AudioStreamSample"):
            props = res_info["properties"]
            audio_data = props.get("data")
            fmt = props.get("format", 0)
            mix_rate = props.get("mix_rate", 44100)
            stereo = props.get("stereo", False)
            loop_mode = props.get("loop_mode", 0)
            loop_begin = props.get("loop_begin", 0)
            loop_end = props.get("loop_end", 0)

    if not isinstance(audio_data, bytes) or len(audio_data) == 0:
        return None

    channels = 2 if stereo else 1

    if fmt == 0:
        bits_per_sample = 8
        wav_data = audio_data
    elif fmt == 1:
        bits_per_sample = 16
        wav_data = audio_data
    elif fmt == 2:
        bits_per_sample = 16
        wav_data = _decode_ima_adpcm(audio_data, stereo)
    else:
        bits_per_sample = 16
        wav_data = audio_data

    return _build_wav(wav_data, channels, mix_rate, bits_per_sample)


def _build_wav(audio_data: bytes, channels: int, sample_rate: int, bits_per_sample: int) -> bytes:
    byte_rate = sample_rate * channels * bits_per_sample // 8
    block_align = channels * bits_per_sample // 8
    data_size = len(audio_data)

    wav = b"RIFF"
    wav += struct.pack("<I", 36 + data_size)
    wav += b"WAVE"
    wav += b"fmt "
    wav += struct.pack("<I", 16)  
    wav += struct.pack("<H", WAVE_FORMAT_PCM)
    wav += struct.pack("<H", channels)
    wav += struct.pack("<I", sample_rate)
    wav += struct.pack("<I", byte_rate)
    wav += struct.pack("<H", block_align)
    wav += struct.pack("<H", bits_per_sample)
    wav += b"data"
    wav += struct.pack("<I", data_size)
    wav += audio_data

    return wav


def _decode_ima_adpcm(data: bytes, stereo: bool) -> bytes:
    ima_step_table = [
        7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 19, 21, 23, 25, 28, 31,
        34, 37, 41, 45, 50, 55, 60, 66, 73, 80, 88, 97, 107, 118, 130, 143,
        157, 173, 190, 209, 230, 253, 279, 307, 337, 371, 408, 449, 494, 544,
        598, 658, 724, 796, 876, 963, 1060, 1166, 1282, 1411, 1552, 1707,
        1878, 2066, 2272, 2499, 2749, 3024, 3327, 3660, 4026, 4428, 4871,
        5358, 5894, 6484, 7132, 7845, 8630, 9493, 10442, 11487, 12635,
        13899, 15289, 16818, 18500, 20350, 22385, 24623, 27086, 29794, 32767,
    ]
    ima_index_table = [-1, -1, -1, -1, 2, 4, 6, 8]

    channels = 2 if stereo else 1
    out = bytearray()
    offset = 0

    for ch in range(channels):
        ch_out = bytearray()
        off = offset
        while off < len(data):
            if off + 4 > len(data):
                break
            predictor = struct.unpack_from("<h", data, off)[0]
            step_index = struct.unpack_from("<H", data, off + 2)[0]
            step_index = min(step_index, 88)
            off += 4

            block_data_size = min(4096, len(data) - off)
            for i in range(block_data_size):
                byte = data[off + i]
                for nibble_idx in range(2):
                    nibble = byte & 0x0F if nibble_idx == 0 else (byte >> 4) & 0x0F

                    step = ima_step_table[step_index]
                    diff = step >> 3
                    if nibble & 1:
                        diff += step >> 2
                    if nibble & 2:
                        diff += step >> 1
                    if nibble & 4:
                        diff += step
                    if nibble & 8:
                        predictor -= diff
                    else:
                        predictor += diff

                    predictor = max(-32768, min(32767, predictor))
                    step_index += ima_index_table[nibble & 7]
                    step_index = max(0, min(88, step_index))

                    ch_out += struct.pack("<h", predictor)

            off += block_data_size

        if stereo:
            if ch == 0:
                left = ch_out
            else:
                right = ch_out
                for i in range(0, min(len(left), len(right)), 2):
                    out += left[i : i + 2]
                    out += right[i : i + 2]
        else:
            out = ch_out

        offset = off

    return bytes(out)

def detect_resource_type(data: bytes) -> str:
    if data[:4] == b"GST2":
        return "ctex"
    if data[:4] == b"GDST":
        return "stex"  
    if data[:4] == b"RSRC":
        type_pos = data.find(b"AudioStreamOggVorbis")
        if type_pos != -1 and type_pos < 128:
            return "oggvorbisstr"
        type_pos = data.find(b"AudioStreamWAV")
        if type_pos != -1 and type_pos < 128:
            return "sample"
        type_pos = data.find(b"AudioStreamSample")
        if type_pos != -1 and type_pos < 128:
            return "sample"
        type_pos = data.find(b"OggPacketSequence")
        if type_pos != -1 and type_pos < 128:
            return "oggvorbisstr"
        return "rsrc"
    return "unknown"


def convert_resource(data: bytes, original_ext: str = "") -> Optional[Tuple[str, bytes]]:
    res_type = detect_resource_type(data)

    if res_type == "ctex":
        return convert_ctex(data)

    if res_type == "stex":
        return convert_stex(data)

    if res_type == "oggvorbisstr":
        ogg = convert_oggvorbisstr(data)
        if ogg:
            return (".ogg", ogg)

    if res_type == "sample":
        wav = convert_sample(data)
        if wav:
            return (".wav", wav)

    return None
