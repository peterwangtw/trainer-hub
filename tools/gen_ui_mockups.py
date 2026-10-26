"""產生 Trainer Hub 的 UI/UX 設計稿（SVG，Figma 風格：假資料 + 標線 + 註解）。

用法（在 repo 根目錄）：python tools\\gen_ui_mockups.py   → 輸出到 docs\\ui\\*.svg
設計值與 app/main.py 的 C / F 常數一致；改設計時兩邊一起改。一律使用假資料。
"""
import os

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "ui")

SANS = "'Microsoft JhengHei UI','Microsoft JhengHei','Noto Sans TC',sans-serif"
SERIF = "Georgia,serif"
MONO = "Consolas,monospace"

C = {
    "bg": "#ECEBE7", "dot": "#D3D1CB", "nav": "#202020", "nav_fg": "#F5F5F2", "nav_dim": "#9C9A95",
    "ink": "#0E0E0E", "ink2": "#5D5B56", "ink3": "#8F8D88", "line": "#D8D6D0",
    "card": "#FFFFFF", "card_alt": "#F6F5F2", "placeholder": "#DAD8D2",
    "orange": "#F04E23", "orange_hover": "#D63F17", "yellow": "#FFF78B", "yellow_hover": "#F5EC6E",
    "green": "#2E9B57", "amber": "#C77700", "off": "#C8C6C0", "muted": "#F4A58F",
}
RED = "#E8368F"        # 標線顏色（Figma redline）
CANVAS = "#E4E4E4"     # 畫布底色
PAD = 80               # 畫框外留白
NOTE_W = 380           # 右側註解欄寬


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def tw(s, size):
    """估算文字寬度（CJK 全形、拉丁半形）。"""
    return sum(size * (1.0 if ord(ch) > 0x2E80 else 0.56) for ch in s)


class Svg:
    def __init__(self, w, h):
        self.w, self.h, self.items, self.defs = w, h, [], []
        self.defs.append(
            f'<pattern id="dots" width="18" height="18" patternUnits="userSpaceOnUse">'
            f'<rect x="10" y="10" width="1.5" height="1.5" fill="{C["dot"]}"/></pattern>')

    def add(self, s):
        self.items.append(s)

    def rect(self, x, y, w, h, fill="none", stroke=None, rx=0, sw=1, dash=None, opacity=None):
        a = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
        a += f' stroke-dasharray="{dash}"' if dash else ""
        a += f' opacity="{opacity}"' if opacity is not None else ""
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}"{a}/>')

    def text(self, x, y, s, size=13, fill=None, weight=400, anchor="start", family=SANS, italic=False):
        st = ' font-style="italic"' if italic else ""
        self.add(f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" font-weight="{weight}" '
                 f'fill="{fill or C["ink"]}" text-anchor="{anchor}"{st}>{esc(s)}</text>')

    def line(self, x1, y1, x2, y2, stroke, sw=1, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" stroke-width="{sw}"{d}/>')

    def circle(self, x, y, r, fill, stroke=None):
        s = f' stroke="{stroke}"' if stroke else ""
        self.add(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}"{s}/>')

    def save(self, name):
        os.makedirs(OUT, exist_ok=True)
        body = "\n".join(self.items)
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
               f'viewBox="0 0 {self.w} {self.h}"><defs>{"".join(self.defs)}</defs>'
               f'<rect width="100%" height="100%" fill="{CANVAS}"/>\n{body}\n</svg>')
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
            f.write(svg)
        print("wrote", name)


# ---- 標註 -----------------------------------------------------------------
def label_pill(s, cx, cy, text):
    w = tw(text, 11) + 10
    s.rect(cx - w / 2, cy - 9, w, 18, RED, rx=3)
    s.text(cx, cy + 4, text, 11, "#FFFFFF", 700, "middle")


def dim_h(s, x1, x2, y, text):
    s.line(x1, y, x2, y, RED)
    s.line(x1, y - 5, x1, y + 5, RED)
    s.line(x2, y - 5, x2, y + 5, RED)
    label_pill(s, (x1 + x2) / 2, y, text)


def dim_v(s, y1, y2, x, text):
    s.line(x, y1, x, y2, RED)
    s.line(x - 5, y1, x + 5, y1, RED)
    s.line(x - 5, y2, x + 5, y2, RED)
    label_pill(s, x, (y1 + y2) / 2, text)


def callout(s, x, y, n):
    s.circle(x, y, 11, RED)
    s.text(x, y + 4, str(n), 12, "#FFFFFF", 700, "middle")


def frame_title(s, x, y, title, size):
    s.text(x, y - 14, title, 14, "#555555", 700)
    s.text(x + tw(title, 14) + 12, y - 14, size, 12, "#888888")


def notes(s, x, y, items, title="註解"):
    s.text(x, y, title, 15, C["ink"], 700)
    yy = y + 30
    for i, (head, body) in enumerate(items, 1):
        callout(s, x + 11, yy - 4, i)
        s.text(x + 30, yy, head, 13, C["ink"], 700)
        yy += 20
        for ln in body:
            s.text(x + 30, yy, ln, 12, C["ink2"])
            yy += 18
        yy += 14


