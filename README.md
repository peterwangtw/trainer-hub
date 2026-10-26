# Trainer Hub

給**單機遊戲測試**用的修改器啟動器。選擇遊戲 → 開啟修改器 → 用開關、滑桿或全域快捷鍵調整功能。

- 免安裝：內建精簡的 Python 執行環境（`runtime/`），雙擊 `launcher.bat` 即可使用
- 自動偵測遊戲是否執行、版本是否相符；版本不符時自動停用
- 遊戲庫會列出本機 Steam 已安裝的遊戲（使用 Steam 本機快取的封面）
- 所有設定只存在程式資料夾內的 `config.json`，不修改系統設定或環境變數

## 支援的遊戲

| 遊戲 | 版本 | 功能 |
|---|---|---|
| [FrontLine](https://store.steampowered.com/app/4846480/) | Ver.1.49 | 無限子彈、無限生命、移動速度倍率（1–50） |

## 使用方式

1. 從 [Releases](../../releases) 下載 `TrainerHub-x.y.z.zip` 並解壓縮
2. 雙擊 `launcher.bat`
3. 點選遊戲 → 開啟「修改器」總開關 → 開啟想要的功能

預設快捷鍵（遊戲中也有效，可在介面上自訂）：

| 功能 | 按鍵 |
|---|---|
| 修改器總開關 | F6 |
| 無限子彈 | F7 |
| 無限生命 | F8 |
| 移動速度 −1 / +1（按住連續調整） | PgDn / PgUp |

點選介面上的按鍵標籤後按下新按鍵即可變更；Esc 取消、Backspace 清除。

### Steam 路徑

預設會自動偵測 Steam 安裝位置與其所有遊戲庫。若遊戲沒有出現，點右上角 **⚙ → 設定**，
用「+ 新增路徑」加入 Steam 安裝目錄或任何含 `steamapps` 的遊戲庫資料夾（可加多個，− 刪除）。
封面圖片取自 Steam 安裝目錄的本機快取，只加入遊戲庫時會列出遊戲但沒有圖片。

出問題時執行 `launcher.bat debug` 可看到錯誤訊息，或查看 `launcher_error.log`。

## 運作原理

- 以 Windows API（`ReadProcessMemory` / `WriteProcessMemory`）讀寫遊戲程序記憶體
- 位址以「模組基址 + 偏移」表示，支援 ASLR
- 移動速度會修改遊戲程式碼中的常數；修改前會比對原始指令，關閉修改器或關閉啟動器時自動還原
- 介面使用 tkinter；圖片以 Windows 內建的 GDI+ 轉換，無第三方套件

## 開發

需求：Windows、已安裝的 Python 3.11+（含 tkinter，只在建置 runtime 時需要）。

```bat
git clone https://github.com/peterwangtw/trainer-hub.git
cd trainer-hub

:: 從已安裝的 Python 複製出精簡、隔離的 runtime\（約 16 MB）
python tools\build_runtime.py

:: 啟動（含主控台）
launcher.bat debug

:: 打包發佈用 zip 到 dist\
python tools\make_release.py 1.0.0
```

`runtime/` 以 `python311._pth` 鎖定為隔離模式：不讀 `PYTHONPATH` 等環境變數、不載入使用者套件、不查登錄檔。

### 專案結構

```
launcher.bat            啟動器
app/
  main.py               介面與修改器邏輯
  memory.py             程序記憶體讀寫
  steam.py              Steam 遊戲庫掃描
  imaging.py            GDI+ 圖片縮放
  icon.py               App 圖示（程式產生的像素圖）
  games/
    base.py             GameDef / Feature / Setting 定義
    frontline.py        FrontLine 修改器
tools/
  build_runtime.py      建立內建 Python 執行環境
  make_release.py       打包發佈 zip
  gen_ui_mockups.py     產生 UI/UX 設計稿（docs/ui/*.svg）
docs/
  ui-ux.md              UI / UX 規格（設計 tokens、頁面框架、元件狀態、互動規則）
```

介面設計規格見 [docs/ui-ux.md](docs/ui-ux.md)。

### 新增遊戲

1. 在 `app/games/` 新增模組，定義 `GAME = GameDef(...)`
   - `Feature`：開關型功能，開啟時每個 tick 呼叫 `apply(process)`
   - `Setting`：數值型功能（滑桿），值改變時呼叫 `apply(process, value)`；值等於 `default` 代表遊戲原本行為
2. 在 `app/games/__init__.py` 的 `GAMES` 中註冊

## 注意事項

- 僅供單機遊戲測試使用，請勿用於線上 / 多人遊戲
- 與各遊戲開發商無關；遊戲名稱與圖片版權屬於各自的權利人

## 授權

Trainer Hub 以 [GNU General Public License v3.0](LICENSE)（GPL-3.0）授權。

- 你可以自由使用、研究、修改與再散布本程式。
- 散布修改版，或散布包含本程式的作品時，**必須同樣以 GPL-3.0 授權並公開完整原始碼**，且保留原本的版權與授權聲明。
  因此本專案不能被改成閉源的商品。

`runtime/`（隨 Release 發佈）內含的第三方元件依其各自的授權散布：

- Python：PSF License（見 `runtime/LICENSE.txt`，內含 libffi 等第三方聲明）
- Tcl/Tk：BSD 式授權（見 `runtime/tcl/tk8.6/license.terms`）
- Microsoft Visual C++ Runtime（`vcruntime140*.dll`）：依 Microsoft 可再散布條款隨 Python 一同散布