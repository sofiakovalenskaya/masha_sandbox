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
    side=int(rng.integers(292,350))
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
        hand_canvas=Image.new('RGBA',(W,H))
        hand_canvas.alpha_composite(holding,(160,180+dy))
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
        source=holding if pose<7 else releasing
        # Wrist remains below the lower edge while holding the card.
        hand_canvas=Image.new('RGBA',(W,H))
        hand_canvas.alpha_composite(source,(160+dx,180+dy))
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

clean_cards=[{k:v for k,v in c.items() if k not in ('sprite','arriving')} for c in cards[:39]]
report={'width':W,'height':H,'fps':FPS,'frames':54+prefix_frames,'duration':(54+prefix_frames)/FPS,
        'reference_duration':37/30,'duration_multiplier':(54+prefix_frames)/37,
        'drawings':18+len(intro_offsets),'hold_frames':3,'final_table_cards':40,
        'based_on':'card_scatter_v4',
        'changes':'empty opening, entrance from below, brand pink background; approved card sequence retained',
        'background_color':'#FF006F','prefix_frames':prefix_frames,
        'intro_vertical_offsets':intro_offsets,
        'source_artwork_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(ART.glob('*.png'))},
        'cards':clean_cards,'frame_map':manifest}
(ROOT/'animation_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print('COMPLETE',54+prefix_frames,'FRAMES',flush=True)
