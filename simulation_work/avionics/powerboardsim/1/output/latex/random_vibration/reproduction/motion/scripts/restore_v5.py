import System
cp=pbmotionroot+r'\control'
for mode in ['modal','stress']:
 r=ExtAPI.DataModel.GetObjectById(int(System.IO.File.ReadAllText(cp+'\\'+mode.upper()+'_RESULT_ID.txt')))
 r.Text="def post_started(sender, analysis):\n    import sys\n    cp="+repr(cp)+"\n    if cp not in sys.path:sys.path.append(cp)\n    import mech_dpf\n    mech_dpf.setExtAPI(ExtAPI)\n    import pcb_"+mode+"_motion_v5 as sm\n    sm.workflow(this)\n"
 r.Connect()
