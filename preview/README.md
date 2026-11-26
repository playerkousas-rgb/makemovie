# 3D 主題故事影片預覽

| 檔案 | 內容 |
|---|---|
| `index.html` | 一頁睇晒：影片播放器＋分鏡表（用瀏覽器開） |
| `animal_mixed_v2_preview.mp4` | **v3.2 示範**：真人＋貓（biped）＋羊（quadruped）兩鏡，106 格 720p |
| `visual_final_day.png` | v3.2 日間定格：無限草地、日間雲、太陽光暈、接觸陰影 |
| `visual_final_space.png` | v3.2 太空定格：自動星空、行星環加密、夜間調色 |
| `space_adventure_preview.mp4` | **v3.0 示範**：「飛出太空」6 鏡 20 秒，AI 自由場景（夜晚營地→太空→月球→隕石→行星→回望地球） |
| `contact_sheet_space_adventure.jpg` | 太空示範 24 格分鏡表 |
| `story_ai_joins_grasshopper_preview.mp4` | 21 秒 9:16 無聲預覽（BGM 版；有聲版喺你部機用 edge-tts 生成） |
| `story_preview.gif` | 270px 輕量動態 GIF（方便直接預覽） |
| `contact_sheet_story_ai_joins_grasshopper.jpg` | 24 格分鏡表（原尺寸） |
| `story_contact_sheet_small.jpg` | 分鏡表縮圖 |
| `story_multi_section_preview.mp4` | 新功能示範：4 位不同支部角色＋4 種運鏡（9.6 秒） |
| `contact_sheet_story_multi_section_preview.jpg` | 多角色分鏡表 |

太空示範用 `scene` 積木：`kind: space/night` ＋ `props: stars, planet, rocket, moon, satellite, asteroid, flag, campfire, tent`，三個角色（AI 機械人＋幼童軍＋童軍）。

舊示範：小童軍（橙色活動服＋棗紅領巾）＋ AI 機械人主角，7 鏡：集會打招呼 → 圍圈自我介紹 →
領袖講解任務 → 戶外搬營具 → 合作起帳篷 → 夜晚營火會 → 齊齊敬三指禮。
片中中間 3 秒右下角有超小「© SCOUT SYSTEM」水印。

## v2.3 新功能示範（4 人）
`story_multi_section_preview.mp4` 用 `characters` 加入小童軍 AI 機械人、幼童軍、童軍、成年領袖，
四鏡分別用 `push_in` → `orbit_left` → `pull_out` → `crane_up` 運鏡。
