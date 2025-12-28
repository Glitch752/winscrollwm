# adapters/windows/watcher.py
import threading
from typing import Callable
import win32gui
import win32api
import ctypes
import ctypes.wintypes
import logging

import typing

from adapters.windows.enumerate import is_manageable
if typing.TYPE_CHECKING:
    from adapters.windows.adapter import WindowsAdapter


user32 = ctypes.windll.user32
ole32 = ctypes.windll.ole32

WinEventHookCallable = Callable[[
    ctypes.wintypes.HANDLE,
    ctypes.wintypes.DWORD,
    ctypes.wintypes.HWND,
    ctypes.wintypes.LONG,
    ctypes.wintypes.LONG,
    ctypes.wintypes.DWORD,
    ctypes.wintypes.DWORD
], None]

WinEventProcType = ctypes.WINFUNCTYPE(
    None, 
    ctypes.wintypes.HANDLE,
    ctypes.wintypes.DWORD,
    ctypes.wintypes.HWND,
    ctypes.wintypes.LONG,
    ctypes.wintypes.LONG,
    ctypes.wintypes.DWORD,
    ctypes.wintypes.DWORD
)
def SetWinEventHook(
    eventMin: int,
    eventMax: int,
    hmodWinEventProc: int,
    pfnWinEventProc: WinEventHookCallable,
    idProcess: int,
    idThread: int,
    dwFlags: int
) -> ctypes.wintypes.HANDLE:
    proc = WinEventProcType(pfnWinEventProc)
    
    # Leak the proc to keep it alive
    # this could be better but I really don't care
    import atexit
    atexit.register(lambda: ctypes.cast(proc, ctypes.c_void_p))
    
    return user32.SetWinEventHook(
        eventMin,
        eventMax,
        hmodWinEventProc,
        proc,
        idProcess,
        idThread,
        dwFlags
    )

def UnhookWinEvent(hWinEventHook: ctypes.wintypes.HANDLE):
    return user32.UnhookWinEvent(hWinEventHook)

# Event constants (some are not in win32con)
EVENT_OBJECT_CREATE = 0x8000
EVENT_OBJECT_DESTROY = 0x8001
EVENT_OBJECT_SHOW = 0x8002
EVENT_OBJECT_HIDE = 0x8003
EVENT_OBJECT_LOCATIONCHANGE = 0x800B

WINEVENT_OUTOFCONTEXT = 0x0000

log = logging.getLogger(__name__)

class WinEventWatcher(threading.Thread):
    """
    runs a message loop and installs SetWinEventHook to observe window creation/show/destroy/hide.
    calls callbacks on adapter when relevant top-level windows appear/disappear.
    """
    
    adapter: "WindowsAdapter"
    hooks: list[ctypes.wintypes.HANDLE]
    _running: threading.Event
    
    def __init__(self, adapter: "WindowsAdapter"):
        super().__init__(daemon=True)
        self.adapter = adapter
        self.hooks = []
        self._running = threading.Event()

    def run(self):
        self._running.set()
        
        ole32.CoInitializeEx(1)

        def callback(hWinEventHook, event, hwnd, idObject, idChild, dwEventThread, dwmsEventTime):
            if not self._running.is_set():
                return
            if idObject != 0 or idChild != 0:
                return
            if event in (EVENT_OBJECT_CREATE, EVENT_OBJECT_SHOW):
                if is_manageable(hwnd):
                    log.debug(f"WinEventWatcher: Detected manageable window created/shown: {hwnd}")
                    self.adapter.on_window_created(hwnd)
            elif event in (EVENT_OBJECT_DESTROY, EVENT_OBJECT_HIDE):
                log.debug(f"WinEventWatcher: Detected window destroyed/hidden: {hwnd}")
                self.adapter.on_window_destroyed(hwnd)

        # Set hooks for relevant events
        self.hooks.append(SetWinEventHook(EVENT_OBJECT_CREATE, EVENT_OBJECT_CREATE, 0, callback, 0, 0, WINEVENT_OUTOFCONTEXT))
        self.hooks.append(SetWinEventHook(EVENT_OBJECT_DESTROY, EVENT_OBJECT_DESTROY, 0, callback, 0, 0, WINEVENT_OUTOFCONTEXT))
        self.hooks.append(SetWinEventHook(EVENT_OBJECT_SHOW, EVENT_OBJECT_SHOW, 0, callback, 0, 0, WINEVENT_OUTOFCONTEXT))
        self.hooks.append(SetWinEventHook(EVENT_OBJECT_HIDE, EVENT_OBJECT_HIDE, 0, callback, 0, 0, WINEVENT_OUTOFCONTEXT))

        # Message loop
        msg = ctypes.wintypes.MSG()
        while self._running.is_set():
            ret = user32.GetMessageW(ctypes.byref(msg), 0, 0, 0)
            if ret == -1:
                raise RuntimeError("GetMessageW failed in WinEventWatcher")
            elif ret == 0:
                break
            else:
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        
        # Unhook events
        for hook in self.hooks:
            UnhookWinEvent(hook)
        self.hooks.clear()

    def stop(self):
        # Post a quit message to the thread's message loop
        try:
            win32gui.PostQuitMessage(0)
        except Exception:
            pass
        self._running.clear()
