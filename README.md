# 3D 主題故事影片生成器（本機出片）

**你打主題 → AI 寫廣東話劇本＋自由設計場景 → 本機一鍵生成 3D MP4。**

呢個係一個**個人用嘅主題→影片工具**：任何題材（飛出太空、海底尋寶、城市天台、恐龍島…）都可以出片。
角色由 `SCOUT 3D` 引擎畫成童軍制服 3D 人仔 —— **SCOUT 3D 只係「角色繪製器」，唔係成個 app 嘅主題**，
所以故事、世界觀、場景、道具全部由 AI 自由創作，唔會硬銷任何產品。

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
- `tools/3D主題故事影片生成器_v3.0.html`：純前端單檔工具（對齊 `© SCOUT SYSTEM` 介面；支援 **15s / 30s / 45s / 60s / 90s 彈性片長**、**主角支部**、**真人／AI 機械人**、`S3D1_...` 制服碼，簡化成 **「一鍵複製 CMD 出片指令」**）。
  - **🎯 主題自由**：打咩主題就寫咩故事（太空、海底、城市、魔法…），唔會夾硬拉返童軍營地；`SCOUT 3D` 只負責角色畫風。
  - **🏞️ AI 自由場景（v3.0 重點）**：AI 用 `scene` 積木自己砌背景（11 種 `kind` × 20 種 `props` ＋色盤 ＋鏡位 framing），唔再局限於 9 個 preset。Preset 只係手動備用。
  - **🎥 場景／運鏡分開**：「AI 自動導演」／「我揀運鏡」／「我全權話事」，劇本生成後仍可逐鏡改場景類型同運鏡。
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
1. 用瀏覽器或放入 Gemini Canvas 打開 `tools/3D主題故事影片生成器_v3.0.html`
2. 第 1 步先揀 **目標片長**（15 秒～90 秒，自動配對合理分鏡範圍）＋ **主角支部**（可留空由 AI 判斷）＋ **主角類型**（可留空由 AI 判斷，AI／機械人故事會出 3D 機械人角色），並可選填貼入由 `SCOUT 3D` 複製過嚟嘅 **`S3D1_...` 角色穿搭碼**；想成團有唔同支部，可撳 **「＋ 加一位角色」**（最多 5 人，每人可獨立制服碼），再揀 **AI 導演／我揀運鏡／我話事**
3. 第 2 步打 **主題**（例：`飛出太空`、`海底尋寶`、`如果有個 AI 加入小童軍`），再撳 **「🤖 AI 全自動」** 或 **「✍️ 我作大綱」**：AI 會寫廣東話旁白，**同時自己設計每鏡場景**（唔使你自己揀 preset）
4. 撳右邊 **「📋 一鍵複製 CMD 出片指令」** ➔ 貼落 Windows `CMD` 按 **Enter**，即喺 `output\<檔名>.mp4` 生成 3D 影片（廣東話配音＋字幕＋BGM＋你嘅角色制服）。

### 4. 內置 21 個 3D 鏡位（9 個真實童軍故事場景 ＋ 12 個制服／徽章示範）
**故事場景（純原創童軍故事預設只用呢批）**
`story_arrival_meet`（到達集會打招呼）· `story_group_chat`（小隊圍圈傾偈）· `story_leader_briefing`（領袖講解任務）· `story_challenge_oops`（遇到難題／蝦碌）· `story_camp_outdoors`（戶外營地帳篷松樹）· `story_team_task`（小隊合作）· `story_campfire_night`（營火晚會）· `story_hero_closeup`（主角近鏡）· `story_happy_salute_end`（齊齊敬三指禮）

**制服／徽章示範（有 GitHub 連結或重點講徽章先會用）**
`disaster_wrong_badges` · `scout3d_auto_snap` · `closeup_chest_badges` · `closeup_right_sleeve` · `closeup_left_sleeve` · `leader_guide_explain` · `turntable_360_closeup` · `mom_turntable_sew` · `camp_eve_ready` · `mom_and_kid_proud` · `section_parade` · `dual_salute_praise`

> 例：只打 `如果有個AI 加入小童軍`（GitHub 留空）→ AI 會寫 `story_section: grasshopper`＋`actor_skin: ai_robot`，3D 畫面就係一個著住小童軍橙色活動服＋棗紅領巾嘅 AI 機械人，喺集會、營地、營火會同隊員一齊活動，最後齊齊敬禮，完全唔會變 `SCOUT 3D` 廣告。

### 5. AI 自由場景 `scene`（v3.0 重點）

你（或者 AI）可以喺 episode 或每一鏡加 `scene`，自由組合背景同道具；**冇 `scene` 就照舊用 `preset`**，所以所有舊劇本完全兼容。

```json
{
  "episode_id": "space_adventure_ep01",
  "story_section": "grasshopper",
  "actor_skin": "ai_robot",
  "shots": [
    {
      "duration": 3.4,
      "camera": "tilt_up",
      "scene": {
        "kind": "space",
        "props": ["stars", "planet", "rocket"],
        "framing": "wide",
        "float": true,
        "palette": {"sky_top": "#05081A", "sky_bottom": "#241A46"}
      },
      "narration": "火箭一點火，三、二、一，衝破雲層！",
      "subtitle": "三、二、一\n衝破雲層！"
    }
  ]
}
```

- `kind`（背景）：`space` 太空 · `sky` 高空 · `sunset` 黃昏 · `night` 夜晚 · `forest` 森林／營地 · `beach` 海灘 · `snow` 雪地 · `city` 城市 · `indoor` 室內 · `underwater` 海底 · `void` 虛空
- `props`（可選 0–8 個）：`stars`、`moon`、`planet`、`rocket`、`satellite`、`asteroid`、`cloud`、`tent`、`campfire`、`pine`、`palm`、`rock`、`crystal`、`snowman`、`balloon`、`building`、`streetlamp`、`book`、`flag`、`bubble`
- `framing`：`wide`（遠景）／`medium`（中景）／`closeup`（特寫）
- `float`：角色漂浮（太空／虛空／天空預設 `true`）
- 亦可寫簡寫：`"scene": "太空"` 或 `"scene": "space"`，道具會用該背景嘅預設組合。
- 場景可以寫喺 episode 做全片預設，每鏡再覆蓋。

```bat
python src/scout3d_runner.py --list-scenes
python src/scout3d_runner.py --list-props
python src/scout3d_runner.py --spec episodes/story_example.json
```

> 示範成品：`preview/space_adventure_preview.mp4`（夜晚營地 → 火箭升空 → 月球／衛星 → 隕石 → 光環行星插旗 → 太空回望地球）。

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

