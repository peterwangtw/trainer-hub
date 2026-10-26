"""用 Windows 內建的 GDI+（ctypes 呼叫）把 JPG/PNG/GIF 縮放成 tkinter 可讀的 PNG。"""
import ctypes
import ctypes.wintypes as wt
import os
import threading

gdip = ctypes.WinDLL("gdiplus")

PIXEL_FORMAT_32BPP_ARGB = 0x26200A
INTERPOLATION_HQ_BICUBIC = 7
PIXEL_OFFSET_HQ = 2
WRAP_TILE_FLIP_XY = 3
UNIT_PIXEL = 2


class GUID(ctypes.Structure):
    _fields_ = [("Data1", wt.DWORD), ("Data2", wt.WORD), ("Data3", wt.WORD), ("Data4", ctypes.c_ubyte * 8)]


class StartupInput(ctypes.Structure):
    _fields_ = [("GdiplusVersion", ctypes.c_uint32), ("DebugEventCallback", ctypes.c_void_p),
                ("SuppressBackgroundThread", wt.BOOL), ("SuppressExternalCodecs", wt.BOOL)]


ColorMatrix = (ctypes.c_float * 25)

# {557CF406-1A04-11D3-9A73-0000F81EF32E}
PNG_ENCODER = GUID(0x557CF406, 0x1A04, 0x11D3, (ctypes.c_ubyte * 8)(0x9A, 0x73, 0x00, 0x00, 0xF8, 0x1E, 0xF3, 0x2E))

GRAY = ColorMatrix(
    0.30, 0.30, 0.30, 0, 0,
    0.59, 0.59, 0.59, 0, 0,
    0.11, 0.11, 0.11, 0, 0,
    0, 0, 0, 1, 0,
    0.10, 0.10, 0.09, 0, 1,
)

_token = ctypes.c_size_t()
_lock = threading.Lock()
_started = False


def _startup():
    global _started
    with _lock:
        if not _started:
            si = StartupInput(1, None, False, False)
            if gdip.GdiplusStartup(ctypes.byref(_token), ctypes.byref(si), None) != 0:
                raise OSError("GdiplusStartup 失敗")
            _started = True


def _check(status, what):
    if status != 0:
        raise OSError(f"{what} 失敗 (GDI+ 狀態 {status})")


def is_fresh(src, dst):
    try:
        return os.path.getmtime(dst) >= os.path.getmtime(src)
    except OSError:
        return False


def convert(src, dst, w, h, mode="cover", gray=False):
    """把 src 縮放成 w×h 的 PNG。mode: cover（裁切填滿）/ contain（完整置中，留透明）。"""
    if is_fresh(src, dst):
        return True
    _startup()
    img, bmp, gfx, attr = ctypes.c_void_p(), ctypes.c_void_p(), ctypes.c_void_p(), ctypes.c_void_p()
    try:
        _check(gdip.GdipLoadImageFromFile(ctypes.c_wchar_p(src), ctypes.byref(img)), "讀取圖片")
        sw, sh = ctypes.c_uint(), ctypes.c_uint()
        gdip.GdipGetImageWidth(img, ctypes.byref(sw))
        gdip.GdipGetImageHeight(img, ctypes.byref(sh))
        sw, sh = sw.value, sh.value
        if not sw or not sh:
            return False

        scale = (min if mode == "contain" else max)(w / sw, h / sh)
        dw, dh = round(sw * scale), round(sh * scale)
        dx, dy = (w - dw) // 2, (h - dh) // 2

        _check(gdip.GdipCreateBitmapFromScan0(w, h, 0, PIXEL_FORMAT_32BPP_ARGB, None, ctypes.byref(bmp)), "建立畫布")
        _check(gdip.GdipGetImageGraphicsContext(bmp, ctypes.byref(gfx)), "建立繪圖")
        gdip.GdipSetInterpolationMode(gfx, INTERPOLATION_HQ_BICUBIC)
        gdip.GdipSetPixelOffsetMode(gfx, PIXEL_OFFSET_HQ)
        _check(gdip.GdipCreateImageAttributes(ctypes.byref(attr)), "建立屬性")
        gdip.GdipSetImageAttributesWrapMode(attr, WRAP_TILE_FLIP_XY, 0, False)
        if gray:
            gdip.GdipSetImageAttributesColorMatrix(attr, 0, True, ctypes.byref(GRAY), None, 0)
        _check(gdip.GdipDrawImageRectRectI(gfx, img, dx, dy, dw, dh, 0, 0, sw, sh, UNIT_PIXEL, attr, None, None),
               "繪製圖片")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        tmp = dst + ".tmp"
        _check(gdip.GdipSaveImageToFile(bmp, ctypes.c_wchar_p(tmp), ctypes.byref(PNG_ENCODER), None), "儲存 PNG")
        os.replace(tmp, dst)
        return True
    except OSError:
        return False
    finally:
        if attr:
            gdip.GdipDisposeImageAttributes(attr)
        if gfx:
            gdip.GdipDeleteGraphics(gfx)
        if bmp:
            gdip.GdipDisposeImage(bmp)
        if img:
            gdip.GdipDisposeImage(img)
