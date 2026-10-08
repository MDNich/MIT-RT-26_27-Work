$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class VideoBridgeInput {
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hwnd);
[DllImport("user32.dll")] public static extern bool SetCursorPos(int x,int y);
[DllImport("user32.dll")] public static extern void mouse_event(uint flags,uint dx,uint dy,uint data,UIntPtr extra);
}
'@
$cond=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty,15108)
$win=[System.Windows.Automation.AutomationElement]::RootElement.FindFirst([System.Windows.Automation.TreeScope]::Children,$cond)
if($null -eq $win){throw 'Mechanical window missing'}
[VideoBridgeInput]::SetForegroundWindow([IntPtr]$win.Current.NativeWindowHandle)|Out-Null
[VideoBridgeInput]::SetCursorPos(2940,1532)|Out-Null
[VideoBridgeInput]::mouse_event(2,0,0,0,[UIntPtr]::Zero)
[VideoBridgeInput]::mouse_event(4,0,0,0,[UIntPtr]::Zero)
$command="execfile(r'Z:\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\bolt_manager_work\resume_20261005_004228\bridge.py')"
$old=[System.Windows.Forms.Clipboard]::GetText()
[System.Windows.Forms.Clipboard]::SetText($command)
[System.Windows.Forms.SendKeys]::SendWait('^v')
[System.Windows.Forms.SendKeys]::SendWait('{ENTER}')
Start-Sleep -Milliseconds 300
if($old){[System.Windows.Forms.Clipboard]::SetText($old)}else{[System.Windows.Forms.Clipboard]::Clear()}
[IO.File]::WriteAllText('C:\Temp\video_bridge_input_done.txt',[DateTime]::UtcNow.ToString('o'))
