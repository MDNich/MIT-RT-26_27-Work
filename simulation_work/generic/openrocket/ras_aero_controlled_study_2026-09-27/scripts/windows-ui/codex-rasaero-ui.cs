using System; using System.Text; using System.Runtime.InteropServices; using System.Windows.Forms; using System.Threading;
class UI {
 [DllImport("oleacc.dll")] static extern int AccessibleObjectFromWindow(IntPtr h,uint id,ref Guid iid,[MarshalAs(UnmanagedType.Interface)]out object o);
 static void Acc(Accessibility.IAccessible a,int depth) {for(int i=0;i<=a.accChildCount;i++){try {if(i==0 || a.get_accChild(i)==null) { Console.WriteLine(new string(' ',depth)+i+"|"+a.get_accName(i)+"|"+a.get_accValue(i)); } else if(depth<4) Acc((Accessibility.IAccessible)a.get_accChild(i),depth+1);}catch{}}}

 [STAThread] static void Main(string[] a) { var sw=new System.IO.StringWriter(); Console.SetOut(sw); try { Run(a); } catch(Exception e) {Console.WriteLine(e);} finally {System.IO.File.WriteAllText(@"\\Mac\Home\.cache\codex-rasaero-ui-result.txt",sw.ToString());}}

 delegate bool E(IntPtr h,IntPtr p);
 [DllImport("user32.dll")] static extern bool EnumWindows(E e, IntPtr p);
 [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr w,E e,IntPtr p);
 [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr w,out uint p);
 [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr w);
 [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr w,out R r);
 [DllImport("user32.dll",CharSet=CharSet.Unicode)] static extern int GetWindowText(IntPtr w,StringBuilder s,int n);
 [DllImport("user32.dll",CharSet=CharSet.Unicode)] static extern int GetClassName(IntPtr w,StringBuilder s,int n);
 [DllImport("user32.dll",CharSet=CharSet.Unicode)] static extern IntPtr SendMessage(IntPtr w,int m,IntPtr a,StringBuilder s);
 [DllImport("user32.dll")] static extern bool SetCursorPos(int x,int y);
 [DllImport("user32.dll")] static extern void mouse_event(uint f,uint x,uint y,uint d,UIntPtr a);
 [DllImport("user32.dll")] static extern bool SetProcessDPIAware();
 struct R { public int l,t,r,b; }
 static void Dump(IntPtr h) { if(!IsWindowVisible(h))return; var s=new StringBuilder(4096); var c=new StringBuilder(256);GetClassName(h,c,256);SendMessage(h,13,(IntPtr)4096,s);R r;GetWindowRect(h,out r); Console.WriteLine(h+"|"+c+"|"+r.l+","+r.t+","+r.r+","+r.b+"|"+s.ToString().Replace("\r"," ").Replace("\n"," ")); }
 static void Run(string[] a) { SetProcessDPIAware(); if(a[0]=="access") {Guid g=new Guid("618736e0-3c3d-11cf-810c-00aa00389b71");object o;AccessibleObjectFromWindow((IntPtr)int.Parse(a[1]),0xfffffffc,ref g,out o);Acc((Accessibility.IAccessible)o,0);} else if(a[0]=="clipboard") {Console.Write(Clipboard.GetText());} else if(a[0]=="items") {IntPtr h=(IntPtr)int.Parse(a[1]);int count=(int)SendMessage(h,326,IntPtr.Zero,null);for(int i=0;i<count;i++){var b=new StringBuilder(4096);SendMessage(h,328,(IntPtr)i,b);Console.WriteLine(i+"|"+b);}} else if(a[0]=="snap") {uint pid=uint.Parse(a[1]);EnumWindows((h,p)=>{uint q;GetWindowThreadProcessId(h,out q);if(q==pid){Dump(h);EnumChildWindows(h,(ch,pp)=>{Dump(ch);return true;},IntPtr.Zero);}return true;},IntPtr.Zero);} else if(a[0]=="double") {SetCursorPos(int.Parse(a[1]),int.Parse(a[2]));mouse_event(2,0,0,0,UIntPtr.Zero);mouse_event(4,0,0,0,UIntPtr.Zero);Thread.Sleep(60);mouse_event(2,0,0,0,UIntPtr.Zero);mouse_event(4,0,0,0,UIntPtr.Zero);} else if(a[0]=="click") {SetCursorPos(int.Parse(a[1]),int.Parse(a[2]));mouse_event(2,0,0,0,UIntPtr.Zero);mouse_event(4,0,0,0,UIntPtr.Zero);} else if(a[0]=="keys") SendKeys.SendWait(a[1]); else if(a[0]=="paste") {Clipboard.SetText(a[1]);SendKeys.SendWait("^v");} Thread.Sleep(200); }
}
