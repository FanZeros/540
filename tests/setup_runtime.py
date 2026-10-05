#!/usr/bin/env python3
"""把官方运行器安装在项目 tests/runtime；不安装全局软件，不下载美术。"""
import os
import sys
import stat
import zipfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "tests" / "runtime"
PLATFORM = {"win32": "windows", "darwin": "macos", "linux": "linux"}

def main():
    plat = PLATFORM.get(sys.platform)
    if not plat:
        raise SystemExit("不支持此平台；请在 TapTap Spark Editor 中运行 scripts/main.lua")
    DEST.mkdir(parents=True, exist_ok=True)
    exe = DEST / ("UrhoXRuntime.exe" if sys.platform == "win32" else "UrhoXRuntime")
    if exe.exists():
        print("运行器已存在：", exe.relative_to(ROOT))
        return
    proxy = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({"https": proxy} if proxy else {}))
    url = f"https://urhox-demo-platform.spark.xd.com/runtime/{plat}/latest/UrhoXRuntime.zip"
    bundle = DEST / "UrhoXRuntime.zip"
    print("下载官方运行器；素材全部来自本项目的生成代码。")
    with opener.open(url, timeout=90) as src, bundle.open("wb") as out:
        while True:
            block = src.read(1024 * 1024)
            if not block:
                break
            out.write(block)
    with zipfile.ZipFile(bundle) as z:
        for item in z.infolist():
            target = (DEST / item.filename).resolve()
            if not target.is_relative_to(DEST.resolve()):
                raise RuntimeError("压缩包包含越界路径")
        z.extractall(DEST)
    if not exe.exists():
        raise RuntimeError("压缩包缺少运行器")
    if sys.platform != "win32":
        exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    print("运行器准备完成：", exe.relative_to(ROOT))

if __name__ == "__main__":
    main()
