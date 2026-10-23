# -*- coding: utf-8 -*-
"""ТИПО — коробка 67 × 67 × 27 мм и одна карта 65 × 65 мм.

Blender 4.x. Откройте этот файл в Text Editor и нажмите Run Script.
Исходные четыре PNG должны находиться в ~/Downloads (Загрузки).
Авторские изображения не заменяются шрифтами или сгенерированным рисунком.
Создаётся отдельная сцена; существующие сцены не удаляются.
"""
import bpy
import math
import os
import unicodedata
from collections import deque
from datetime import datetime
from pathlib import Path

import numpy as np
from mathutils import Vector
from mathutils.geometry import tessellate_polygon


# -------------------------- НАСТРОЙКИ --------------------------
# При необходимости укажите свою папку, например:
# ASSET_DIR = Path('/Users/marialepilina/Downloads')
ASSET_DIR = Path(os.environ.get('TIPO_ASSET_DIR', str(Path.home() / 'Downloads')))
RENDER_NOW = os.environ.get('TIPO_RENDER', '1') == '1'
RENDER_SIZE = int(os.environ.get('TIPO_RENDER_SIZE', '1400'))
SAMPLES = int(os.environ.get('TIPO_SAMPLES', '96'))
BOX_MM = 67.0
DEPTH_MM = 27.0
CARD_MM = 65.0
# Толщины и радиус скругления пока являются настраиваемыми допущениями.
BOARD_MM = 0.35
CARD_THICKNESS_MM = 0.28
CARD_CORNER_MM = 0.65
MM = 0.001
PAPER_HEX = '#FFFCF4'
PINK_HEX = '#FF006F'

# Границы панелей в показанной развёртке 1877 × 1344.
# Нормированные координаты автоматически переносятся на оригинал 4497 × 3218.
# Вылеты не растягиваются на лицевую грань: каждая панель берётся отдельно.
LAYOUT_W, LAYOUT_H = 1877.0, 1344.0
PANELS = {
    'front': (273, 417, 934, 1078),
    'left': (7, 417, 273, 1078),
    'right': (934, 417, 1199, 1078),
    'back': (1199, 417, 1860, 1078),
    'bottom': (273, 1078, 934, 1344),
    'top': (1199, 150, 1860, 417),
    'tuck': (1199, 0, 1860, 150),
}


def normalized_name(value):
    return unicodedata.normalize('NFC', value).casefold().replace('ё', 'е')


def find_source(*stems):
    roots = [ASSET_DIR]
    if bpy.data.filepath:
        roots.append(Path(bpy.data.filepath).parent)
    try:
        roots.append(Path(__file__).resolve().parent)
    except NameError:
        pass
    expected = {normalized_name(s) for s in stems}
    for root in dict.fromkeys(roots):
        if root.is_dir():
            for path in sorted(root.iterdir()):
                if (path.is_file() and path.suffix.lower() == '.png'
                        and normalized_name(path.stem) in expected):
                    return path
    raise FileNotFoundError(
        'Не найден исходный PNG: ' + ' / '.join(stems)
        + '. Поместите четыре исходных PNG в ' + str(ASSET_DIR)
        + ' или измените ASSET_DIR в начале скрипта. Сцена ещё не изменялась.'
    )


def load_rgba(path, name):
    image = bpy.data.images.load(str(path), check_existing=False)
    image.name = name
    image.colorspace_settings.name = 'sRGB'
    width, height = image.size[:]
    pixels = np.empty(width * height * 4, dtype=np.float32)
    image.pixels.foreach_get(pixels)
    pixels = pixels.reshape(height, width, 4)[::-1].copy()
    image.pack()
    image.use_fake_user = True
    return image, pixels


