# Tea Egg OpusCar Project

用 Code 画动画，唔用 AI 直接生图。同一故事，一键换风格：蜡笔绘本风 + 16-bit 像素风。

## 目录
- AGENTS.md - 俾 AI 睇嘅工作守则
- specs/ - 99 份风格说明书
- prompts/ - 可直接贴去 ARENA.AI 嘅 prompt
- src/ - 2D 雙風格引擎 + **SCOUT 3D 立體動畫元件庫**
- assets/scout3d/ - 由 `playerkousas-rgb/SCOUT3D` 官方程式規則直接編譯之精確 3D 人仔比例、徽章座標（`scout3d_rig_data.json`）與 48 張官方透明底徽章 PNG
- presets/ - **可無限重用嘅 3D 角色設定卡（`.json`）**，一次設定演員即可跨集數直接調用
- episodes/ - SCOUT 3D 各集獨立劇本檔（頂頭第 1 行即改粵語字幕）
- tools/ - **SCOUT 3D 動畫劇本＆CMD 指令生成器 HTML 工具**
- output/ - 渲染輸出嘅 MP4 與 Contact Sheet（本機生成）

---

## SCOUT 3D 立體動畫元件庫 ＆ Windows CMD 使用方法

### 1. 核心 3D 元件清單（`src/` ＆ `assets/scout3d/`）
- `src/engine3d.py`：純 Python + NumPy 向量化 3D Ray-Primitive Z-Buffer 攝影棚渲染引擎（支援圓滑膠囊、橢球、圓角方塊、柔和陰影與 `add_textured_patch_3d` 高清 RGBA 透明裁切徽章貼片）。
- `src/scout3d_characters.py`：100% 讀取 `SCOUT3D` 官方 `body.js` + `badgeLayout.js` + `*_rules_v1.0.json` 編譯數據（`assets/scout3d/scout3d_rig_data.json`），精確還原七大制服組別（`grasshopper` 小童軍、`cub` 幼童軍、`scout` 童軍、`sea_scout` 海童軍、`air_scout` 空童軍、`venture` 深資童軍、`leader` 成年領袖）、綠底紅邊左肩斜落右腰專章帶（壓於領巾之下）、2×2 菱形專科章、右袖旅章＋地域／區章並排＋小隊章、以及 `CHARACTER_PRESETS` 可重用 3D 演員庫。
- `scripts/compile_scout3d_rig.mjs`：如需同步最新 `SCOUT3D` 規則，可一鍵由 `SCOUT3D` 源碼重新編譯 `assets/scout3d/`（一般本機 `CMD` 出片完全唔需要裝 Node.js）。
- `src/scout3d_whatif.py`：《如果系列 EP.01：如果你有 SCOUT 3D》完整渲染管線。
- `src/scout3d_runner.py`：通用劇本執行引擎（支援 `--b64` 免開檔直接貼落 Windows `CMD` 一鍵出片，或執行 `episodes/*.py`）。
- `tools/SCOUT3D_動畫劇本生成器_v1.0.html`：純前端單檔 HTML 工具，一鍵產出新集數劇本與對應 `CMD` 指令。

### 2. 本機首次安裝（Windows CMD 只需做一次）
```bat
git pull
pip install -r requirements.txt
```

### 3. 日後出新片（兩種方法任揀）
- **方法 A（免放上 Git・直接貼落 CMD 連劇本即刻整片）**：
  雙擊打開 `tools/SCOUT3D_動畫劇本生成器_v1.0.html` ➔ 撳「📋 一鍵複製 CMD 直出片指令（連劇本）」➔ 貼落 `CMD` 按 Enter：
  ```bat
  python src/scout3d_runner.py --b64 <自動編碼劇本> --write-py
  ```
- **方法 B（執行獨立劇本檔／秒速改字幕）**：
  ```bat
  python src/scout3d_whatif.py
  python episodes/ep02_camp_eve.py
  python episodes/ep02_camp_eve.py --fast-sub-only
  ```

