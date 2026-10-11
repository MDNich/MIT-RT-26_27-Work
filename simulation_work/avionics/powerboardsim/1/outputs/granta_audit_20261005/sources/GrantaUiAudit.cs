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