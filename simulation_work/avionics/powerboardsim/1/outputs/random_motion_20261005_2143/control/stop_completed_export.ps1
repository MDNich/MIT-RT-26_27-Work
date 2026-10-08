Add-Type @'
using System;using System.Text;using System.Runtime.InteropServices;
public class PBC{public delegate bool CB(IntPtr h,IntPtr p);[DllImport("user32.dll")]public static extern bool EnumWindows(CB c,IntPtr p);[DllImport("user32.dll")]public static extern bool EnumChildWindows(IntPtr h,CB c,IntPtr p);[DllImport("user32.dll")]public static extern int GetClassName(IntPtr h,StringBuilder s,int n);[DllImport("user32.dll")]public static extern int GetWindowText(IntPtr h,StringBuilder s,int n);[DllImport("user32.dll")]public static extern uint GetWindowThreadProcessId(IntPtr h,out uint p);[DllImport("user32.dll")]public static extern bool PostMessage(IntPtr h,uint msg,IntPtr w,IntPtr l);[DllImport("user32.dll")]public static extern bool GetWindowRect(IntPtr h,out RECT r);public struct RECT{public int l,t,r,b;}[DllImport("user32.dll")]public static extern bool SetProcessDPIAware();}
'@
[void][PBC]::SetProcessDPIAware()
$ls=New-Object System.Collections.Generic.List[System.IntPtr]
[void][PBC]::EnumWindows({param($h,$v) [uint32]$p=0;[void][PBC]::GetWindowThreadProcessId($h,[ref]$p);if($p -eq 15208){$s=New-Object Text.StringBuilder 512;[void][PBC]::GetWindowText($h,$s,512);if($s.ToString().Contains('Systems')){$ls.Add($h)}};return $true},[IntPtr]::Zero)
if($ls.Count -ne 1){throw 'Window ambiguous'}
$bars=New-Object System.Collections.Generic.List[System.IntPtr]
[void][PBC]::EnumChildWindows($ls[0],{param($h,$v) $s=New-Object Text.StringBuilder 256;[void][PBC]::GetClassName($h,$s,256);if($s.ToString() -eq 'XTPStatusBar'){$bars.Add($h)};return $true},[IntPtr]::Zero)
foreach($b in $bars){$r=New-Object PBC+RECT;[void][PBC]::GetWindowRect($b,[ref]$r);Write-Output "$b $($r.l),$($r.t),$($r.r),$($r.b)";if($r.t -gt 1900 -and $r.b -lt 2010){$x=238-$r.l;$y=1976-$r.t;[void][PBC]::PostMessage($b,0x201,[IntPtr]1,[IntPtr](($y -shl 16)-bor $x));[void][PBC]::PostMessage($b,0x202,[IntPtr]0,[IntPtr](($y -shl 16)-bor $x));'Stop click posted to completed export'}}
