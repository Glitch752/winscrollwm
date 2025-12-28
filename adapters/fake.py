from core.models import Monitor, Workspace, Window
from adapters.base import Adapter

class FakeAdapter(Adapter):
    def __init__(self):
        self._monitors = [
            Monitor(
                workspaces=[
                    Workspace(
                        windows=[
                            Window(1),
                            Window(2),
                            Window(3),
                        ]
                    ),
                    Workspace(
                        windows=[
                            Window(21),
                            Window(22),
                        ]
                    )
                ]
            ),
            Monitor()
        ]

    def get_monitors(self):
        return self._monitors

    def focus_window(self, window):
        print(f"[FAKE] Focus {window.id}")

    def resize_window(self, window):
        print(f"[FAKE] Resize {window.id} -> {window.width}")

    def refresh(self):
        print("[FAKE] Refresh layout")
