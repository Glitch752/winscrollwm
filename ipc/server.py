import asyncio
from asyncio.subprocess import Process
import subprocess
import signal
import typing
from log import log_error

if typing.TYPE_CHECKING:
    from core.manager import WindowManager

async def start_ahk():
    process = await asyncio.create_subprocess_exec(
        "./ahk/scrollwm.exe",
        '1',
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE
    )
    
    def signal_handler(sig, frame):
        process.kill()
        process._transport.close() # type: ignore
        exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    return process

async def read_ahk_output(proc: Process, wm: 'WindowManager'):
    print("Started reading AHK output...")
    while True:
        if not proc.stdout:
            log_error("No stdout available.")
            break
        
        line = await proc.stdout.readline()
        if not line:
            log_error("AHK process terminated.")
            break
        cmd = line.strip()
        # convert from bytes to string; we know it's valid UTF-8
        cmd = cmd.decode('utf-8')
        
        print(f"> {cmd}")
        if cmd == "exit":
            wm.exit()
            break
        handle_command(wm, cmd)

def handle_command(wm, cmd):
    match cmd:
        case "focus_left":
            wm.move_focus_horizontal(-1)
        case "focus_right":
            wm.move_focus_horizontal(1)
        case "workspace_up":
            wm.move_workspace_vertical(-1)
        case "workspace_down":
            wm.move_workspace_vertical(1)
        case "resize_inc":
            wm.resize_window(0.1)
        case "resize_dec":
            wm.resize_window(-0.1)
        case "move_ws_left":
            wm.move_workspace_to_monitor(-1)
        case "move_ws_right":
            wm.move_workspace_to_monitor(1)
        case _:
            log_error(f"Unknown command: {cmd}")
