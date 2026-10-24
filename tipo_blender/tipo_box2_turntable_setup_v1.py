# -*- coding: utf-8 -*-
"""ТИПО: коробка №2, оборот вокруг вертикальной оси, чёрный стол и фон.

Откройте утверждённую коробку №2 v4 и запустите этот код в Text Editor.
Также поддерживается v4 в одной папке с кодом. Исходные сцены не изменяются.
Готовая анимация сохраняется отдельным .blend в Downloads/TIPO_ANIMATION.
"""
import bpy
import math
import os
from datetime import datetime
from pathlib import Path
from mathutils import Vector

FPS = 30
SECONDS = 8
FRAME_COUNT = FPS * SECONDS
SIZE = int(os.environ.get('TIPO_LOOP_SIZE','1080'))
SAMPLES = int(os.environ.get('TIPO_LOOP_SAMPLES','32'))
OUTPUT_DIR = Path(os.environ.get('TIPO_LOOP_OUTPUT',str(Path.home()/'Downloads'/'TIPO_ANIMATION')))


def source_scene():
    name='TIPO_61_CARDS_СТОЯ_v4'
    if name in bpy.data.scenes:
        return bpy.data.scenes[name]
    folders=[]
    if bpy.data.filepath:folders.append(Path(bpy.data.filepath).parent)
    try:folders.append(Path(__file__).resolve().parent)
    except NameError:pass
    folders.append(Path.home()/'Downloads')
    for folder in folders:
        path=folder/'tipo_box_61_cards_v4.blend'
        if path.is_file():
            with bpy.data.libraries.load(str(path),link=False) as (available,loaded):
                if name not in available.scenes:continue
                loaded.scenes=[name]
            return loaded.scenes[0]
    raise FileNotFoundError('Откройте утверждённый tipo_box_61_cards_v4.blend и повторите запуск кода.')


def point_at(obj,target):
    obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()


def area_light(collection,name,location,target,power,size,size_y=None):
    data=bpy.data.lights.new(name,'AREA')
    data.energy=power
    data.shape='RECTANGLE' if size_y else 'DISK'
    data.size=size
    if size_y:data.size_y=size_y
    if hasattr(data,'use_shadow_jitter'):data.use_shadow_jitter=False
    obj=bpy.data.objects.new(name,data)
    collection.objects.link(obj)
    obj.location=location
    point_at(obj,target)
    return obj


def action_curves(action):
    # Blender 4.3 использует fcurves, более новые версии — channelbags.
    if hasattr(action,'fcurves'):
        return list(action.fcurves)
    result=[]
    for layer in action.layers:
        for strip in layer.strips:
            for channelbag in getattr(strip,'channelbags',[]):
                result.extend(channelbag.fcurves)
    return result


