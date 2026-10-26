"""Trainer Hub — 遊戲測試修改器啟動器（tkinter）。"""
import ctypes
import json
import os
import queue
import subprocess
import threading
import time
import tkinter as tk
import traceback
import winsound

from . import imaging, steam
from .games import GAMES
from .memory import Process, find_pid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(ROOT, "cache")
CONFIG_PATH = os.path.join(ROOT, "config.json")
ERROR_LOG = os.path.join(ROOT, "launcher_error.log")

# ---- 設計樣式（參考 melius.com）-------------------------------------------
C = {
    "bg": "#ECEBE7", "dot": "#D3D1CB", "nav": "#202020", "nav_fg": "#F5F5F2", "nav_dim": "#9C9A95",
    "ink": "#0E0E0E", "ink2": "#5D5B56", "ink3": "#8F8D88", "line": "#D8D6D0",
    "card": "#FFFFFF", "card_alt": "#F6F5F2", "placeholder": "#DAD8D2",
    "orange": "#F04E23", "orange_hover": "#D63F17", "yellow": "#FFF78B", "yellow_hover": "#F5EC6E",
    "green": "#2E9B57", "amber": "#C77700", "off": "#C8C6C0", "black_chip": "#0E0E0E",
}
SANS = "Microsoft JhengHei UI"
SERIF = "Georgia"
F = {
    "logo": (SANS, 12, "bold"), "nav": (SANS, 10), "announce": (SANS, 9),
    "hero": (SANS, 30, "bold"), "hero_sub": (SANS, 11), "title": (SERIF, 30), "title_cn": (SANS, 22, "bold"),
    "section": (SANS, 13, "bold"), "count": (SANS, 10), "card_name": (SANS, 10, "bold"), "card_sub": (SANS, 9),
    "body": (SANS, 10), "small": (SANS, 9), "btn": (SANS, 10, "bold"), "feature": (SANS, 13, "bold"),
    "chip": (SANS, 9, "bold"), "status": (SANS, 10, "bold"), "mono": ("Consolas", 10),
}
CONTENT_W = 1040
CARD_W, CARD_H, GAP = 180, 270, 20
HERO_H = 260

TICK_MS = 15
DETECT_MS = 1000
HOLD_DELAY = 0.4    # 按住加速/減速鍵多久後開始連續調整（秒）
HOLD_REPEAT = 0.08

user32 = ctypes.WinDLL("user32")


# ---- 設定檔 ----------------------------------------------------------------
class Config:
    def __init__(self, path):
        self.path = path
        self.data = {"hotkeys": {}, "enabled": {}, "values": {}}
        try:
            with open(path, encoding="utf-8") as f:
                self.data.update(json.load(f))
        except (OSError, ValueError):
            pass

    def save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def hotkey(self, key, default):
        if key in self.data["hotkeys"]:
            v = self.data["hotkeys"][key]
            return tuple(v) if v else None
        return default

    def set_hotkey(self, key, value):
        self.data["hotkeys"][key] = list(value) if value else None
        self.save()

    def enabled(self, key):
        return bool(self.data["enabled"].get(key, False))

    def set_enabled(self, key, value):
        self.data["enabled"][key] = bool(value)
        self.save()

    def value(self, key, default):
        try:
            return int(self.data["values"].get(key, default))
        except (TypeError, ValueError):
            return default

    def set_value(self, key, value):
        self.data["values"][key] = int(value)
        self.save()

    def steam_paths(self):
        return [p for p in self.data.get("steam_paths", []) if isinstance(p, str)]

    def steam_autodetect(self):
        return bool(self.data.get("steam_autodetect", True))

    def set_steam(self, paths, autodetect):
        self.data["steam_paths"] = list(paths)
        self.data["steam_autodetect"] = bool(autodetect)
        self.save()


# ---- 修改器邏輯 ------------------------------------------------------------
class Session:
    """單一遊戲的修改器狀態：偵測程序、總開關、各功能開關。"""

    def __init__(self, game, cfg):
        self.game = game
        self.cfg = cfg
        self.proc = None
        self.master = False  # 每次啟動預設關閉，避免意外寫入
        self.enabled = {f.id: cfg.enabled(f"{game.id}.{f.id}") for f in game.features}
        self.values = {s.id: self._clamp(s, cfg.value(f"{game.id}.{s.id}", s.default)) for s in game.settings}
        self.setting_error = {}  # setting id → True 表示指令比對失敗，無法套用
        self.state = "absent"  # absent | ok | mismatch | denied
        self.error = ""
        self.info = {}
        self.install_dir = None

    @staticmethod
    def _clamp(setting, value):
        return max(setting.minimum, min(setting.maximum, int(value)))

    def _drop(self):
        if self.proc:
            self.proc.close()
        self.proc = None

    def detect(self):
        if self.proc and not self.proc.alive():
            self._drop()
        if not self.proc:
            pid = find_pid(self.game.exe)
            if not pid:
                self.state, self.info = "absent", {}
                return
            try:
                self.proc = Process(pid)
            except OSError as e:
                self.state, self.error, self.info = "denied", str(e), {}
                return
            if self.proc.path:
                self.install_dir = os.path.dirname(self.proc.path)
        size_ok = True
        if self.game.exe_size and self.proc.path:
            try:
                size_ok = os.path.getsize(self.proc.path) == self.game.exe_size
            except OSError:
                pass
        self.state = "ok" if size_ok else "mismatch"
        if self.state == "ok":
            try:
                self.info = self.game.read_status(self.proc)
            except OSError:
                self._drop()
                self.state, self.info = "absent", {}

    def _sync_settings(self, active):
        """數值型功能：修改器開啟時套用設定值，關閉時還原成預設值（apply 只在不同時才寫入）。"""
        for s in self.game.settings:
            want = self.values[s.id] if active else s.default
            self.setting_error[s.id] = not s.apply(self.proc, want)

    def tick(self):
        if not (self.proc and self.state == "ok"):
            return
        try:
            self._sync_settings(self.master)
            if self.master:
                for f in self.game.features:
                    if self.enabled[f.id]:
                        f.apply(self.proc)
        except OSError:
            self._drop()
            self.state = "absent"

    def restore(self):
        """關閉啟動器前呼叫：把改過的程式碼還原。"""
        if self.proc and self.state == "ok":
            try:
                self._sync_settings(False)
            except OSError:
                pass

    def set_master(self, value):
        self.master = bool(value)

    def set_value(self, sid, value):
        s = next(s for s in self.game.settings if s.id == sid)
        value = self._clamp(s, value)
        self.values[sid] = value
        self.cfg.set_value(f"{self.game.id}.{sid}", value)
        if value != s.default:
            self.master = True  # 調整數值時自動開啟修改器
        return value

    def set_feature(self, fid, value):
        self.enabled[fid] = bool(value)
        self.cfg.set_enabled(f"{self.game.id}.{fid}", value)
        if value:
            self.master = True  # 開啟任一功能時自動開啟修改器

    @property
    def active(self):
        return self.master and self.state == "ok"


