;@Ahk2Exe-ConsoleApp

#Requires AutoHotkey v2.0
#SingleInstance Force

; Disable the hotkey limit
A_HotkeyInterval := 1
A_MaxHotkeysPerInterval := 200


SendMode('Input')
SetWorkingDir(A_ScriptDir)

send(cmd) {
    FileAppend(cmd . "`n", "*")
}


#Left::send("focus_left")
#Right::send("focus_right")
#Up::send("workspace_up")
#Down::send("workspace_down")

#+Left::send("move_ws_left")
#+Right::send("move_ws_right")

#-::send("resize_dec")
#=::send("resize_inc")

#Esc::send("exit")
