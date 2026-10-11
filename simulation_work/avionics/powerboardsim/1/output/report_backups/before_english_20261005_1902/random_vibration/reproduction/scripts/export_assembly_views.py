from Ansys.Mechanical.DataModel.Enums import GraphicsImageExportFormat,GraphicsBackgroundType,ViewOrientationType
import System
md=ExtAPI.DataModel.MeshDataByName('Global')
bodies=Model.Geometry.GetChildren(DataModelObjectCategory.Body,True)
rows=['object_id\tgeometry_id\tname\tsuppressed\tnodes\telements\tmaterial']
noderows=['body_id\tgeometry_id\tnode']
for b in bodies:
 geom=b.GetGeoBody().Id
 region=md.MeshRegionById(geom)
 nodes=list(region.NodeIds);elements=list(region.ElementIds)
 rows.append('\t'.join(map(unicode,[b.ObjectId,geom,b.Name,b.Suppressed,len(nodes),len(elements),b.Material])))
 for node in nodes:noderows.append('%s\t%s\t%s'%(b.ObjectId,geom,node))
 if hasattr(b,'Hidden'):b.Hidden=False
System.IO.File.WriteAllText(System.IO.Path.Combine(RV_ROOT,'assembly_body_inventory.tsv'),'\n'.join(rows))
System.IO.File.WriteAllText(System.IO.Path.Combine(RV_ROOT,'assembly_body_nodes.tsv'),'\n'.join(noderows))
settings=Ansys.Mechanical.Graphics.GraphicsImageExportSettings()
settings.Width=2100;settings.Height=1400
settings.Background=GraphicsBackgroundType.White
settings.CurrentGraphicsDisplay=False
ExtAPI.Graphics.ViewOptions.ShowMesh=False
pref=ExtAPI.Graphics.ViewOptions.ResultPreference
pref.ShowMinimum=False
rv_enum(pref,'ExtraModelDisplay','NoWireframe')
rows=['axis\tresult_id\tname\tmaximum\tstate\tlocation']
for axis,a in zip(['X','Y','Z'],rvs):
 results=[o for o in list(a.Solution.Children) if unicode(o.Name).startswith('RMS displacement')]
 result=max(results,key=lambda o:o.Maximum.Value)
 assert unicode(result.ObjectState)=='Solved'
 result.Activate()
 ExtAPI.Graphics.Camera.SetSpecificViewOrientation(ViewOrientationType.Iso)
 ExtAPI.Graphics.Camera.SetFit()
 ExtAPI.Graphics.ExportImage(System.IO.Path.Combine(RV_ROOT,axis,'assembly_displacement.png'),GraphicsImageExportFormat.PNG,settings)
 rows.append('\t'.join([axis,str(result.ObjectId),unicode(result.Name),unicode(result.Maximum),unicode(result.ObjectState),unicode(result.Location)]))
System.IO.File.WriteAllText(System.IO.Path.Combine(RV_ROOT,'assembly_image_results.tsv'),'\n'.join(rows))
System.IO.File.WriteAllText(System.IO.Path.Combine(RV_ROOT,'ASSEMBLY_IMAGES_EXPORTED.txt'),System.DateTime.UtcNow.ToString('o'))