def build():
    source=source_scene()
    assert source['Карт внутри']==61
    # Сначала вычисляем трансформации именно стоящего варианта.
    # У неактивной сцены matrix_world после загрузки может быть ещё не обновлена.
    if bpy.context.window:bpy.context.window.scene=source
    source.frame_set(source.frame_current)
    bpy.context.view_layer.update()
    source_objects=[o for c in source.collection.children if c.name.startswith(('01','04')) for o in c.objects]
    assert all(o.parent is None and not o.constraints for o in source_objects)
    # У утверждённой модели нет родителей и constraints: basis — точная
    # сохранённая мировая матрица, независимая от кэша неактивной сцены.
    source_matrices={o.as_pointer():o.matrix_basis.copy() for o in source_objects}
    scene=bpy.data.scenes.new('TIPO_Box2_Turntable_v1')
    scene.use_fake_user=True
    scene.unit_settings.system='METRIC'
    scene.unit_settings.length_unit='MILLIMETERS'
    scene.unit_settings.scale_length=1.0
    model=bpy.data.collections.new('01 • Коробка №2 и 61 карта • вращение')
    stage=bpy.data.collections.new('02 • Чёрный стол, свет и неподвижная камера')
    scene.collection.children.link(model)
    scene.collection.children.link(stage)
    if bpy.context.window:bpy.context.window.scene=scene
    rig=bpy.data.objects.new('Ось вращения • вертикальная Z • центр основания',None)
    model.objects.link(rig)
    rig.empty_display_type='PLAIN_AXES'
    rig.empty_display_size=.02
    rig.location=(0,-.0135,0)
    rig.rotation_mode='XYZ'
    bpy.context.view_layer.update()
    originals=[]
    for collection in source.collection.children:
        if not collection.name.startswith(('01','04')):continue
        for original in collection.objects:
            assert original.type=='MESH'
            obj=original.copy()
            obj.data=original.data
            model.objects.link(obj)
            obj.parent=rig
            obj.matrix_parent_inverse=rig.matrix_basis.inverted()
            obj.matrix_basis=source_matrices[original.as_pointer()].copy()
            originals.append((original,obj))
    assert len(originals)==68,'Ожидались семь панелей коробки и 61 карта.'
    rig.rotation_euler=(0,0,0)
    rig.keyframe_insert(data_path='rotation_euler',frame=1)
    rig.rotation_euler.z=2*math.pi
    rig.keyframe_insert(data_path='rotation_euler',frame=FRAME_COUNT)
    curves=action_curves(rig.animation_data.action)
    assert curves,'Ключи вращения не созданы.'
    for curve in curves:
        for key in curve.keyframe_points:key.interpolation='LINEAR'
        curve.modifiers.new('CYCLES')
    scene.frame_start=1
    scene.frame_end=FRAME_COUNT
    scene.render.fps=FPS
    scene.render.fps_base=1
    scene.timeline_markers.new('НАЧАЛО • фронтальный вид',frame=1)
    scene.timeline_markers.new('КОНЕЦ • тот же фронтальный вид',frame=FRAME_COUNT)
    scene.frame_set(1)
    bpy.context.view_layer.update()
    for original,obj in originals:
        initial=source_matrices[original.as_pointer()]
        actual=rig.matrix_basis @ obj.matrix_parent_inverse @ obj.matrix_basis
        delta=max(abs(actual[r][c]-initial[r][c]) for r in range(4) for c in range(4))
        assert delta<1e-6,'Начальное положение модели изменилось.'

    table_material=bpy.data.materials.new('Стол • чистый матовый чёрный')
    table_material.use_nodes=True
    nodes=table_material.node_tree.nodes
    nodes.clear()
    diffuse=nodes.new('ShaderNodeBsdfDiffuse')
    diffuse.inputs['Color'].default_value=(0,0,0,1)
    diffuse.inputs['Roughness'].default_value=1
    output=nodes.new('ShaderNodeOutputMaterial')
    table_material.node_tree.links.new(diffuse.outputs[0],output.inputs['Surface'])
    mesh=bpy.data.meshes.new('Поверхность стола • Z = 0')
    mesh.from_pydata([(-1,-1,0),(1,-1,0),(1,1,0),(-1,1,0)],[],[(0,1,2,3)])
    table=bpy.data.objects.new('Чёрный стол • коробка стоит на поверхности',mesh)
    stage.objects.link(table)
    table.data.materials.append(table_material)
    world=bpy.data.worlds.new('Однотонный чёрный фон • RGB 000000')
    world.use_nodes=True
    world.node_tree.nodes['Background'].inputs['Color'].default_value=(0,0,0,1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value=0
    scene.world=world
    target=(0,-.0135,.0335)
    area_light(stage,'Ключевой софтбокс',(-.10,-.13,.15),target,.40,.13)
    area_light(stage,'Мягкое заполнение',(.11,-.08,.075),target,.15,.11)
    area_light(stage,'Контровой свет',(.025,.085,.12),target,.25,.10,.035)
    camera_data=bpy.data.cameras.new('Фронтальная камера • без наклона')
    camera=bpy.data.objects.new('Камера • неподвижная • прямо перед коробкой',camera_data)
    stage.objects.link(camera)
    camera.location=(0,-.30,.0335)
    point_at(camera,target)
    camera_data.type='ORTHO'
    camera_data.ortho_scale=.108
    camera_data.clip_start=.001
    camera_data.clip_end=10
    scene.camera=camera
    scene.render.engine='BLENDER_EEVEE_NEXT'
    scene.eevee.taa_render_samples=SAMPLES
    scene.eevee.use_taa_reprojection=False
    scene.eevee.use_raytracing=False
    if hasattr(scene.eevee,'use_gtao'):scene.eevee.use_gtao=True
    if hasattr(scene.eevee,'gtao_distance'):scene.eevee.gtao_distance=.003
    if hasattr(scene.eevee,'use_fast_gi'):scene.eevee.use_fast_gi=False
    if hasattr(scene.render,'use_motion_blur'):scene.render.use_motion_blur=False
    scene.render.resolution_x=scene.render.resolution_y=SIZE
    scene.render.resolution_percentage=100
    scene.render.film_transparent=False
    scene.view_settings.view_transform='Standard'
    scene.view_settings.look='None'
    scene.view_settings.exposure=0
    scene.view_settings.gamma=1
    scene.render.image_settings.file_format='FFMPEG'
    scene.render.ffmpeg.format='MPEG4'
    scene.render.ffmpeg.codec='H264'
    scene.render.ffmpeg.constant_rate_factor='HIGH'
    scene.render.ffmpeg.gopsize=1
    scene.render.ffmpeg.audio_codec='NONE'
    scene['Основа']='Утверждённая коробка №2 v4; геометрия и рисунки сохранены.'
    scene['Карт внутри']=61
    scene['Вращение']='Общий родитель: вертикальная Z через центр основания; постоянная скорость.'
    scene['Камера']='Неподвижная, фронтальная, на высоте центра коробки, без наклона.'
    scene['Петля']='Кадры 1 и 240 показывают одну позу: 0 и 360 градусов.'
    OUTPUT_DIR.mkdir(parents=True,exist_ok=True)
    path=OUTPUT_DIR/'tipo_box2_turntable_v1.blend'
    if path.exists():path=OUTPUT_DIR/('tipo_box2_turntable_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.blend')
    scene.render.filepath='//'+path.stem+'.mp4'
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                area.spaces.active.clip_start=.001
                area.spaces.active.region_3d.view_perspective='CAMERA'
                area.spaces.active.overlay.show_overlays=False
                area.spaces.active.shading.type='RENDERED'
    bpy.ops.wm.save_as_mainfile(filepath=str(path))
    print('TURNTABLE BLEND:',path,flush=True)
    print('MODEL:',len(originals),'objects; 61 cards; source meshes and materials unchanged.',flush=True)
    return scene


if __name__=='__main__':
    build()
