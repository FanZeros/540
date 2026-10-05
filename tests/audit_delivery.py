#!/usr/bin/env python3
"""审计每个素材的游戏用途、源码边界和入口，保留完整检查结果。"""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tests" / "output"
usage = {"Background.png": "整屏676×288背景，地面246、四门刷兵",
         "大壮动作.png": "近战FSM全部动作切图", "大壮动作.json": "启动读取Aseprite标签",
         "盾牌男.png": "枪手FSM全部动作切图", "盾牌男.json": "启动读取Aseprite标签",
         "Bullet.png": "敌弹、反弹与箱体飞片", "Crate.png": "可破坏木箱",
         "Barrel.png": "可破坏爆炸桶", "Portal.png": "成对传送区域", "Platform.png": "单向落脚平台",
         "VFX_Jump.png": "跳跃足底光粒", "VFX_Land.png": "落地尘光",
         "VFX_Roll.png": "翻滚光环", "VFX_Slash.png": "挥刀弧光", "受击特效.png": "敌人与玩家受击喷血",
         "大壮攻击特效.png": "近战攻击刀光", "射击特效.png": "枪口火花",
         "Ambient.wav": "循环雨夜氛围", "Music.wav": "循环原创电子节奏"}
for name in ("Idle", "Run", "Prerun", "Stoprun", "Jump", "Land", "Roll", "Slash", "Squat", "Wallslide", "Hit"):
    usage[f"武士零主角/{name}.png"] = "玩家状态动画：" + name
for name in ("jump", "land", "landwire", "prerun", "roll", "wallslide"):
    usage[f"sound_player_{name}.wav"] = "对应玩家动作音效：" + name
usage["sound_playerdie.wav"] = "玩家一击死亡音效"
for i in range(1, 5):
    usage[f"sound_player_running_{i}.wav"] = "跑步脚步轮换变体" + str(i)
for i in range(1, 4):
    usage[f"sound_player_slash_{i}.wav"] = "挥刀轮换变体" + str(i) + "，部分用于敌人枪声"
records = []
unknown = []
for p in sorted((ROOT / "assets").rglob("*")):
    if not p.is_file():
        continue
    path = p.relative_to(ROOT / "assets").as_posix()
    target = path[:-5] if path.endswith(".meta") else path
    purpose = usage.get(target)
    if not purpose:
        unknown.append(path)
    if path.endswith(".meta"):
        purpose = "官方构建导入UUID旁车；对应 " + target + "；不作为画面纹理加载"
    records.append({"path": "assets/" + path, "purpose": purpose, "bytes": p.stat().st_size,
                    "sha256": hashlib.sha256(p.read_bytes()).hexdigest()})
missing = sorted(set(usage) - {r["path"][7:] for r in records})
forbidden = []
absolute = []
for p in sorted((ROOT / "scripts").rglob("*.lua")):
    text = p.read_text()
    if p.name != "TestHarness.lua":
        if re.search(r'CreateComponent\("(?:Physics|Collision|AnimatedSprite|AnimationStateMachine)', text):
            forbidden.append(str(p.relative_to(ROOT)))
        if re.search(r'"/(?:workspace|home|tmp|opt)/', text):
            absolute.append(str(p.relative_to(ROOT)))
report = {"total_assets_including_sidecars": len(records), "game_assets": len(usage),
          "sidecars": sum(r["path"].endswith(".meta") for r in records), "records": records,
          "unknown_assets": unknown, "missing_assets": missing, "forbidden_gameplay_components": forbidden,
          "absolute_paths_in_game_source": absolute,
          "entry_files": {name: (ROOT / name).exists() for name in ["scripts/main.lua", "启动.cmd", "启动.sh"]}}
report["pass"] = not (unknown or missing or forbidden or absolute) and all(report["entry_files"].values())
OUT.mkdir(exist_ok=True)
(OUT / "delivery_audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
lines = ["| 素材文件 | 用途 |", "|---|---|"] + [f'| `{r["path"]}` | {r["purpose"]} |' for r in records]
(OUT / "asset_usage.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("交付审计", "通过" if report["pass"] else "失败", "素材", len(records), "未知", unknown, "遗漏", missing)
raise SystemExit(0 if report["pass"] else 1)
