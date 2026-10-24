"""Render 270 native Full HD frames, with subframe motion blur at the burst."""
import argparse, json, math, time
from pathlib import Path
import numpy as np
from PIL import Image
import animate as A

P=argparse.ArgumentParser();P.add_argument('--out',default='/workspace/tipo_typography_work/frames');P.add_argument('--frames',nargs='*',type=int);args=P.parse_args()
OUT=Path(args.out);OUT.mkdir(parents=True,exist_ok=True)
ASSETS=A.ROOT/'assets'
CACHE={p.name:Image.open(p).convert('RGBA') for p in ASSETS.glob('*.png')}

def paste_pose(canvas,p):
    if not A.visible(p):return
    w,h=p['size'];im=CACHE[p['asset']]
    im=im.resize((max(1,round(w)),max(1,round(h))),Image.Resampling.LANCZOS)
    if abs(p['angle'])>.001:
        im=im.rotate(-p['angle'],resample=Image.Resampling.BICUBIC,expand=True)
    x,y=p['center'];canvas.alpha_composite(im,(round(x-im.width/2),round(y-im.height/2)))

def render_at(t):
    canvas=Image.new('RGBA',(1920,1080),(*A.DATA['background'],255))
    p=A.box_pose(t)
    if p:paste_pose(canvas,p)
    for _,p in A.all_poses(t):paste_pose(canvas,p)
    return canvas.convert('RGB')

def render(f):
    t=f/30
    if t>=8.4:
        return CACHE['seam_frame.png'].convert('RGB')
    if 6.0<=t<8.4:
        samples=[np.asarray(render_at(t+dt),dtype=np.float32) for dt in np.linspace(-.00625,.00625,9)]
        return Image.fromarray(np.rint(np.mean(samples,axis=0)).astype('uint8'))
    return render_at(t)

frames=args.frames if args.frames else range(A.DATA['frames'])
for f in frames:
    path=OUT/f'frame_{f:04}.png'
    render(f).save(path,compress_level=2)
    if f%15==0:print('FRAME',f,flush=True)
    (OUT/'progress.json').write_text(json.dumps({'frame':f,'total':270}))
print('COMPLETED',len(frames),'frames',flush=True)
