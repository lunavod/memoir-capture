import os
import pytest
from memoir_capture import CaptureEngine, MonitorTarget

pytestmark = pytest.mark.capture


def _warm_up(engine, n=2):
    for i, pkt in enumerate(engine.frames()):
        pkt.release()
        if i >= n:
            break


def _record_frames(engine, n=5):
    for i, pkt in enumerate(engine.frames()):
        pkt.release()
        if i >= n - 1:
            break


# ---- split path recording ----


def test_split_recording_creates_files(tmp_path):
    rec_dir = tmp_path / "session"
    rec_dir.mkdir()

    engine = CaptureEngine(MonitorTarget(0), max_fps=10.0)
    engine.start()
    _warm_up(engine)

    info = engine.start_recording(
        path=str(rec_dir), video_name="data", meta_name="keys",
    )
    assert info.video_path == str(rec_dir / "data.mp4")
    assert info.meta_path == str(rec_dir / "keys.meta")

    _record_frames(engine)
    engine.stop_recording()
    engine.stop()

    assert os.path.isfile(rec_dir / "data.mp4")
    assert os.path.isfile(rec_dir / "keys.meta")
    assert os.path.getsize(rec_dir / "data.mp4") > 0
    assert os.path.getsize(rec_dir / "keys.meta") > 0


def test_split_recording_strips_mp4_extension(tmp_path):
    rec_dir = tmp_path / "strip_mp4"
    rec_dir.mkdir()

    engine = CaptureEngine(MonitorTarget(0), max_fps=10.0)
    engine.start()
    _warm_up(engine)

    info = engine.start_recording(
        path=str(rec_dir), video_name="data.mp4", meta_name="keys",
    )
    assert info.video_path == str(rec_dir / "data.mp4")
    assert "data.mp4.mp4" not in info.video_path

    _record_frames(engine)
    engine.stop()


def test_split_recording_strips_meta_extension(tmp_path):
    rec_dir = tmp_path / "strip_meta"
    rec_dir.mkdir()

    engine = CaptureEngine(MonitorTarget(0), max_fps=10.0)
    engine.start()
    _warm_up(engine)

    info = engine.start_recording(
        path=str(rec_dir), video_name="data", meta_name="keys.meta",
    )
    assert info.meta_path == str(rec_dir / "keys.meta")
    assert "keys.meta.meta" not in info.meta_path

    _record_frames(engine)
    engine.stop()


def test_split_recording_strips_both_extensions(tmp_path):
    rec_dir = tmp_path / "strip_both"
    rec_dir.mkdir()

    engine = CaptureEngine(MonitorTarget(0), max_fps=10.0)
    engine.start()
    _warm_up(engine)

    info = engine.start_recording(
        path=str(rec_dir), video_name="data.mp4", meta_name="keys.meta",
    )
    assert info.video_path == str(rec_dir / "data.mp4")
    assert info.meta_path == str(rec_dir / "keys.meta")

    _record_frames(engine)
    engine.stop()


# ---- error cases (no engine needed) ----


def test_both_base_path_and_path_raises():
    engine = CaptureEngine(MonitorTarget(0), max_fps=5.0)
    engine.start()
    with pytest.raises(TypeError, match="Cannot specify both"):
        engine.start_recording("some/path", path="other/path",
                               video_name="v", meta_name="m")
    engine.stop()


def test_path_without_video_name_raises():
    engine = CaptureEngine(MonitorTarget(0), max_fps=5.0)
    engine.start()
    with pytest.raises(TypeError, match="video_name= and meta_name= are required"):
        engine.start_recording(path="some/path", meta_name="m")
    engine.stop()


def test_path_without_meta_name_raises():
    engine = CaptureEngine(MonitorTarget(0), max_fps=5.0)
    engine.start()
    with pytest.raises(TypeError, match="video_name= and meta_name= are required"):
        engine.start_recording(path="some/path", video_name="v")
    engine.stop()


def test_no_args_raises():
    engine = CaptureEngine(MonitorTarget(0), max_fps=5.0)
    engine.start()
    with pytest.raises(TypeError, match="requires either"):
        engine.start_recording()
    engine.stop()


def test_video_name_with_base_path_raises():
    engine = CaptureEngine(MonitorTarget(0), max_fps=5.0)
    engine.start()
    with pytest.raises(TypeError, match="require path="):
        engine.start_recording("some/path", video_name="v", meta_name="m")
    engine.stop()


# ---- original calling convention still works ----


def test_base_path_still_works(tmp_path):
    base = str(tmp_path / "classic")

    engine = CaptureEngine(MonitorTarget(0), max_fps=10.0)
    engine.start()
    _warm_up(engine)

    info = engine.start_recording(base)
    assert info.video_path == base + ".mp4"
    assert info.meta_path == base + ".meta"

    _record_frames(engine)
    engine.stop()

    assert os.path.isfile(base + ".mp4")
    assert os.path.isfile(base + ".meta")
