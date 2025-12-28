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
        elif cmd == "restart_wm":
            wm.exit(restart=True)
            break
        handle_command(wm, cmd)

def open_application(args: list[str]):
    # Open as a disconnected process
    try:
        subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True, creationflags=subprocess.DETACHED_PROCESS)
    except Exception as e:
        log_error(f"Failed to open application {' '.join(args)}: {e}")

def handle_command(wm: 'WindowManager', cmd: str):
    match cmd.split()[0]:
        case "focus_left": # Focus left window in current workspace
            wm.move_focus_horizontal(-1)
        case "focus_right": # Focus right window in current workspace
            wm.move_focus_horizontal(1)
        case "workspace_up": # Move to previous workspace
            wm.move_workspace_focus(-1)
        case "workspace_down": # Move to next workspace
            wm.move_workspace_focus(1)
        case "focus_first": # Focus first window in current workspace
            wm.focus_position(0)
        case "focus_last": # Focus last window in current workspace
            wm.focus_position(-1)
        
        case "move_left": # Move focused window left
            wm.move_window_horizontal(-1)
        case "move_right": # Move focused window right
            wm.move_window_horizontal(1)
        case "move_up": # Move focused window up
            wm.move_window_vertical(-1)
        case "move_down": # Move focused window down
            wm.move_window_vertical(1)
        case "move_first": # Move focused window to first position
            wm.move_window_to_position(0)
        case "move_last": # Move focused window to last position
            wm.move_window_to_position(-1)
        
        case "monitor_left":
            wm.move_monitor_focus(-1)
        case "monitor_right":
            wm.move_monitor_focus(1)
        case "move_monitor_left":
            wm.move_window_to_monitor(-1)
        case "move_monitor_right":
            wm.move_window_to_monitor(1)
        
        case "resize_inc": # Increase window size
            wm.resize_window(0.1)
        case "resize_dec": # Decrease window size
            wm.resize_window(-0.1)
        case "maximize_toggle":
            wm.toggle_maximize_focused_window()
        case "preset_width_toggle":
            wm.toggle_preset_width_focused_window()
        
        case "close_window":
            wm.close_focused_window()        
        case "open":
            args = cmd.split()[1:]
            if not args:
                log_error("No application specified to open.")
                return
            open_application(args)
        case _:
            log_error(f"Unknown command: {cmd}")