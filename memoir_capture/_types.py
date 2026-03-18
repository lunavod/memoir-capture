"""Typed dataclasses for all memoir-capture public API return values."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


# ---------------------------------------------------------------------------
# Capture targets
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class MonitorTarget:
    """Capture a monitor by index (0 = primary)."""
    index: int = 0


@dataclass(frozen=True, slots=True)
class WindowTitleTarget:
    """Capture a window whose title matches a regex."""
    pattern: str


@dataclass(frozen=True, slots=True)
class WindowExeTarget:
    """Capture a window whose executable name matches a regex."""
    pattern: str


CaptureTarget = MonitorTarget | WindowTitleTarget | WindowExeTarget


# ---------------------------------------------------------------------------
# Engine stats
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class EngineStats:
    frames_seen: int
    frames_accepted: int
    frames_dropped_queue_full: int
    frames_dropped_internal_error: int
    frames_recorded: int
    python_queue_depth: int
    recording_active: bool


# ---------------------------------------------------------------------------
# Recording info
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class RecordingInfo:
    base_path: str
    video_path: str
    meta_path: str
    codec: str
    width: int
    height: int


# ---------------------------------------------------------------------------
# Metadata file types
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class MetaHeader:
    magic: bytes
    version: int
    created_unix_ns: int
    key_count: int


@dataclass(frozen=True, slots=True)
class MetaKeyEntry:
    bit_index: int
    virtual_key: int
    name: str


@dataclass(frozen=True, slots=True)
class MetaRow:
    frame_id: int
    record_frame_index: int
    capture_qpc: int
    host_accept_qpc: int
    keyboard_mask: int
    width: int
    height: int
    analysis_stride: int
    flags: int = 0

    def is_pressed(self, name: str, keys: list[MetaKeyEntry]) -> bool:
        """Check if a key was pressed in this frame by name."""
        for k in keys:
            if k.name == name:
                return bool(self.keyboard_mask & (1 << k.bit_index))
        raise KeyError(f"Key {name!r} not in key map")

    def pressed_keys(self, keys: list[MetaKeyEntry]) -> list[str]:
        """Return list of key names that were pressed in this frame."""
        return [
            k.name for k in keys
            if self.keyboard_mask & (1 << k.bit_index)
        ]

    def capture_time_sec(self, qpc_frequency: int) -> float:
        """Convert capture_qpc to seconds (divide by QPC frequency)."""
        return self.capture_qpc / qpc_frequency


@dataclass(frozen=True, slots=True)
class MetaFile:
    """Complete contents of a .meta file."""
    header: MetaHeader
    keys: list[MetaKeyEntry]
    rows: list[MetaRow]

    # -- sequence protocol --

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> MetaRow:
        return self.rows[index]

    def __iter__(self):
        return iter(self.rows)

    # -- key lookup --

    def key_by_name(self, name: str) -> MetaKeyEntry:
        """Find a key entry by name. Raises KeyError if not found."""
        for k in self.keys:
            if k.name == name:
                return k
        raise KeyError(f"Key {name!r} not in key map")

    def key_by_bit(self, bit_index: int) -> MetaKeyEntry:
        """Find a key entry by bit index. Raises KeyError if not found."""
        for k in self.keys:
            if k.bit_index == bit_index:
                return k
        raise KeyError(f"Bit index {bit_index} not in key map")

    # -- filtering --

    def rows_where(self, predicate: Callable[[MetaRow], bool]) -> list[MetaRow]:
        """Return rows matching a predicate.

        Example::

            meta.rows_where(lambda r: r.is_pressed("W", meta.keys))
        """
        return [r for r in self.rows if predicate(r)]

    def time_range(
        self, start_qpc: int, end_qpc: int
    ) -> list[MetaRow]:
        """Return rows with capture_qpc in [start_qpc, end_qpc]."""
        return [
            r for r in self.rows
            if start_qpc <= r.capture_qpc <= end_qpc
        ]

    # -- keyboard helpers --

    @staticmethod
    def mask_from_names(keys: list[MetaKeyEntry], names: list[str]) -> int:
        """Build a keyboard_mask from a list of key names.

        Useful for constructing synthetic MetaRows::

            mask = MetaFile.mask_from_names(meta.keys, ["W", "Space"])
        """
        name_set = set(names)
        mask = 0
        for k in keys:
            if k.name in name_set:
                mask |= (1 << k.bit_index)
        return mask

    # -- time helpers --

    def duration_sec(self, qpc_frequency: int) -> float:
        """Total session duration in seconds based on first/last capture_qpc."""
        if len(self.rows) < 2:
            return 0.0
        return (
            (self.rows[-1].capture_qpc - self.rows[0].capture_qpc)
            / qpc_frequency
        )

    # -- merging --

    @staticmethod
    def concat(*metas: MetaFile) -> MetaFile:
        """Merge multiple MetaFiles into one, renumbering record_frame_index.

        All inputs must have identical key tables.
        """
        if not metas:
            raise ValueError("No MetaFiles to concat")

        ref_keys = metas[0].keys
        for i, m in enumerate(metas[1:], 1):
            if m.keys != ref_keys:
                raise ValueError(
                    f"Key table mismatch: meta[0] has {len(ref_keys)} keys, "
                    f"meta[{i}] has {len(m.keys)} keys"
                )

        merged_rows: list[MetaRow] = []
        for m in metas:
            for row in m.rows:
                merged_rows.append(MetaRow(
                    frame_id=row.frame_id,
                    record_frame_index=len(merged_rows),
                    capture_qpc=row.capture_qpc,
                    host_accept_qpc=row.host_accept_qpc,
                    keyboard_mask=row.keyboard_mask,
                    width=row.width,
                    height=row.height,
                    analysis_stride=row.analysis_stride,
                    flags=row.flags,
                ))

        return MetaFile(
            header=MetaHeader(
                magic=ref_keys and metas[0].header.magic or b"RCMETA1\x00",
                version=1,
                created_unix_ns=metas[0].header.created_unix_ns,
                key_count=len(ref_keys),
            ),
            keys=ref_keys,
            rows=merged_rows,
        )