# ---- 元件 -----------------------------------------------------------------
def nav(s, x, y, w, crumb=None, active=None):
    s.rect(x, y, w, 54, C["nav"])
    s.text(x + 24, y + 33, "◧  Trainer Hub", 16, C["nav_fg"], 700)
    s.text(x + 186, y + 32, "遊戲庫", 13, C["nav_fg"])
    if crumb:
        s.text(x + 236, y + 32, f"›   {crumb}", 13, C["nav_dim"])
    s.text(x + w - 30, y + 34, "⚙", 18, C["nav_fg"], 400, "middle")
    button(s, x + w - 60 - 96, y + 13, "重新掃描", "secondary", w=96, h=28, size=12)
    if active:
        t = f"●  修改器運作中：{active}"
        s.text(x + w - 60 - 96 - 16, y + 32, t, 11, C["orange"], 400, "end")


def button(s, x, y, text, kind="primary", w=None, h=34, size=13):
    fill, fg, stroke = {
        "primary": (C["orange"], "#FFFFFF", None),
        "primary_hover": (C["orange_hover"], "#FFFFFF", None),
        "secondary": (C["yellow"], C["ink"], None),
        "neutral": (C["card"], C["ink"], None),
        "subtle": (C["card_alt"], C["ink"], None),
    }[kind]
    w = w or tw(text, size) + 32
    s.rect(x, y, w, h, fill, stroke)
    s.text(x + w / 2, y + h / 2 + size * 0.36, text, size, fg, 700, "middle")
    return w


def toggle(s, x, y, on=False, muted=False, w=48, h=26):
    col = (C["muted"] if muted else C["orange"]) if on else C["off"]
    s.rect(x, y, w, h, col, rx=h / 2)
    kx = x + w - h / 2 if on else x + h / 2
    s.circle(kx, y + h / 2, h / 2 - 3, "#FFFFFF")


def chip(s, x, y, text, state="default"):
    fill = C["yellow"] if state == "capture" else C["card_alt"]
    w = tw(text, 12) + 22
    s.rect(x, y, w, 30, fill, C["line"])
    s.text(x + w / 2, y + 19.5, text, 12, C["ink"], 700, "middle")
    return w


def placeholder(s, x, y, w, h, label, dark=False):
    fill = "#2A2A2A" if dark else C["placeholder"]
    cross = "#3A3A3A" if dark else "#C9C7C0"
    s.rect(x, y, w, h, fill)
    s.line(x, y, x + w, y + h, cross)
    s.line(x + w, y, x, y + h, cross)
    lw = tw(label, 11) + 12
    s.rect(x + w / 2 - lw / 2, y + h / 2 - 10, lw, 20, "#FFFFFF" if not dark else "#1B1B1B", rx=3)
    s.text(x + w / 2, y + h / 2 + 4, label, 11, C["ink3"] if not dark else "#AAAAAA", 400, "middle")


def card(s, x, y, name, sub, sub_color, state="default", art="封面 180×270"):
    border = C["orange"] if state == "hover" else C["line"]
    s.rect(x, y, 182, 330, C["card"], border, sw=1.5 if state == "hover" else 1)
    if state == "noart":
        s.rect(x + 1, y + 1, 180, 270, C["placeholder"])
        s.text(x + 91, y + 140, name, 13, C["ink2"], 700, "middle")
    else:
        placeholder(s, x + 1, y + 1, 180, 270, art)
        if state == "unsupported":
            s.rect(x + 1, y + 1, 180, 270, "#808080", opacity=0.35)
    s.text(x + 14, y + 296, name, 13, C["ink"], 700)
    s.text(x + 14, y + 316, sub, 11, sub_color)


def section(s, x, y, w, title, count):
    s.text(x, y, title, 16, C["ink"], 700)
    cx = x + tw(title, 16) + 10
    s.text(cx, y, str(count), 12, C["ink3"])
    s.line(cx + 22, y - 5, x + w, y - 5, C["line"])


def feature_card(s, x, y, w, title, desc, key, on, muted=False):
    s.rect(x, y, w, 88, C["card"], C["line"])
    s.text(x + 26, y + 36, title, 16, C["ink"], 700)
    s.text(x + 26, y + 62, desc, 12, C["ink2"])
    toggle(s, x + w - 26 - 48, y + 31, on, muted)
    cw = tw(f"快捷鍵  {key}", 12) + 22
    chip(s, x + w - 26 - 48 - 16 - cw, y + 29, f"快捷鍵  {key}")


