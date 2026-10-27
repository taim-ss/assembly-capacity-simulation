"""Static storyboard projected from canonical ALP geometry; never a native capture."""
from pathlib import Path
import math
import re
import xml.etree.ElementTree as ET
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon,Rectangle,FancyBboxPatch
import matplotlib.colors as colors

ROOT=Path(__file__).resolve().parents[1]
NAVY='#17324d';MUTED='#526476';BG='#f4f7fb'
LABELS=[('INCOMING PARTS','PCB + probe + housing'),('1  KIT PARTS','Prepare complete kits'),
        ('2  ASSEMBLE','Connect and enclose'),('3  TEST','Check electrical function'),
        ('4  QUALITY','Inspect and approve'),('5  PACK','Protect and label'),('READY TO SHIP','Completed orders')]
KEYS=['dock','kitting','assembly','test','quality','handover','ship']
CAPS=dict(zip(KEYS[1:6],[2,5,5,3,1]))


def project(x,y,z):
    return x+.34*y,.40*y-.92*z


def tint(color,multiplier):
    return tuple(min(1,c*multiplier) for c in colors.to_rgb(color))


def fill(shape):
    value=int(shape.findtext('FillColor','-657931'))&0xffffffff
    return '#'+format(value&0xffffff,'06x')


def number(shape,name,default=0):
    return float(shape.findtext(name,str(default)))


def faces(shape,offset=(0,0,0),override=None):
    x=number(shape,'X')+offset[0];y=number(shape,'Y')+offset[1]
    z=number(shape,'Z')+offset[2];h=number(shape,'ZHeight')
    color=override or fill(shape)
    if shape.tag=='Rectangle':
        w=number(shape,'Width');d=number(shape,'Height')
        outline=[(x,y),(x+w,y),(x+w,y+d),(x,y+d)]
    elif shape.tag=='Oval':
        rx=number(shape,'RadiusX');ry=number(shape,'RadiusY')
        outline=[(x+rx*math.cos(t*math.tau/16),y+ry*math.sin(t*math.tau/16)) for t in range(16)]
    else:return []
    result=[]
    for a,b in zip(outline,outline[1:]+outline[:1]):
        verts=[(*a,z),(*b,z),(*b,z+h),(*a,z+h)]
        shade=.74 if a[0]==b[0] else .88
        result.append((sum(v[1] for v in verts)/4-.012*z,
                       [project(*v) for v in verts],tint(color,shade)))
    result.append((y+1-.012*z,[project(a,b,z+h) for a,b in outline],color))
    return result


def render_world(ax,main,job):
    surfaces=[]
    for shape in main:
        if shape.findtext('DrawMode')!='SHAPE_DRAW_3D':continue
        name=shape.findtext('Name','')
        marker=re.fullmatch(r'a3d_unit_(\w+)_(\d+)',name)
        if marker and int(marker[2])>=CAPS[marker[1]]:continue
        surfaces.extend(faces(shape,override='#97a4b1' if marker else None))
    # Illustrative products use the canonical Job geometry; these are not recorded states.
    states=[(0,380,210,'#577590'),(1,600,285,'#43aa8b'),
            (2,730,470,'#e63946'),(3,1040,285,'#43aa8b'),(4,1260,285,None),(4,1480,285,None)]
    for phase,x,y,state in states:
        for shape in job:
            name=shape.findtext('Name','')
            visible=(name=='a3d_box' or
                     name=='a3d_product_pcb' and phase<4 or
                     name.startswith('a3d_product_chip_') and phase==0 or
                     name in ['a3d_product_housing','a3d_product_sensing_tip'] and 1<=phase<4 or
                     name=='a3d_product_qa_seal' and phase==3 or
                     name in ['a3d_product_carton','a3d_product_carton_label'] and phase>=4)
            if not visible:continue
            offsets=[]
            for key in ['XCode','YCode','ZCode']:
                match=re.search(r'\+\((-?[\d.]+)\)',shape.findtext(key,''))
                offsets.append(float(match[1]) if match else 0)
            local=ET.fromstring(ET.tostring(shape))
            for key,value in zip(['X','Y','Z'],[x+offsets[0],y+offsets[1],82+offsets[2]]):
                local.find(key).text=str(value)
            surfaces.extend(faces(local,override=state if name=='a3d_box' else None))
    for depth,vertices,color in sorted(surfaces,key=lambda v:v[0]):
        ax.add_patch(Polygon(vertices,facecolor=color,edgecolor=tint(color,.68),linewidth=.35))
    for left,right in zip(range(160,1480,220),range(380,1700,220)):
        ax.annotate('',project(right-75,300,82),project(left+75,300,82),
                    arrowprops=dict(arrowstyle='-|>',lw=2.6,color='#456780'))
    path=[project(820,355,5),project(820,470,5),project(600,470,5),project(600,355,5)]
    ax.plot(*zip(*path),color='#d94853',lw=2,ls='--')
    ax.annotate('',path[-1],path[-2],arrowprops=dict(arrowstyle='-|>',color='#d94853',lw=2))
    ax.text(*project(710,535,0),'Failed test → repair → retest',ha='center',fontsize=11,color='#c13943',weight='bold')
    for i,(heading,detail) in enumerate(LABELS):
        x=160+220*i
        px,py=project(x,620,0)
        ax.text(px,py,heading,ha='center',fontsize=12,color=NAVY,weight='bold')
        ax.text(px,py+19,detail,ha='center',fontsize=10,color=MUTED)
    ax.set(xlim=(0,1900),ylim=(310,-65));ax.axis('off')


