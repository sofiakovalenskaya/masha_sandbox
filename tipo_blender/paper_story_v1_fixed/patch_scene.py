"""Edit the supplied first project; retain its card rotations, bends and release times."""
import bpy,os,math,json,hashlib
from pathlib import Path
import numpy as np
from mathutils import Vector,Matrix
WORK=Path(__file__).resolve().parent;ROOT=WORK.parent
SOURCE=Path(os.environ.get('TIPO_V1_SOURCE',str(ROOT/'tipo_paper_story_v1.blend')))
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()=='0d50306e825fac218604ab67b4f12788060b3e9fe2bf5f1f238f5169eedc2c2e'
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
s=bpy.data.scenes['TIPO_Paper_Story_v1'];bpy.context.window.scene=s
cards=sorted(next(c for c in s.collection.children if c.name.startswith('02')).objects,key=lambda o:o['deck_index'])
box=next(c for c in s.collection.children if c.name.startswith('01'))
master=next(o for o in box.objects if o.name.startswith('Коробка •'))
def linear(code):
 a=np.array([int(code[i:i+2],16)/255 for i in [1,3,5]])
 return (*np.where(a<=.04045,a/12.92,((a+.055)/1.055)**2.4),1.)
def smooth(x):
 x=max(0,min(1,x));return x*x*(3-2*x)
def smoother(x):
 x=max(0,min(1,x));return x*x*x*(x*(x*6-15)+10)
def channels(obj,path):return [c for c in obj.animation_data.action.fcurves if c.data_path==path]
def sample(obj,path):
 cs=channels(obj,path)
 return np.array([[next(c for c in cs if c.array_index==a).evaluate(f) for a in range(3)] for f in range(1,751)])
def set_locations(obj,values,frames=None):
 if frames is None:frames=np.arange(1,len(values)+1)
 action=obj.animation_data.action
 for c in list(action.fcurves):
  if c.data_path=='location':action.fcurves.remove(c)
 for a in range(3):
  fc=action.fcurves.new('location',index=a);fc.keyframe_points.add(len(values))
  for f,k in enumerate(fc.keyframe_points):
   k.co=(float(frames[f]),float(values[f,a]));k.interpolation='BEZIER';k.handle_left_type=k.handle_right_type='AUTO_CLAMPED'
  fc.update()
# Only replace box translation. Preserve the original flip and opening actions.
old=sample(master,'location');new=old.copy()
for k in range(750):new[k,2]=.90+.18*smoother((k/30)/1.0)
set_locations(master,new)
corrections=json.loads((WORK/'motion_offsets.json').read_text()) if (WORK/'motion_offsets.json').exists() else {}
refine=json.loads((WORK/'separation_refinement.json').read_text()) if (WORK/'separation_refinement.json').exists() else None
continuous=json.loads((WORK/'continuous_separation.json').read_text()) if (WORK/'continuous_separation.json').exists() else None
manifest=[]
for obj in cards:
 idx=obj['deck_index'];p=sample(obj,'location');release=obj['release_second'];land=obj['land_second']
 for k in range(750):
  if k/30<=release:p[k]+=new[k]-old[k]
 data=corrections.get(str(idx))
 if data:
  ts=np.array(data['t']);coef=np.array(data['c'])
  for k in range(750):
   t=k/30
   if not ts[0]<t<ts[-1]:continue
   j=int(np.searchsorted(ts,t)-1);u=t-ts[j]
   p[k]+=((coef[0,j]*u+coef[1,j])*u+coef[2,j])*u+coef[3,j]
 set_locations(obj,p)
 if refine:
  fine_frames=np.arange(1,750.001,.5);fine_times=(fine_frames-1)/30
  fc=channels(obj,'location');fine_positions=np.array([[next(c for c in fc if c.array_index==a).evaluate(float(f)) for a in range(3)] for f in fine_frames])
  extra=np.array(refine['offsets'])[:,idx,:]
  for a in range(3):fine_positions[:,a]+=np.interp(fine_times,refine['times'],extra[:,a],left=0,right=0)
  set_locations(obj,fine_positions,fine_frames)
 if continuous:
  quarter_frames=np.arange(1,750.001,.25);quarter_times=(quarter_frames-1)/30
  fc=channels(obj,'location');positions=np.array([[next(c for c in fc if c.array_index==a).evaluate(float(f)) for a in range(3)] for f in quarter_frames])
  extra=np.array(continuous['offsets'])[:,idx,:]
  for a in range(3):positions[:,a]+=np.interp(quarter_times,continuous['times'],extra[:,a],left=0,right=0)
  set_locations(obj,positions,quarter_frames)
 manifest.append({'index':idx,'release':release,'land':land,'hero':obj['layout_slot'],'face':obj['face_key'],'back':obj['back_color']})