def slider_card(s, x, y, w, value=11, maximum=50, active=True):
    s.rect(x, y, w, 158, C["card"], C["line"])
    s.text(x + 26, y + 38, "數值型功能名稱", 16, C["ink"], 700)
    w2 = tw("增加  PgUp", 12) + 22
    w1 = tw("減少  PgDn", 12) + 22
    chip(s, x + w - 26 - w2, y + 18, "增加  PgUp")
    chip(s, x + w - 26 - w2 - 8 - w1, y + 18, "減少  PgDn")
    s.text(x + 26, y + 66, "1 為原本的數值，數字代表倍率（例如 11 = 原本 ×11）。", 12, C["ink2"])
    ry = y + 96
    button(s, x + 26, ry, "−", "subtle", w=40, h=30, size=16)
    tx1, tx2 = x + 26 + 40 + 14, x + w - 26 - 18 - 54 - 14 - 40 - 14
    s.rect(tx1, ry + 10, tx2 - tx1, 10, C["off"])
    kx = tx1 + (tx2 - tx1 - 22) * (value - 1) / (maximum - 1)
    s.rect(kx, ry + 7, 22, 16, C["orange"] if active and value > 1 else (C["muted"] if value > 1 else C["ink3"]))
    button(s, tx2 + 14, ry, "+", "subtle", w=40, h=30, size=14)
    s.rect(x + w - 26 - 18 - 54, ry - 2, 54, 34, C["card_alt"], C["line"])
    s.text(x + w - 26 - 18 - 27, ry + 21, str(value), 17, C["ink"], 700, "middle")
    s.text(x + w - 26 - 9, ry + 20, "×", 15, C["ink2"], 400, "middle")
    s.text(tx1, ry + 46, "1（原速）", 11, C["ink3"])
    s.text(tx2, ry + 46, str(maximum), 11, C["ink3"], 400, "end")
    return kx, tx1, tx2, ry


def status(s, x, y, text, color):
    s.circle(x + 5, y - 4, 5, color)
    s.text(x + 18, y, text, 12, color, 700)


# ---- 畫面 -----------------------------------------------------------------
def screen_library():
    W, H = 1180, 820
    s = Svg(PAD * 2 + W + NOTE_W, PAD + H + 60)
    fx, fy = PAD, PAD
    frame_title(s, fx, fy, "01 · 遊戲庫", "1180 × 820（預設視窗）")
    s.rect(fx, fy, W, H, C["bg"])
    nav(s, fx, fy, W, active=None)
    # hero
    s.rect(fx, fy + 54, W, 230, "url(#dots)")
    cx = fx + W / 2
    s.text(cx, fy + 54 + 84, "選擇要測試的遊戲", 36, C["ink"], 700, "middle")
    s.text(cx, fy + 54 + 122, "點選遊戲進入修改器設定。修改器只在你開啟時才會寫入遊戲記憶體。", 14, C["ink2"], 400, "middle")
    s.rect(cx - 180, fy + 54 + 152, 360, 40, C["card"], C["line"])
    s.text(cx - 164, fy + 54 + 178, "⌕   搜尋遊戲名稱", 13, C["ink3"])
    L = fx + 70
    section(s, L, fy + 320, 1040, "已支援的遊戲", 2)
    card(s, L, fy + 340, "Sample Game", "●  執行中 · Ver.1.0", C["green"])
    card(s, L + 202, fy + 340, "Another Game", "已支援 · Ver.2.3", C["ink3"], state="hover")
    section(s, L, fy + 712, 1040, "Steam 已安裝 · 尚未支援", 24)
    s.add(f'<clipPath id="clipL"><rect x="{fx}" y="{fy}" width="{W}" height="{H}"/></clipPath>')
    s.add('<g clip-path="url(#clipL)">')
    for i in range(5):
        st = "noart" if i == 3 else "unsupported"
        card(s, L + i * 202, fy + 732, f"Game Title {i + 1:02d}", "尚未支援", C["ink3"], state=st)
    s.add("</g>")
    # 標線
    dim_v(s, fy, fy + 54, fx - 24, "54")
    dim_h(s, fx, L, fy + 300, "70")
    dim_h(s, L, L + 1040, fy + 296 - 30 + 40, "內容最大寬 1040（置中）")
    dim_v(s, fy + 54, fy + 284, fx + W + 24, "230")
    dim_h(s, L, L + 182, fy + 682, "180")
    dim_h(s, L + 182, L + 202, fy + 682, "20")
    dim_v(s, fy + 340, fy + 610, L - 24, "270")
    # 編號
    callout(s, fx + 12, fy + 12, 1)
    callout(s, cx - 200, fy + 54 + 172, 2)
    callout(s, L + 2, fy + 352, 3)
    callout(s, L + 204, fy + 352, 4)
    callout(s, L + 2, fy + 744, 5)
    callout(s, fx + W - 30, fy + 70, 6)
    notes(s, fx + W + 60, fy + 10, [
        ("導覽列", ["高 54，底色 #202020。左：Logo（回遊戲庫）、", "「遊戲庫」、麵包屑。右：運作中提示、", "重新掃描（黃）、⚙。"]),
        ("Hero + 搜尋", ["點點底紋（18px 間距）。標題 30pt 粗、", "副標 11pt。搜尋框 360×40，即時過濾", "兩個區塊，區段數字同步更新。"]),
        ("已支援卡片", ["彩色封面。副標顯示狀態：", "已支援（灰）／● 執行中（綠）／", "● 修改器運作中（橘）。點擊進入修改器頁。"]),
        ("卡片 hover", ["邊框變橘 #F04E23、游標變手指。"]),
        ("尚未支援卡片", ["灰階封面、副標「尚未支援」、不可點。", "無封面圖時灰底＋名稱置中（Title 04）。", "圖片逐張載入，先出卡片再補圖。"]),
        ("齒輪選單", ["點 ⚙ 展開下拉選單 → 設定（見 03）。"]),
    ])
    s.save("01-library.svg")


