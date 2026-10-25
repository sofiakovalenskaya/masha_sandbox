"""Separate, seamless blue-card anticipation and rightward exit shot."""
from pathlib import Path
import hashlib
import json
from PIL import Image, ImageFilter
import numpy as np

ROOT=Path(__file__).resolve().parent
PARENT=ROOT.parent
SOURCE=PARENT/'card_scatter_v11'
FRAMES=ROOT/'frames'
FRAMES.mkdir(exist_ok=True)
W,H,FPS=1920,1080,30
SIDE=972
SCALE=SIDE/320
START_HOLD,WINDUP,EXIT,END_HOLD=3,12,15,30

bg=Image.open(PARENT/'card_scatter_v9/opening_background.png').convert('RGBA')
hw,hh=W/(2*SCALE),H/(2*SCALE)
background=bg.resize((W,H),Image.Resampling.LANCZOS,
                     box=(960-hw,540-hh,960+hw,540+hh))
art_path=PARENT/'card_scatter_v1/artwork/blue.png'
art=Image.open(art_path).convert('RGBA').resize((SIDE,SIDE),Image.Resampling.LANCZOS)
pad=round(24*SCALE)
sprite=Image.new('RGBA',(SIDE+2*pad,SIDE+2*pad))
sprite.alpha_composite(art,(pad,pad))
alpha=sprite.getchannel('A').filter(ImageFilter.GaussianBlur(7*SCALE))
shadow=Image.new('RGBA',sprite.size,(60,34,10,0))
shadow.putalpha(alpha.point(lambda a:round(a*.22)))
combined=Image.new('RGBA',sprite.size)
combined.alpha_composite(shadow,(round(3*SCALE),round(7*SCALE)))
combined.alpha_composite(sprite)

def render(x):
    canvas=background.copy()
    canvas.alpha_composite(combined,(round(x-combined.width/2),round(540-combined.height/2)))
    return canvas.convert('RGB')

def flight_x(u):
    return 880+(2850-880)*max(0,min(1,u))**1.65

def render_flight(i):
    # A short shutter gives the fast rightward launch a restrained motion blur.
    samples=[render(flight_x((i+offset)/EXIT)) for offset in [-.16,-.053,.053,.16]]
    avg=np.mean([np.asarray(im,dtype=np.float32) for im in samples],axis=0)
    return Image.fromarray(np.rint(avg).astype('uint8'))

source_final=SOURCE/'final_blue_back.png'
assert render(960).tobytes()==Image.open(source_final).convert('RGB').tobytes()
manifest=[]

def emit(image,phase,hold=1,**metadata):
    first=None
    for i in range(hold):
        n=len(manifest);dest=FRAMES/f'frame_{n:04d}.png'
        if dest.exists():dest.unlink()
        if first is None:
            image.save(dest,compress_level=3);first=dest
        else:dest.hardlink_to(first)
        manifest.append({'frame':n,'phase':phase,'card_side_px':SIDE,
                         'card_center_y':540,'card_angle':0,**metadata})

emit(Image.open(source_final).convert('RGB'),'matching_start',START_HOLD,card_center_x=960)
# Preserve the exact original PNG at the edit point, including PNG bytes.
for n in range(START_HOLD):
    dest=FRAMES/f'frame_{n:04d}.png';dest.unlink();dest.hardlink_to(source_final)
for i in range(1,WINDUP+1):
    u=i/WINDUP
    eased=u*u*u*(10+u*(-15+6*u))
    x=960-80*eased
    emit(render(x),'anticipation_left',card_center_x=x)
for i in range(1,EXIT+1):
    emit(render_flight(i),'launch_right',card_center_x=flight_x(i/EXIT),motion_blur=True)
emit(background.convert('RGB'),'empty_pink',END_HOLD,card_visible=False)
background.convert('RGB').save(ROOT/'final_empty_pink.png',compress_level=3)
assert len(manifest)==60
report={'source_video':'tipo_card_scatter_v11_flip_color_cycles_1080p.mp4',
        'separate_clip':True,'width':W,'height':H,'fps':FPS,'frames':len(manifest),
        'duration_seconds':len(manifest)/FPS,'card_side_px':SIDE,
        'card_start_center':[960,540],'anticipation_px':80,'anticipation_frames':WINDUP,
        'launch_frames':EXIT,'start_hold_frames':START_HOLD,'empty_background_frames':END_HOLD,
        'first_frame_png_matches_previous_final':True,
        'source_final_sha256':hashlib.sha256(source_final.read_bytes()).hexdigest(),
        'source_artwork_sha256':hashlib.sha256(art_path.read_bytes()).hexdigest(),
        'camera_fixed':True,'card_size_fixed':True,'card_rotation_degrees':0,
        'frame_map':manifest}
(ROOT/'animation_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print('COMPLETE',len(manifest),'frames',flush=True)
