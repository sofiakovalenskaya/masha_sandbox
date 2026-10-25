"""Card collage grows around a hand, using held stop-motion drawings."""
from pathlib import Path
import json, hashlib, math
import numpy as np
from PIL import Image, ImageFilter, ImageChops

ROOT = Path(__file__).resolve().parent
ART = ROOT.parent / 'card_scatter_v1' / 'artwork'
ASSETS = ROOT.parent / 'card_scatter_v1' / 'assets'
SWEEP_ASSETS = ROOT.parent / 'card_scatter_v7' / 'assets'
POSES = ROOT / 'poses'
FRAMES = ROOT / 'frames'
for folder in (POSES, FRAMES):
    folder.mkdir(exist_ok=True)
W, H, FPS = 1920, 1080, 30
CARD_SIDE = 320
rng = np.random.default_rng(20261025)

# Brand-pink tabletop with the same restrained photographic grain.
yy, xx = np.mgrid[:H, :W]
light = 1.0 - .025 * ((xx-W*.40)**2/W**2 + (yy-H*.32)**2/H**2)
noise = rng.normal(0, .32, (H, W))
base = np.stack([np.clip(c*light+noise, 0, 255) for c in (255,0,111)], axis=2)
background = Image.fromarray(np.rint(base).astype('uint8')).convert('RGBA')

def drop_shadow(im, radius=7, opacity=.22, offset=(3,7)):
    alpha = im.getchannel('A').filter(ImageFilter.GaussianBlur(radius))
    shadow = Image.new('RGBA', im.size, (60,34,10,0))
    shadow.putalpha(alpha.point(lambda a: round(a*opacity)))
    combined = Image.new('RGBA', im.size)
    combined.alpha_composite(shadow, offset)
    combined.alpha_composite(im)
    return combined

def card_sprite(path, side, angle, with_shadow=True):
    im = Image.open(path).convert('RGBA').resize((side, side), Image.Resampling.LANCZOS)
    padded = Image.new('RGBA', (side+48,side+48))
    padded.alpha_composite(im, (24,24))
    padded = padded.rotate(angle, Image.Resampling.BICUBIC, expand=True)
    return drop_shadow(padded) if with_shadow else padded

def place(canvas, sprite, x, y):
    canvas.alpha_composite(sprite, (round(x-sprite.width/2), round(y-sprite.height/2)))

faces = sorted(p for p in ART.glob('*.png') if p.stem.startswith(('face_', 'ref_H')) and p.stem != 'face_49')
backs = [ART / (color+'.png') for color in ['pink','blue','green','yellow','blue','pink','green','yellow','pink']]
sources = faces + backs
assert len(sources)==59, len(sources)
rng.shuffle(sources)
positions=[]
for row in range(6):
    for col in range(10):
        if (col,row)==(4,2):
            continue
        x=-35+col*222+rng.uniform(-55,55)
        y=-35+row*229+rng.uniform(-48,48)
        radius=((x-W/2)/(W/2))**2+((y-H/2)/(H/2))**2
        positions.append((radius+rng.uniform(-.12,.12),x,y))
positions.sort()
cards=[]
for i,(path,(_,x,y)) in enumerate(zip(sources,positions)):
    rng.integers(292,350)  # Preserve the approved sequence of random angles.
    side=CARD_SIDE
    angle=float(rng.uniform(-38,38))
    if i%13==3:
        angle+=90
    cards.append({'file':path.name,'x':x,'y':y,'side':side,'angle':angle,
                  'sprite':card_sprite(path,side,angle),
                  'arriving':card_sprite(path,side,angle+float(rng.choice([-1,1]))*1.7)})

releasing=Image.open(ASSETS/'hand_releasing.png').convert('RGBA')
hero=card_sprite(ART/'face_49.png',CARD_SIDE,-20)
held_card=card_sprite(ART/'face_49.png',CARD_SIDE,-20,with_shadow=False)
retained_card=card_sprite(ROOT/'assets/rules_front.png',CARD_SIDE,0)
# Replace the first dealt card with the retained card. It remains at this
# exact transform, underneath the other cards, from its first appearance.
cards[0].update({'file':'rules_front.png','x':960,'y':540,'side':CARD_SIDE,'angle':0,
                 'sprite':retained_card,'arriving':retained_card})

def hand_layer(dx,dy,holding_card):
    layer=Image.new('RGBA',(W,H))
    if holding_card:
        # The same exact-size artwork is placed under the thumb. At the
        # final held pose it reaches the existing table-card position.
        place(layer,held_card,960+dx,468+dy)
    layer.alpha_composite(releasing,(160+dx,180+dy))
    return layer

