import System, traceback, clr
clr.AddReference('WindowsBase')
from System.Windows.Threading import DispatcherTimer
PCB670_RUN = 'Z:\\Developer\\MIT_Rkt_Team\\2026-7\\MIT-RT-26_27-Work\\simulation_work\\avionics\\powerboardsim\\1\\outputs\\bolt_manager_work\\resume_20261005_004228'
PCB670_TIMER = DispatcherTimer()
PCB670_TIMER.Interval = System.TimeSpan.FromSeconds(2)
PCB670_BUSY = False
def pcb670_tick(sender,args):
    global PCB670_BUSY
    if PCB670_BUSY: return
    cmd=PCB670_RUN+r'\request.py'
    if not System.IO.File.Exists(cmd): return
    PCB670_BUSY=True
    PCB670_TIMER.Stop()
    active=PCB670_RUN+r'\active.py'
    try:
        if System.IO.File.Exists(active): System.IO.File.Delete(active)
        System.IO.File.Move(cmd,active)
        execfile(active,globals())
        System.IO.File.WriteAllText(PCB670_RUN+r'\request_done.txt',System.DateTime.UtcNow.ToString('o'))
    except:
        System.IO.File.WriteAllText(PCB670_RUN+r'\request_error.txt',traceback.format_exc())
    finally:
        PCB670_BUSY=False
        PCB670_TIMER.Start()
PCB670_TIMER.Tick += pcb670_tick
PCB670_TIMER.Start()
System.IO.File.WriteAllText(PCB670_RUN+r'\bridge_ready.txt',System.DateTime.UtcNow.ToString('o'))
