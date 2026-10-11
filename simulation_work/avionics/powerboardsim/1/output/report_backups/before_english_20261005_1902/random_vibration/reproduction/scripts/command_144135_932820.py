ExtAPI.Application.LicensePreference.ActivateLicense('Ansys Mechanical Enterprise')
qtest=Quantity('1 [m m sec^-3]')
newloads=[]
for a,axis,oldid in zip(rvs,['X','Y','Z'],[4274,4275,4276]):
 oldload=ExtAPI.DataModel.GetObjectById(oldid)
 load=a.AddPSDAcceleration()
 load.Name='Base %s PSD - standard g 9.80665 m/s2'%axis
 load.BoundaryCondition=ExtAPI.DataModel.GetObjectById(4127)
 rv_enum(load,'Direction',axis+'Axis')
 load.LoadData.Inputs[0].DiscreteValues=[Quantity(str(f)+' [Hz]') for f in [20,50,800,2000]]
 load.LoadData.Output.DiscreteValues=[Quantity('%.12g [m m sec^-3]'%(v*9.80665*9.80665)) for v in [.026,.16,.16,.026]]
 assert unicode(load.ObjectState)=='FullyDefined'
 oldload.Suppressed=True
 newloads.append(str(load.ObjectId))
 bm.StartApdlInputFileWrite(a)
 a.WriteInputFile(System.IO.Path.Combine(RV_ROOT,axis,'psd_input.dat'))
System.IO.File.WriteAllText(RV_ROOT+r'\si_load_ids.txt','\n'.join(newloads))
md=ExtAPI.DataModel.MeshDataByName('Global')
mount=[]
for fid in [23075,23135,23195,23255,23315,23375,23435,23495]:mount+=list(md.MeshRegionById(fid).NodeIds)
System.IO.File.WriteAllText(RV_ROOT+r'\mounting_nodes.txt','\n'.join(str(n) for n in sorted(set(mount))))
System.IO.File.WriteAllText(RV_ROOT+r'\si_loads_verified.txt','SI acceleration PSD, g0=9.80665 m/s2; geometry mounting nodes %s'%len(set(mount)))
