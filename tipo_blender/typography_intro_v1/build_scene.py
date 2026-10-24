"""Create a self-contained editable Blender project with individual glyphs."""
import bpy, sys, math
from pathlib import Path
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
import animate as A

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.preferences.filepaths.save_version=0
s=bpy.context.scene;s.name='TIPO_Typography_Intro_v1'
s.render.engine='BLENDER_EEVEE_NEXT';s.eevee.taa_render_samples=32
s.render.resolution_x=1920;s.render.resolution_y=1080;s.render.resolution_percentage=100
s.render.fps=30;s.frame_start=1;s.frame_end=270
s.view_settings.view_transform='Standard';s.view_settings.look='None';s.view_settings.exposure=0;s.view_settings.gamma=1
s.render.dither_intensity=0;s.render.film_transparent=False
def linear(v):
    v=v/255;return v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4
yellow=tuple(linear(v) for v in A.DATA['background'])+(1,)
world=bpy.data.worlds.new('Фирменный жёлтый • FFD000');world.use_nodes=True
world.node_tree.nodes['Background'].inputs['Color'].default_value=yellow
world.node_tree.nodes['Background'].inputs['Strength'].default_value=1;s.world=world
camdata=bpy.data.cameras.new('Камера • Full HD');cam=bpy.data.objects.new('Камера',camdata);s.collection.objects.link(cam)
cam.location=(0,0,100);camdata.type='ORTHO';camdata.ortho_scale=1920;camdata.clip_end=1000;s.camera=cam

def collection(name):
    c=bpy.data.collections.new(name);s.collection.children.link(c);return c
letters=collection('01 • Отдельные буквы');variants=collection('02 • Четыре варианта О');punctuation=collection('03 • Покадровый !');boxcol=collection('04 • Коробка — точный кадр стыка')
mats={}
def material(filename):
    if filename in mats:return mats[filename]
    image=bpy.data.images.load(str(ROOT/'assets'/filename),check_existing=True);image.pack()
    mat=bpy.data.materials.new(filename);mat.use_nodes=True
    mat.surface_render_method='DITHERED';mat.use_transparent_shadow=False
    n=mat.node_tree.nodes;n.clear();l=mat.node_tree.links
    tex=n.new('ShaderNodeTexImage');tex.image=image;tex.interpolation='Linear';tex.extension='CLIP'
    emission=n.new('ShaderNodeEmission');transparent=n.new('ShaderNodeBsdfTransparent');mix=n.new('ShaderNodeMixShader');out=n.new('ShaderNodeOutputMaterial')
    l.new(tex.outputs['Color'],emission.inputs['Color']);l.new(tex.outputs['Alpha'],mix.inputs[0]);l.new(transparent.outputs[0],mix.inputs[1]);l.new(emission.outputs[0],mix.inputs[2]);l.new(mix.outputs[0],out.inputs['Surface'])
    mats[filename]=mat;return mat

def plane(name,asset,col,z):
    mesh=bpy.data.meshes.new(name);mesh.from_pydata([(-.5,-.5,0),(.5,-.5,0),(.5,.5,0),(-.5,.5,0)],[],[(0,1,2,3)]);mesh.update()
    uv=mesh.uv_layers.new()
    for loop,co in zip(uv.data,[(0,0),(1,0),(1,1),(0,1)]):loop.uv=co
    ob=bpy.data.objects.new(name,mesh);col.objects.link(ob);mesh.materials.append(material(asset));ob['source_asset']=asset;ob['layer_z']=z;return ob

items=[]
for g in A.DATA['letters']:
    if g['id']==A.DATA['o_glyph_id']:continue
    ob=plane(f'{g["id"]+1:02} • {g["letter"]}',g['asset'],letters,2);ob['group']=g['group'];items.append((ob,g,None))
for index,v in enumerate(A.DATA['o_variants']):
    ob=plane(f'О • вариант {index+1}',v['asset'],variants,2)
    g=next(g for g in A.DATA['letters'] if g['id']==A.DATA['o_glyph_id']);items.append((ob,g,index))
g=A.DATA['exclamation'];ob=plane('! • покадровые позы',g['asset'],punctuation,2);items.append((ob,g,None))
box=plane('Коробка №2 • кадр 31 предыдущего ролика',A.DATA['box']['asset'],boxcol,1)
box['seam_reference_frame']=31;box['seam_continuation_frame']=32

def key_pose(ob,p,f):
    hidden=p is None;ob.hide_render=hidden;ob.hide_viewport=hidden
    ob.keyframe_insert('hide_render',frame=f);ob.keyframe_insert('hide_viewport',frame=f)
    if hidden:return
    x,y=p['center'];w,h=p['size'];ob.location=(x-960,540-y,ob['layer_z']);ob.scale=(w,h,1);ob.rotation_euler=(0,0,-math.radians(p['angle']))
    for channel in ['location','scale','rotation_euler']:ob.keyframe_insert(channel,frame=f)

for f in range(1,271):
    t=(f-1)/30
    for ob,g,index in items:
        p=A.pose(g,t)
        if index is not None and A.variant_at(t)!=index:p=None
        key_pose(ob,p,f)
    key_pose(box,A.box_pose(t),f)
for ob,g,index in items+[(box,None,None)]:
    for fc in ob.animation_data.action.fcurves:
        for key in fc.keyframe_points:
            key.interpolation='CONSTANT' if fc.data_path.startswith('hide_') or (g and g['group']=='exclamation' and key.co.x<1+A.BURST[g['id']]['start']*30) else 'LINEAR'

for name,t in [('ВИЗУАЛЬНАЯ',.3),('ИГРА',1.2),('НА',2.1),('ВНИМАТЕЛЬНОСТЬ',2.4),('Два круга О',3.4),('Покадровый !',134/30),('Коробка и разлёт букв',6),('Точный стык с кадром 31',8.4)]:s.timeline_markers.new(name,frame=round(t*30)+1)
s['Сценарий']='Появление слов на месте; четыре О дважды; покадровый !; разлёт отдельных букв от коробки.'
s['Стык']='Финал соответствует кадру 31 tipo_paper_story_v1_fixed. Продолжение — с кадра 32 (00:01.033333).'
s['Источник рисунков']='Пять PNG из пользовательского архива анимация буквы.zip. Все изображения упакованы.'
s.render.image_settings.file_format='FFMPEG';s.render.ffmpeg.format='MPEG4';s.render.ffmpeg.codec='H264';s.render.ffmpeg.constant_rate_factor='HIGH';s.render.ffmpeg.audio_codec='NONE';s.render.filepath='//tipo_typography_intro_v1_1080p.mp4'
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.region_3d.view_perspective='CAMERA';area.spaces.active.overlay.show_overlays=False;area.spaces.active.shading.type='MATERIAL';area.spaces.active.shading.use_scene_world=True
s.frame_set(166)
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(ROOT.parent/'tipo_typography_intro_v1.blend'),compress=True)
print('EDITABLE INTRO SAVED',flush=True)
