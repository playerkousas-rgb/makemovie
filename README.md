# 主題故事影片生成器（本機出片 · 多用途）

**你打主題 → AI 寫廣東話劇本＋自由設計場景 → 本機一鍵生成 MP4。**

呢個係一個**多用途嘅本機動畫生成器**，唔係單一產品工具：任何題材（飛出太空、海底尋寶、城市天台、恐龍島…）都可以出片。
`SCOUT 3D` 只係**其中一個可選角色繪製器**（用嚟準確重現童軍制服／徽章），
**唔用 SCOUT 3D 一樣出到片**；故事、世界觀、場景、道具、服裝全部由 AI 自由創作。

## 目录
- AGENTS.md - 俾 AI 睇嘅工作守则
- specs/ - 99 份风格说明书
- prompts/ - 可直接贴去 ARENA.AI 嘅 prompt
- src/ - 2D 雙風格引擎 + **SCOUT 3D 立體角色／場景元件庫**
- assets/scout3d/ - 由 `playerkousas-rgb/SCOUT3D` 官方程式規則直接編譯之精確 3D 人仔比例、徽章座標（`scout3d_rig_data.json`）與 48 張官方透明底徽章 PNG
- presets/ - **可無限重用嘅 3D 角色設定卡（`.json`）**，一次設定演員即可跨集數直接調用
- episodes/ - SCOUT 3D 各集獨立劇本檔（頂頭第 1 行即改粵語字幕）
- tools/ - **3D 主題故事影片生成器 HTML 工具（v3.0，支援 AI 自由場景）**
- output/ - 渲染輸出嘅 MP4 與 Contact Sheet（本機生成）

---

## SCOUT 3D 立體動畫元件庫 ＆ Windows CMD 使用方法

### 1. 核心 3D 元件清單（`src/` ＆ `assets/scout3d/`）
- `src/engine3d.py`：純 Python + NumPy 向量化 3D Ray-Primitive Z-Buffer 攝影棚渲染引擎（支援圓滑膠囊、橢球、圓角方塊、柔和陰影與 `add_textured_patch_3d` 高清 RGBA 透明裁切徽章貼片）。
- `src/scout3d_characters.py`：100% 讀取 `SCOUT3D` 官方 `body.js` + `badgeLayout.js` + `*_rules_v1.0.json` 編譯數據（`assets/scout3d/scout3d_rig_data.json`），精確還原七大制服組別（`grasshopper` 小童軍、`cub` 幼童軍、`scout` 童軍、`sea_scout` 海童軍、`air_scout` 空童軍、`venture` 深資童軍、`leader` 成年領袖）、綠底紅邊左肩斜落右腰專章帶（壓於領巾之下）、2×2 菱形專科章、右袖旅章＋地域／區章並排＋小隊章、以及 `CHARACTER_PRESETS` 可重用 3D 演員庫。
- `scripts/compile_scout3d_rig.mjs`：如需同步最新 `SCOUT3D` 規則，可一鍵由 `SCOUT3D` 源碼重新編譯 `assets/scout3d/`（一般本機 `CMD` 出片完全唔需要裝 Node.js）。
- `src/scout3d_whatif.py`：《如果系列 EP.01：如果你有 SCOUT 3D》完整渲染管線。
- `src/scout3d_runner.py`：通用劇本＋香港廣東話配音執行引擎（支援 `--b64 z_...` 短碼免開檔直接貼落 Windows `CMD` 一鍵出片；內置 `edge-tts` 香港廣東話自然語音合成、**按 `edge-tts` 實測語音長度精準鎖定每鏡秒數（零死空氣）**、以及 BGM 自動壓聲 Ducking；
  另支援 **右下角超小「© SCOUT SYSTEM」水印**（預設只喺片中中間出現 3 秒、有淡入淡出、唔會遮字幕；可用 `watermark: {"enabled": false}` 關閉或自訂文字／`show_sec`）、`story_section`（`grasshopper`／`cub`／`scout`／`sea_scout`／`air_scout`／`venture`／`leader`，貼咗 `S3D1_...` 穿搭碼時以穿搭碼為準）、`actor_skin`（`human`／`ai_robot`）、**`characters` 多角色陣容（1–5 人，每人可獨立支部／真人或 AI／自己嘅制服碼）**，以及 **`camera` 運鏡（可全片固定，亦可逐鏡指定；共 11 種）**）。
