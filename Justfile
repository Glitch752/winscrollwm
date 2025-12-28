# use bash
set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]

run:
    uv run main.py

compile:
    cmd /C "C:\Program Files\AutoHotkey\Compiler\Ahk2Exe.exe" /in ahk/scrollwm.ahk "/out" scrollwm.exe