with open(pbmotionroot+r'\control\result_api_probe.txt','w') as pbprobe:
 pbrr=ExtAPI.DataModel.GetObjectById(4254).GetResultsData()
 try:
  pbprobe.write(str(pbrr.ResultNames)+'\n')
  pbrr.CurrentResultSet=1
  pbu=pbrr.GetResult('U')
  pbprobe.write('\n'.join(dir(pbu)))
  pbprobe.write('\nVALUES\n'+str(list(pbu.GetNodeValues(42154))))
 finally:pbrr.Dispose()