- `tools/3D主題故事影片生成器_v3.1.html`：純前端單檔工具（對齊 `© SCOUT SYSTEM` 介面；支援 **15s / 30s / 45s / 60s / 90s 彈性片長**、**主角支部**、**真人／AI 機械人**、`S3D1_...` 制服碼，簡化成 **「一鍵複製 CMD 出片指令」**）。
  - **🎯 主題自由**：打咩主題就寫咩故事（太空、海底、城市、魔法…），唔會夾硬拉返童軍營地；`SCOUT 3D` 只負責角色畫風。
  - **🏞️ AI 自由場景（v3.1 重點）**：AI 用 6 種基本形狀砌 `scene.objects`（位置／大小／顏色／發光／動畫／散佈），可以發明土星環、冰洞、糖果屋；冇場景名單。人手打一句描述，AI 翻譯成 objects。
  - **🎨 逐鏡 AI 重畫場景**：每鏡自由文字框，打「土星環上面有條冰跑道」→ AI 即場砌；亦可揀「AI 自動導演／我揀運鏡／我全權話事」。
  - **👥 多角色陣容**：最多 5 位，每位可獨立支部、真人／AI、自己嘅 `S3D1_...` 制服碼。
  - **水印**：右下角超小「© SCOUT SYSTEM」，只喺片中中間出現 3 秒（可關）。

### 2. 本機更新與安裝（Windows CMD）
```bat
cd /d D:\makemovie
git pull
pip install -r requirements.txt
```
> 💡 即使忘記手動安裝新套件，`scout3d_runner.py` 首次啟用廣東話配音時亦會自動幫你安裝 `edge-tts`。

### 3. 本機極速出片流程（支援 `SCOUT 3D` 穿搭碼 · 免經 Git · 直接貼落 CMD 即刻整片）
1. 用瀏覽器或放入 Gemini Canvas 打開 `tools/3D主題故事影片生成器_v3.1.html`
2. 第 1 步先揀 **目標片長**（15 秒～90 秒，自動配對合理分鏡範圍）＋ **主角支部**（可留空由 AI 判斷）＋ **主角類型**（可留空由 AI 判斷，AI／機械人故事會出 3D 機械人角色），並可選填貼入由 `SCOUT 3D` 複製過嚟嘅 **`S3D1_...` 角色穿搭碼**；想成團有唔同支部，可撳 **「＋ 加一位角色」**（最多 5 人，每人可獨立制服碼），再揀 **AI 導演／我揀運鏡／我話事**
3. 第 2 步打 **主題**（例：`飛出太空`、`海底尋寶`、`如果有個 AI 加入小童軍`），再撳 **「🤖 AI 全自動」** 或 **「✍️ 我作大綱」**：AI 會寫廣東話旁白，**同時自己設計每鏡場景**（唔使你自己揀 preset）
4. 撳右邊 **「📋 一鍵複製 CMD 出片指令」** ➔ 貼落 Windows `CMD` 按 **Enter**，即喺 `output\<檔名>.mp4` 生成 3D 影片（廣東話配音＋字幕＋BGM＋你嘅角色制服）。

### 4. 內置 21 個 3D 鏡位（9 個真實童軍故事場景 ＋ 12 個制服／徽章示範）
**故事場景（純原創童軍故事預設只用呢批）**
`story_arrival_meet`（到達集會打招呼）· `story_group_chat`（小隊圍圈傾偈）· `story_leader_briefing`（領袖講解任務）· `story_challenge_oops`（遇到難題／蝦碌）· `story_camp_outdoors`（戶外營地帳篷松樹）· `story_team_task`（小隊合作）· `story_campfire_night`（營火晚會）· `story_hero_closeup`（主角近鏡）· `story_happy_salute_end`（齊齊敬三指禮）

**制服／徽章示範（有 GitHub 連結或重點講徽章先會用）**
`disaster_wrong_badges` · `scout3d_auto_snap` · `closeup_chest_badges` · `closeup_right_sleeve` · `closeup_left_sleeve` · `leader_guide_explain` · `turntable_360_closeup` · `mom_turntable_sew` · `camp_eve_ready` · `mom_and_kid_proud` · `section_parade` · `dual_salute_praise`

> 例：只打 `如果有個AI 加入小童軍`（GitHub 留空）→ AI 會寫 `story_section: grasshopper`＋`actor_skin: ai_robot`，3D 畫面就係一個著住小童軍橙色活動服＋棗紅領巾嘅 AI 機械人，喺集會、營地、營火會同隊員一齊活動，最後齊齊敬禮，完全唔會變 `SCOUT 3D` 廣告。

