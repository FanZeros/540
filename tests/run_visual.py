#!/usr/bin/env python3
"""在官方 UrhoX 引擎中运行真实渲染与动作机器人，不启动服务器。"""
import argparse
import concurrent.futures
import json
import os
import subprocess
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "tests" / "output"
CASES = [
    ("final_title", "main.lua", 140, []),
    ("final_action", "TestHarness.lua", 560, ["-test-level=1", "-test-style=campaign"]),
    ("final_portal", "TestHarness.lua", 240, ["-test-level=4", "-test-style=campaign"]),
    ("final_rewind", "TestHarness.lua", 480, ["-test-level=2", "-test-style=death"]),
    ("final_jump", "TestHarness.lua", 80, ["-test-level=1", "-test-style=jump"]),
    ("final_roll", "TestHarness.lua", 166, ["-test-level=1", "-test-style=jump"]),
    ("final_replay", "TestHarness.lua", 1100, ["-test-level=1", "-test-style=campaign"]),
]

def run(case, suffix):
    base_name, entry, shot_frame, extra = case
    name=base_name+suffix
    work = OUTPUT / (name + "_runtime")
    work.mkdir(parents=True, exist_ok=True)
    runtime = ROOT / "tests" / "runtime" / ("UrhoXRuntime.exe" if os.name == "nt" else "UrhoXRuntime")
    shot = OUTPUT / (name + ".png")
    report = OUTPUT / (name + ".json")
    cmd = [str(runtime), entry, f"-tapcode_dir={ROOT}", "-tool_mode",
           "-validate", f"-validate-frames={shot_frame+40}", "-validate-timeout=110",
           "-validate-spike-threshold=10000", f"-validate-output={report}",
           f"-screenshot={shot}", f"-screenshot-frame={shot_frame}",
           "-x", "1352", "-y", "576", "-nosound", *extra]
    env = os.environ.copy()
    env.update(HOME=str(work), TMPDIR=str(work), XDG_CACHE_HOME=str(work), XDG_CONFIG_HOME=str(work),
               XDG_DATA_HOME=str(work), HTTP_PROXY="http://127.0.0.1:1080", HTTPS_PROXY="http://127.0.0.1:1080",
               PYTHONDONTWRITEBYTECODE="1")
    if os.name != "nt" and os.sys.platform != "darwin":
        cmd.append("-graphicssurfaceless")
        env.update(LIBGL_ALWAYS_SOFTWARE="1", GALLIUM_DRIVER="llvmpipe", EGL_PLATFORM="surfaceless")
    log = OUTPUT / (name + ".log")
    if any(p.exists() for p in (shot, report, log)):
        raise RuntimeError("此后缀已有测试产物，请使用新 --suffix，避免覆盖原始证据："+name)
    with log.open("w", encoding="utf-8") as out:
        out.write("命令：" + subprocess.list2cmdline(cmd) + "\n")
        out.flush()
        try:
            proc = subprocess.run(cmd, cwd=work, env=env, stdout=out, stderr=subprocess.STDOUT, timeout=120)
            code = proc.returncode
        except subprocess.TimeoutExpired:
            code = 124
        out.write("\n退出码：" + str(code) + "\n")
    r = json.loads(report.read_text()) if report.exists() else {}
    errors = [e for p in r.get("phases", {}).values() for e in p.get("errors", [])]
    # 不隐藏原始状态；截图读回的软件渲染尖刺单独报告。
    noise = [e for e in errors if "Frame time spike" in e["message"] or "[ShaderError]" in e["message"]]
    real = [e for e in errors if e not in noise]
    image_ok = shot.exists() and shot.stat().st_size > 0
    if image_ok:
        with Image.open(shot) as im:
            image_ok = im.size == (1352, 576) and len(im.getcolors(1000000) or []) > 100
    row = {"name": name, "command": cmd, "exit": code, "raw_result": r.get("result"),
           "real_errors": real, "noise": noise, "missing_resources": r.get("missing_resources", []),
           "frames": r.get("frames_completed"), "image_ok": image_ok,
           "png": str(shot.relative_to(ROOT)), "log": str(log.relative_to(ROOT))}
    row["rendered_without_script_errors"] = image_ok and not real and not row["missing_resources"] and code not in (124, 139)
    row["passed"] = row["rendered_without_script_errors"] and code == 0 and r.get("result") == "PASS"
    return row

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", default="all", choices=["all"] + [c[0] for c in CASES])
    parser.add_argument("--suffix",default="_v3",help="为新测试保留独立文件名")
    args = parser.parse_args()
    if not args.suffix.replace("_", "").isalnum(): parser.error("后缀只能包含字母数字下划线")
    OUTPUT.mkdir(exist_ok=True)
    summary_tag=args.suffix+("" if args.case=="all" else "_"+args.case)
    summary_path=OUTPUT / ("visual_summary"+summary_tag+".json")
    contact_path=OUTPUT / ("visual_contact"+summary_tag+".png")
    if summary_path.exists() or contact_path.exists():
        parser.error("汇总文件已存在，请选用新后缀，原始证据不会覆盖")
    cases = CASES if args.case == "all" else [c for c in CASES if c[0] == args.case]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(lambda c: run(c,args.suffix), cases))
    result = {"backend": "真实 UrhoX / NanoVG 软件离屏渲染", "cases": rows,
              "limitations": ["机器人动作输入，不等同实体键盘/鼠标操作；当前环境无可听音频输出。",
                              "独立场景截图并不替代 simulation.lua 的连续十关流程。"]}
    summary_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    images = [Image.open(OUTPUT / (r["name"] + ".png")).convert("RGB") for r in rows if r["image_ok"]]
    if images:
        sheet = Image.new("RGB", (676, 288 * len(images)), (5, 7, 16))
        for i, im in enumerate(images):
            sheet.paste(im.resize((676, 288), Image.Resampling.NEAREST), (0, i * 288))
        sheet.save(contact_path)
    for row in rows:
        print(row["name"], "通过" if row["passed"] else "失败", "原始报告", row["raw_result"], "实错", len(row["real_errors"]))
    raise SystemExit(0 if all(r["passed"] for r in rows) else 1)

if __name__ == "__main__":
    main()