# 18 separate drawings, held for three output frames each. No tweening.
counts=[0,0,0,0,0,3,8,15,25,36,45,54,59,59,59,59,59,59]
counts=[min(count,39) for count in counts]
hand_offsets=[(0,0),(-2,2),(1,1),(-1,4),(2,9),(0,22),(-2,34),
              (0,35),(3,95),(9,210),(17,355),(28,540)]
manifest=[]
coverage=Image.new('L',(W,H))
background.convert('RGB').save(ROOT/'opening_background.png',compress_level=3)
# Prepend an empty opening and a gently eased entrance. The approved
# original 54-frame animation follows in full, with its original timing.
intro_offsets=[None,None,860,802,645,430,215,58,0]
prefix_frames=len(intro_offsets)*3
for drawing,dy in enumerate(intro_offsets):
    canvas=background.copy()
    if dy is not None:
        hand_canvas=hand_layer(0,dy,True)
        canvas.alpha_composite(drop_shadow(hand_canvas,radius=15,opacity=.12,offset=(-12,13)))
    target=POSES/f'intro_{drawing:02}.png'
    canvas.convert('RGB').save(target,compress_level=3)
    for repeat in range(3):
        frame=drawing*3+repeat
        dest=FRAMES/f'frame_{frame:04d}.png'
        if dest.exists():dest.unlink()
        dest.hardlink_to(target)
        manifest.append({'frame':frame,'drawing':f'intro_{drawing:02}',
                         'phase':'entrance','table_cards':0,'hand_layer':dy is not None,
                         'vertical_offset':dy})
for pose,count in enumerate(counts):
    canvas=background.copy()
    previous=counts[pose-1] if pose else 0
    for index,c in enumerate(cards[:count]):
        sprite=c['arriving'] if index>=previous and count!=previous else c['sprite']
        place(canvas,sprite,c['x'],c['y'])
    if pose>=7:
        place(canvas,hero,960,502)
    if pose<len(hand_offsets):
        dx,dy=hand_offsets[pose]
        # Wrist remains below the lower edge while holding the card.
        hand_canvas=hand_layer(dx,dy,pose<7)
        canvas.alpha_composite(drop_shadow(hand_canvas,radius=15,opacity=.12,offset=(-12,13)))
    target=POSES/f'pose_{pose:02d}.png'
    canvas.convert('RGB').save(target,compress_level=3)
    for repeat in range(3):
        frame=prefix_frames+pose*3+repeat
        dest=FRAMES/f'frame_{frame:04d}.png'
        if dest.exists():
            dest.unlink()
        dest.hardlink_to(target)
        manifest.append({'frame':frame,'drawing':f'pose_{pose:02}',
                         'phase':'original','base_frame':pose*3+repeat,
                         'table_cards':count+(pose>=7),'hand':pose<len(hand_offsets)})
    print('POSE',pose,'CARDS',count,'HAND',pose<len(hand_offsets),flush=True)

baseline=Image.open(FRAMES/'frame_0080.png').convert('RGBA')
tail_frame=81;tail_poses=[];motion=[]
for repeat in range(6):
    dest=FRAMES/f'frame_{tail_frame:04d}.png'
    if dest.exists():dest.unlink()
    dest.hardlink_to(FRAMES/'frame_0080.png')
    manifest.append({'frame':tail_frame,'phase':'layout_hold'});tail_frame+=1

def emit_tail(name,canvas,info,hold=3):
    global tail_frame
    path=POSES/(name+'.png');canvas.convert('RGB').save(path,compress_level=3)
    tail_poses.append({'file':name+'.png','static_card_center':[960,540],
                       'static_card_size':[CARD_SIDE,CARD_SIDE],'static_card_angle':0,**info})
    for repeat in range(hold):
        dest=FRAMES/f'frame_{tail_frame:04d}.png'
        if dest.exists():dest.unlink()
        dest.hardlink_to(path)
        manifest.append({'frame':tail_frame,'phase':info['phase'],'pose':name});tail_frame+=1

