#pragma once

#include <Windows.h>
#include <string>

namespace memoir {

HWND     FindWindowByTitleRegex(const std::wstring& pattern);
HWND     FindWindowByExeRegex(const std::wstring& pattern);
HMONITOR GetMonitorByIndex(int32_t index);

} // namespace memoir
