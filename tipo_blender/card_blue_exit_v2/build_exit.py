"""Bent-paper anticipation and perspective whip to the right; separate shot."""
from pathlib import Path
import hashlib,json,math
import numpy as np
from PIL import Image,ImageDraw,ImageFilter
from scipy.interpolate import LinearNDInterpolator
from scipy.ndimage import map_coordinates

ROOT=Path(__file__).resolve().parent
PARENT=ROOT.parent
FRAMES=ROOT/'frames';FRAMES.mkdir(exist_ok=True)
W,H,FPS,SIDE=1920,1080,30,972
START_HOLD,WINDUP,EXIT,END_HOLD=3,15,18,24
source_final=PARENT/'card_scatter_v11/final_blue_back.png'
background=Image.open(PARENT/'card_blue_exit_v1/final_empty_pink.png').convert('RGBA')
art_path=PARENT/'card_scatter_v1/artwork/blue.png'
art=np.asarray(Image.open(art_path).convert('RGBA').resize((SIDE,SIDE),Image.Resampling.LANCZOS))
nodes=np.linspace(0,1,25)
uu,vv=np.meshgrid(nodes,nodes)
uv=np.column_stack([uu.ravel(),vv.ravel()])
texcoords=uv*(SIDE-1)

def smooth(u):return u*u*u*(10+u*(-15+6*u))

def geometry(center_x,bend):
    u,v=uv.T
    nx,ny=2*u-1,2*v-1
    # A shallow curved sheet: the upper edge leans right, the lower edge
    # leans left, with curved boundaries matching the supplied sketch.
    x=(u-.5)*SIDE-65*bend*ny
    y=(v-.5)*SIDE-25*bend*nx+32*bend*(1-nx*nx)
    z=190*abs(bend)+95*bend*(1-nx*nx)+55*bend*nx*ny
    yaw=math.radians(14*bend)
    xr=x*math.cos(yaw)+z*math.sin(yaw)
    zr=-x*math.sin(yaw)+z*math.cos(yaw)
    roll=math.radians(-2.5*bend)
    xp=xr*math.cos(roll)-y*math.sin(roll)
    yp=xr*math.sin(roll)+y*math.cos(roll)
    focal=4800
    projection=focal/(focal+zr)
    # Remove the center's apparent lateral drift from the yawed bend.
    center_shift=190*abs(bend)*math.sin(yaw)*focal/(focal+190*abs(bend)*math.cos(yaw))
    return np.column_stack([center_x+xp*projection-center_shift,540+yp*projection])

