import bpy,math,json,os,sys,hashlib
from pathlib import Path
import numpy as np
from mathutils import Vector,Matrix,Quaternion

WORK=Path(__file__).resolve().parent
ROOT=WORK.parent
sys.path.insert(0,str(WORK))
import story_motion as motion

ALLOW_MISSING=os.environ.get('TIPO_ALLOW_PLACEHOLDER','0')=='1'
SIZE_PERCENT=int(os.environ.get('TIPO_STORY_PERCENT','100'))
SAMPLES=int(os.environ.get('TIPO_STORY_SAMPLES','4'))
PINK='#FF006F'

def linear(hexcode):
    a=np.array([int(hexcode[i:i+2],16)/255 for i in (1,3,5)])
    return (*np.where(a<=.04045,a/12.92,((a+.055)/1.055)**2.4),1.)

def point_at(obj,target):obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()

def curves(action):
    if hasattr(action,'fcurves'):return list(action.fcurves)
    return [c for layer in action.layers for strip in layer.strips for bag in strip.channelbags for c in bag.fcurves]

def polish_action(action,linear_keys=False):
    for curve in curves(action):
        for key in curve.keyframe_points:
            key.interpolation='LINEAR' if linear_keys else 'BEZIER'
            if not linear_keys:key.handle_left_type=key.handle_right_type='AUTO_CLAMPED'

def paper_material(name,image=None,front=False,edge=False):
    m=bpy.data.materials.new(name);m.use_nodes=True
    m.diffuse_color=linear('#FFFCF4')
    nodes=m.node_tree.nodes;links=m.node_tree.links
    nodes.clear();out=nodes.new('ShaderNodeOutputMaterial');out.location=(600,0)
    shader=nodes.new('ShaderNodeBsdfPrincipled');shader.location=(300,0)
    shader.inputs['Base Color'].default_value=linear('#EEE8DC' if edge else '#FFFCF4')
    shader.inputs['Roughness'].default_value=.78 if edge else .43
    shader.inputs['IOR'].default_value=1.46
    shader.inputs['Specular IOR Level'].default_value=.28
    shader.inputs['Coat Weight'].default_value=0 if edge else .10
    shader.inputs['Coat Roughness'].default_value=.35
    shader.inputs['Sheen Weight'].default_value=0 if edge else .08
    links.new(shader.outputs[0],out.inputs['Surface'])
    if image:
        uv=nodes.new('ShaderNodeUVMap');uv.uv_map='Card UV';uv.location=(-900,0)
        texture=nodes.new('ShaderNodeTexImage');texture.image=image;texture.extension='EXTEND';texture.location=(-400,0)
        if front:
            separate=nodes.new('ShaderNodeSeparateXYZ');combine=nodes.new('ShaderNodeCombineXYZ');sub=nodes.new('ShaderNodeMath')
            sub.operation='SUBTRACT';sub.inputs[0].default_value=1
            links.new(uv.outputs['UV'],separate.inputs[0]);links.new(separate.outputs['X'],sub.inputs[1])
            links.new(sub.outputs[0],combine.inputs['X']);links.new(separate.outputs['Y'],combine.inputs['Y'])
            links.new(combine.outputs[0],texture.inputs[0])
        else:links.new(uv.outputs['UV'],texture.inputs[0])
        mix=nodes.new('ShaderNodeMixRGB');mix.blend_type='MIX';mix.inputs[1].default_value=linear('#FFFCF4')
        links.new(texture.outputs['Alpha'],mix.inputs[0]);links.new(texture.outputs['Color'],mix.inputs[2])
        links.new(mix.outputs[0],shader.inputs['Base Color'])
    return m

def get_image(key):
    return next((i for i in bpy.data.images if i.name=='TIPO CARDS • оригинал • '+key),None)