def beep(on):
    def run():
        try:
            if on:
                winsound.Beep(880, 60); winsound.Beep(1320, 80)
            else:
                winsound.Beep(660, 60); winsound.Beep(440, 80)
        except RuntimeError:
            pass
    threading.Thread(target=run, daemon=True).start()


def beep_value(value):
    def run():
        try:
            winsound.Beep(min(2400, 400 + value * 40), 50)
        except RuntimeError:
            pass
    threading.Thread(target=run, daemon=True).start()


# ---- 共用元件 --------------------------------------------------------------
def flat_button(parent, text, command, bg, fg, hover, font=F["btn"], padx=16, pady=7):
    b = tk.Label(parent, text=text, bg=bg, fg=fg, font=font, padx=padx, pady=pady, cursor="hand2")
    b.bind("<Enter>", lambda e: b.config(bg=hover))
    b.bind("<Leave>", lambda e: b.config(bg=bg))
    b.bind("<Button-1>", lambda e: command())
    return b


def bind_tree(widget, sequence, func):
    widget.bind(sequence, func, add="+")
    for child in widget.winfo_children():
        bind_tree(child, sequence, func)


def truncate(text, font, width, root):
    import tkinter.font as tkfont
    f = tkfont.Font(root=root, font=font)
    if f.measure(text) <= width:
        return text
    while text and f.measure(text + "…") > width:
        text = text[:-1]
    return text + "…"


class Toggle(tk.Canvas):
    def __init__(self, parent, command=None, w=48, h=26, bg=C["card"]):
        super().__init__(parent, width=w, height=h, bg=bg, highlightthickness=0, bd=0, cursor="hand2")
        self.w, self.h, self.state, self.command = w, h, False, command
        self.muted = False
        self.bind("<Button-1>", self._click)
        self._draw()

    def _draw(self):
        self.delete("all")
        w, h = self.w, self.h
        if self.state:
            col = "#F4A58F" if self.muted else C["orange"]
        else:
            col = C["off"]
        self.create_oval(0, 0, h, h, fill=col, outline=col)
        self.create_oval(w - h, 0, w, h, fill=col, outline=col)
        self.create_rectangle(h / 2, 0, w - h / 2, h, fill=col, outline=col)
        x = w - h + 3 if self.state else 3
        self.create_oval(x, 3, x + h - 6, h - 3, fill="white", outline="white")

    def set(self, value, muted=False):
        if bool(value) != self.state or muted != self.muted:
            self.state, self.muted = bool(value), muted
            self._draw()

    def _click(self, _):
        self.set(not self.state, self.muted)
        if self.command:
            self.command(self.state)


