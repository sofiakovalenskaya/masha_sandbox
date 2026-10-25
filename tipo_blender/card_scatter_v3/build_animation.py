"""Forty equal-size cards with short outward stop-motion trajectories."""
from pathlib import Path
import hashlib, json, math
import numpy as np
from PIL import Image, ImageFilter, ImageChops

ROOT=Path(__file__).resolve().parent
ART=ROOT.parent/'card_scatter_v1/artwork'
ASSETS=ROOT.parent/'card_scatter_v1/assets'
POSES=ROOT/'poses'; FRAMES=ROOT/'frames'
for folder in (POSES,FRAMES): folder.mkdir(exist_ok=True)
W,H,FPS,SIDE=1920,1080,30,220
NPOSES,HOLD=30,3
ORIGIN=(980.,540.)
rng=np.random.default_rng(20261025)

yy,xx=np.mgrid[:H,:W]
light=1-.025*((xx-W*.4)**2/W**2+(yy-H*.32)**2/H**2)
noise=rng.normal(0,.32,(H,W))
background=Image.fromarray(np.rint(np.stack([np.clip(c*light+noise,0,255) for c in (255,208,0)],axis=2)).astype('uint8')).convert('RGBA')
background.convert('RGB').save(ROOT/'opening_background.png',compress_level=3)

def shadow(im,radius=7,opacity=.22,offset=(3,7)):
    a=im.getchannel('A').filter(ImageFilter.GaussianBlur(radius))
    s=Image.new('RGBA',im.size,(60,34,10,0));s.putalpha(a.point(lambda v:round(v*opacity)))
    out=Image.new('RGBA',im.size);out.alpha_composite(s,offset);out.alpha_composite(im)
    return out

def sprite(path,angle):
    # Every card, including the one in the hand, uses exactly this size.
    im=Image.open(path).convert('RGBA').resize((SIDE,SIDE),Image.Resampling.LANCZOS)
    out=Image.new('RGBA',(SIDE+48,SIDE+48));out.alpha_composite(im,(24,24))
    return shadow(out.rotate(angle,Image.Resampling.BICUBIC,expand=True))

def place(canvas,im,x,y):
    canvas.alpha_composite(im,(round(x-im.width/2),round(y-im.height/2)))

faces=sorted(p for p in ART.glob('*.png') if p.stem.startswith(('face_','ref_H')) and p.stem!='face_49')
rng.shuffle(faces)
sources=faces[:32]+[ART/(c+'.png') for c in ['pink','blue','green','yellow','blue','pink','green']]
rng.shuffle(sources)
positions=[]
for row in range(5):
    for col in range(8):
        if (col,row)==(4,2):continue
        x=90+col*248+rng.uniform(-40,40)
        y=80+row*230+rng.uniform(-30,30)
        radius=((x-ORIGIN[0])/960)**2+((y-ORIGIN[1])/540)**2
        positions.append((radius+rng.uniform(-.12,.12),x,y))
positions.sort()
launches=[9]*4+[11]*5+[13]*6+[15]*6+[17]*6+[19]*6+[21]*6
assert len(sources)==len(positions)==len(launches)==39
cards=[]
for i,(path,(_,x,y),launch) in enumerate(zip(sources,positions,launches)):
    angle=float(rng.uniform(-40,40))+(90 if i%13==3 else 0)
    spin=float(rng.uniform(11,21)*rng.choice([-1,1]))
    bend=float(rng.uniform(-26,26))
    cards.append({'file':path.name,'x':x,'y':y,'angle':angle,'side':SIDE,'launch_pose':launch,'spin':spin,'bend':bend})

