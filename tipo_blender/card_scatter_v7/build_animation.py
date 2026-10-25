"""Append a held-drawing hand sweep, leaving one centred black-backed card."""
from pathlib import Path
import json,math,hashlib,subprocess,sys
import numpy as np
from PIL import Image,ImageFilter

ROOT=Path(__file__).resolve().parent
BASE=ROOT.parent/'card_scatter_v6'
ART=ROOT.parent/'card_scatter_v1/artwork'
ASSETS=ROOT/'assets';FRAMES=ROOT/'frames';POSES=ROOT/'poses'
for p in (FRAMES,POSES):p.mkdir(exist_ok=True)
W,H,FPS,SIDE=1920,1080,30,320
if not (BASE/'frames/frame_0080.png').exists():
    subprocess.run([sys.executable,str(BASE/'build_animation.py')],check=True)
data=json.loads((BASE/'animation_manifest.json').read_text())
background=Image.open(BASE/'opening_background.png').convert('RGBA')

def shadow(im,radius=7,opacity=.22,offset=(3,7)):
    alpha=im.getchannel('A').filter(ImageFilter.GaussianBlur(radius))
    sh=Image.new('RGBA',im.size,(60,34,10,0));sh.putalpha(alpha.point(lambda a:round(a*opacity)))
    out=Image.new('RGBA',im.size);out.alpha_composite(sh,offset);out.alpha_composite(im)
    return out

textures={}
def card(file,angle,projected_width=SIDE):
    path=Path(file)
    if path not in textures:
        im=Image.open(path).convert('RGBA')
        if path.name=='black_back.png':
            bbox=im.getchannel('A').point(lambda a:255 if a>127 else 0).getbbox();im=im.crop(bbox)
        textures[path]=im.resize((SIDE,SIDE),Image.Resampling.LANCZOS)
    im=textures[path]
    if projected_width!=SIDE:im=im.resize((projected_width,SIDE),Image.Resampling.LANCZOS)
    out=Image.new('RGBA',(im.width+48,im.height+48));out.alpha_composite(im,(24,24))
    return shadow(out.rotate(angle,Image.Resampling.BICUBIC,expand=True))

def place(canvas,im,x,y):
    canvas.alpha_composite(im,(round(x-im.width/2),round(y-im.height/2)))

def link(target,source):
    if target.exists():target.unlink()
    target.hardlink_to(source)

cards=data['cards']
rest=[card(ART/c['file'],c['angle']) for c in cards]
face=card(ART/'face_49.png',-20)
back=card(ASSETS/'black_back.png',0)
baseline=background.copy()
for c,im in zip(cards,rest):place(baseline,im,c['x'],c['y'])
place(baseline,face,960,502)
assert np.array_equal(np.asarray(baseline.convert('RGB')),np.asarray(Image.open(BASE/'frames/frame_0080.png'))),'Original layout seam changed'

hand=Image.open(ASSETS/'sweep_hand.png').convert('RGBA')
if hand.height!=941:hand=hand.resize((round(hand.width*941/hand.height),941),Image.Resampling.LANCZOS)
hb=hand.getchannel('A').point(lambda a:255 if a>24 else 0).getbbox()
tip_anchor=hb[0]
base_y=max(180,H+40-hb[3])
palm_offset=hand.width*.58-tip_anchor

def hand_layer(tip_x,dy=0):
    layer=Image.new('RGBA',(W,H));layer.alpha_composite(hand,(round(tip_x-tip_anchor),round(base_y+dy)))
    return shadow(layer,15,.12,(-12,13)),layer.getchannel('A').getbbox()

right_edges=[c['x']+SIDE/2*(abs(math.cos(math.radians(c['angle'])))+abs(math.sin(math.radians(c['angle'])))) for c in cards]
start=min(max(right_edges)+40,W+220)
fronts=[]
for i in range(12):
    u=i/11;e=u*u*(3-2*u)
    fronts.append(start+(-1250-start)*e)
tips=[front-300 for front in fronts]
flip_index=min(range(12),key=lambda i:abs(tips[i]+palm_offset-960))
assert 2<=flip_index<=8

frame=0;mapping=[];poses=[]
for i in range(81):
    link(FRAMES/f'frame_{frame:04d}.png',BASE/'frames'/f'frame_{i:04d}.png')
    mapping.append({'frame':frame,'phase':'approved_scatter','source_frame':i});frame+=1
