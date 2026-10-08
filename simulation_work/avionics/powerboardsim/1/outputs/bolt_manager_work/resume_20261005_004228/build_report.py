from pathlib import Path
import json,csv
from xml.sax.saxutils import escape
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,Image,PageBreak,KeepTogether
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
R=Path(__file__).resolve().parent
C=json.loads((R/'report_content.json').read_text())
O=R.parents[2]/'output/pdf';O.mkdir(parents=True,exist_ok=True)
P=O/'power_board_modal_comparison.pdf'
styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='TitleCustom',fontName='Helvetica-Bold',fontSize=23,leading=27,textColor=colors.HexColor('#122B42'),spaceAfter=12))
styles.add(ParagraphStyle(name='SubCustom',fontName='Helvetica-Bold',fontSize=13,leading=17,textColor=colors.HexColor('#126B79'),spaceBefore=12,spaceAfter=7))
styles.add(ParagraphStyle(name='TextCustom',fontName='Helvetica',fontSize=9,leading=12,spaceAfter=7))
styles.add(ParagraphStyle(name='SmallCustom',fontName='Helvetica',fontSize=7.5,leading=10,spaceAfter=5,textColor=colors.HexColor('#435567')))
story=[]
def para(s,style='TextCustom'):
 return Paragraph(escape(s),styles[style])
def add(s,style='TextCustom'):story.append(para(s,style))
def table(data,widths):
 t=Table([[para(str(c),'SmallCustom') for c in row] for row in data],colWidths=widths,repeatRows=1,hAlign='LEFT')
 t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#E5EFF3')),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,0),.7,colors.HexColor('#126B79')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F5F8FA')]),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),2)]));story.append(t)
def figure(path,caption,width=460):
 from PIL import Image as PI
 with PI.open(path) as im:w,h=im.size
 story.append(Image(str(path),width=width,height=width*h/w));add(caption,'SmallCustom')
def header(canvas,doc):
 canvas.saveState();canvas.setStrokeColor(colors.HexColor('#D6E1E7'));canvas.line(42,37,553,37)
 canvas.setFont('Helvetica',7);canvas.setFillColor(colors.HexColor('#556675'));canvas.drawString(42,25,'MIT Rocket Team | Power board modal study | 4 October 2026');canvas.drawRightString(553,25,str(doc.page));canvas.restoreState()
add('Power board\nNatural-frequency comparison','TitleCustom')
add('20 undamped modes above 1 Hz | Six fasteners at 750 N each','SubCustom')
for s in C['summary']:add(s)
add('Frequency results','SubCustom')
data=[C['frequency_headers']]+C['frequency_rows'];table(data,C['frequency_widths'])
add(C['frequency_note'],'SmallCustom')
story.append(PageBreak());add('Default-contact deformation','TitleCustom')
for f in C['default_figures']:figure(R/f['path'],f['caption'])
add('Mode-shape amplitudes are mass-normalized eigenvectors. Their displayed metre values and automatic scale factors are not physical displacement predictions. No excitation level was specified.','SmallCustom')
story.append(PageBreak());add('750 N bolt configuration','TitleCustom')
for s in C['bolt_summary']:add(s)
for f in C.get('bolt_figures',[]):figure(R/f['path'],f['caption'])
if C.get('bolt_rows'):table([['Bolt location','Applied preload (N)','Locked reaction (N)']]+C['bolt_rows'],[210,135,140])
story.append(PageBreak());add('Model, checks and limitations','TitleCustom')
for title,paras in C['method_sections']:
 add(title,'SubCustom')
 for s in paras:add(s)
add('Evidence and references','SubCustom')
for s in C['evidence']:add(s,'SmallCustom')
for label,url in C['references']:
 story.append(Paragraph('<link href="'+escape(url,{'"':'&quot;'})+'" color="#126B79">'+escape(label)+'</link>',styles['SmallCustom']))
SimpleDocTemplate(str(P),pagesize=A4,rightMargin=42,leftMargin=42,topMargin=40,bottomMargin=48,title='Power board natural-frequency comparison',author='MIT Rocket Team - simulation study').build(story,onFirstPage=header,onLaterPages=header)
print(P)
