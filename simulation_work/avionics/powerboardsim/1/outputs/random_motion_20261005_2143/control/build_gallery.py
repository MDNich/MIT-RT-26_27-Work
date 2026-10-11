from pathlib import Path
import json,html
T=Path(__file__).resolve().parents[1];D=T.parents[1]/'output/videos/power_board_random_motion_4k60'
cards=[]
for meta in sorted((T/'videos').glob('*/ENCODED.json')):
 o=meta.parent;m=json.loads((o/'manifest.json').read_text());p=D/(o.name+'.mp4')
 if not p.exists():continue
 label=(f"Base {m['base']} · Dynamic von Mises stress · PCB (unaveraged)" if m.get('kind')=='stress' else f"Base {m['base']} · {m['response']} displacement · {m['view_label']}")
 cards.append(f'<article><h2>{html.escape(label)}</h2><video controls preload="metadata" poster="{p.stem}.jpg" src="{p.name}"></video><p><a href="{p.name}" download>Download MP4</a> · 3840 × 2160 · 60 fps · 8 seconds</p></article>')
s='''<!DOCTYPE html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Power-board vibration motion</title><style>body{max-width:1200px;margin:40px auto;padding:0 24px;background:#121923;color:#edf3ff;font:18px/1.6 system-ui}h1{line-height:1.15}h2{font-size:22px}p{color:#c5d1e0}a{color:#8cceff}article{border-top:1px solid #394655;margin:40px 0;padding-top:12px}video{width:100%;background:#242424;border-radius:10px}small{color:#aab6c8}</style><h1>Power-board vibration motion</h1><p>Representative random vibration from new seeded time-history calculations. The camera stays fixed while the solved assembly deforms. Displacement contours are instantaneous and signed. The stress view shows instantaneous unaveraged von Mises stress from the dynamic tensor, excluding static clamp stress. These differ from the statistical RMS figures in the report.</p><p>Six bolts at 750 N each; 2% modal damping. X, Y and Z are separate excitation cases. Motion is magnified 50× and playback is slowed 273.07×. Each clip shows 480 solved states from 1.000061 to 1.029297 seconds after startup.</p><p><small>Exploratory linearized response about the preload state. Existing material, mesh, contact and modal-truncation limitations apply. The synthetic record is one representative realization, not a measured flight response.</small></p>'''+''.join(cards)+f'<p>{len(cards)} accepted motion video(s) currently available. {('All planned motion views are complete.' if len(cards)==7 else 'Additional views are being prepared.')}</p></html>'
(D/'index.html').write_text(s)
print(D/'index.html')
