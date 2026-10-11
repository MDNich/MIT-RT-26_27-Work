Add-Type @'
using System;using System.Text;using System.Runtime.InteropServices;
public class PBC{public delegate bool CB(IntPtr h,IntPtr p);[DllImport("user32.dll")]public static extern bool EnumWindows(CB c,IntPtr p);[DllImport("user32.dll")]public static extern bool EnumChildWindows(IntPtr h,CB c,IntPtr p);[DllImport("user32.dll")]public static extern int GetClassName(IntPtr h,StringBuilder s,int n);[DllImport("user32.dll")]public static extern int GetWindowText(IntPtr h,StringBuilder s,int n);[DllImport("user32.dll")]public static extern uint GetWindowThreadProcessId(IntPtr h,out uint p);[DllImport("user32.dll")]public static extern bool PostMessage(IntPtr h,uint msg,IntPtr w,IntPtr l);[DllImport("user32.dll")]public static extern bool GetWindowRect(IntPtr h,out RECT r);public struct RECT{public int l,t,r,b;}[DllImport("user32.dll")]public static extern bool SetProcessDPIAware();}
'@
[void][PBC]::SetProcessDPIAware()
$rows=New-Object System.Collections.Generic.List[string]
[void][PBC]::EnumWindows({param($h,$v) [uint32]$p=0;[void][PBC]::GetWindowThreadProcessId($h,[ref]$p);if($p -eq 15208){$s=New-Object Text.StringBuilder 512;$c=New-Object Text.StringBuilder 256;[void][PBC]::GetWindowText($h,$s,512);[void][PBC]::GetClassName($h,$c,256);$r=New-Object PBC+RECT;[void][PBC]::GetWindowRect($h,[ref]$r);$rows.Add("$h | $s | $c | $($r.l),$($r.t),$($r.r),$($r.b)")};return $true},[IntPtr]::Zero)
$rows