### 5. AI 自由場景（冇清單：AI 用基本形狀自己砌）

場景唔係由 preset／props 名單揀。每一鏡嘅 `scene.objects` 由 AI 用 6 種引擎基本形狀砌出嚟，
所以「土星環」、「冰洞」、「糖果屋」、「恐龍骨架」都可以即場發明。**冇 `scene` 就照舊用 `preset`**，舊劇本完全兼容。

```json
{
  "episode_id": "ai_scene_test",
  "shots": [{
    "duration": 3.4,
    "camera": "auto",
    "scene": {
      "objects": [
        {"shape": "ring", "pos": [0, 0.12, -5], "size": [2.5, 0.1], "tube": 0.05,
         "color": "#E8D5A8", "count": 64, "rot": [10, 0, -6]},
        {"shape": "sphere", "pos": [0, 0.12, -5], "size": [0.75], "color": "#D6A26A"},
        {"shape": "box", "pos": [0, 0.02, -1.7], "size": [1.5, 0.04, 0.45],
         "color": "#BFE9FF", "roughness": 0.15, "rot": [0, -12, 0]},
        {"shape": "ellipsoid", "pos": [-1.8, 2.4, -6.5], "size": [0.1, 0.1, 0.1],
         "color": "#FFFFFF", "glow": 0.9,
         "repeat": {"count": 40, "area": [[-4, 4], [0.5, 4.5], [-8, -4]]}}
      ],
      "sky": {"top": "#0A0E22", "bottom": "#2A2144"},
      "floor": false,
      "framing": "wide",
      "float": true
    },
    "narration": "土星環上面有條發光冰跑道。",
    "subtitle": "土星環上面\n有條發光冰跑道"
  }]
}
```

**6 種 shape**

| shape | size 意思 |
|---|---|
| `sphere` | `[半徑]` |
| `ellipsoid` | `[rx, ry, rz]`（拉長／壓扁） |
| `box` | `[半邊長 x, y, z]`，`bevel` 控制圓角 |
| `capsule` / `cylinder` | `[半徑, 長度]`，`axis: x/y/z` |
| `ring` | `[半徑, 粗幼]`，`tube`、`count` 控制每節粗細／密度 |

每個 object 亦可加：`rot`（度）、`color`、`glow` 0–1、`roughness`、`anim`（`bob` / `drift` / `spin` / `pulse`）、
`repeat`（`count` + `area` 散佈，適合星星／碎石／螢火蟲）。
scene 層可用：`sky`、`floor`（`{color,y}` 或 `false`）、`framing`、`float`、`cast:false`（純景物空鏡）。

> `kind`（space／city／snow…）同 `props` 只係可選捷徑，唔再係限制；AI 用 `objects` 就唔會加預設 props。

```bat
python src/scout3d_runner.py --list-shapes
python src/scout3d_runner.py --spec episodes/story_example.json
```

### 5b. 喺 Gemini Canvas 直接測試 AI（免本機 key）

HTML 第 2 步下面有 **「🧪 AI 場景測試（唔出片）」**：打一句場景描述，撳一下，
就會用 Canvas 自動注入嘅 Gemini Key 問 AI，即場顯示 **AI 原始回覆＋格式驗證**。
唔會出片、唔會改劇本，用嚟確認 AI 真係有砌 `objects`，定係偷懶用 preset。

生成故事之後，如果 AI 冇出場景，預覽會顯示 **「⚠️ preset（AI 未出場景）」**，
狀態欄亦會講有幾鏡缺場景，唔會再靜靜哋當成功。

### 5c. 真實 AI 測試 script（可選，本機用）

HTML 每一鏡都有 **「場景描述」自由文字框**：你打字，撳 **「🎨 叫 AI 用呢段描述重畫場景」**，
AI 會將你嘅描述翻譯成 `scene.objects`，再寫入 CMD payload。
第 2 步亦可以填「場景／世界觀描述」，生成故事時一次過交畀 AI。

想喺 terminal 直接測試 AI（唔經 UI）：

```bat
set GEMINI_API_KEY=你的key
python scripts/ai_scene_test.py --text "土星環上面有條發光冰跑道，遠處見到地球" --raw-out output/ai_raw.txt --render
```

