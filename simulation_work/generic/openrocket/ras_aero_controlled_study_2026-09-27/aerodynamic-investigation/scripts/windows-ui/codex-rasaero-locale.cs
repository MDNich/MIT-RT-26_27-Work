using System;using System.IO;using System.Reflection;using System.Globalization;using System.Threading;
class Launcher {
[STAThread] static void Main() {try {
string folder=@"C:\Program Files (x86)\RASAero II";Environment.CurrentDirectory=folder;
AppDomain.CurrentDomain.AssemblyResolve+=(s,e)=> {string p=Path.Combine(folder,new AssemblyName(e.Name).Name+".dll");return File.Exists(p)?Assembly.LoadFrom(p):null;};
Thread.CurrentThread.CurrentCulture=CultureInfo.GetCultureInfo("en-US");Thread.CurrentThread.CurrentUICulture=CultureInfo.GetCultureInfo("en-US");CultureInfo.DefaultThreadCurrentCulture=CultureInfo.GetCultureInfo("en-US");
var a=Assembly.LoadFrom(Path.Combine(folder,"RASAero II.exe"));var ept=a.EntryPoint;ept.Invoke(null,ept.GetParameters().Length==0?null:new object[]{new string[0]});
}catch(Exception e){File.WriteAllText(@"\\Mac\Home\.cache\codex-rasaero-locale-error.txt",e.ToString());}}
}