def build():
    extras={key:WORK/'reference_faces'/(key+'.png') for key in ['ref_H3','ref_H4','ref_H7']}
    missing=[key for key,p in extras.items() if not p.is_file()]
    if missing and not ALLOW_MISSING:raise FileNotFoundError('Нужны оригинальные лица '+', '.join(missing))
    source=bpy.data.scenes['TIPO_61_CARDS_СТОЯ_v4']
    source_box=next(c for c in source.collection.children if c.name.startswith('01'))
    source_cards=next(c for c in source.collection.children if c.name.startswith('04'))
    originals=sorted(source_cards.objects,key=lambda o:o['deck_index'])
    assert len(originals)==61
    scene=bpy.data.scenes.new('TIPO_Paper_Story_v1');scene.use_fake_user=True
    if bpy.context.window:bpy.context.window.scene=scene
    scene.unit_settings.system='METRIC';scene.unit_settings.length_unit='MILLIMETERS'
    boxcol=bpy.data.collections.new('01 • Утверждённая коробка • открывание')
    cardcol=bpy.data.collections.new('02 • 61 гибкая двусторонняя карта')
    stage=bpy.data.collections.new('03 • Розовый стол, свет и непрерывная камера')
    for c in [boxcol,cardcol,stage]:scene.collection.children.link(c)
    master=bpy.data.objects.new('Коробка • зависание и переворот',None);boxcol.objects.link(master)
    master.rotation_mode='QUATERNION'
    center=Vector((0,-.0135,.0335))
    lid_hinge=Vector((0,.0135,.0335));flap_hinge=Vector((0,-.0135,.0335))
    lid=bpy.data.objects.new('Крышка • шарнир',None);boxcol.objects.link(lid);lid.parent=master;lid.location=lid_hinge
    flap=bpy.data.objects.new('Синий клапан • шарнир',None);boxcol.objects.link(flap);flap.parent=lid;flap.location=flap_hinge-lid_hinge
    for original in source_box.objects:
        obj=original.copy();obj.data=original.data;boxcol.objects.link(obj)
        rest=Matrix.Translation(-center)@original.matrix_basis
        if original.name.startswith('Верхний закрывающий'):
            obj.parent=lid;obj.matrix_basis=Matrix.Translation(-lid_hinge)@rest
        elif original.name.startswith('Заправляемый'):
            obj.parent=flap;obj.matrix_basis=Matrix.Translation(-flap_hinge)@rest
        else:obj.parent=master;obj.matrix_basis=rest
        # Коробка уже ушла вверх за кадр; исключаем её возвращение при финальном отъезде.
        for frame,hidden in [(1,False),(255,False),(260,True)]:
            obj.hide_render=hidden;obj.hide_viewport=hidden
            obj.keyframe_insert('hide_render',frame=frame);obj.keyframe_insert('hide_viewport',frame=frame)
    for frame in sorted(set([1,750]+list(range(1,181,3)))):
        t=(frame-1)/30;p,q=motion.box_pose(t);a,b=motion.lid_angles(t)
        master.location=p;master.rotation_quaternion=q
        master.keyframe_insert('location',frame=frame);master.keyframe_insert('rotation_quaternion',frame=frame)
        lid.rotation_euler.x=a;flap.rotation_euler.x=b
        lid.keyframe_insert('rotation_euler',frame=frame);flap.keyframe_insert('rotation_euler',frame=frame)
    for o in [master,lid,flap]:polish_action(o.animation_data.action)

    images={}
    for key in ['yellow','green','blue','pink','rules_back','rules_front']+['face_'+str(n) for n in range(49,97)]:
        images[key]=get_image(key);assert images[key] is not None,key
    for key,path in extras.items():
        if path.is_file():
            im=bpy.data.images.load(str(path),check_existing=False);im.colorspace_settings.name='sRGB';im.pack();im.use_fake_user=True
            im.name='ТИПО • точный референс • '+key;images[key]=im
        else:images[key]=None
    back_mats={k:paper_material('Бумага • рубашка • '+k,images[k]) for k in ['yellow','green','blue','pink','rules_back']}
    face_mats={k:paper_material('Бумага • лицо • '+k,im,front=True) for k,im in images.items() if k not in back_mats}
    edge=paper_material('Бумага • тонкий торец',edge=True)
    geo=json.loads((WORK/'card_mesh.json').read_text())
    xy=np.array(geo['points'],float);n=len(xy);base=np.c_[xy,np.zeros(n)]
    a=motion.SIZE/2
    modes=np.array([.004*(xy[:,0]/a)**2,.004*(xy[:,1]/a)**2,.003*(xy[:,0]*xy[:,1]/a**2)])
    manifest=[]
    print('Creating 61 flexible cards…',flush=True)
    for original in originals:
        idx=original['deck_index'];back=original['back_color']
        face='rules_front' if idx==0 else 'face_'+str(49+(idx-1)%48)
        hero=motion.HERO_MAP.get(idx)
        if hero:face=hero[2]
        verts=original.data.vertices
        x=(min(v.co.x for v in verts)+max(v.co.x for v in verts))/2
        y=(min(v.co.y for v in verts)+max(v.co.y for v in verts))/2
        z=max(v.co.z for v in verts)
        initial=original.matrix_basis@Vector((x,y,z))-center
        rotation=original.matrix_basis.to_quaternion()
        path=motion.CardMotion(idx,initial,rotation)
        mesh=bpy.data.meshes.new(f'Гибкая бумага {idx:02d}')
        mesh.from_pydata(base.tolist(),[],geo['faces']);mesh.update()
        obj=bpy.data.objects.new(f'Карта {idx:02d} • '+(hero[1] if hero else 'пролёт'),mesh);cardcol.objects.link(obj)
        obj.rotation_mode='QUATERNION'
        obj['deck_index']=idx;obj['back_color']=back;obj['face_key']=face;obj['layout_slot']=hero[1] if hero else ''
        obj['release_second']=path.release;obj['land_second']=path.land
        obj['Бумага']='Изгиб X, изгиб Y, скручивание; точная укладка лицом вверх.'
        mesh.materials.append(back_mats[back]);mesh.materials.append(face_mats[face]);mesh.materials.append(edge)
        uv=mesh.uv_layers.new(name='Card UV')
        for poly in mesh.polygons:
            poly.use_smooth=True
            for li in poly.loop_indices:
                v=mesh.vertices[mesh.loops[li].vertex_index].co
                uv.data[li].uv=(v.x/.065+.5,v.y/.065+.5)
        obj.shape_key_add(name='Basis')
        for j,name in enumerate(['Bend X','Bend Y','Twist']):
            key=obj.shape_key_add(name=name);key.slider_min=-1;key.slider_max=1
            for i in range(n):key.data[i].co.z=modes[j,i]
        solid=obj.modifiers.new('Толщина бумаги • 0.25 мм','SOLIDIFY')
        solid.thickness=motion.THICKNESS;solid.offset=-1;solid.material_offset=1;solid.material_offset_rim=2
        solid.use_rim=True
        frames=set([1,750]+list(range(1,int((path.land+.15)*30)+2,3)))
        frames.update(range(max(1,int((path.land-.5)*30)),int((path.land+.1)*30)+2))
        frames.update(round(t*30)+1 for t in [path.release,path.clear,path.land])
        previous=None
        for frame in sorted(frames):
            t=(frame-1)/30;p,q,bends=path.pose(t)
            if previous is not None and q.dot(previous)<0:q.negate()
            previous=q.copy()
            deform_z=np.array(bends)@modes
            R=np.array(q.to_matrix());low=float(np.min(xy@R[2,:2]+deform_z*R[2,2])-max(0,motion.THICKNESS*R[2,2]))
            if p.z+low<.00008:p.z=.00008-low
            obj.location=p;obj.rotation_quaternion=q
            obj.keyframe_insert('location',frame=frame);obj.keyframe_insert('rotation_quaternion',frame=frame)
            for j,value in enumerate(bends):
                key=mesh.shape_keys.key_blocks[j+1];key.value=value;key.keyframe_insert('value',frame=frame)
        polish_action(obj.animation_data.action)
        polish_action(mesh.shape_keys.animation_data.action)
        if not hero:
            gone=min(700,int((path.land+.45)*30)+1)
            for frame,hidden in [(1,False),(gone-1,False),(gone,True)]:
                obj.hide_render=hidden;obj.hide_viewport=hidden
                obj.keyframe_insert('hide_render',frame=frame);obj.keyframe_insert('hide_viewport',frame=frame)
        manifest.append({'index':idx,'face':face,'back':back,'hero':hero[1] if hero else None,'release':path.release,'land':path.land})
        if idx%10==0:print('BAKED CARD',idx,flush=True)

    table_m=bpy.data.materials.new('Фирменный розовый стол • FF006F');table_m.use_nodes=True
    nodes=table_m.node_tree.nodes;links=table_m.node_tree.links;nodes.clear()
    e=nodes.new('ShaderNodeEmission');e.name='Pink baseline';e.inputs['Color'].default_value=linear(PINK);e.inputs['Strength'].default_value=.87
    d=nodes.new('ShaderNodeBsdfDiffuse');d.inputs['Color'].default_value=tuple(c*.12 if i<3 else 1 for i,c in enumerate(linear(PINK)))
    add=nodes.new('ShaderNodeAddShader');o=nodes.new('ShaderNodeOutputMaterial')
    links.new(e.outputs[0],add.inputs[0]);links.new(d.outputs[0],add.inputs[1]);links.new(add.outputs[0],o.inputs[0])
    mesh=bpy.data.meshes.new('Стол • Z=0');mesh.from_pydata([(-20,-20,0),(20,-20,0),(20,20,0),(-20,20,0)],[],[(0,1,2,3)])
    table=bpy.data.objects.new('Розовый стол',mesh);stage.objects.link(table);mesh.materials.append(table_m)
    world=bpy.data.worlds.new('Нейтральное окружение');world.use_nodes=True
    world.node_tree.nodes['Background'].inputs['Color'].default_value=(1,1,1,1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value=.15;scene.world=world
    for name,loc,power in [('Мягкий ключевой',(-.4,-.8,1.2),2.5),('Заполняющий',(.8,-.5,.7),1.4),('Контровой',(.1,.7,1.2),1.7)]:
        data=bpy.data.lights.new(name,'SUN');data.energy=power;data.angle=.12
        if hasattr(data,'use_shadow_jitter'):data.use_shadow_jitter=False
        light=bpy.data.objects.new(name,data);stage.objects.link(light);light.location=loc;point_at(light,(0,0,.4))
    camera_data=bpy.data.cameras.new('Перспективная камера • 45 мм');camera_data.type='PERSP';camera_data.lens=45;camera_data.sensor_width=36;camera_data.sensor_fit='HORIZONTAL'
    camera_data.clip_start=.001;camera_data.clip_end=100
    camera=bpy.data.objects.new('Камера • один непрерывный пролёт',camera_data);stage.objects.link(camera);camera.rotation_mode='QUATERNION';scene.camera=camera
    previous=None
    for frame in range(1,751):
        p,q,aim=motion.camera_pose((frame-1)/30)
        if previous is not None and q.dot(previous)<0:q.negate()
        previous=q.copy();camera.location=p;camera.rotation_quaternion=q
        camera.keyframe_insert('location',frame=frame);camera.keyframe_insert('rotation_quaternion',frame=frame)
    polish_action(camera.animation_data.action,linear_keys=True)
    scene.render.engine='BLENDER_EEVEE_NEXT';scene.eevee.taa_render_samples=SAMPLES
    scene.eevee.use_raytracing=False;scene.eevee.use_taa_reprojection=False
    if hasattr(scene.eevee,'use_fast_gi'):scene.eevee.use_fast_gi=False
    if hasattr(scene.eevee,'use_gtao'):scene.eevee.use_gtao=True
    if hasattr(scene.eevee,'gtao_distance'):scene.eevee.gtao_distance=.004
    if hasattr(scene.render,'use_motion_blur'):scene.render.use_motion_blur=True
    if hasattr(scene.render,'motion_blur_shutter'):scene.render.motion_blur_shutter=.20
    scene.render.resolution_x=1920;scene.render.resolution_y=1080;scene.render.resolution_percentage=SIZE_PERCENT
    scene.render.fps=30;scene.frame_start=1;scene.frame_end=750
    scene.render.film_transparent=True
    scene.view_settings.view_transform='Standard';scene.view_settings.look='None';scene.view_settings.exposure=0;scene.view_settings.gamma=1
    scene.use_nodes=True;nodes=scene.node_tree.nodes;links=scene.node_tree.links;nodes.clear()
    layers=nodes.new('CompositorNodeRLayers');over=nodes.new('CompositorNodeAlphaOver');over.inputs[1].default_value=linear(PINK)
    links.new(layers.outputs['Image'],over.inputs[2])
    fade=nodes.new('CompositorNodeMixRGB');fade.blend_type='MIX';fade.inputs[1].default_value=linear(PINK)
    links.new(over.outputs[0],fade.inputs[2]);out=nodes.new('CompositorNodeComposite');links.new(fade.outputs[0],out.inputs[0])
    for f,value in [(1,0),(13,1),(750,1)]:fade.inputs[0].default_value=value;fade.inputs[0].keyframe_insert('default_value',frame=f)
    scene['Сценарий']='25 секунд, 1920×1080, FF006F, один непрерывный пролёт, без звука.'
    scene['Карты']=61;scene['Финальная раскладка']=14;scene['Missing artwork']=json.dumps(missing)
    scene['Референс']='8 по горизонтали, 7 по вертикали; общая H6/V5; Airy H3–H7.'
    scene['Коробка']='Утверждённая №2 v4; исходники не перезаписаны; анимированы крышка и клапан.'
    for frame,name in [(1,'Появление'),(67,'Переворот'),(125,'Открывание'),(168,'Выпадение'),(304,'Укладка'),(346,'Горизонтальный пролёт'),(490,'Вертикальный пролёт'),(595,'Отъезд'),(721,'Общий план')]:scene.timeline_markers.new(name,frame=frame)
    scene.frame_set(31)
    scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA'
    output=ROOT/'tipo_paper_story_v1.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(output))
    (WORK/'card_manifest.json').write_text(json.dumps(manifest,indent=2))
    print('STORY SAVED:',output,'MISSING:',missing,flush=True)

if __name__=='__main__':
    source_path=ROOT/'tipo_box_61_cards_v4.blend'
    expected='c8573e543203062b589489c2d720c0c994a39e1a297b1f2bbccea90d4a75b5f0'
    assert hashlib.sha256(source_path.read_bytes()).hexdigest()==expected, 'Approved source checksum mismatch'
    bpy.ops.wm.open_mainfile(filepath=str(source_path))
    build()
