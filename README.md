# MC-Prop-Bridge

A tool for converting 3D models (GLB/GLTF) into Minecraft JSON models. Designed for complex industrial props that are too tedious to build manually in Blockbench.

## Features
- **Standalone & Blender Plugin**: Works as a command-line tool or runs directly inside Blender.
- **Auto-Discovery**: Automatically splits GLB files into separate models based on object names.
- **PBR Extraction**: Saves Normal (`_n`) and Specular (`_s`) maps using the LabPBR 1.3 standard for shader support.
- **GeckoLib Mode**: Can export `.geo.json` to bypass standard Minecraft rotation limits.
- **UV Projection**: Proportional planar mapping to prevent texture smearing on custom-sized elements.

## Requirements
- Python 3.10+
- `trimesh` and `numpy` (for standalone/CLI mode)
- Blender (for plugin mode)

## Usage

### 1. Standalone / CLI
Use this to batch convert GLB files.
```bash
python mc_prop_bridge.py multi-part input.glb output_dir texture_name --namespace=your_mod_id
```

### 2. Blender Mode
Import the script into Blender or run it headless to convert scenes.
```bash
blender -b --python mc_prop_bridge.py -- input.glb output_dir texture_name your_mod_id
```

### 3. GeckoLib Export
For models that need arbitrary rotations beyond the 22.5° limit.
```bash
python mc_prop_bridge.py geckolib-geo input.glb output.geo.json texture_name
```

## Modular Kits
Generate optimized parts for modular systems like wiring or pipes.
```bash
python mc_prop_bridge.py horizontal-kit output_dir texture_name width height --namespace=your_mod_id
```

## Credits
Author: [VocalOpal](https://github.com/VocalOpal)
License: MIT
