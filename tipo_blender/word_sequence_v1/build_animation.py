"""Transfer the measured squash/stretch and local ink motion from the reference.

The uploaded PNGs provide every printed pixel. No typeface is substituted and
no image-generation step is used. The 4-word reference is adapted to the three
uploaded slides; its last returning loop word becomes a final winner hold.
"""
import sys,json,math,hashlib,shutil,time,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/'pydeps'))
import cv2
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

WORK=Path(__file__).resolve().parent
OUT=WORK/'frames';OUT.mkdir(exist_ok=True)
ASSETS=WORK/'layers';ASSETS.mkdir(exist_ok=True)
SLOW=1.15;FPS=30;N=92
METRICS=json.loads((WORK/'reference_metrics.json').read_text())
if not (WORK/'reference_frames/frame_001.png').exists():
    (WORK/'reference_frames').mkdir(exist_ok=True)
    subprocess.run(['ffmpeg','-v','error','-y','-i',str(WORK/'input/реф.mp4'),'-vsync','0',str(WORK/'reference_frames/frame_%03d.png')],check=True)
H,W=1080,1920
NW,NH=640,384

def image(path):return np.asarray(Image.open(path).convert('RGB'))
def input_mask(im):
    # All three supplied designs have a blue ground. Red is the most stable
    # foreground signal for both white and yellow ink.
    return im[:,:,0]>80

inputs=[]
background=None
for key in ['увидел','крикнул','выиграл']:
    p=WORK/'input'/(key+'.png');im=image(p);m=input_mask(im)
    ys,xs=np.where(m);box=[int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1)]
    # Estimate the blue under the ink from nearby blue pixels. Smooth normalized
    # convolution avoids giving the printed grain any new synthetic texture.
    known=1-cv2.dilate(m.astype('uint8'),np.ones((5,5),'uint8')).astype(float)
    denom=gaussian_filter(known,30)
    bg=np.stack([gaussian_filter(im[:,:,c]*known,30)/np.maximum(denom,1e-6) for c in range(3)],axis=2)
    peak=np.percentile(im[m],90,axis=0)
    alpha=np.clip((im[:,:,0]-bg[:,:,0])/(peak[0]-bg[:,:,0]+1e-6),0,1)
    alpha[alpha<.12]=0
    alpha=np.clip((alpha-.03)/.97,0,1)
    # Remove the low-frequency background color from fractional edge pixels.
    fg=(im.astype(float)-bg*(1-alpha[:,:,None]))/np.maximum(alpha[:,:,None],.015)
    fg=np.clip(fg,0,255).astype('uint8')
    rgba=np.dstack([fg,np.rint(alpha*255).astype('uint8')])
    x0,y0,x1,y1=box;pad=20;crop=rgba[max(0,y0-pad):min(len(im),y1+pad),max(0,x0-pad):min(im.shape[1],x1+pad)]
    Image.fromarray(crop).save(ASSETS/(key+'.png'))
    item={'key':key,'rgba':crop,'bbox':box,'source':p,'width':x1-x0,'height':y1-y0,
          'cx':(x0+x1)/2,'cy':(y0+y1)/2,'pad':pad,'scale':W/im.shape[1]}
    inputs.append(item)
    if background is None:
        # Keep the original blue texture, replacing the old lettering only.
        cleaned=im.copy();wide=cv2.dilate(m.astype('uint8'),np.ones((15,15),'uint8'))
        a=np.minimum(1,cv2.GaussianBlur(wide.astype('float32'),(0,0),3)*2)
        cleaned=np.rint(im*(1-a[:,:,None])+bg*a[:,:,None]).astype('uint8')
        cleaned[wide>0]=np.rint(bg[wide>0]).astype('uint8')
        background=np.asarray(Image.fromarray(cleaned).resize((W,H),Image.Resampling.LANCZOS))
        Image.fromarray(background).save(ASSETS/'background.png')

def ref_mask(f):
    im=image(WORK/'reference_frames'/f'frame_{f+1:03}.png')
    return ((im[:,:,0]>170)&(im[:,:,1]>35)&(im[:,:,2]<125)).astype('uint8')*255

def stage(f):
    if f<=10:return 0,5,f
    if f<=32:return 1,19,f
    if f<=53:return 2,41,f
    return 2,63,min(f,70)

def normalized_mask(f):
    x0,y0,x1,y1=METRICS[f]['bbox']
    return cv2.resize(ref_mask(f)[y0:y1,x0:x1],(NW,NH),interpolation=cv2.INTER_AREA)

