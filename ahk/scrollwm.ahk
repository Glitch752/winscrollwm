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


; Focus with just mod
#Left::send("focus_left")
#Right::send("focus_right")
#Up::send("workspace_up")
#Down::send("workspace_down")

#Home::send("focus_first")
#End::send("focus_last")

; Also focus vertical with mod+scroll and horizontal with mod+shift+scroll
#WheelUp::send("workspace_up")
#WheelDown::send("workspace_down")
#+WheelUp::send("focus_left")
#+WheelDown::send("focus_right")

; Move windows with mod+ctrl
#+Left::send("move_left")
#+Right::send("move_right")
#+Up::send("move_up")
#+Down::send("move_down")

#+Home::send("move_first")
#+End::send("move_last")

; Focus monitors with mod+shift
#^Left::send("monitor_left")
#^Right::send("monitor_right")

; Move windows between monitors with mod+shift+ctrl
#^+Left::send("move_monitor_left")
#^+Right::send("move_monitor_right")

; Resizing
#-::send("resize_dec")
#=::send("resize_inc")
#F::send("maximize_toggle")
#X::send("preset_width_toggle")

; Miscellaneous
#C::send("close_window")
#Q::send("open wt")
#E::send("open explorer")

#^R::send("restart_wm")
#Esc::send("exit")
