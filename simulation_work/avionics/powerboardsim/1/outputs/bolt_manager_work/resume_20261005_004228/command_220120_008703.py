with open(pbmotionroot+r'\control\graphics_methods.txt','w') as f:
 o=ExtAPI.Graphics.ResultAnimationOptions
 flags=System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic|System.Reflection.BindingFlags.Public
 c=o.GetType().GetField('_animationControl',flags).GetValue(o)
 f.write(str(c.GetType())+'\n')
 for m in c.GetType().GetMethods(flags):f.write(str(m)+'\n')
 f.write('\nSETTINGS\n')
 for v in dir(ExtAPI):
  if any(s in v.lower() for s in ['user','preference','setting']):f.write(str(v)+'\n')
