# Metadata File Format (.meta)

## Overview

Every recording session produces a `.meta` file alongside the `.mp4`. The meta file is a binary file containing:

1. A fixed-size **header** with format version and creation time
2. A **key table** describing which keyboard keys are tracked
3. A sequence of **per-frame rows**, one for each recorded frame

The file is written sequentially during recording and can be read back with `MetaReader` or parsed manually with Python's `struct` module.

## File Layout

```
┌──────────────────────────┐
│  Header (32 bytes)       │
├──────────────────────────┤
│  Key entry 0 (40 bytes)  │
│  Key entry 1 (40 bytes)  │
│  ...                     │
│  Key entry N-1           │
├──────────────────────────┤
│  Frame row 0 (56 bytes)  │
│  Frame row 1 (56 bytes)  │
│  ...                     │
│  Frame row M-1           │
└──────────────────────────┘
```

## Header

32 bytes, little-endian, packed:

| Offset | Size | Type | Field | Description |
|--------|------|------|-------|-------------|
| 0 | 8 | `char[8]` | `magic` | `"RCMETA1\0"` (null-terminated) |
| 8 | 4 | `uint32` | `version` | Always `1` |
| 12 | 4 | `uint32` | `reserved0` | Zero |
| 16 | 8 | `uint64` | `created_unix_ns` | Creation time (nanoseconds since Unix epoch) |
| 24 | 4 | `uint32` | `key_count` | Number of key entries that follow |
| 28 | 4 | `uint32` | `reserved1` | Zero |

Python struct format: `<8sII Q II`

## Key Table Entry

40 bytes each, little-endian, packed. `key_count` entries follow the header.

| Offset | Size | Type | Field | Description |
|--------|------|------|-------|-------------|
| 0 | 4 | `uint32` | `bit_index` | Position in the 64-bit keyboard mask (0-63) |
| 4 | 4 | `uint32` | `virtual_key` | Windows virtual-key code |
| 8 | 32 | `char[32]` | `name` | Human-readable name, null-padded |

Python struct format: `<II 32s`

The key table defines the mapping from `keyboard_mask` bits to actual keys. For example, if entry 0 is `{bit_index=0, virtual_key=0x57, name="W"}`, then bit 0 of every frame's `keyboard_mask` indicates whether W was pressed.

## Per-Frame Row

56 bytes each, little-endian, packed. One row per recorded frame, in recording order.

| Offset | Size | Type | Field | Description |
|--------|------|------|-------|-------------|
| 0 | 8 | `uint64` | `frame_id` | Global engine frame ID |
| 8 | 8 | `uint64` | `record_frame_index` | 0-based index within this recording |
| 16 | 8 | `int64` | `capture_qpc` | WGC capture timestamp (100ns units) |
| 24 | 8 | `int64` | `host_accept_qpc` | Host QPC when frame was accepted |
| 32 | 8 | `uint64` | `keyboard_mask` | Packed key states at acceptance time |
| 40 | 4 | `uint32` | `width` | Source capture width |
| 44 | 4 | `uint32` | `height` | Source capture height |
| 48 | 4 | `uint32` | `analysis_stride` | CPU pixel buffer row stride in bytes |
| 52 | 4 | `uint32` | `flags` | Reserved (zero) |

Python struct format: `<QQ qq Q II II`

## Reading with MetaReader

```python
from memoir_capture import MetaReader

meta = MetaReader.read("session_001.meta")

# Header
print(f"Version: {meta.header.version}")
print(f"Created: {meta.header.created_unix_ns}")
print(f"Keys tracked: {meta.header.key_count}")

# Key table
for key in meta.keys:
    print(f"  Bit {key.bit_index}: vk=0x{key.virtual_key:02X} name={key.name}")

# Per-frame rows
for row in meta.rows:
    print(f"  Frame {row.frame_id} (rec #{row.record_frame_index}): "
          f"keys=0x{row.keyboard_mask:016x} "
          f"{row.width}x{row.height}")
```

`MetaReader.read()` returns a `MetaFile` dataclass:

```python
@dataclass
class MetaFile:
    header: MetaHeader     # magic, version, created_unix_ns, key_count
    keys: list[MetaKeyEntry]  # bit_index, virtual_key, name
    rows: list[MetaRow]    # frame_id, record_frame_index, timestamps, keyboard, dimensions
```

## Writing with MetaWriter

`MetaWriter` creates `.meta` files from Python — useful for synthetic replays, test data, or modifying existing recordings.

```python
from memoir_capture import MetaWriter, MetaKeyEntry, MetaRow

keys = [
    MetaKeyEntry(bit_index=0, virtual_key=0x57, name="W"),
    MetaKeyEntry(bit_index=1, virtual_key=0x41, name="A"),
    MetaKeyEntry(bit_index=2, virtual_key=0x53, name="S"),
    MetaKeyEntry(bit_index=3, virtual_key=0x44, name="D"),
]

with MetaWriter("synthetic.meta", keys) as writer:
    for i in range(100):
        writer.write_row(MetaRow(
            frame_id=i,
            record_frame_index=i,
            capture_qpc=i * 1_000_000,       # 100ms intervals in 100ns units
            host_accept_qpc=i * 1_000_000,
            keyboard_mask=(1 << 0) if i % 2 == 0 else 0,  # W every other frame
            width=1920,
            height=1080,
            analysis_stride=7680,             # 1920 * 4
        ))

print(f"Wrote {writer.row_count} rows")
```

### Modifying an existing meta file

```python
from memoir_capture import MetaReader, MetaWriter

# Read original
original = MetaReader.read("session.meta")

# Write modified version
with MetaWriter("session_modified.meta", original.keys) as w:
    for row in original.rows:
        # Clear keyboard state for privacy
        w.write_row(MetaRow(
            frame_id=row.frame_id,
            record_frame_index=row.record_frame_index,
            capture_qpc=row.capture_qpc,
            host_accept_qpc=row.host_accept_qpc,
            keyboard_mask=0,  # cleared
            width=row.width,
            height=row.height,
            analysis_stride=row.analysis_stride,
        ))
```

## Alignment Guarantees

- Row `N` in the meta file corresponds to frame `N` in the MP4
- `record_frame_index` is always `0, 1, 2, ...` within a session
- `frame_id` is monotonically increasing but may have gaps (dropped frames don't get IDs)
- The key table is identical for all frames in a session

## Parsing Manually (without memoir_capture)

If you need to read `.meta` files without installing the package:

```python
import struct

with open("session.meta", "rb") as f:
    # Header
    magic, ver, _, created_ns, key_count, _ = struct.unpack("<8sII Q II", f.read(32))
    assert magic == b"RCMETA1\x00"

    # Keys
    for _ in range(key_count):
        bit, vk, name = struct.unpack("<II 32s", f.read(40))
        print(f"Key bit={bit} vk=0x{vk:02X} name={name.split(b'\\x00')[0].decode()}")

    # Rows
    while (data := f.read(56)):
        fid, rfi, cqpc, hqpc, kb, w, h, stride, flags = struct.unpack("<QQ qq Q II II", data)
        print(f"Frame {fid}: {w}x{h} keys=0x{kb:016x}")
```
