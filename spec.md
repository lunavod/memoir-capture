# Memoir Native Capture/Replay Module Specification

## 1. Overview

### 1.1 What this is

**Memoir** is a native Windows capture module with Python bindings for real-time computer-vision pipelines.

Its job is to sit between a live visual source such as a game window and a Python analysis pipeline, and provide:

- continuous capture of frames from a chosen window or monitor
- CPU-readable accepted frames for Python analysis
- optional GPU-side recording of those same accepted frames
- exact per-frame input metadata, especially keyboard state
- deterministic replay data for debugging and verification

It is specifically meant for systems where Python is doing frame analysis in real time, but where replay accuracy matters enough that “video plus a loose input log” is not good enough.

### 1.2 Why it exists

The target use case is a system like this:

- a Python daemon captures gameplay frames
- Python analyzes those frames for things like scoreboard extraction, OCR, subtitle parsing, state tracking, or event detection
- the developer wants to later replay the exact analyzed frames together with the exact keyboard state that was present when those frames were processed
- the replay must be deterministic and frame-accurate

A naive design often ends up doing at least one of these:

- CPU-only frame transport everywhere
- storing raw or lightly compressed images in a custom blob file
- recording keyboard events separately and reconstructing state later
- letting recording and analysis drift apart by a frame or two

Memoir exists to avoid that.

### 1.3 Core idea

Memoir treats an **accepted frame** as the authoritative unit.

For every accepted frame, the engine can provide:

- one unique `frame_id`
- one captured source image
- one keyboard snapshot
- one metadata record
- optionally one encoded video frame in a replay recording

If a frame is not accepted, it does not become part of replay.

That means replay data is built from a strict 1:1 relationship:

- 1 accepted frame
- 1 frame ID
- 1 keyboard state snapshot
- 1 metadata row
- 1 recorded frame, if recording is enabled

### 1.4 Design goals

The module should:

- keep capture running continuously
- expose CPU-readable frames to Python in a simple way
- keep the record path GPU-native
- avoid GPU -> CPU -> GPU roundtrips in the recording path
- allow Python to start and stop recording dynamically
- keep replay deterministic even if Python analysis is slow
- keep the Python-facing API simple and boring

### 1.5 Non-goals for v1

The first version is **not** trying to be:

- a full multimedia framework
- a general-purpose desktop recorder
- a generic streaming solution
- a cross-platform library
- a Python-first graphics API

It is a focused Windows native component for deterministic capture + replay support.

---

## 2. Problem Statement

The source pipeline is assumed to have these properties:

- capture resolution may be 4K for best OCR / visual analysis quality
- Python analysis may take variable time per frame
- the developer wants a lower-resolution recording, such as 1080p, for replay/debugging
- keyboard state must be exactly aligned to the accepted frame
- recording should not require reconfiguring or recreating the engine

The main challenge is that analysis and recording want different memory domains:

- analysis usually wants **CPU-readable pixels**
- recording wants **GPU-resident frames**

Memoir must branch the same accepted frame into two paths:

1. **GPU -> CPU** for Python analysis
2. **GPU -> GPU** for resize/encode/recording

without making recording depend on a CPU roundtrip.

---

## 3. High-Level Architecture

### 3.1 Capture source

Capture uses **Windows.Graphics.Capture** on Windows.

The captured frame arrives as a GPU-resident D3D11 surface.

### 3.2 Two output paths from the same accepted frame

For each accepted frame, the engine may do both:

- **Analysis path**
  - GPU frame is copied to a CPU-readable staging/resource path
  - frame is exposed to Python as BGRA8 data

- **Recording path**
  - GPU frame remains on GPU
  - it may be resized on GPU
  - it is passed to NVENC for video encoding
  - no CPU roundtrip is required for recording

### 3.3 Dynamic recording

Capture is always active while the engine is running.

Recording is optional and dynamic:

