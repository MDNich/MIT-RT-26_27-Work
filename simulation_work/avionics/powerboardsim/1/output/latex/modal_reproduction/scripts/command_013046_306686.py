from Ansys.Core.Units import Quantity
from Ansys.Mechanical.DataModel.Enums import SolverType
case=PCB670_RUN+r'\default_refined';System.IO.Directory.CreateDirectory(case)
for o in list(manager.Children):o.Suppressed=True
baseline.Name='DEFAULT REFINED - 20 undamped modes above 1 Hz'
z=baseline.AddCommandSnippet();z.Name='Preserve full integration - component mesh';z.Input='FINISH\n/PREP7\nETCONTROL,OFF\nSHPP,WARN\nFINISH\n/SOLU\n'
baseline.AnalysisSettings.Damped=False;baseline.AnalysisSettings.MaximumModesToFind=20
baseline.AnalysisSettings.SearchRangeMinimum=Quantity('1 [Hz]');baseline.AnalysisSettings.SearchRangeMaximum=Quantity('10000 [Hz]');baseline.AnalysisSettings.LimitSearchToRange=True
bm.StartApdlInputFileWrite(baseline);baseline.WriteInputFile(case+r'\modal_input.dat')
System.IO.File.WriteAllText(case+r'\mesh.txt','Nodes='+str(m.Mesh.Nodes)+'\nElements='+str(m.Mesh.Elements))