def screen_trainer():
    W, H = 1180, 1190
    s = Svg(PAD * 2 + W + NOTE_W, PAD + H + 60)
    fx, fy = PAD, PAD
    frame_title(s, fx, fy, "02 · 修改器頁", "1180 × 整頁（可捲動）")
    s.rect(fx, fy, W, H, C["bg"])
    nav(s, fx, fy, W, crumb="Sample Game", active="Sample Game")
    L, CW = fx + 70, 1040
    s.text(L, fy + 86, "←  遊戲庫", 13, C["ink2"])
    placeholder(s, L, fy + 104, CW, 260, "Hero 圖 1040×260（cover 裁切）", dark=True)
    s.rect(L + 28, fy + 104 + 260 - 16 - 110, 300, 110, "none", "#888888", dash="6 4")
    s.text(L + 178, fy + 104 + 260 - 16 - 50, "Logo（contain 360×200）", 12, "#AAAAAA", 400, "middle")
    ty = fy + 390
    s.text(L, ty + 38, "Sample Game", 40, C["ink"], 400, family=SERIF)
    s.text(L, ty + 66, "Ver.1.0  ·  Steam 000000  ·  一句話介紹這款遊戲。", 12, C["ink2"])
    status(s, L, ty + 94, "遊戲執行中  ·  PID 1234", C["green"])
    bw = button(s, L + CW - 96, ty + 8, "啟動遊戲", "primary", w=96)
    button(s, L + CW - 96 - 10 - 108, ty + 8, "遊戲資料夾", "secondary", w=108)
    # master
    my = fy + 512
    s.rect(L, my, CW, 112, C["card"], C["line"])
    s.text(L + 26, my + 50, "修改器", 28, C["ink"], 700)
    s.text(L + 26, my + 82, "已開啟 — 下方開啟的功能會持續生效。", 12, C["green"])
    toggle(s, L + CW - 26 - 60, my + 40, True, w=60, h=32)
    chip(s, L + CW - 26 - 60 - 16 - 90, my + 41, "快捷鍵  F6")
    sy = fy + 660
    section(s, L, sy, CW, "功能", "")
    feature_card(s, L, sy + 18, CW, "功能名稱 A", "一行說明文字，描述這個開關型功能會做什麼。", "F7", True)
    feature_card(s, L, sy + 116, CW, "功能名稱 B", "一行說明文字，描述這個開關型功能會做什麼。", "F8", False)
    ky = sy + 214
    kx, tx1, tx2, ry = slider_card(s, L, ky, CW, 11)
    iy = ky + 176
    s.rect(L, iy, CW, 86, C["card_alt"], C["line"])
    for i, (k, v) in enumerate([("數值 A", "100 / 100"), ("數值 B", "每幀 22 像素（×11）"), ("數值 C", "項目1 12  項目2 30  項目3 5")]):
        s.text(L + 20, iy + 26 + i * 20, f"{k}　{v}", 12, C["ink2"], family=MONO)
    s.text(L, iy + 116, "快捷鍵是全域的：遊戲在前景時一樣有效，切換時會發出提示音。", 11, C["ink3"])
    s.text(L, iy + 134, "點選按鍵標籤後按下新按鍵即可變更；Esc 取消、Backspace 清除。", 11, C["ink3"])
    # 視窗可視範圍
    s.line(fx - 30, fy + 820, fx + W + 30, fy + 820, RED, 1, "8 6")
    s.text(fx + W + 34, fy + 824, "預設視窗可視範圍（820）", 11, RED, 700)
    dim_v(s, fy + 104, fy + 364, L - 24, "260")
    dim_v(s, my, my + 112, fx + W + 24 - 70 + 70, "112")
    dim_v(s, sy + 18, sy + 106, L - 24, "88")
    dim_h(s, L + CW - 26 - 60, L + CW - 26, my + 128, "60×32")
    dim_h(s, L + CW - 26 - 48, L + CW - 26, sy + 18 + 104, "48×26")
    dim_h(s, L, L + 26, my + 100, "26")
    for n, (x, y) in enumerate([(fx + 340, fy + 14), (L - 4, fy + 80), (L + 12, fy + 116), (L - 20, ty + 90),
                               (L + CW - 220, ty + 4), (L + 12, my + 14), (L + 12, sy + 30),
                               (L + 12, ky + 14), (L + 12, iy + 12)], 1):
        callout(s, x, y, n)
    notes(s, fx + W + 60, fy + 10, [
        ("麵包屑 + 運作中提示", ["修改器生效時，導覽列右側顯示橘色", "「● 修改器運作中：遊戲名」。"]),
        ("返回", ["「← 遊戲庫」，hover 變橘。"]),
        ("橫幅", ["Steam hero 圖 + Logo 疊在左下。", "沒有圖時：深色底 + Georgia 斜體遊戲名。"]),
        ("標題與狀態", ["遊戲名 Georgia 30pt；中繼資訊 9pt；", "狀態：● 執行中（綠）／● 未偵測（灰）／", "● 版本不符、無法存取（琥珀）。"]),
        ("動作按鈕", ["遊戲資料夾（黃，次要）、啟動遊戲", "（橘，主要；遊戲已執行時無作用）。"]),
        ("修改器總開關", ["每次啟動預設關閉。說明文字隨狀態：", "關閉（灰）／開啟＋執行中（綠）／", "開啟＋等待遊戲（琥珀）。"]),
        ("開關型功能", ["快捷鍵標籤 + 開關。開啟任一功能會", "自動打開總開關。總開關關閉時，", "已開啟的功能顯示淡橘 #F4A58F。"]),
        ("數值型功能", ["滑桿 / − + / 數字輸入 / 快捷鍵四種", "輸入同步。值 1 = 遊戲原本行為。", "按住快捷鍵 0.4s 後每 0.08s 連續調整。"]),
        ("即時數值", ["Consolas 等寬字，每秒更新。", "遊戲未執行時顯示提示文字。"]),
    ])
    s.save("02-trainer.svg")