- `engine.start_recording(base_path)`
- `engine.stop_recording()`

Python does not need to recreate the engine to toggle recording.

### 3.4 Acceptance model

The engine does **not** promise to keep every captured frame.

Instead, it defines a smaller sequence of **accepted frames**.

Only accepted frames:

- receive a `frame_id`
- receive a keyboard snapshot
- are delivered to Python
- are eligible for recording

This is intentional and is the basis for deterministic replay.

---

## 4. Key Concepts

### 4.1 Captured frame

A captured frame is a frame delivered by Windows.Graphics.Capture.

It exists only inside the native pipeline until the engine decides whether to accept or drop it.

### 4.2 Accepted frame

An accepted frame is a captured frame that the engine has chosen to admit into the pipeline.

Acceptance means:

- assign `frame_id`
- snapshot keyboard state immediately
- schedule CPU readback
- schedule recording work if recording is active
- eventually deliver the frame packet to Python

### 4.3 Dropped frame

A dropped frame is a captured frame that is not admitted into the accepted-frame sequence.

Dropped frames:

- do not get a `frame_id`
- do not get keyboard metadata
- do not appear in replay
- do not get encoded

### 4.4 Frame packet

A frame packet is the Python-visible representation of an accepted frame.

It contains:

- `frame_id`
- timestamps
- keyboard state
- dimensions / stride
- CPU-readable pixel data

### 4.5 Recording session

A recording session is a bounded interval during which accepted frames are also encoded and written to disk.

A session begins when Python calls `start_recording()` and ends when Python calls `stop_recording()`.

---

## 5. Functional Requirements

### 5.1 Engine lifecycle

The engine shall support:

- creation
- start
- stop
- destruction

Capture shall only happen while the engine is running.

### 5.2 Continuous capture

Once started, the engine shall continuously capture frames from the configured target until stopped or faulted.

### 5.3 Accepted-frame queue

The engine shall maintain a bounded queue of accepted frames waiting to be consumed by Python.

For v1, the default queue capacity shall be 1.

### 5.4 Drop policy

If a captured frame arrives while the accepted-frame queue is full, the default v1 policy shall be:

- **drop the new captured frame**

The already-queued accepted frame shall remain intact.

### 5.5 Frame ID generation

The engine shall assign a unique monotonic `frame_id` to each accepted frame.

Frames that are dropped shall not consume IDs.

### 5.6 Keyboard snapshot timing

For every accepted frame, keyboard state shall be captured immediately at acceptance time.

It shall **not** be deferred until Python starts processing the frame.

### 5.7 Python frame delivery

Accepted frames shall be exposed to Python through a pull-based API.

The engine shall provide a blocking or timed wait operation to retrieve the next accepted frame packet.

### 5.8 Recording

The engine shall support dynamic start/stop of recording while capture remains active.

When recording is active, each accepted frame shall also be recorded.

When recording is inactive, accepted frames shall still be delivered to Python, but no recording outputs shall be written.

### 5.9 Metadata writing

When recording is active, the engine shall write metadata records in frame order for each recorded accepted frame.

### 5.10 Statistics

The engine shall expose live counters and state useful for debugging and profiling.

---

## 6. Non-Functional Requirements

### 6.1 Determinism

Replay data shall be deterministic with respect to the accepted-frame sequence.

For a given recorded session, frame `N` in the replay video must correspond to metadata row `N` and to the original accepted frame with its associated keyboard state.

### 6.2 Performance

The recording path shall avoid unnecessary CPU involvement.

The module shall keep the recording path GPU-native:

- capture on GPU
- optional resize/convert on GPU
- encode on GPU

### 6.3 Simplicity of Python API

Python should interact with the engine at a high level.

Python shall not manage:

- GPU textures
- D3D11 surfaces
- encoder input surfaces
- capture callbacks

### 6.4 Isolation of failures

A recording failure should, when possible, stop only the recording session and not kill capture.