def crop_panel(pixels, key):
    height, width = pixels.shape[:2]
    x0, y0, x1, y1 = PANELS[key]
    xa, xb = round(x0 * width / LAYOUT_W), round(x1 * width / LAYOUT_W)
    ya, yb = round(y0 * height / LAYOUT_H), round(y1 * height / LAYOUT_H)
    return pixels[ya:yb, xa:xb].copy()


def packed_image(name, rgba):
    height, width = rgba.shape[:2]
    image = bpy.data.images.new(name, width, height, alpha=True, float_buffer=False)
    image.colorspace_settings.name = 'sRGB'
    image.pixels.foreach_set(np.ascontiguousarray(rgba[::-1]).ravel())
    image.update()
    image.pack()
    image.use_fake_user = True
    return image


def component(mask, seed):
    """Выделение одной связной области без сторонних библиотек."""
    height, width = mask.shape
    sx, sy = seed
    result = np.zeros_like(mask)
    if not (0 <= sx < width and 0 <= sy < height and mask[sy, sx]):
        return result
    queue = deque([(sx, sy)])
    result[sy, sx] = True
    while queue:
        x, y = queue.popleft()
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if (0 <= nx < width and 0 <= ny < height
                    and mask[ny, nx] and not result[ny, nx]):
                result[ny, nx] = True
                queue.append((nx, ny))
    return result


def extract_cutouts(front):
    """Поддерживает и прозрачное окно PNG, и окно, залитое чёрным."""
    height, width = front.shape[:2]
    void = (front[:, :, 3] < 0.4) | (np.max(front[:, :, :3], axis=2) < 0.16)
    eligible = void.copy()
    eligible[:int(height * 0.20)] = False
    eligible[int(height * 0.78):] = False
    eligible[:, :int(width * 0.025)] = False
    eligible[:, int(width * 0.975):] = False
    yy, xx = np.where(eligible)
    if len(xx) == 0:
        raise ValueError('В пустой развёртке не найдено окно. Проверьте файл и PANELS.')
    closest = np.argmin((xx / width - 0.5) ** 2 + (yy / height - 0.48) ** 2)
    window = component(void, (int(xx[closest]), int(yy[closest])))
    fraction = float(window.mean())
    if not 0.04 < fraction < 0.45:
        raise ValueError('Контур окна не распознан уверенно; проверьте пустую развёртку.')
    # Полукруглая выемка у верхнего края — отдельный настоящий вырез.
    notch = np.zeros_like(void)
    for y in range(min(4, height)):
        x = width // 2
        if void[y, x]:
            candidate = component(void, (x, y))
            if 0.001 < candidate.mean() < 0.06:
                notch = candidate
            break
    return window, notch


def simplify_polyline(points, tolerance=0.65):
    points = np.asarray(points, dtype=float)
    if len(points) < 3:
        return points.tolist()
    a, b = points[0], points[-1]
    line = b - a
    length = np.linalg.norm(line)
    if length < 1e-10:
        distance = np.linalg.norm(points - a, axis=1)
    else:
        distance = np.abs(line[0] * (points[:, 1] - a[1])
                          - line[1] * (points[:, 0] - a[0])) / length
    index = int(np.argmax(distance))
    if distance[index] <= tolerance:
        return [points[0].tolist(), points[-1].tolist()]
    left = simplify_polyline(points[:index + 1], tolerance)
    right = simplify_polyline(points[index:], tolerance)
    return left[:-1] + right


