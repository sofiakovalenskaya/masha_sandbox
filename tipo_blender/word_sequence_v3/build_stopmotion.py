"""Held drawings: scribbles become individual printed glyphs, without a wave.

Intermediate drawings are signed-distance shape morphs. Readable drawings use
the original raster lettering and texture. There is no temporal interpolation.
"""
from pathlib import Path
import math,json,hashlib
import numpy as np
from PIL import Image,ImageDraw
from scipy.ndimage import distance_transform_edt,binary_closing,label,maximum_filter,gaussian_filter

WORK=Path(__file__).resolve().parent
SOURCE=WORK/'input';LAYERS=WORK/'layers'
OUT=WORK/'stopmotion_frames';OUT.mkdir(exist_ok=True)
POSES=WORK/'stopmotion_poses';POSES.mkdir(exist_ok=True)
BACKGROUND=Image.open(LAYERS/'background.png').convert('RGBA')
SCALE=1920/1672
WORDS=[('увидел','УВИДЕЛ'),('крикнул','КРИКНУЛ'),('выиграл','ВЫИГРАЛ!')]
PAD=55

def runs(mask):
    ids=np.where(mask.any(axis=0))[0]
    return [(int(g[0]),int(g[-1]+1)) for g in np.split(ids,np.where(np.diff(ids)>1)[0]+1) if len(g)]

def sdf(mask):return distance_transform_edt(mask)-distance_transform_edt(~mask)

def bezier(points):
    p=np.array(points,dtype=float);u=np.linspace(0,1,50)[:,None]
    return (1-u)**3*p[0]+3*(1-u)**2*u*p[1]+3*(1-u)*u*u*p[2]+u**3*p[3]

