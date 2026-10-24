import bpy,json,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from pathlib import Path
s=bpy.data.scenes['TIPO_Paper_Story_v1_fixed'];bpy.context.window.scene=s
cards=sorted(next(c for c in s.collection.children if c.name.startswith('02')).objects,key=lambda o:o['deck_index'])
def bvh(obj,deps):
 ev=obj.evaluated_get(deps);m=ev.to_mesh()
 try:return BVHTree.FromPolygons([ev.matrix_world@v.co for v in m.vertices],[tuple(p.vertices) for p in m.polygons])
 finally:ev.to_mesh_clear()
contacts=[];count=0
for f in range(166,427):
 for sub in [.25,.5,.75]:
  s.frame_set(f,subframe=sub);deps=bpy.context.evaluated_depsgraph_get();visible=[o for o in cards if not o.hide_render];lo=[];hi=[]
  for o in visible:
   ev=o.evaluated_get(deps);v=np.array([ev.matrix_world@Vector(c) for c in ev.bound_box]);lo.append(v.min(axis=0));hi.append(v.max(axis=0))
  lo=np.array(lo);hi=np.array(hi);pairs=np.argwhere(np.triu(np.all(hi[:,None,:]>lo[None,:,:]+2e-6,axis=2)&np.all(hi[None,:,:]>lo[:,None,:]+2e-6,axis=2),1));cache={}
  for i,j in pairs:
   for k in [i,j]:
    if k not in cache:cache[k]=bvh(visible[k],deps)
   if cache[i].overlap(cache[j]):contacts.append([f+sub,visible[i]['deck_index'],visible[j]['deck_index']])
  count+=1
 if f%50==0:print('INTERMEDIATE',f,'contacts',len(contacts),flush=True)
root=Path(__file__).resolve().parent
(root/'intermediate_contacts.json').write_text(json.dumps(contacts))
(root/'intermediate_validation.json').write_text(json.dumps({'positions_checked':count,'mesh_intersections':len(contacts),'subframe_offsets':[.25,.5,.75],'frames':[166,426]},indent=2))
assert not contacts,str(contacts[:10])
print('INTERMEDIATE PASS',flush=True)
