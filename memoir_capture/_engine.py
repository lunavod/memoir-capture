"""Typed Python wrapper around the native CaptureEngine."""

from __future__ import annotations

import os
import threading
from typing import Callable, Iterator

import numpy as np

from memoir_capture import _native
from memoir_capture._types import (
    CaptureTarget,
    EngineStats,
    MetaKeyEntry,
    MonitorTarget,
    RecordingInfo,
    WindowExeTarget,
    WindowTitleTarget,
)

# Re-export FramePacket directly — it's a pybind11 class with proper
# attribute access and context manager support already.
FramePacket = _native.FramePacket


def _target_to_dict(target: CaptureTarget) -> dict:
    if isinstance(target, MonitorTarget):
        return {"type": "monitor_index", "value": target.index}
    elif isinstance(target, WindowTitleTarget):
        return {"type": "window_title", "value": target.pattern}
    elif isinstance(target, WindowExeTarget):
        return {"type": "window_exe", "value": target.pattern}
    else:
        raise TypeError(f"Unknown target type: {type(target)}")


class CaptureEngine:
    """Memoir capture engine with optional recording.

    Args:
        target: What to capture — a MonitorTarget, WindowTitleTarget,
            or WindowExeTarget.
        max_fps: Maximum accepted frame rate.
        analysis_queue_capacity: Bounded queue size for Python delivery.
        capture_cursor: Include the cursor in captured frames.
        key_map: List of keys to track in the keyboard bitmask. Each entry
            is a MetaKeyEntry(bit_index, virtual_key, name). If None, uses
            the default 40-key gaming set (WASD, arrows, modifiers, numbers,
            F1-F5, etc.).
        record_width: Recording output width in pixels.
        record_height: Recording output height in pixels.
        record_gop: GOP size for recording (1 = all-intra).
    """

    def __init__(
        self,
        target: CaptureTarget,
        *,
        max_fps: float = 10.0,
        analysis_queue_capacity: int = 1,
        capture_cursor: bool = False,
        key_map: list[MetaKeyEntry] | None = None,
        record_width: int = 1920,
        record_height: int = 1080,
        record_gop: int = 1,
    ) -> None:
        # Convert MetaKeyEntry list to tuples for the C++ side
        native_key_map = None
        if key_map is not None:
            native_key_map = [
                (k.bit_index, k.virtual_key, k.name) for k in key_map
            ]

        self._engine = _native.CaptureEngine(
            _target_to_dict(target),
            max_fps=max_fps,
            analysis_queue_capacity=analysis_queue_capacity,
            key_map=native_key_map,
            capture_cursor=capture_cursor,
            record_width=record_width,
            record_height=record_height,
            record_gop=record_gop,
        )

    # -- context manager --

    def __enter__(self) -> CaptureEngine:
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()

    # -- lifecycle --

    def start(self) -> None:
        """Start capturing frames."""
        self._engine.start()

    def stop(self) -> None:
        """Stop capture and any active recording."""
        self._engine.stop()

    def close(self) -> None:
        """Alias for stop()."""
        self._engine.stop()

    # -- frame delivery --

    def get_next_frame(self, timeout_ms: int = -1) -> FramePacket | None:
        """Return the next accepted frame, or None on timeout.

        Args:
            timeout_ms: -1 = block forever, 0 = poll, >0 = wait up to N ms.
        """
        return self._engine.get_next_frame(timeout_ms)

    def frames(self) -> Iterator[FramePacket]:
        """Yield accepted frames until the engine stops."""
        return self._engine.frames()

    # -- recording --

    def start_recording(self, base_path: str | os.PathLike) -> RecordingInfo:
        """Start recording accepted frames to ``base_path.mp4`` + ``.meta``.

        Raises RuntimeError if already recording.
        """
        d = self._engine.start_recording(str(base_path))
        return RecordingInfo(**d)

    def stop_recording(self) -> None:
        """Stop the current recording session. No-op if not recording."""
        self._engine.stop_recording()

    def is_recording(self) -> bool:
        """Return whether a recording session is active."""
        return self._engine.is_recording()

    # -- diagnostics --

    def stats(self) -> EngineStats:
        """Return live engine counters."""
        d = self._engine.stats()
        return EngineStats(**d)

    def get_last_error(self) -> str | None:
        """Return the last non-fatal error message, or None."""
        return self._engine.get_last_error()

    def submit_analysis_result(
        self,
        frame_id: int,
        flags: int = 0,
        payload: bytes | None = None,
    ) -> None:
        """Submit an analysis result for a frame (stub in v1)."""
        self._engine.submit_analysis_result(frame_id, flags, payload)

    # -- callback-style frame delivery --

    def on_frame(
        self, callback: Callable[[FramePacket], None]
    ) -> threading.Thread:
        """Run *callback* for each frame in a daemon thread.

        The callback receives a FramePacket that is automatically released
        after the callback returns. The thread stops when the engine stops.

        Returns the thread object (useful for joining).

        Example::

            engine.start()
            engine.on_frame(lambda pkt: print(pkt.frame_id))
        """
        def _worker() -> None:
            for pkt in self._engine.frames():
                try:
                    callback(pkt)
                finally:
                    pkt.release()

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        return t


# ---------------------------------------------------------------------------
# Convenience: grab a single frame
# ---------------------------------------------------------------------------

def grab(
    target: CaptureTarget,
    *,
    timeout_ms: int = 5000,
    max_fps: float = 60.0,
) -> np.ndarray:
    """Capture a single frame and return it as a numpy array.

    Creates a temporary engine, captures one frame, stops, and returns
    the BGRA pixel data as a ``(H, W, 4)`` uint8 array.

    Example::

        img = memoir_capture.grab(MonitorTarget(0))
    """
    engine = CaptureEngine(target, max_fps=max_fps)
    engine.start()
    try:
        pkt = engine.get_next_frame(timeout_ms)
        if pkt is None:
            raise RuntimeError("No frame captured within timeout")
        with pkt:
            return pkt.cpu_bgra.copy()
    finally:
        engine.stop()


# ---------------------------------------------------------------------------
# FramePacket extensions (monkey-patched onto the pybind11 class)
# ---------------------------------------------------------------------------

def _frame_repr(self: FramePacket) -> str:
    return (
        f"<FramePacket #{self.frame_id} "
        f"{self.width}x{self.height} "
        f"keys=0x{self.keyboard_mask:04x}>"
    )


def _frame_save_png(self: FramePacket, path: str | os.PathLike) -> None:
    """Save frame as a PNG file. Requires opencv-python.

    Example::

        packet.save_png("debug_frame.png")
    """
    try:
        import cv2
    except ImportError:
        raise ImportError(
            "save_png requires opencv-python: "
            "pip install memoir-capture[cv]"
        ) from None
    cv2.imwrite(str(path), self.cpu_bgra[:, :, :3])


FramePacket.__repr__ = _frame_repr  # type: ignore[attr-defined]
FramePacket.save_png = _frame_save_png  # type: ignore[attr-defined]
