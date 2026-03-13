import json
import sys
import os
from pathlib import Path

# Dependency imports with safety guards
try:
    import numpy as np
except ImportError:
    np = None

try:
    import trimesh
except ImportError:
    trimesh = None

try:
    import bpy
    import mathutils
    IN_BLENDER = True
except ImportError:
    bpy = None
    mathutils = None
    IN_BLENDER = False

# Constants
DEFAULT_NAMESPACE = "minecraft"
FACES = ("north", "south", "east", "west", "up", "down")
DEFAULT_MIN_COMPONENT_RATIO = 0.02
DEFAULT_MIN_VERTICES = 8

WALL_MOUNT_VARIANTS = {
    "face=wall,facing=south": {},
    "face=wall,facing=west": {"y": 90},
    "face=wall,facing=north": {"y": 180},
    "face=wall,facing=east": {"y": 270},
    "face=floor,facing=south": {"x": 90},
    "face=floor,facing=west": {"x": 90, "y": 90},
    "face=floor,facing=north": {"x": 90, "y": 180},
    "face=floor,facing=east": {"x": 90, "y": 270},
    "face=ceiling,facing=south": {"x": 270},
    "face=ceiling,facing=west": {"x": 270, "y": 90},
    "face=ceiling,facing=north": {"x": 270, "y": 180},
    "face=ceiling,facing=east": {"x": 270, "y": 270},
}

# --- Shared Utilities ---

def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))

def round_box(values):
    return [round(value, 3) for value in values]

def make_textured_element(from_coords, to_coords, texture_ref):
    x1, y1, z1 = from_coords
    x2, y2, z2 = to_coords
    def uv_clamp(v): return clamp(v, 0, 16)
    uv_ns = [uv_clamp(x1), uv_clamp(16-y2), uv_clamp(x2), uv_clamp(16-y1)]
    uv_ew = [uv_clamp(z1), uv_clamp(16-y2), uv_clamp(z2), uv_clamp(16-y1)]
    uv_ud = [uv_clamp(x1), uv_clamp(z1), uv_clamp(x2), uv_clamp(z2)]
    return {
        "from": from_coords,
        "to": to_coords,
        "faces": {
            "north": {"uv": uv_ns, "texture": texture_ref},
            "south": {"uv": uv_ns, "texture": texture_ref},
            "east":  {"uv": uv_ew, "texture": texture_ref},
            "west":  {"uv": uv_ew, "texture": texture_ref},
            "up":    {"uv": uv_ud, "texture": texture_ref},
            "down":  {"uv": uv_ud, "texture": texture_ref}
        }
    }

def write_json(path, payload):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

def write_wall_mounted_assets(model_dir, model_name, namespace=DEFAULT_NAMESPACE):
    asset_root = Path(model_dir).parent.parent
    bs_path = asset_root / "blockstates" / f"{model_name}.json"
    item_path = asset_root / "models" / "item" / f"{model_name}.json"
    
    variants = {}
    for skey, transform in WALL_MOUNT_VARIANTS.items():
        val = {"model": f"{namespace}:block/{model_name}"}
        val.update(transform)
        variants[skey] = val
    write_json(bs_path, {"variants": variants})
    write_json(item_path, {"parent": f"{namespace}:block/{model_name}"})

# --- PBR Extraction Logic ---

