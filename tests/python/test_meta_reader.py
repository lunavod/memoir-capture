"""Python reader for Memoir .meta files — validates binary format."""
import struct, sys, os, tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import Memoir

# --- Binary format readers ---

HEADER_FMT = "<8sII Q II"           # magic(8) version(4) reserved(4) created_ns(8) key_count(4) reserved(4)
HEADER_SIZE = struct.calcsize(HEADER_FMT)

KEY_FMT = "<II 32s"                  # bit_index(4) virtual_key(4) name(32)
KEY_SIZE = struct.calcsize(KEY_FMT)

ROW_FMT = "<QQ qq Q II II"          # frame_id(8) record_frame_index(8) capture_qpc(8) host_accept_qpc(8) keyboard_mask(8) width(4) height(4) analysis_stride(4) flags(4)
ROW_SIZE = struct.calcsize(ROW_FMT)


def read_meta(path):
    with open(path, "rb") as f:
        # Header
        hdr_data = f.read(HEADER_SIZE)
        assert len(hdr_data) == HEADER_SIZE, f"Header too short ({len(hdr_data)})"
        magic, version, _, created_ns, key_count, _ = struct.unpack(HEADER_FMT, hdr_data)
        assert magic == b"RCMETA1\x00", f"Bad magic: {magic!r}"
        assert version == 1

        # Key table
        keys = []
        for _ in range(key_count):
            kd = f.read(KEY_SIZE)
            bit_idx, vk, name_bytes = struct.unpack(KEY_FMT, kd)
            name = name_bytes.split(b"\x00", 1)[0].decode("ascii")
            keys.append({"bit_index": bit_idx, "virtual_key": vk, "name": name})

        # Rows
        rows = []
        while True:
            rd = f.read(ROW_SIZE)
            if len(rd) < ROW_SIZE:
                break
            fid, rfi, cqpc, hqpc, kbm, w, h, stride, flags = struct.unpack(ROW_FMT, rd)
            rows.append({
                "frame_id": fid,
                "record_frame_index": rfi,
                "capture_qpc": cqpc,
                "host_accept_qpc": hqpc,
                "keyboard_mask": kbm,
                "width": w, "height": h,
                "analysis_stride": stride,
                "flags": flags,
            })

    return {"magic": magic, "version": version, "created_ns": created_ns,
            "keys": keys, "rows": rows}


def test_meta_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        base = os.path.join(tmpdir, "meta_test")

        engine = Memoir.CaptureEngine(
            {"type": "monitor_index", "value": 0},
            max_fps=10.0,
        )
        engine.start()

        # Record 10 frames
        info = engine.start_recording(base)
        for i, pkt in enumerate(engine.frames()):
            pkt.release()
            if i >= 9:
                break
        engine.stop_recording()
        engine.stop()

        # Read and validate meta file
        meta_path = base + ".meta"
        assert os.path.isfile(meta_path), f"Meta file not found: {meta_path}"

        meta = read_meta(meta_path)
        print(f"Magic: {meta['magic']}")
        print(f"Version: {meta['version']}")
        print(f"Keys: {len(meta['keys'])}")
        print(f"Rows: {len(meta['rows'])}")

        # Key count should match engine's default key map
        assert meta["version"] == 1
        assert len(meta["keys"]) > 0, "No keys in key table"
        assert meta["keys"][0]["name"] == "W", f"First key should be W, got {meta['keys'][0]['name']}"

        # Row count should match recorded frames
        assert len(meta["rows"]) >= 10, f"Expected >= 10 rows, got {len(meta['rows'])}"

        # Validate row ordering
        for i, row in enumerate(meta["rows"]):
            assert row["record_frame_index"] == i, \
                f"Row {i}: expected record_frame_index={i}, got {row['record_frame_index']}"

        # frame_id should be monotonically increasing
        fids = [r["frame_id"] for r in meta["rows"]]
        assert fids == sorted(fids), "frame_ids not monotonically increasing"
        assert len(set(fids)) == len(fids), "Duplicate frame_ids"

        # Dimensions should be non-zero
        for row in meta["rows"]:
            assert row["width"] > 0 and row["height"] > 0

        print("Meta file validation passed!")


if __name__ == "__main__":
    test_meta_file()
