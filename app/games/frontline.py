"""FrontLine Ver.1.49 修改器定義。偏移皆相對於 FrontLine.exe 模組基址。"""
import struct

from .base import Feature, GameDef, Setting

WEAPON_TABLE = 0x47690   # 手槍 / 機槍 / 霰彈槍 / 狙擊槍 / 手榴彈
WEAPON_STRIDE = 0x38
WEAPON_COUNT = 5
#   +0x00 彈匣內子彈   +0x04 備用子彈(-1 = 無限)   +0x0C 彈匣容量
PLAYER_HP = 0x47AFC
PLAYER_HP_MAX = 0x47B00


def refill_ammo(p):
    for i in range(WEAPON_COUNT):
        w = WEAPON_TABLE + i * WEAPON_STRIDE
        cap = p.read_int(w + 0x0C)
        if 0 < cap < 1000 and p.read_int(w) != cap:
            p.write_int(w, cap)


def refill_hp(p):
    hp_max = p.read_int(PLAYER_HP_MAX)
    if 0 < hp_max < 100000 and p.read_int(PLAYER_HP) != hp_max:
        p.write_int(PLAYER_HP, hp_max)


# 移動速度寫在程式碼裡的常數（每幀 2 像素）：
#   +0x33A7  83 E8 02            sub eax, 2          ; 向左 (A/Z)
#   +0x3509  83 05 <X 位址> 02    add [X], 2          ; 向右 (D/C)
PLAYER_X = 0x47AF4
MOVE_LEFT = 0x33A7
MOVE_RIGHT = 0x3509
BASE_SPEED = 2
MAX_SPEED_MULT = 50  # 常數只有 1 byte（最大 127）


def _speed_sites(p):
    """確認兩段指令都是預期的內容，回傳兩個常數的偏移；不符合時回傳 None。"""
    left = p.read_bytes(MOVE_LEFT, 3)
    right = p.read_bytes(MOVE_RIGHT, 7)
    x_addr = struct.pack("<I", p.base + PLAYER_X)
    if left[:2] == b"\x83\xE8" and right[:2] == b"\x83\x05" and right[2:6] == x_addr:
        return MOVE_LEFT + 2, MOVE_RIGHT + 6
    return None


def set_speed(p, mult):
    sites = _speed_sites(p)
    if not sites:
        return False
    imm = bytes([BASE_SPEED * max(1, min(MAX_SPEED_MULT, int(mult)))])
    for off in sites:
        if p.read_bytes(off, 1) != imm:
            p.write_code(off, imm)
    return True


def read_status(p):
    hp, hp_max = p.read_int(PLAYER_HP), p.read_int(PLAYER_HP_MAX)
    mags = [p.read_int(WEAPON_TABLE + i * WEAPON_STRIDE) for i in range(WEAPON_COUNT)]
    sites = _speed_sites(p)
    speed = p.read_bytes(sites[1], 1)[0] if sites else None
    return {
        "血量": f"{hp} / {hp_max}",
        "移速": f"每幀 {speed} 像素（×{speed // BASE_SPEED}）" if speed else "無法讀取",
        "彈匣": "  ".join(f"{n} {m}" for n, m in zip(("手槍", "機槍", "霰彈", "狙擊", "手榴彈"), mags)),
    }


GAME = GameDef(
    id="frontline",
    name="FrontLine",
    exe="FrontLine.exe",
    steam_appid=4846480,
    version_label="Ver.1.49",
    exe_size=497160,
    tagline="橫向捲軸射擊。切換武器、補給彈藥，盡可能向前推進。",
    features=[
        Feature("ammo", "無限子彈", "所有武器的彈匣保持全滿，包含手榴彈。", (0x76, "F7"), refill_ammo),
        Feature("hp", "無限生命", "血量持續補滿至最大值。", (0x77, "F8"), refill_hp),
    ],
    settings=[
        Setting("speed", "移動速度", "1 為原本的走路速度，數字代表倍率（例如 11 = 原速 ×11）。",
                1, MAX_SPEED_MULT, 1, "×", (0x22, "PgDn"), (0x21, "PgUp"), set_speed),
    ],
    read_status=read_status,
    master_key=(0x75, "F6"),
    fallback_art=r"image\Title.gif",
)
