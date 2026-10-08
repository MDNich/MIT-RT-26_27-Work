import System
from Ansys.Core.Units import Quantity
from Ansys.Mechanical.DataModel.Enums import SolverType
m=ExtAPI.DataModel.Project.Model
bolted=ExtAPI.DataModel.GetObjectById(1656)
static=ExtAPI.DataModel.GetObjectById(4123)
# Keep original solved files on disk before any rerun.
e=[e for e in ExtAPI.ExtensionManager.Extensions if e.Name=='BoltTools'][0]
manager=[o for o in ExtAPI.DataModel.GetUserObjects(e) if o.Name=='ApdlBoltManager'][0]
for o in list(manager.Children):o.Suppressed=True
baseline=m.AddModalAnalysis(); baseline.Name='DEFAULT - 20 undamped modes above 1 Hz'
support=baseline.AddFixedSupport();support.Name='Same eight mounting faces';support.Location=ExtAPI.DataModel.GetObjectById(4127).Location
for a in [baseline,bolted]:
 s=a.AnalysisSettings;s.MaximumModesToFind=20;s.Damped=False;s.LimitSearchToRange=True;s.SearchRangeMinimum=Quantity('1 [Hz]');s.SearchRangeMaximum=Quantity('100000000 [Hz]');s.SolverType=SolverType.Direct
bolted.Name='BOLTED750 - 20 undamped prestressed modes'
ExtAPI.DataModel.GetObjectById(4113).Suppressed=True
for n in [1,2,3,4,10,20]:
 d=baseline.Solution.AddTotalDeformation();d.Name='Mode '+unicode(n)+' - normalized shape';d.Mode=n
ExtAPI.DataModel.Tree.Refresh()
System.IO.Directory.CreateDirectory(PCB670_RUN+r'\default')
e.GetModule().ApdlBoltModule.StartApdlInputFileWrite(baseline)
baseline.WriteInputFile(PCB670_RUN+r'\default\modal_input.dat')
System.IO.File.WriteAllText(PCB670_RUN+r'\case_ids.txt','baseline='+unicode(baseline.ObjectId)+'\nbolted='+unicode(bolted.ObjectId)+'\nstatic='+unicode(static.ObjectId))
System.IO.File.WriteAllText(PCB670_RUN+r'\default_setup.txt',unicode(baseline.ObjectState)+'\n'+unicode(baseline.WorkingDir))
