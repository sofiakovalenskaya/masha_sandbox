"""Extend the colours of paper textures beyond their photographed silhouettes.

These opaque RGB material maps are used on geometry, not composited over the
movie. Nearest-edge colour extension avoids a rectangular colour boundary.
"""
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt
from scipy.ndimage import gaussian_filter

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'material_textures';OUT.mkdir(exist_ok=True)
for name in ['paper_near_flat.png','paper_light_creases.png','paper_medium_creases.png']:
    a=np.asarray(Image.open(ROOT.parent/'word_sequence_v6/assets'/name).convert('RGBA'))
    indices=distance_transform_edt(a[:,:,3]<128,return_distances=False,return_indices=True)
    rgb=a[indices[0],indices[1],:3]
    if name=='paper_medium_creases.png':
        # Suppress one-pixel edge fibres extending into long streaks in the
        # padded material region. Original printed paper pixels stay intact.
        outside=a[:,:,3]<128
        distance=distance_transform_edt(outside)
        smooth=gaussian_filter(rgb.astype(float),sigma=(7,7,0))
        weight=np.clip(distance/7,0,1)[:,:,None]
        rgb=np.rint(rgb*(1-weight)+smooth*weight).astype('uint8')
    Image.fromarray(rgb).save(OUT/name,compress_level=3)
print('OPAQUE MATERIAL TEXTURES READY',flush=True)
