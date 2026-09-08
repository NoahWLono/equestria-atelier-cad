#!/usr/bin/env python3
"""Construct exact OpenCascade solids and export this collection's CAD assets.

The editable design contract uses millimeters, +X nose, +Y flank and +Z up.
STEP keeps the named, colored overlapping design components. STL is the full
boolean union of their BRep tessellations. GLB converts coordinates to meters
and +Y up, preserving every component, its name, and its material.
"""
from __future__ import annotations

import argparse
from collections import Counter
from functools import lru_cache
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import struct
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("XDG_CACHE_HOME", str(ROOT / ".cache"))
if sys.platform.startswith("linux"):
    os.environ.setdefault("FONTCONFIG_FILE", str(Path(__file__).with_name("fontconfig.conf")))

import cadquery as cq
from OCP.BRep import BRep_Tool
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.TopAbs import TopAbs_Orientation
from OCP.TopLoc import TopLoc_Location
import manifold3d
import numpy as np
import trimesh


LINEAR_TOLERANCE_MM = 0.10
ANGULAR_TOLERANCE_RAD = 0.12
STL_SIMPLIFICATION_TOLERANCE_MM = 0.0


class STLSerializationError(ValueError):
    """A valid indexed union could not round-trip through STL serialization."""


def _vec(values):
    arr = np.asarray(values, dtype=float)
    if arr.shape != (3,) or not np.isfinite(arr).all():
        raise ValueError(f"Expected three finite coordinates, got {values!r}")
    return arr


def _positive(value, label):
    value = float(value)
    if not np.isfinite(value) or value <= 0:
        raise ValueError(f"{label} must be finite and positive")
    return value