def boundary_polygon(mask):
    """Контур по границам пикселей, затем субпиксельное упрощение."""
    padded = np.pad(mask, 1)
    edges = {}

    def add(starts, ends):
        for a, b in zip(starts, ends):
            edges.setdefault(tuple(a), []).append(tuple(b))

    y, x = np.where(mask & ~padded[:-2, 1:-1])
    add(zip(x, y), zip(x + 1, y))
    y, x = np.where(mask & ~padded[1:-1, 2:])
    add(zip(x + 1, y), zip(x + 1, y + 1))
    y, x = np.where(mask & ~padded[2:, 1:-1])
    add(zip(x + 1, y + 1), zip(x, y + 1))
    y, x = np.where(mask & ~padded[1:-1, :-2])
    add(zip(x, y + 1), zip(x, y))
    loops = []
    while edges:
        start = next(iter(edges))
        point, loop = start, [start]
        while True:
            destinations = edges.get(point)
            if not destinations:
                raise ValueError('Не удалось замкнуть контур выреза.')
            nxt = destinations.pop()
            if not destinations:
                del edges[point]
            point = nxt
            if point == start:
                break
            loop.append(point)
        loops.append(loop)
    loop = max(loops, key=len)
    # Разбиваем замкнутый контур на две открытые дуги для RDP.
    middle = len(loop) // 2
    return (simplify_polyline(loop[:middle + 1])[:-1]
            + simplify_polyline(loop[middle:] + [loop[0]])[:-1])


def srgb(hex_color):
    return np.array([int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)])


def linear_color(hex_color):
    values = srgb(hex_color)
    linear = np.where(values <= 0.04045, values / 12.92,
                      ((values + 0.055) / 1.055) ** 2.4)
    return (*map(float, linear), 1.0)


def make_card_image(filled_front, cut_mask, resolution=768):
    """Точное видимое изображение из макета; скрытая область — розовая.

    Полный оригинал карты не предоставлен. Здесь не выдумывается оборот.
    Результат видимой области сохраняется без перерисовки логотипа.
    """
    front_h, front_w = filled_front.shape[:2]
    result = np.empty((resolution, resolution, 4), dtype=np.float32)
    result[:, :, :3] = srgb(PINK_HEX)
    result[:, :, 3] = 1.0
    # Соответствие координат карты 65 мм и лицевой панели 67 мм.
    normalized = ((np.arange(resolution) + 0.5) / resolution - 0.5)
    uv = normalized * CARD_MM / BOX_MM + 0.5
    xs = np.clip(uv * front_w - 0.5, 0, front_w - 1)
    ys = np.clip(uv * front_h - 0.5, 0, front_h - 1)
    x0, y0 = np.floor(xs).astype(int), np.floor(ys).astype(int)
    x1, y1 = np.minimum(x0 + 1, front_w - 1), np.minimum(y0 + 1, front_h - 1)
    fx, fy = xs - x0, ys - y0
    sampled = (
        filled_front[y0[:, None], x0[None, :]] * (1 - fy[:, None, None]) * (1 - fx[None, :, None])
        + filled_front[y0[:, None], x1[None, :]] * (1 - fy[:, None, None]) * fx[None, :, None]
        + filled_front[y1[:, None], x0[None, :]] * fy[:, None, None] * (1 - fx[None, :, None])
        + filled_front[y1[:, None], x1[None, :]] * fy[:, None, None] * fx[None, :, None]
    )
    expanded = cut_mask.copy()
    for _ in range(3):
        p = np.pad(expanded, 1)
        expanded = np.logical_or.reduce([
            p[dy:dy + front_h, dx:dx + front_w]
            for dy in range(3) for dx in range(3)
        ])
    selected = expanded[np.rint(ys).astype(int)[:, None],
                        np.rint(xs).astype(int)[None, :]]
    result[selected, :3] = sampled[selected, :3]
    return packed_image('TIPO • карта • видимая авторская графика', result)


def set_input(node, names, value):
    for name in names:
        if name in node.inputs:
            node.inputs[name].default_value = value
            return


