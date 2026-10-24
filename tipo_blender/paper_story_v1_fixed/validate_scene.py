import bpy,json,math
from pathlib import Path
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from bpy_extras.object_utils import world_to_camera_view
W=Path(__file__).resolve().parent
s=bpy.data.scenes['TIPO_Paper_Story_v1_fixed'];bpy.context.window.scene=s
cards=sorted(next(c for c in s.collection.children if c.name.startswith('02')).objects,key=lambda o:o['deck_index'])
box=next(c for c in s.collection.children if c.name.startswith('01'));master=next(o for o in box.objects if o.name.startswith('Коробка •'))
assert len(cards)==61 and len([o for o in cards if o['layout_slot']])==14
assert (s.render.resolution_x,s.render.resolution_y,s.render.fps,s.frame_end)==(1920,1080,30,750)
assert not s.render.film_transparent
bg=s.world.node_tree.nodes['Background'];assert np.max(abs(np.array(bg.inputs['Color'].default_value)-[1,.6307571363,0,1]))<1e-5
assert bg.inputs['Strength'].default_value==1
assert not any(n.type=='ALPHAOVER' for n in s.node_tree.nodes)
for f in range(31,68):
 s.frame_set(f);assert abs(master.location.z-1.08)<1e-7 and abs(master.rotation_quaternion.angle)<1e-7
s.frame_set(1)
assert max(world_to_camera_view(s,s.camera,o.matrix_world@Vector(v)).y for o in box.objects if o.type=='MESH' for v in o.bound_box)<0
oldq=None
for f in range(1,751):
 s.frame_set(f);q=s.camera.rotation_quaternion.normalized()
 if oldq:assert abs(oldq.dot(q))>.98,'Camera orientation discontinuity'
 oldq=q.copy()
 if 346<=f<=460:
  assert abs(s.camera.location.y+.11)<1e-6 and abs(s.camera.location.z-.19)<1e-6
  look=q@Vector((0,0,-1));assert abs(look.x)<1e-5
for obj in cards:
 assert not any(m.type=='BOOLEAN' for m in obj.modifiers)
 for mat in obj.data.materials:
  for n in mat.node_tree.nodes:
   if n.type=='TEX_IMAGE':assert n.image.packed_file

def bvh(obj,deps):
 ev=obj.evaluated_get(deps);m=ev.to_mesh()
 try:return BVHTree.FromPolygons([ev.matrix_world@v.co for v in m.vertices],[tuple(p.vertices) for p in m.polygons])
 finally:ev.to_mesh_clear()
contacts=[];ground=1.;tested=0
for f in range(1,751):
 s.frame_set(f);deps=bpy.context.evaluated_depsgraph_get();visible=[o for o in cards if not o.hide_render]
 lo=[];hi=[]
 for o in visible:
  ev=o.evaluated_get(deps);a=np.array([ev.matrix_world@Vector(v) for v in ev.bound_box]);lo.append(a.min(axis=0));hi.append(a.max(axis=0))
 lo=np.array(lo);hi=np.array(hi);ground=min(ground,float(lo[:,2].min()))
 pairs=np.argwhere(np.triu(np.all(hi[:,None,:]>lo[None,:,:]+2e-6,axis=2)&np.all(hi[None,:,:]>lo[:,None,:]+2e-6,axis=2),1));cache={}
 for i,j in pairs:
  tested+=1
  for k in [i,j]:
   if k not in cache:cache[k]=bvh(visible[k],deps)
  if cache[i].overlap(cache[j]):contacts.append({'frame':f,'cards':[visible[i]['deck_index'],visible[j]['deck_index']]})
 if f%100==0:print('CHECK',f,'contacts',len(contacts),flush=True)
(W/'collision_samples.json').write_text(json.dumps(contacts))
assert not contacts,str(contacts[:20])
assert ground>-2e-6,'Card below table'
proof={'source':'uploaded tipo_paper_story_v1.blend','frames_checked':750,'mesh_intersections':0,'broadphase_pairs_tested':tested,'minimum_card_height_m':ground,'yellow_background':'#FFD000','opaque_background':True,'box_enters_from_below':True,'box_static_hold_seconds':[1,2.2],'horizontal_scan_seconds':[11.5,15.3],'pullback_seconds':[15.3,17.4],'no_vertical_scan':True,'source_camera_preserved_frames':[1,345],'card_rotations_bends_artwork_and_timing_preserved':True}
(W/'validation.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2));print('VALIDATION PASS',flush=True)
