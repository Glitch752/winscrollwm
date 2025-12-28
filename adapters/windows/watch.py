# adapters/windows/watcher.py
import threading
from typing import Callable
import win32gui
import win32api
import win32con
import ctypes
import ctypes.wintypes
import logging
import queue

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
EVENT_OBJECT_NAMECHANGE = 0x800C
EVENT_OBJECT_REORDER = 0x8004
EVENT_OBJECT_FOCUS = 0x8005

EVENT_SYSTEM_FOREGROUND = 0x0003
EVENT_SYSTEM_MINIMIZESTART = 0x0016
EVENT_SYSTEM_MINIMIZEEND = 0x0017

WINEVENT_OUTOFCONTEXT = 0x0000
WINEVENT_SKIPOWNPROCESS = 0x0002

log = logging.getLogger(__name__)

class WinEventWatcher(threading.Thread):
    """
    runs a message loop and installs SetWinEventHook to observe window creation/show/destroy/hide.
    calls callbacks on adapter when relevant top-level windows appear/disappear.
    """
    
    adapter: "WindowsAdapter"
    hooks: list[ctypes.wintypes.HANDLE]
    _running: threading.Event
    
    # Used for running functions on this thread
    # Windows is sometimes picky about event loops in the right places,
    # so this is the easiest solution since we already have an event loop here
    _call_queue: queue.Queue[Callable]
    _thread_id: int | None
    
    def __init__(self, adapter: "WindowsAdapter"):
        super().__init__(daemon=True)
        self.adapter = adapter
        self.hooks = []
        self._running = threading.Event()
        self.name = "WinEventWatcher"
        self._call_queue = queue.Queue()
        self._thread_id = None

    def run(self):
        self._thread_id = win32api.GetCurrentThreadId()
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
            elif event == EVENT_OBJECT_LOCATIONCHANGE:
                self.adapter.on_window_moved(hwnd)
            elif event == EVENT_SYSTEM_FOREGROUND:
                self.adapter.on_foreground_changed(hwnd)
            elif event == EVENT_OBJECT_NAMECHANGE:
                self.adapter.on_window_title_changed(hwnd)
            elif event == EVENT_SYSTEM_MINIMIZESTART:
                self.adapter.on_window_minimized(hwnd)
            elif event == EVENT_SYSTEM_MINIMIZEEND:
                self.adapter.on_window_restored(hwnd)

        # Set hooks for relevant events
        def listen(event: int):
            self.hooks.append(SetWinEventHook(event, event, 0, callback, 0, 0, WINEVENT_OUTOFCONTEXT | WINEVENT_SKIPOWNPROCESS))
        
        listen(EVENT_OBJECT_CREATE)
        listen(EVENT_OBJECT_DESTROY)
        listen(EVENT_OBJECT_SHOW)
        listen(EVENT_OBJECT_HIDE)
        listen(EVENT_OBJECT_LOCATIONCHANGE)
        listen(EVENT_OBJECT_NAMECHANGE)
        # listen(EVENT_OBJECT_REORDER)
        # listen(EVENT_OBJECT_FOCUS)
        listen(EVENT_SYSTEM_FOREGROUND)
        listen(EVENT_SYSTEM_MINIMIZESTART)
        listen(EVENT_SYSTEM_MINIMIZEEND)

        # Message loop
        msg = ctypes.wintypes.MSG()
        while self._running.is_set():
            ret = user32.GetMessageW(ctypes.byref(msg), 0, 0, 0)
            if ret == -1:
                raise RuntimeError("GetMessageW failed in WinEventWatcher")
            elif ret == 0:
                break
            else:
                if msg.message == win32con.WM_USER + 1:
                    while self._call_queue.qsize() > 0:
                        try:
                            func = self._call_queue.get_nowait()
                            func()
                        except queue.Empty:
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

    def run_on_thread(self, func: Callable):
        """
        Schedules a function to run on the watcher's thread.
        """
        self._call_queue.put(func)
        
        if not self._running.is_set() or self._thread_id is None:
            return
        
        win32gui.PostThreadMessage(self._thread_id, win32con.WM_USER + 1, 0, 0)