def save_pbr_maps(scene, material_name, base_tex_path):
    # Standalone mode (trimesh)
    if not IN_BLENDER:
        if trimesh is None: return
        base_path = Path(base_tex_path)
        base_dir, base_stem = base_path.parent, base_path.stem
        for mesh in scene.dump():
            mat = getattr(getattr(mesh, "visual", None), "material", None)
            if mat and getattr(mat, "name", "") == material_name:
                img = getattr(mat, "image", None)
                if img: img.save(base_path)
                norm = getattr(mat, "normalTexture", None)
                if norm: norm.save(base_dir / f"{base_stem}_n.png")
                mr = getattr(mat, "metallicRoughnessTexture", None)
                if mr: mr.save(base_dir / f"{base_stem}_s.png")
                return
    else:
        # Blender mode
        base_path = Path(base_tex_path)
        base_dir, base_stem = base_path.parent, base_path.stem
        images = [i for i in bpy.data.images if i.size[0] > 0 and i.type != "RENDER_RESULT"]
        for img in images:
            name = img.name.lower()
            if any(x in name for x in ["normal", "_n", "height", "bump"]):
                img.filepath_raw = str(base_dir / f"{base_stem}_n.png")
                img.file_format = "PNG"
                img.save()
            elif any(x in name for x in ["spec", "_s", "metal", "rough", "smooth"]):
                img.filepath_raw = str(base_dir / f"{base_stem}_s.png")
                img.file_format = "PNG"
                img.save()
            elif material_name.lower() in name or len(images) == 1 or "color" in name:
                img.filepath_raw = str(base_path)
                img.file_format = "PNG"
                img.save()

# --- Minecraft Geometry Logic ---

def part_group_bounds(parts):
    if not parts: return None, None
    if np:
        all_mins = np.array([p[0][0] for p in parts])
        all_maxs = np.array([p[0][1] for p in parts])
        return all_mins.min(axis=0).tolist(), all_maxs.max(axis=0).tolist()
    
    g_min = [float(x) for x in parts[0][0]]
    g_max = [float(x) for x in parts[0][1]]
    for b_min, b_max in parts[1:]:
        for i in range(3):
            g_min[i] = min(g_min[i], float(b_min[i]))
            g_max[i] = max(g_max[i], float(b_max[i]))
    return g_min, g_max

def wall_parts_to_elements(parts, y_mode, scale=None, texture_ref="#texture"):
    if not parts: return []
    g_min, g_max = part_group_bounds(parts)
    # Coordinate flip logic (Blender Z is MC Y)
    if IN_BLENDER:
        # Mesh coords: X=X, Y=-Z, Z=Y (Standard Blender to MC flip)
        span_x = g_max[0] - g_min[0]
        span_y = g_max[2] - g_min[2]
        if scale is None: scale = 16.0 / max(span_x, span_y, 0.1)
        x_off, y_off = (g_min[0]+g_max[0])/2.0, (g_max[2] if y_mode == "top" else (g_min[2]+g_max[2])/2.0)
    else:
        # Trimesh coords
        span_x = g_max[0] - g_min[0]
        span_y = g_max[1] - g_min[1]
        if scale is None: scale = 16.0 / max(span_x, span_y, 0.1)
        x_off, y_off = (g_min[0]+g_max[0])/2.0, (g_max[1] if y_mode == "top" else (g_min[1]+g_max[1])/2.0)

    elements = []
    for (b_min, b_max), p_tex in parts:
        ref = p_tex if p_tex else texture_ref
        if IN_BLENDER:
            mx1, mx2 = (b_min[0]-x_off)*scale + 8.0, (b_max[0]-x_off)*scale + 8.0
            my1 = 16.0 - (y_off-b_min[2])*scale if y_mode == "top" else (b_min[2]-y_off)*scale + 8.0
            my2 = 16.0 - (y_off-b_max[2])*scale if y_mode == "top" else (b_max[2]-y_off)*scale + 8.0
            mz1, mz2 = 16.0 - (b_max[1]-g_min[1])*scale, 16.0 - (b_min[1]-g_min[1])*scale
        else:
            mx1, mx2 = (b_min[0]-x_off)*scale + 8.0, (b_max[0]-x_off)*scale + 8.0
            my1 = 16.0 - (y_off-b_min[1])*scale if y_mode == "top" else (b_min[1]-y_off)*scale + 8.0
            my2 = 16.0 - (y_off-b_max[1])*scale if y_mode == "top" else (b_max[1]-y_off)*scale + 8.0
            mz1, mz2 = 16.0 - (b_max[2]-g_min[2])*scale, 16.0 - (b_min[2]-g_min[2])*scale
            
        fc = [clamp(c, -16, 32) for c in round_box([mx1, my1, mz1])]
        tc = [clamp(c, -16, 32) for c in round_box([mx2, my2, mz2])]
        tc = [max(fc[i]+0.1, tc[i]) for i in range(3)]
        elements.append(make_textured_element(fc, tc, ref))
    return elements