def flight(c,pose):
    age=pose-c['launch_pose']
    if age<0:return None
    # Each new card has four distinct outward positions before settling.
    # Slight overshoot is a brief inertial slide, not scale animation.
    progress=[.74,.91,1.035,1.012,1.0][min(age,4)]
    dx,dy=c['x']-ORIGIN[0],c['y']-ORIGIN[1]
    length=max(1.,math.hypot(dx,dy))
    arc=c['bend']*math.sin(min(age,4)/4*math.pi)
    x=ORIGIN[0]+dx*progress-dy/length*arc
    y=ORIGIN[1]+dy*progress+dx/length*arc
    angle=c['angle']+c['spin']*[1.,.42,-.13,-.04,0.][min(age,4)]
    return {'x':x,'y':y,'angle':angle,'age':age,'side':SIDE}

hand=Image.open(ASSETS/'hand_releasing.png').convert('RGBA')
hand_offsets=[None,(0,800),(0,610),(0,365),(0,160),(0,45),
              (0,0),(-1,3),(1,9),(0,22),(-2,34),(0,35),
              (3,95),(9,180),(17,290),(24,420),(28,570)]
hero=sprite(ART/'face_49.png',-20)
cache={}
manifest=[];trajectory=[]
for pose in range(NPOSES):
    canvas=background.copy();states=[]
    for index,c in enumerate(cards):
        state=flight(c,pose)
        if state is None:continue
        key=(index,min(state['age'],4))
        if key not in cache:cache[key]=sprite(ART/c['file'],state['angle'])
        place(canvas,cache[key],state['x'],state['y'])
        states.append({'card':index,**state})
    visible_hand=pose<len(hand_offsets) and hand_offsets[pose] is not None
    if visible_hand:
        dx,dy=hand_offsets[pose]
        if pose<12:place(canvas,hero,980+dx,505+dy)
    if pose>=12:place(canvas,hero,*ORIGIN)
    if visible_hand:
        dx,dy=hand_offsets[pose]
        layer=Image.new('RGBA',(W,H));layer.alpha_composite(hand,(160+dx,180+dy))
        canvas.alpha_composite(shadow(layer,15,.12,(-12,13)))
    target=POSES/f'pose_{pose:02d}.png';canvas.convert('RGB').save(target,compress_level=3)
    trajectory.append({'pose':pose,'cards':states})
    for repeat in range(HOLD):
        frame=pose*HOLD+repeat;dest=FRAMES/f'frame_{frame:04d}.png'
        if dest.exists():dest.unlink()
        dest.hardlink_to(target)
        manifest.append({'frame':frame,'drawing':pose,'scatter_cards':len(states),'total_visible_cards':len(states)+(pose>0),
                         'hand':visible_hand,'all_card_sides_px':SIDE})
    print('POSE',pose,'CARDS',len(states)+(pose>0),flush=True)

coverage=Image.new('L',(W,H))
for im,x,y in [(sprite(ART/c['file'],c['angle']),c['x'],c['y']) for c in cards]+[(hero,*ORIGIN)]:
    local=Image.new('L',(W,H));local.paste(im.getchannel('A'),(round(x-im.width/2),round(y-im.height/2)))
    coverage=ImageChops.lighter(coverage,local)
table_fraction=float(np.mean(np.asarray(coverage)<128))
assert table_fraction>.18,table_fraction
report={'width':W,'height':H,'fps':FPS,'frames':NPOSES*HOLD,'duration':NPOSES*HOLD/FPS,
        'drawings':NPOSES,'hold_frames':HOLD,'final_cards':40,'uniform_card_side_px':SIDE,
        'motion':'short radial flights with turning, outward overshoot and settling; held drawings',
        'visible_table_fraction':table_fraction,
        'source_artwork_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(ART.glob('*.png'))},
        'hero':{'file':'face_49.png','side':SIDE,'x':ORIGIN[0],'y':ORIGIN[1],'angle':-20},
        'cards':cards,'frame_map':manifest,'trajectories':trajectory}
(ROOT/'animation_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print('COMPLETE',NPOSES*HOLD,'FRAMES; VISIBLE TABLE',table_fraction,flush=True)
