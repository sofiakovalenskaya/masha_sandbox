import bpy,json,os,shutil,time
from pathlib import Path

WORK=Path(__file__).resolve().parent
ROOT=WORK.parent
folder=Path(os.environ.get('TIPO_RENDER_DIR',str(WORK/'render_frames')))
folder.mkdir(exist_ok=True,parents=True)
scene=bpy.data.scenes['TIPO_Paper_Story_v3'];bpy.context.window.scene=scene
assert json.loads(scene['Missing artwork'])==[]
scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
scene.render.image_settings.color_mode='RGB'
scene.render.image_settings.compression=15
requested=os.environ.get('TIPO_FRAMES','')
frames=[int(f) for f in requested.split(',')] if requested else range(1,751)
last_native=0
for frame in frames:
    target=folder/f'frame_{frame:04d}.png'
    source=1 if 2<=frame<=13 else 37 if 38<=frame<=91 else 586 if 587<=frame<=750 else None
    if target.exists():
        with target.open('rb') as handle:
            handle.seek(-12,2);complete=handle.read()==b'\x00\x00\x00\x00IEND\xaeB\x60\x82'
        if not complete:target.unlink()
    if not target.exists():
        if source is not None and (folder/f'frame_{source:04d}.png').exists():
            shutil.copyfile(folder/f'frame_{source:04d}.png',target)
        else:
            scene.frame_set(frame)
            scene.eevee.taa_render_samples=16 if frame in [37,586] else int(os.environ.get('TIPO_SAMPLES','4'))
            scene.render.filepath=str(target);start=time.monotonic()
            bpy.ops.render.render(write_still=True,scene=scene.name)
            last_native=frame
            print('FINAL_FRAME',frame,'SECONDS',round(time.monotonic()-start,2),flush=True)
    if frame==586:shutil.copyfile(target,ROOT/'tipo_paper_story_v3.png')
    temporary=folder/'progress.tmp'
    temporary.write_text(json.dumps({'completed_frame':frame,'total':750,'last_native_frame':last_native}))
    temporary.replace(folder/'progress.json')
print('FRAME_SEQUENCE_COMPLETE',flush=True)
