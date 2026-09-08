#!/usr/bin/env python3
"""Render the exported Equestria CAD geometry in a reproducible Blender studio.

Run with the Python environment containing bpy:
  .venv311/bin/python source/render_studio.py --all
  .venv311/bin/python source/render_studio.py --only luna --quick
  .venv311/bin/python source/render_studio.py --hero

The input is the actual colored CAD export, never a separate illustration mesh.
Native CAD dimensions remain meters in the saved Blender scene.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
RENDERS = OUT / "renders"


def reset_scene(quick: bool, resolution=(1200, 1400)):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 12 if quick else 16
    scene.cycles.adaptive_threshold = 0.05
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 6
    scene.cycles.diffuse_bounces = 3
    scene.cycles.glossy_bounces = 3
    scene.render.threads_mode = "FIXED"
    scene.render.threads = min(8, os.cpu_count() or 8)
    if hasattr(scene.render, "use_persistent_data"):
        scene.render.use_persistent_data = True
    scene.render.resolution_x = resolution[0] // (2 if quick else 1)
    scene.render.resolution_y = resolution[1] // (2 if quick else 1)
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.film_transparent = True
    scene.render.use_file_extension = True
    scene["preview_mode"] = quick
    scene.render.pixel_aspect_x = 1
    scene.render.pixel_aspect_y = 1
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = -0.3
    scene.view_settings.gamma = 1
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "MILLIMETERS"
    scene.unit_settings.scale_length = 1.0
    world = bpy.data.worlds.new("Soft neutral studio environment")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.50, 0.58, 0.72, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.32
    scene.world = world
    return scene


def aim(obj, target):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def area(name, location, target, energy, size, color, size_y=None):
    light = bpy.data.lights.new(name, type="AREA")
    # The figurines are physically small (roughly 0.1m), so macro-studio lamps
    # need a fraction of the wattage used for human-scale Blender scenes.
    light.energy = energy * 0.12
    light.shape = "RECTANGLE" if size_y else "DISK"
    light.size = size
    if size_y:
        light.size_y = size_y
    light.color = color
    obj = bpy.data.objects.new(name, light)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    aim(obj, target)
    return obj


def studio_lights(hero=False):
    if hero:
        area("Key | enormous warm silk", (0.4, -0.5, 0.85), (0, 0, 0.08), 125, 0.80, (1.0, 0.87, 0.76))
        area("Fill | soft blue bounce", (-0.25, -0.3, 0.50), (0, 0, 0.08), 65, 0.65, (0.67, 0.79, 1.0))
        area("Rim | porcelain edge", (-0.35, 0.50, 0.60), (0, 0, 0.08), 130, 0.70, (0.84, 0.89, 1.0))
        area("Front | face catchlight", (0.50, -0.60, 0.3), (0, 0, 0.08), 23, 0.50, (1.0, 0.96, 0.90))
    else:
        area("Key | warm silk", (0.20, -0.24, 0.36), (0, 0, 0.065), 22, 0.23, (1.0, 0.87, 0.77))
        area("Fill | sky bounce", (-0.20, -0.13, 0.16), (0, 0, 0.060), 8, 0.21, (0.63, 0.78, 1.0))
        area("Rim | cool porcelain edge", (-0.11, 0.17, 0.30), (0, 0, 0.07), 24, 0.18, (0.78, 0.86, 1.0))
        area("Front | soft catchlight", (0.23, -0.28, 0.12), (0, 0, 0.075), 3.5, 0.14, (1.0, 0.94, 0.86))


def import_character(character, location=(0, 0, 0)):
    asset = OUT / "color" / f"{character['id']}.glb"
    if not asset.is_file():
        raise FileNotFoundError(f"Export the CAD model first: {asset}")
    if not bpy.context.scene.get("preview_mode", False):
        report_path = OUT / "reports" / f"{character['id']}.json"
        report = json.loads(report_path.read_text())
        design_hash = hashlib.sha256(json.dumps(character, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if report.get("design_sha256") != design_hash:
            raise ValueError(f"The exported design is stale for {character['id']}; rebuild its CAD outputs before final rendering")
        expected_hash = report.get("output_sha256", {}).get("glb")
        if expected_hash and expected_hash != hashlib.sha256(asset.read_bytes()).hexdigest():
            raise ValueError(f"The GLB hash differs from the CAD validation report for {character['id']}")
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(asset))
    imported = set(bpy.data.objects) - before
    parent = bpy.data.objects.new(character["name"], None)
    bpy.context.collection.objects.link(parent)
    for obj in imported:
        if obj.parent not in imported:
            obj.parent = parent
        if obj.type == "MESH":
            # CAD tessellation determines the surface exactly; interpolate only
            # shading normals so curved solids do not look like faceted meshes.
            for polygon in obj.data.polygons:
                polygon.use_smooth = True
            obj.data.set_sharp_from_angle(angle=math.radians(38))
            for slot in obj.material_slots:
                material = slot.material
                if material and material.use_nodes:
                    bsdf = next((n for n in material.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
                    if bsdf:
                        label = (material.name + " " + obj.name).lower()
                        metal = any(s in label for s in ("plinth_gold", "plinth_name", "golden_", "crown_band", "crown_point", "royal_collar", "royal_shoe")) and not any(s in label for s in ("_gem", "_jewel"))
                        bsdf.inputs["Roughness"].default_value = 0.28 if metal else (0.60 if "_hat_" in label else 0.36)
                        bsdf.inputs["Metallic"].default_value = 0.55 if metal else 0.04
                        bsdf.inputs["IOR"].default_value = 1.46
                        if "Coat Weight" in bsdf.inputs:
                            bsdf.inputs["Coat Weight"].default_value = 0.12
                            bsdf.inputs["Coat Roughness"].default_value = 0.23
    parent.location = location
    parent["character_id"] = character["id"]
    parent["source_file"] = str(asset.relative_to(ROOT))
    parent["source_sha256"] = hashlib.sha256(asset.read_bytes()).hexdigest()
    parent["source_units"] = "CAD millimeters; glTF meters; Blender meters"
    bpy.context.view_layer.update()
    meshes = [o for o in imported if o.type == "MESH"]
    if len(meshes) != len(character["parts"]):
        raise ValueError(f"Imported {len(meshes)} meshes for {character['id']}, expected {len(character['parts'])} CAD components")
    low, high = bounds(meshes)
    if high.z - low.z < 0.035 or high.z - low.z > 0.40:
        raise ValueError(f"Unexpected physical scale or orientation for {character['id']}: bounds {tuple(low)} to {tuple(high)}")
    return parent, meshes


def bounds(objects):
    points = [obj.matrix_world @ Vector(corner) for obj in objects for corner in obj.bound_box]
    if not points:
        raise ValueError("No imported CAD mesh objects found")
    return Vector(tuple(min(p[i] for p in points) for i in range(3))), Vector(tuple(max(p[i] for p in points) for i in range(3)))


def camera_for(objects, view="three-quarter", hero=False):
    scene = bpy.context.scene
    low, high = bounds(objects)
    target = (low + high) / 2
    directions = {
        "three-quarter": (0.68, -1.0, 0.48),
        "front": (1, 0, 0),
        "side": (0, -1, 0),
        "back": (-1, 0, 0),
    }
    direction = Vector((0.68, -1.0, 0.48) if hero else directions[view]).normalized()
    data = bpy.data.cameras.new(f"Camera | {view}")
    camera = bpy.data.objects.new(data.name, data)
    bpy.context.collection.objects.link(camera)
    camera.location = target + direction * 1.5
    aim(camera, target)
    data.type = "ORTHO"
    data.clip_start = 0.001
    data.clip_end = 100
    scene.camera = camera
    bpy.context.view_layer.update()
    inverse = camera.matrix_world.inverted()
    camera_points = [inverse @ (obj.matrix_world @ Vector(corner)) for obj in objects for corner in obj.bound_box]
    xs = [p.x for p in camera_points]
    ys = [p.y for p in camera_points]
    width, height = max(xs)-min(xs), max(ys)-min(ys)
    # Blender's AUTO sensor fit measures ortho_scale along the larger image
    # dimension. Query its actual frame rather than assuming a vertical scale.
    data.ortho_scale = 1.0
    frame = data.view_frame(scene=scene)
    frame_width = max(p.x for p in frame)-min(p.x for p in frame)
    frame_height = max(p.y for p in frame)-min(p.y for p in frame)
    data.ortho_scale = max(height/frame_height, width/frame_width) * (1.12 if hero else 1.18)
    # Center projected geometry. Rotated 3D bounds alone can leave excess space on one side.
    offset = camera.rotation_euler.to_quaternion() @ Vector(((max(xs)+min(xs))/2, (max(ys)+min(ys))/2, 0))
    camera.location += offset
    bpy.context.view_layer.update()
    from bpy_extras.object_utils import world_to_camera_view
    projected = [world_to_camera_view(scene, camera, obj.matrix_world @ Vector(corner)) for obj in objects for corner in obj.bound_box]
    if any(p.x < 0 or p.x > 1 or p.y < 0 or p.y > 1 for p in projected):
        raise ValueError("Camera framing clips imported CAD geometry")
    return camera


def ground():
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -0.00005))
    plane = bpy.context.object
    plane.name = "Studio floor | shadow catcher"
    plane.is_shadow_catcher = True
    material = bpy.data.materials.new("Neutral matte studio floor")
    material.use_nodes = True
    bsdf = material.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.3, 0.34, 0.4, 1)
    bsdf.inputs["Roughness"].default_value = 0.7
    plane.data.materials.append(material)
    return plane


def render(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    scene.render.filepath = str(path)
    started = time.monotonic()
    bpy.ops.render.render(write_still=True)
    evidence = {
        "image": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "engine": scene.render.engine,
        "blender_version": bpy.app.version_string,
        "resolution": [scene.render.resolution_x, scene.render.resolution_y],
        "samples": scene.cycles.samples,
        "camera": scene.camera.name,
        "units": "meters",
        "render_seconds": round(time.monotonic()-started, 3),
        "sources": [{"id": o["character_id"], "file": o["source_file"], "sha256": o["source_sha256"]} for o in bpy.data.objects if "character_id" in o],
    }
    if path.is_relative_to(RENDERS):
        report = OUT / "reports" / "renders" / (path.stem + ".json")
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"RENDERED {path}", flush=True)


def image_is_current(character, relative_image, resolution):
    image_path = RENDERS / relative_image
    report_path = OUT / "reports" / "renders" / f"{image_path.stem}.json"
    asset = OUT / "color" / f"{character['id']}.glb"
    if not (report_path.exists() and asset.exists() and image_path.exists()):
        return False
    report = json.loads(report_path.read_text())
    return report.get("resolution") == resolution and report.get("sources") == [{
        "id": character["id"], "file": str(asset.relative_to(ROOT)),
        "sha256": hashlib.sha256(asset.read_bytes()).hexdigest(),
    }] and report.get("sha256") == hashlib.sha256(image_path.read_bytes()).hexdigest()


def render_is_current(character, quick=False):
    return image_is_current(character, f"{character['id']}.png", [600, 700] if quick else [1200, 1400])


def orthographic_is_current(character, view, quick=False):
    return image_is_current(character, f"orthographic/{character['id']}_{view}.png", [450, 500] if quick else [900, 1000])


def individual(character, quick=False, orthographic=False, resume=False):
    skip_beauty = resume and render_is_current(character, quick)
    if skip_beauty and (not orthographic or all(orthographic_is_current(character, view, quick) for view in ("front", "side", "back"))):
        print(f"CURRENT {character['id']}", flush=True)
        return
    reset_scene(quick)
    _, meshes = import_character(character)
    studio_lights()
    ground()
    camera_for(meshes)
    if not skip_beauty:
        render(RENDERS / f"{character['id']}.png")
    if orthographic:
        bpy.context.scene.render.resolution_x = 450 if quick else 900
        bpy.context.scene.render.resolution_y = 500 if quick else 1000
        bpy.context.scene.cycles.samples = 8
        cameras = {view: camera_for(meshes, view=view) for view in ("front", "side", "back")}
        common_scale = max(camera.data.ortho_scale for camera in cameras.values())
        for view, camera in cameras.items():
            if resume and orthographic_is_current(character, view, quick):
                print(f"CURRENT {character['id']} {view}", flush=True)
                continue
            camera.data.ortho_scale = common_scale
            bpy.context.scene.camera = camera
            render(RENDERS / "orthographic" / f"{character['id']}_{view}.png")


def podium(location, radius=0.047, height=0.028):
    bpy.ops.mesh.primitive_cylinder_add(vertices=128, radius=radius, depth=height, location=(location[0], location[1], height/2))
    obj = bpy.context.object
    obj.name = "Removable photographic display plinth"
    bevel = obj.modifiers.new("Soft museum plinth edge", "BEVEL")
    bevel.width = 0.0012
    bevel.segments = 3
    obj.modifiers.new("Weighted normals", "WEIGHTED_NORMAL")
    material = bpy.data.materials.get("Display plinth | blue slate") or bpy.data.materials.new("Display plinth | blue slate")
    material.diffuse_color = (0.021, 0.033, 0.055, 1)
    material.use_nodes = True
    bsdf = material.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.021, 0.033, 0.055, 1)
    bsdf.inputs["Roughness"].default_value = 0.45
    obj.data.materials.append(material)
    return obj


def prepare_viewports():
    """Open the miniature collection at its camera, with its material colors visible."""
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                space = area.spaces.active
                space.region_3d.view_perspective = "CAMERA"
                space.region_3d.view_camera_zoom = 0
                space.clip_start = 0.001
                space.clip_end = 100
                space.shading.type = "MATERIAL"
                space.overlay.show_overlays = False


def hero(characters, quick=False):
    reset_scene(quick, resolution=(3600, 1900))
    by_id = {c["id"]: c for c in characters}
    # Camera-right and camera-away vectors. Row positions use physical meters.
    right = Vector((1.0, 0.68, 0)).normalized()
    away = Vector((-0.68, 1.0, 0)).normalized()
    royals = [c for c in characters if any(t in c["id"] for t in ("celestia", "luna", "clockwork"))]
    ordinary = [c for c in characters if c not in royals]
    all_meshes = []
    for index, character in enumerate(ordinary):
        sideways = (index-(len(ordinary)-1)/2) * 0.116
        position = right * sideways + away * (-0.024 + abs(sideways)*0.075)
        _, meshes = import_character(character, position)
        all_meshes.extend(meshes)
    # Taller figures form an elevated rear arc; their faces remain above the foreground.
    order = {"celestia": 0, "luna": 1, "clockwork_relativity": 2}
    royals.sort(key=lambda c: next((v for k, v in order.items() if k in c["id"]), 3))
    for index, character in enumerate(royals):
        sideways = (index-(len(royals)-1)/2) * 0.153
        position = right * sideways + away * 0.135
        platform_height = 0.036 if "clockwork" in character["id"] else 0.028
        podium(position, radius=0.051, height=platform_height)
        position.z = platform_height
        _, meshes = import_character(character, position)
        all_meshes.extend(meshes)
    studio_lights(hero=True)
    ground()
    camera_for(all_meshes, hero=True)
    scene = bpy.context.scene
    scene["collection_title"] = "EQUESTRIA | Atelier Collection"
    scene["geometry_provenance"] = "Imported from the colored CAD GLB exports; no illustration-only character geometry."
    scene["display_plinths"] = "Rear-row photographic display plinths are scene props, separate from the CAD figurines."
    scene.render.filepath = str(RENDERS / "full_cast.png")
    prepare_viewports()
    blend_path = OUT / "collection.blend"
    bpy.context.preferences.filepaths.save_version = 0
    source_records = sorted([{"id": o["character_id"], "file": o["source_file"], "sha256": o["source_sha256"]} for o in bpy.data.objects if "character_id" in o], key=lambda item: item["id"])
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path), compress=True)
    bpy.ops.wm.open_mainfile(filepath=str(blend_path))
    restored_records = sorted([{"id": o["character_id"], "file": o["source_file"], "sha256": o["source_sha256"]} for o in bpy.data.objects if "character_id" in o], key=lambda item: item["id"])
    if restored_records != source_records or len(restored_records) != len(characters) or bpy.context.scene.camera is None:
        raise ValueError("Saved Blender scene did not preserve all source characters and its camera")
    blend_report = {
        "file": str(blend_path.relative_to(ROOT)),
        "sha256": hashlib.sha256(blend_path.read_bytes()).hexdigest(),
        "character_count": len(restored_records),
        "characters": restored_records,
        "readback_verified": True,
        "blender_version": bpy.app.version_string,
        "scene_units": "meters",
    }
    (OUT / "reports" / "blend.json").write_text(json.dumps(blend_report, indent=2) + "\n")
    render(RENDERS / "full_cast.png")


def mother_and_son(characters, quick=False):
    reset_scene(quick, resolution=(2400, 2000))
    luna = next(c for c in characters if c["id"] == "princess_luna")
    clockwork = next(c for c in characters if c["id"] == "clockwork_relativity")
    right = Vector((1.0, 0.68, 0)).normalized()
    meshes = []
    for character, sideways in ((luna, -0.065), (clockwork, 0.065)):
        _, imported = import_character(character, right * sideways)
        meshes.extend(imported)
    studio_lights(hero=True)
    ground()
    camera_for(meshes)
    render(RENDERS / "luna_and_clockwork.png")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", metavar="ID")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--hero", action="store_true")
    parser.add_argument("--pair", action="store_true", help="Render Princess Luna with her son Clockwork Relativity")
    parser.add_argument("--orthographic", action="store_true")
    parser.add_argument("--quick", action="store_true", help="Half resolution and 12 samples for visual checks")
    parser.add_argument("--resume", action="store_true", help="Skip individual renders whose asset hashes and resolution still match")
    args = parser.parse_args()
    collection = json.loads((OUT / "collection.json").read_text())
    characters = collection["characters"]
    if args.only:
        found = next((c for c in characters if c["id"] == args.only), None)
        if found is None:
            parser.error(f"Unknown ID {args.only!r}; choose from " + ", ".join(c["id"] for c in characters))
        individual(found, args.quick, args.orthographic, args.resume)
    if args.all:
        for character in characters:
            individual(character, args.quick, args.orthographic, args.resume)
        hero(characters, args.quick)
        if any(c["id"] == "clockwork_relativity" for c in characters):
            mother_and_son(characters, args.quick)
    elif args.hero:
        hero(characters, args.quick)
    elif args.pair:
        mother_and_son(characters, args.quick)
    elif not args.only:
        parser.error("Choose --only ID, --all, --hero, or --pair")


if __name__ == "__main__":
    main()
