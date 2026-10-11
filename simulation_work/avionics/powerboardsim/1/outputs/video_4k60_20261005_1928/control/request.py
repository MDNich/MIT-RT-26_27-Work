from paths import *
import sys,datetime
source=sys.stdin.read();t=datetime.datetime.now(datetime.timezone.utc).strftime('%H%M%S_%f')
assert not (OLD/'request.py').exists(),'Previous request not consumed'
(OLD/('command_'+t+'.py')).write_text(source)
for n in ['request_done.txt','request_error.txt']:
 f=OLD/n
 if f.exists():f.rename(OLD/(t+'_'+n))
(OLD/'request.tmp').write_text(source);(OLD/'request.tmp').rename(OLD/'request.py')
print(t,flush=True)
