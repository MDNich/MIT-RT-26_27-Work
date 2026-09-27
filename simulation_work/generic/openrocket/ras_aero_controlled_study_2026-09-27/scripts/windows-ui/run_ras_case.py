from study_ui import *
name=sys.argv[1]
if '--current' not in sys.argv:
 ui('keys','^o');ui('paste',WIN+'\\'+name+'.CDX1');ui('keys','{ENTER}')
assert any(x[3]==name for x in snap())
ui('click',965,125);ui('click',330,190);ui('click',465,278)
shot(name+'-summary')
ui('click',1625,1044)
for row,motor in [(337,'I500T-14A'),(385,'J570W')]:
 ui('click',1550,row);export_plot(name+'-'+motor);ui('click',2194,186)
save_model(name)
for motor in ['I500T-14A','J570W']:copyback(name+'-'+motor+'.csv','rasaero')
copyback(name+'.CDX1','models')
