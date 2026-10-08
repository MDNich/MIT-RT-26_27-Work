Add-Type @'
using System;using System.Text;using System.Runtime.InteropServices;
public class VF {
[DllImport("user32.dll")]public static extern bool SetCursorPos(int x,int y);
[DllImport("user32.dll")]public static extern void mouse_event(uint f,uint x,uint y,uint d,UIntPtr e);
public struct PT {public int x,y;}
[DllImport("user32.dll")]public static extern bool ScreenToClient(IntPtr h,ref PT p);
[DllImport("user32.dll")]public static extern IntPtr SetFocus(IntPtr h);
[DllImport("user32.dll")]public static extern bool PostMessage(IntPtr h,uint msg,IntPtr w,IntPtr l);

[DllImport("user32.dll")]public static extern bool SetProcessDPIAware();
[DllImport("user32.dll")]public static extern bool SetForegroundWindow(IntPtr h);
[DllImport("user32.dll")]public static extern bool ShowWindow(IntPtr h,int n);
[DllImport("user32.dll")]public static extern bool BringWindowToTop(IntPtr h);
[DllImport("user32.dll")]public static extern IntPtr GetForegroundWindow();
[DllImport("user32.dll")]public static extern uint GetWindowThreadProcessId(IntPtr h,out uint p);
[DllImport("kernel32.dll")]public static extern uint GetCurrentThreadId();
[DllImport("user32.dll")]public static extern bool AttachThreadInput(uint a,uint b,bool x);
[DllImport("user32.dll")]public static extern int GetWindowText(IntPtr h,StringBuilder s,int n);
[DllImport("user32.dll")]public static extern int GetClassName(IntPtr h,StringBuilder s,int n);
[DllImport("user32.dll")]public static extern bool GetWindowRect(IntPtr h,out R r);
public struct R{public int l,t,r,b;}
public delegate bool EnumProc(IntPtr h,IntPtr p);
[DllImport("user32.dll")]public static extern bool EnumChildWindows(IntPtr h,EnumProc f,IntPtr p);
}
'@
[void][VF]::SetProcessDPIAware()
$h=[IntPtr]658162;[uint32]$fgpid=0;$fg=[VF]::GetForegroundWindow();$ft=[VF]::GetWindowThreadProcessId($fg,[ref]$fgpid);$ct=[VF]::GetCurrentThreadId();[uint32]$mp=0;$mt=[VF]::GetWindowThreadProcessId($h,[ref]$mp)
$out=New-Object System.Collections.Generic.List[string]
$out.Add("before FG=$fg pid=$fgpid mt=$mt ct=$ct ft=$ft")
[void][VF]::AttachThreadInput($ct,$ft,$true);[void][VF]::AttachThreadInput($ct,$mt,$true)
try{$out.Add('show='+[VF]::ShowWindow($h,3));$out.Add('bring='+[VF]::BringWindowToTop($h));$out.Add('foreground='+[VF]::SetForegroundWindow($h))}finally{[void][VF]::AttachThreadInput($ct,$mt,$false);[void][VF]::AttachThreadInput($ct,$ft,$false)}
Start-Sleep -Milliseconds 500
$fg=[VF]::GetForegroundWindow();[void][VF]::GetWindowThreadProcessId($fg,[ref]$fgpid);$out.Add("after FG=$fg pid=$fgpid")

if($fgpid -ne 15108){throw ('Foreground='+$fgpid)}
[void][VF]::SetCursorPos(2940,1570)
[VF]::mouse_event(2,0,0,0,[UIntPtr]::Zero)
[VF]::mouse_event(4,0,0,0,[UIntPtr]::Zero)
Start-Sleep -Milliseconds 300
[void][VF]::GetWindowThreadProcessId([VF]::GetForegroundWindow(),[ref]$fgpid)
if($fgpid -notin @(15108,13148)){throw ('Focus after direct click='+$fgpid)}
Add-Type -AssemblyName System.Windows.Forms
$command="execfile(r'Z:\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\bolt_manager_work\resume_20261005_004228\bridge.py')"
[System.Windows.Forms.Clipboard]::SetText($command)
Start-Sleep -Milliseconds 500
[System.Windows.Forms.SendKeys]::SendWait('^{END}')
$escaped=$command.Replace('(', '{(}').Replace(')', '{)}')
[System.Windows.Forms.SendKeys]::SendWait($escaped)
