Add-Type @'
using System;using System.Text;using System.Runtime.InteropServices;
public class PBC{[DllImport("user32.dll")]public static extern bool IsWindowVisible(IntPtr h);[DllImport("user32.dll")]public static extern bool IsWindowEnabled(IntPtr h);public delegate bool CB(IntPtr h,IntPtr p);[DllImport("user32.dll")]public static extern bool EnumWindows(CB c,IntPtr p);[DllImport("user32.dll")]public static extern bool EnumChildWindows(IntPtr h,CB c,IntPtr p);[DllImport("user32.dll")]public static extern int GetClassName(IntPtr h,StringBuilder s,int n);[DllImport("user32.dll")]public static extern int GetWindowText(IntPtr h,StringBuilder s,int n);[DllImport("user32.dll")]public static extern uint GetWindowThreadProcessId(IntPtr h,out uint p);[DllImport("user32.dll")]public static extern bool PostMessage(IntPtr h,uint msg,IntPtr w,IntPtr l);[DllImport("user32.dll")]public static extern bool GetWindowRect(IntPtr h,out RECT r);public struct RECT{public int l,t,r,b;}[DllImport("user32.dll")]public static extern bool SetProcessDPIAware();}
'@
[void][PBC]::SetProcessDPIAware()
$rows=New-Object System.Collections.Generic.List[string]
[void][PBC]::EnumChildWindows([IntPtr]658374,{param($h,$v) $s=New-Object Text.StringBuilder 512;$c=New-Object Text.StringBuilder 256;[void][PBC]::GetWindowText($h,$s,512);[void][PBC]::GetClassName($h,$c,256);$rows.Add("$h | $s | $c | visible=$([PBC]::IsWindowVisible($h)) enabled=$([PBC]::IsWindowEnabled($h))");return $true},[IntPtr]::Zero)
"Dialog visible=$([PBC]::IsWindowVisible([IntPtr]658374)) enabled=$([PBC]::IsWindowEnabled([IntPtr]658374))"
$rows
Get-ChildItem 'C:\Temp\PBMotionControl' | Select Name,Length,LastWriteTime | ConvertTo-Json -Compress
Get-Process -Id 15208 -ErrorAction SilentlyContinue | Select Id,CPU,Responding | ConvertTo-Json -Compress
