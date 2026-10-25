"""Check the edit point, row framing, native frames and final MP4."""
from pathlib import Path
import hashlib,json,subprocess,os
from PIL import Image
import numpy as np

ROOT=Path(__file__).resolve().parent
PARENT=ROOT.parent
FRAMES=ROOT/'frames'
original=Path(os.environ.get('TIPO_SOURCE_FHD_FRAMES','/workspace/tipo_fullhd_work/render_frames'))
m=json.loads((ROOT/'animation_manifest.json').read_text())
assert m['frames']==85 and m['source_start_frame']==451
for i in range(85):
    p=FRAMES/f'frame_{i:04d}.png'
    with Image.open(p) as im:
        assert im.size==(1920,1080);im.verify()
for i in range(10):
    assert (FRAMES/f'frame_{i:04d}.png').read_bytes()==(original/f'frame_{451+i:04d}.png').read_bytes()
final=(ROOT/'final_horizontal_row.png').read_bytes()
for i in range(54,85):assert (FRAMES/f'frame_{i:04d}.png').read_bytes()==final
box=m['final_horizontal_row_bounds']
assert abs((box[2]-box[0])-.90)<1e-6
assert .049<box[0]<.051 and .949<box[2]<.951
h=[b for slot,b in m['final_card_bounds'].items() if slot.startswith('H')]
assert len(h)==8 and all(0<b[0]<b[2]<1 and 0<b[1]<b[3]<1 for b in h)
v=[b for slot,b in m['final_card_bounds'].items() if slot.startswith('V')]
assert any(b[3]>1 or b[1]<0 for b in v)
assert hashlib.sha256((PARENT/'tipo_paper_story_v1_fixed.blend').read_bytes()).hexdigest()==m['source_project_sha256']
p=PARENT/'tipo_paper_story_horizontal_close_pullback_v1_1080p.mp4'
probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(p)]))
assert len(probe['streams'])==1
s=probe['streams'][0]
assert (s['width'],s['height'],s['r_frame_rate'],int(s['nb_read_frames']))==(1920,1080,'30/1',85)
subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(p),'-f','null','-'],check=True)
def decoded(path,frame):
    b=subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-vf',f'select=eq(n\\,{frame})',
        '-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'])
    return np.frombuffer(b,dtype=np.uint8).reshape(1080,1920,3)
a=decoded(PARENT/'tipo_paper_story_v1_fixed_1080p.mp4',450)
b=decoded(p,0)
seam=float(np.abs(a.astype(float)-b.astype(float)).mean())
assert seam<1.5
report={'file':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
    'dimensions':[1920,1080],'fps':30,'frames':85,'duration_seconds':float(probe['format']['duration']),
    'audio':False,'separate_fragment':True,'rendered_from_original_3d':True,
    'upscaled':False,'stitch_source_frame':451,'stitch_source_seconds':15.,
    'first_ten_frames_byte_identical_to_approved_pngs':True,
    'encoded_seam_mean_rgb_difference_0_255':seam,
    'horizontal_cards_fully_in_frame':8,'horizontal_row_width_fraction':box[2]-box[0],
    'horizontal_row_side_margins':[box[0],1-box[2]],'vertical_row_intentionally_cropped':True,
    'final_camera_height_m':m['final_camera_height_m'],'original_project_unchanged':True,
    'full_decode':'passed'}
(ROOT/'video_validation.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2),flush=True)
