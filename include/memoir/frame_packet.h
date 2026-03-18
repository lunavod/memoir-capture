#pragma once

#include <cstdint>
#include <vector>

namespace memoir {

class FramePacket {
public:
    uint64_t frame_id = 0;
    int64_t  capture_qpc = 0;
    int64_t  host_accept_qpc = 0;
    uint64_t keyboard_mask = 0;

    uint32_t width = 0;
    uint32_t height = 0;
    uint32_t stride = 0;
    uint32_t channels = 4;

    std::vector<uint8_t> pixel_data;

    bool IsReleased() const { return released_; }

    void Release() {
        if (released_) return;
        released_ = true;
        pixel_data.clear();
        pixel_data.shrink_to_fit();
    }

private:
    bool released_ = false;
};

} // namespace memoir
