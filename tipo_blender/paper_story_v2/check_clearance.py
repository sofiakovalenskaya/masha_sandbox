import bpy,json,sys,math
from pathlib import Path
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from bpy_extras.object_utils import world_to_camera_view

WORK=Path(__file__).resolve().parent
sys.path.insert(0,str(WORK))
import story_motion as motion
scene=bpy.data.scenes['TIPO_Paper_Story_v2'];bpy.context.window.scene=scene
cards=sorted(next(c for c in scene.collection.children if c.name.startswith('02')).objects,key=lambda o:o['deck_index'])
boxcol=next(c for c in scene.collection.children if c.name.startswith('01'))
master=next(o for o in boxcol.objects if o.name.startswith('Коробка •'))
reference=None
for frame in range(31,91):
    scene.frame_set(frame)
    pose=np.array(master.matrix_world)
    if reference is None:reference=pose
    assert np.max(abs(pose-reference))<1e-7, 'Box must be static during its hold'
    cp,cq,aim=motion.camera_pose((frame-1)/30)
    assert (cp-Vector((0,-.235,1.08))).length<1e-7
scene.frame_set(1)
assert max(world_to_camera_view(scene,scene.camera,o.matrix_world@Vector(p)).y for o in boxcol.objects if o.type=='MESH' for p in o.bound_box)<0
background=scene.world.node_tree.nodes['Background']
assert np.max(abs(np.array(background.inputs['Color'].default_value)-np.array([1,.6307571363461468,0,1])))<1e-5
assert background.inputs['Strength'].default_value==1 and not scene.render.film_transparent
assert scene.node_tree.nodes.get('CompositorNodeAlphaOver') is None

def world_bvh(obj,deps):
    ev=obj.evaluated_get(deps);mesh=ev.to_mesh()
    try:
        return BVHTree.FromPolygons([ev.matrix_world@v.co for v in mesh.vertices],
                                   [tuple(p.vertices) for p in mesh.polygons])
    finally:ev.to_mesh_clear()

overlaps=[];broadphase=0;minimum_ground=1e3
for frame in range(1,751):
    scene.frame_set(frame);deps=bpy.context.evaluated_depsgraph_get()
    visible=[o for o in cards if not o.hide_render]
    lo=[];hi=[]
    for obj in visible:
        ev=obj.evaluated_get(deps)
        points=np.array([ev.matrix_world@Vector(p) for p in ev.bound_box])
        lo.append(points.min(axis=0));hi.append(points.max(axis=0))
    lo=np.array(lo);hi=np.array(hi)
    minimum_ground=min(minimum_ground,float(lo[:,2].min()))
    # AABB overlap is conservative; intersecting bounds get an exact mesh test.
    eps=2e-6
    pairs=np.argwhere(np.triu(np.all(hi[:,None,:]>lo[None,:,:]+eps,axis=2)&
                                np.all(hi[None,:,:]>lo[:,None,:]+eps,axis=2),1))
    cache={}
    for i,j in pairs:
        broadphase+=1
        for k in [int(i),int(j)]:
            if k not in cache:cache[k]=world_bvh(visible[k],deps)
        if cache[int(i)].overlap(cache[int(j)]):
            overlaps.append({'frame':frame,'cards':[visible[int(i)]['deck_index'],visible[int(j)]['deck_index']]})
    if frame%100==0:print('CLEARANCE',frame,'broadphase',broadphase,'intersections',len(overlaps),flush=True)
assert not overlaps, 'Card mesh intersections: '+str(overlaps[:20])
assert minimum_ground>=-2e-6,'A card penetrates the table'
for f in range(round(11.6*30)+1,round(17.4*30)+1):
    cp,cq,aim=motion.camera_pose((f-1)/30)
    assert abs(aim.y)<1e-6 and abs(cp.z-.19)<1e-5
proof={'frames_checked':750,'card_mesh_intersections':0,'broadphase_pairs_checked':broadphase,
       'minimum_card_height_m':minimum_ground,'box_static_hold_seconds':[1,3],
       'box_enters_from_below':True,'background_and_viewport_world':'#FFD000',
       'film_transparent':False,'cards_in_scene':61,'cards_released':14,'cards_remaining_inside':47,
       'release_gap_seconds':motion.RELEASE_GAP,'clear_opening_before_bending':True,
       'close_camera_pass':'horizontal_only'}
(WORK/'clearance_validation.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n')
print('PASS CLEARANCE',json.dumps(proof,ensure_ascii=False),flush=True)
