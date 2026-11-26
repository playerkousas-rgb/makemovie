#!/usr/bin/env python3
"""真實 AI 場景測試：你打一句描述 → Gemini 自己砌場景 JSON → runner 照 AI 輸出渲染。

呢個 script 嘅重點係「AI 實際測試」：
  · 唔會用任何預先寫好嘅場景或 preset
  · 你打嘅字直接送去 Gemini，AI 自己決定物件、顏色、位置、動畫
  · 收到嘅 JSON 只做格式驗證（唔會幫 AI 改內容），再交畀 scout3d_runner 出片

用法（Windows CMD）：
  set GEMINI_API_KEY=你的key
  python scripts/ai_scene_test.py --text "土星環上面有條發光冰跑道，遠處見到地球" --render
  python scripts/ai_scene_test.py --text "海底城市，霓虹珊瑚同水母" --out output/ai_scene.json
  python scripts/ai_scene_test.py --text "..." --raw-out output/ai_scene_raw.txt

Privacy: 金鑰只會喺記憶體用，唔會寫入任何檔案。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scout3d_runner import normalize_episode_spec  # noqa: E402

MODELS = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-flash-latest"]

SCENE_DOC = """【自由場景規格：冇 preset 清單，由你自己用基本形狀砌】
可用 shape：sphere（球）／ellipsoid（橢球）／box（圓角方塊）／capsule（膠囊）／cylinder（圓柱）／ring（環，tube 控制粗幼）
每個 object：
  pos [x,y,z]            角色企喺 y≈0，鏡頭望住 (0,1.2,0)；x 約 ±2 係畫面中心
  size                   球＝半徑；橢球＝[rx,ry,rz]；方塊＝[半邊長x,y,z]；柱／膠囊＝[半徑,長度]；環＝[半徑,粗幼]
  color "#RRGGBB"        glow 0–1（發光）      rot [x,y,z] 度      roughness 0–1
  anim                   {"kind":"bob|drift|spin|pulse","amp":0.15,"speed":1.0}
  repeat                 {"count":40,"area":[[x0,x1],[y0,y1],[z0,z1]]}
scene：
  objects []             1–24 件（repeat.count ≤ 60）
  sky {top,bottom}       顏色；floor {color,y} 或 false
  framing                wide | medium | closeup
  float                  角色漂浮（無地面通常 true）
  cast                   false＝純景物空鏡（測試場景時建議 false）

限制：物件唔好遮住角色面部；顏色要跟描述嘅氣氛。
只輸出純 JSON：{"scene":{"objects":[...],"sky":{"top":"#...","bottom":"#..."},"floor":false,"framing":"wide","float":true,"cast":false}}"""


def build_prompt(desc: str, framing: str, cast: bool) -> str:
    return f"""你係 3D 場景美術指導。將用戶嘅描述翻譯成引擎用到嘅場景 JSON。

【用戶描述】
{desc}

{SCENE_DOC}

【今次設定】
framing = {framing}
cast = {str(cast).lower()}

