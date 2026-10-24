"""Check the exported movie and record the deliverable checksums."""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
movie=ROOT/'tipo_paper_story_v3.mp4'
probe=json.loads(subprocess.check_output([
    'ffprobe','-v','error','-count_frames','-show_streams','-show_format',
    '-of','json',str(movie)],text=True))
video=[s for s in probe['streams'] if s['codec_type']=='video']
assert len(video)==1
v=video[0]
assert v['width']==1920 and v['height']==1080
assert v['codec_name']=='h264' and v['pix_fmt']=='yuv420p'
assert v['avg_frame_rate']=='30/1'
assert int(v['nb_read_frames'])==750
assert abs(float(probe['format']['duration'])-25)<.001
assert not any(s['codec_type']=='audio' for s in probe['streams'])
subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(movie),'-f','null','-'],check=True)
motion=json.loads((ROOT/'paper_story_v3/motion_validation.json').read_text())
assert motion['production_ready'] and motion['all_card_textures_packed']
proof={
    'duration_seconds':25,'resolution':[1920,1080],'fps':30,'decoded_frames':750,
    'video_codec':'H.264','pixel_format':'yuv420p','audio_streams':0,
    'full_decode_passed':True,'render_engine':'Blender 4.3.2 Eevee Next',
    'render_resolution_native':True,'motion_samples':4,'final_hold_samples':16,
    'source_project':'tipo_paper_story_v3.blend',
    'final_static_hold_frames':[586,750],'box_static_hold_frames':[37,91],
    'scene_checks':'paper_story_v3/motion_validation.json',
    'clearance_checks':'paper_story_v3/clearance_validation.json',
    'background':'#FFD000','cards_released':30,'cards_remaining_inside':31,
    'close_camera_pass':'horizontal_only','entry_bounce_m':.006,'pullback_seconds':2.1,
    'files':{}
}
for name in ['tipo_paper_story_v3.mp4','tipo_paper_story_v3.blend','tipo_paper_story_v3.png']:
    p=ROOT/name
    proof['files'][name]={'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
target=ROOT/'tipo_paper_story_v3_validation.json'
target.write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(proof,ensure_ascii=False,indent=2))
