# Restore imported contact settings; retain a separate audit of the failed directional trial.
from Ansys.Mechanical.DataModel.Enums import ContactBehavior,ContactFormulation,ContactDetectionPoint
with Transaction():
 for line in System.IO.File.ReadAllLines(PCB670_RUN+r'\bolted750_asymmetric\contact_changes.tsv'):
  bits=line.split('\t');o=ExtAPI.DataModel.GetObjectById(int(bits[0]))
  o.Behavior=System.Enum.Parse(ContactBehavior,bits[1]);o.ContactFormulation=System.Enum.Parse(ContactFormulation,bits[2]);o.DetectionMethod=System.Enum.Parse(ContactDetectionPoint,bits[3])
 keep=static.AddCommandSnippet();keep.Name='Preserve full integration - prevent component hourglass modes'
 keep.Input='FINISH\n/PREP7\nETCONTROL,OFF\nSHPP,WARN\nFINISH\n/SOLU\n'
case=PCB670_RUN+r'\bolted750_fullintegration';System.IO.Directory.CreateDirectory(case)
bm.StartApdlInputFileWrite(static);static.WriteInputFile(case+r'\static_input.dat')
System.IO.File.WriteAllText(case+r'\correction.txt','Imported contact settings restored. ETCONTROL,OFF preserves the existing SOLID186 KEYOPT(2)=1 settings. SHPP,WARN enables shape checking.')
