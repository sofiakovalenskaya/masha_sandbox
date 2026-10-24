import bpy,hashlib,json,numpy as np
from pathlib import Path
root=Path(__file__).resolve().parent.parent;w=root/'paper_story_v1_fixed'
def action_signature(action,exclude=()):
 return [(fc.data_path,fc.array_index,[(tuple(k.co),tuple(k.handle_left),tuple(k.handle_right),k.interpolation) for k in fc.keyframe_points]) for fc in action.fcurves if fc.data_path not in exclude]
def snapshot(name):
 s=bpy.data.scenes[name];bpy.context.window.scene=s
 cards=sorted(next(c for c in s.collection.children if c.name.startswith('02')).objects,key=lambda o:o['deck_index'])
 carddata={o['deck_index']:{'rotation':action_signature(o.animation_data.action,('location','hide_render','hide_viewport')),'bends':action_signature(o.data.shape_keys.animation_data.action),'release':o['release_second'],'land':o['land_second'],'face':o['face_key'],'textures':[hashlib.sha256(n.image.packed_file.data).hexdigest() for m in o.data.materials for n in m.node_tree.nodes if n.type=='TEX_IMAGE']} for o in cards}
 cam=s.camera
 camera=[[fc.evaluate(f) for fc in cam.animation_data.action.fcurves] for f in range(1,346)]
 return carddata,np.array(camera)
bpy.ops.wm.open_mainfile(filepath=str(root/'tipo_paper_story_v1.blend'));original,camera=snapshot('TIPO_Paper_Story_v1')
bpy.ops.wm.open_mainfile(filepath=str(root/'tipo_paper_story_v1_fixed.blend'));fixed,fix_camera=snapshot('TIPO_Paper_Story_v1_fixed')
assert original==fixed,'Card rotations/bends/artwork/timing changed'
assert np.max(abs(camera-fix_camera))<1e-7,'Original close camera changed'
proof={'source_sha256':hashlib.sha256((root/'tipo_paper_story_v1.blend').read_bytes()).hexdigest(),'card_count_unchanged':61,'original_card_rotation_and_bend_actions_identical':True,'release_and_landing_times_identical':True,'original_card_artwork_identical':True,'original_camera_keys_identical_frames':[1,345]}
(w/'source_comparison.json').write_text(json.dumps(proof,indent=2));print('SOURCE PRESERVATION PASS',flush=True)
