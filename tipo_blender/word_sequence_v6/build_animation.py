"""Insert a gradual, held-drawing crease onset before the approved paper ending."""
from pathlib import Path
import json,hashlib,subprocess,sys
from PIL import Image,ImageFilter

ROOT=Path(__file__).resolve().parent
BASE=ROOT.parent/'word_sequence_v5'
ASSETS=ROOT/'assets';FRAMES=ROOT/'frames';POSES=ROOT/'poses'
for p in (FRAMES,POSES):p.mkdir(exist_ok=True)
W,H,FPS,HOLD=1920,1080,30,3
PINK=(255,0,111,255)
if not (BASE/'frames/frame_0148.png').exists():
    subprocess.run([sys.executable,str(BASE/'build_animation.py')],check=True)

def link(target,source):
    if target.exists():target.unlink()
    target.hardlink_to(source)

def paper_frame(filename,width,height,angle=0):
    # Retain the complete image canvas, so the print stays at its original
    # relative location during the first shallow creases.
    im=Image.open(ASSETS/filename).convert('RGBA').resize((width,height),Image.Resampling.LANCZOS)
    if angle:im=im.rotate(angle,Image.Resampling.BICUBIC,expand=True)
    layer=Image.new('RGBA',(W,H))
    layer.alpha_composite(im,(round((W-im.width)/2),round((H-im.height)/2)))
    sh=Image.new('RGBA',(W,H),(84,0,31,0))
    sh.putalpha(layer.getchannel('A').filter(ImageFilter.GaussianBlur(12)).point(lambda a:round(a*.24)))
    canvas=Image.new('RGBA',(W,H),PINK)
    canvas.alpha_composite(sh,(7,10));canvas.alpha_composite(layer)
    return canvas.convert('RGB')

frame=0;mapping=[];stats=[]
for i in range(92):
    link(FRAMES/f'frame_{frame:04d}.png',BASE/'frames'/f'frame_{i:04d}.png')
    mapping.append({'frame':frame,'phase':'approved_words','base_frame':i});frame+=1

flat=Image.open(BASE/'frames/frame_0091.png').convert('RGB')
barely=paper_frame('paper_near_flat.png',W,H)
stages=[]
for amount in [.08,.18,.34,.54,.76,1.]:
    # Six discrete onset drawings introduce relief and edge separation
    # gradually. No motion-interpolated or flowing cloth-like deformation.
    stages.append((f'crease_relief_{amount:.2f}',Image.blend(flat,barely,amount),{'relief_mix':amount}))
stages.extend([
    ('light_creases',paper_frame('paper_light_creases.png',1920,1080),{}),
    ('light_edges_gather',paper_frame('paper_light_creases.png',1910,1074,.15),{}),
    ('medium_creases',paper_frame('paper_medium_creases.png',1900,1070),{}),
    ('medium_edges_gather',paper_frame('paper_medium_creases.png',1880,1050,-.20),{}),
])
for index,(name,image,extra) in enumerate(stages):
    file=POSES/f'onset_{index:02d}.png';image.save(file,compress_level=3)
    stats.append({'drawing':index,'name':name,**extra})
    for repeat in range(HOLD):
        link(FRAMES/f'frame_{frame:04d}.png',file)
        mapping.append({'frame':frame,'phase':'crease_onset','onset_drawing':index});frame+=1

inserted=len(stages)*HOLD
old=json.loads((BASE/'animation_manifest.json').read_text())
for i in range(92,149):
    link(FRAMES/f'frame_{frame:04d}.png',BASE/'frames'/f'frame_{i:04d}.png')
    phase=old['frame_map'][i]['phase']
    mapping.append({'frame':frame,'phase':phase,'base_frame':i});frame+=1
link(ROOT/'final_pink.png',BASE/'final_pink.png')
assert inserted==30 and frame==179
manifest={'width':W,'height':H,'fps':FPS,'frames':frame,'duration_seconds':frame/FPS,
          'based_on':'word_sequence_v5','preserved_original_word_frames':92,
          'preserved_previous_tail_frames':57,'inserted_frames':inserted,
          'inserted_drawings':len(stages),'crease_onset_seconds':inserted/FPS,
          'total_crumple_drawings':len(stages)+6,'crumple_frames':inserted+18,
          'drawing_hold_frames':HOLD,'rolling_frames_unchanged':24,
          'final_color':'#FF006F','final_empty_hold_frames':15,
          'change':'gradual subtle crease onset and extra paper states; previous crumple and rolling tail retained pixel-for-pixel',
          'assets_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(ASSETS.glob('*.png'))},
          'onset_drawings':stats,'frame_map':mapping}
(ROOT/'animation_manifest.json').write_text(json.dumps(manifest,indent=2))
print('ASSEMBLED',frame,'FRAMES; INSERTED',inserted,flush=True)