def screen_settings():
    s = Svg(PAD * 2 + 720 + 60 + 420 + NOTE_W - 40, PAD + 640 + 60)
    fx, fy = PAD, PAD
    frame_title(s, fx, fy, "03 · 設定視窗", "720 × 640（modal，可縱向拉長）")
    W = 720
    s.rect(fx, fy, W, 640, C["bg"])
    s.rect(fx, fy, W, 56, C["nav"])
    s.text(fx + 24, fy + 36, "設定", 19, C["nav_fg"], 700)
    x = fx + 24
    s.text(x, fy + 92, "Steam 遊戲庫", 16, C["ink"], 700)
    s.text(x, fy + 116, "可以填 Steam 安裝目錄，或任何含有 steamapps 的遊戲庫資料夾。封面圖片只存在 Steam", 11, C["ink2"])
    s.text(x, fy + 134, "安裝目錄裡，只加入遊戲庫時會列出遊戲但沒有圖片。", 11, C["ink2"])
    s.rect(x, fy + 152, 672, 72, C["card"], C["line"])
    s.text(x + 16, fy + 180, "自動偵測 Steam 安裝位置", 13, C["ink"], 700)
    s.text(x + 16, fy + 202, "C:\\Program Files (x86)\\Steam  ·  Steam 安裝目錄，含 2 個遊戲庫，24 款遊戲", 11, C["ink3"])
    toggle(s, x + 672 - 16 - 48, fy + 175, True)
    s.text(x, fy + 262, "自訂路徑", 13, C["ink"], 700)
    button(s, x + 672 - 104, fy + 244, "+  新增路徑", "secondary", w=104, h=28, size=12)
    rows = [("D:\\SteamLibrary", "✓  遊戲庫，12 款遊戲", C["green"]),
            ("X:\\Games\\Steam", "✗  資料夾不存在", C["orange"]),
            ("", "✗  請輸入或選擇資料夾", C["orange"])]
    for i, (p, msg, col) in enumerate(rows):
        ry = fy + 284 + i * 86
        s.rect(x, ry, 672, 76, C["card"], C["line"])
        focus = i == 2
        s.rect(x + 12, ry + 12, 512, 30, C["card_alt"], C["orange"] if focus else C["line"])
        s.text(x + 22, ry + 32, p, 13, C["ink"])
        s.text(x + 12, ry + 62, msg, 11, col)
        button(s, x + 536, ry + 14, "瀏覽…", "subtle", w=60, h=26, size=11)
        button(s, x + 606, ry + 14, "−", "subtle", w=54, h=26, size=14)
    s.line(fx, fy + 568, fx + W, fy + 568, C["line"])
    button(s, fx + W - 24 - 148, fy + 584, "儲存並重新掃描", "primary", w=148, h=36)
    button(s, fx + W - 24 - 148 - 10 - 62, fy + 584, "取消", "neutral", w=62, h=36)
    dim_v(s, fy, fy + 56, fx - 24, "56")
    dim_h(s, fx, x, fy + 66, "24")
    dim_v(s, fy + 284, fy + 360, fx + W + 20, "76")
    dim_h(s, x + 12, x + 524, fy + 284 + 86 * 2 + 50, "輸入框（彈性寬）")
    for n, (cx, cy) in enumerate([(x + 2, fy + 166), (x + 560, fy + 258), (x + 2, fy + 296),
                                  (x + 2, fy + 382), (fx + W - 190, fy + 578)], 1):
        callout(s, cx, cy, n)
    # 下拉選單
    dx = fx + W + 60
    frame_title(s, dx, fy, "03b · 齒輪選單", "下拉，place 在主視窗")
    s.rect(dx, fy, 420, 54, C["nav"])
    button(s, dx + 420 - 60 - 96, fy + 13, "重新掃描", "secondary", w=96, h=28, size=12)
    s.rect(dx + 420 - 46, fy + 10, 34, 34, "#3A3A3A")
    s.text(dx + 420 - 29, fy + 34, "⚙", 18, C["nav_fg"], 400, "middle")
    s.rect(dx, fy + 54, 420, 160, C["bg"])
    s.rect(dx + 420 - 14 - 170, fy + 60, 170, 40, C["card"], C["line"])
    s.rect(dx + 420 - 14 - 169, fy + 61, 168, 38, C["card_alt"])
    s.text(dx + 420 - 14 - 152, fy + 85, "⚙   設定", 13, C["ink"])
    s.text(dx + 16, fy + 140, "· 點 ⚙ 展開；再點或點其他地方收起", 12, C["ink2"])
    s.text(dx + 16, fy + 162, "· 項目 hover：底色 #F6F5F2", 12, C["ink2"])
    s.text(dx + 16, fy + 184, "· 齒輪 hover：#3A3A3A", 12, C["ink2"])
    callout(s, dx + 420 - 14 - 176, fy + 66, 6)
    notes(s, dx, fy + 260, [
        ("自動偵測", ["讀登錄檔 SteamPath + libraryfolders.vdf。", "關閉時說明文字變淡。"]),
        ("新增路徑", ["新增一列並自動聚焦輸入框。"]),
        ("路徑列（有效）", ["輸入停頓 300ms 後驗證；✓ 綠色。", "貼 …\\steamapps(\\common) 會自動校正。"]),
        ("路徑列（無效）", ["✗ 橘色說明原因。無效路徑仍可儲存", "（例如外接硬碟暫時沒插）。"]),
        ("頁尾", ["取消（白）／儲存並重新掃描（橘）。", "掃描中儲存會排隊，完成後再掃一次。"]),
        ("齒輪選單", ["目前只有「設定」一項。"]),
    ])
    s.save("03-settings.svg")