for repeat in range(6):
    link(FRAMES/f'frame_{frame:04d}.png',BASE/'frames/frame_0080.png')
    mapping.append({'frame':frame,'phase':'layout_hold'});frame+=1

def emit(name,canvas,info,hold=3):
    global frame
    path=POSES/(name+'.png');canvas.convert('RGB').save(path,compress_level=3)
    poses.append({'file':name+'.png',**info})
    for repeat in range(hold):
        link(FRAMES/f'frame_{frame:04d}.png',path)
        mapping.append({'frame':frame,'phase':info['phase'],'pose':name});frame+=1

for i,dy in enumerate([650,400,160,0]):
    canvas=baseline.copy();layer,bbox=hand_layer(tips[0],dy)
    canvas.alpha_composite(layer)
    emit(f'return_{i:02d}',canvas,{'phase':'hand_return','hand_tip_x':tips[0],'hand_vertical_offset':dy,'hand_bbox':bbox,'visible_moving_cards':39,'hero_side':'face'})

motion=[]
for step,(front,tip) in enumerate(zip(fronts,tips)):
    canvas=background.copy();states=[];visible=0
    for i,(c,right) in enumerate(zip(cards,right_edges)):
        dx=min(0.,front-right)
        moving=dx<0
        progress=min(1.,-dx/600)
        # Overlapping cards collect into a loose stack in front of the hand.
        x=c['x']+dx-((i%5)*9*progress)
        y=c['y']+(540-c['y'])*.16*progress+((i%7)-3)*3*progress
        angle=c['angle']+((i%7)-3)*2.2*progress
        im=card(ART/c['file'],angle)
        if x+im.width/2>0 and x-im.width/2<W and y+im.height/2>0 and y-im.height/2<H:visible+=1
        place(canvas,im,x,y)
        states.append({'card':i,'x':x,'y':y,'angle':angle,'moving':moving,'physical_side':SIDE})
    relative=step-flip_index
    if relative<-1:
        hero_file=ART/'face_49.png';width=SIDE;angle=-20;hy=502;hero_side='face'
    elif relative==-1:
        hero_file=ART/'face_49.png';width=210;angle=-12;hy=515;hero_side='face'
    elif relative==0:
        hero_file=ART/'face_49.png';width=18;angle=-5;hy=532;hero_side='edge'
    elif relative==1:
        hero_file=ASSETS/'black_back.png';width=210;angle=0;hy=540;hero_side='black_back'
    else:
        hero_file=ASSETS/'black_back.png';width=SIDE;angle=0;hy=540;hero_side='black_back'
    place(canvas,card(hero_file,angle,width),960,hy)
    layer,bbox=hand_layer(tip);canvas.alpha_composite(layer)
    emit(f'sweep_{step:02d}',canvas,{'phase':'sweep_left','hand_tip_x':tip,'pressure_front_x':front,'hand_bbox':bbox,
                                  'visible_moving_cards':visible,'hero_side':hero_side,'hero_center':[960,hy],
                                  'hero_projected_width':width,'hero_physical_side':SIDE})
    motion.append({'step':step,'cards':states})

final=background.copy();place(final,back,960,540)
assert visible==0 and bbox is None,'Sweep did not fully clear the hand and other cards'
emit('one_black_card',final,{'phase':'final_one_card','visible_moving_cards':0,'hand_bbox':None,
                           'hero_side':'black_back','hero_center':[960,540],'hero_physical_side':SIDE},hold=18)
assert frame==153,frame
report={'width':W,'height':H,'fps':FPS,'frames':frame,'duration_seconds':frame/FPS,
        'preserved_original_frames':81,'hold_frames':3,'starting_cards':40,'final_visible_cards':1,
        'uniform_physical_card_side_px':SIDE,'final_card_center':[960,540],'final_card_angle':0,
        'final_card_back_color':'black','final_hold_frames':18,'flip_occlusion_step':flip_index,
        'sweep_direction':'left','hand_appearance':'same woman, flat palm-down sweeping pose',
        'asset_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(ASSETS.glob('*.png'))},
        'poses':poses,'card_motion':motion,'frame_map':mapping}
(ROOT/'animation_manifest.json').write_text(json.dumps(report,indent=2))
final.convert('RGB').save(ROOT/'final_one_black_card.png',compress_level=3)
print('COMPLETE',frame,'FRAMES; FLIP STEP',flip_index,'FINAL ONE CARD',flush=True)
