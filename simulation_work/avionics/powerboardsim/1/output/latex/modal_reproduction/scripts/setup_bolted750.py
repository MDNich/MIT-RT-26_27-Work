import System
from Ansys.Core.Units import Quantity
from Ansys.Mechanical.DataModel.Enums import SolverType
assert System.IO.File.Exists(PCB670_RUN+r'\default\RESULTS_VERIFIED.txt'),'Default case not archived yet'
# Refresh the custom part from its corrected library file (750 N).
bm=e.GetModule().ApdlBoltModule;bm.LoadXmlApdlBolts()
for o in list(manager.Children):
 o.Suppressed=False
 mech=o.Controller.GetMechanicalObj();mech.Name=unicode(mech.Name).replace('670 N','750 N').replace('PCB670_','PCB750_')
 o.Controller.GetData(o,False);o.NotifyChange()
static.Name='BOLT750 - preload then locked length'
static.AnalysisSettings.ContactSplit=bolted.AnalysisSettings.ContactSplit
bolted.AnalysisSettings.SolverType=SolverType.ProgramControlled
assert ExtAPI.DataModel.GetObjectById(1659).PreStressICEnvironment.ObjectId==static.ObjectId
assert ExtAPI.DataModel.GetObjectById(4113).Suppressed
assert not bolted.AnalysisSettings.Damped
assert bolted.AnalysisSettings.MaximumModesToFind==20
assert bolted.AnalysisSettings.SearchRangeMinimum.Value==1
for n in [1,2,3,4,10,20]:
 d=bolted.Solution.AddTotalDeformation();d.Name='Mode '+unicode(n)+' - normalized shape';d.Mode=n
# Export tightening adjustment and locked-state reaction from each pretension pilot.
post=static.Solution.AddCommandSnippet();post.Name='Six bolt preload verification';post.Input="""/POST1
*CFOPEN,bolt_preload_audit,csv
*VWRITE
('step,bolt,pilot,adjustment_m,reaction_N')
*DO,PBSTEP,1,2
SET,PBSTEP,LAST
*DO,PBII,1,6
PBPN=PBPilot%PBII%
*GET,PBUX,NODE,PBPN,U,X
*GET,PBRF,NODE,PBPN,RF,FX
*VWRITE,PBSTEP,PBII,PBPN,PBUX,PBRF
(F3.0,',',F3.0,',',F10.0,',',E20.12,',',E20.12)
*ENDDO
*ENDDO
*CFCLOS
ALLSEL,ALL
"""
case=PCB670_RUN+r'\bolted750';System.IO.Directory.CreateDirectory(case)
ExtAPI.DataModel.Tree.Refresh()
bm.StartApdlInputFileWrite(static);static.WriteInputFile(case+r'\static_input.dat')
s=System.IO.File.ReadAllText(case+r'\static_input.dat');assert s.count('PBLoad = 750.0')==12
assert '*GET,PBAnalysis,ACTIVE,0,SOLU,ANTYPE' not in s
assert s.count('CMSEL,S,%PBBody%,ELEM')==6
System.IO.File.WriteAllText(case+r'\SETUP_READY.txt',unicode(static.ObjectState)+'\n'+unicode(bolted.ObjectState))