def doodle_mask(size,seed,stroke_width):
    w,h=size;rng=np.random.default_rng(seed)
    im=Image.new('L',(w,h));d=ImageDraw.Draw(im)
    # An uneven two-part curl/hook, resembling rapidly drawn thick ink marks.
    x0,y0=PAD,PAD;gw,gh=w-2*PAD,h-2*PAD
    patterns=[
      [[(.16,.70),(.04,.02),(.94,.02),(.66,.46)],[(.66,.46),(.18,.20),(.08,.98),(.87,.75)]],
      [[(.25,.88),(.78,.57),(.02,.19),(.75,.10)],[(.12,.37),(.79,.87),(.85,.25),(.43,.69)]],
      [[(.24,.18),(.97,.04),(.06,.95),(.80,.82)],[(.80,.82),(.09,1.02),(.92,.07),(.24,.18)]],
      [[(.20,.85),(.05,.32),(.85,.03),(.70,.40)],[(.70,.40),(.34,.90),(.02,.12),(.84,.74)]],
      [[(.22,.19),(.81,-.02),(.85,.66),(.20,.70)],[(.20,.70),(.09,1.04),(.58,.97),(.78,.56)]],
      [[(.20,.12),(.99,.19),(.01,.48),(.68,.53)],[(.68,.53),(.99,.95),(.12,.97),(.27,.65)]]
    ]
    variations=patterns[(seed//19)%len(patterns)]
    # Compensate for the smaller initial drawing so the final on-screen ink
    # weight is comparable to the full-size letter strokes.
    thickness=max(28,int(round(stroke_width*1.42)))
    for part in variations:
        p=np.asarray(part)+rng.normal(0,.065,(4,2));p[:,0]=x0+p[:,0]*gw;p[:,1]=y0+p[:,1]*gh
        if seed%3==1:p[:,0]=w-p[:,0]
        path=bezier(p);xy=[tuple(v) for v in path]
        d.line(xy,fill=255,width=thickness,joint='curve')
        for x,y in [xy[0],xy[-1]]:d.ellipse((x-thickness/2,y-thickness/2,x+thickness/2,y+thickness/2),fill=255)
    return np.asarray(im)>127,thickness

def boiling_contour(g,seed):
    """A held hand-drawn outline variant, with source ink texture unchanged."""
    rng=np.random.default_rng(seed)
    h,w=g['rgba'].shape[:2]
    coarse=rng.normal(0,1,(6,5)).astype('float32')
    field=np.asarray(Image.fromarray(coarse).resize((w,h),Image.Resampling.BICUBIC))
    field=gaussian_filter(field,5)
    field=field/max(.1,float(np.max(np.abs(field))))
    shift=field*2.3+rng.uniform(-.65,.65)
    signed=g['target_sdf']
    shape=np.clip(.5+(signed+shift)/1.5,0,1)
    alpha=g['rgba'][:,:,3].astype(float)/255
    band=np.abs(signed)<5
    alpha[band]=(shape*g['grain'])[band]
    out=g['rgba'].copy()
    # Expanded contours need ink color too; transparent pixels in the source
    # have no reliable color. Preserve the original RGB on original ink.
    out[:,:,:3][g['rgba'][:,:,3]<32]=g['ink']
    out[:,:,3]=np.rint(alpha*255).astype('uint8')
    return out

letters=[]
for wi,(key,text) in enumerate(WORDS):
    original=np.asarray(Image.open(SOURCE/(key+'.png')).convert('RGB'))
    ys,xs=np.where(original[:,:,0]>80);origin=(xs.min()-20,ys.min()-20)
    layer=np.asarray(Image.open(LAYERS/(key+'.png')).convert('RGBA'))
    intervals=runs(layer[:,:,3]>100)
    if key=='выиграл':
        # Ы has two disjoint pieces; Р and А touch in the uploaded artwork.
        x0,x1=intervals[5]
        counts=(layer[:,:,3]>100).sum(axis=0)
        split=int(np.argmin(counts[920:980])+920)
        intervals=[intervals[0],(intervals[1][0],intervals[2][1]),intervals[3],intervals[4],(x0,split),(split,x1),intervals[6],intervals[7]]
    assert len(intervals)==len(text),(key,intervals,len(text))
    glyphs=[]
    for gi,(char,(x0,x1)) in enumerate(zip(text,intervals)):
        yy,xx=np.where(layer[:,x0:x1,3]>100);y0,y1=int(yy.min()),int(yy.max()+1)
        crop=layer[y0:y1,x0:x1];gh,gw=crop.shape[:2]
        rgba=np.zeros((gh+2*PAD,gw+2*PAD,4),'uint8');rgba[PAD:PAD+gh,PAD:PAD+gw]=crop
        alpha=rgba[:,:,3]/255
        target=binary_closing(alpha>.4,iterations=2)
        # Fill only printed grain holes; retain real counters in the letters.
        holes=~target;labs,n=label(holes);sizes=np.bincount(labs.ravel())
        fill=np.where(sizes<45)[0];target[np.isin(labs,fill)]=True
        dist=distance_transform_edt(target)
        ridge=(dist>=maximum_filter(dist,size=7)-.15)&(dist>5)
        stroke=float(np.median(dist[ridge])*2) if np.any(ridge) else min(gw,gh)*.25
        stroke=float(np.clip(stroke,min(gw,gh)*.17,min(gw,gh)*.39))
        doodle,doodle_width=doodle_mask((gw+2*PAD,gh+2*PAD),wi*101+gi*19+73,stroke)
        ink=np.percentile(crop[:,:,:3][crop[:,:,3]>220],70,axis=0)
        rng=np.random.default_rng(wi*1000+gi*31)
        # Intermediate ink keeps the source's print pores where it overlaps.
        grain=np.ones(alpha.shape);grain[PAD:PAD+gh,PAD:PAD+gw]=np.where(target[PAD:PAD+gh,PAD:PAD+gw],np.maximum(.0,crop[:,:,3]/255),1)
        grain[(rng.random(alpha.shape)<.009)]=0
        glyphs.append({'char':char,'rgba':rgba,'target_sdf':sdf(target),'doodle_sdf':sdf(doodle),
             'cx':(origin[0]+(x0+x1)/2)*SCALE,'cy':(origin[1]+(y0+y1)/2)*1080/941,
             'w':gw,'h':gh,'ink':ink,'grain':grain,'seed':wi*100+gi,
             'letter_stroke_px':stroke,'doodle_stroke_px':doodle_width})
    letters.append(glyphs)

# Each entry is a discrete drawing; several output frames hold that drawing.
# The last word finishes as a readable picture instead of disappearing.
plans=[
 {'kind':'scribble','blend':0.,'sx':.82,'sy':.61,'rotation':14,'jitter':6},
 {'kind':'growing','blend':.34,'sx':.88,'sy':.75,'rotation':10,'jitter':5},
 {'kind':'growing','blend':.73,'sx':.93,'sy':.88,'rotation':6,'jitter':4},
 {'kind':'overshoot','blend':1.,'sx':1.025,'sy':1.075,'rotation':2.6,'jitter':3},
 {'kind':'readable','blend':1.,'sx':1.,'sy':.985,'rotation':1.5,'jitter':2},
 {'kind':'readable','blend':1.,'sx':1.,'sy':1.015,'rotation':1.1,'jitter':2},
 {'kind':'settled','blend':1.,'sx':1.,'sy':1.,'rotation':0.,'jitter':0},
 {'kind':'collapse','blend':.69,'sx':.91,'sy':.69,'rotation':10,'jitter':5},
 {'kind':'scribble_out','blend':.12,'sx':.82,'sy':.60,'rotation':17,'jitter':7}
]
holds=[3,3,4,3,3,4,3,3,4]
metadata=[];frame=0
for wi,(key,text) in enumerate(WORDS):
    current=[dict(p) for p in plans]
    durations=holds[:]
    if wi==2:
        current=current[:7]+[dict(plans[4]),dict(plans[5]),dict(plans[6])]
        durations=[3,3,4,3,3,3,3,3,3,4]
    for pi,(p,hold) in enumerate(zip(current,durations)):
        canvas=BACKGROUND.copy()
        for gi,g in enumerate(letters[wi]):
            rng=np.random.default_rng(gi*739+wi*2903+pi*41)
            if p['blend']==1:
                rgba=boiling_contour(g,gi*127+wi*1297+pi*41)
            else:
                signed=(1-p['blend'])*g['doodle_sdf']+p['blend']*g['target_sdf']
                alpha=np.clip(.5+signed/1.7,0,1)*g['grain']
                rgba=np.zeros((*alpha.shape,4),'uint8');rgba[:,:,:3]=g['ink'];rgba[:,:,3]=np.rint(alpha*255).astype('uint8')
            im=Image.fromarray(rgba)
            sx,sy=p['sx'],p['sy']
            # Growth rises from each letter's lower edge, independently.
            w=max(1,round(im.width*SCALE*sx));h=max(1,round(im.height*SCALE*sy))
            im=im.resize((w,h),Image.Resampling.LANCZOS)
            angle=float(rng.uniform(-p['rotation'],p['rotation']))
            if angle:im=im.rotate(angle,Image.Resampling.BICUBIC,expand=True)
            x=g['cx']+float(rng.uniform(-p['jitter'],p['jitter']))
            y=g['cy']+g['h']*SCALE*(1-sy)/2+float(rng.uniform(-p['jitter'],p['jitter']))
            canvas.alpha_composite(im,(round(x-im.width/2),round(y-im.height/2)))
        rendered=canvas.convert('RGB');posefile=POSES/f'{wi}_{pi:02}_{p["kind"]}.png';rendered.save(posefile,compress_level=3)
        for repeat in range(hold):
            output=OUT/f'frame_{frame:04}.png'
            if output.exists():output.unlink()
            output.hardlink_to(posefile)
            metadata.append({'frame':frame,'word':key,'drawing':f'{wi}_{pi:02}','kind':p['kind']})
            frame+=1
        print('DRAWING',wi,pi,p['kind'],'HOLD',hold,flush=True)
assert frame==92,frame
report={'width':1920,'height':1080,'fps':30,'frames':frame,'duration_seconds':frame/30,
        'distinct_drawings':sum([9,9,10]),'drawing_holds_frames':[3,4],
        'motion':'thick scribbles growing into glyphs; small independently redrawn contours on every readable pose; no temporal interpolation',
        'contour_variation_source_px':2.3,
        'stroke_measurements':[[{'char':g['char'],'letter_px':g['letter_stroke_px'],'scribble_px_before_pose_scale':g['doodle_stroke_px'],
          'minimum_initial_screen_weight_ratio':g['doodle_stroke_px']*.61/g['letter_stroke_px']} for g in glyphs] for glyphs in letters],
        'order':['УВИДЕЛ','КРИКНУЛ','ВЫИГРАЛ!'],'frame_map':metadata}
(WORK/'animation_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print('STOP MOTION COMPLETE',frame,flush=True)