@lru_cache(maxsize=1)
def _font_path():
    candidates = [
        os.environ.get("CAD_FONT_PATH", ""),
        str(ROOT / "assets/fonts/NotoSans-Bold.ttf"),
        "/usr/share/fonts/noto/NotoSans-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise ValueError("No supported bold sans font found. Set CAD_FONT_PATH to a .ttf or .otf font file")


def _rotate(shape, rotation, center):
    center = _vec(center)
    for angle, axis in zip(_vec(rotation), np.eye(3)):
        if angle:
            shape = shape.rotate(tuple(center), tuple(center + axis), float(angle))
    return shape


@lru_cache(maxsize=256)
def _ellipsoid(rx, ry, rz):
    unit = cq.Solid.makeSphere(1.0, angleDegrees1=-90, angleDegrees2=90)
    matrix = cq.Matrix([[rx, 0, 0, 0], [0, ry, 0, 0], [0, 0, rz, 0], [0, 0, 0, 1]])
    return unit.transformGeometry(matrix)


def _catmull_rom(values, subdivisions=4):
    values = np.asarray(values, dtype=float)
    padded = np.concatenate([values[:1], values, values[-1:]], axis=0)
    samples = []
    for i in range(len(values) - 1):
        a, b, c, d = padded[i:i + 4]
        for t in np.arange(subdivisions) / subdivisions:
            samples.append(.5 * ((2*b) + (-a+c)*t + (2*a-5*b+4*c-d)*t*t + (-a+3*b-3*c+d)*t*t*t))
    samples.append(values[-1])
    return np.asarray(samples)


def _tube(part):
    points = np.asarray(part["points"], dtype=float)
    radii = np.asarray(part["radii"], dtype=float)
    if points.ndim != 2 or points.shape[1] != 3 or len(points) < 2:
        raise ValueError("A tube needs at least two 3D points")
    if radii.shape != (len(points),) or not np.isfinite(points).all() or not np.isfinite(radii).all():
        raise ValueError("Tube points and radii must be finite and have matching lengths")
    if np.any(radii < .25):
        raise ValueError("Tube radius is below the 0.25 mm contract minimum")
    if np.any(np.linalg.norm(np.diff(points, axis=0), axis=1) < 1e-6):
        raise ValueError("Tube has duplicate adjacent control points")
    centers = _catmull_rom(points)
    sizes = np.maximum(.25, _catmull_rom(radii))
    tangents = np.gradient(centers, axis=0)
    lengths = np.linalg.norm(tangents, axis=1)
    if np.any(lengths < 1e-8):
        raise ValueError("Tube centerline reverses through a zero tangent")
    tangents /= lengths[:, None]
    previous_x = None
    wires = []
    for center, normal, radius in zip(centers, tangents, sizes):
        if previous_x is None:
            candidate = np.eye(3)[np.argmin(np.abs(normal))]
        else:
            candidate = previous_x
        x_axis = candidate - normal * np.dot(candidate, normal)
        if np.linalg.norm(x_axis) < 1e-6:
            candidate = np.eye(3)[np.argmin(np.abs(normal))]
            x_axis = candidate - normal * np.dot(candidate, normal)
        x_axis /= np.linalg.norm(x_axis)
        plane = cq.Plane(origin=tuple(center), xDir=tuple(x_axis), normal=tuple(normal))
        wires.append(cq.Workplane(plane).circle(float(radius)).val())
        previous_x = x_axis
    return cq.Solid.makeLoft(wires, ruled=False)


def build_part(part):
    """Build a contract primitive as a shape containing valid positive solids."""
    kind = part["kind"]
    if kind == "ellipsoid":
        rx, ry, rz = (_positive(x, "ellipsoid radius") for x in part["radii"])
        center = _vec(part["center"])
        shape = _ellipsoid(rx, ry, rz).translate(tuple(center))
        shape = _rotate(shape, part.get("rotation", [0, 0, 0]), center)
    elif kind == "tube":
        shape = _tube(part)
    elif kind == "cone":
        start, end = _vec(part["start"]), _vec(part["end"])
        delta = end - start
        height = _positive(np.linalg.norm(delta), "cone length")
        radius1, radius2 = _positive(part["r1"], "cone radius"), _positive(part["r2"], "cone radius")
        if abs(radius1 - radius2) < 1e-10:
            shape = cq.Solid.makeCylinder(radius1, height, cq.Vector(*start), cq.Vector(*(delta / height)))
        else:
            shape = cq.Solid.makeCone(radius1, radius2, height, cq.Vector(*start), cq.Vector(*(delta / height)))
    elif kind == "cylinder":
        center = _vec(part["center"])
        shape = cq.Solid.makeCylinder(_positive(part["radius"], "cylinder radius"), _positive(part["height"], "cylinder height"), cq.Vector(*center))
        shape = _rotate(shape, part.get("rotation", [0, 0, 0]), center)
    elif kind == "polygon":
        origin, u, v = _vec(part["origin"]), _vec(part["u"]), _vec(part["v"])
        if abs(np.linalg.norm(u) - 1) > 1e-6 or abs(np.linalg.norm(v) - 1) > 1e-6 or abs(np.dot(u, v)) > 1e-6:
            raise ValueError("Polygon u and v vectors must be orthonormal")
        uv = np.asarray(part["points"], dtype=float)
        if uv.ndim != 2 or uv.shape[1] != 2 or len(uv) < 3 or not np.isfinite(uv).all():
            raise ValueError("A polygon needs at least three finite UV points")
        signed_area = .5 * np.sum(uv[:, 0] * np.roll(uv[:, 1], -1) - np.roll(uv[:, 0], -1) * uv[:, 1])
        if signed_area <= 1e-9:
            raise ValueError("Polygon points must be counterclockwise with positive area")
        points = [cq.Vector(*(origin + u * x + v * y)) for x, y in uv]
        wire = cq.Wire.makePolygon(points, close=True)
        normal = np.cross(u, v)
        shape = cq.Solid.extrudeLinear(wire, [], cq.Vector(*(normal * _positive(part["depth"], "polygon depth"))))
    elif kind == "text":
        center = _vec(part["center"])
        if not str(part["text"]).strip():
            raise ValueError("Text must contain printable characters")
        text = cq.Workplane("XY").text(str(part["text"]), _positive(part["size"], "text size"), _positive(part["depth"], "text depth"), fontPath=_font_path(), kind="bold", halign="center", valign="center", combine=False)
        shape = cq.Compound.makeCompound(text.vals()).translate(tuple(center))
        shape = _rotate(shape, part.get("rotation", [0, 0, 0]), center)
    else:
        raise ValueError(f"Unsupported primitive kind {kind!r}")
    solids = shape.Solids()
    if not shape.isValid() or not solids or any(not solid.isValid() or solid.Volume() <= 1e-9 for solid in solids):
        raise ValueError(f"{part.get('name', kind)} produced invalid or non-positive-volume BRep geometry")
    return shape


def tessellate_part(shape):
    # CadQuery's default mesher uses relative deflection. Mesh explicitly with
    # absolute millimeters first, so the contract remains scale independent.
    BRepMesh_IncrementalMesh(shape.wrapped, LINEAR_TOLERANCE_MM, False, ANGULAR_TOLERANCE_RAD)
    vertices = []
    triangles = []
    offset = 0
    # Extract OCCT's existing absolute mesh directly. Shape.tessellate may
    # decide to remesh a face and reintroduce CadQuery's relative settings.
    for face in shape.Faces():
        location = TopLoc_Location()
        polygon = BRep_Tool.Triangulation_s(face.wrapped, location)
        if polygon is None:
            raise ValueError("OCCT failed to tessellate a BRep face")
        transform = location.Transformation()
        for i in range(1, polygon.NbNodes() + 1):
            point = polygon.Node(i).Transformed(transform)
            vertices.append((point.X(), point.Y(), point.Z()))
        reverse = face.wrapped.Orientation() == TopAbs_Orientation.TopAbs_REVERSED
        for triangle in polygon.Triangles():
            indices = [triangle.Value(i) + offset - 1 for i in (1, 2, 3)]
            triangles.append(indices[::-1] if reverse else indices)
        offset += polygon.NbNodes()
    mesh = trimesh.Trimesh(vertices=np.array(vertices), faces=np.array(triangles), process=True, validate=True)
    mesh.fix_normals(multibody=True)
    if not mesh.is_watertight or not mesh.is_winding_consistent or mesh.volume <= 0:
        raise ValueError(f"BRep tessellation is not a closed, consistently wound positive-volume mesh: watertight={mesh.is_watertight}, winding={mesh.is_winding_consistent}, volume={mesh.volume}")
    return mesh


def _bounds(shape):
    bbox = shape.BoundingBox()
    return [[bbox.xmin, bbox.ymin, bbox.zmin], [bbox.xmax, bbox.ymax, bbox.zmax]]


def _mesh_summary(mesh):
    return dict(watertight=bool(mesh.is_watertight), winding_consistent=bool(mesh.is_winding_consistent), vertex_count=len(mesh.vertices), triangle_count=len(mesh.faces), extents_mm=mesh.extents.tolist(), bounds_mm=mesh.bounds.tolist(), centroid_mm=mesh.centroid.tolist(), volume_mm3=float(mesh.volume))


def _color(hex_color):
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", str(hex_color)):
        raise ValueError(f"Expected hex RGB color, got {hex_color!r}")
    return [int(hex_color[i:i+2], 16) for i in (1, 3, 5)]


def _apply_linear_materials(tree, palette):
    """glTF factors are linear; preserve exact sRGB conversion after trimesh's
    uint8 material storage, which would otherwise quantize the linear factors.
    """
    for material in tree.get("materials", []):
        name = material.get("name")
        if name not in palette:
            raise ValueError(f"Unexpected GLB material name {name!r}")
        srgb = np.asarray(_color(palette[name]), dtype=float) / 255.0
        linear = np.where(srgb <= .04045, srgb / 12.92, ((srgb + .055) / 1.055) ** 2.4)
        material["pbrMetallicRoughness"]["baseColorFactor"] = linear.tolist() + [1.0]


def rewrite_glb_colors(path, parts):
    """Refresh an existing export's material factors without altering geometry."""
    path = Path(path)
    original = path.read_bytes()
    magic, version, total_size = struct.unpack_from("<4sII", original, 0)
    json_size, chunk_type = struct.unpack_from("<II", original, 12)
    if magic != b"glTF" or version != 2 or total_size != len(original) or chunk_type != 0x4E4F534A:
        raise ValueError("Not a valid GLB 2.0 file with an initial JSON chunk")
    tree = json.loads(original[20:20 + json_size])
    _apply_linear_materials(tree, {part["name"]: part["color"] for part in parts})
    encoded = json.dumps(tree, separators=(",", ":")).encode("utf-8")
    encoded += b" " * ((-len(encoded)) % 4)
    remaining = original[20 + json_size:]
    header = struct.pack("<4sII", b"glTF", 2, 20 + len(encoded) + len(remaining))
    path.write_bytes(header + struct.pack("<II", len(encoded), chunk_type) + encoded + remaining)


def _write_report(path, report):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")


def _manifold_union(meshes):
    solids = []
    for name, mesh in meshes:
        if hasattr(manifold3d, "Mesh64"):
            data = manifold3d.Mesh64(vert_properties=np.asarray(mesh.vertices, dtype=np.float64), tri_verts=np.asarray(mesh.faces, dtype=np.uint64))
        else:
            data = manifold3d.Mesh(vert_properties=np.asarray(mesh.vertices, dtype=np.float32), tri_verts=np.asarray(mesh.faces, dtype=np.uint32))
        solid = manifold3d.Manifold(data)
        if solid.status() != manifold3d.Error.NoError or solid.is_empty():
            raise ValueError(f"Manifold rejected component {name}: {solid.status()}")
        solids.append(solid)
    union = manifold3d.Manifold.batch_boolean(solids, manifold3d.OpType.Add)
    if union.status() != manifold3d.Error.NoError or union.is_empty():
        raise ValueError(f"Manifold union failed: {union.status()}")
    original_shells = union.decompose()
    original_volume = union.volume()
    data = union.to_mesh64() if hasattr(union, "to_mesh64") else union.to_mesh()
    # Manifold already supplies indexed, consistently oriented, closed topology.
    # Generic Trimesh validation removes tiny intersection triangles and opens
    # otherwise valid unions; preserve the authoritative indices exactly.
    result = trimesh.Trimesh(vertices=np.asarray(data.vert_properties)[:, :3], faces=np.asarray(data.tri_verts), process=False)
    result.metadata["manifold"] = dict(simplification_tolerance_mm=STL_SIMPLIFICATION_TOLERANCE_MM, volume_before_mm3=original_volume, volume_after_mm3=union.volume(), shell_count_before=len(original_shells), shell_count_after=len(union.decompose()), original_shells=[dict(volume_mm3=shell.volume(), bounds_mm=list(shell.bounding_box())) for shell in original_shells])
    return result


def _write_stl(mesh, path):
    """Keep double-precision coordinates; binary STL rounds them to float32."""
    path = Path(path)
    candidate = path.with_name(f".{path.stem}.candidate.stl")
    mesh.export(candidate, file_type="stl_ascii")
    imported = trimesh.load(candidate, force="mesh")
    exported = mesh
    removed = 0
    before_volume = float(imported.volume)
    before_bounds = imported.bounds.copy()
    if not imported.is_watertight:
        faces = imported.faces
        keep = (faces[:, 0] != faces[:, 1]) & (faces[:, 1] != faces[:, 2]) & (faces[:, 0] != faces[:, 2])
        removed = int((~keep).sum())
        if removed:
            # Remove only triangles already reduced to a repeated vertex index
            # by the standard STL loader's weld. Never use an area tolerance:
            # tiny triangles with three distinct indices remain untouched.
            repaired = imported.copy()
            repaired.update_faces(keep)
            if not np.array_equal(repaired.bounds, before_bounds) or not np.isclose(repaired.volume, before_volume, rtol=0, atol=1e-9):
                candidate.unlink(missing_ok=True)
                raise STLSerializationError("Collapsed-index normalization changed STL bounds or volume")
            if repaired.is_watertight and repaired.is_winding_consistent and len(repaired.split(only_watertight=False)) == 1:
                repaired.export(candidate, file_type="stl_ascii")
                imported = trimesh.load(candidate, force="mesh")
                exported = repaired
    count = len(imported.split(only_watertight=False))
    if not imported.is_watertight or not imported.is_winding_consistent or count != 1:
        candidate.unlink(missing_ok=True)
        raise STLSerializationError(f"ASCII STL import-back validation failed: watertight={imported.is_watertight}, shells={count}")
    candidate.replace(path)
    return imported, imported, dict(encoding="ascii_float64", coordinate_precision="Python shortest round-trip float64 representation", connected_shell_count=count, collapsed_index_faces_removed=removed, normalization_volume_change_mm3=float(imported.volume) - before_volume, normalization_bounds_changed=not np.array_equal(imported.bounds, before_bounds))


def export_character(character, output_root=ROOT / "outputs"):
    """Export one design. A failed print validation remains explicit in its report."""
    started = time.monotonic()
    output_root = Path(output_root)
    identifier = character["id"]
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", identifier):
        raise ValueError("Character ID must be a safe lowercase file stem")
    for directory in ("step", "stl", "color", "reports"):
        (output_root / directory).mkdir(parents=True, exist_ok=True)
    report_path = output_root / "reports" / f"{identifier}.json"
    design_sha256 = hashlib.sha256(json.dumps(character, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    report = dict(id=identifier, name=character["name"], design_sha256=design_sha256, status="building", source_units="mm", source_axes="X forward, Y flank, Z up", tolerances=dict(linear_mm=LINEAR_TOLERANCE_MM, linear_mode="absolute", angular_rad=ANGULAR_TOLERANCE_RAD, stl_simplification_mm=STL_SIMPLIFICATION_TOLERANCE_MM), components=[], outputs={}, versions={name: importlib.metadata.version(name) for name in ("cadquery", "trimesh", "manifold3d", "numpy")})
    try:
        parts = character["parts"]
        names = [p["name"] for p in parts]
        duplicates = [name for name, count in Counter(names).items() if count > 1]
        if not parts or duplicates:
            raise ValueError(f"A figure must have parts with unique names; duplicates={duplicates}")
        assembly = cq.Assembly(name=identifier)
        scene = trimesh.Scene()
        meshes = []
        shapes = []
        solid_count = 0
        glb_transform = np.array([[.001, 0, 0, 0], [0, 0, .001, 0], [0, -.001, 0, 0], [0, 0, 0, 1]])
        for index, part in enumerate(parts):
            component_started = time.monotonic()
            name = part["name"]
            try:
                rgb = _color(part["color"])
                shape = build_part(part)
                mesh = tessellate_part(shape)
            except Exception as exc:
                report["components"].append(dict(name=name, kind=part["kind"], valid=False, error=str(exc)))
                raise ValueError(f"{identifier}/{name}: {exc}") from exc
            count = len(shape.Solids())
            solid_count += count
            report["components"].append(dict(name=name, kind=part["kind"], color=part["color"], valid=True, cad_solid_count=count, cad_volume_mm3=shape.Volume(), cad_bounds_mm=_bounds(shape), mesh=_mesh_summary(mesh), duration_seconds=round(time.monotonic() - component_started, 3)))
            assembly.add(shape, name=name, color=cq.Color(*(c / 255 for c in rgb)))
            colored = mesh.copy()
            colored.visual = trimesh.visual.TextureVisuals(material=trimesh.visual.material.PBRMaterial(name=name, baseColorFactor=rgb + [255], metallicFactor=0.0, roughnessFactor=.64, doubleSided=False))
            colored.apply_transform(glb_transform)
            scene.add_geometry(colored, geom_name=name, node_name=name)
            meshes.append((name, mesh))
            shapes.append(shape)
            if (index + 1) % 20 == 0 or index == len(parts) - 1:
                print(f"{identifier}: built {index + 1}/{len(parts)} components", flush=True)
        cad = cq.Compound.makeCompound(shapes)
        report["cad"] = dict(valid=cad.isValid(), component_count=len(parts), solid_count=solid_count, volume_mm3=cad.Volume(), bounds_mm=_bounds(cad), note="Overlapping design-component assembly; volume sums components.")
        step_path = output_root / "step" / f"{identifier}.step"
        print(f"{identifier}: exporting and importing STEP", flush=True)
        assembly.export(str(step_path), exportType="STEP", mode="default")
        imported = cq.Compound.makeCompound(cq.importers.importStep(str(step_path)).vals())
        imported_solids = imported.Solids()
        report["step_import"] = dict(valid=bool(imported.isValid() and all(s.isValid() and s.Volume() > 0 for s in imported_solids)), solid_count=len(imported_solids), volume_mm3=imported.Volume(), bounds_mm=_bounds(imported))
        if not report["step_import"]["valid"] or len(imported_solids) != solid_count:
            raise ValueError("STEP import-back validation failed or changed the solid count")
        if abs(imported.Volume() - cad.Volume()) > max(.01, abs(cad.Volume()) * 1e-6):
            raise ValueError("STEP import-back validation changed the component volume")
        report["outputs"]["step"] = str(step_path.relative_to(output_root))
        glb_path = output_root / "color" / f"{identifier}.glb"
        scene.metadata.update(dict(units="meters", source_units="millimeters", axis_conversion="(X, Y, Z)mm -> (X, Z, -Y)/1000 meters"))
        palette = {part["name"]: part["color"] for part in parts}
        glb_path.write_bytes(scene.export(file_type="glb", tree_postprocessor=lambda tree: _apply_linear_materials(tree, palette)))
        loaded_glb = trimesh.load(glb_path, force="scene")
        if len(loaded_glb.geometry) != len(parts):
            raise ValueError("GLB import-back validation changed the component count")
        report["glb"] = dict(component_count=len(loaded_glb.geometry), units="m", up_axis="Y", color_encoding="sRGB hex converted to exact linear glTF baseColorFactor", bounds_m=loaded_glb.bounds.tolist(), names_preserved=sorted(loaded_glb.geometry) == sorted(names))
        if not report["glb"]["names_preserved"]:
            raise ValueError("GLB import-back validation lost component names")
        report["outputs"]["glb"] = str(glb_path.relative_to(output_root))
        print(f"{identifier}: boolean union of {len(meshes)} meshes", flush=True)
        union = _manifold_union(meshes)
        shells = list(union.split(only_watertight=False))
        shells.sort(key=lambda mesh: abs(mesh.volume), reverse=True)
        report["stl"] = _mesh_summary(union)
        report["stl"]["manifold"] = union.metadata["manifold"]
        report["stl"]["connected_shell_count"] = len(shells)
        report["stl"]["shells"] = []
        for shell in shells:
            summary = _mesh_summary(shell)
            summary["nearby_components"] = [name for name, mesh in meshes if np.all(mesh.bounds[1] >= shell.bounds[0] - .01) and np.all(mesh.bounds[0] <= shell.bounds[1] + .01)]
            report["stl"]["shells"].append(summary)
        if union.metadata["manifold"]["shell_count_before"] != union.metadata["manifold"]["shell_count_after"]:
            raise ValueError(f"{identifier}: precision simplification changed the connected component count; no components may be dropped")
        if len(shells) != 1:
            raise ValueError(f"{identifier}: printable union has {len(shells)} disconnected shells; see shell bounds and nearby_components in report")
        if not union.is_watertight or not union.is_winding_consistent or union.volume <= 0:
            raise ValueError(f"{identifier}: union is not a valid closed printable mesh")
        if union.bounds[0, 2] < -.01:
            raise ValueError(f"{identifier}: printable figure extends below its Z=0 base")
        stl_path = output_root / "stl" / f"{identifier}.stl"
        exported_stl, imported_stl, serialization = _write_stl(union, stl_path)
        report["stl"]["raw_triangle_count"] = len(union.faces)
        report["stl"].update(_mesh_summary(exported_stl))
        report["stl"]["shells"] = [_mesh_summary(exported_stl)]
        report["stl"]["serialization"] = serialization
        stl_shells = list(imported_stl.split(only_watertight=False))
        report["stl_import"] = _mesh_summary(imported_stl)
        report["stl_import"]["connected_shell_count"] = len(stl_shells)
        if not imported_stl.is_watertight or not imported_stl.is_winding_consistent or len(stl_shells) != 1:
            raise ValueError("STL import-back validation failed after ASCII float64 serialization")
        report["outputs"]["stl"] = str(stl_path.relative_to(output_root))
        report["output_sha256"] = {kind: hashlib.sha256((output_root / relative_path).read_bytes()).hexdigest() for kind, relative_path in report["outputs"].items()}
        report["status"] = "passed"
        report["duration_seconds"] = round(time.monotonic() - started, 3)
        _write_report(report_path, report)
        print(f"{identifier}: PASS, {len(parts)} CAD components, {len(union.faces):,} STL triangles, {report['duration_seconds']:.1f}s", flush=True)
        return report
    except Exception as exc:
        report["status"] = "failed"
        report["error"] = str(exc)
        report["duration_seconds"] = round(time.monotonic() - started, 3)
        _write_report(report_path, report)
        if isinstance(exc, STLSerializationError):
            print(f"{identifier}: STL serialization needs STEP precision; rebuilding STL from the freshly exported STEP", flush=True)
            return repair_character_stl(character, output_root, source="step")
        raise


def repair_character_stl(character, output_root=ROOT / "outputs", source="glb"):
    """Rebuild only STL from existing named BRep tessellations in the GLB."""
    started = time.monotonic()
    output_root = Path(output_root)
    identifier = character["id"]
    report_path = output_root / "reports" / f"{identifier}.json"
    report = json.loads(report_path.read_text())
    digest = hashlib.sha256(json.dumps(character, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if report.get("design_sha256") != digest or not report.get("step_import", {}).get("valid"):
        raise ValueError("STL repair requires an existing valid STEP report for this exact character design")
    try:
        glb_path = output_root / "color" / f"{identifier}.glb"
        scene = trimesh.load(glb_path, force="scene")
        expected = {part["name"] for part in character["parts"]}
        if set(scene.geometry) != expected:
            raise ValueError("STL repair GLB component names do not match the current design")
        component_reports = {component["name"]: component for component in report["components"]}
        meshes = []
        max_bounds_difference = 0.0
        for part in character["parts"]:
            name = part["name"]
            mesh = scene.geometry[name].copy()
            mesh.vertices = np.asarray(mesh.vertices)[:, [0, 2, 1]] * np.array([1000., -1000., 1000.])
            difference = float(np.max(np.abs(mesh.bounds - np.asarray(component_reports[name]["mesh"]["bounds_mm"]))))
            max_bounds_difference = max(max_bounds_difference, difference)
            if difference > .001 or not mesh.is_watertight or not mesh.is_winding_consistent:
                raise ValueError(f"STL repair component {name} failed geometry provenance checks")
            meshes.append((name, mesh))
        source_description = "named BRep tessellations recovered from GLB float32 positions"
        source_step_sha256 = None
        if source == "step":
            step_path = output_root / "step" / f"{identifier}.step"
            imported = cq.Compound.makeCompound(cq.importers.importStep(str(step_path)).vals())
            solids = imported.Solids()
            if not imported.isValid() or len(solids) != report["step_import"]["solid_count"]:
                raise ValueError("STEP solid provenance validation failed during STL repair")
            if np.max(np.abs(np.asarray(_bounds(imported)) - np.asarray(report["step_import"]["bounds_mm"]))) > .0001:
                raise ValueError("STEP bounds changed since the existing validation report")
            print(f"{identifier}: tessellating {len(solids)} imported STEP solids", flush=True)
            meshes = [(f"step_solid_{i:03d}", tessellate_part(solid)) for i, solid in enumerate(solids)]
            source_description = "absolute-tolerance float64 tessellation of imported STEP solids"
            source_step_sha256 = hashlib.sha256(step_path.read_bytes()).hexdigest()
        print(f"{identifier}: rebuilding unsimplified STL from {len(meshes)} {source.upper()} meshes", flush=True)
        union = _manifold_union(meshes)
        shells = sorted(union.split(only_watertight=False), key=lambda shell: abs(shell.volume), reverse=True)
        report["stl"] = _mesh_summary(union)
        report["stl"].update(manifold=union.metadata["manifold"], connected_shell_count=len(shells), shells=[_mesh_summary(shell) for shell in shells])
        if len(shells) != 1 or not union.is_watertight or not union.is_winding_consistent or union.volume <= 0:
            raise ValueError(f"STL repair raw union failed: watertight={union.is_watertight}, shells={len(shells)}")
        path = output_root / "stl" / f"{identifier}.stl"
        exported_stl, imported, serialization = _write_stl(union, path)
        report["stl"]["raw_triangle_count"] = len(union.faces)
        report["stl"].update(_mesh_summary(exported_stl))
        report["stl"]["shells"] = [_mesh_summary(exported_stl)]
        report["stl"]["serialization"] = serialization
        report["stl_import"] = _mesh_summary(imported)
        report["stl_import"]["connected_shell_count"] = serialization["connected_shell_count"]
        report["outputs"]["stl"] = str(path.relative_to(output_root))
        report["tolerances"]["stl_simplification_mm"] = 0.0
        report["stl_repair"] = dict(source=source_description, source_glb_sha256=hashlib.sha256(glb_path.read_bytes()).hexdigest(), maximum_component_bounds_difference_mm=max_bounds_difference, duration_seconds=round(time.monotonic() - started, 3))
        if source_step_sha256:
            report["stl_repair"]["source_step_sha256"] = source_step_sha256
        report["output_sha256"] = {kind: hashlib.sha256((output_root / relative_path).read_bytes()).hexdigest() for kind, relative_path in report["outputs"].items()}
        report["status"] = "passed"
        report.pop("error", None)
        _write_report(report_path, report)
        print(f"{identifier}: PASS ASCII STL, {len(union.faces):,} triangles, {time.monotonic() - started:.1f}s", flush=True)
        return report
    except Exception as exc:
        report["status"] = "failed"
        report["error"] = str(exc)
        _write_report(report_path, report)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "outputs/collection.json")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs")
    parser.add_argument("--only", action="append", metavar="ID", help="Export only this character; repeat for multiple IDs")
    parser.add_argument("--repair-stl", action="store_true", help="Rebuild STL from existing matching-design GLBs and update validation reports")
    parser.add_argument("--repair-source", choices=("glb", "step"), default="glb", help="Source for --repair-stl (STEP retains full CAD precision)")
    args = parser.parse_args(argv)
    collection = json.loads(args.input.read_text())
    if collection.get("units") != "mm":
        parser.error("Input collection must declare millimeter units")
    characters = collection["characters"]
    if args.only:
        missing = set(args.only) - {c["id"] for c in characters}
        if missing:
            parser.error("Unknown character IDs: " + ", ".join(sorted(missing)))
        characters = [c for c in characters if c["id"] in args.only]
    failures = []
    for character in characters:
        try:
            if args.repair_stl:
                repair_character_stl(character, args.output, source=args.repair_source)
            else:
                export_character(character, args.output)
        except Exception:
            traceback.print_exc()
            failures.append(character["id"])
    if failures:
        print("Export failed for: " + ", ".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
