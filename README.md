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
- `src/scout3d_runner.py`：通用劇本＋香港廣東話配音執行引擎（支援 `--b64 z_...` 短碼免開檔直接貼落 Windows `CMD` 一鍵出片；內置 `edge-tts` 香港廣東話自然語音合成、按每鏡語音長度自動延長 3D 動作、以及 BGM 自動壓聲 Ducking）。
- `tools/SCOUT3D_動畫劇本生成器_v2.1.html`：對齊 `© SCOUT SYSTEM` 介面設計嘅純前端單檔工具（支援先設定 **15s / 30s / 45s / 60s / 90s 彈性片長範圍** 與 **貼入 `SCOUT 3D` 角色穿搭碼 `S3D1_...`**，再由 AI 結合真實佩戴徽章與 GitHub `README` 編排遠近特寫分鏡與廣東話旁白；簡化為單一 **「一鍵複製 CMD 出片指令」**）。

### 2. 本機更新與安裝（Windows CMD）
```bat
cd /d D:\makemovie
git pull
pip install -r requirements.txt
```
> 💡 即使忘記手動安裝新套件，`scout3d_runner.py` 首次啟用廣東話配音時亦會自動幫你安裝 `edge-tts`。

### 3. 本機極速出片流程（支援 `SCOUT 3D` 穿搭碼 · 免經 Git · 直接貼落 CMD 即刻整片）
1. 用瀏覽器或放入 Gemini Canvas 打開 `tools/SCOUT3D_動畫劇本生成器_v2.1.html`
2. 第 1 步先揀 **目標片長**（15 秒～90 秒，自動配對合理分鏡範圍），並可選填貼入由 `SCOUT 3D` 複製過嚟嘅 **`S3D1_...` 角色穿搭碼**
3. 第 2 步撳 **「🤖 AI 全自動」** 或 **「✍️ 我作大綱」** 生成廣東話旁白與遠近特寫 3D 分鏡
4. 撳右邊 **「📋 一鍵複製 CMD 出片指令」** ➔ 貼落 Windows `CMD` 按 **Enter**，即喺 `output\<檔名>.mp4` 生成 1:1 還原徽章穿搭＋廣東話配音＋BGM 嘅 3D 影片！

