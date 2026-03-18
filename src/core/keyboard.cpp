#include "keyboard.h"
#include <Windows.h>
#include <cstring>

namespace memoir {

static KeySpec MakeKey(uint32_t bit, uint32_t vk, const char* name) {
    KeySpec k{};
    k.bit_index = bit;
    k.virtual_key = vk;
    strncpy_s(k.name, sizeof(k.name), name, _TRUNCATE);
    return k;
}

std::vector<KeySpec> GetDefaultKeyMap() {
    return {
        MakeKey(0,  0x57, "W"),
        MakeKey(1,  0x41, "A"),
        MakeKey(2,  0x53, "S"),
        MakeKey(3,  0x44, "D"),
        MakeKey(4,  VK_UP, "Up"),
        MakeKey(5,  VK_DOWN, "Down"),
        MakeKey(6,  VK_LEFT, "Left"),
        MakeKey(7,  VK_RIGHT, "Right"),
        MakeKey(8,  VK_SPACE, "Space"),
        MakeKey(9,  VK_LSHIFT, "LShift"),
        MakeKey(10, VK_LCONTROL, "LCtrl"),
        MakeKey(11, VK_LMENU, "LAlt"),
        MakeKey(12, 0x31, "1"),
        MakeKey(13, 0x32, "2"),
        MakeKey(14, 0x33, "3"),
        MakeKey(15, 0x34, "4"),
        MakeKey(16, 0x35, "5"),
        MakeKey(17, 0x36, "6"),
        MakeKey(18, 0x37, "7"),
        MakeKey(19, 0x38, "8"),
        MakeKey(20, 0x39, "9"),
        MakeKey(21, 0x30, "0"),
        MakeKey(22, VK_TAB, "Tab"),
        MakeKey(23, VK_ESCAPE, "Esc"),
        MakeKey(24, 0x51, "Q"),
        MakeKey(25, 0x45, "E"),
        MakeKey(26, 0x52, "R"),
        MakeKey(27, 0x46, "F"),
        MakeKey(28, 0x47, "G"),
        MakeKey(29, 0x5A, "Z"),
        MakeKey(30, 0x58, "X"),
        MakeKey(31, 0x43, "C"),
        MakeKey(32, 0x56, "V"),
        MakeKey(33, VK_RETURN, "Enter"),
        MakeKey(34, VK_BACK, "Backspace"),
        MakeKey(35, VK_F1, "F1"),
        MakeKey(36, VK_F2, "F2"),
        MakeKey(37, VK_F3, "F3"),
        MakeKey(38, VK_F4, "F4"),
        MakeKey(39, VK_F5, "F5"),
    };
}

uint64_t SnapshotKeyboard(const std::vector<KeySpec>& key_map) {
    uint64_t mask = 0;
    for (const auto& k : key_map) {
        if (k.bit_index >= 64) continue;
        SHORT state = GetAsyncKeyState(static_cast<int>(k.virtual_key));
        if (state & 0x8000) {
            mask |= (1ULL << k.bit_index);
        }
    }
    return mask;
}

} // namespace memoir
