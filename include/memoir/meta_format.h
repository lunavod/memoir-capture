#pragma once

#include <cstdint>

namespace memoir {

#pragma pack(push, 1)

struct ReplayMetaFileHeaderV1 {
    char     magic[8];           // "RCMETA1\0"
    uint32_t version;            // 1
    uint32_t reserved0;
    uint64_t created_unix_ns;
    uint32_t key_count;
    uint32_t reserved1;
};

struct ReplayMetaKeyEntryV1 {
    uint32_t bit_index;
    uint32_t virtual_key;
    char     name[32];
};

struct ReplayMetaV1 {
    uint64_t frame_id;
    uint64_t record_frame_index;
    int64_t  capture_qpc;
    int64_t  host_accept_qpc;
    uint64_t keyboard_mask;
    uint32_t width;
    uint32_t height;
    uint32_t analysis_stride;
    uint32_t flags;
};

#pragma pack(pop)

} // namespace memoir
