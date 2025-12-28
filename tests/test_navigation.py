from core.manager import WindowManager
from adapters.fake import FakeAdapter

def test_horizontal_navigation():
    wm = WindowManager(FakeAdapter())
    wm.move_focus_horizontal(1)
    win = wm.current_monitor().current_workspace().focused_window()
    assert win and win.id == 2

    wm.move_focus_horizontal(1)
    win = wm.current_monitor().current_workspace().focused_window()
    assert win and win.id == 3
