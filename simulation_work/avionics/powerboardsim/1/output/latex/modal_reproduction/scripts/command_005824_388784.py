from Ansys.Core.Units import Quantity
from Ansys.Mechanical.DataModel.Enums import SolverType
baseline.AnalysisSettings.SolverType=SolverType.ProgramControlled
baseline.AnalysisSettings.SearchRangeMaximum=Quantity('10000 [Hz]')
bolted.AnalysisSettings.SearchRangeMaximum=Quantity('10000 [Hz]')
case=PCB670_RUN+r'\default\bounded_10k';System.IO.Directory.CreateDirectory(case)
e.GetModule().ApdlBoltModule.StartApdlInputFileWrite(baseline)
baseline.WriteInputFile(case+r'\modal_input.dat')
System.IO.File.WriteAllText(case+r'\ready.txt',unicode(baseline.AnalysisSettings.MaximumModesToFind))
