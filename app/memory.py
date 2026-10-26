"""讀寫其他程序記憶體的共用工具（只用 ctypes）。"""
import ctypes
import ctypes.wintypes as wt
import struct

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)
k32.OpenProcess.restype = wt.HANDLE
k32.CreateToolhelp32Snapshot.restype = wt.HANDLE

PROCESS_ACCESS = 0x0008 | 0x0010 | 0x0020 | 0x0400  # VM_OPERATION|VM_READ|VM_WRITE|QUERY_INFORMATION
STILL_ACTIVE = 259
PAGE_EXECUTE_READWRITE = 0x40
INVALID_HANDLE = wt.HANDLE(-1).value


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ProcessID", wt.DWORD),
        ("th32DefaultHeapID", ctypes.c_void_p), ("th32ModuleID", wt.DWORD),
        ("cntThreads", wt.DWORD), ("th32ParentProcessID", wt.DWORD),
        ("pcPriClassBase", ctypes.c_long), ("dwFlags", wt.DWORD),
        ("szExeFile", ctypes.c_wchar * 260),
    ]


def find_pid(exe_name):
    snap = k32.CreateToolhelp32Snapshot(0x2, 0)  # TH32CS_SNAPPROCESS
    if snap in (None, INVALID_HANDLE):
        return None
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        ok = k32.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            if entry.szExeFile.lower() == exe_name.lower():
                return entry.th32ProcessID
            ok = k32.Process32NextW(snap, ctypes.byref(entry))
    finally:
        k32.CloseHandle(snap)
    return None


class Process:
    def __init__(self, pid):
        self.pid = pid
        self.handle = k32.OpenProcess(PROCESS_ACCESS, False, pid)
        if not self.handle:
            raise OSError(ctypes.get_last_error(), "無法開啟遊戲程序")
        self.base = self._module_base()
        self.path = self._image_path()

    def _module_base(self):
        mods = (wt.HMODULE * 1024)()
        need = wt.DWORD()
        # LIST_MODULES_ALL = 3，32/64 位元遊戲都適用
        if not psapi.EnumProcessModulesEx(self.handle, mods, ctypes.sizeof(mods), ctypes.byref(need), 3):
            raise OSError(ctypes.get_last_error(), "無法取得模組基址")
        return mods[0]

    def _image_path(self):
        buf = ctypes.create_unicode_buffer(1024)
        size = wt.DWORD(len(buf))
        if k32.QueryFullProcessImageNameW(self.handle, 0, buf, ctypes.byref(size)):
            return buf.value
        return None

    def alive(self):
        code = wt.DWORD()
        return bool(self.handle) and bool(k32.GetExitCodeProcess(self.handle, ctypes.byref(code))) \
            and code.value == STILL_ACTIVE

    def read_int(self, off):
        buf = ctypes.c_int32()
        if not k32.ReadProcessMemory(self.handle, ctypes.c_void_p(self.base + off), ctypes.byref(buf), 4, None):
            raise OSError(ctypes.get_last_error(), "ReadProcessMemory 失敗")
        return buf.value

    def write_int(self, off, value):
        data = struct.pack("<i", value)
        if not k32.WriteProcessMemory(self.handle, ctypes.c_void_p(self.base + off), data, 4, None):
            raise OSError(ctypes.get_last_error(), "WriteProcessMemory 失敗")

    def read_bytes(self, off, size):
        buf = ctypes.create_string_buffer(size)
        if not k32.ReadProcessMemory(self.handle, ctypes.c_void_p(self.base + off), buf, size, None):
            raise OSError(ctypes.get_last_error(), "ReadProcessMemory 失敗")
        return buf.raw

    def write_code(self, off, data):
        """寫入程式碼區段：暫時改成可寫，寫完恢復原本的保護並清除指令快取。"""
        addr = ctypes.c_void_p(self.base + off)
        old = wt.DWORD()
        if not k32.VirtualProtectEx(self.handle, addr, len(data), PAGE_EXECUTE_READWRITE, ctypes.byref(old)):
            raise OSError(ctypes.get_last_error(), "VirtualProtectEx 失敗")
        try:
            if not k32.WriteProcessMemory(self.handle, addr, data, len(data), None):
                raise OSError(ctypes.get_last_error(), "WriteProcessMemory 失敗")
        finally:
            k32.VirtualProtectEx(self.handle, addr, len(data), old.value, ctypes.byref(wt.DWORD()))
            k32.FlushInstructionCache(self.handle, addr, len(data))

    def close(self):
        if self.handle:
            k32.CloseHandle(self.handle)
            self.handle = None