- 你打嘅字直接送去 Gemini，AI 自己決定物件、顏色、位置、動畫
- Script 只做**格式驗證**（`normalize_episode_spec`），唔會幫 AI 改場景內容
- `--raw-out` 會保存 AI 原始回覆，方便 debug
- `--render` 會直接用 AI 回傳嘅 JSON 出 MP4（**冇人手寫嘅場景**）
- 如果 AI 亂作 shape，script 會報錯並印出可辨識嘅 6 種形狀
- 已經有 AI 原始回覆？`--raw-file output/ai_raw.txt` 可以離線驗證／渲染

### 5d. 語音引擎（edge-tts / Piper / Coqui / 自訂指令）

配音唔再焊死喺 edge-tts。spec 加三個欄位就得，留空即沿用 edge-tts：

```json
{
  "voice": "zh-HK-HiuMaanNeural",
  "voice_rate": "+6%",
  "voice_engine": "piper",
  "voice_model": "D:/tts/voices/zh_CN-huayan-medium.onnx",
  "tts_command": "mytts --in {text_file} --out {out}"
}
```

| `voice_engine` | 需要 | 粵語？ | 備註 |
|---|---|---|---|
| `edge`（預設） | 網絡 | ✅ HiuMaan / WanLung 等 | 免費微軟雲端，暫時係粵語最自然 |
| `piper` | `pip install piper-tts` ＋ ONNX 聲線 | ❌ 只有普通話 | 純 CPU、極快、完全離線；`PIPER_BIN` 可指定 exe |
| `coqui` | `pip install TTS` ＋ 模型名 | ✅ 有粵語社群模型 | 較慢，第一次會落模型；`voice_model` 填 Coqui 模型名 |
| `command` | 任何本機 TTS CLI | 睇你用邊個 | 支援 `{out}`（輸出檔）、`{text_file}`（逐句文字）、`{text}`、`{voice}` |

重點：**目前冇大型歐洲開源引擎出到粵語**（Kyutai Pocket TTS 只有 6 種歐洲語言；Piper 44 個 locale 得普通話，冇粵語）。
所以粵語預設仍然係 edge-tts，其他語言／完全離線就可以揀 Piper 或 Coqui。

本機亦可以直接用 CLI 指定（會覆寫 spec）：

```bat
python src/scout3d_runner.py --spec episodes/story_example.json --tts-engine piper --tts-model D:\tts\voices\zh_CN-huayan-medium.onnx
python src/scout3d_runner.py --b64 z_xxx --tts-engine command --tts-command "mytts --in {text_file} --out {out}"
```

HTML 第 3 步有 **「🔊 語音引擎（進階）」** 摺疊欄：填一次就會寫入 CMD payload，唔使改 Python。
合成失敗（模型未裝、指令錯）只會令該鏡轉純 BGM，唔會令成套片 crash。

### 6. 多角色 ＋ 運鏡 spec 寫法（`characters` / `camera`）

```json
{
  "episode_id": "scout_story_multi_section",
  "story_section": "grasshopper",
  "actor_skin": "ai_robot",
  "camera": "auto",
  "characters": [
    {"name": "AI", "section": "grasshopper", "actor_skin": "ai_robot"},
    {"name": "小明", "section": "cub"},
    {"name": "阿珍", "section": "scout", "uniform_code": "S3D1_..."}
  ],
  "shots": [
    {"preset": "story_arrival_meet", "camera": "push_in", "duration": 3.0, "narration": "…", "subtitle": "…"},
    {"preset": "story_group_chat", "camera": "orbit_left", "duration": 3.0, "narration": "…", "subtitle": "…"}
  ]
}
```

- `characters`：最多 5 位；第一位係主角。每項可加 `section`（7 個支部）、`actor_skin`（`human`／`ai_robot`）同 `uniform_code`（`S3D1_...`，貼咗就以碼為準）。舊 spec 冇 `characters` 會自動當單一主角。
- `camera`：`auto`（跟場景原有運鏡）／`push_in`／`pull_out`／`pan_left`／`pan_right`／`tilt_up`／`orbit_left`／`orbit_right`／`crane_up`／`low_angle`／`handheld`。可以寫喺 episode 做預設，亦可以每鏡覆蓋。

```bat
python src/scout3d_runner.py --spec episodes/story_example.json
python src/scout3d_runner.py --list-presets
python src/scout3d_runner.py --list-cameras
python src/scout3d_runner.py --list-scenes
python src/scout3d_runner.py --list-props
```

