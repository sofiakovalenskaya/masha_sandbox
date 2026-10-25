"""Preserve the complete approved word animation and append the paper ending."""
from pathlib import Path
import hashlib,json,subprocess,sys
from PIL import Image,ImageFilter

ROOT=Path(__file__).resolve().parent
BASE=ROOT.parent/'word_sequence_v3'
FRAMES=ROOT/'frames';POSES=ROOT/'poses'
for p in (FRAMES,POSES):p.mkdir(exist_ok=True)
if not (BASE/'stopmotion_frames/frame_0091.png').exists():
    subprocess.run([sys.executable,str(BASE/'build_stopmotion.py')],check=True)
source=BASE/'stopmotion_frames'
assert (source/'frame_0091.png').read_bytes()==(ROOT/'assets/final_word_frame.png').read_bytes()
frame=0;frame_map=[]

def link(target,source):
    if target.exists():target.unlink()
    target.hardlink_to(source)

for i in range(92):
    link(FRAMES/f'frame_{frame:04d}.png',source/f'frame_{i:04d}.png')
    frame_map.append({'frame':frame,'phase':'approved_word_animation','source_frame':i})
    frame+=1

pink=Image.new('RGBA',(1920,1080),(255,0,111,255))
pink.convert('RGB').save(ROOT/'final_pink.png',compress_level=3)
data=json.loads((ROOT/'paper_poses.json').read_text())
paper_stats=[]
for pose in data['poses']:
    index=pose['index']
    image=Image.open(ROOT/'paper_renders'/f'paper_{index:02d}.png').convert('RGBA')
    alpha=image.getchannel('A')
    shadow=Image.new('RGBA',image.size,(82,0,32,0))
    shadow.putalpha(alpha.filter(ImageFilter.GaussianBlur(18)).point(lambda a:round(a*.21)))
    canvas=pink.copy();canvas.alpha_composite(shadow,(10,12));canvas.alpha_composite(image)
    target=POSES/f'paper_{index:02d}.png';canvas.convert('RGB').save(target,compress_level=3)
    paper_stats.append({'pose':index,'alpha_bbox':alpha.getbbox(),'progress':pose['progress'],'kind':pose['kind']})
    for repeat in range(3):
        link(FRAMES/f'frame_{frame:04d}.png',target)
        frame_map.append({'frame':frame,'phase':pose['kind'],'paper_pose':index})
        frame+=1
for repeat in range(15):
    link(FRAMES/f'frame_{frame:04d}.png',ROOT/'final_pink.png')
    frame_map.append({'frame':frame,'phase':'empty_pink'})
    frame+=1
assert frame==158
report={'width':1920,'height':1080,'fps':30,'frames':frame,'duration_seconds':frame/30,
        'preserved_original_frames':92,'paper_drawing_hold_frames':3,
        'paper_drawings':17,'empty_final_hold_frames':15,'final_color':'#FF006F',
        'motion':'one connected UV-textured sheet folds into a paper ball in held poses, then leaves the frame downward',
        'source_texture_sha256':hashlib.sha256((ROOT/'assets/final_word_frame.png').read_bytes()).hexdigest(),
        'paper_stats':paper_stats,'frame_map':frame_map}
(ROOT/'animation_manifest.json').write_text(json.dumps(report,indent=2))
print('ASSEMBLED',frame,'FRAMES',flush=True)
