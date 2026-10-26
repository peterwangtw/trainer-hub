"""讀取本機 Steam 的遊戲庫與封面圖片（唯讀）。

路徑來源：
  - 自動偵測：登錄檔 HKCU\\Software\\Valve\\Steam\\SteamPath + 其 libraryfolders.vdf
  - 使用者自訂：Steam 安裝目錄或任何含 steamapps 的遊戲庫資料夾（可多個）
"""
import glob
import os
import re

try:
    import winreg
except ImportError:  # pragma: no cover
    winreg = None

# 不是遊戲的 Steam 工具
SKIP_APPIDS = {228980, 1070560, 1391110, 1628350, 1493710, 2180100}
SKIP_WORDS = ("redistributable", "steamworks", "proton", "steam linux runtime", "soundtrack")


def steam_root():
    """自動偵測的 Steam 安裝目錄；找不到時回傳 None。"""
    if winreg:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
                path = os.path.normpath(winreg.QueryValueEx(k, "SteamPath")[0])
                if os.path.isdir(path):
                    return path
        except OSError:
            pass
    default = r"C:\Program Files (x86)\Steam"
    return default if os.path.isdir(default) else None


def normalize(path):
    """使用者可能貼 ...\\steamapps 或 ...\\steamapps\\common，統一成含 steamapps 的那層。"""
    p = os.path.normpath(os.path.expandvars(path.strip().strip('"')))
    name = os.path.basename(p).lower()
    if name == "common" and os.path.basename(os.path.dirname(p)).lower() == "steamapps":
        p = os.path.dirname(os.path.dirname(p))
    elif name == "steamapps":
        p = os.path.dirname(p)
    return p


def is_steam_root(path):
    return os.path.isdir(os.path.join(path, "appcache")) or os.path.isfile(os.path.join(path, "steam.exe"))


def library_paths(root):
    """root 本身 + root\\steamapps\\libraryfolders.vdf 列出的其他遊戲庫。"""
    paths = [root]
    vdf = os.path.join(root, "steamapps", "libraryfolders.vdf")
    try:
        text = open(vdf, encoding="utf-8", errors="ignore").read()
        for m in re.finditer(r'"path"\s+"(.+?)"', text):
            p = os.path.normpath(m.group(1).replace("\\\\", "\\"))
            if p.lower() not in (x.lower() for x in paths):
                paths.append(p)
    except OSError:
        pass
    return [p for p in paths if os.path.isdir(os.path.join(p, "steamapps"))]


def _add_unique(lst, path):
    if path.lower() not in (x.lower() for x in lst):
        lst.append(path)


def resolve(custom_paths, autodetect=True):
    """回傳 (遊戲庫清單, 圖片快取根目錄清單)。"""
    libraries, art_roots = [], []
    sources = []
    if autodetect:
        root = steam_root()
        if root:
            sources.append(root)
    sources += [normalize(p) for p in custom_paths if p.strip()]
    for src in sources:
        if not os.path.isdir(os.path.join(src, "steamapps")):
            continue
        for lib in library_paths(src):
            _add_unique(libraries, lib)
        if is_steam_root(src):
            _add_unique(art_roots, src)
    return libraries, art_roots


def _acf_value(text, key):
    m = re.search(r'"%s"\s+"(.*?)"' % key, text, re.IGNORECASE)
    return m.group(1) if m else None


def _manifests(lib):
    return glob.glob(os.path.join(lib, "steamapps", "appmanifest_*.acf"))


def installed_games(libraries):
    games = {}
    for lib in libraries:
        for acf in _manifests(lib):
            try:
                text = open(acf, encoding="utf-8", errors="ignore").read()
                appid = int(_acf_value(text, "appid"))
            except (OSError, TypeError, ValueError):
                continue
            name = _acf_value(text, "name") or str(appid)
            if appid in SKIP_APPIDS or any(w in name.lower() for w in SKIP_WORDS):
                continue
            installdir = _acf_value(text, "installdir") or ""
            games.setdefault(appid, {
                "appid": appid,
                "name": name,
                "dir": os.path.join(lib, "steamapps", "common", installdir),
            })
    return games


def inspect(path):
    """檢查使用者輸入的路徑，回傳 (是否有效, 說明文字)。"""
    if not path.strip():
        return False, "請輸入或選擇資料夾"
    p = normalize(path)
    if not os.path.isdir(p):
        return False, "資料夾不存在"
    if not os.path.isdir(os.path.join(p, "steamapps")):
        return False, "找不到 steamapps 資料夾"
    libs = library_paths(p)
    count = len(installed_games(libs))  # 與遊戲庫相同的計算方式（排除 Steam 工具）
    if is_steam_root(p):
        extra = f"，含 {len(libs)} 個遊戲庫" if len(libs) > 1 else ""
        return True, f"Steam 安裝目錄{extra}，{count} 款遊戲"
    return True, f"遊戲庫，{count} 款遊戲"


_ART_FILES = {
    "capsule": ("library_capsule.jpg", "{id}_library_600x900.jpg"),
    "hero": ("library_hero.jpg", "{id}_library_hero.jpg"),
    "logo": ("logo.png", "{id}_logo.png"),
    "header": ("library_header.jpg", "{id}_header.jpg"),
}


def find_art(art_roots, appid, kind):
    """在各 Steam 安裝目錄的快取中找圖片（支援新舊兩種快取結構）。"""
    new_name, old_name = _ART_FILES[kind]
    for root in art_roots:
        cache = os.path.join(root, "appcache", "librarycache")
        hits = glob.glob(os.path.join(cache, str(appid), "**", new_name), recursive=True)
        if hits:
            return max(hits, key=os.path.getmtime)
        old = os.path.join(cache, old_name.format(id=appid))
        if os.path.isfile(old):
            return old
    return None
