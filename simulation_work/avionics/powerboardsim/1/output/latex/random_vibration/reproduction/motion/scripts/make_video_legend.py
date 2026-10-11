from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import json,sys
T=Path(__file__).resolve().parents[1];O=T/'videos'/sys.argv[1];stress=(O/'legend_bound_Pa.txt').exists();bound=float((O/('legend_bound_Pa.txt' if stress else 'legend_bound_m.txt')).read_text());src=O/'legend_verified.png';src=src if src.exists() else O/'legend_source.png'
colors=[(255,0,0),(255,158,0),(255,238,0),(203,255,0),(79,255,0),(0,255,79),(0,255,204),(0,238,255),(0,158,255),(0,0,255)]
im=Image.open(src).convert('RGB');column={im.getpixel((80,y)) for y in range(im.height)}
assert all(c in column for c in colors),'Native color scale differs'
out=Image.new('RGB',(3840,2160),(36,36,36));d=ImageDraw.Draw(out);font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',42)
x,y,w,h=56,470,56,62
for i,c in enumerate(colors):d.rectangle((x,y+i*h,x+w,y+(i+1)*h),fill=c)
d.rectangle((x,y,x+w,y+10*h),outline=(255,255,255),width=2)
for i in range(11):
 value=bound*(1-i/(10 if stress else 5));value=0 if abs(value)<bound*1e-10 else value
 d.text((145,y+i*h-23),format(value,'.5g'),font=font,fill='white')
out.save(O/'legend_relabeled.png');(O/'legend_provenance.json').write_text(json.dumps({'native_source':str(src),'native_colors_verified_in_column_x':80,'colors':colors,'contour_bound':bound,'units':('Pa' if stress else 'm'),'meaning':'Fixed limits used during native frame rendering; symmetric for displacement, zero-to-bound for equivalent stress. English decimal labels replace locale-specific text and omit stale single-frame minima/maxima; model pixels are unchanged.'},indent=2))
