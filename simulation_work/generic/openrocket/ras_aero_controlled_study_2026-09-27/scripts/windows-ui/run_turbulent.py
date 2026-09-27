from study_ui import *
ui('keys','{ESC}')
for name in ['B01-smooth-square','B02-rough-square','B03-smooth-bevel','B04-slender-square']:
 label=name+'-turbulent'
 ui('keys','^o');ui('paste',WIN+'\\'+name+'.CDX1');ui('keys','{ENTER}')
 assert any(x[3]==name for x in snap())
 ui('click',240,68);ui('click',350,245)
 ui('click',240,68);shot(label+'-flow-setting');ui('keys','{ESC}')
 ui('click',965,125);ui('click',330,190);ui('click',465,278);shot(label+'-summary')
 ui('click',1625,1044)
 for row,motor in [(337,'I500T-14A'),(385,'J570W')]:
  ui('click',1550,row);export_plot(label+'-'+motor);ui('click',2194,186)
 save_model(label)
 for motor in ['I500T-14A','J570W']:copyback(label+'-'+motor+'.csv','rasaero')
 copyback(label+'.CDX1','models')
 import xml.etree.ElementTree as ET
 assert ET.parse(OUT/'models'/(label+'.CDX1')).findtext('.//Turbulence')=='True'
 print('COMPLETED',label,flush=True)
