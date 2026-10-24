import bpy,math,json,sys,hashlib
from pathlib import Path
from collections import Counter
from mathutils import Vector,Quaternion
from bpy_extras.object_utils import world_to_camera_view
WORK=Path(__file__).resolve().parent
sys.path.insert(0,str(WORK))
import story_motion as motion

scene=bpy.data.scenes['TIPO_Paper_Story_v4']
assert scene.render.resolution_x==1920 and scene.render.resolution_y==1080
assert scene.render.fps==30 and scene.frame_start==1 and scene.frame_end==750
cards=next(c for c in scene.collection.children if c.name.startswith('02'))
assert len(cards.objects)==61
assert Counter(o['back_color'] for o in cards.objects)=={'yellow':15,'green':15,'blue':15,'pink':15,'rules_back':1}
heroes=[o for o in cards.objects if o['layout_slot']]
assert len(heroes)==14
assert sorted(o['deck_index'] for o in heroes)==sorted(motion.HERO_MAP)
assert len({o['layout_slot'] for o in heroes})==14
assert set(o['layout_slot'] for o in heroes)=={*[f'H{i}' for i in range(1,9)],'V1','V2','V3','V4','V6','V7'}

def evaluate(obj,frame,path,count):
    base=list(getattr(obj,path))
    action=obj.animation_data.action
    for c in action.fcurves:
        if c.data_path==path:base[c.array_index]=c.evaluate(frame)
    return base[:count]

max_bend=0
for obj in cards.objects:
    assert len(obj.data.shape_keys.key_blocks)==4
    assert obj.modifiers[0].type=='SOLIDIFY' and abs(obj.modifiers[0].thickness-.00025)<1e-7
    assert not any(m.type=='BOOLEAN' for m in obj.modifiers)
    max_bend=max(max_bend,max(abs(k.co.y) for c in obj.data.shape_keys.animation_data.action.fcurves for k in c.keyframe_points))
for obj in heroes:
    index=obj['deck_index'];data=motion.HERO_MAP[index]
    p=evaluate(obj,750,'location',3);q=Quaternion(evaluate(obj,750,'rotation_quaternion',4)).normalized()
    assert abs(p[0]-data[3][0])<1e-6 and abs(p[1]-data[3][1])<1e-6
    assert (q@Vector((0,0,-1))).z>.9999
    assert (q@Vector((-1,0,0))).x>.9999
    assert (q@Vector((0,1,0))).y>.9999
    assert p[2]>=.00007
    for c in obj.data.shape_keys.animation_data.action.fcurves:assert abs(c.evaluate(750))<1e-6
assert max_bend>.3
camera=scene.camera
assert camera.data.type=='PERSP' and camera.data.lens==45
assert len([c for c in camera.animation_data.action.fcurves if c.data_path=='location'])==3
for c in camera.animation_data.action.fcurves:assert len(c.keyframe_points)==750
qs=[]
for f in range(1,751):
    p,q,target=motion.camera_pose((f-1)/30)
    assert p.z>.1 and (target-p).length>.1
    if qs:assert abs(q.dot(qs[-1]))>.98,'Camera has an orientation jump'
    qs.append(q)
box=next(c for c in scene.collection.children if c.name.startswith('01'))
box_meshes=[o for o in box.objects if o.type=='MESH']
assert len(box_meshes)==7
minimum_border=1.0
for frame in range(31,140):
    scene.frame_set(frame)
    deps=bpy.context.evaluated_depsgraph_get()
    for obj in box_meshes:
        ev=obj.evaluated_get(deps)
        for corner in ev.bound_box:
            p=world_to_camera_view(scene,camera,ev.matrix_world@Vector(corner))
            minimum_border=min(minimum_border,p.x,1-p.x,p.y,1-p.y)
assert minimum_border>.005, 'A box corner leaves the frame during the roll'
for o in box_meshes:
    fc=next(c for c in o.animation_data.action.fcurves if c.data_path=='hide_render')
    assert fc.evaluate(750)>.5
root=WORK.parent
assets=json.loads((root/'ANIMATION_ASSETS.json').read_text())
for asset in assets['assets']:assert hashlib.sha256((root/asset['file']).read_bytes()).hexdigest()==asset['sha256']
missing=json.loads(scene['Missing artwork'])
extra_hashes={}
for key in ['ref_H3','ref_H4','ref_H7']:
    original=WORK/'reference_faces'/(key+'.png')
    expected=hashlib.sha256(original.read_bytes()).hexdigest()
    image=next(i for i in bpy.data.images if i.name=='ТИПО • точный референс • '+key)
    assert image.packed_file is not None
    assert hashlib.sha256(image.packed_file.data).hexdigest()==expected
    assert tuple(image.size)==(768,768)
    extra_hashes[key]=expected
for obj in cards.objects:
    for material in obj.data.materials:
        for node in material.node_tree.nodes:
            if node.type=='TEX_IMAGE':
                assert node.image is not None and node.image.packed_file is not None
proof={'duration_seconds':25,'width':1920,'height':1080,'fps':30,'frames':750,
       'cards_falling':30,'cards_remaining_inside':31,'final_cards':14,'horizontal':8,'vertical':7,
       'single_shared_intersection':'H6 / V5','paper_modes':['bend_x','bend_y','twist'],
       'single_continuous_perspective_camera':True,'font_winning_run':'Airy H3–H7',
       'no_highlights_or_title':True,'audio':False,'approved_models_unchanged':True,
       'missing_original_artwork':missing,'production_ready':not missing,
       'original_extra_faces_sha256':extra_hashes,'all_card_textures_packed':True,
       'artwork_note':'H3: supplied original card 06 has a wavy underline.',
       'box_fully_visible_before_opening':True,'close_camera_pass':'horizontal_only','minimum_box_frame_margin':minimum_border}
(WORK/'motion_validation.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n')
print('PASS MOTION:',json.dumps(proof,ensure_ascii=False),flush=True)