def sheet_components():
    s = Svg(1500, 1420)
    x0, y = PAD, PAD
    frame_title(s, x0, y, "04 · 元件與狀態", "Components")
    s.rect(x0, y, 1340, 1260, C["bg"])

    def row_title(yy, t):
        s.text(x0 + 30, yy, t, 14, C["ink"], 700)
        s.line(x0 + 30, yy + 10, x0 + 1310, yy + 10, C["line"])

    def cap(x, yy, t):
        s.text(x, yy, t, 11, C["ink3"])

    yy = y + 44
    row_title(yy, "按鈕")
    bx = x0 + 30
    for text, kind, c in [("啟動遊戲", "primary", "主要 · #F04E23"), ("啟動遊戲", "primary_hover", "主要 hover · #D63F17"),
                          ("重新掃描", "secondary", "次要 · #FFF78B"), ("取消", "neutral", "中性 · 白"),
                          ("瀏覽…", "subtle", "輕量 · #F6F5F2")]:
        w = button(s, bx, yy + 30, text, kind, w=120)
        cap(bx, yy + 84, c)
        bx += 180
    s.rect(bx, yy + 28, 38, 38, C["nav"])
    s.text(bx + 19, yy + 54, "⚙", 18, C["nav_fg"], 400, "middle")
    cap(bx, yy + 84, "圖示 · 導覽列上")
    s.text(bx + 120, yy + 52, "←  遊戲庫", 13, C["ink2"])
    s.text(bx + 230, yy + 52, "←  遊戲庫", 13, C["orange"])
    cap(bx + 120, yy + 84, "文字連結 · 預設 / hover")

    yy += 140
    row_title(yy, "開關 Toggle")
    tx = x0 + 30
    for on, muted, big, c in [(False, False, False, "關閉"), (True, False, False, "開啟（生效中）"),
                              (True, True, False, "開啟但未生效"), (True, False, True, "總開關 60×32")]:
        if big:
            toggle(s, tx, yy + 30, on, muted, 60, 32)
        else:
            toggle(s, tx, yy + 33, on, muted)
        cap(tx, yy + 84, c)
        tx += 200
    cap(tx, yy + 50, "未生效 = 功能開啟，但總開關關閉或遊戲未執行（#F4A58F）")

    yy += 140
    row_title(yy, "快捷鍵標籤 Hotkey chip")
    cx = x0 + 30
    for t, st, c in [("快捷鍵  F7", "default", "預設"), ("請按下按鍵…", "capture", "錄製中（黃）"),
                     ("快捷鍵  未設定", "default", "未設定"), ("減少  PgDn", "default", "數值：減少"),
                     ("增加  PgUp", "default", "數值：增加")]:
        chip(s, cx, yy + 32, t, st)
        cap(cx, yy + 84, c)
        cx += 200
    cap(cx, yy + 50, "Esc 取消 · Backspace 清除 · 同鍵只綁一個功能")

    yy += 140
    row_title(yy, "狀態 Status")
    sx = x0 + 30
    for t, col in [("遊戲執行中 · PID 1234", C["green"]), ("未偵測到遊戲 · 每秒自動偵測", C["ink3"]),
                   ("遊戲版本不符（需要 Ver.1.0），功能已停用", C["amber"])]:
        status(s, sx, yy + 50, t, col)
        sx += tw(t, 12) + 70
    s.text(x0 + 30, yy + 84, "總開關說明：", 11, C["ink3"])
    for i, (t, col) in enumerate([("已關閉 — 不會對遊戲做任何修改。", C["ink2"]),
                                  ("已開啟 — 下方開啟的功能會持續生效。", C["green"]),
                                  ("已開啟 — 等待遊戲啟動後自動套用。", C["amber"])]):
        s.text(x0 + 110 + i * 320, yy + 84, t, 12, col)

    yy += 140
    row_title(yy, "遊戲卡片 Game card（180×270 + 名稱列）")
    gx = x0 + 30
    for name, sub, col, st, c in [("Sample Game", "已支援 · Ver.1.0", C["ink3"], "default", "已支援"),
                                  ("Sample Game", "已支援 · Ver.1.0", C["ink3"], "hover", "hover"),
                                  ("Sample Game", "●  執行中 · Ver.1.0", C["green"], "default", "遊戲執行中"),
                                  ("Sample Game", "●  修改器運作中 · Ver.1.0", C["orange"], "default", "修改器運作中"),
                                  ("Game Title", "尚未支援", C["ink3"], "unsupported", "尚未支援（灰階）"),
                                  ("Game Title", "尚未支援", C["ink3"], "noart", "沒有封面圖")]:
        card(s, gx, yy + 26, name, sub, col, st, art="封面")
        cap(gx, yy + 374, c)
        gx += 210

    yy += 420
    row_title(yy, "數值滑桿")
    slider_card(s, x0 + 30, yy + 26, 620, 1)
    cap(x0 + 30, yy + 200, "值 = 1（原本行為）：滑塊灰")
    slider_card(s, x0 + 690, yy + 26, 620, 11, active=False)
    cap(x0 + 690, yy + 200, "值 > 1 但未生效：滑塊淡橘（生效中為橘）")
    s.save("04-components.svg")


