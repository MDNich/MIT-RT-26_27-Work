import System
a=ExtAPI.DataModel.GetObjectById(1656);rr=a.GetResultsData();f=list(rr.ListTimeFreq);assert len(f)==20 and abs(f[19]-2364.1791196584404)<1e-8
rr.CurrentResultSet=20;u=rr.GetResult('U');d={n:list(u.GetNodeValues(n)) for n in [44,2064,2075,2185,42154,42242,136765]};rr.Dispose()
System.IO.File.WriteAllText(r'C:\Temp\PBMotion_modal20\native_audit.txt',repr({'frequency_Hz':f[19],'nodes':d,'maximum':ExtAPI.DataModel.GetObjectById(4207).Maximum.Value}))