# --- GeckoLib Export Logic ---

def export_geckolib_geo(name, elements, texture_name):
    # Standard GeckoLib/Bedrock 1.12.0 format
    cubes = []
    for e in elements:
        size = [round(e["to"][i] - e["from"][i], 3) for i in range(3)]
        cubes.append({
            "origin": [e["from"][0], e["from"][1], e["from"][2]],
            "size": size,
            "uv": [0, 0]
        })
    
    geo = {
        "format_version": "1.12.0",
        "minecraft:geometry": [{
            "description": {
                "identifier": f"geometry.{name}",
                "texture_width": 16,
                "texture_height": 16,
                "visible_bounds_width": 2,
                "visible_bounds_height": 2,
                "visible_bounds_offset": [0, 0, 0]
            },
            "bones": [{
                "name": "root",
                "pivot": [8, 0, 8],
                "cubes": cubes
            }]
        }]
    }
    return geo

def export_horizontal_kit(model_dir, tex, width=2.0, height=1.0, namespace=DEFAULT_NAMESPACE):
    mpath = Path(model_dir)
    hw, h = clamp(width/2.0, 0.5, 8.0), clamp(height, 0.2, 16.0)
    x1, x2 = round(8.0-hw, 3), round(8.0+hw, 3)
    
    kits = {
        "core": [[([x1, 0, x1], [x2, h, x2]), None]],
        "arm": [[([x1, 0, 0], [x2, h, x2]), None]],
        "straight": [[([x1, 0, 0], [x2, h, 16]), None]]
    }
    for kname, parts in kits.items():
        els = wall_parts_to_elements(parts, "bottom", texture_ref=f"#{tex}")
        write_json(mpath / f"{tex}_{kname}.json", {
            "parent": f"{namespace}:block/{tex}" if kname != "base" else "minecraft:block/block",
            "textures": {tex: f"{namespace}:block/{tex}", "particle": f"{namespace}:block/{tex}"},
            "elements": els
        })

def export_industrial_wiring_kit(model_dir, namespace=DEFAULT_NAMESPACE):
    tex = "electrical_wiring"
    mpath = Path(model_dir)
    write_json(mpath / "electrical_wiring_core.json", {
        "parent": f"{namespace}:block/electrical_wiring",
        "elements": [
            make_textured_element([6.3, 7.0, 6.3], [9.7, 9.5, 9.7], "#electrical_wiring"),
            make_textured_element([5.8, 7.9, 5.8], [10.2, 8.6, 10.2], "#electrical_wiring")
        ]
    })
    write_json(mpath / "electrical_wiring_straight.json", {
        "parent": f"{namespace}:block/electrical_wiring",
        "elements": [make_textured_element([6.2, 8.6, 0.0], [6.9, 9.2, 16.0], "#electrical_wiring")]
    })

# --- Main Entry Points ---