def paper_material(name, image=None, color=PAPER_HEX, gloss=True, edge=False):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    material.diffuse_color = linear_color(color)
    nodes, links = material.node_tree.nodes, material.node_tree.links
    nodes.clear()
    output = nodes.new('ShaderNodeOutputMaterial')
    output.location = (650, 60)
    shader = nodes.new('ShaderNodeBsdfPrincipled')
    shader.location = (340, 60)
    shader.inputs['Base Color'].default_value = linear_color(color)
    shader.inputs['Roughness'].default_value = 0.28 if gloss else 0.62
    shader.inputs['IOR'].default_value = 1.46
    set_input(shader, ('Coat Weight', 'Clearcoat'), 0.42 if gloss else 0.0)
    set_input(shader, ('Coat Roughness', 'Clearcoat Roughness'), 0.18)
    links.new(shader.outputs['BSDF'], output.inputs['Surface'])
    if image:
        texture = nodes.new('ShaderNodeTexImage')
        texture.name = 'Авторский PNG — sRGB, без перекрашивания'
        texture.label = texture.name
        texture.image = image
        texture.interpolation = 'Linear'
        texture.extension = 'EXTEND'
        texture.location = (-430, 220)
        links.new(texture.outputs['Color'], shader.inputs['Base Color'])
    geometry = nodes.new('ShaderNodeNewGeometry')
    geometry.location = (-850, -150)
    noise = nodes.new('ShaderNodeTexNoise')
    noise.location = (-600, -150)
    noise.inputs['Scale'].default_value = 14000.0 if edge else 10000.0
    noise.inputs['Detail'].default_value = 2.0
    noise.inputs['Roughness'].default_value = 0.65
    links.new(geometry.outputs['Position'], noise.inputs['Vector'])
    bump = nodes.new('ShaderNodeBump')
    bump.location = (40, -120)
    bump.inputs['Strength'].default_value = 0.14 if edge else 0.075
    bump.inputs['Distance'].default_value = 0.000012 if edge else 0.000006
    links.new(noise.outputs['Fac'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], shader.inputs['Normal'])
    # Ламинат остаётся гладким: микрорельеф бумаги под глянцевым слоем.
    ramp = nodes.new('ShaderNodeMapRange')
    ramp.location = (-150, -330)
    ramp.inputs['From Min'].default_value = 0.0
    ramp.inputs['From Max'].default_value = 1.0
    ramp.inputs['To Min'].default_value = 0.24 if gloss else 0.55
    ramp.inputs['To Max'].default_value = 0.30 if gloss else 0.72
    links.new(noise.outputs['Fac'], ramp.inputs['Value'])
    links.new(ramp.outputs['Result'], shader.inputs['Roughness'])
    return material


def mesh_object(name, vertices, faces, collection):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.validate()
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    return obj


def cuboid(name, lo, hi, collection):
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    vertices = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    faces = [(3, 2, 1, 0), (0, 1, 5, 4), (1, 2, 6, 5),
             (2, 3, 7, 6), (3, 0, 4, 7), (4, 5, 6, 7)]
    return mesh_object(name, vertices, faces, collection)


def prism(name, profile, z0, z1, collection):
    profile = list(profile)
    area = sum(profile[i][0] * profile[(i + 1) % len(profile)][1]
               - profile[(i + 1) % len(profile)][0] * profile[i][1]
               for i in range(len(profile)))
    if area < 0:
        profile.reverse()
    n = len(profile)
    vectors = [Vector((x, y, 0.0)) for x, y in profile]
    triangles = tessellate_polygon([vectors])
    index = {(v.x, v.y): i for i, v in enumerate(vectors)}
    faces = []
    for triangle in triangles:
        # Blender возвращает индексы; поддерживаем и варианты API с Vector.
        ids = tuple(index[(v.x, v.y)] if hasattr(v, 'x') else int(v)
                    for v in triangle)
        faces.extend([tuple(reversed(ids)), tuple(i + n for i in ids)])
    faces += [(i, (i + 1) % n, (i + 1) % n + n, i + n) for i in range(n)]
    vertices = [(x, y, z) for z in (z0, z1) for x, y in profile]
    return mesh_object(name, vertices, faces, collection)


