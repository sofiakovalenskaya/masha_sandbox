"""Corner-driven paper onset; no frame blending or opacity fades."""
from pathlib import Path
import json,hashlib,subprocess,sys
from PIL import Image,ImageFilter

ROOT=Path(__file__).resolve().parent
BASE=ROOT.parent/'word_sequence_v5'
FRAMES=ROOT/'frames';POSES=ROOT/'poses'
for p in (FRAMES,POSES):p.mkdir(exist_ok=True)
if not (BASE/'frames/frame_0148.png').exists():
    subprocess.run([sys.executable,str(BASE/'build_animation.py')],check=True)

def link(target,source):
    if target.exists():target.unlink()
    target.hardlink_to(source)

def composite(layer):
    canvas=Image.new('RGBA',(1920,1080),(255,0,111,255))
    shadow=Image.new('RGBA',canvas.size,(84,0,31,0))
    shadow.putalpha(layer.getchannel('A').filter(ImageFilter.GaussianBlur(10)).point(lambda a:round(a*.22)))
    canvas.alpha_composite(shadow,(6,9));canvas.alpha_composite(layer)
    return canvas.convert('RGB')

frame=0;mapping=[]
for i in range(92):
    link(FRAMES/f'frame_{frame:04d}.png',BASE/'frames'/f'frame_{i:04d}.png')
    mapping.append({'frame':frame,'phase':'approved_words','base_frame':i});frame+=1

data=json.loads((ROOT/'corner_poses.json').read_text())
for p in data['poses']:
    index=p['index'];layer=Image.open(ROOT/'corner_renders'/f'corner_{index:02d}.png').convert('RGBA')
    target=POSES/f'corner_{index:02d}.png';composite(layer).save(target,compress_level=3)
    for repeat in range(3):
        link(FRAMES/f'frame_{frame:04d}.png',target)
        mapping.append({'frame':frame,'phase':'rigid_corner_folds','corner_pose':index});frame+=1

# Once all four corners are folded, creases gather across the body of the
# sheet. These are opaque photographic paper poses, with no dissolves.
medium=Image.open(ROOT.parent/'word_sequence_v6/assets/paper_medium_creases.png').convert('RGBA')
for i,(width,height) in enumerate([(1900,1070),(1870,1040)]):
    im=medium.resize((width,height),Image.Resampling.LANCZOS)
    layer=Image.new('RGBA',(1920,1080))
    layer.alpha_composite(im,(round((1920-width)/2),round((1080-height)/2)))
    target=POSES/f'body_gather_{i:02d}.png';composite(layer).save(target,compress_level=3)
    for repeat in range(3):
        link(FRAMES/f'frame_{frame:04d}.png',target)
        mapping.append({'frame':frame,'phase':'body_gather','pose':i});frame+=1

inserted=frame-92
old=json.loads((BASE/'animation_manifest.json').read_text())
for i in range(92,149):
    link(FRAMES/f'frame_{frame:04d}.png',BASE/'frames'/f'frame_{i:04d}.png')
    mapping.append({'frame':frame,'phase':old['frame_map'][i]['phase'],'base_frame':i});frame+=1
link(ROOT/'final_pink.png',BASE/'final_pink.png')
assert inserted==42 and frame==191
report={'width':1920,'height':1080,'fps':30,'frames':frame,'duration_seconds':frame/30,
        'preserved_word_frames':92,'preserved_previous_tail_frames':57,'tail_offset':42,
        'corner_drawings':12,'corner_phase_frames':36,'body_gather_drawings':2,
        'hold_frames':3,'frame_blending':False,'opacity_fades':False,
        'corner_material_alpha':1,'top_bottom_edges_locked_during_corner_phase':True,
        'final_color':'#FF006F','final_empty_hold_frames':15,
        'source_texture_sha256':hashlib.sha256((ROOT/'assets/final_word_frame.png').read_bytes()).hexdigest(),
        'corner_poses':data['poses'],'frame_map':mapping}
(ROOT/'animation_manifest.json').write_text(json.dumps(report,indent=2))
print('ASSEMBLED',frame,'FRAMES; PHYSICAL CORNER ONSET',inserted,flush=True)
