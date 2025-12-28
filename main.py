import asyncio
from adapters.windows.adapter import WindowsAdapter
from core.manager import WindowManager
from ipc.server import read_ahk_output, start_ahk

async def main():
    wm = WindowManager(WindowsAdapter())
    
    ahk = await start_ahk()
    if not ahk:
        print("Failed to start AHK process.")
        return

    ahk_task = asyncio.create_task(read_ahk_output(ahk, wm))
    await ahk_task
    
    ahk.terminate()

if __name__ == "__main__":
    asyncio.run(main())