### 6.5 Safe buffer lifetime

The module shall ensure CPU pixel buffers remain valid while a frame packet is owned by Python.

---

## 7. Runtime Model

### 7.1 Typical live flow

1. Engine is started
2. Capture continuously produces frames
3. For each captured frame:
   - if queue is full, drop the frame
   - otherwise accept it
4. On acceptance:
   - assign `frame_id`
   - read capture timestamp
   - snapshot keyboard state
   - schedule CPU readback
   - if recording is active, schedule encode
5. Python retrieves the accepted frame packet
6. Python analyzes the frame
7. Python releases the packet buffer

### 7.2 Typical recording flow

1. Engine is already running
2. Python calls `start_recording("path/base_name")`
3. Engine creates session outputs
4. Each accepted frame is:
   - encoded to video
   - written to metadata
5. Python later calls `stop_recording()`
6. Engine flushes encoder and finalizes outputs
7. Capture continues normally

---

## 8. State Machines

### 8.1 Engine states

The engine shall have the following states:

- `Created`
- `Running`
- `Stopping`
- `Stopped`
- `Faulted`

Transitions:

- `Created -> Running`
- `Running -> Stopping`
- `Stopping -> Stopped`
- any state may transition to `Faulted` on unrecoverable failure

### 8.2 Recording states

Recording is logically separate from engine state.

Recording states:

- `Inactive`
- `Starting`
- `Active`
- `Stopping`
- `Failed`

Valid transitions:

- `Inactive -> Starting -> Active`
- `Active -> Stopping -> Inactive`
- `Starting -> Failed`
- `Active -> Failed`

A recording failure should ideally result in `Failed -> Inactive` after cleanup, while the engine remains `Running`.

---

## 9. Threads and Concurrency

### 9.1 Capture thread

Responsibilities:

- receive frames from WGC
- decide accept vs drop
- assign `frame_id`
- snapshot keyboard state
- submit work to downstream queues

### 9.2 Readback / packet-preparation thread

Responsibilities:

- perform or finalize GPU -> CPU transfer
- prepare packet buffer
- enqueue packet for Python consumption

This can be merged with the capture thread if that is simpler and still performant.

### 9.3 Recording thread

Responsibilities:

- consume accepted frames when recording is active
- perform GPU resize / color conversion as needed
- submit frames to NVENC
- write video stream
- write metadata rows

### 9.4 Python consumer thread

Python retrieves accepted frames via `get_next_frame()` or iteration.

The engine shall assume Python may be slower than capture and shall handle backpressure through its queue/drop policy.

---

## 10. Invariants

The implementation shall preserve these invariants:

1. Every accepted frame has exactly one unique `frame_id`
2. A dropped frame has no `frame_id`
3. Every accepted frame has exactly one keyboard snapshot
4. If a frame is delivered to Python, it is an accepted frame
5. If a frame is recorded, it is an accepted frame
6. Recorded frame order matches metadata order
7. Recording start/stop does not require restarting capture
8. Stopping recording does not stop capture
9. Buffer memory exposed to Python remains valid until release

---

## 11. Data Model

### 11.1 EngineConfig

Suggested native config structure:

```cpp
struct EngineConfig {
    CaptureTarget target;
    double max_fps = 10.0;
    uint32_t analysis_queue_capacity = 1;
    AnalysisPixelFormat analysis_format = AnalysisPixelFormat::BGRA8;
    DropPolicy drop_policy = DropPolicy::DropNew;
    bool capture_cursor = false;

    uint32_t record_width = 1920;
    uint32_t record_height = 1080;
    RecordCodec record_codec = RecordCodec::HEVC;

    std::vector<KeySpec> key_map;
};
```

### 11.2 CaptureTarget

Suggested union-like target model:

```cpp
enum class CaptureTargetType {
    WindowTitleRegex,
    WindowExeRegex,
    MonitorIndex
};

struct CaptureTarget {
    CaptureTargetType type;
    std::wstring value_wstr;
    int32_t monitor_index = -1;
};
```