# One opaque yellow environment, including the material-preview viewport.
yellow=linear('#FFD000');world=bpy.data.worlds.new('Жёлтый фон • FFD000');world.use_nodes=True;world.color=yellow[:3]
n=world.node_tree.nodes;l=world.node_tree.links;n.clear()
bg=n.new('ShaderNodeBackground');bg.name='Background';bg.inputs['Color'].default_value=yellow;bg.inputs['Strength'].default_value=1
neutral=n.new('ShaderNodeBackground');neutral.inputs['Color'].default_value=(1,1,1,1);neutral.inputs['Strength'].default_value=.15
path=n.new('ShaderNodeLightPath');mix=n.new('ShaderNodeMixShader');out=n.new('ShaderNodeOutputWorld')
l.new(path.outputs['Is Camera Ray'],mix.inputs[0]);l.new(neutral.outputs[0],mix.inputs[1]);l.new(bg.outputs[0],mix.inputs[2]);l.new(mix.outputs[0],out.inputs[0]);s.world=world
stage=next(c for c in s.collection.children if c.name.startswith('03'));stage.name='03 • Жёлтый стол, свет и камера'
table=next(o for o in stage.objects if o.type=='MESH');table.name='Жёлтый стол'
mat=table.data.materials[0];mat.name='Фирменный жёлтый стол • FFD000';mat.diffuse_color=yellow
for node in mat.node_tree.nodes:
 if node.type=='EMISSION':node.inputs['Color'].default_value=yellow;node.inputs['Strength'].default_value=.859155
 if node.type=='BSDF_DIFFUSE':node.inputs['Color'].default_value=tuple(c*.12 if i<3 else 1 for i,c in enumerate(yellow))
s.render.film_transparent=False;s.render.dither_intensity=0
s.node_tree.animation_data_clear()
n=s.node_tree.nodes;l=s.node_tree.links;n.clear();rl=n.new('CompositorNodeRLayers');out=n.new('CompositorNodeComposite');l.new(rl.outputs['Image'],out.inputs[0])
# Keep all original close-flight camera keys up to the start of the horizontal scan.
cam=s.camera;cut=346
for fc in cam.animation_data.action.fcurves:
 while len(fc.keyframe_points) and fc.keyframe_points[-1].co.x>=cut:
  fc.keyframe_points.remove(fc.keyframe_points[-1],fast=True)
 fc.update()
PITCH=.065*848/768
knots=[(11.5,(-3*PITCH,-.11,.19),(-3*PITCH,0,.001))]
for i in range(1,8):
 x=(i-3.5)*PITCH;knots.append((11.5+i*.5,(x,-.11,.19),(x,0,.001)))
knots +=[(15.3,(3.5*PITCH,-.11,.19),(3.5*PITCH,0,.001)),(16.,(.10,-.08,.65),(.03,.04,0)),(17.4,(0,PITCH,1.35),(0,PITCH,0))]
def path_at(t,which):
 ts=np.array([k[0] for k in knots]);ps=np.array([k[which] for k in knots]);ms=np.zeros_like(ps)
 for i in range(1,len(ts)-1):
  if np.allclose(ps[i-1],ps[i]) or np.allclose(ps[i+1],ps[i]):continue
  ms[i]=(ps[i+1]-ps[i-1])/(ts[i+1]-ts[i-1])
 if t<=ts[0]:return Vector(ps[0])
 if t>=ts[-1]:return Vector(ps[-1])
 i=int(np.searchsorted(ts,t)-1);dt=ts[i+1]-ts[i];u=(t-ts[i])/dt
 return Vector((2*u**3-3*u*u+1)*ps[i]+(u**3-2*u*u+u)*dt*ms[i]+(-2*u**3+3*u*u)*ps[i+1]+(u**3-u*u)*dt*ms[i+1])
prev=None
for f in range(cut,751):
 t=(f-1)/30;p=path_at(t,1);a=path_at(t,2);forward=(a-p).normalized();u=smooth((t-15.3)/2.1)
 up_hint=Vector((0,u,1-u)).normalized();right=forward.cross(up_hint).normalized();up=right.cross(forward).normalized()
 q=Matrix(((right.x,up.x,-forward.x),(right.y,up.y,-forward.y),(right.z,up.z,-forward.z))).to_quaternion()
 if prev is not None and prev.dot(q)<0:q.negate()
 prev=q.copy();cam.location=p;cam.rotation_quaternion=q;cam.keyframe_insert('location',frame=f);cam.keyframe_insert('rotation_quaternion',frame=f)
for fc in cam.animation_data.action.fcurves:
 for key in fc.keyframe_points:
  if key.co.x>=cut:key.interpolation='LINEAR'
for marker in list(s.timeline_markers):
 if marker.frame>=346:s.timeline_markers.remove(marker)
for f,name in [(346,'Только горизонтальный ряд'),(460,'Быстрый отъезд'),(523,'Общий план')]:s.timeline_markers.new(name,frame=f)
s.name='TIPO_Paper_Story_v1_fixed';s['Основа']='Прикреплённый v1, SHA-256 0d50306e825fac218604ab67b4f12788060b3e9fe2bf5f1f238f5169eedc2c2e';s['Сценарий']='v1: жёлтый фон, статичное зависание, выезд снизу, разделение карт, горизонтальный пролёт и быстрый отъезд.'
s.frame_set(1);s.render.resolution_percentage=100;s.render.image_settings.file_format='FFMPEG';s.render.image_settings.color_mode='RGB';s.render.ffmpeg.format='MPEG4';s.render.ffmpeg.codec='H264';s.render.ffmpeg.audio_codec='NONE';s.render.filepath='//tipo_paper_story_v1_fixed.mp4'
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':
   space=area.spaces.active;space.region_3d.view_perspective='CAMERA';space.overlay.show_overlays=False;space.shading.type='MATERIAL';space.shading.use_scene_world=True;space.shading.use_scene_lights=True;space.shading.background_type='WORLD';space.shading.background_color=yellow[:3];space.shading.studiolight_background_alpha=1
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'tipo_paper_story_v1_fixed.blend'),compress=True)
(WORK/'card_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
print('PATCHED ORIGINAL V1',flush=True)
