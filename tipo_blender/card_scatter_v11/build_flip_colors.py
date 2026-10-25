"""Preserve v10, then turn the rules card over and cycle original backs twice."""
from pathlib import Path
import hashlib
import json
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent/'card_scatter_v10'
RULES = ROOT.parent/'card_scatter_v9'
ART = ROOT.parent/'card_scatter_v1/artwork'
FRAMES = ROOT/'frames'
FRAMES.mkdir(exist_ok=True)
W,H,FPS = 1920,1080,30
SIDE = 972
SCALE = SIDE/320
PREFIX = 228
FLIP_FRAMES = 25
BLACK_HOLD = 12
COLOR_HOLD = 6
FINAL_HOLD = 18
COLORS = ['green','pink','yellow','blue']*2

back_path = ROOT/'assets/black_back_original.png'
paths = {'rules':RULES/'assets/rules_front.png','black':back_path,
         **{color:ART/(color+'.png') for color in COLORS}}
artwork = {key:Image.open(path).convert('RGBA') for key,path in paths.items()}
bg = Image.open(RULES/'opening_background.png').convert('RGBA')
half_w,half_h = W/(2*SCALE),H/(2*SCALE)
background = bg.resize((W,H),Image.Resampling.LANCZOS,
    box=(960-half_w,540-half_h,960+half_w,540+half_h))

def flat_card(key):
    pad = round(24*SCALE)
    sprite = Image.new('RGBA',(SIDE+2*pad,SIDE+2*pad))
    sprite.alpha_composite(artwork[key].resize((SIDE,SIDE),Image.Resampling.LANCZOS),(pad,pad))
    alpha = sprite.getchannel('A').filter(ImageFilter.GaussianBlur(7*SCALE))
    shadow = Image.new('RGBA',sprite.size,(60,34,10,0))
    shadow.putalpha(alpha.point(lambda a:round(a*.22)))
    combined = Image.new('RGBA',sprite.size)
    combined.alpha_composite(shadow,(round(3*SCALE),round(7*SCALE)))
    combined.alpha_composite(sprite)
    canvas = background.copy()
    canvas.alpha_composite(combined,(round(960-combined.width/2),round(540-combined.height/2)))
    return canvas.convert('RGB')

def perspective_coefficients(dst,src):
    matrix=[];values=[]
    for (x,y),(u,v) in zip(dst,src):
        matrix.extend([[x,y,1,0,0,0,-u*x,-u*y],[0,0,0,x,y,1,-v*x,-v*y]])
        values.extend([u,v])
    return np.linalg.solve(np.array(matrix,float),np.array(values,float)).tolist()

def turn_card(theta):
    if theta == 0:
        return flat_card('rules')
    if abs(theta-math.pi)<1e-9:
        return flat_card('black')
    key = 'rules' if theta<math.pi/2 else 'black'
    # The reverse texture has its own outward-facing coordinates, so the
    # logo ends upright and is never mirrored as the card turns around Y.
    angle = theta if key=='rules' else theta-math.pi
    focal=6500
    corners=[]
    for x,y in [(-SIDE/2,-SIDE/2),(SIDE/2,-SIDE/2),(SIDE/2,SIDE/2),(-SIDE/2,SIDE/2)]:
        depth=-x*math.sin(angle)
        perspective=focal/(focal+depth)
        corners.append((960+x*math.cos(angle)*perspective,540+y*perspective))
    layer=Image.new('RGBA',(W,H))
    if abs(math.cos(angle))<.003:
        # A finite ivory paper edge remains visible at exactly 90 degrees.
        ImageDraw.Draw(layer).line([(960,min(y for x,y in corners)),
                                    (960,max(y for x,y in corners))],fill=(255,252,244,255),width=3)
    else:
        tex=artwork[key]
        src=[(0,0),(tex.width,0),(tex.width,tex.height),(0,tex.height)]
        coeff=perspective_coefficients(corners,src)
        layer=tex.transform((W,H),Image.Transform.PERSPECTIVE,coeff,
                            Image.Resampling.BICUBIC)
    alpha=layer.getchannel('A').filter(ImageFilter.GaussianBlur(7*SCALE))
    shadow=Image.new('RGBA',(W,H),(60,34,10,0))
    shadow.putalpha(alpha.point(lambda a:round(a*.22)))
    canvas=background.copy()
    canvas.alpha_composite(shadow,(round(3*SCALE),round(7*SCALE)))
    canvas.alpha_composite(layer)
    return canvas.convert('RGB')

manifest=[]
for frame in range(PREFIX):
    src=SOURCE/'frames'/f'frame_{frame:04d}.png'
    dest=FRAMES/src.name
    if dest.exists():dest.unlink()
    dest.hardlink_to(src)
    manifest.append({'frame':frame,'phase':'approved_v10_unchanged','source_frame':frame})

def emit(image,phase,hold=1,**metadata):
    first=None
    for i in range(hold):
        n=len(manifest);path=FRAMES/f'frame_{n:04d}.png'
        if path.exists():path.unlink()
        if first is None:
            image.save(path,compress_level=3);first=path
        else:path.hardlink_to(first)
        manifest.append({'frame':n,'phase':phase,'card_center':[960,540],
                         'physical_card_side':SIDE,**metadata})

assert flat_card('rules').tobytes()==Image.open(SOURCE/'final_rules_closeup.png').convert('RGB').tobytes()
for i in range(FLIP_FRAMES):
    u=i/(FLIP_FRAMES-1)
    eased=u*u*(3-2*u)
    theta=math.pi*eased
    emit(turn_card(theta),'card_flip',angle_degrees=180*eased,
         face='rules' if i<FLIP_FRAMES//2 else 'black_back')
    if i%6==0:print('FLIP',i,round(180*eased,2),flush=True)
black=flat_card('black')
emit(black,'black_back_hold',BLACK_HOLD,back_color='black',angle_degrees=180)
black.save(ROOT/'black_back_closeup.png',compress_level=3)
for i,color in enumerate(COLORS):
    emit(flat_card(color),'color_cycle',COLOR_HOLD,
         back_color=color,cycle=i//4+1,color_index=i%4,angle_degrees=180)
final=flat_card('blue')
emit(final,'final_blue_hold',FINAL_HOLD,back_color='blue',angle_degrees=180)
final.save(ROOT/'final_blue_back.png',compress_level=3)
report={'based_on':'card_scatter_v10','width':W,'height':H,'fps':FPS,
        'frames':len(manifest),'duration_seconds':len(manifest)/FPS,
        'unchanged_prefix_frames':PREFIX,'flip_frames':FLIP_FRAMES,
        'flip_axis':'vertical Y','black_back_hold_frames':BLACK_HOLD,
        'color_order':COLORS,'color_cycles':2,'frames_per_color':COLOR_HOLD,
        'seconds_per_color':COLOR_HOLD/FPS,'final_hold_frames':FINAL_HOLD,
        'card_side_px':SIDE,'card_center':[960,540],'background_unchanged':True,
        'original_artwork_sha256':{key:hashlib.sha256(path.read_bytes()).hexdigest()
                                   for key,path in paths.items()},'frame_map':manifest}
(ROOT/'animation_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print('COMPLETE',len(manifest),'frames',flush=True)
