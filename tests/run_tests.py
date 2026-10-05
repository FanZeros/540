#!/usr/bin/env python3
"""离线自测：使用项目内官方运行器的真实 Lua 5.4，不安装依赖、不修改玩法。
仅生成 tests/output/simulation* 和 test_report*。退出码：0通过，1用例失败，2未能验证。
Windows 分支仅兼容代码，未在本机实测。
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
try:
    import resource
except ImportError:
    resource = None

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "tests" / "output"
MODULES = ["Config", "World", "Player", "Enemies", "Combat", "Collision", "Replay", "Effects"]
STATUS = {"pass": "通过", "fail": "失败", "blocked": "未运行", "inconclusive": "结果待确认"}


def hashes():
    files = [ROOT / "scripts" / "Game" / (n + ".lua") for n in MODULES]
    files += [ROOT / "scripts" / "main.lua", ROOT / "计划.md", ROOT / "tests" / "simulation.lua"]
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.exists()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=int, default=600, help="运行器实际超时秒数")
    parser.add_argument("--suffix", default="", help="保留独立记录，例如 _v3")
    args = parser.parse_args()
    if args.suffix and (not args.suffix.startswith("_") or not args.suffix.replace("_", "").isalnum()):
        parser.error("记录后缀必须为下划线和英数字")
    OUTPUT.mkdir(exist_ok=True)
    # 引擎自行生成日志和缓存；工作目录及各用户目录指向测试产物树。
    sandbox = OUTPUT / ("simulation_runtime" + args.suffix)
    sandbox.mkdir(exist_ok=True)
    runtime = ROOT / "tests" / "runtime" / ("UrhoXRuntime.exe" if os.name == "nt" else "UrhoXRuntime")
    cmd = [str(runtime), str(ROOT / "tests" / "simulation.lua"), "-tapcode_dir=" + str(ROOT),
           "-tool_mode", "-graphicsheadless", "-nosound", "-log", "warning"]
    env = os.environ.copy()
    env.update(HOME=str(sandbox), TMPDIR=str(sandbox), XDG_DATA_HOME=str(sandbox),
               XDG_CONFIG_HOME=str(sandbox), XDG_CACHE_HOME=str(sandbox),
               SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy", PYTHONDONTWRITEBYTECODE="1")
    # 仅保留受控代理；测试不主动发出任何网络请求，不安装任何软件。
    env.update(http_proxy="http://127.0.0.1:1080", https_proxy="http://127.0.0.1:1080",
               HTTP_PROXY="http://127.0.0.1:1080", HTTPS_PROXY="http://127.0.0.1:1080")
    before = hashes()
    started = time.time()
    path = OUTPUT / ("simulation" + args.suffix + ".stdout.log")
    timeout, launch_error = False, None
    try:
        with path.open("wb") as out:
            out.write(("$ " + subprocess.list2cmdline(cmd) + "\n工作目录=" + str(sandbox) + "\n").encode())
            out.flush()
            process = subprocess.Popen(cmd, cwd=sandbox, env=env, stdout=out, stderr=subprocess.STDOUT,
                                       start_new_session=os.name != "nt")
            try:
                code = process.wait(timeout=args.timeout)
            except subprocess.TimeoutExpired:
                timeout = True
                process.kill()
                code = process.wait()
            out.write(("\nRUNNER_RETURN_CODE=" + str(code) + "\n").encode())
    except OSError as exc:
        launch_error, code = str(exc), None
        path.write_text("运行器启动失败=" + launch_error + "\n", encoding="utf-8")
    elapsed = time.time() - started
    text = path.read_text(encoding="utf-8", errors="replace")
    marker, report = "SIMULATION_REPORT_JSON ", None
    for line in text.splitlines():
        if marker in line:
            try:
                report = json.loads(line.split(marker, 1)[1])
            except json.JSONDecodeError:
                pass
    after = hashes()
    changed = [name for name in before if after.get(name) != before[name]]
    result = {
        "schema": 1, "command": cmd, "cwd": str(sandbox), "wall_seconds": elapsed,
        "returncode": code, "timeout": timeout, "launch_error": launch_error,
        "source_hashes_before": before, "source_hashes_after": after, "changed_during_run": changed,
        "max_child_rss_kib": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss if resource else None,
        "stdout": str(path), "execution_backend": "官方 UrhoXRuntime 内嵌 Lua 5.4",
        "network_or_install_by_runner": False, "simulation": report,
        "limitations": ["仅验证实际 Lua 逻辑，未声称实测画面、可听声音或操作系统键盘投递。",
                        "隔离单测可安排初始场景；十关和200k长测只使用合法动作输入，不改玩家敌人状态。",
                        "引擎启动的Noop界面着色器警告不计入玩法测试失败；全部日志保留。",
                        "Windows启动与resource缺失兼容分支仅编码，未在Windows实测。"]}
    if report is None:
        result.update(status="blocked", reason="未收到完整JSON；启动、语法、崩溃或超时不能算通过。")
        exit_code = 2
    elif code != 0 or timeout or changed:
        result.update(status="inconclusive", reason="运行器异常或运行中源码变化，需要重跑。")
        exit_code = 2
    else:
        counts = report["counts"]
        result["status"] = "fail" if counts["fail"] or counts["blocked"] else "pass"
        exit_code = 1 if result["status"] == "fail" else 0
    summary = OUTPUT / ("simulation" + args.suffix + ".json")
    summary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path = OUTPUT / ("test_report" + args.suffix + ".txt")
    lines = ["零刻：真实Lua全面自测", "结果：" + STATUS[result["status"]],
             "实际命令：" + subprocess.list2cmdline(cmd), "工作目录：" + str(sandbox),
             f"运行器退出码={code}；实际耗时={elapsed:.3f}秒；超时={timeout}", "完整日志：" + str(path),
             "JSON摘要：" + str(summary),
             "全运行器峰值RSS(KiB)：" + str(result["max_child_rss_kib"]) + "（含引擎及对抗单测；不等于长测Lua活内存）"]
    if report:
        lines.append("用例数：" + json.dumps(report["counts"]))
        for case in report["tests"]:
            lines.append(STATUS[case["status"]] + " " + case["id"])
            if case["status"] != "pass":
                lines.append(case.get("error", ""))
                evidence = dict(case.get("evidence", {}))
                if "result" in evidence:
                    evidence["result"] = {k: v for k, v in evidence["result"].items() if k != "trace"}
                    lines.append("逐步机器人轨迹保留于JSON与完整日志。")
                lines.append("复现数据：" + json.dumps(evidence, ensure_ascii=False))
        campaign = report.get("campaign") or {}
        lines.append("十关机器人：" + json.dumps({k: campaign.get(k) for k in
                     ("level", "mode", "total_steps", "actions", "high_water", "no_state_mutation")}, ensure_ascii=False))
        for level in campaign.get("levels", []):
            lines.append("关卡结果：" + json.dumps({k: level.get(k) for k in
                         ("level", "mode", "steps", "retries", "stats", "world_seconds", "real_seconds")}, ensure_ascii=False))
        lines.append("200k长测：" + json.dumps({k: (report.get("longrun") or {}).get(k) for k in
                     ("steps", "active_steps", "replay_steps", "completions", "failures", "high_water", "memory_max_gc_kib")}, ensure_ascii=False))
    else:
        lines.extend([result["reason"], text[-6000:]])
    if changed:
        lines.append("运行中改变的文件：" + ", ".join(changed))
    lines += ["未验证与边界说明："] + result["limitations"]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:8]))
    if report:
        for case in report["tests"]:
            if case["status"] != "pass":
                print(STATUS[case["status"]], case["id"], case.get("error", "").splitlines()[0])
    print("详细报告：", report_path)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
