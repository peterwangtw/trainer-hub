"""打包可直接發佈的 zip（含 runtime/），輸出到 dist/。

用法（在 trainer 資料夾執行）：
    python tools\\make_release.py 1.0.0（使用已安裝的 Python；runtime 不含 zipfile 相依模組）
"""
import os
import sys
import zipfile

TRAINER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME = "TrainerHub"
INCLUDE = ["launcher.bat", "README.md", "LICENSE", "app", "runtime"]
SKIP_DIRS = {"__pycache__"}


def main():
    version = sys.argv[1] if len(sys.argv) > 1 else "dev"
    if not os.path.isfile(os.path.join(TRAINER, "runtime", "pythonw.exe")):
        sys.exit("找不到 runtime/，請先執行 tools\\build_runtime.py")
    out_dir = os.path.join(TRAINER, "dist")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"{NAME}-{version}.zip")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for item in INCLUDE:
            src = os.path.join(TRAINER, item)
            if os.path.isfile(src):
                z.write(src, os.path.join(NAME, item))
            elif os.path.isdir(src):
                for root, dirs, files in os.walk(src):
                    dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
                    for fn in files:
                        full = os.path.join(root, fn)
                        z.write(full, os.path.join(NAME, os.path.relpath(full, TRAINER)))
    print(f"{out}  ({os.path.getsize(out) / 1024 / 1024:.1f} MB)")


if __name__ == "__main__":
    main()
