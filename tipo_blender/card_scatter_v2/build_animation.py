"""Card collage grows around a hand, using held stop-motion drawings."""
from pathlib import Path
import json, hashlib, math
import numpy as np
from PIL import Image, ImageFilter, ImageChops

ROOT = Path(__file__).resolve().parent
ART = ROOT.parent / 'card_scatter_v1' / 'artwork'
ASSETS = ROOT.parent / 'card_scatter_v1' / 'assets'
POSES = ROOT / 'poses'
FRAMES = ROOT / 'frames'
for folder in (POSES, FRAMES):
    folder.mkdir(exist_ok=True)
W, H, FPS = 1920, 1080, 30
rng = np.random.default_rng(20261025)

# A yellow tabletop with restrained photographic grain, fixed throughout.
yy, xx = np.mgrid[:H, :W]
light = 1.0 - .025 * ((xx-W*.40)**2/W**2 + (yy-H*.32)**2/H**2)
noise = rng.normal(0, .32, (H, W))
base = np.stack([np.clip(c*light+noise, 0, 255) for c in (255,208,0)], axis=2)
background = Image.fromarray(np.rint(base).astype('uint8')).convert('RGBA')

def drop_shadow(im, radius=7, opacity=.22, offset=(3,7)):
    alpha = im.getchannel('A').filter(ImageFilter.GaussianBlur(radius))
    shadow = Image.new('RGBA', im.size, (60,34,10,0))
    shadow.putalpha(alpha.point(lambda a: round(a*opacity)))
    combined = Image.new('RGBA', im.size)
    combined.alpha_composite(shadow, offset)
    combined.alpha_composite(im)
    return combined

def card_sprite(path, side, angle):
    im = Image.open(path).convert('RGBA').resize((side, side), Image.Resampling.LANCZOS)
    padded = Image.new('RGBA', (side+48,side+48))
    padded.alpha_composite(im, (24,24))
    padded = padded.rotate(angle, Image.Resampling.BICUBIC, expand=True)
    return drop_shadow(padded)

def place(canvas, sprite, x, y):
    canvas.alpha_composite(sprite, (round(x-sprite.width/2), round(y-sprite.height/2)))

faces = sorted(p for p in ART.glob('*.png') if p.stem.startswith(('face_', 'ref_H')) and p.stem != 'face_49')
backs = [ART / (color+'.png') for color in ['pink','blue','green','yellow','blue','pink','green','yellow','pink']]
sources = faces + backs
rng.shuffle(sources)
# Retain the mix of faces and brand-colour backs in the smaller selection.
for index,color in [(7,'blue'),(12,'pink'),(17,'green'),(21,'yellow')]:
    sources[index]=ART/(color+'.png')
positions=[]
for row in range(4):
    for col in range(6):
        if (col,row)==(3,1):
            continue
        x=140+col*328+rng.uniform(-34,34)
        y=100+row*290+rng.uniform(-29,29)
        radius=((x-W/2)/(W/2))**2+((y-H/2)/(H/2))**2
        positions.append((radius+rng.uniform(-.12,.12),x,y))
positions.sort()
cards=[]
for i,(path,(_,x,y)) in enumerate(zip(sources,positions)):
    side=int(rng.integers(235,280))
    angle=float(rng.uniform(-38,38))
    if i%13==3:
        angle+=90
    cards.append({'file':path.name,'x':x,'y':y,'side':side,'angle':angle,
                  'sprite':card_sprite(path,side,angle),
                  'arriving':card_sprite(path,round(side*1.018),angle+float(rng.choice([-1,1]))*1.7)})

holding=Image.open(ASSETS/'hand_holding.png').convert('RGBA')
releasing=Image.open(ASSETS/'hand_releasing.png').convert('RGBA')
assert holding.size==releasing.size
hero=card_sprite(ART/'face_49.png',350,-20)

# Empty opening, gently eased entrance, then the approved held-drawing scatter.
# Twenty-four cards including the released hero leave visible yellow channels.
counts=[0]*9+[3,6,10,14,18,21,23]+[23]*8
hand_offsets=[None,(0,800),(0,610),(0,365),(0,160),(0,45),
              (0,0),(-1,3),(1,9),(0,22),(-2,34),
              (0,35),(3,95),(9,210),(17,355),(28,540)]
manifest=[]
background.convert('RGB').save(ROOT/'opening_background.png',compress_level=3)
for pose,count in enumerate(counts):
    canvas=background.copy()
    previous=counts[pose-1] if pose else 0
    for index,c in enumerate(cards[:count]):
        sprite=c['arriving'] if index>=previous and count!=previous else c['sprite']
        place(canvas,sprite,c['x'],c['y'])
    if pose>=11:
        place(canvas,hero,960,502)
    hand_visible=pose<len(hand_offsets) and hand_offsets[pose] is not None
    if hand_visible:
        dx,dy=hand_offsets[pose]
        source=holding if pose<11 else releasing
        # Wrist remains below the lower edge while holding the card.
        hand_canvas=Image.new('RGBA',(W,H))
        hand_canvas.alpha_composite(source,(160+dx,180+dy))
        canvas.alpha_composite(drop_shadow(hand_canvas,radius=15,opacity=.12,offset=(-12,13)))
    target=POSES/f'pose_{pose:02d}.png'
    canvas.convert('RGB').save(target,compress_level=3)
    for repeat in range(3):
        frame=pose*3+repeat
        dest=FRAMES/f'frame_{frame:04d}.png'
        if dest.exists():
            dest.unlink()
        dest.hardlink_to(target)
        manifest.append({'frame':frame,'drawing':pose,'table_cards':count+(pose>=11),'hand':hand_visible})
    print('POSE',pose,'CARDS',count,'HAND',hand_visible,flush=True)

clean_cards=[{k:v for k,v in c.items() if k not in ('sprite','arriving')} for c in cards]
coverage=Image.new('L',(W,H))
for sprite,x,y in [(c['sprite'],c['x'],c['y']) for c in cards]+[(hero,960,502)]:
    local=Image.new('L',(W,H))
    local.paste(sprite.getchannel('A'),(round(x-sprite.width/2),round(y-sprite.height/2)))
    coverage=ImageChops.lighter(coverage,local)
table_fraction=float(np.mean(np.asarray(coverage)<128))
assert table_fraction>.25,table_fraction
report={'width':W,'height':H,'fps':FPS,'frames':len(counts)*3,'duration':len(counts)*3/FPS,
        'reference_duration':37/30,'duration_multiplier':len(counts)*3/37,
        'drawings':len(counts),'hold_frames':3,'final_table_cards':24,
        'opening':'empty yellow table; hand and card rise from below frame',
        'final_visible_table_fraction':table_fraction,
        'source_artwork_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(ART.glob('*.png'))},
        'cards':clean_cards,'frame_map':manifest}
(ROOT/'animation_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print('COMPLETE',len(counts)*3,'FRAMES; VISIBLE TABLE',table_fraction,flush=True)
