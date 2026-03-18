"""Phase 5: Comprehensive lifecycle, error handling, and edge-case tests."""
import sys, os, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import Memoir


def test_double_release():
    """release() is safe to call multiple times."""
    engine = Memoir.CaptureEngine({"type": "monitor_index", "value": 0}, max_fps=5.0)
    engine.start()
    pkt = engine.get_next_frame(2000)
    assert pkt is not None
    pkt.release()
    pkt.release()  # no-op, must not crash
    engine.stop()
    print("PASS: double release")


def test_cpu_bgra_after_release():
    """Accessing cpu_bgra after release raises ValueError."""
    engine = Memoir.CaptureEngine({"type": "monitor_index", "value": 0}, max_fps=5.0)
    engine.start()
    pkt = engine.get_next_frame(2000)
    assert pkt is not None
    pkt.release()
    try:
        _ = pkt.cpu_bgra
        assert False, "Should have raised"
    except ValueError as e:
        assert "released" in str(e).lower()
    engine.stop()
    print("PASS: cpu_bgra after release")


def test_context_manager():
    """with packet: usage releases on exit."""
    engine = Memoir.CaptureEngine({"type": "monitor_index", "value": 0}, max_fps=5.0)
    engine.start()
    pkt = engine.get_next_frame(2000)
    assert pkt is not None
    with pkt:
        _ = pkt.cpu_bgra
    # After exiting with-block, packet should be released
    try:
        _ = pkt.cpu_bgra
        assert False, "Should have raised"
    except ValueError:
        pass
    engine.stop()
    print("PASS: context manager")


def test_stop_stops_recording():
    """stop() finalizes any active recording."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = os.path.join(tmpdir, "stop_test")
        engine = Memoir.CaptureEngine({"type": "monitor_index", "value": 0}, max_fps=10.0)
        engine.start()

        engine.start_recording(base)
        assert engine.is_recording()

        for i, pkt in enumerate(engine.frames()):
            pkt.release()
            if i >= 4:
                break

        engine.stop()  # should stop recording too
        assert not engine.is_recording()

        assert os.path.isfile(base + ".mp4")
        assert os.path.isfile(base + ".meta")
        print("PASS: stop stops recording")


def test_start_recording_while_recording():
    """start_recording while already recording raises."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base1 = os.path.join(tmpdir, "session1")
        base2 = os.path.join(tmpdir, "session2")
        engine = Memoir.CaptureEngine({"type": "monitor_index", "value": 0}, max_fps=10.0)
        engine.start()

        engine.start_recording(base1)
        try:
            engine.start_recording(base2)
            assert False, "Should have raised"
        except RuntimeError:
            pass

        engine.stop_recording()
        engine.stop()
        print("PASS: double start_recording raises")


def test_stop_recording_when_not_recording():
    """stop_recording when not recording is a no-op."""
    engine = Memoir.CaptureEngine({"type": "monitor_index", "value": 0}, max_fps=5.0)
    engine.start()
    engine.stop_recording()  # no-op, must not crash
    engine.stop()
    print("PASS: stop_recording no-op")


def test_get_next_frame_timeout():
    """get_next_frame with timeout returns None when no frame available."""
    engine = Memoir.CaptureEngine({"type": "monitor_index", "value": 0}, max_fps=0.5)
    engine.start()
    # Drain any pending frame first
    engine.get_next_frame(500)
    # Now request with very short timeout — likely no frame available
    pkt = engine.get_next_frame(0)
    # pkt might be None or a frame; just verify no crash
    if pkt:
        pkt.release()
    engine.stop()
    print("PASS: get_next_frame timeout")


def test_stats_counters():
    """Stats counters are populated correctly."""
    engine = Memoir.CaptureEngine(
        {"type": "monitor_index", "value": 0},
        max_fps=10.0, analysis_queue_capacity=1,
    )
    engine.start()

    for i, pkt in enumerate(engine.frames()):
        pkt.release()
        if i >= 9:
            break

    stats = engine.stats()
    assert stats["frames_accepted"] >= 10
    assert stats["frames_seen"] >= stats["frames_accepted"]
    assert stats["python_queue_depth"] == 0  # we consumed everything
    engine.stop()
    print("PASS: stats counters")


def test_get_last_error_initially_none():
    """get_last_error returns None when no error."""
    engine = Memoir.CaptureEngine({"type": "monitor_index", "value": 0})
    engine.start()
    assert engine.get_last_error() is None
    engine.stop()
    print("PASS: get_last_error initially None")


if __name__ == "__main__":
    test_double_release()
    test_cpu_bgra_after_release()
    test_context_manager()
    test_stop_stops_recording()
    test_start_recording_while_recording()
    test_stop_recording_when_not_recording()
    test_get_next_frame_timeout()
    test_stats_counters()
    test_get_last_error_initially_none()
    print("\nAll Phase 5 tests passed!")