def apply_cut(obj, cutter):
    modifier = obj.modifiers.new('Настоящий сквозной вырез', 'BOOLEAN')
    modifier.operation = 'DIFFERENCE'
    modifier.solver = 'EXACT'
    modifier.object = cutter
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    bpy.data.objects.remove(cutter, do_unlink=True)
    obj.select_set(False)


def finish_surface(obj, printed_material, paper, outward, uv_function, bevel_mm=0.045):
    obj.data.materials.append(printed_material)
    obj.data.materials.append(paper)
    uv = obj.data.uv_layers.new(name='Авторская развёртка')
    direction = Vector(outward)
    for polygon in obj.data.polygons:
        polygon.material_index = 0 if polygon.normal.dot(direction) > 0.9 else 1
        for loop_index in polygon.loop_indices:
            co = obj.data.vertices[obj.data.loops[loop_index].vertex_index].co
            uv.data[loop_index].uv = uv_function(co)
    bevel = obj.modifiers.new('Мягкий край бумаги', 'BEVEL')
    bevel.width = bevel_mm * MM
    bevel.segments = 3
    bevel.limit_method = 'ANGLE'
    bevel.angle_limit = math.radians(32)
    bevel.material = 1
    bevel.use_clamp_overlap = True
    return obj


def rounded_square(size, radius, segments=12):
    half = size / 2
    profile = []
    for cx, cy, start in [(half - radius, half - radius, 0),
                          (-half + radius, half - radius, 90),
                          (-half + radius, -half + radius, 180),
                          (half - radius, -half + radius, 270)]:
        for i in range(segments + 1):
            a = math.radians(start + i * 90 / segments)
            profile.append((cx + radius * math.cos(a), cy + radius * math.sin(a)))
    return profile