### 11.3 Frame packet data

Suggested native representation:

```cpp
struct FramePacketData {
    uint64_t frame_id;
    int64_t capture_qpc;
    int64_t host_accept_qpc;
    uint64_t keyboard_mask;

    uint32_t width;
    uint32_t height;
    uint32_t stride;
    uint32_t channels; // always 4 in v1

    uint8_t* data;
};
```

### 11.4 Engine statistics

Suggested structure:

```cpp
struct EngineStats {
    uint64_t frames_seen;
    uint64_t frames_accepted;
    uint64_t frames_dropped_queue_full;
    uint64_t frames_dropped_internal_error;
    uint64_t frames_recorded;

    uint32_t python_queue_depth;
    bool recording_active;
};
```

---

## 12. Frame ID Semantics

### 12.1 Definition

`frame_id` is a global monotonic counter for the lifetime of the engine.

It increments once per accepted frame.

### 12.2 Why global IDs

Global IDs make it easier to correlate:

- analysis logs
- performance diagnostics
- replay metadata
- live errors

across multiple recording sessions.

### 12.3 Recording-local frame index

Each recording session shall also maintain a local sequential index:

- `record_frame_index`
- starts at 0 when recording starts
- increments for each recorded accepted frame

This is useful for replay files where physical frame order matters.

---

## 13. Timestamps

### 13.1 `capture_qpc`

The capture timestamp from WGC for the accepted frame.

This is the closest thing to the actual source-frame capture/compositor time.

### 13.2 `host_accept_qpc`

A host-side timestamp captured at the moment the engine accepts the frame.

This is useful for latency diagnostics and debugging.

### 13.3 Optional future timestamps

The implementation may later add:

- CPU readback completion time
- packet enqueue time
- Python dequeue time
- encode submission time

but these are not required for v1.

---

## 14. Keyboard State

### 14.1 Representation

Keyboard state shall be stored as a packed bitmask.

The mapping from bit position to key shall be fixed for the engine instance and persisted in recording metadata.

### 14.2 Default key set

A reasonable default key set for game debugging might include:

- movement keys
- modifiers
- common action keys
- number keys
- tab / escape

The exact default set is implementation-defined, but must be stable and discoverable.

### 14.3 Snapshot timing

The snapshot must happen when the frame is accepted, not later.

This is a hard requirement.

---

## 15. Recording Output

### 15.1 Session outputs

`start_recording(base_path)` shall create a pair of outputs:

- `base_path` + video extension
- `base_path` + metadata extension

Recommended v1 defaults:

- video: `.mp4`
- metadata: `.meta`

Example:

- `session_001.mp4`
- `session_001.meta`

### 15.2 Video requirements

Video shall contain only accepted frames from the interval where recording was active.

The record path shall stay GPU-native.

### 15.3 Codec defaults

Recommended v1 defaults:

- HEVC NVENC
- no B-frames
- all-intra or equivalent short-GOP debug-friendly settings

The exact muxer/container may be implementation-defined as long as the output is playable and stable.

---

## 16. Metadata File Format

### 16.1 Overview

Metadata shall be written in frame order and must be sufficient to pair each recorded frame with its original accepted-frame identity and input state.

### 16.2 File header

Suggested v1 header:

```cpp
#pragma pack(push, 1)
struct ReplayMetaFileHeaderV1 {
    char     magic[8];           // "RCMETA1\0"
    uint32_t version;            // 1
    uint32_t reserved0;
    uint64_t created_unix_ns;
    uint32_t key_count;
    uint32_t reserved1;
};
#pragma pack(pop)
```

After the header, write the key map table.

### 16.3 Key map table

Each key entry should contain enough information to reconstruct the keyboard bit layout.

Suggested entry:

```cpp
#pragma pack(push, 1)
struct ReplayMetaKeyEntryV1 {
    uint32_t bit_index;
    uint32_t virtual_key;
    char     name[32];
};
#pragma pack(pop)
```

### 16.4 Per-frame metadata record

Suggested v1 record:

```cpp
#pragma pack(push, 1)
struct ReplayMetaV1 {
    uint64_t frame_id;             // global engine frame id
    uint64_t record_frame_index;   // 0-based within this recording session
    int64_t  capture_qpc;          // source capture/compositor time
    int64_t  host_accept_qpc;      // engine acceptance time
    uint64_t keyboard_mask;        // packed key states
    uint32_t width;                // source width
    uint32_t height;               // source height
    uint32_t analysis_stride;      // CPU stride
    uint32_t flags;                // reserved
};
#pragma pack(pop)
```

### 16.5 Ordering guarantee

Metadata rows must be written in the same order as encoded replay frames.

---

## 17. Buffer Ownership Model

### 17.1 Requirement

Python must receive CPU-readable frame buffers that remain valid while Python owns the packet.

### 17.2 Recommended model

Use a bounded pool/ring of native buffer slots.

A `FramePacket` object keeps a reference to its underlying slot.

The slot is returned to the pool only when the packet is released.

### 17.3 Python release

Python shall explicitly release packets when done.

Repeated release should be safe and treated as a no-op.

### 17.4 Context-manager convenience

Bindings should also support context-manager usage so that Python can do:

```python
with engine.get_next_frame() as packet:
    analyze(packet.cpu_bgra)
```

---

## 18. Python Binding API

## 18.1 Design philosophy

The Python API should expose:

- accepted CPU-visible frames
- simple engine lifecycle
- dynamic recording control
- stats and basic errors

It should **not** expose:

- raw D3D textures
- raw WGC frames
- encoder sessions
- “encode this frame” style control
- callback-heavy GPU plumbing

### 18.2 Module name

Suggested Python module name:

- `Memoir`

### 18.3 CaptureEngine constructor

Suggested Python API:

```python
engine = Memoir.CaptureEngine(
    target,
    max_fps=10.0,
    analysis_queue_capacity=1,
    analysis_format="bgra",
    key_map=None,
    drop_policy="drop_new",
    capture_cursor=False,
    record_width=1920,
    record_height=1080,
    record_codec="hevc",
)
```

#### Parameters

- `target`
  - dict-like descriptor of what to capture
- `max_fps`
  - target maximum accepted capture rate
- `analysis_queue_capacity`
  - number of accepted frames that may wait for Python
- `analysis_format`
  - `"bgra"` only in v1
- `key_map`
  - optional list of keys to track
- `drop_policy`
  - `"drop_new"` only in v1
- `capture_cursor`
  - whether to include cursor in capture
- `record_width`, `record_height`
  - default encode resolution when recording
- `record_codec`
  - `"hevc"` only in v1

### 18.4 Target descriptors

Examples:

```python
{"type": "window_title", "value": "(?i)overwatch"}
{"type": "window_exe", "value": "(?i)overwatch.exe"}
{"type": "monitor_index", "value": 0}
```

### 18.5 CaptureEngine methods

#### `start() -> None`

Starts capture.

#### `stop() -> None`

Stops capture and any active recording.

#### `close() -> None`

Alias for `stop()`.

#### `get_next_frame(timeout_ms: int = -1) -> FramePacket | None`

Returns the next accepted frame packet.

Rules:

- negative timeout: block indefinitely
- zero timeout: poll, non-blocking
- positive timeout: wait up to timeout

Returns `None` if no frame becomes available before timeout.

#### `frames() -> iterator[FramePacket]`

Convenience iterator yielding accepted frames until engine stops.

#### `start_recording(base_path: str) -> RecordingInfo`

Starts a recording session.

Behavior:

- creates new video and metadata outputs derived from `base_path`
- fails if recording is already active

#### `stop_recording() -> None`

