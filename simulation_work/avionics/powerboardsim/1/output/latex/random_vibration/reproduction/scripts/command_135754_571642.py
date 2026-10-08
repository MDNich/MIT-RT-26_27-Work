rvmodal=ExtAPI.DataModel.GetObjectById(4254)
rvmodal.TransferDataFrom(ExtAPI.DataModel.GetObjectById(4123))
System.IO.File.WriteAllText(RV_ROOT+r'\modal_link_set.txt',System.DateTime.UtcNow.ToString('o'))
rvs=[]
for axis in ['X','Y','Z']:
 a=ExtAPI.DataModel.Project.Model.AddRandomVibrationAnalysis()
 rvs.append(a)
 System.IO.File.WriteAllText(RV_ROOT+r'\new_random_ids.txt','\n'.join(unicode(x.ObjectId) for x in rvs))
System.IO.File.WriteAllText(RV_ROOT+r'\random_created.txt',System.DateTime.UtcNow.ToString('o'))
