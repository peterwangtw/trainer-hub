"""從本機已安裝的 Python 建立精簡、可攜、隔離的執行環境 runtime/。

用法（在 trainer 資料夾執行，使用要被複製的那個 Python）：
    python tools\\build_runtime.py

做法：
  1. 用 modulefinder 找出 app.main 實際用到的標準函式庫與 .pyd
  2. 複製 python.exe / pythonw.exe / DLL / 必要的 Lib、DLLs、Tcl/Tk 到 runtime/
  3. 寫入 pythonXY._pth，讓 runtime 以隔離模式執行：
     不讀 PYTHONPATH 等環境變數、不載入 site / 使用者套件、不查登錄檔
"""
import modulefinder
import os
import shutil
import subprocess
import sys

TRAINER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNTIME = os.path.join(TRAINER, "runtime")
BASE = sys.base_prefix
VER = f"{sys.version_info.major}{sys.version_info.minor}"

ROOT_FILES = ["python.exe", "pythonw.exe", f"python{VER}.dll", "python3.dll",
              "vcruntime140.dll", "vcruntime140_1.dll", "LICENSE.txt"]
# 動態載入、modulefinder 找不到的模組
ALWAYS_PACKAGES = ["encodings"]
ALWAYS_MODULES = ["codecs", "io", "abc", "os", "stat", "ntpath", "genericpath", "_collections_abc",
                  "_sitebuiltins", "linecache", "tokenize", "token", "warnings", "weakref", "_weakrefset",
                  "copyreg", "functools", "collections", "keyword", "operator", "reprlib", "types",
                  "enum", "re", "traceback", "contextlib", "heapq", "struct", "tkinter.font",
                  "tkinter.constants"]
# modulefinder 會連帶掃進來、但啟動器不會用到的模組
EXCLUDES = ["test", "unittest", "doctest", "pydoc", "pdb", "_testcapi", "_testinternalcapi",
            "ssl", "_ssl", "_hashlib", "asyncio", "_asyncio", "_overlapped", "multiprocessing",
            "_multiprocessing", "xml", "xmlrpc", "email", "http", "urllib", "lzma", "_lzma", "bz2", "_bz2",
            "_decimal", "_pydecimal", "socket", "_socket", "pyexpat", "tkinter.test", "lib2to3", "idlelib"]
# Tcl/Tk 用不到的部分
TCL_SKIP = {"demos", "images", "tzdata", "msgs", "encoding"}
TCL_KEEP_ENCODINGS = {"ascii.enc", "cp1252.enc", "iso8859-1.enc", "utf-8.enc", "unicode.enc",
                      "big5.enc", "cp950.enc", "cp936.enc", "gb2312.enc", "shiftjis.enc", "cp932.enc",
                      "euc-jp.enc", "jis0208.enc", "jis0212.enc", "jis0201.enc", "euc-kr.enc", "cp949.enc"}


def find_modules():
    finder = modulefinder.ModuleFinder(path=[TRAINER] + sys.path, excludes=EXCLUDES)
    finder.import_hook("app.main")
    for name in ALWAYS_MODULES:
        try:
            finder.import_hook(name)
        except ImportError:
            pass
    return finder.modules


def copy_file(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)


def sync_file(src, dst):
    """內容相同就跳過 —— 啟動器執行中時，正被使用的 exe / dll 無法覆寫。"""
    if os.path.isfile(dst):
        s, d = os.stat(src), os.stat(dst)
        if s.st_size == d.st_size and int(s.st_mtime) == int(d.st_mtime):
            return
    copy_file(src, dst)


def main():
    os.makedirs(RUNTIME, exist_ok=True)
    # Lib / tcl 只是腳本，執行中也不會被鎖住，直接重建以清掉舊檔
    for sub in ("Lib", "tcl"):
        shutil.rmtree(os.path.join(RUNTIME, sub), ignore_errors=True)

    for name in ROOT_FILES:
        sync_file(os.path.join(BASE, name), os.path.join(RUNTIME, name))

    lib_dir = os.path.normcase(os.path.join(BASE, "Lib"))
    dll_dir = os.path.normcase(os.path.join(BASE, "DLLs"))
    dlls = set()
    copied = 0
    for name, mod in find_modules().items():
        path = getattr(mod, "__file__", None)
        if not path:
            continue
        norm = os.path.normcase(os.path.abspath(path))
        if norm.startswith(lib_dir + os.sep) and "site-packages" not in norm:
            rel = os.path.relpath(path, os.path.join(BASE, "Lib"))
            copy_file(path, os.path.join(RUNTIME, "Lib", rel))
            copied += 1
        elif norm.startswith(dll_dir + os.sep):
            dlls.add(os.path.basename(path))
            copied += 1

    for pkg in ALWAYS_PACKAGES:
        shutil.copytree(os.path.join(BASE, "Lib", pkg), os.path.join(RUNTIME, "Lib", pkg),
                        ignore=shutil.ignore_patterns("__pycache__"), dirs_exist_ok=True)

    # .pyd 依賴的 DLL（ctypes → libffi、tkinter → Tcl/Tk）
    for dll in os.listdir(os.path.join(BASE, "DLLs")):
        if dll.lower().startswith(("libffi", "tcl8", "tk8")) and dll.lower().endswith(".dll"):
            dlls.add(dll)
    for dll in dlls:
        sync_file(os.path.join(BASE, "DLLs", dll), os.path.join(RUNTIME, "DLLs", dll))
    for old in os.listdir(os.path.join(RUNTIME, "DLLs")):
        if old not in dlls:
            try:
                os.remove(os.path.join(RUNTIME, "DLLs", old))
            except OSError:
                print(f"無法刪除使用中的 DLLs\\{old}，關閉啟動器後再重跑一次")

    # Tcl/Tk 腳本庫
    tcl_src = os.path.join(BASE, "tcl")
    for entry in os.listdir(tcl_src):
        if entry.startswith(("tcl8", "tk8")) and os.path.isdir(os.path.join(tcl_src, entry)):
            def ignore(d, names):
                skip = {n for n in names if n in TCL_SKIP and n != "encoding"}
                if os.path.basename(d) == "encoding":
                    skip |= {n for n in names if n not in TCL_KEEP_ENCODINGS}
                return skip
            shutil.copytree(os.path.join(tcl_src, entry), os.path.join(RUNTIME, "tcl", entry), ignore=ignore)

    # 隔離模式：只用這些路徑，不 import site
    with open(os.path.join(RUNTIME, f"python{VER}._pth"), "w", encoding="utf-8") as f:
        f.write("Lib\nDLLs\n..\n")

    # 預先編譯，加快啟動
    subprocess.run([sys.executable, "-m", "compileall", "-q", "-b", os.path.join(RUNTIME, "Lib")], check=True)
    for root, dirs, files in os.walk(os.path.join(RUNTIME, "Lib")):
        for fn in files:
            if fn.endswith(".py") and os.path.exists(os.path.join(root, fn + "c")):
                os.remove(os.path.join(root, fn))  # 只留 .pyc
        if "__pycache__" in dirs:
            shutil.rmtree(os.path.join(root, "__pycache__"))

    size = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(RUNTIME) for f in fs)
    print(f"runtime 建立完成：Python {sys.version.split()[0]}，{copied} 個模組，{size / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()
