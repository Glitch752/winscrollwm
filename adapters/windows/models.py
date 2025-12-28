from dataclasses import dataclass
from adapters.windows.thumbnail.thumbnail_window import ThumbnailWindow
from core.models import Rect

@dataclass
class WinMonitor:
    hMonitor: int
    # (monitor_left, monitor_top, monitor_right, monitor_bottom)
    monitor: Rect
    # (work_left, work_top, work_right, work_bottom)
    work: Rect
    device: str

@dataclass
class WinWindow:
    id: int
    title: str
    rect: Rect
    
    thumbnail: ThumbnailWindow | None = None