"""Verify that the FramePool is recreated when the captured window's
ContentSize changes.

Regression test for the bug where a target window that was tiny at the
moment ``CaptureEngine.start()`` was called (e.g. Overwatch's
launch/restore splash reporting 160x28) caused WGC to clamp every
subsequent frame to that initial pool size — even after the window
grew to its real resolution.

The capture engine now reads ``frame.ContentSize()`` on every
FrameArrived and calls ``framePool.Recreate(...)`` on mismatch.
"""

import subprocess
import sys
import time

import pytest

from memoir_capture import CaptureEngine, WindowTitleTarget

pytestmark = pytest.mark.capture

UNIQUE_TITLE = "MemoirResizeTest_4b8e1c"

# A tkinter window that starts small and then resizes itself larger after
# ~2 seconds. A normal-bordered window is used so tkinter's geometry()
# reliably calls SetWindowPos.
_WINDOW_SCRIPT = f"""\
import sys
import tkinter as tk

SMALL_W, SMALL_H = 320, 160
LARGE_W, LARGE_H = 1280, 720

root = tk.Tk()
root.title("{UNIQUE_TITLE}")
root.geometry(f"{{SMALL_W}}x{{SMALL_H}}+200+200")
root.configure(bg="red")

def grow():
    root.geometry(f"{{LARGE_W}}x{{LARGE_H}}+0+0")
    root.configure(bg="green")
    root.update_idletasks()
    print(f"GROWN to {{root.winfo_width()}}x{{root.winfo_height()}}", flush=True)

# Repaint constantly so WGC keeps emitting FrameArrived events.
_colors = ["red", "orange", "yellow", "green", "blue", "purple"]
_idx = [0]
def repaint():
    _idx[0] = (_idx[0] + 1) % len(_colors)
    root.configure(bg=_colors[_idx[0]])
    root.after(50, repaint)

root.after(2000, grow)
root.after(50, repaint)
root.mainloop()
"""


def _drain_until(engine, predicate, timeout_s):
    """Pull frames until ``predicate(packet)`` is True or we time out.

    Returns the matching packet (caller releases) or None.
    """
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        pkt = engine.get_next_frame(timeout_ms=200)
        if pkt is None:
            continue
        if predicate(pkt):
            return pkt
        pkt.release()
    return None


def test_pool_recreates_on_window_growth():
    proc = subprocess.Popen([sys.executable, "-c", _WINDOW_SCRIPT])
    try:
        # Let the small window appear before we start capture, so the
        # FramePool is initialized at the small size.
        time.sleep(1.0)

        engine = CaptureEngine(
            WindowTitleTarget(UNIQUE_TITLE),
            max_fps=30.0,
        )
        engine.start()
        try:
            # First frame should reflect the small initial window.
            small_pkt = engine.get_next_frame(timeout_ms=5000)
            assert small_pkt is not None, "failed to capture initial frame"
            try:
                assert small_pkt.width < 600, (
                    f"expected small initial width, got {small_pkt.width}"
                )
                assert small_pkt.height < 400, (
                    f"expected small initial height, got {small_pkt.height}"
                )
            finally:
                small_pkt.release()

            # After ~2s the tkinter window grows to 1280x720. Wait for a
            # frame whose dims reflect the new size — that's only possible
            # if the FramePool was recreated.
            large_pkt = _drain_until(
                engine,
                lambda p: p.width >= 1200 and p.height >= 700,
                timeout_s=6.0,
            )
            assert large_pkt is not None, (
                "FramePool was not recreated after window grew — "
                "frames stayed clamped to the initial small pool size"
            )
            try:
                assert large_pkt.width >= 1200
                assert large_pkt.height >= 700
            finally:
                large_pkt.release()
        finally:
            engine.stop()
    finally:
        proc.kill()
        proc.wait(timeout=5)