def sheet_tokens():
    s = Svg(1500, 900)
    x0, y = PAD, PAD
    frame_title(s, x0, y, "00 · 設計 Tokens", "顏色 / 字型 / 尺寸")
    s.rect(x0, y, 1340, 760, C["bg"])
    s.text(x0 + 30, y + 44, "顏色", 16, C["ink"], 700)
    sw = [("nav", "導覽列 / 標題列"), ("bg", "頁面底色"), ("card", "卡片"), ("card_alt", "次要面"),
          ("line", "邊框 / 分隔線"), ("ink", "主要文字"), ("ink2", "說明文字"), ("ink3", "提示文字"),
          ("orange", "主色 / 開啟 / hover 邊框"), ("orange_hover", "主色 hover"), ("yellow", "次要按鈕 / 錄製中"),
          ("yellow_hover", "次要 hover"), ("green", "執行中 / ✓"), ("amber", "警告 / 等待"),
          ("off", "關閉 / 軌道"), ("muted", "開啟但未生效"), ("placeholder", "無封面卡片"), ("dot", "點點紋")]
    for i, (k, desc) in enumerate(sw):
        cx = x0 + 30 + (i % 6) * 215
        cy = y + 64 + (i // 6) * 120
        s.rect(cx, cy, 190, 54, C[k], C["line"])
        s.text(cx, cy + 74, k, 12, C["ink"], 700)
        s.text(cx + 190, cy + 74, C[k], 11, C["ink3"], 400, "end", MONO)
        s.text(cx, cy + 92, desc, 11, C["ink2"])
    ty = y + 450
    s.text(x0 + 30, ty, "字型", 16, C["ink"], 700)
    scale = [("Hero", "選擇要測試的遊戲", 36, 700, SANS, "JhengHei UI 30pt 粗"),
             ("遊戲標題", "Sample Game", 40, 400, SERIF, "Georgia 30pt"),
             ("卡片大標", "修改器", 28, 700, SANS, "22pt 粗"),
             ("區段 / 功能名", "功能名稱", 16, 700, SANS, "13pt 粗"),
             ("內文", "一行說明文字。", 13, 400, SANS, "10pt"),
             ("小字", "提示與中繼資訊", 11, 400, SANS, "9pt"),
             ("數值", "100 / 100", 13, 400, MONO, "Consolas 10pt")]
    yy = ty + 40
    for name, sample, size, weight, fam, spec in scale:
        s.text(x0 + 30, yy, name, 11, C["ink3"])
        s.text(x0 + 170, yy, sample, size, C["ink"], weight, family=fam)
        s.text(x0 + 620, yy, spec, 11, C["ink2"])
        yy += max(size + 10, 30)
    sx = x0 + 820
    s.text(sx, ty, "尺寸", 16, C["ink"], 700)
    for i, (k, v) in enumerate([("視窗預設 / 最小", "1180×820 / 1000×680"), ("內容最大寬", "1040，置中，左右 ≥ 24"),
                                ("導覽列高", "54"), ("遊戲卡片", "180×270 封面 + 名稱列，間距 20"),
                                ("橫幅", "1040×260（cover）"), ("Logo", "360×200（contain）"),
                                ("開關", "48×26；總開關 60×32"), ("卡片內距", "左右 22–26，上下 16–20"),
                                ("圓角", "無（直角，扁平風格）"), ("邊框", "1px #D8D6D0"), ("點點紋", "1.5px 點，間距 18")]):
        s.text(sx, ty + 40 + i * 26, k, 12, C["ink"], 700)
        s.text(sx + 130, ty + 40 + i * 26, v, 12, C["ink2"])
    s.save("00-tokens.svg")


def sheet_icon():
    from_pixels = [
        ".KKKKKKKKKKKKKK.", "KKKKKKKKKKKKKKKK", "KKYKGKKKKKKKKKKK", "KKKKKKKKKKKKKKKK",
        "KKKKKKKKKKKKKKKK", "KKKTTTTTTWWWWKKK", "KKTTTTTTWWWWWWKK", "KKTTLTTTWWWWWWKK",
        "KKTTLTTTWWWWWWKK", "KKTTTTTTWWWWWWKK", "KKKTTTTTTggggKKK", "KKKKKKKKKKKKKKKK",
        "KKKKKKKKKKKKKKKK", "KKKKKKKKKKKKKKKK", "KKKKKKKKKKKKKKKK", ".KKKKKKKKKKKKKK.",
    ]
    pal = {"K": ("#202020", "底色"), "T": ("#FFF78B", "開關軌道"), "L": ("#34D058", "燈號"),
           "W": ("#F5F5F2", "圓鈕"), "g": ("#C8C6C0", "圓鈕陰影"), "Y": ("#FFF78B", "左上小燈"), "G": ("#8F8D88", "左上小燈（暗）")}
    s = Svg(1100, 560)
    x0, y = PAD, PAD
    frame_title(s, x0, y, "05 · App 圖示", "16 × 16 像素，最近鄰放大")
    P = 22
    for yy, row in enumerate(from_pixels):
        for xx, ch in enumerate(row):
            if ch in pal:
                s.rect(x0 + xx * P, y + yy * P, P, P, pal[ch][0])
    for i in range(17):
        s.line(x0 + i * P, y, x0 + i * P, y + 16 * P, "#FFFFFF", 0.4)
        s.line(x0, y + i * P, x0 + 16 * P, y + i * P, "#FFFFFF", 0.4)
    lx = x0 + 16 * P + 60
    s.text(lx, y + 10, "調色盤", 15, C["ink"], 700)
    for i, (k, (col, name)) in enumerate(pal.items()):
        s.rect(lx, y + 30 + i * 34, 24, 24, col, C["line"])
        s.text(lx + 36, y + 47 + i * 34, f"{k}  {name}", 12, C["ink"])
        s.text(lx + 220, y + 47 + i * 34, col, 12, C["ink3"], family=MONO)
    px = lx + 320
    s.text(px, y + 10, "尺寸", 15, C["ink"], 700)
    for i, sz in enumerate([64, 32, 16]):
        p = sz / 16
        oy = y + 30 + sum([64, 32, 16][:i]) + i * 20
        for yy, row in enumerate(from_pixels):
            for xx, ch in enumerate(row):
                if ch in pal:
                    s.rect(px + xx * p, oy + yy * p, p + 0.05, p + 0.05, pal[ch][0])
        s.text(px + sz + 12, oy + sz / 2 + 4, f"{sz}px", 11, C["ink3"])
    s.text(lx, y + 300, "用途：標題列、設定視窗、工作列（AppUserModelID）。", 12, C["ink2"])
    s.text(lx, y + 320, "定義在 app/icon.py 的 PIXELS / PALETTE。", 12, C["ink2"])
    s.save("05-icon.svg")


if __name__ == "__main__":
    sheet_tokens()
    screen_library()
    screen_trainer()
    screen_settings()
    sheet_components()
    sheet_icon()
