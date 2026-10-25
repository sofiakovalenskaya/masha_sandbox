"""Render only the corrected horizontal-row pullback, starting at the blue Ж."""
from pathlib import Path
import bpy,os,json,hashlib,time
from mathutils import Vector,Quaternion
from bpy_extras.object_utils import world_to_camera_view

ROOT=Path(__file__).resolve().parent
PARENT=ROOT.parent
SOURCE=PARENT/'tipo_paper_story_v1_fixed.blend'
SOURCE_HASH='44d494117090ffd704107ff00682643d82b462190e473e14d0b461d5e686de68'
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==SOURCE_HASH
s=bpy.data.scenes['TIPO_Paper_Story_v1_fixed'];bpy.context.window.scene=s
cam=s.camera
START,CUT,END,FINISH=451,460,505,535
preview=os.environ.get('TIPO_HORIZONTAL_PREVIEW')=='1'
original_frames=Path(os.environ.get('TIPO_SOURCE_FHD_FRAMES','/workspace/tipo_fullhd_work/render_frames'))

prefix=[]
for f in range(START,CUT+1):
    s.frame_set(f)
    prefix.append((f,cam.location.copy(),cam.rotation_quaternion.copy()))
start_pos,start_q=prefix[-1][1:]
heroes=[o for o in s.objects if o.get('layout_slot')]
row=sorted([o for o in heroes if str(o['layout_slot']).startswith('H')],key=lambda o:o['layout_slot'])
assert len(row)==8
card_state={o.name:{'location':list(o.location),'rotation':list(o.rotation_quaternion),
                    'scale':list(o.scale),'face':o.get('face_key'),'slot':o.get('layout_slot')}
            for o in heroes}
points=[o.matrix_world@Vector(v) for o in row for v in o.bound_box]
cam.animation_data_clear();cam.rotation_mode='QUATERNION'
target_q=Quaternion((1,0,0,0))
cam.rotation_quaternion=target_q

def row_projection(height):
    cam.location=(0,0,height);bpy.context.view_layer.update()
    ps=[world_to_camera_view(s,cam,p) for p in points]
    return [min(p.x for p in ps),min(p.y for p in ps),max(p.x for p in ps),max(p.y for p in ps)]

low,high=.6,1.1
for _ in range(36):
    mid=(low+high)/2
    box=row_projection(mid)
    if box[2]-box[0]>.90:low=mid
    else:high=mid
target_pos=Vector((0,0,(low+high)/2))
final_projection=row_projection(target_pos.z)
assert abs((final_projection[2]-final_projection[0])-.90)<1e-6

def smooth(u):return u*u*u*(10+u*(-15+6*u))
poses=[]
for f in range(START,FINISH+1):
    if f<=CUT:
        _,pos,q=prefix[f-START]
        phase='original_blue_zh_closeup'
    else:
        u=min(1,(f-CUT)/(END-CUT));e=smooth(u)
        pos=start_pos.lerp(target_pos,e);q=start_q.slerp(target_q,e)
        phase='closer_horizontal_pullback' if f<=END else 'horizontal_row_hold'
    cam.location=pos;cam.rotation_quaternion=q
    cam.keyframe_insert('location',frame=f);cam.keyframe_insert('rotation_quaternion',frame=f)
    poses.append({'output_frame':f-START,'source_frame':f,'phase':phase,
                  'camera_position':list(pos),'camera_quaternion':list(q)})
for fc in cam.animation_data.action.fcurves:
    for k in fc.keyframe_points:k.interpolation='LINEAR'
s.render.resolution_x=1920;s.render.resolution_y=1080;s.render.resolution_percentage=100
s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGB'
s.render.image_settings.color_depth='8';s.render.image_settings.compression=15
s.render.filepath='//paper_story_horizontal_pullback_v1/frames/render_'
s.frame_start=START;s.frame_end=FINISH;s.frame_set(START)
if not preview:
    bpy.ops.wm.save_as_mainfile(filepath=str(PARENT/'tipo_paper_story_horizontal_close_pullback_v1.blend'),compress=True)
folder=ROOT/('preview' if preview else 'frames');folder.mkdir(exist_ok=True)
if preview:s.render.resolution_percentage=35
to_render=[START,475,490,END] if preview else list(range(START,FINISH+1))
for f in to_render:
    dest=folder/f'frame_{f-START:04d}.png'
    if dest.exists():continue
    if not preview and f<=CUT:
        dest.hardlink_to(original_frames/f'frame_{f:04d}.png')
    elif not preview and f>END:
        dest.hardlink_to(folder/f'frame_{END-START:04d}.png')
    else:
        s.frame_set(f);s.eevee.taa_render_samples=16 if f==END else 4
        s.render.filepath=str(dest);begin=time.monotonic();bpy.ops.render.render(write_still=True)
        print('FRAGMENT_FRAME',f-START,'SOURCE',f,'SECONDS',round(time.monotonic()-begin,2),flush=True)

s.frame_set(END)
final_bounds={}
for o in heroes:
    ps=[world_to_camera_view(s,cam,o.matrix_world@Vector(v)) for v in o.bound_box]
    final_bounds[o['layout_slot']]=[min(p.x for p in ps),min(p.y for p in ps),
                                   max(p.x for p in ps),max(p.y for p in ps)]
if not preview:
    (ROOT/'final_horizontal_row.png').write_bytes((folder/f'frame_{END-START:04d}.png').read_bytes())
    report={'source_project':SOURCE.name,'source_project_sha256':SOURCE_HASH,
            'separate_fragment':True,'width':1920,'height':1080,'fps':30,'frames':FINISH-START+1,
            'duration_seconds':(FINISH-START+1)/30,'source_start_frame':START,
            'source_start_seconds':(START-1)/30,'matching_letter':'blue Ж • H8 • face_52',
            'unchanged_prefix_source_frames':[START,CUT],'pullback_frames':END-CUT,
            'final_hold_frames':FINISH-END,'final_horizontal_row_width_fraction':.9,
            'final_horizontal_row_bounds':final_projection,'final_card_bounds':final_bounds,
            'final_camera_height_m':target_pos.z,'original_final_camera_height_m':1.35,
            'cards_materials_background_unchanged':True,'original_card_state':card_state,
            'frame_map':poses}
    (ROOT/'animation_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print('PREVIEW COMPLETE' if preview else 'FRAGMENT COMPLETE',flush=True)
