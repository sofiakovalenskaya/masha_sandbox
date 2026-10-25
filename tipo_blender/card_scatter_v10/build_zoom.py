"""Append a centered camera zoom to the approved v9 animation."""
from pathlib import Path
import hashlib
import json
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / 'card_scatter_v9'
FRAMES = ROOT / 'frames'
FRAMES.mkdir(exist_ok=True)
W, H, FPS = 1920, 1080, 30
PREFIX = 153
ZOOM_FRAMES = 45
HOLD_FRAMES = 30
FINAL_SIDE = 972
FINAL_ZOOM = FINAL_SIDE / 320

background = Image.open(SOURCE / 'opening_background.png').convert('RGBA')
artwork = Image.open(SOURCE / 'assets/rules_front.png').convert('RGBA')

def render_zoom(scale):
    # Sample the whole tabletop through the same centered camera zoom.
    # Re-render the original high-resolution card to keep small type sharp.
    half_w, half_h = W / (2 * scale), H / (2 * scale)
    canvas = background.resize((W, H), Image.Resampling.LANCZOS,
        box=(960-half_w, 540-half_h, 960+half_w, 540+half_h))
    side = round(320 * scale)
    pad = round(24 * scale)
    sprite = Image.new('RGBA', (side + 2*pad, side + 2*pad))
    sprite.alpha_composite(artwork.resize((side, side), Image.Resampling.LANCZOS), (pad, pad))
    alpha = sprite.getchannel('A').filter(ImageFilter.GaussianBlur(7 * scale))
    shadow = Image.new('RGBA', sprite.size, (60, 34, 10, 0))
    shadow.putalpha(alpha.point(lambda a: round(a * .22)))
    combined = Image.new('RGBA', sprite.size)
    combined.alpha_composite(shadow, (round(3*scale), round(7*scale)))
    combined.alpha_composite(sprite)
    canvas.alpha_composite(combined,
        (round(960-combined.width/2), round(540-combined.height/2)))
    return canvas.convert('RGB')

manifest = []
for n in range(PREFIX):
    src = SOURCE / 'frames' / f'frame_{n:04d}.png'
    dst = FRAMES / src.name
    if dst.exists():
        dst.unlink()
    dst.hardlink_to(src)
    manifest.append({'frame': n, 'phase': 'approved_v9_unchanged', 'source_frame': n})

for i in range(ZOOM_FRAMES):
    u = i / (ZOOM_FRAMES-1)
    # Minimum-jerk ease: still camera at both ends, smoothly increasing size.
    eased = u*u*u*(10 + u*(-15 + 6*u))
    scale = 1 + (FINAL_ZOOM-1) * eased
    frame = PREFIX+i
    canvas = render_zoom(scale)
    canvas.save(FRAMES / f'frame_{frame:04d}.png', compress_level=3)
    manifest.append({'frame': frame, 'phase': 'camera_zoom', 'camera_zoom': scale,
                     'card_center': [960, 540], 'card_side_px': round(320*scale)})
    if i % 10 == 0:
        print('ZOOM', i, round(scale, 4), flush=True)

last = FRAMES / f'frame_{PREFIX+ZOOM_FRAMES-1:04d}.png'
(ROOT / 'final_rules_closeup.png').write_bytes(last.read_bytes())
for i in range(HOLD_FRAMES):
    frame = PREFIX+ZOOM_FRAMES+i
    dst = FRAMES / f'frame_{frame:04d}.png'
    if dst.exists():
        dst.unlink()
    dst.hardlink_to(last)
    manifest.append({'frame': frame, 'phase': 'closeup_hold', 'camera_zoom': FINAL_ZOOM,
                     'card_center': [960, 540], 'card_side_px': FINAL_SIDE})

assert render_zoom(1).tobytes() == Image.open(SOURCE / 'final_one_rules_card.png').convert('RGB').tobytes()
report = {
    'based_on': 'card_scatter_v9', 'width': W, 'height': H, 'fps': FPS,
    'frames': len(manifest), 'duration_seconds': len(manifest)/FPS,
    'unchanged_prefix_frames': PREFIX, 'zoom_frames': ZOOM_FRAMES,
    'final_hold_frames': HOLD_FRAMES, 'final_card_side_px': FINAL_SIDE,
    'final_card_height_fraction': FINAL_SIDE/H, 'final_camera_zoom': FINAL_ZOOM,
    'camera_center': [960,540], 'card_rotation_degrees': 0,
    'zoom_starts_after_cards_swept_away': True,
    'source_rules_sha256': hashlib.sha256((SOURCE/'assets/rules_front.png').read_bytes()).hexdigest(),
    'frame_map': manifest,
}
(ROOT / 'animation_manifest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
print('COMPLETE', len(manifest), 'frames', flush=True)
