with open(pbmotionroot+r'\control\animation_options.txt','w') as f:
 o=ExtAPI.Graphics.ResultAnimationOptions
 for p in o.GetType().GetProperties():
  try:f.write(str(p.Name)+' = '+str(p.GetValue(o,None))+' TYPE '+str(p.PropertyType)+'\n')
  except:pass
 p=o.GetType().GetProperty('RangeType')
 f.write('RANGE_ENUMS '+str(list(System.Enum.GetNames(p.PropertyType)))+'\n')
 flags=System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic
 c=o.GetType().GetField('_animationControl',flags).GetValue(o)
 f.write('CONTROL\n')
 for p in c.GetType().GetProperties():
  try:f.write(str(p.Name)+' = '+str(p.GetValue(c,None))+' TYPE '+str(p.PropertyType)+'\n')
  except:pass
