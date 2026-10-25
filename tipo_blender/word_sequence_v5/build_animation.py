"""Photographic stiff-paper poses and a multi-view rolling exit."""
from pathlib import Path
import hashlib,json,math,subprocess,sys
from PIL import Image,ImageFilter
import numpy as np
from scipy.ndimage import label,find_objects

ROOT=Path(__file__).resolve().parent
BASE=ROOT.parent/'word_sequence_v3'
ASSETS=ROOT/'assets';FRAMES=ROOT/'frames';POSES=ROOT/'poses'
for p in (FRAMES,POSES):p.mkdir(exist_ok=True)
W,H,FPS=1920,1080,30
PINK=(255,0,111,255)
if not (BASE/'stopmotion_frames/frame_0091.png').exists():
    subprocess.run([sys.executable,str(BASE/'build_stopmotion.py')],check=True)

def sprite(im):
    im=im.convert('RGBA')
    box=im.getchannel('A').point(lambda a:255 if a>24 else 0).getbbox()
    assert box,'Empty paper sprite'
    return im.crop(box)

def fit(im,width,height):
    scale=min(width/im.width,height/im.height)
    return im.resize((round(im.width*scale),round(im.height*scale)),Image.Resampling.LANCZOS)

def draw(im,center,angle=0):
    if angle:im=im.rotate(angle,Image.Resampling.BICUBIC,expand=True)
    canvas=Image.new('RGBA',(W,H),PINK)
    layer=Image.new('RGBA',(W,H))
    xy=(round(center[0]-im.width/2),round(center[1]-im.height/2))
    layer.alpha_composite(im,xy)
    sh=Image.new('RGBA',(W,H),(84,0,31,0))
    sh.putalpha(layer.getchannel('A').filter(ImageFilter.GaussianBlur(12)).point(lambda a:round(a*.24)))
    canvas.alpha_composite(sh,(7,10));canvas.alpha_composite(layer)
    return canvas.convert('RGB'),layer.getchannel('A').getbbox()

def link(target,source):
    if target.exists():target.unlink()
    target.hardlink_to(source)

mapping=[];frame=0
for i in range(92):
    source=BASE/'stopmotion_frames'/f'frame_{i:04d}.png'
    link(FRAMES/f'frame_{frame:04d}.png',source)
    mapping.append({'frame':frame,'phase':'approved_words','source_frame':i});frame+=1

early=sprite(Image.open(ASSETS/'paper_early.png'))
gathered=sprite(Image.open(ASSETS/'paper_gathered.png'))
ball=sprite(Image.open(ASSETS/'paper_ball.png'))
steps=[
    ('early_large',early,1840,1000,(960,540),0),
    ('early_gathering',early,1600,900,(957,543),-1.8),
    ('gathered',gathered,1120,800,(963,540),2),
    ('gathered_tight',gathered,690,620,(958,542),-3),
    ('compact_ball',ball,360,360,(960,541),0),
    ('ball_settled',ball,310,310,(960,548),0),
]
pose_stats=[]
for index,(name,asset,width,height,center,angle) in enumerate(steps):
    image,bbox=draw(fit(asset,width,height),center,angle)
    path=POSES/f'fold_{index:02d}.png';image.save(path,compress_level=3)
    pose_stats.append({'pose':index,'phase':'crumple','asset':name,'center':center,'alpha_bbox':bbox})
    for repeat in range(3):
        link(FRAMES/f'frame_{frame:04d}.png',path)
        mapping.append({'frame':frame,'phase':'crumple','pose':index});frame+=1

# The atlas contains distinct 3D orientations: printed fragments turn under
# the ball while it travels down. No flat spin or repeated falling still.
atlas=Image.open(ASSETS/'rolling_atlas.png').convert('RGBA')
labels,n=label(np.asarray(atlas.getchannel('A'))>24)
sizes=np.bincount(labels.ravel());components=find_objects(labels)
ids=np.argsort(sizes[1:])[-8:]+1
ids=sorted(ids,key=lambda i:(int((components[i-1][0].start+components[i-1][0].stop)/2>atlas.height/2),components[i-1][1].start))
views=[];view_boxes=[]
for ident in ids:
    sy,sx=components[ident-1]
    box=(sx.start,sy.start,sx.stop,sy.stop)
    assert int(sizes[ident])>50000
    views.append(sprite(atlas.crop(box)));view_boxes.append(box)
radius=155.
for index,view in enumerate(views):
    angle=index*math.pi/4
    center=(960+[0,4,-3,3,5,7,8,8][index],548+radius*angle)
    image,bbox=draw(fit(view,310,310),center)
    path=POSES/f'roll_{index:02d}.png';image.save(path,compress_level=3)
    pose_stats.append({'pose':index,'phase':'rolling','atlas_view':index,
                       'rotation_x_degrees':index*45,'center':center,
                       'rolling_radius_px':radius,'alpha_bbox':bbox,
                       'view_sha256':hashlib.sha256(view.tobytes()).hexdigest()})
    for repeat in range(3):
        link(FRAMES/f'frame_{frame:04d}.png',path)
        mapping.append({'frame':frame,'phase':'rolling','pose':index});frame+=1

pink=Image.new('RGB',(W,H),PINK[:3]);pink.save(ROOT/'final_pink.png',compress_level=3)
for repeat in range(15):
    link(FRAMES/f'frame_{frame:04d}.png',ROOT/'final_pink.png')
    mapping.append({'frame':frame,'phase':'empty_pink'});frame+=1
assert frame==149,frame
manifest={'width':W,'height':H,'fps':FPS,'frames':frame,'duration_seconds':frame/FPS,
          'preserved_original_frames':92,'final_color':'#FF006F','final_empty_hold_frames':15,
          'fold_drawings':6,'rolling_drawings':8,'hold_frames':3,
          'rolling_atlas_view_boxes':view_boxes,
          'motion':'photographic stiff folds followed by eight successive surface orientations rolling down; no cloth waves',
          'assets_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(ASSETS.glob('*.png'))},
          'poses':pose_stats,'frame_map':mapping}
(ROOT/'animation_manifest.json').write_text(json.dumps(manifest,indent=2))
print('COMPLETE',frame,'FRAMES',flush=True)
