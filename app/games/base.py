"""遊戲修改器的定義格式。新增遊戲時，在 games/ 下新增一個模組並在 __init__.py 註冊。"""
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

Hotkey = Tuple[int, str]  # (Windows 虛擬鍵碼, 顯示名稱)


@dataclass
class Feature:
    id: str
    name: str
    desc: str
    default_key: Optional[Hotkey]
    apply: Callable  # apply(process) — 開啟時每個 tick 呼叫一次


@dataclass
class Setting:
    """數值型功能（滑桿）。value == default 時代表遊戲原本的行為。"""
    id: str
    name: str
    desc: str
    minimum: int
    maximum: int
    default: int
    unit: str
    dec_key: Optional[Hotkey]
    inc_key: Optional[Hotkey]
    apply: Callable  # apply(process, value) — 數值改變時呼叫；回傳 False 表示無法套用


@dataclass
class GameDef:
    id: str
    name: str
    exe: str
    steam_appid: int
    version_label: str
    exe_size: Optional[int]          # 用檔案大小確認版本；None 表示不檢查
    tagline: str
    features: List[Feature]
    read_status: Callable = lambda p: {}  # 回傳 {標籤: 值}，顯示在介面上
    master_key: Optional[Hotkey] = None
    settings: List[Setting] = field(default_factory=list)
    fallback_art: Optional[str] = None   # 找不到 Steam 圖片時，用遊戲資料夾內的圖片（相對路徑）
    extra: Dict = field(default_factory=dict)