class ScrollArea(tk.Frame):
    """可捲動的頁面，內容置中並限制最大寬度。"""

    def __init__(self, parent, bg=C["bg"]):
        super().__init__(parent, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.vsb = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self.win = self.canvas.create_window(0, 0, window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.vsb.pack(side="right", fill="y")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", self._on_resize)
        self.body = tk.Frame(self.inner, bg=bg)
        self.body.pack(fill="both", expand=True, padx=32)
        self.resize_listeners = []

    def _on_resize(self, e):
        self.canvas.itemconfigure(self.win, width=e.width)
        pad = max(24, (e.width - CONTENT_W) // 2)
        self.body.pack_configure(padx=pad)
        for fn in self.resize_listeners:
            fn(e.width - 2 * pad)

    def wheel(self, e):
        if self.inner.winfo_height() > self.canvas.winfo_height():
            self.canvas.yview_scroll(int(-e.delta / 120) * 3, "units")

    def top(self):
        self.canvas.yview_moveto(0)


# ---- 遊戲庫頁 --------------------------------------------------------------
class GameCard(tk.Frame):
    def __init__(self, parent, name, subtitle, sub_color, on_click=None):
        super().__init__(parent, bg=C["card"], highlightthickness=1, width=CARD_W, height=CARD_H + 58,
                         highlightbackground=C["line"], highlightcolor=C["line"])
        self.pack_propagate(False)  # 固定卡片尺寸，長名稱不會撐寬
        self.name = name
        self.art = tk.Canvas(self, width=CARD_W, height=CARD_H, bg=C["placeholder"], highlightthickness=0, bd=0)
        self.art.pack()
        self.art.create_text(CARD_W / 2, CARD_H / 2, text=name, width=CARD_W - 24,
                             font=F["card_name"], fill=C["ink2"], justify="center")
        self.name_lbl = tk.Label(self, text=truncate(name, F["card_name"], CARD_W - 20, parent),
                                 bg=C["card"], fg=C["ink"], font=F["card_name"], anchor="w")
        self.name_lbl.pack(fill="x", padx=10, pady=(8, 0))
        self.sub = tk.Label(self, text=subtitle, bg=C["card"], fg=sub_color, font=F["card_sub"], anchor="w")
        self.sub.pack(fill="x", padx=10, pady=(0, 9))
        self.photo = None
        if on_click:
            self.configure(cursor="hand2")
            bind_tree(self, "<Button-1>", lambda e: on_click())
            bind_tree(self, "<Enter>", lambda e: self.configure(highlightbackground=C["orange"]))
            bind_tree(self, "<Leave>", lambda e: self.configure(highlightbackground=C["line"]))

    def set_image(self, path):
        try:
            self.photo = tk.PhotoImage(file=path)
        except tk.TclError:
            return
        self.art.delete("all")
        self.art.create_image(0, 0, image=self.photo, anchor="nw")

    def set_sub(self, text, color):
        if self.sub.cget("text") != text:
            self.sub.config(text=text, fg=color)


class LibraryPage(ScrollArea):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.cards = []  # (card, section)
        self.query = tk.StringVar()
        self.query.trace_add("write", lambda *_: self.layout())

        # Hero（點點背景 + 大標題 + 搜尋）
        self.hero = tk.Canvas(self.inner, height=230, bg=C["bg"], highlightthickness=0, bd=0)
        self.hero.pack(fill="x", before=self.body)
        self.hero.bind("<Configure>", self._draw_hero)
        self.search_box = tk.Frame(self.hero, bg=C["card"], highlightthickness=1,
                                   highlightbackground=C["line"], highlightcolor=C["ink"])
        tk.Label(self.search_box, text="⌕", bg=C["card"], fg=C["ink3"], font=(SANS, 13)).pack(side="left", padx=(12, 4))
        self.entry = tk.Entry(self.search_box, textvariable=self.query, bd=0, font=F["body"], bg=C["card"],
                              fg=C["ink"], insertbackground=C["ink"], width=38)
        self.entry.pack(side="left", ipady=8, padx=(0, 12))

        # 已支援
        self.sec_supported = self._section("已支援的遊戲")
        self.grid_supported = tk.Frame(self.body, bg=C["bg"])
        self.grid_supported.pack(fill="x")
        # 尚未支援
        self.sec_other = self._section("Steam 已安裝 · 尚未支援", top=36)
        self.grid_other = tk.Frame(self.body, bg=C["bg"])
        self.grid_other.pack(fill="x", pady=(0, 48))
        self.empty_other = tk.Label(self.grid_other, text="正在掃描 Steam 遊戲庫…", bg=C["bg"],
                                    fg=C["ink3"], font=F["body"])
        self.width = CONTENT_W
        self.resize_listeners.append(self._on_width)

    def _section(self, title, top=8):
        row = tk.Frame(self.body, bg=C["bg"])
        row.pack(fill="x", pady=(top, 14))
        tk.Label(row, text=title, bg=C["bg"], fg=C["ink"], font=F["section"]).pack(side="left")
        count = tk.Label(row, text="", bg=C["bg"], fg=C["ink3"], font=F["count"])
        count.pack(side="left", padx=8, pady=(3, 0))
        tk.Frame(row, bg=C["line"], height=1).pack(side="left", fill="x", expand=True, padx=(8, 0), pady=(4, 0))
        return count

    def _draw_hero(self, e):
        c = self.hero
        c.delete("all")
        for y in range(10, e.height, 18):
            for x in range(10, e.width, 18):
                c.create_rectangle(x, y, x + 1, y + 1, fill=C["dot"], outline=C["dot"])
        cx = e.width / 2
        c.create_text(cx, 74, text="選擇要測試的遊戲", font=F["hero"], fill=C["ink"])
        c.create_text(cx, 118, text="點選遊戲進入修改器設定。修改器只在你開啟時才會寫入遊戲記憶體。",
                      font=F["hero_sub"], fill=C["ink2"])
        c.create_window(cx, 172, window=self.search_box)

    def add_card(self, card, section):
        self.cards.append((card, section))

    def _on_width(self, w):
        if w != self.width:
            self.width = w
            self.layout()

    def layout(self):
        q = self.query.get().strip().lower()
        cols = max(1, (self.width + GAP) // (CARD_W + GAP))
        counts = {"supported": 0, "other": 0}
        for card, section in self.cards:
            card.grid_forget()
        for card, section in self.cards:
            if q and q not in card.name.lower():
                continue
            i = counts[section]
            counts[section] += 1
            card.grid(row=i // cols, column=i % cols, padx=(0, GAP), pady=(0, GAP), sticky="n")
        self.sec_supported.config(text=str(counts["supported"]))
        self.sec_other.config(text=str(counts["other"]))
        if counts["other"] == 0:
            if not self.app.scan_done:
                text = "正在掃描 Steam 遊戲庫…"
            elif q:
                text = "沒有符合的遊戲"
            else:
                text = "找不到 Steam 遊戲。請點右上角 ⚙ → 設定，加入 Steam 安裝目錄或遊戲庫資料夾。"
            self.empty_other.config(text=text)
            self.empty_other.grid(row=0, column=0, sticky="w")
        else:
            self.empty_other.grid_forget()


# ---- 修改器頁 --------------------------------------------------------------
class HotkeyChip(tk.Label):
    def __init__(self, parent, app, key_id, default, prefix="快捷鍵"):
        super().__init__(parent, bg=C["card_alt"], fg=C["ink"], font=F["chip"], padx=10, pady=5,
                         cursor="hand2", highlightthickness=1, highlightbackground=C["line"])
        self.app, self.key_id, self.default, self.prefix = app, key_id, default, prefix
        self.bind("<Button-1>", lambda e: app.begin_capture(self))
        self.refresh()

    @property
    def value(self):
        return self.app.cfg.hotkey(self.key_id, self.default)

    def refresh(self, capturing=False):
        if capturing:
            self.config(text="請按下按鍵…", bg=C["yellow"])
        else:
            v = self.value
            self.config(text=f"{self.prefix}  {v[1]}" if v else f"{self.prefix}  未設定", bg=C["card_alt"])


class SettingCard(tk.Frame):
    """數值型功能：滑桿 + −/+ 按鈕 + 數字輸入框 + 減少/增加快捷鍵。"""

    def __init__(self, parent, app, session, setting):
        super().__init__(parent, bg=C["card"], highlightthickness=1, highlightbackground=C["line"])
        self.app, self.session, self.setting = app, session, setting
        gid, st = session.game.id, setting
        self._updating = False

        inner = tk.Frame(self, bg=C["card"])
        inner.pack(fill="x", padx=22, pady=16)
        top = tk.Frame(inner, bg=C["card"])
        top.pack(fill="x")
        tk.Label(top, text=st.name, bg=C["card"], fg=C["ink"], font=F["feature"]).pack(side="left")
        self.inc_chip = HotkeyChip(top, app, f"{gid}.{st.id}.inc", st.inc_key, prefix="增加")
        self.dec_chip = HotkeyChip(top, app, f"{gid}.{st.id}.dec", st.dec_key, prefix="減少")
        self.inc_chip.pack(side="right")
        self.dec_chip.pack(side="right", padx=(0, 8))
        self.desc = tk.Label(inner, text=st.desc, bg=C["card"], fg=C["ink2"], font=F["body"], anchor="w")
        self.desc.pack(anchor="w", pady=(4, 12))

        row = tk.Frame(inner, bg=C["card"])
        row.pack(fill="x")
        flat_button(row, "−", lambda: self.commit(self.session.values[st.id] - 1), C["card_alt"], C["ink"],
                    C["line"], font=(SANS, 12, "bold"), padx=12, pady=2).pack(side="left")
        unit = tk.Label(row, text=st.unit, bg=C["card"], fg=C["ink2"], font=F["feature"])
        unit.pack(side="right", padx=(6, 0))
        self.var = tk.StringVar()
        vcmd = (self.register(lambda s: s == "" or (s.isdigit() and len(s) <= 3)), "%P")
        self.entry = tk.Entry(row, textvariable=self.var, width=4, justify="center", font=F["feature"],
                              bd=0, bg=C["card_alt"], fg=C["ink"], insertbackground=C["ink"],
                              highlightthickness=1, highlightbackground=C["line"], highlightcolor=C["orange"],
                              validate="key", validatecommand=vcmd)
        self.entry.pack(side="right", ipady=4)
        self.entry.bind("<Return>", lambda e: (self.commit(self.var.get()), self.app.root.focus_set()))
        self.entry.bind("<FocusOut>", lambda e: self.commit(self.var.get()))
        flat_button(row, "+", lambda: self.commit(self.session.values[st.id] + 1), C["card_alt"], C["ink"],
                    C["line"], font=(SANS, 12, "bold"), padx=12, pady=2).pack(side="right", padx=(10, 14))
        self.scale = tk.Scale(row, from_=st.minimum, to=st.maximum, orient="horizontal", showvalue=False,
                              resolution=1, bg=C["orange"], activebackground=C["orange_hover"],
                              troughcolor=C["off"], highlightthickness=0, bd=0, sliderrelief="flat",
                              sliderlength=22, width=12, command=self._on_scale)
        self.scale.pack(side="left", fill="x", expand=True, padx=(14, 0))
        scale_labels = tk.Frame(inner, bg=C["card"])
        scale_labels.pack(fill="x", padx=(48, 150))
        tk.Label(scale_labels, text=f"{st.minimum}（原速）", bg=C["card"], fg=C["ink3"],
                 font=F["small"]).pack(side="left")
        tk.Label(scale_labels, text=str(st.maximum), bg=C["card"], fg=C["ink3"], font=F["small"]).pack(side="right")
        self.sync()

    def _on_scale(self, value):
        if not self._updating:
            self.commit(value)

    def commit(self, value):
        try:
            value = int(float(value))
        except (TypeError, ValueError):
            value = self.session.values[self.setting.id]
        self.session.set_value(self.setting.id, value)
        self.app._sync_views()

    def sync(self):
        st, s = self.setting, self.session
        v = s.values[st.id]
        self._updating = True
        if int(self.scale.get()) != v:
            self.scale.set(v)
        self._updating = False
        if self.app.root.focus_get() is not self.entry and self.var.get() != str(v):
            self.var.set(str(v))
        changed = v != st.default
        self.scale.config(bg=(C["orange"] if s.active and changed else "#F4A58F" if changed else C["ink3"]))
        if s.setting_error.get(st.id):
            self.desc.config(text="遊戲程式碼與預期不符，無法套用（可能是不同版本）。", fg=C["orange"])
        else:
            self.desc.config(text=st.desc, fg=C["ink2"])

    def refresh_chips(self):
        self.dec_chip.refresh()
        self.inc_chip.refresh()


class TrainerPage(ScrollArea):
    def __init__(self, parent, app, session):
        super().__init__(parent)
        self.app, self.session, self.game = app, session, session.game
        g = self.game
        b = self.body

        back = tk.Label(b, text="←  遊戲庫", bg=C["bg"], fg=C["ink2"], font=F["body"], cursor="hand2")
        back.pack(anchor="w", pady=(20, 12))
        back.bind("<Button-1>", lambda e: app.show_library())
        back.bind("<Enter>", lambda e: back.config(fg=C["orange"]))
        back.bind("<Leave>", lambda e: back.config(fg=C["ink2"]))

        # 橫幅
        self.hero = tk.Canvas(b, height=HERO_H, bg="#1B1B1B", highlightthickness=0, bd=0)
        self.hero.pack(fill="x")
        self.hero.create_text(36, HERO_H - 48, text=g.name, anchor="w", font=(SERIF, 36, "italic"), fill="white",
                              tags="fallback")
        self.hero_img = self.logo_img = None

        # 標題列
        head = tk.Frame(b, bg=C["bg"])
        head.pack(fill="x", pady=(22, 18))
        left = tk.Frame(head, bg=C["bg"])
        left.pack(side="left")
        tk.Label(left, text=g.name, bg=C["bg"], fg=C["ink"], font=F["title"]).pack(anchor="w")
        tk.Label(left, text=f"{g.version_label}  ·  Steam {g.steam_appid}  ·  {g.tagline}",
                 bg=C["bg"], fg=C["ink2"], font=F["small"]).pack(anchor="w", pady=(2, 8))
        self.status = tk.Label(left, text="", bg=C["bg"], font=F["status"], anchor="w")
        self.status.pack(anchor="w")
        right = tk.Frame(head, bg=C["bg"])
        right.pack(side="right", anchor="n", pady=(6, 0))
        flat_button(right, "啟動遊戲", self.launch_game, C["orange"], "white", C["orange_hover"]).pack(side="right")
        flat_button(right, "遊戲資料夾", self.open_folder, C["yellow"], C["ink"], C["yellow_hover"]) \
            .pack(side="right", padx=(0, 10))

        # 修改器總開關
        self.master_card, mt = self._card(b, "修改器", "", big=True)
        self.master_desc = mt["desc"]
        self.master_chip = HotkeyChip(mt["right"], app, f"{g.id}.master", g.master_key)
        self.master_toggle = Toggle(mt["right"], self.on_master, w=60, h=32)
        self.master_toggle.pack(side="right")
        self.master_chip.pack(side="right", padx=(0, 16))

        # 功能
        row = tk.Frame(b, bg=C["bg"])
        row.pack(fill="x", pady=(30, 12))
        tk.Label(row, text="功能", bg=C["bg"], fg=C["ink"], font=F["section"]).pack(side="left")
        tk.Frame(row, bg=C["line"], height=1).pack(side="left", fill="x", expand=True, padx=(12, 0), pady=(4, 0))

        self.feature_toggles = {}
        self.feature_chips = {}
        for f in g.features:
            _, ft = self._card(b, f.name, f.desc)
            chip = HotkeyChip(ft["right"], app, f"{g.id}.{f.id}", f.default_key)
            tog = Toggle(ft["right"], lambda v, fid=f.id: self.on_feature(fid, v))
            tog.pack(side="right")
            chip.pack(side="right", padx=(0, 16))
            self.feature_toggles[f.id] = tog
            self.feature_chips[f.id] = chip

        self.setting_cards = []
        for st in g.settings:
            card = SettingCard(b, app, session, st)
            card.pack(fill="x", pady=(0, 10))
            self.setting_cards.append(card)

        # 即時數值
        info_card = tk.Frame(b, bg=C["card_alt"], highlightthickness=1, highlightbackground=C["line"])
        info_card.pack(fill="x", pady=(18, 0))
        self.info = tk.Label(info_card, text="", bg=C["card_alt"], fg=C["ink2"], font=F["mono"],
                             justify="left", anchor="w")
        self.info.pack(fill="x", padx=18, pady=12)

        tk.Label(b, text="快捷鍵是全域的：遊戲在前景時一樣有效，切換時會發出提示音。\n"
                         "點選按鍵標籤後按下新按鍵即可變更；Esc 取消、Backspace 清除。",
                 bg=C["bg"], fg=C["ink3"], font=F["small"], justify="left").pack(anchor="w", pady=(14, 48))

        self.sync()

    def _card(self, parent, title, desc, big=False):
        card = tk.Frame(parent, bg=C["card"], highlightthickness=1, highlightbackground=C["line"])
        card.pack(fill="x", pady=(0, 10))
        inner = tk.Frame(card, bg=C["card"])
        inner.pack(fill="x", padx=22, pady=20 if big else 16)
        text = tk.Frame(inner, bg=C["card"])
        text.pack(side="left", fill="x", expand=True)
        tk.Label(text, text=title, bg=C["card"], fg=C["ink"],
                 font=F["title_cn"] if big else F["feature"], anchor="w").pack(anchor="w")
        d = tk.Label(text, text=desc, bg=C["card"], fg=C["ink2"], font=F["body"], anchor="w", justify="left")
        d.pack(anchor="w", pady=(4, 0))
        right = tk.Frame(inner, bg=C["card"])
        right.pack(side="right")
        return card, {"desc": d, "right": right}

    def set_art(self, hero, logo):
        if hero:
            try:
                self.hero_img = tk.PhotoImage(file=hero)
                self.hero.delete("all")
                self.hero.create_image(0, 0, image=self.hero_img, anchor="nw", tags="hero")
            except tk.TclError:
                pass
        if logo:
            try:
                self.logo_img = tk.PhotoImage(file=logo)
                self.hero.delete("fallback")
                self.hero.create_image(28, HERO_H - 16, image=self.logo_img, anchor="sw")
            except tk.TclError:
                pass

    def on_master(self, value):
        self.session.set_master(value)
        self.sync()

    def on_feature(self, fid, value):
        self.session.set_feature(fid, value)
        self.sync()

    def launch_game(self):
        if self.session.state != "absent":
            return
        try:
            os.startfile(f"steam://rungameid/{self.game.steam_appid}")
        except OSError:
            d = self.app.install_dir(self.game)
            if d:
                subprocess.Popen([os.path.join(d, self.game.exe)], cwd=d)

    def open_folder(self):
        d = self.session.install_dir or self.app.install_dir(self.game)
        if d and os.path.isdir(d):
            os.startfile(d)

    def sync(self):
        s = self.session
        if s.state == "ok":
            self.status.config(text=f"●  遊戲執行中  ·  PID {s.proc.pid}", fg=C["green"])
        elif s.state == "mismatch":
            self.status.config(text=f"●  遊戲版本不符（需要 {self.game.version_label}），功能已停用", fg=C["amber"])
        elif s.state == "denied":
            self.status.config(text=f"●  找到遊戲但無法存取：{s.error}", fg=C["amber"])
        else:
            self.status.config(text="●  未偵測到遊戲  ·  每秒自動偵測", fg=C["ink3"])

        self.master_toggle.set(s.master)
        if s.master and s.state == "ok":
            self.master_desc.config(text="已開啟 — 下方開啟的功能會持續生效。", fg=C["green"])
        elif s.master:
            self.master_desc.config(text="已開啟 — 等待遊戲啟動後自動套用。", fg=C["amber"])
        else:
            self.master_desc.config(text="已關閉 — 不會對遊戲做任何修改。", fg=C["ink2"])
        for fid, tog in self.feature_toggles.items():
            tog.set(s.enabled[fid], muted=not s.active)
        for card in self.setting_cards:
            card.sync()

        if s.info:
            self.info.config(text="\n".join(f"{k}　{v}" for k, v in s.info.items()))
        else:
            self.info.config(text="遊戲執行後會在這裡顯示即時數值。")

    def refresh_chips(self):
        self.master_chip.refresh()
        for chip in self.feature_chips.values():
            chip.refresh()
        for card in self.setting_cards:
            card.refresh_chips()


# ---- 下拉選單與設定 --------------------------------------------------------
class Dropdown:
    """點齒輪展開的下拉選單（place 在主視窗上，點其他地方自動收起）。"""

    def __init__(self, root, anchor, items):
        self.root, self.anchor = root, anchor
        self.frame = tk.Frame(root, bg=C["card"], highlightthickness=1, highlightbackground=C["line"])
        for label, command in items:
            row = tk.Label(self.frame, text=label, bg=C["card"], fg=C["ink"], font=F["body"],
                           anchor="w", padx=18, pady=9, width=14, cursor="hand2")
            row.pack(fill="x")
            row.bind("<Enter>", lambda e, r=row: r.config(bg=C["card_alt"]))
            row.bind("<Leave>", lambda e, r=row: r.config(bg=C["card"]))
            row.bind("<Button-1>", lambda e, cmd=command: (self.hide(), cmd()))
        self.visible = False

    def contains(self, widget):
        w = widget
        while w is not None:
            if w in (self.frame, self.anchor):
                return True
            w = getattr(w, "master", None)
        return False

    def toggle(self):
        self.hide() if self.visible else self.show()

    def show(self):
        self.frame.update_idletasks()
        x = self.anchor.winfo_rootx() - self.root.winfo_rootx() + self.anchor.winfo_width() - self.frame.winfo_reqwidth()
        y = self.anchor.winfo_rooty() - self.root.winfo_rooty() + self.anchor.winfo_height() + 6
        self.frame.place(x=x, y=y)
        self.frame.lift()
        self.visible = True

    def hide(self):
        self.frame.place_forget()
        self.visible = False


class SettingsDialog(tk.Toplevel):
    """設定視窗：Steam 遊戲庫路徑（自動偵測 + 多個自訂路徑）。"""

    def __init__(self, app):
        super().__init__(app.root, bg=C["bg"])
        self.app = app
        self.title("設定")
        self.transient(app.root)
        self.resizable(False, True)
        w, h = 720, 640
        rx, ry = app.root.winfo_rootx(), app.root.winfo_rooty()
        self.geometry(f"{w}x{h}+{rx + (app.root.winfo_width() - w) // 2}+{ry + 60}")
        self.minsize(w, 420)

        head = tk.Frame(self, bg=C["nav"])
        head.pack(fill="x")
        tk.Label(head, text="設定", bg=C["nav"], fg=C["nav_fg"], font=(SANS, 14, "bold")).pack(
            side="left", padx=24, pady=14)

        foot = tk.Frame(self, bg=C["bg"])
        foot.pack(side="bottom", fill="x", padx=24, pady=16)
        flat_button(foot, "儲存並重新掃描", self.save, C["orange"], "white", C["orange_hover"]).pack(side="right")
        flat_button(foot, "取消", self.destroy, C["card"], C["ink"], C["card_alt"]).pack(side="right", padx=(0, 10))
        tk.Frame(self, bg=C["line"], height=1).pack(side="bottom", fill="x")

        body = tk.Frame(self, bg=C["bg"])
        body.pack(fill="both", expand=True, padx=24, pady=(20, 8))
        tk.Label(body, text="Steam 遊戲庫", bg=C["bg"], fg=C["ink"], font=F["section"]).pack(anchor="w")
        tk.Label(body, text="可以填 Steam 安裝目錄，或任何含有 steamapps 的遊戲庫資料夾。"
                                      "封面圖片只存在 Steam 安裝目錄裡，只加入遊戲庫時會列出遊戲但沒有圖片。",
                 bg=C["bg"], fg=C["ink2"], font=F["small"], wraplength=660, justify="left").pack(anchor="w", pady=(4, 12))

        # 自動偵測
        auto = tk.Frame(body, bg=C["card"], highlightthickness=1, highlightbackground=C["line"])
        auto.pack(fill="x")
        auto_in = tk.Frame(auto, bg=C["card"])
        auto_in.pack(fill="x", padx=16, pady=12)
        self.auto_toggle = Toggle(auto_in, self._on_auto)
        self.auto_toggle.pack(side="right")
        tk.Label(auto_in, text="自動偵測 Steam 安裝位置", bg=C["card"], fg=C["ink"],
                 font=F["btn"]).pack(anchor="w")
        root = steam.steam_root()
        self.auto_info = tk.Label(auto_in, bg=C["card"], fg=C["ink3"], font=F["small"], anchor="w", justify="left",
                                  text=(f"{root}　·　{steam.inspect(root)[1]}" if root else "這台電腦上找不到 Steam"))
        self.auto_info.pack(anchor="w", pady=(2, 0))
        self.auto_toggle.set(app.cfg.steam_autodetect())

        # 自訂路徑
        bar = tk.Frame(body, bg=C["bg"])
        bar.pack(fill="x", pady=(18, 8))
        tk.Label(bar, text="自訂路徑", bg=C["bg"], fg=C["ink"], font=F["btn"]).pack(side="left")
        flat_button(bar, "+  新增路徑", self.add_row, C["yellow"], C["ink"], C["yellow_hover"],
                    font=(SANS, 9, "bold"), padx=12, pady=4).pack(side="right")

        self.list_area = ScrollArea(body)
        self.list_area.body.pack_configure(padx=0)
        self.list_area.pack(fill="both", expand=True)
        self.list_area.canvas.bind("<Configure>", self._list_resize)  # 取代置中邏輯，填滿寬度
        self.empty = tk.Label(self.list_area.body, text="尚未加入自訂路徑。按「+ 新增路徑」加入。",
                              bg=C["bg"], fg=C["ink3"], font=F["small"])
        self.rows = []
        for p in app.cfg.steam_paths():
            self.add_row(p, focus=False)
        self._refresh_empty()

        self.bind("<MouseWheel>", lambda e: (self.list_area.wheel(e), "break")[1])  # 不要捲到後面的主頁
        self.bind("<Escape>", lambda e: self.destroy())
        self.grab_set()
        self.focus_set()

    def _list_resize(self, e):
        self.list_area.canvas.itemconfigure(self.list_area.win, width=e.width)

    def _on_auto(self, value):
        self.auto_info.config(fg=C["ink3"] if value else C["off"])

    def _refresh_empty(self):
        if self.rows:
            self.empty.pack_forget()
        else:
            self.empty.pack(anchor="w", pady=6)

    def add_row(self, path="", focus=True):
        row = tk.Frame(self.list_area.body, bg=C["card"], highlightthickness=1, highlightbackground=C["line"])
        row.pack(fill="x", pady=(0, 8))
        inner = tk.Frame(row, bg=C["card"])
        inner.pack(fill="x", padx=12, pady=10)
        var = tk.StringVar(value=path)
        minus = flat_button(inner, "−", lambda: self.remove_row(row), C["card_alt"], C["ink"], "#F6D5CB",
                            font=(SANS, 12, "bold"), padx=11, pady=0)
        minus.pack(side="right", padx=(8, 0))
        browse = flat_button(inner, "瀏覽…", lambda: self._browse(var), C["card_alt"], C["ink"], C["line"],
                             font=(SANS, 9), padx=10, pady=3)
        browse.pack(side="right", padx=(8, 0))
        col = tk.Frame(inner, bg=C["card"])
        col.pack(side="left", fill="x", expand=True)
        entry = tk.Entry(col, textvariable=var, font=F["body"], bd=0, bg=C["card_alt"], fg=C["ink"],
                         insertbackground=C["ink"], highlightthickness=1, highlightbackground=C["line"],
                         highlightcolor=C["orange"])
        entry.pack(fill="x", ipady=5)
        status = tk.Label(col, text="", bg=C["card"], font=F["small"], anchor="w")
        status.pack(fill="x", pady=(4, 0))
        item = {"frame": row, "var": var, "status": status, "job": None}
        var.trace_add("write", lambda *_: self._schedule_check(item))
        self.rows.append(item)
        self._check(item)
        self._refresh_empty()
        if focus:
            entry.focus_set()
            self.list_area.canvas.update_idletasks()
            self.list_area.canvas.yview_moveto(1.0)

    def remove_row(self, frame):
        self.rows = [r for r in self.rows if r["frame"] is not frame]
        frame.destroy()
        self._refresh_empty()

    def _browse(self, var):
        from tkinter import filedialog
        start = steam.normalize(var.get()) if var.get().strip() else (steam.steam_root() or "C:\\")
        path = filedialog.askdirectory(parent=self, title="選擇 Steam 安裝目錄或遊戲庫資料夾",
                                       initialdir=start if os.path.isdir(start) else "C:\\", mustexist=True)
        if path:
            var.set(os.path.normpath(path))

    def _schedule_check(self, item):
        if item["job"]:
            self.after_cancel(item["job"])
        item["job"] = self.after(300, lambda: self._check(item))

    def _check(self, item):
        item["job"] = None
        ok, msg = steam.inspect(item["var"].get())
        item["status"].config(text=("✓  " if ok else "✗  ") + msg, fg=C["green"] if ok else C["orange"])
        item["ok"] = ok

    def save(self):
        paths = []
        for r in self.rows:
            p = r["var"].get().strip()
            if p and steam.normalize(p).lower() not in (steam.normalize(x).lower() for x in paths):
                paths.append(steam.normalize(p))
        self.app.cfg.set_steam(paths, self.auto_toggle.state)
        self.destroy()
        self.app.rescan()


# ---- 主程式 ----------------------------------------------------------------
TK_KEY_NAMES = {"Prior": "PgUp", "Next": "PgDn", "Return": "Enter", "Escape": "Esc", "Delete": "Del",
                "Insert": "Ins", "space": "Space", "Tab": "Tab", "Home": "Home", "End": "End",
                "Up": "↑", "Down": "↓", "Left": "←", "Right": "→", "Pause": "Pause", "Scroll_Lock": "ScrLk"}
MODIFIERS = {"Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R", "Win_L", "Win_R", "Caps_Lock"}


def key_label(event):
    ks = event.keysym
    if ks.startswith("KP_"):
        return "Num " + ks[3:]
    if ks in TK_KEY_NAMES:
        return TK_KEY_NAMES[ks]
    if len(ks) == 1:
        return ks.upper()
    return ks


class App:
    def __init__(self, root):
        self.root = root
        self.cfg = Config(CONFIG_PATH)
        self.sessions = {g.id: Session(g, self.cfg) for g in GAMES}
        self.steam_games = {}
        self.libraries = []
        self.art_roots = []
        self.rescan_pending = False
        self.menu = None
        self.scan_done = False
        self.capturing = None
        self.key_down = {}
        self.key_repeat = {}
        self.pages = {}
        self.current = None
        self.supported_cards = {}
        self.other_cards = {}
        self.art = {}
        self.ui_queue = queue.Queue()
        self.scanning = False

        root.title("Trainer Hub")
        root.configure(bg=C["bg"])
        root.minsize(1000, 680)
        w, h = 1180, 820
        root.geometry(f"{w}x{h}+{(root.winfo_screenwidth() - w) // 2}+{max(0, (root.winfo_screenheight() - h) // 2 - 30)}")

        self._build_chrome()
        self.library = LibraryPage(self.container, self)
        for g in GAMES:
            card = GameCard(self.library.grid_supported, g.name, "", C["ink3"],
                            on_click=lambda g=g: self.show_trainer(g.id))
            self.supported_cards[g.id] = card
            self.library.add_card(card, "supported")
        self.library.layout()
        self.show_library()

        root.protocol("WM_DELETE_WINDOW", self.on_close)
        root.bind_all("<MouseWheel>", lambda e: self.current and self.current.wheel(e))
        root.bind("<KeyPress>", self._on_key)
        root.bind("<Button-1>", self._on_root_click, add="+")

        self.detect()
        self.tick()
        self._drain_queue()
        self.rescan()

    def _on_root_click(self, e):
        if self.menu and not self.menu.contains(e.widget):
            self.menu.hide()
        if e.widget is not self.library.entry:
            self.root.focus_set()

    # --- 外框 ---
    def _build_chrome(self):
        nav = tk.Frame(self.root, bg=C["nav"], height=54)
        nav.pack(fill="x")
        nav.pack_propagate(False)
        logo = tk.Label(nav, text="◧  Trainer Hub", bg=C["nav"], fg=C["nav_fg"], font=F["logo"], cursor="hand2")
        logo.pack(side="left", padx=(22, 26))
        logo.bind("<Button-1>", lambda e: self.show_library())
        lib = tk.Label(nav, text="遊戲庫", bg=C["nav"], fg=C["nav_fg"], font=F["nav"], cursor="hand2")
        lib.pack(side="left", padx=10)
        lib.bind("<Button-1>", lambda e: self.show_library())
        self.nav_game = tk.Label(nav, text="", bg=C["nav"], fg=C["nav_dim"], font=F["nav"])
        self.nav_game.pack(side="left")
        self.gear = flat_button(nav, "⚙", lambda: self.menu.toggle(), C["nav"], C["nav_fg"], "#3A3A3A",
                                font=("Segoe UI Symbol", 14), padx=10, pady=0)
        self.gear.pack(side="right", padx=(4, 14))
        flat_button(nav, "重新掃描", self.rescan, C["yellow"], C["ink"], C["yellow_hover"],
                    font=(SANS, 9, "bold"), padx=14, pady=5).pack(side="right", padx=(8, 4))
        self.nav_active = tk.Label(nav, text="", bg=C["nav"], fg=C["nav_dim"], font=F["small"])
        self.nav_active.pack(side="right", padx=8)

        bar = tk.Frame(self.root, bg=C["yellow"])
        bar.pack(fill="x", padx=12, pady=(0, 0))
        inner = tk.Frame(bar, bg=C["yellow"])
        inner.pack(pady=6)
        names = "、".join(f"{g.name} {g.version_label}" for g in GAMES)
        tk.Label(inner, text=f"目前支援：{names}　·　更多遊戲開發中", bg=C["yellow"], fg=C["ink"],
                 font=F["announce"]).pack(side="left", padx=(0, 10))
        chip = tk.Label(inner, text="開啟", bg=C["black_chip"], fg="white", font=(SANS, 8, "bold"),
                        padx=8, pady=2, cursor="hand2")
        chip.pack(side="left")
        chip.bind("<Button-1>", lambda e: self.show_trainer(GAMES[0].id))

        self.container = tk.Frame(self.root, bg=C["bg"])
        self.container.pack(fill="both", expand=True)

        self.menu = Dropdown(self.root, self.gear, [("⚙   設定", self.open_settings)])

    def open_settings(self):
        SettingsDialog(self)

    # --- 頁面切換 ---
    def _show(self, page):
        if self.current is page:
            return
        if self.current:
            self.current.pack_forget()
        self.current = page
        page.pack(fill="both", expand=True)
        page.top()

    def show_library(self):
        self.cancel_capture()
        self.nav_game.config(text="")
        self._show(self.library)

    def show_trainer(self, game_id):
        self.cancel_capture()
        if game_id not in self.pages:
            page = TrainerPage(self.container, self, self.sessions[game_id])
            self.pages[game_id] = page
            self._apply_art_to_page(game_id)
        self.nav_game.config(text=f"›   {self.sessions[game_id].game.name}")
        self._show(self.pages[game_id])

    # --- Steam 與圖片 ---
    def install_dir(self, game):
        info = self.steam_games.get(game.steam_appid)
        return info["dir"] if info else None

    def rescan(self):
        if self.scanning:
            self.rescan_pending = True  # 掃描完成後再掃一次（例如掃描中儲存了新設定）
            return
        self.scanning = True
        args = (self.cfg.steam_paths(), self.cfg.steam_autodetect())
        threading.Thread(target=self._scan_steam, args=args, daemon=True).start()

    def _art_jobs(self, games, art_roots):
        jobs = []
        supported_ids = {g.steam_appid: g for g in GAMES}
        # 已支援的遊戲排前面，先轉換
        for appid, info in sorted(games.items(), key=lambda kv: kv[0] not in supported_ids):
            g = supported_ids.get(appid)
            cap, mode = steam.find_art(art_roots, appid, "capsule"), "cover"
            if not cap and g and g.fallback_art:
                p = os.path.join(info["dir"], g.fallback_art)
                cap = p if os.path.isfile(p) else None
            if not cap:  # 沒有直式封面時，把橫式標頭圖置中顯示
                cap, mode = steam.find_art(art_roots, appid, "header"), "contain"
            if cap:
                dst = os.path.join(CACHE_DIR, f"{appid}_card{'' if g else '_gray'}.png")
                jobs.append(((appid, "capsule"), dict(src=cap, dst=dst, w=CARD_W, h=CARD_H, mode=mode, gray=not g)))
            if g:
                hero = steam.find_art(art_roots, appid, "hero")
                if hero:
                    dst = os.path.join(CACHE_DIR, f"{appid}_hero.png")
                    jobs.append(((appid, "hero"), dict(src=hero, dst=dst, w=CONTENT_W, h=HERO_H, mode="cover")))
                logo = steam.find_art(art_roots, appid, "logo")
                if logo:
                    dst = os.path.join(CACHE_DIR, f"{appid}_logo.png")
                    jobs.append(((appid, "logo"), dict(src=logo, dst=dst, w=360, h=200, mode="contain")))
        return jobs

    def _scan_steam(self, custom_paths, autodetect):
        """背景執行緒：掃描 Steam → 通知介面建立卡片 → 逐張轉換圖片。"""
        libraries, art_roots = steam.resolve(custom_paths, autodetect)
        games = steam.installed_games(libraries)
        for g in GAMES:  # 不是透過 Steam 安裝時也要顯示
            games.setdefault(g.steam_appid, {"appid": g.steam_appid, "name": g.name, "dir": ""})
        self.ui_queue.put(("games", games, libraries, art_roots))
        for key, job in self._art_jobs(games, art_roots):
            if imaging.convert(**job):
                self.ui_queue.put(("art", key, job["dst"]))
        self.ui_queue.put(("done",))

    def _drain_queue(self):
        try:
            while True:
                msg = self.ui_queue.get_nowait()
                if msg[0] == "games":
                    self.libraries, self.art_roots = msg[2], msg[3]
                    self._on_games(msg[1])
                elif msg[0] == "art":
                    self._on_art(msg[1], msg[2])
                elif msg[0] == "done":
                    self.scanning = False
                    if self.rescan_pending:
                        self.rescan_pending = False
                        self.rescan()
        except queue.Empty:
            pass
        self.root.after(80, self._drain_queue)

    def _on_games(self, games):
        self.steam_games = games
        self.scan_done = True
        supported = {g.steam_appid for g in GAMES}
        self.library.cards = [(c, s) for c, s in self.library.cards if s == "supported"]
        for card in self.other_cards.values():
            card.destroy()
        self.other_cards = {}
        for appid, info in sorted(games.items(), key=lambda kv: kv[1]["name"].lower()):
            if appid in supported:
                continue
            card = GameCard(self.library.grid_other, info["name"], "尚未支援", C["ink3"])
            self.other_cards[appid] = card
            self.library.add_card(card, "other")
        self.library.layout()

    def _on_art(self, key, path):
        self.art[key] = path
        appid, kind = key
        if kind == "capsule":
            card = self.other_cards.get(appid) or next(
                (self.supported_cards[g.id] for g in GAMES if g.steam_appid == appid), None)
            if card:
                card.set_image(path)
        else:
            for g in GAMES:
                if g.steam_appid == appid:
                    self._apply_art_to_page(g.id)

    def _apply_art_to_page(self, game_id):
        page = self.pages.get(game_id)
        if not page:
            return
        appid = page.game.steam_appid
        page.set_art(self.art.get((appid, "hero")), self.art.get((appid, "logo")))

    # --- 快捷鍵 ---
    def begin_capture(self, chip):
        self.cancel_capture()
        self.capturing = chip
        chip.refresh(capturing=True)
        self.root.focus_force()

    def cancel_capture(self):
        if self.capturing:
            chip, self.capturing = self.capturing, None
            chip.refresh()

    def _on_key(self, event):
        chip = self.capturing
        if not chip:
            return
        if event.keysym in MODIFIERS:
            return
        if event.keysym == "Escape":
            self.cancel_capture()
            return
        if event.keysym in ("BackSpace", "Delete"):
            self.cfg.set_hotkey(chip.key_id, None)
        else:
            value = (event.keycode, key_label(event))
            for key in self._all_hotkey_ids():  # 同一個按鍵只能綁一個功能
                if key != chip.key_id and self._hotkey_of(key) and self._hotkey_of(key)[0] == value[0]:
                    self.cfg.set_hotkey(key, None)
            self.cfg.set_hotkey(chip.key_id, value)
            self.key_down[value[0]] = True  # 避免設定時立刻觸發
        self.cancel_capture()
        for page in self.pages.values():
            page.refresh_chips()

    def _all_hotkey_ids(self):
        for g in GAMES:
            yield f"{g.id}.master"
            for f in g.features:
                yield f"{g.id}.{f.id}"
            for st in g.settings:
                yield f"{g.id}.{st.id}.dec"
                yield f"{g.id}.{st.id}.inc"

    def _hotkey_of(self, key_id):
        parts = key_id.split(".")
        g = self.sessions[parts[0]].game
        if parts[1] == "master":
            return self.cfg.hotkey(key_id, g.master_key)
        if len(parts) == 3:
            st = next(st for st in g.settings if st.id == parts[1])
            return self.cfg.hotkey(key_id, st.inc_key if parts[2] == "inc" else st.dec_key)
        f = next(f for f in g.features if f.id == parts[1])
        return self.cfg.hotkey(key_id, f.default_key)

    def _poll_hotkeys(self):
        if self.capturing:
            return
        now = time.monotonic()
        for key_id in self._all_hotkey_ids():
            hk = self._hotkey_of(key_id)
            if not hk:
                continue
            vk = hk[0]
            down = bool(user32.GetAsyncKeyState(vk) & 0x8000)
            was = self.key_down.get(vk, False)
            self.key_down[vk] = down
            if down and not was:
                self._fire(key_id)
                self.key_repeat[vk] = now + HOLD_DELAY
            elif down and key_id.endswith((".inc", ".dec")) and now >= self.key_repeat.get(vk, now + 1):
                self._fire(key_id, quiet=True)  # 按住不放時連續調整
                self.key_repeat[vk] = now + HOLD_REPEAT

    def _fire(self, key_id, quiet=False):
        parts = key_id.split(".")
        s = self.sessions[parts[0]]
        if parts[1] == "master":
            s.set_master(not s.master)
            beep(s.master)
        elif len(parts) == 3:
            delta = 1 if parts[2] == "inc" else -1
            old = s.values[parts[1]]
            new = s.set_value(parts[1], old + delta)
            if not quiet and new != old:
                beep_value(new)
        else:
            s.set_feature(parts[1], not s.enabled[parts[1]])
            beep(s.enabled[parts[1]])
        self._sync_views()

    def on_close(self):
        for s in self.sessions.values():
            s.restore()
        self.root.destroy()

    # --- 迴圈 ---
    def _sync_views(self):
        for page in self.pages.values():
            page.sync()
        active = [s.game.name for s in self.sessions.values() if s.active]
        self.nav_active.config(text=f"●  修改器運作中：{'、'.join(active)}" if active else "",
                               fg=C["orange"] if active else C["nav_dim"])
        for gid, card in self.supported_cards.items():
            s = self.sessions[gid]
            if s.active:
                card.set_sub(f"● 修改器運作中  ·  {s.game.version_label}", C["orange"])
            elif s.state == "ok":
                card.set_sub(f"● 執行中  ·  {s.game.version_label}", C["green"])
            else:
                card.set_sub(f"已支援  ·  {s.game.version_label}", C["ink3"])

    def detect(self):
        for s in self.sessions.values():
            s.detect()
        self._sync_views()
        self.root.after(DETECT_MS, self.detect)

    def tick(self):
        self._poll_hotkeys()
        for s in self.sessions.values():
            s.tick()
        self.root.after(TICK_MS, self.tick)


def main():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass
    root = tk.Tk()
    try:
        App(root)
    except Exception:
        with open(ERROR_LOG, "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        raise
    root.report_callback_exception = lambda *a: open(ERROR_LOG, "a", encoding="utf-8").write(
        "".join(traceback.format_exception(*a)))
    root.mainloop()


if __name__ == "__main__":
    main()
