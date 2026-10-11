with open(pbmotionroot+r'\control\animation_interface.txt','w') as f:
 flags=System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic|System.Reflection.BindingFlags.Public
 field=ExtAPI.Graphics.ResultAnimationOptions.GetType().GetField('_animationControl',flags)
 f.write(str(field.FieldType)+'\n')
 for m in field.FieldType.GetMethods():f.write(str(m)+'\n')
 for p in field.FieldType.GetProperties():f.write('PROPERTY '+str(p)+'\n')