anchors={a:normalized_mask(a) for a in [5,19,41,63]}
motion={};last_pose=None;pose_index=0
for f in range(80):
    word,anchor,rf=stage(f)
    # Ignore codec noise and retain the deliberately held source poses.
    if f>0 and METRICS[rf]['change']<.01 and stage(f-1)[:2]==(word,anchor):
        motion[f]=motion[f-1];continue
    current=normalized_mask(rf)
    flow=cv2.calcOpticalFlowFarneback(current,anchors[anchor],None,.5,4,49,5,7,1.5,0)
    # A coarse smooth displacement mesh transfers the broad reference motion
    # without optical-flow folds tearing the supplied raster letter outlines.
    flow=cv2.resize(cv2.resize(flow,(9,5),interpolation=cv2.INTER_AREA),(NW,NH),interpolation=cv2.INTER_CUBIC)
    flow=cv2.GaussianBlur(flow,(0,0),12)
    flow[:,:,0]=np.clip(flow[:,:,0],-NW*.035,NW*.035)
    flow[:,:,1]=np.clip(flow[:,:,1],-NH*.07,NH*.07)
    gyx,gxx=np.gradient(flow[:,:,0]);gyy,gxy=np.gradient(flow[:,:,1])
    gradient_norm=np.max(np.sqrt(gyx**2+gxx**2+gyy**2+gxy**2))
    if gradient_norm>.42:flow*=.42/gradient_norm
    b=np.array(METRICS[rf]['bbox'],dtype=float);ab=np.array(METRICS[anchor]['bbox'],dtype=float)
    bw,bh=b[2]-b[0],b[3]-b[1];aw,ah=ab[2]-ab[0],ab[3]-ab[1]
    motion[f]={'word':word,'anchor':anchor,'ref_frame':rf,'flow':flow,
               'sx':bw/aw,'sy':bh/ah,'dx':(b[0]+b[2]-ab[0]-ab[2])/2/aw,
               'dy':(b[1]+b[3]-ab[1]-ab[3])/2/ah,'pose':pose_index}
    pose_index+=1

metadata=[]
for f in range(N):
    reference_frame=min(79,int(f/SLOW));m=motion[reference_frame];src=inputs[m['word']]
    sx,sy=m['sx'],m['sy'];k=src['scale']
    width=src['width']*k*sx;height=src['height']*k*sy
    cx=src['cx']*k+m['dx']*src['width']*k
    cy=src['cy']*(H/941)+m['dy']*src['height']*k
    pad=96*k
    x0=max(0,int(math.floor(cx-width/2-pad)));x1=min(W,int(math.ceil(cx+width/2+pad)))
    y0=max(0,int(math.floor(cy-height/2-pad)));y1=min(H,int(math.ceil(cy+height/2+pad)))
    yy,xx=np.mgrid[y0:y1,x0:x1].astype('float32')
    u=(xx-(cx-width/2))/width;v=(yy-(cy-height/2))/height
    flow=cv2.remap(m['flow'],(u*NW).astype('float32'),(v*NH).astype('float32'),cv2.INTER_LINEAR,borderMode=cv2.BORDER_REPLICATE)
    # Transfer the original normalized local warp onto the new ink layer.
    mapx=(u+flow[:,:,0]/NW)*src['width']+src['pad']
    mapy=(v+flow[:,:,1]/NH)*src['height']+src['pad']
    layer=cv2.remap(src['rgba'],mapx.astype('float32'),mapy.astype('float32'),cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
    a=layer[:,:,3:4].astype('float32')/255
    frame=background.copy();frame[y0:y1,x0:x1]=np.rint(frame[y0:y1,x0:x1]*(1-a)+layer[:,:,:3]*a).astype('uint8')
    Image.fromarray(frame).save(OUT/f'frame_{f:04}.png',compress_level=2)
    metadata.append({'frame':f,'reference_time_frame':reference_frame,'reference_pose_frame':m['ref_frame'],'word':src['key'],
                     'scale_x':sx,'scale_y':sy,'pose':m['pose']})
    if f%15==0:print('FRAME',f,'WORD',src['key'],flush=True)

report={'fps':FPS,'frames':N,'resolution':[W,H],'duration_seconds':N/FPS,
        'time_scale':SLOW,'reference_frames':80,'reference_fps':30,
        'order':['УВИДЕЛ','КРИКНУЛ','ВЫИГРАЛ!'],
        'note':'Final uploaded image says ВЫИГРАЛ!, retained exactly. Silent reference audio omitted.',
        'source_images':[{'file':i['source'].name,'sha256':hashlib.sha256(i['source'].read_bytes()).hexdigest()} for i in inputs],
        'frame_motion':metadata}
(WORK/'animation_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print('RENDER COMPLETE',flush=True)
