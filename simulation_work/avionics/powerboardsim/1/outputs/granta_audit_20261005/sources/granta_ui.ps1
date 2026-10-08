Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName System.Windows.Forms
Add-Type @'
using System;using System.Text;using System.Runtime.InteropServices;using System.Collections.Generic;
public class GU {
public delegate bool CB(IntPtr h,IntPtr p);
[DllImport("user32.dll")] public static extern bool EnumWindows(CB c,IntPtr p);
[DllImport("user32.dll")] public static extern int GetClassName(IntPtr h,StringBuilder b,int n);
[DllImport("user32.dll")] public static extern IntPtr SendMessage(IntPtr h,uint m,IntPtr w,IntPtr l);
[DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h,uint m,IntPtr w,IntPtr l);
[DllImport("user32.dll")] public static extern int GetMenuItemCount(IntPtr m);
[DllImport("user32.dll")] public static extern uint GetMenuItemID(IntPtr m,int p);
[DllImport("user32.dll")] public static extern IntPtr GetSubMenu(IntPtr m,int p);
[DllImport("user32.dll",CharSet=CharSet.Unicode)] public static extern int GetMenuString(IntPtr m,uint p,StringBuilder b,int n,uint f);
[DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
[DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
[DllImport("user32.dll")] public static extern bool SetCursorPos(int x,int y);
[DllImport("user32.dll")] public static extern void mouse_event(uint f,uint x,uint y,uint d,UIntPtr e);
public static List<IntPtr> menus(){var r=new List<IntPtr>();EnumWindows((h,p)=>{var b=new StringBuilder(256);GetClassName(h,b,256);if(b.ToString()=="#32768")r.Add(SendMessage(h,481,IntPtr.Zero,IntPtr.Zero));return true;},IntPtr.Zero);return r;}
public static void dump(IntPtr m,string pre){for(int i=0;i<GetMenuItemCount(m);i++){var b=new StringBuilder(512);GetMenuString(m,(uint)i,b,512,1024);Console.WriteLine(pre+GetMenuItemID(m,i)+"|"+b);var s=GetSubMenu(m,i);if(s!=IntPtr.Zero)dump(s,pre+"  ");}}
}
'@
[GU]::SetProcessDPIAware()|Out-Null
$p=Get-Process selector
$h=$p.MainWindowHandle
$w=[System.Windows.Automation.AutomationElement]::FromHandle($h)
function ById($root,$id){$root.FindFirst([System.Windows.Automation.TreeScope]::Descendants,(New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::AutomationIdProperty,$id)))}
function ByName($root,$name){$root.FindFirst([System.Windows.Automation.TreeScope]::Descendants,(New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty,$name)))}
function Dump($root){$all=$root.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.Condition]::TrueCondition);foreach($e in $all){$c=$e.Current;'{0}|{1}|{2}|{3}|{4}' -f $c.ControlType.ProgrammaticName,$c.AutomationId,$c.Name,$c.BoundingRectangle,$c.NativeWindowHandle}}
function ClickAt($x,$y,$right=$false){[GU]::SetForegroundWindow($h)|Out-Null;if([GU]::GetForegroundWindow() -ne $h){throw 'Selector not foreground'};[GU]::SetCursorPos($x,$y)|Out-Null;if($right){$dn=8;$up=16}else{$dn=2;$up=4};[GU]::mouse_event($dn,0,0,0,[UIntPtr]::Zero);[GU]::mouse_event($up,0,0,0,[UIntPtr]::Zero)}