# The original held card now leaves with the other 38 face cards. The
# retained rules card stays underneath; it is never flipped/scaled.
moving=[{**{k:v for k,v in c.items() if k not in ('sprite','arriving')},'sweep_id':i} for i,c in enumerate(cards[1:39],1)]
moving.append({'file':'face_49.png','x':960,'y':502,'angle':-20,'side':CARD_SIDE,'sweep_id':39})
assert len(moving)==39
hand=Image.open(SWEEP_ASSETS/'sweep_hand.png').convert('RGBA')
if hand.height!=941:hand=hand.resize((round(hand.width*941/hand.height),941),Image.Resampling.LANCZOS)
hb=hand.getchannel('A').point(lambda a:255 if a>24 else 0).getbbox()
anchor=hb[0];base_y=max(180,H+40-hb[3])

def sweep_hand(tip,dy=0):
    layer=Image.new('RGBA',(W,H));layer.alpha_composite(hand,(round(tip-anchor),round(base_y+dy)))
    return drop_shadow(layer,15,.12,(-12,13)),layer.getchannel('A').getbbox()

edges=[c['x']+CARD_SIDE/2*(abs(math.cos(math.radians(c['angle'])))+abs(math.sin(math.radians(c['angle'])))) for c in moving]
start=min(max(edges)+40,W+220)
fronts=[start+(-1250-start)*(u*u*(3-2*u)) for u in [i/11 for i in range(12)]]
tips=[x-300 for x in fronts]
for i,dy in enumerate([650,400,160,0]):
    canvas=baseline.copy();layer,bbox=sweep_hand(tips[0],dy);canvas.alpha_composite(layer)
    emit_tail(f'return_{i:02d}',canvas,{'phase':'hand_return','hand_bbox':bbox,'visible_moving_cards':39})

for step,(front,tip) in enumerate(zip(fronts,tips)):
    canvas=background.copy();place(canvas,retained_card,960,540)
    states=[];visible=0
    for c,right in zip(moving,edges):
        i=c['sweep_id'];dx=min(0.,front-right);progress=min(1.,-dx/600)
        x=c['x']+dx-(i%5)*9*progress
        y=c['y']+(540-c['y'])*.16*progress+((i%7)-3)*3*progress
        angle=c['angle']+((i%7)-3)*2.2*progress
        im=card_sprite(ART/c['file'],CARD_SIDE,angle)
        if x+im.width/2>0 and x-im.width/2<W and y+im.height/2>0 and y-im.height/2<H:visible+=1
        place(canvas,im,x,y)
        states.append({'card_id':i,'x':x,'y':y,'angle':angle,'side':CARD_SIDE})
    layer,bbox=sweep_hand(tip);canvas.alpha_composite(layer)
    emit_tail(f'sweep_{step:02d}',canvas,{'phase':'sweep_left','hand_bbox':bbox,'visible_moving_cards':visible})
    motion.append({'step':step,'cards':states})
final=background.copy();place(final,retained_card,960,540)
assert visible==0 and bbox is None
emit_tail('one_static_rules_card',final,{'phase':'final_one_card','hand_bbox':None,'visible_moving_cards':0},hold=18)
final.convert('RGB').save(ROOT/'final_one_rules_card.png',compress_level=3)
assert tail_frame==153

for f in manifest:
    exists=f['frame']>=42
    f['static_rules_card_layer']=exists
    if exists:f.update({'static_card_center':[960,540],'static_card_size':[CARD_SIDE,CARD_SIDE],'static_card_angle':0})
clean_cards=[{k:v for k,v in c.items() if k not in ('sprite','arriving')} for c in cards[:39]]
report={'width':W,'height':H,'fps':FPS,'frames':tail_frame,'duration':tail_frame/FPS,
        'hold_frames':3,'starting_cards':40,'final_visible_cards':1,
        'based_on':'card_scatter_v8',
        'changes':'only replace the retained black back texture with the original rules front',
        'uniform_card_side_px':CARD_SIDE,'hero_side_px':CARD_SIDE,'held_card_side_px':CARD_SIDE,
        'arrival_scale':1,'static_rules_card_center':[960,540],'static_rules_card_size':[CARD_SIDE,CARD_SIDE],
        'static_rules_card_angle':0,'rules_card_first_frame':42,'rules_card_flips':False,'rules_card_resizes':False,
        'background_color':'#FF006F','prefix_frames':prefix_frames,
        'intro_vertical_offsets':intro_offsets,
        'source_artwork_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(ART.glob('*.png'))},
        'rules_card_asset_sha256':hashlib.sha256((ROOT/'assets/rules_front.png').read_bytes()).hexdigest(),
        'cards':clean_cards,'card_motion':motion,'tail_poses':tail_poses,'frame_map':manifest}
(ROOT/'animation_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print('COMPLETE',tail_frame,'FRAMES; STATIC RULES FRONT 320x320',flush=True)
