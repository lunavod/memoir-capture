#include "window_finder.h"
#include <regex>

namespace memoir {

// --- Window by title ---

struct TitleEnumData {
    std::wregex pattern;
    HWND result = nullptr;
};

static BOOL CALLBACK TitleEnumProc(HWND hwnd, LPARAM lParam) {
    auto* d = reinterpret_cast<TitleEnumData*>(lParam);
    if (!IsWindowVisible(hwnd)) return TRUE;

    wchar_t title[512]{};
    GetWindowTextW(hwnd, title, 512);
    if (title[0] == L'\0') return TRUE;

    if (std::regex_search(title, d->pattern)) {
        d->result = hwnd;
        return FALSE;
    }
    return TRUE;
}

HWND FindWindowByTitleRegex(const std::wstring& pattern) {
    TitleEnumData d;
    d.pattern = std::wregex(pattern);
    EnumWindows(TitleEnumProc, reinterpret_cast<LPARAM>(&d));
    return d.result;
}

// --- Window by exe name ---

struct ExeEnumData {
    std::wregex pattern;
    HWND result = nullptr;
};

static BOOL CALLBACK ExeEnumProc(HWND hwnd, LPARAM lParam) {
    auto* d = reinterpret_cast<ExeEnumData*>(lParam);
    if (!IsWindowVisible(hwnd)) return TRUE;

    DWORD pid = 0;
    GetWindowThreadProcessId(hwnd, &pid);
    if (!pid) return TRUE;

    HANDLE proc = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, FALSE, pid);
    if (!proc) return TRUE;

    wchar_t path[MAX_PATH]{};
    DWORD size = MAX_PATH;
    BOOL ok = QueryFullProcessImageNameW(proc, 0, path, &size);
    CloseHandle(proc);

    if (!ok) return TRUE;

    std::wstring full(path);
    auto pos = full.find_last_of(L"\\/");
    std::wstring exe = (pos != std::wstring::npos) ? full.substr(pos + 1) : full;

    if (std::regex_search(exe, d->pattern)) {
        d->result = hwnd;
        return FALSE;
    }
    return TRUE;
}

HWND FindWindowByExeRegex(const std::wstring& pattern) {
    ExeEnumData d;
    d.pattern = std::wregex(pattern);
    EnumWindows(ExeEnumProc, reinterpret_cast<LPARAM>(&d));
    return d.result;
}

// --- Monitor by index ---

struct MonitorEnumData {
    int32_t target;
    int32_t current = 0;
    HMONITOR result = nullptr;
};

static BOOL CALLBACK MonitorEnumProc(HMONITOR hMon, HDC, LPRECT, LPARAM lParam) {
    auto* d = reinterpret_cast<MonitorEnumData*>(lParam);
    if (d->current == d->target) {
        d->result = hMon;
        return FALSE;
    }
    d->current++;
    return TRUE;
}

HMONITOR GetMonitorByIndex(int32_t index) {
    MonitorEnumData d;
    d.target = index;
    EnumDisplayMonitors(nullptr, nullptr, MonitorEnumProc,
                        reinterpret_cast<LPARAM>(&d));
    return d.result;
}

} // namespace memoir
