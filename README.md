# MC-Prop-Bridge

A tool for converting 3D models (GLB/GLTF) into Minecraft JSON models. Designed for complex furniture, decorative items, and architectural props.

## Features
- **Standalone & Blender Plugin**: Works as a command-line tool or runs directly inside Blender.
- **Optimization Engine**: Built-in geometric merger to reduce the number of Minecraft box elements, preventing client-side lag.
- **Auto-Discovery**: Automatically splits GLB files into separate models based on object names.
- **PBR Extraction**: Saves Normal (`_n`) and Specular (`_s`) maps using the LabPBR 1.3 standard for shader support.
- **GeckoLib Mode**: Can export `.geo.json` to bypass standard Minecraft rotation limits.
- **Proportional UVs**: Automatic planar mapping to ensure textures match the scale of your 3D parts.
- **Embedded Attribution**: Every generated model includes a hardcoded `credit` metadata field identifying **VocalOpal** as a digital trademark.

## License & Attribution
This tool is released under the **MC-Prop-Bridge Attribution License**.
- **No Open-Source Requirement**: You are **not** forced to open-source your own mod or project. You can use this tool for private, commercial, or closed-source mods.
- **Credit Required**: You **must** provide visible credit to **VocalOpal** in your project's documentation, credits file, or in-game screen.
- **Trademark Integrity**: The generated `credit` field in the JSON files must not be removed.

## Requirements
- Python 3.10+
- `trimesh` and `numpy` (for standalone/CLI mode)
- Blender (for plugin mode)

## Usage

### 1. Standalone / CLI
Use this to batch convert models from GLB to JSON.
```bash
python mc_prop_bridge.py multi-part input.glb output_dir texture_name --namespace=your_mod_id --optimize
```

### 2. Blender Mode
Import the script into Blender to convert specific meshes from your scene.
```bash
blender -b --python mc_prop_bridge.py -- input.glb output_dir texture_name your_mod_id --optimize
```

### 3. GeckoLib Export
For furniture or props that require smooth rotations beyond the 22.5° limit.
```bash
python mc_prop_bridge.py geckolib-geo input.glb output.geo.json texture_name
```

## Credits
Author: [VocalOpal](https://github.com/VocalOpal)
Code: Antigravity
License: Custom Attribution
