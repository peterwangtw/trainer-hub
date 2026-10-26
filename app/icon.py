"""Trainer Hub 圖示：16×16 像素風撥動開關（黃色軌道、綠色燈號），由程式直接產生，不需要圖檔。"""
import ctypes
import tkinter as tk

PALETTE = {
    "K": "#202020",  # 底色（同導覽列）
    "T": "#FFF78B",  # 開關軌道（黃）
    "L": "#34D058",  # 燈號（綠）
    "W": "#F5F5F2",  # 圓鈕
    "g": "#C8C6C0",  # 圓鈕陰影
    "Y": "#FFF78B",  # 左上指示燈
    "G": "#8F8D88",  # 左上指示燈（暗）
}

PIXELS = [
    ".KKKKKKKKKKKKKK.",
    "KKKKKKKKKKKKKKKK",
    "KKYKGKKKKKKKKKKK",
    "KKKKKKKKKKKKKKKK",
    "KKKKKKKKKKKKKKKK",
    "KKKTTTTTTWWWWKKK",
    "KKTTTTTTWWWWWWKK",
    "KKTTLTTTWWWWWWKK",
    "KKTTLTTTWWWWWWKK",
    "KKTTTTTTWWWWWWKK",
    "KKKTTTTTTggggKKK",
    "KKKKKKKKKKKKKKKK",
    "KKKKKKKKKKKKKKKK",
    "KKKKKKKKKKKKKKKK",
    "KKKKKKKKKKKKKKKK",
    ".KKKKKKKKKKKKKK.",
]

APP_ID = "TrainerHub.Launcher"


def set_app_id():
    """讓 Windows 工作列把我們當成獨立程式（顯示自己的圖示，而不是 pythonw.exe 的）。必須在建立視窗前呼叫。"""
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except (AttributeError, OSError):
        pass


def base_image(master):
    img = tk.PhotoImage(master=master, width=16, height=16)  # 未填的像素為透明
    for y, row in enumerate(PIXELS):
        for x, ch in enumerate(row):
            color = PALETTE.get(ch)
            if color:
                img.put(color, (x, y))
    return img


def apply(root):
    """設定主視窗與之後所有 Toplevel 的圖示；回傳圖片參照（需保留，避免被回收）。"""
    base = base_image(root)
    sizes = [base.zoom(n) for n in (16, 4, 2)]  # 256 / 64 / 32，最近鄰放大保持像素銳利
    images = sizes + [base]
    root.iconphoto(True, *images)
    return images
