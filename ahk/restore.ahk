#Requires AutoHotkey v2.0

; Restores miscellaneous changes the WM makes.

; Enumerate windows
windowList := WinGetList("")
for window in windowList {
    ; Restore transparency
    try {
        WinSetTransparent("", window)
    } catch {
        ; Ignore errors
    }
}