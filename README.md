# winscrollwm

Have you ever looked at Linux scrolling window managers and thought, "I wish I had that on windows..."  

No? I did for some reason, I guess.  

It's (inspired by) [niri](https://github.com/YaLTeR/niri) but for Microsoft Windows! This is just a proof-of-concept I threw together in a day, so nothing seriously meant for daily use. That said, I plan to keep using it myself for when I need to use Windows.  

As with anything Windows, system-wide keybinds are a mess, so we use an AutoHotKey script and communicate over its stdout. A little cursed, but this whole project is.

I've always been dissatisfied with Windows WMs' multi-monitor support: DWM is highly restrictive of how external programs can change compositing, so most of the time monitor workspaces can interact in weird ways. I'm not able to entirely solve this, of course, but this program uses a novel (to my knowledge) solution to isolating windows to their workspace. We create a fake "proxy" window behind each composited window with a DWM thumbnail attached (which, in my testing, adds minimal or zero latency). Then, we set every top-level window with a thumbnail view to zero opacity so they still take interactions and child windows appear as expected. This works for every application I've been able to test it with, and while it's probably not the best for performance, it's worth having per-monitor workspaces to me.

## TODO
- [ ] Use BeginDeferWindowPos for both regular layout and cloaking use to batch window updates
- [ ] Disable cloaking for windows that don't strictly pass monitor boundaries
- [ ] Better workspace management
- [ ] Somehow implement an overview-like feature?
- [ ] Animations?