只輸出 JSON，唔要解釋、唔要 markdown。"""


def extract_json(text: str):
    t = (text or "").strip()
    t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.I)
    t = re.sub(r"```\s*$", "", t).strip()
    a, b = t.find("{"), t.rfind("}")
    if a < 0 or b <= a:
        return None
    try:
        return json.loads(t[a : b + 1])
    except json.JSONDecodeError:
        return None


def call_gemini(prompt: str, key: str, model: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.9, "maxOutputTokens": 4096},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    parts = (((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or [])
    return "".join(p.get("text", "") for p in parts if isinstance(p, dict))


def scene_report(scene: dict) -> str:
    objs = scene.get("objects") or []
    shapes = {}
    glow = 0
    repeats = 0
    for o in objs:
        shapes[o.get("shape", "?")] = shapes.get(o.get("shape", "?"), 0) + 1
        if float(o.get("glow") or 0) > 0:
            glow += 1
        if o.get("repeat"):
            repeats += int((o.get("repeat") or {}).get("count") or 0)
    sky = scene.get("palette") or {}
    floor = scene.get("floor")
    return (
        f"objects={len(objs)}（{', '.join(f'{k}×{v}' for k, v in shapes.items()) or '無'}）"
        f" · repeat={repeats} · glow={glow}"
        f" · sky={sky.get('sky_top', '預設')}/{sky.get('sky_bottom', '預設')}"
        f" · floor={'無' if floor is False else (floor or '預設')}"
        f" · framing={scene.get('framing')} · float={scene.get('float')} · cast={scene.get('cast')}"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="用真 Gemini 測試 AI 自由場景")
    ap.add_argument("--text", required=True, help="你自己打嘅場景描述")
    ap.add_argument("--key", default="", help="Gemini API key（預設讀 GEMINI_API_KEY 環境變數）")
    ap.add_argument("--model", default="", help="模型（預設自動試 gemini-2.5-flash → pro → latest）")
    ap.add_argument("--out", default="output/ai_scene.json", help="AI 回傳場景嘅 spec 輸出路徑")
    ap.add_argument("--raw-out", default="", help="另存 AI 原始回覆（debug 用）")
    ap.add_argument("--raw-file", default="", help="唔連網，直接用你貼出嚟嘅 AI 原始回覆檔做驗證／渲染")
    ap.add_argument("--render", action="store_true", help="即刻用 AI 回傳嘅 JSON 出 MP4")
    ap.add_argument("--mp4", default="", help="MP4 路徑（預設 output/ai_scene_test.mp4）")
    ap.add_argument("--aspect", default="9:16", choices=["9:16", "16:9", "1:1"])
    ap.add_argument("--framing", default="wide", choices=["wide", "medium", "closeup"])
    ap.add_argument("--cast", action="store_true", help="畫面加入主角（預設純景物空鏡）")
    args = ap.parse_args()

    raw, last_err = "", None
    if args.raw_file:
        raw = Path(args.raw_file).read_text(encoding="utf-8")
        print(f"[ai-test] 用現成 AI 原始回覆：{args.raw_file}（唔連網）")
    else:
        key = (args.key or os.environ.get("GEMINI_API_KEY") or "").strip()
        if not key:
            print("✗ 未提供 Gemini key：請設定 GEMINI_API_KEY，或用 --key（唔好貼落 chat）。", file=sys.stderr)
            return 2
        prompt = build_prompt(args.text.strip(), args.framing, args.cast)
        models = [args.model] if args.model else MODELS
        for model in models:
            try:
                print(f"[ai-test] 問 {model} 設計場景…")
                raw = call_gemini(prompt, key, model)
                if raw.strip():
                    break
            except urllib.error.HTTPError as exc:
                last_err = f"{model}: HTTP {exc.code} {exc.reason}"
                print(f"  ! {last_err}", file=sys.stderr)
            except Exception as exc:  # noqa: BLE001
                last_err = f"{model}: {exc}"
                print(f"  ! {last_err}", file=sys.stderr)
        if not raw.strip():
            print(f"✗ AI 冇回覆（{last_err or 'unknown'}）", file=sys.stderr)
            return 1

    if args.raw_out:
        Path(args.raw_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.raw_out).write_text(raw, encoding="utf-8")

    obj = extract_json(raw)
    if not obj:
        print("✗ AI 回覆唔係有效 JSON（用 --raw-out 睇原始回覆）", file=sys.stderr)
        return 1
    scene_raw = obj.get("scene") if isinstance(obj, dict) and "scene" in obj else obj
    allowed = {"sphere", "ellipsoid", "box", "capsule", "cylinder", "ring"}
    raw_objs = scene_raw.get("objects") if isinstance(scene_raw, dict) else None
    if isinstance(raw_objs, list):
        bad = [str(o.get("shape")) for o in raw_objs if isinstance(o, dict) and str(o.get("shape", "")).lower() not in allowed]
        good = [o for o in raw_objs if isinstance(o, dict) and str(o.get("shape", "")).lower() in allowed]
        if bad:
            print(f"⚠ AI 用咗唔存在嘅 shape：{bad}（只支援 {sorted(allowed)}；已當作 sphere）", file=sys.stderr)
        if not good:
            print("✗ AI 冇用任何合法 shape，場景唔可信；試下再生成。", file=sys.stderr)
            return 1

    spec_raw = {
        "episode_id": "ai_scene_test",
        "series_badge": "AI 場景測試",
        "aspect": args.aspect,
        "fps": 24,
        "voice": "none",
        "story_section": "grasshopper",
        "actor_skin": "human",
        "shots": [
            {
                "duration": 3.4,
                "camera": "auto",
                "scene": scene_raw,
                "narration": args.text.strip(),
                "subtitle": args.text.strip()[:26],
            }
        ],
    }
    if args.cast:
        spec_raw["characters"] = [{"name": "主角", "section": "grasshopper"}]

    try:
        norm = normalize_episode_spec(spec_raw)
    except Exception as exc:  # noqa: BLE001
        print(f"✗ 場景格式驗證失敗：{exc}", file=sys.stderr)
        return 1
    scene = norm["shots"][0].get("scene")
    if not scene:
        print("✗ AI 輸出冇可辨識嘅場景物件（可能亂作形狀名）", file=sys.stderr)
        return 1
    if not scene.get("objects"):
        print("⚠ AI 冇用 objects，而係用咗舊 kind/props 清單 —— 呢個就係要修嘅問題。", file=sys.stderr)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(norm, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[ai-test] AI 場景驗證完成：")
    print("  " + scene_report(scene))
    print(f"  spec → {out}")

    if args.render:
        mp4 = Path(args.mp4 or "output/ai_scene_test.mp4")
        mp4.parent.mkdir(parents=True, exist_ok=True)
        cmd = [sys.executable, str(ROOT / "src" / "scout3d_runner.py"),
               "--spec", str(out), "--voice", "none", "--out", str(mp4), "--force"]
        print("[ai-test] 直接用 AI 回傳嘅 JSON 渲染：", " ".join(cmd))
        rc = subprocess.call(cmd, cwd=str(ROOT))
        if rc != 0:
            print("✗ 渲染失敗", file=sys.stderr)
            return rc
        print(f"✓ MP4 → {mp4}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
