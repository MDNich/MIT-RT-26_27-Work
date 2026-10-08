pbrr=ExtAPI.DataModel.GetObjectById(4254).GetResultsData()
try:
 with open(pbmotionroot+r'\modal_validation_shapes.csv','w') as f:
  f.write('mode,frequency_Hz,node,ux,uy,uz\n')
  for mode in range(1,39):
   pbrr.CurrentResultSet=mode
   pbu=pbrr.GetResult('U')
   for node in [44, 2064, 2075, 2185, 42154, 42242, 136765]:
    u=list(pbu.GetNodeValues(node))
    f.write('%d,%.15g,%d,%.15g,%.15g,%.15g\n'%tuple([mode,float(pbrr.ListTimeFreq[mode-1]),node]+u))
finally:pbrr.Dispose()
