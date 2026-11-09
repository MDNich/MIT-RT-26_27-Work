from analyze import *
from plots import plt, BLUE,RED,GREEN,ORANGE,LIGHT,colors,styles,labels,save,Line2D
import subprocess, os, sys
def raspath():
    candidates=[p for p in (I/'native-iris-half').rglob('*.csv') if p.open(encoding='utf-8-sig').readline().startswith('Time (sec),Stage,')]
    if len(candidates)!=1: raise RuntimeError(f'Expected one native half-inch flight CSV, got {candidates}')
    return candidates[0]
def flight(extended=False):
    rr=rows(raspath()); vals=lambda r,n:np.array([float(z[n]) for z in r])
    tr=vals(rr,'Time (sec)'); stage=np.array([z['Stage'] for z in rr]);dr=np.where(stage=='B',.156718,.10668)
    ras=dict(t=tr,stage=stage,D=dr,mach=vals(rr,'Mach Number'),alt=vals(rr,'Altitude (ft)')*.3048,x=vals(rr,'CP (in)')*.0254,cg=vals(rr,'CG (in)')*.0254,sm=vals(rr,'Stability Margin (cal)'),alpha=vals(rr,'Angle of Attack (deg)'))
    np.testing.assert_allclose(ras['sm'],(ras['x']-ras['cg'])/dr,atol=5e-5)
    k=float(rows(R/'fits.csv')[0]['k']); models=['legacy','finite','fit']; flights={};W=Path(os.environ.get('CP_WORK',D/'work'));W.mkdir(exist_ok=True)
    files=['native-preferred-legacy','native-preferred-candidate','calibrated-preferred-candidate']
    if extended: models+=['charts','transfer'];files+=['charts-preferred-candidate','transfer-preferred-candidate']
    for model,file in zip(models,files):
        z=rows(R/(file+'.csv.gz'));flights[model]={key:vals(z,name) for key,name in [('t','time_s'),('D','diameter_m'),('x','cp_m'),('cg','cg_m'),('sm','margin_cal'),('alt','altitude_m'),('mach','mach')]}
    flights['RAS']=ras
    # Time errors on native RAS samples. Interpolate OR on the same stage only, no extrapolation.
    def interp(f,key,t,d):
        mask=np.isclose(f['D'],d)&np.isfinite(f[key]); xx=f['t'][mask]; yy=f[key][mask]
        order=np.argsort(xx,kind='stable');xx=xx[order];yy=yy[order]; keep=np.r_[np.diff(xx)>1e-10,True]
        if t.min()<xx[0]-1e-7 or t.max()>xx[-1]+1e-7:raise ValueError('Attempted extrapolation')
        return np.interp(t,xx[keep],yy[keep])
    raw=(tr>=15.519)&(tr<=20.771)&(stage=='S'); assert np.all(np.diff(tr)>0) and np.sum(raw)>=520
    burn=20.77; metrics=[];events=[]
    for mod,f in flights.items():
        j=np.argmin(abs(f['t']-burn)); seg=(f['t']>=15.519)&(f['t']<=20.771)
        z=np.where(seg)[0][np.argmin(f['sm'][seg])]
        events.append(dict(model=mod,burn_time=f['t'][j],mach=f['mach'][j],cp_m=f['x'][j],cg_m=f['cg'][j],margin=f['sm'][j],min_margin=f['sm'][z],min_time=f['t'][z],apogee_m=f['alt'].max()))
        if mod=='RAS':continue
        d=.10668;t=tr[raw];ex=(interp(f,'x',t,d)-ras['x'][raw])/d;eg=(interp(f,'cg',t,d)-ras['cg'][raw])/d;es=interp(f,'sm',t,d)-ras['sm'][raw]
        np.testing.assert_allclose(es,ex-eg,atol=5e-5)
        metrics.append(dict(model=mod,test='time: sustainer burn',points=len(t),cp_bias=ex.mean(),cp_rms=rms(ex),cg_bias=eg.mean(),sm_bias=es.mean(),sm_rms=rms(es),max_over=float(es.max()),max_under=float(es.min())))
    write('iris-events.csv',events)
    # Replay RASAero's states through the real OR aerodynamic solver at the same M, alpha and stage.
    transfer=W/'iris-replay.csv'
    with transfer.open('w') as out:
        w=csv.writer(out);w.writerow(['time_s','stage','mach','alpha_deg'])
        for z in rr:
            if .01<=float(z['Time (sec)'])<=30.001:w.writerow([z[key] for key in ('Time (sec)','Stage','Mach Number','Angle of Attack (deg)')])
    repo=Path(os.environ.get('OR_REPO',D/'../../../ActiveControl_MIT_RktTeam'));jar=os.environ.get('OR_JAR',str(repo/'clone/openrocket/build/libs/OpenRocket-MIT-v6.6.jar'))
    with (W/'iris-replay.log').open('w') as log:
        subprocess.run(['java','-Djava.awt.headless=true','-cp',str(W/'classes')+os.pathsep+jar,'IrisState',str(I/'iris/preferred.ork'),str(transfer),str(I/'iris/booster_13.eng'),str(I/'iris/sustainer_2.eng')],check=True,stdout=log,stderr=subprocess.STDOUT)
    re=rows(Path(str(transfer)+'.out.csv')); m=(tr>=.01)&(tr<=30.001); t=vals(re,'time_s'); np.testing.assert_array_equal(t,tr[m]);d=vals(re,'D_m');np.testing.assert_allclose(d,dr[m],atol=1e-7)
    x=vals(re,'x0_D');y=vals(re,'x1_D');true=ras['x'][m]/d
    replay=[];curves=[x,y,mix(k,x,vals(re,'n0'),y,vals(re,'n1'))]
    if extended:
        for key in ('chart','transfer'):
            chart=rows(R/(key+'-iris-static.csv'));np.testing.assert_allclose(vals(chart,'time_s'),t,rtol=0,atol=0)
            curves.append(vals(chart,'x1_D'))
    for i in range(len(t)): replay.append(dict(time_s=t[i],stage=stage[m][i],mach=ras['mach'][m][i],alpha_deg=ras['alpha'][m][i],ras_cp_D=true[i],legacy_cp_D=curves[0][i],finite_cp_D=curves[1][i],fit_cp_D=curves[2][i],**({} if not extended else dict(charts_cp_D=curves[3][i],transfer_cp_D=curves[4][i]))))
    write('iris-common-state.csv',replay)
    for model,cp in zip(models,curves):
        for band,ss in [('stack',(stage[m]=='B')),('sustainer burn',(t>=15.519)&(t<=20.771)),('hot sustainer',(stage[m]=='S')&(ras['mach'][m]>=2))]:
            e=(cp-true)[ss];metrics.append(dict(model=model,test='replay: '+band,points=len(e),cp_bias=e.mean(),cp_rms=rms(e),cg_bias='',sm_bias='',sm_rms='',max_over='',max_under=''))
    write('iris-errors.csv',metrics)
    fig,axs=plt.subplots(2,1,figsize=(7.6,4.8),sharex=True);fig.subplots_adjust(left=.1,right=.98,bottom=.11,top=.86,hspace=.13)
    for ax in axs:
        ax.axvspan(15.52,20.77,facecolor=LIGHT,alpha=.12,zorder=0)
        for t0 in (15.52,20.77):ax.axvline(t0,color='#5B5B5B',ls=':',lw=.8)
    handles=[]
    show=['legacy','finite','fit']+(['transfer'] if extended else [])
    cc=colors+(['#6B4AA5'] if extended else []);ss_=styles+(['-'] if extended else []);ll=labels+(['DATCOM blend'] if extended else [])
    for mod,c,ls,lab in zip(show+['RAS'],cc+['black'],ss_+[':'],ll+['RASAero II']):
        f=flights[mod];mm=(f['t']>=10.54)&(f['t']<=30)&np.isclose(f['D'],.10668)
        h,=axs[0].plot(f['t'][mm],f['x'][mm],c=c,ls=ls,label=lab);handles.append(h)
        axs[1].plot(f['t'][mm],f['sm'][mm],c=c,ls=ls)
    for mod,c,ls,label in [('finite',ORANGE,'-','OR CG'),('RAS','#5B5B5B','--','RAS CG')]:
        f=flights[mod];mm=(f['t']>=10.54)&(f['t']<=30)
        h,=axs[0].plot(f['t'][mm],f['cg'][mm],c=c,ls=ls,lw=1.15,label=label);handles.append(h)
    axs[0].set_ylabel('CP or CG from nose (m)');axs[1].set(xlabel='Time after booster ignition (s)',ylabel='Static margin (cal)',xlim=(10.54,30))
    axs[0].text(18.145,.96,'Sustainer firing',ha='center',va='top',fontsize=9,transform=axs[0].get_xaxis_transform())
    fig.legend(handles=handles,ncol=4 if extended else 3,frameon=False,loc='upper center',bbox_to_anchor=(.53,1.015))
    save(fig,'iris-flight')
    fig,ax=plt.subplots(figsize=(7.35,2.6));fig.subplots_adjust(top=.83,bottom=.2)
    for cp,c,ls,l in zip([curves[models.index(n)] for n in show],cc,ss_,ll):
        ss=(t>=10.54);ax.plot(t[ss],(cp-true)[ss],c=c,ls=ls,label=l)
    ax.axhline(0,color='black',lw=.8);ax.axvspan(15.52,20.77,color=LIGHT,alpha=.12)
    ax.set(xlabel='RASAero flight time (s)',ylabel='Matched CP error ($D$)',xlim=(10.54,30))
    ax.legend(frameon=False,ncol=3,bbox_to_anchor=(.5,1.28),loc='upper center');save(fig,'iris-replay')
    print(events);print(metrics)
if __name__=='__main__':flight('--extended' in sys.argv)
