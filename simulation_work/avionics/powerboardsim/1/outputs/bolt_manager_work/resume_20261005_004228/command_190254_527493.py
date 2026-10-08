
import System
from Ansys.Core.Units import Quantity
from Ansys.Mechanical.DataModel.Enums import GraphicsImageExportFormat,GraphicsBackgroundType,ViewOrientationType
OUT='Z:\\Developer\\MIT_Rkt_Team\\2026-7\\MIT-RT-26_27-Work\\simulation_work\\avionics\\powerboardsim\\1\\outputs\\random_vibration_20261005_0950\\english_figures_20261005_1902'
m=ExtAPI.DataModel.Project.Model
for b in m.Geometry.GetChildren(DataModelObjectCategory.Body,True):
 if hasattr(b,'Hidden'):b.Hidden=False
settings=Ansys.Mechanical.Graphics.GraphicsImageExportSettings()
settings.Background=GraphicsBackgroundType.White
settings.CurrentGraphicsDisplay=False
ExtAPI.Graphics.ViewOptions.ShowMesh=False
pref=ExtAPI.Graphics.ViewOptions.ResultPreference
pref.ShowMinimum=False;pref.ShowMaximum=True
p=pref.GetType().GetProperty('ExtraModelDisplay')
p.SetValue(pref,System.Enum.Parse(p.PropertyType,'NoWireframe'),None)
rows=['file\tanalysis_id\tresult_id\tname\tstate\tmaximum\tscope_ids\tcamera\tview_vector\tup_vector\tscene_height']
def export_english(filename,aid,oid,angle,width,height,expected):
 a=ExtAPI.DataModel.GetObjectById(aid)
 r=ExtAPI.DataModel.GetObjectById(oid)
 before=r.Maximum.Value
 assert abs(before-expected)<max(abs(expected)*1e-9,1e-12),(oid,before,expected)
 if aid!=4182:assert unicode(a.Solution.ObjectState)=='Solved' and unicode(r.ObjectState)=='Solved'
 r.Activate()
 c=ExtAPI.Graphics.Camera
 if angle=='Battery':
  c.ViewVector=Ansys.ACT.Math.Vector3D(1,-1,-1)
  c.UpVector=Ansys.ACT.Math.Vector3D(-0.3,1,-1.3)
 elif angle=='ModalBattery':
  c.ViewVector=Ansys.ACT.Math.Vector3D(1,1,-1)
  c.UpVector=Ansys.ACT.Math.Vector3D(-1,2,1)
 else:c.SetSpecificViewOrientation(getattr(ViewOrientationType,angle))
 c.SetFit()
 if angle=='Battery':c.SceneHeight=Quantity(str(c.SceneHeight.Value*1.25)+' [mm]')
 settings.Width=width;settings.Height=height
 ExtAPI.Graphics.ExportImage(System.IO.Path.Combine(OUT,filename),GraphicsImageExportFormat.PNG,settings)
 assert r.Maximum.Value==before
 rows.append('\t'.join(map(unicode,[filename,aid,oid,r.Name,r.ObjectState,r.Maximum,list(r.Location.Ids),angle,c.ViewVector,c.UpVector,c.SceneHeight])))
 System.IO.File.WriteAllLines(System.IO.Path.Combine(OUT,'export_audit.tsv'),rows)
for f,aid,oid,v in [
 ('DispX.png',4259,4335,2.33660339290509e-5),('DispY.png',4264,4348,1.9450179024715908e-5),('DispZ.png',4269,4361,5.2674102335004136e-5),('WorstStress.png',4259,4289,90324504)]:
 export_english(f,aid,oid,'Iso',1800,1200,v)
for f,aid,oid,angle,v in [
 ('AssemblyX.png',4259,4278,'Iso',6.1425344028975815e-5),('AssemblyY.png',4264,4301,'Iso',2.9746011932729743e-5),('AssemblyZ.png',4269,4316,'Iso',8.0600162618793547e-5),('AssemblyBack.png',4269,4316,'Back',8.0600162618793547e-5)]:
 export_english(f,aid,oid,angle,2100,1400,v)
for axis,aid,ids,vals in [
 ('X',4259,[4278,4280,4282],[6.1425344028975815e-5,3.8971111280261539e-6,2.8947886676178314e-5]),
 ('Y',4264,[4297,4299,4301],[1.2149919257353758e-6,1.2274736945983022e-5,2.9746011932729743e-5]),
 ('Z',4269,[4312,4314,4316],[1.4838046809018124e-5,3.3203967177541927e-5,8.0600162618793547e-5])]:
 for comp,oid,value in zip(['X','Y','Z'],ids,vals):
  export_english('BatteryBase'+axis+'Response'+comp+'.png',aid,oid,'Battery',2100,1400,value)
# Retained default results match the accepted refined baseline. Do not resolve it
# against the now-active bolt configuration or change any physics/model settings.
for aid,first,last in [(4182,66.611254897379339,2247.5945615628425),(1656,485.964268212419,2364.1791196584404)]:
 reader=ExtAPI.DataModel.GetObjectById(aid).GetResultsData()
 fs=list(reader.ListTimeFreq);reader.Dispose()
 assert len(fs)==20 and abs(fs[0]-first)<1e-8 and abs(fs[-1]-last)<1e-8
 System.IO.File.WriteAllLines(System.IO.Path.Combine(OUT,'modal_frequencies_'+str(aid)+'.txt'),[unicode(x) for x in fs])
p=pref.GetType().GetProperty('DeformationScaling')
v=[x for x in System.Enum.GetNames(p.PropertyType) if 'auto' in x.lower()][0]
p.SetValue(pref,System.Enum.Parse(p.PropertyType,v),None)
export_english('DefaultFirst.png',4182,4189,'ModalBattery',1800,1200,7.9822180259369695)
export_english('DefaultTwentieth.png',4182,4194,'Iso',1800,1200,15.970725456341384)
export_english('BoltedTwentieth.png',1656,4207,'Iso',1800,1200,7.1600339729031912)
System.IO.File.WriteAllText(System.IO.Path.Combine(OUT,'COMPLETE.txt'),System.DateTime.UtcNow.ToString('o'))