Stops current recording session.

Preferred v1 behavior if no recording is active:

- no-op

#### `is_recording() -> bool`

Returns whether recording is active.

#### `stats() -> dict`

Returns engine counters and state.

Suggested fields:

- `frames_seen`
- `frames_accepted`
- `frames_dropped_queue_full`
- `frames_dropped_internal_error`
- `frames_recorded`
- `python_queue_depth`
- `recording_active`

#### `get_last_error() -> str | None`

Returns last non-fatal error text if any.

#### `submit_analysis_result(frame_id: int, flags: int = 0, payload: bytes | None = None) -> None`

Optional hook for later integration.

May be a stub in v1.

### 18.6 FramePacket properties

Suggested Python-visible properties:

- `frame_id: int`
- `capture_qpc: int`
- `host_accept_qpc: int`
- `keyboard_mask: int`
- `width: int`
- `height: int`
- `stride: int`
- `channels: int`
- `cpu_bgra: numpy.ndarray`

The NumPy array shall be shape `(height, width, 4)` and type `uint8`.

### 18.7 FramePacket methods

#### `release() -> None`

Releases the underlying native buffer slot.

After release, accessing the packet pixel buffer is invalid.

Repeated release should be safe.

#### Context manager support

`FramePacket` should support `with` usage.

### 18.8 RecordingInfo properties

Suggested:

- `base_path: str`
- `video_path: str`
- `meta_path: str`
- `codec: str`
- `width: int`
- `height: int`

---

## 19. Native C++ API Boundary

A reasonable internal C++ API might look like this:

```cpp
class CaptureEngine {
public:
    explicit CaptureEngine(const EngineConfig& cfg);
    ~CaptureEngine();

    void Start();
    void Stop();

    std::shared_ptr<FramePacket> GetNextFrame(int timeout_ms);

    RecordingInfo StartRecording(const std::wstring& base_path);
    void StopRecording();
    bool IsRecording() const;

    EngineStats GetStats() const;
    std::optional<std::string> GetLastError() const;

    void SubmitAnalysisResult(
        uint64_t frame_id,
        uint32_t flags,
        std::span<const uint8_t> payload
    );
};
```

And packet wrapper:

```cpp
class FramePacket {
public:
    uint64_t frame_id;
    int64_t capture_qpc;
    int64_t host_accept_qpc;
    uint64_t keyboard_mask;
    uint32_t width;
    uint32_t height;
    uint32_t stride;
    uint32_t channels;
    uint8_t* data;

    void Release();
};
```

The exact internal class layout is up to the implementation, but the semantics should remain consistent with this spec.

---

## 20. Error Handling

### 20.1 Fatal errors

Fatal errors should fault the engine and stop capture.

Examples:

- failure to initialize required graphics device
- failure to create capture session
- unrecoverable internal synchronization failure

### 20.2 Non-fatal recording errors

Recording failures should ideally stop the recording session while capture continues.

Examples:

- output file open failure
- encoder initialization failure for a specific session
- mux/write failure

In these cases:

- `is_recording()` becomes false
- `get_last_error()` reports a useful message
- Python frame delivery continues if possible

### 20.3 Python-visible exceptions

Binding layer should raise Python exceptions on clear API misuse, such as:

- calling `start_recording()` while already recording
- invalid target descriptor
- invalid parameter values

---

## 21. Logging and Diagnostics

The implementation should maintain enough internal visibility to answer these questions:

- how many frames were captured?
- how many were accepted?
- how many were dropped because Python was behind?
- was recording active?
- how many frames were recorded?
- did the encoder fail?
- what was the last error?

Optional internal logging is recommended, but the exact logging backend is implementation-defined.

---

## 22. Example Python Usage

### 22.1 Live analysis only

