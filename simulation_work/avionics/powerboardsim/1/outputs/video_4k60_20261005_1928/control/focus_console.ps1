Add-Type @'
using System;using System.Runtime.InteropServices;
public class VI {
[DllImport("user32.dll")]public static extern bool SetProcessDPIAware();
[DllImport("user32.dll")]public static extern IntPtr SetThreadDpiAwarenessContext(IntPtr c);
[DllImport("user32.dll")]public static extern bool SetForegroundWindow(IntPtr h);
[DllImport("user32.dll")]public static extern bool ShowWindow(IntPtr h,int n);
[DllImport("user32.dll")]public static extern bool SetCursorPos(int x,int y);
[DllImport("user32.dll")]public static extern void mouse_event(uint f,uint x,uint y,uint d,UIntPtr e);
[DllImport("user32.dll")]public static extern int GetSystemMetrics(int n);
[DllImport("user32.dll")]public static extern IntPtr GetForegroundWindow();
[DllImport("user32.dll")]public static extern uint GetWindowThreadProcessId(IntPtr h,out uint p);
}
'@
[VI]::SetProcessDPIAware()|Out-Null
[VI]::SetThreadDpiAwarenessContext([IntPtr](-4))|Out-Null
[VI]::ShowWindow([IntPtr]658162,9)|Out-Null
[VI]::SetForegroundWindow([IntPtr]658162)|Out-Null
Start-Sleep -Milliseconds 250
[VI]::SetCursorPos(2940,1570)|Out-Null
[VI]::mouse_event(2,0,0,0,[UIntPtr]::Zero)
[VI]::mouse_event(4,0,0,0,[UIntPtr]::Zero)
[uint32]$focused=0;[VI]::GetWindowThreadProcessId([VI]::GetForegroundWindow(),[ref]$focused)|Out-Null
[IO.File]::WriteAllText('Z:\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\video_4k60_20261005_1928\control\focus_check.txt',([VI]::GetSystemMetrics(0)).ToString()+','+([VI]::GetSystemMetrics(1)).ToString()+' PID='+$focused)
