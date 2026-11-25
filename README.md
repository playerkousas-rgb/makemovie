# Tea Egg OpusCar Project

用 Code 画动画，唔用 AI 直接生图。同一故事，一键换风格：蜡笔绘本风 + 16-bit 像素风。

## 目录
- AGENTS.md - 俾 AI 睇嘅工作守则
- specs/ - 99 份风格说明书
- prompts/ - 可直接贴去 ARENA.AI 嘅 prompt
- src/ - 2D 雙風格引擎 + **SCOUT 3D 立體動畫元件庫**
- episodes/ - SCOUT 3D 各集獨立劇本檔（頂頭第 1 行即改粵語字幕）
- tools/ - **SCOUT 3D 動畫劇本＆CMD 指令生成器 HTML 工具**
- output/ - 渲染輸出嘅 MP4 與 Contact Sheet（本機生成）

---

## SCOUT 3D 立體動畫元件庫 ＆ Windows CMD 使用方法

### 1. 核心 3D 元件清單（`src/`）
- `src/engine3d.py`：純 Python + NumPy 向量化 3D Ray-Primitive Z-Buffer 攝影棚渲染引擎（支援圓滑膠囊、橢球、圓角方塊、柔和陰影與 3D 立體童軍徽章貼片）。
- `src/scout3d_characters.py`：香港童軍 `SCOUT 3D` 角色與道具元件庫（支援**波波圓滑 3D 風 `bobo`** 及 **簡約方塊 3D 風 `blocky`**、六大支部制服 `grasshopper` / `cub` / `scout` / `venture` / `sea_scout` / `air_scout`、男女髮型、三指童軍敬禮、動態飛章入位、綠紅斜佩專章帶、媽媽、領袖、360° 旋轉底座、手冊書疊及 3D 營幕）。
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

