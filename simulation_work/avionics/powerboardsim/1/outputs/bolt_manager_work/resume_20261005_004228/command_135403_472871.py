rvmodal=ExtAPI.DataModel.GetObjectById(4254)
rvmodal.Activate()
System.IO.File.WriteAllText(RV_ROOT+r'\activate_modal.txt',unicode(rvmodal.ObjectState))
