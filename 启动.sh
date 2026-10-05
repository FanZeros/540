#!/bin/sh
# 从当前项目内启动官方运行器；缓存、配置仍留在项目目录。
set -eu
cd "$(dirname "$0")"
ROOT="$(pwd)"
export HOME="$ROOT/tests/runtime"
export XDG_CACHE_HOME="$ROOT/tests/runtime/cache"
export XDG_CONFIG_HOME="$ROOT/tests/runtime/config"
export TMPDIR="$ROOT/tests/output"
mkdir -p tests/output
if [ ! -x tests/runtime/UrhoXRuntime ]; then
    python3 tests/setup_runtime.py
fi
exec tests/runtime/UrhoXRuntime main.lua "-tapcode_dir=$ROOT" -tool_mode -x 1352 -y 576 "$@"
