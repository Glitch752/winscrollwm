# adapters/windows/monitor_info.py
import win32api
from .models import Rect, WinMonitor

def list_monitors() -> list[WinMonitor]:
    monitors = []
    for hMonitor, hdc, rect in win32api.EnumDisplayMonitors(None, None):
        info = win32api.GetMonitorInfo(hMonitor.handle)
        monitors.append(WinMonitor(
            hMonitor=hMonitor.handle,
            monitor=Rect(*info['Monitor']),
            work=Rect(*info['Work']),
            device=info['Device']
        ))
    
    # Sort by left coordinate, then top
    monitors.sort(key=lambda m: (m.monitor.left(), m.monitor.top()))
    
    return monitors