def run_cli():
    if trimesh is None: 
        print("Error: trimesh not installed. Use 'pip install trimesh'.")
        return
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python mc_prop_bridge.py multi-part <in.glb> <out_dir> <texture> [y_mode] [--namespace=id]")
        print("  python mc_prop_bridge.py horizontal-kit <out_dir> <texture> <width> <height> [--namespace=id]")
        print("  python mc_prop_bridge.py industrial-wiring-kit <out_dir> [--namespace=id]")
        print("  python mc_prop_bridge.py geckolib-geo <in.glb> <out_path> <texture>")
        return
        
    namespace = DEFAULT_NAMESPACE
    for arg in sys.argv:
        if arg.startswith("--namespace="):
            namespace = arg.split("=")[1]

    cmd = sys.argv[1]
    if cmd == "multi-part":
        glb_path, out_dir, tex = sys.argv[2], sys.argv[3], sys.argv[4]
        y_mode = sys.argv[5] if len(sys.argv) > 5 and not sys.argv[5].startswith("--") else "center"
        scene = trimesh.load(glb_path, force="scene")
        meshes = list(scene.dump())
        named_parts = {}
        for i, m in enumerate(meshes):
            name = m.metadata.get("name", f"part_{i}")
            if name not in named_parts: named_parts[name] = []
            if m.bounds is not None and len(m.vertices) > 0:
                comps = m.split(only_watertight=False) if hasattr(m, 'split') else [m]
                for c in comps: named_parts[name].append((c.bounds, f"#{tex}"))
        
        for name, parts in named_parts.items():
            els = wall_parts_to_elements(parts, y_mode, texture_ref=f"#{tex}")
            write_json(Path(out_dir) / f"{name}.json", {
                "parent": "minecraft:block/block",
                "textures": {tex: f"{namespace}:block/{tex}", "particle": f"{namespace}:block/{tex}"},
                "elements": els
            })
            write_wall_mounted_assets(out_dir, name, namespace)
            print(f"Exported {name}")
    elif cmd == "horizontal-kit":
        export_horizontal_kit(sys.argv[2], sys.argv[3], float(sys.argv[4]), float(sys.argv[5]), namespace)
    elif cmd == "industrial-wiring-kit":
        export_industrial_wiring_kit(sys.argv[2], namespace)
    elif cmd == "geckolib-geo":
        # Format: python mc_prop_bridge.py geckolib-geo <in.glb> <out_path> <texture>
        glb_path, out_path, tex = sys.argv[2], sys.argv[3], sys.argv[4]
        scene = trimesh.load(glb_path, force="scene")
        meshes = list(scene.dump())
        parts = []
        for m in meshes:
            if m.bounds is not None and len(m.vertices) > 0:
                parts.append((m.bounds, f"#{tex}"))
        els = wall_parts_to_elements(parts, "center", texture_ref=f"#{tex}")
        geo = export_geckolib_geo(Path(out_path).stem, els, tex)
        write_json(out_path, geo)
        print(f"Exported GeckoLib geometry to {out_path}")
def run_blender():
    # Detect args after '--'
    if "--" not in sys.argv: return
    args = sys.argv[sys.argv.index("--") + 1:]
    glb_path, out_dir, tex_name = args[0], args[1], args[2]
    namespace = args[3] if len(args) > 3 else DEFAULT_NAMESPACE
    
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    bpy.ops.import_scene.gltf(filepath=glb_path)
    
    save_pbr_maps(None, "", Path(out_dir).parent.parent / "textures" / "block" / f"{tex_name}.png")
    
    objs = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    for o in objs:
        # Separate loose parts in-place
        bpy.ops.object.select_all(action='DESELECT')
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.separate(type='LOOSE')
        bpy.ops.object.mode_set(mode='OBJECT')
        
        parts = []
        for p in bpy.context.selected_objects:
            c = [o.matrix_world @ mathutils.Vector(v) for v in p.bound_box]
            parts.append((([min(v[i] for v in c) for i in range(3)], [max(v[i] for v in c) for i in range(3)]), f"#{tex_name}"))
        
        cname = "".join(c if c.isalnum() else "_" for c in o.name.lower())
        els = wall_parts_to_elements(parts, "center", texture_ref=f"#{tex_name}")
        write_json(Path(out_dir) / f"{cname}.json", {
            "parent": "minecraft:block/block",
            "textures": {tex_name: f"{namespace}:block/{tex_name}", "particle": f"{namespace}:block/{tex_name}"},
            "elements": els
        })
        write_wall_mounted_assets(out_dir, cname, namespace)
        print(f"Exported {cname}")

if __name__ == "__main__":
    import traceback
    try:
        if IN_BLENDER: run_blender()
        else: run_cli()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
