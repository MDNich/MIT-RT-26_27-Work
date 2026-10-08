Add-Type -AssemblyName System.Windows.Forms
Add-Type @'
using System;using System.Text;using System.Runtime.InteropServices;public class PBK{public delegate bool CB(IntPtr h,IntPtr p);[DllImport("user32.dll")]public static extern bool EnumWindows(CB c,IntPtr p);[DllImport("user32.dll")]public static extern IntPtr GetForegroundWindow();[DllImport("user32.dll")]public static extern uint GetWindowThreadProcessId(IntPtr h,out uint p);[DllImport("user32.dll")]public static extern int GetWindowText(IntPtr h,StringBuilder s,int n);[DllImport("user32.dll")]public static extern bool SetForegroundWindow(IntPtr h);[DllImport("user32.dll")]public static extern bool ShowWindow(IntPtr h,int n);[DllImport("user32.dll")]public static extern bool AttachThreadInput(uint a,uint b,bool x);[DllImport("kernel32.dll")]public static extern uint GetCurrentThreadId();}
'@
$ls=New-Object System.Collections.Generic.List[System.IntPtr]
[void][PBK]::EnumWindows({param($h,$v) [uint32]$pidw=0;[void][PBK]::GetWindowThreadProcessId($h,[ref]$pidw);if($pidw -eq 5808){$s=New-Object Text.StringBuilder 512;[void][PBK]::GetWindowText($h,$s,512);if($s.ToString() -eq 'Megnyitás'){$ls.Add($h)}};return $true},[IntPtr]::Zero)
if($ls.Count -ne 1){throw 'Window ambiguous'}
$h=$ls[0];[uint32]$p=0;$ft=[PBK]::GetWindowThreadProcessId([PBK]::GetForegroundWindow(),[ref]$p);$ct=[PBK]::GetCurrentThreadId();[uint32]$p2=0;$tt=[PBK]::GetWindowThreadProcessId($h,[ref]$p2)
[void][PBK]::AttachThreadInput($ct,$ft,$true);[void][PBK]::AttachThreadInput($ct,$tt,$true)
try{[void][PBK]::ShowWindow($h,9);[void][PBK]::SetForegroundWindow($h)}finally{[void][PBK]::AttachThreadInput($ct,$tt,$false);[void][PBK]::AttachThreadInput($ct,$ft,$false)}
[void][PBK]::GetWindowThreadProcessId([PBK]::GetForegroundWindow(),[ref]$p);if($p -ne 5808){throw "Focus mismatch $p"}
[System.Windows.Forms.SendKeys]::SendWait('C:\Temp\pbmotion_reopen.wbjn{ENTER}')
