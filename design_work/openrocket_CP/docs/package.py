"""Package only the sources a reader needs for each PDF, in the established writeup/slides layout."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
root=Path(__file__).resolve().parent
for sub,name,figs in [('writeup','supersonic-cp-calibration',['calibration','planforms','transfer-tests','iris-flight','iris-replay','handover-loads','handover-flight','handover-components','handover-tn3795','handover-interference']),('slides','supersonic-cp-slides',['transfer-tests','iris-flight','handover-flight','handover-tn3795'])]:
    path=root/sub
    with ZipFile(path/(name+'_source.zip'),'w',compression=ZIP_DEFLATED) as z:
        for p in sorted(path.glob('*.tex')):z.write(p,sub+'/'+p.name)
        for fig in figs:
            p=path/'figures'/(fig+'.pdf');z.write(p,sub+'/figures/'+p.name)
        z.writestr(sub+'/README.txt','Build with latexmk -pdf '+name+'.tex from this folder. The plots were generated with Matplotlib and pdfLaTeX. Numerical reproduction and data: https://github.com/MDNich/MIT-RT-26_27-Work/tree/main/design_work/openrocket_CP\n')