def render(center_x,bend):
    vertices=geometry(center_x,bend)
    left=max(0,int(np.floor(vertices[:,0].min()))-3)
    right=min(W,int(np.ceil(vertices[:,0].max()))+4)
    top=max(0,int(np.floor(vertices[:,1].min()))-3)
    bottom=min(H,int(np.ceil(vertices[:,1].max()))+4)
    if right<=left or bottom<=top:return background.convert('RGB')
    yy,xx=np.mgrid[top:bottom,left:right]
    inverse=LinearNDInterpolator(vertices,texcoords,fill_value=-100)
    coords=inverse(xx,yy)
    sample=[coords[:,:,1],coords[:,:,0]]
    rgba=np.stack([map_coordinates(art[:,:,c],sample,order=1,mode='constant',cval=0)
                   for c in range(4)],axis=-1).astype('uint8')
    # Delaunay interpolation spans the convex hull. Clip it to the curved
    # perimeter so the concave paper edge cannot acquire a straight bridge.
    grid=vertices.reshape(25,25,2)
    boundary=np.concatenate([grid[0],grid[1:,-1],grid[-1,-2::-1],grid[-2:0:-1,0]])
    mask=Image.new('L',((right-left)*2,(bottom-top)*2))
    ImageDraw.Draw(mask).polygon([((x-left)*2,(y-top)*2) for x,y in boundary],fill=255)
    mask=np.asarray(mask.resize((right-left,bottom-top),Image.Resampling.LANCZOS),dtype=np.uint16)
    rgba[:,:,3]=(rgba[:,:,3].astype(np.uint16)*mask//255).astype('uint8')
    layer=Image.new('RGBA',(W,H));layer.alpha_composite(Image.fromarray(rgba),(left,top))
    alpha=layer.getchannel('A').filter(ImageFilter.GaussianBlur(21.26+8*abs(bend)))
    shadow=Image.new('RGBA',(W,H),(60,34,10,0));shadow.putalpha(alpha.point(lambda a:round(a*.22)))
    canvas=background.copy()
    canvas.alpha_composite(shadow,(round(9+16*bend),round(21+15*abs(bend))))
    canvas.alpha_composite(layer)
    return canvas.convert('RGB')

def flight_state(u):
    u=max(0,min(1,u))
    # The loaded bend releases and briefly flexes the other way during launch.
    return 850+2050*u**1.6,(1-u)**2*math.cos(2*math.pi*u)

manifest=[]
def emit(image,phase,hold=1,**metadata):
    first=None
    for _ in range(hold):
        n=len(manifest);dest=FRAMES/f'frame_{n:04d}.png'
        if dest.exists():dest.unlink()
        if first is None:image.save(dest,compress_level=3);first=dest
        else:dest.hardlink_to(first)
        manifest.append({'frame':n,'phase':phase,'physical_card_side':SIDE,**metadata})

emit(Image.open(source_final).convert('RGB'),'matching_start',START_HOLD,
     card_center_x=960,bend=0)
for n in range(START_HOLD):
    path=FRAMES/f'frame_{n:04d}.png';path.unlink();path.hardlink_to(source_final)
for i in range(1,WINDUP+1):
    a=smooth(i/WINDUP);x=960-110*a
    verts=geometry(x,a)
    emit(render(x,a),'perspective_windup_left',card_center_x=x,bend=a,
         projected_bounds=[float(verts[:,0].min()),float(verts[:,1].min()),
                           float(verts[:,0].max()),float(verts[:,1].max())])
    print('WINDUP',i,round(a,3),flush=True)
Image.open(FRAMES/f'frame_{START_HOLD+WINDUP-1:04d}.png').save(ROOT/'windup_perspective.png',compress_level=3)
for i in range(1,EXIT+1):
    # Two close shutter samples add restrained motion blur during the whip.
    samples=[np.asarray(render(*flight_state((i+off)/EXIT)),dtype=np.float32)
             for off in [-.10,.10]]
    image=Image.fromarray(np.rint(np.mean(samples,axis=0)).astype('uint8'))
    x,bend=flight_state(i/EXIT)
    emit(image,'perspective_launch_right',card_center_x=x,bend=bend,motion_blur=True)
    print('EXIT',i,round(x,2),round(bend,3),flush=True)
emit(background.convert('RGB'),'empty_pink',END_HOLD,card_visible=False)
background.convert('RGB').save(ROOT/'final_empty_pink.png',compress_level=3)
assert len(manifest)==60
report={'source_video':'tipo_card_scatter_v11_flip_color_cycles_1080p.mp4',
        'separate_clip':True,'width':W,'height':H,'fps':FPS,'frames':60,'duration_seconds':2,
        'first_frame_png_matches_previous_final':True,
        'source_final_sha256':hashlib.sha256(source_final.read_bytes()).hexdigest(),
        'source_artwork_sha256':hashlib.sha256(art_path.read_bytes()).hexdigest(),
        'physical_card_side':SIDE,'mesh_grid':[25,25],'perspective_focal_px':4800,
        'max_windup_yaw_degrees':14,'max_windup_roll_degrees':-2.5,
        'anticipation_px':110,'windup_frames':WINDUP,'launch_frames':EXIT,
        'paper_bend_rebounds_on_launch':True,'empty_hold_frames':END_HOLD,
        'frame_map':manifest}
(ROOT/'animation_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print('COMPLETE',len(manifest),'frames',flush=True)
