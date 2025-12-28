from core.models import Monitor
import win32gui

def print_ascii_layout(monitors: list[Monitor], focused_monitor: int | None):
    outer_buf = []
    def add_rect(text: str, title: str | None, buf: list[str], style: str, ansi_col: str | None = None):
        chars = {
            'ascii': [
                '/-\\',
                '| |',
                '\\-/'
            ],
            'single': [
                '┌─┐',
                '│ │',
                '└─┘'
            ],
            'double': [
                '╔═╗',
                '║ ║',
                '╚═╝'
            ],
        }[style]
        
        title = f" {title} " if title else None
        
        def len_without_ansi(s: str) -> int:
            import re
            ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
            return len(ansi_escape.sub('', s))
        def ansi_ljust(s: str, width: int) -> str:
            import re
            ansi_escape = re.compile(r'(\x1B\[[0-?]*[ -/]*[@-~])')
            parts = ansi_escape.split(s)
            visible_length = sum(len(part) for i, part in enumerate(parts) if i % 2 == 0)
            padding = width - visible_length
            if padding > 0:
                return s + ' ' * padding
            return s
        
        lines = text.splitlines()
        max_line_length = max(len_without_ansi(line) for line in lines) if lines else 0
        
        height = len(lines) + 2
        length = max(max_line_length + 4, len(title) + 4 if title else 0)
        
        if not buf:
            buf.append("")
        while len(buf) < height:
            buf.append(" " * len(buf[0]))
        
        if len(buf[0]) > 0:
            for i in range(len(buf)):
                buf[i] += " "
        
        ansi_set = ansi_col or ""
        ansi_reset = "\033[0m" if ansi_col else ""
        
        # Header
        if title:
            buf[0] += f"{ansi_set}{chars[0][0]}{chars[0][1]}{title.center(length - 4, chars[0][1])}{chars[0][1]}{chars[0][2]}{ansi_reset}"
        else:
            buf[0] += f"{ansi_set}{chars[0][0]}{chars[0][1] * (length - 2)}{chars[0][2]}{ansi_reset}"
        
        # Content
        for i in range(1, height - 1):
            buf[i] += f"{ansi_set}{chars[1][0]}{ansi_reset} {ansi_ljust(lines[i - 1], length - 4)} {ansi_set}{chars[1][2]}{ansi_reset}"
        
        # Footer
        buf[height - 1] += f"{ansi_set}{chars[2][0]}{chars[2][1] * (length - 2)}{chars[2][2]}{ansi_reset}"
        
        # Pad buf to height
        if len(buf) > height:
            for i in range(height, len(buf)):
                buf[i] += " " * length
    
    for mi, mon in enumerate(monitors):
        monitor_buf = []
        
        for wsi, ws in enumerate(mon.workspaces):
            ws_buf = []
            for wi, win in enumerate(ws.windows):
                name = ""
                win_class = ""
                try:
                    name = win32gui.GetWindowText(win.id)
                    win_class = win32gui.GetClassName(win.id) or ""
                except Exception:
                    pass
                if len(name) > 50:
                    name = name[:47] + "..."
                if len(win_class) > 50:
                    win_class = win_class[:47] + "..."
                add_rect(f"{name}\n{win_class}", f"Win {win.id}", ws_buf, 'double' if win == ws.focused_window() else 'single', '\033[92m' if win.id == ws._focused_id else None)
            
            temp_buf = []
            add_rect("\n".join(ws_buf), f"Workspace {ws.id}", temp_buf, 'single', '\033[94m' if ws.id == mon._focused_workspace else None)
            monitor_buf.extend(temp_buf) # Add vertically
        
        add_rect("\n".join(monitor_buf), f"Monitor {mi} (ws {mon.current_workspace().id})", outer_buf, 'double', '\033[96m' if mi == focused_monitor else None)
    
    # Clear screen
    # print("\033[2J\033[H")
    print("\n" * 2)
    print("\n".join(outer_buf))