def rounded(ax,x,y,w,h,text,face='#ffffff',edge='#d5dfe9',size=12):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=.015,rounding_size=.04',
                 linewidth=1,facecolor=face,edgecolor=edge))
    ax.text(x+w/2,y+h/2,text,ha='center',va='center',fontsize=size,color=NAVY,weight='bold')


def storyboard(ax):
    ax.set(xlim=(0,16.4),ylim=(3.2,0));ax.axis('off')
    ax.text(0,0,'PROCESS LOGIC — its own editor area, separate from the 3D scene',fontsize=16,color=NAVY,weight='bold')
    ax.text(0,.32,'Simplified finite-production route; arrows show actual process order and the Test-to-Assembly return.',fontsize=11,color=MUTED)
    titles=['Order\narrival','Combine:\nprepare kit','Assembly','Functional\ntest','Quality\ninspection','Packing','Completed\norder']
    xpos=[.1,2.3,4.5,6.7,8.9,11.1,13.3]
    for i,(x,title) in enumerate(zip(xpos,titles)):
        face='#e8f0fa' if i==2 else '#fff0df' if i==3 else '#ffffff'
        rounded(ax,x,1,1.85,.65,title,face=face)
        if i<6:ax.annotate('',(xpos[i+1]-.06,1.325),(x+1.9,1.325),arrowprops=dict(arrowstyle='-|>',lw=1.8,color='#496b85'))
    rounded(ax,2.3,.48,1.85,.38,'Parts supply',face='#edf3f8',size=10)
    ax.annotate('',(3.225,.98),(3.225,.88),arrowprops=dict(arrowstyle='-|>',color='#496b85'))
    ax.plot([7.625,7.625,5.425,5.425],[1.67,2.1,2.1,1.67],color='#d94853',lw=2)
    ax.annotate('',(5.425,1.67),(5.425,1.93),arrowprops=dict(arrowstyle='-|>',color='#d94853',lw=2))
    ax.text(6.525,2.35,'FAIL: repair, then test again',ha='center',color='#c13943',fontsize=11,weight='bold')
    ax.text(0,2.93,'Compare the SAME job inputs: BASELINE  •  ASSEMBLY +1  •  TEST +1',fontsize=14,color=NAVY,weight='bold')


def main():
    root=ET.parse(ROOT/'model/P3_Assembly_Flow.alp').getroot()
    main=root.find(".//ActiveObjectClass[Name='Main']/Presentation/Level/Presentation")
    job=root.find(".//ActiveObjectClass[Name='Job']/Presentation/Level/Presentation")
    fig=plt.figure(figsize=(24,14.5),facecolor=BG)
    fig.text(.04,.965,'P3  |  A small temperature-sensor factory',fontsize=28,color=NAVY,weight='bold')
    fig.text(.04,.932,'STATIC DESIGN PREVIEW — not an AnyLogic capture',fontsize=16,color='#b44d20',weight='bold')
    fig.text(.04,.902,'Question: does one extra Assembly unit or one extra Test unit reduce waiting and completion time more?',fontsize=16,color=MUTED)
    fig.text(.04,.86,'3D PRODUCTION SCENE',fontsize=16,color=NAVY,weight='bold')
    ax=fig.add_axes([.025,.48,.95,.35],facecolor=BG);render_world(ax,main,job)
    fig.text(.04,.463,'Illustrative product states:',fontsize=12,color=NAVY,weight='bold')
    fig.text(.17,.463,'parts on a BLUE tray  →  assembled sensor  →  approved module  →  packed carton',fontsize=12,color=MUTED)
    fig.text(.04,.433,'GREEN = receiving service     RED = rework     GREY lights = idle resources     These are design examples, not runtime counts.',fontsize=12,color=MUTED)
    fig.add_artist(plt.Line2D([.04,.96],[.402,.402],transform=fig.transFigure,color='#cbd7e4',lw=1.5))
    bottom=fig.add_axes([.04,.065,.92,.29]);storyboard(bottom)
    fig.text(.04,.025,'SYNTHETIC educational model | Tier B agent-produced | Factory geometry is illustrative; capacities and processing times are assumptions.',fontsize=11,color=MUTED)
    target=ROOT/'docs/3d-layout-plan.png';fig.savefig(target,dpi=120,facecolor=BG);plt.close(fig)
    from PIL import Image
    with Image.open(target) as image:print(f'{target}: {image.width}x{image.height}')


if __name__=='__main__':main()
