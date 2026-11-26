# docs/ — 靜態部署用（GitHub Pages / Vercel）

`index.html` 係 `tools/3D主題故事影片生成器_v3.1.html` 嘅**部署副本**，
放成 `index.html` 就可以零設定當網站首頁。

**更新方法（工具改完之後）：**
```bash
cp "tools/3D主題故事影片生成器_v3.1.html" docs/index.html
```

## GitHub Pages
Repo → Settings → **Pages** → Source: **Deploy from a branch** → Branch: `main` / Folder: **/docs** → Save。
之後開 `https://<你的帳號>.github.io/makemovie/`。

## Vercel
Import repo → **Root Directory** = `docs` → Framework Preset = **Other** → Build Command 留空 → Output Directory = `.`
（或者本機 `npm i -g vercel` 後喺 `docs/` 內執行 `vercel --prod`）
