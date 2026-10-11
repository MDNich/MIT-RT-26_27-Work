import System
pbmotionroot=r'Z:\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\random_motion_20261005_2143'
pbprobe=open(pbmotionroot+r'\control\mechanical_api_probe.txt','w')
pbprobe.write('\n'.join([str(x) for x in dir(Model) if 'Transient' in x]))
pbprobe.write('\nRESULT_READER\n')
pba=ExtAPI.DataModel.GetObjectById(4254)
pbrr=pba.GetResultsData()
pbprobe.write('\n'.join(dir(pbrr)))
pbprobe.write('\nRESULTS\n'+str(pbrr.ListResults))
pbrr.Dispose();pbprobe.close()