```python
import Memoir

engine = Memoir.CaptureEngine(
    {"type": "window_title", "value": "(?i)overwatch"},
    max_fps=10.0,
)

engine.start()

try:
    for packet in engine.frames():
        try:
            img = packet.cpu_bgra
            process_frame(
                img,
                frame_id=packet.frame_id,
                keyboard_mask=packet.keyboard_mask,
            )
        finally:
            packet.release()
finally:
    engine.stop()
```

### 22.2 Dynamic recording

```python
import Memoir

engine = Memoir.CaptureEngine(
    {"type": "window_title", "value": "(?i)overwatch"},
    max_fps=10.0,
    record_width=1920,
    record_height=1080,
)

engine.start()

try:
    # capture and analysis continue regardless of recording state
    for _ in range(20):
        packet = engine.get_next_frame(200)
        if packet is None:
            continue
        try:
            process_frame(packet.cpu_bgra)
        finally:
            packet.release()

    info = engine.start_recording("debug/session_001")

    for _ in range(200):
        packet = engine.get_next_frame(200)
        if packet is None:
            continue
        try:
            process_frame(packet.cpu_bgra)
        finally:
            packet.release()

    engine.stop_recording()
finally:
    engine.stop()
```

### 22.3 Context manager style

```python
packet = engine.get_next_frame(500)
if packet is not None:
    with packet:
        process_frame(packet.cpu_bgra)
```

---

## 23. Implementation Recommendations

### 23.1 Language and tooling

Recommended stack:

- C++20
- Windows.Graphics.Capture
- D3D11
- NVENC
- pybind11 or nanobind for Python bindings

### 23.2 Suggested binding library

`pybind11` is a good default choice because it makes it straightforward to expose:

- classes
- properties
- methods
- NumPy-compatible buffers

### 23.3 Suggested development order

1. Implement capture engine with acceptance queue and CPU readback
2. Expose `FramePacket` to Python
3. Verify Python analysis loop
4. Add dynamic recording session control
5. Add metadata writing
6. Harden error handling and stats
7. Optimize buffer pooling and encoder path

---

## 24. Out of Scope for v1

The following are intentionally out of scope:

- mouse position/button capture
- audio capture
- multiple simultaneous recordings
- arbitrary pixel formats
- exposing GPU frames to Python
- Python callback-driven frame delivery
- built-in replay decoder/reader
- network streaming
- cross-platform support

---

## 25. Future Extensions

Potential v2 features:

- mouse state in metadata
- analysis result sidecar
- optional ROI crops
- support for more codecs/settings
- event markers from Python
- replay reader in the same package
- richer drop-policy modes
- per-frame custom annotations
- explicit device-loss recovery strategy

---

## 26. Acceptance Criteria for v1

A v1 implementation is considered complete when all of the following are true:

1. Python can create and start an engine
2. Python can receive CPU-readable accepted frames
3. Accepted frames expose stable metadata and pixel buffers
4. The engine drops frames cleanly when Python falls behind
5. Python can start recording without restarting capture
6. While recording is active, accepted frames are encoded to video
7. While recording is active, matching metadata rows are written
8. Python can stop recording without stopping capture
9. The replay outputs preserve frame order and input alignment
10. The module exposes useful stats and non-fatal error state

---

## 27. Short Summary for an Implementation Agent

Build a Windows native capture engine with Python bindings.

The engine should:

- continuously capture a selected window or monitor using Windows.Graphics.Capture
- expose only **accepted** frames to Python as BGRA NumPy arrays
- assign a global `frame_id` only to accepted frames
- snapshot keyboard state at acceptance time
- optionally record the same accepted frames using a GPU-native path to NVENC
- support `start_recording(base_path)` and `stop_recording()` while capture stays running
- write a binary metadata file aligned 1:1 with recorded frames
- use a bounded Python-facing queue, default size 1, and drop new frames when full
- keep the Python API simple: start, stop, get frames, iterate frames, start/stop recording, stats, errors

Python should never have to touch GPU objects or manually tell the engine which frame to record.