def point_at(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()


def area_light(collection, name, location, target, energy, size, size_y=None):
    data = bpy.data.lights.new(name, 'AREA')
    data.energy = energy
    data.shape = 'RECTANGLE' if size_y else 'DISK'
    data.size = size
    if size_y:
        data.size_y = size_y
    obj = bpy.data.objects.new(name, data)
    collection.objects.link(obj)
    obj.location = location
    point_at(obj, target)
    return obj


def build():
    if bpy.app.version < (4, 0, 0):
        raise RuntimeError('Для этого скрипта нужен Blender 4.0 или новее.')
    sources = {
        'empty': find_source('корбка без карты', 'коробка без карты'),
        'filled': find_source('коробка с картой', 'коробка с картой'),
        'logo_plain': find_source('логотип без обводки'),
        'logo_outline': find_source('логотип обводка'),
    }
    print('TIPO: загружаю исходные изображения…', flush=True)
    _, empty = load_rgba(sources['empty'], 'TIPO • оригинал • пустая развёртка')
    _, filled = load_rgba(sources['filled'], 'TIPO • оригинал • развёртка с картой')
    load_rgba(sources['logo_plain'], 'TIPO • оригинальный логотип без обводки')
    load_rgba(sources['logo_outline'], 'TIPO • оригинальный логотип с обводкой')
    if empty.shape != filled.shape:
        raise ValueError('Обе развёртки должны иметь одинаковые размеры в пикселях.')
    front = crop_panel(empty, 'front')
    window, notch = extract_cutouts(front)
    cutouts = [('Фигурное окно', window)]
    if notch.any():
        cutouts.append(('Выемка для пальца', notch))
    panel_images = {}
    for key in PANELS:
        pixels = crop_panel(empty, key)
        # Прозрачные области удалены геометрией. Под ними нет чёрной краски.
        pixels[pixels[:, :, 3] < 0.4, :3] = srgb(PAPER_HEX)
        if key == 'front':
            pixels[window | notch, :3] = srgb(PAPER_HEX)
        pixels[:, :, 3] = 1.0
        panel_images[key] = packed_image('TIPO • печать • ' + key, pixels)
    card_image = make_card_image(crop_panel(filled, 'front'), window | notch)

    print('TIPO: создаю новую сцену и физическую геометрию…', flush=True)
    scene = bpy.data.scenes.new('TIPO_Studio')
    scene['TIPO_generator'] = '1.0'
    scene['Размер коробки, мм'] = '67 × 67 × 27'
    scene['Размер единственной карты, мм'] = '65 × 65'
    scene['Примечание о карте'] = 'Авторская видимая область; скрытая часть — розовая реконструкция.'
    scene['Примечание о конструкции'] = 'Толщина картона 0.35 мм и клапан восстановлены по развёртке.'
    if bpy.context.window:
        bpy.context.window.scene = scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.length_unit = 'MILLIMETERS'
    scene.unit_settings.scale_length = 1.0
    packaging = bpy.data.collections.new('01 • Коробка — отдельные панели')
    cards = bpy.data.collections.new('02 • Одна карта')
    studio = bpy.data.collections.new('03 • Студия')
    for collection in (packaging, cards, studio):
        scene.collection.children.link(collection)
    paper = paper_material('TIPO • торец и внутренняя бумага', gloss=False, edge=True)
    materials = {key: paper_material('TIPO • глянцевая печать • ' + key, image=image)
                 for key, image in panel_images.items()}
    card_material = paper_material('TIPO • карта • глянцевая ламинация', image=card_image)
    half, depth, t = BOX_MM * MM / 2, DEPTH_MM * MM, BOARD_MM * MM
    span = 2 * half
    top = cuboid('Лицевая панель • сквозное окно', (-half, -half, depth - t),
                 (half, half, depth), packaging)
    h, w = front.shape[:2]
    for label, mask in cutouts:
        contour = boundary_polygon(mask)
        profile = []
        for x, y in contour:
            world_y = half - y / h * span
            # Крайняя граница выемки выносится наружу для надёжного Boolean.
            if label == 'Выемка для пальца' and y <= 1:
                world_y = half + 0.001
            profile.append(((x / w - 0.5) * span, world_y))
        cutter = prism(label, profile, depth - t - 0.002, depth + 0.002, packaging)
        apply_cut(top, cutter)
    finish_surface(top, materials['front'], paper, (0, 0, 1),
                   lambda p: ((p.x + half) / span, (p.y + half) / span))

    definitions = [
        ('Левая боковина', 'left', (-half, -half, t), (-half + t, half, depth - t),
         (-1, 0, 0), lambda p: (p.z / depth, (p.y + half) / span)),
        ('Правая боковина', 'right', (half - t, -half, t), (half, half, depth - t),
         (1, 0, 0), lambda p: (1 - p.z / depth, (p.y + half) / span)),
        ('Задняя панель', 'back', (-half, -half, 0), (half, half, t),
         (0, 0, -1), lambda p: ((half - p.x) / span, (p.y + half) / span)),
        ('Нижний сгиб', 'bottom', (-half + t, -half, t), (half - t, -half + t, depth - t),
         (0, -1, 0), lambda p: ((p.x + half) / span, p.z / depth)),
        ('Верхний закрывающий клапан', 'top', (-half + t, half - t, t),
         (half - t, half, depth - t), (0, 1, 0),
         lambda p: ((half - p.x) / span, p.z / depth)),
    ]
    for name, key, lo, hi, outward, uv in definitions:
        obj = cuboid(name, lo, hi, packaging)
        finish_surface(obj, materials[key], paper, outward, uv)
    # Клапан заправляется внутрь. Клеевых язычков в геометрии нет.
    tuck_depth = (150 / 661) * BOX_MM * MM
    tuck_z = depth - t - 0.00004
    tuck = cuboid('Заправленный клапан • без клея',
                  (-half + 0.0007, half - tuck_depth, tuck_z - t),
                  (half - 0.0007, half - t, tuck_z), packaging)
    finish_surface(tuck, materials['tuck'], paper, (0, 0, 1),
                   lambda p: ((half - p.x) / span, (half - p.y) / tuck_depth), 0.025)

    # Одна карта расположена сразу за окном, как на предоставленном макете.
    # Она не изображает стопку и не опирается на несуществующие дополнительные карты.
    card_top = tuck_z - t - 0.00013
    card = prism('Карта • единственная • 65 × 65 мм',
                 rounded_square(CARD_MM * MM, CARD_CORNER_MM * MM),
                 card_top - CARD_THICKNESS_MM * MM, card_top, cards)
    card['Количество'] = 1
    card['Положение'] = 'Демонстрационная фиксация непосредственно за окном.'
    card['Скрытая графика'] = 'Розовый фон; полный оригинал карты не предоставлен.'
    finish_surface(card, card_material, paper, (0, 0, 1),
                   lambda p: (p.x / (CARD_MM * MM) + 0.5,
                              p.y / (CARD_MM * MM) + 0.5), 0.025)

    floor_material = paper_material('Студия • тёплый матовый фон', color='#EAE6DF', gloss=False)
    floor = cuboid('Фон • мягкая контактная тень', (-1, -1, -0.002), (1, 1, -0.00015), studio)
    floor.data.materials.append(floor_material)
    world = bpy.data.worlds.new('TIPO • нейтральное освещение')
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (1, 1, 1, 1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.22
    scene.world = world
    area_light(studio, 'Ключевой • большой софтбокс', (-0.09, -0.08, 0.18),
               (0, 0, 0.015), 0.12, 0.14)
    area_light(studio, 'Заполнение • нейтральное', (0.12, -0.015, 0.10),
               (0, 0, 0.015), 0.045, 0.11)
    area_light(studio, 'Контур • отражение на ламинации', (-0.02, 0.11, 0.15),
               (0, 0, 0.020), 0.09, 0.13, 0.035)
    camera_data = bpy.data.cameras.new('TIPO • предметная камера')
    camera = bpy.data.objects.new('Камера • основной ракурс', camera_data)
    studio.objects.link(camera)
    camera.location = (0.112, -0.135, 0.19)
    point_at(camera, (0, 0, 0.012))
    camera_data.type = 'ORTHO'
    camera_data.ortho_scale = 0.125
    camera_data.clip_start = 0.001
    camera_data.clip_end = 20
    scene.camera = camera
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = SAMPLES
    # Некоторые Linux-сборки Blender собраны без OpenImageDenoise.
    # Не включаем недоступный модуль: это иначе прерывает весь рендер.
    try:
        import _cycles
        scene.cycles.use_denoising = bool(getattr(_cycles, 'with_openimagedenoise', False))
    except ImportError:
        scene.cycles.use_denoising = False
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.02
    scene.cycles.max_bounces = 8
    scene.render.resolution_x = RENDER_SIZE
    scene.render.resolution_y = RENDER_SIZE
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.image_settings.color_depth = '8'
    scene.render.film_transparent = False
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    output_dir = ASSET_DIR / 'TIPO_3D'
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    blend_path = output_dir / ('TIPO_box_' + stamp + '.blend')
    render_path = output_dir / ('TIPO_render_' + stamp + '.png')
    scene.render.filepath = str(render_path)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                area.spaces.active.clip_start = 0.001
                area.spaces.active.clip_end = 20
                area.spaces.active.region_3d.view_perspective = 'CAMERA'
                area.spaces.active.overlay.show_overlays = False
                area.spaces.active.shading.type = 'MATERIAL'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    print('TIPO: готово. BLEND: ' + str(blend_path), flush=True)
    print('TIPO: ровно одна карта, окно прорезано геометрически, PNG упакованы.', flush=True)
    if RENDER_NOW:
        print('TIPO: выполняю предметный рендер…', flush=True)
        bpy.ops.render.render(write_still=True, scene=scene.name)
        print('TIPO: PNG: ' + str(render_path), flush=True)
    return scene


if __name__ == '__main__':
    build()
