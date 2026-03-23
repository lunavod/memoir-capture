import subprocess
import sys
import time

import pytest

from memoir_capture import CaptureEngine, WindowTitleTarget

pytestmark = pytest.mark.capture

UNIQUE_TITLE = "MemoirTestWindow_39f7a2"

# A tiny tkinter script that creates a visible window and waits to be killed.
_WINDOW_SCRIPT = f"""\
import tkinter as tk
root = tk.Tk()
root.title("{UNIQUE_TITLE}")
root.geometry("400x300")
root.mainloop()
"""


def test_get_none_and_error_after_window_closes():
    """Closing the captured window should make get_next_frame return None
    and get_last_error report the closure."""
    proc = subprocess.Popen(
        [sys.executable, "-c", _WINDOW_SCRIPT],
    )
    time.sleep(1)  # let the window fully appear

    engine = CaptureEngine(
        WindowTitleTarget(UNIQUE_TITLE),
        max_fps=30.0,
    )
    engine.start()

    # Make sure capture is running before we kill the window
    pkt = engine.get_next_frame(timeout_ms=5000)
    assert pkt is not None, "failed to capture at least one frame"
    pkt.release()

    # Kill the process — destroys the window
    proc.kill()
    proc.wait(timeout=5)

    # After the target is destroyed, get_next_frame should return None
    frame = engine.get_next_frame(timeout_ms=3000)
    assert frame is None, "expected None after target window closed"

    err = engine.get_last_error()
    assert err is not None, "expected an error after target window closed"
    assert "closed" in err.lower(), f"unexpected error message: {err}"

    engine.stop()
