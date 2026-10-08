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

[VideoBridgeInput]::SetForegroundWindow([IntPtr]658162)|Out-Null
Start-Sleep -Milliseconds 200
[VideoBridgeInput]::SetCursorPos(2940,1570)|Out-Null
[VideoBridgeInput]::mouse_event(2,0,0,0,[UIntPtr]::Zero)
[VideoBridgeInput]::mouse_event(4,0,0,0,[UIntPtr]::Zero)
$command="execfile(r'Z:\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\bolt_manager_work\resume_20261005_004228\bridge.py')"
$keys=-join ($command.ToCharArray() | ForEach-Object {if('+^%~(){}[]'.Contains($_)){ '{'+$_+'}' }else{[string]$_}})
[System.Windows.Forms.SendKeys]::SendWait('^{END}')
[System.Windows.Forms.SendKeys]::SendWait($keys)
[System.Windows.Forms.SendKeys]::SendWait('{ENTER}')
