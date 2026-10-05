@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "HOME=%CD%\tests\runtime"
set "XDG_CACHE_HOME=%CD%\tests\runtime\cache"
set "XDG_CONFIG_HOME=%CD%\tests\runtime\config"
set "TEMP=%CD%\tests\output"
set "TMP=%CD%\tests\output"
if not exist "tests\output" mkdir "tests\output"
if not exist "tests\runtime\UrhoXRuntime.exe" (
    python tests\setup_runtime.py
    if errorlevel 1 (
        echo 首次运行需要 Python 3 和网络，也可在 TapTap Spark Editor 中打开本项目。
        pause
        exit /b 1
    )
)
"tests\runtime\UrhoXRuntime.exe" main.lua -tapcode_dir="%CD%" -tool_mode -x 1352 -y 576
