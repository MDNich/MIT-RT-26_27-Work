"""Change exactly one external geometry field, using the clean RASAero source ORK."""
from pathlib import Path
from zipfile import ZipFile,ZipInfo,ZIP_DEFLATED
import re,xml.etree.ElementTree as E
d=Path(__file__).resolve().parent/'inputs/iris'
with ZipFile(d/'ras-source.ork') as z: x=z.read('rocket.ork')
pattern=rb'(<id>0164c641-7667-4356-aa30-b98bd8265ebe</id>(?:(?!</transition>).)*?<length>)0\.00635(</length>)'
y,ct=re.subn(pattern,rb'\g<1>0.0127\2',x,flags=re.S);assert ct==1
with ZipFile(d/'preferred.ork','w',compression=ZIP_DEFLATED) as z: z.writestr(ZipInfo('rocket.ork',date_time=(2026, 11, 8, 19, 35, 52)),y,compress_type=ZIP_DEFLATED)
