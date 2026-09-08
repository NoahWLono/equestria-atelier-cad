"""Geometry and serialization acceptance tests for the CAD exporter."""
from pathlib import Path
import importlib.util
import json
import struct
import tempfile
import unittest


SAMPLE_PARTS = [
    dict(name="base", kind="cylinder", color="#5588aa", center=[0, 0, 0], radius=18, height=3),
    dict(name="body", kind="ellipsoid", color="#dd8866", center=[0, 0, 7], radii=[5, 4, 6], rotation=[8, 12, 10]),
    dict(name="mane", kind="tube", color="#7733aa", points=[[0, 0, 8], [2, 1, 12], [1, 2, 15]], radii=[2.2, 1.6, .8]),
    dict(name="horn", kind="cone", color="#ffeebb", start=[-2, 0, 10], end=[-3, 0, 18], r1=1.8, r2=.3),
    dict(name="badge", kind="polygon", color="#ffee33", points=[[-2, -2], [2, -2], [0, 2]], origin=[8, 0, 2], u=[1, 0, 0], v=[0, 1, 0], depth=2),
    dict(name="label", kind="text", color="#ffffff", text="CAD", center=[0, -10, 2.5], size=3.0, depth=.8),
]


class ExportAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = Path(__file__).with_name("export_cad.py")
        if cls.path.exists():
            spec = importlib.util.spec_from_file_location("export_cad", cls.path)
            cls.exporter = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.exporter)
        else:
            cls.exporter = None

    def test_all_six_primitives_have_positive_valid_watertight_geometry(self):
        self.assertIsNotNone(self.exporter, "CAD exporter has not been implemented")
        for part in SAMPLE_PARTS:
            with self.subTest(kind=part["kind"]):
                shape = self.exporter.build_part(part)
                self.assertTrue(shape.isValid())
                self.assertGreater(shape.Volume(), 0)
                mesh = self.exporter.tessellate_part(shape)
                self.assertTrue(mesh.is_watertight)
                self.assertTrue(mesh.is_winding_consistent)
                self.assertGreater(mesh.volume, 0)

    def test_export_round_trips_all_formats_and_converts_glb_axes(self):
        self.assertIsNotNone(self.exporter, "CAD exporter has not been implemented")
        import trimesh
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            character = dict(id="acceptance", name="CAD acceptance", parts=SAMPLE_PARTS)
            report = self.exporter.export_character(character, output)
            self.assertEqual(report["status"], "passed")
            self.assertEqual(report["stl"]["connected_shell_count"], 1)
            self.assertTrue(report["step_import"]["valid"])
            self.assertEqual(report["step_import"]["solid_count"], report["cad"]["solid_count"])
            self.assertEqual(len(report["components"]), len(SAMPLE_PARTS))
            self.assertTrue((output / "reports/acceptance.json").exists())
            loaded = trimesh.load(output / "color/acceptance.glb", force="scene")
            self.assertEqual(len(loaded.geometry), len(SAMPLE_PARTS))
            self.assertAlmostEqual(float(loaded.bounds[0, 1]), 0.0, places=6)
            self.assertLess(float(loaded.extents.max()), .05)
            payload = (output / "color/acceptance.glb").read_bytes()
            json_length = struct.unpack_from("<I", payload, 12)[0]
            tree = json.loads(payload[20:20 + json_length])
            base_material = next(material for material in tree["materials"] if material["name"] == "base")
            factor = base_material["pbrMetallicRoughness"]["baseColorFactor"]
            self.assertAlmostEqual(factor[0], ((0x55 / 255 + .055) / 1.055) ** 2.4, places=10)
            self.assertEqual(factor[3], 1)

    def test_disconnected_components_fail_and_are_reported(self):
        self.assertIsNotNone(self.exporter, "CAD exporter has not been implemented")
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            character = dict(id="disconnected", name="Disconnected", parts=[
                SAMPLE_PARTS[0], dict(name="floating", kind="ellipsoid", color="#ffffff", center=[0, 0, 80], radii=[1, 1, 1])])
            with self.assertRaisesRegex(ValueError, "disconnected"):
                self.exporter.export_character(character, output)
            report = json.loads((output / "reports/disconnected.json").read_text())
            self.assertEqual(report["status"], "failed")
            self.assertEqual(report["stl"]["connected_shell_count"], 2)
            self.assertEqual(len(report["stl"]["shells"]), 2)

    def test_near_coplanar_boolean_keeps_watertight_topology(self):
        self.assertIsNotNone(self.exporter, "CAD exporter has not been implemented")
        import trimesh
        first = trimesh.creation.icosphere(subdivisions=2)
        second = first.copy()
        second.apply_translation([1.0, 1e-8, 1e-8])
        union = self.exporter._manifold_union([("first", first), ("second", second)])
        self.assertTrue(union.is_watertight)
        self.assertTrue(union.is_winding_consistent)
        self.assertEqual(len(union.split(only_watertight=False)), 1)

    def test_linear_tessellation_tolerance_is_absolute_millimeters(self):
        self.assertIsNotNone(self.exporter, "CAD exporter has not been implemented")
        import cadquery as cq
        import numpy as np
        shape = cq.Solid.makeSphere(1000, angleDegrees1=-90, angleDegrees2=90)
        mesh = self.exporter.tessellate_part(shape)
        midpoints = mesh.vertices[mesh.edges_unique].mean(axis=1)
        radial_error = 1000 - np.linalg.norm(midpoints, axis=1)
        # OCCT's deflection parameter does not certify every triangle-edge
        # midpoint; this large-scale fixture distinguishes absolute meshing
        # (observed 0.208 mm) from relative meshing (over 3.5 mm).
        self.assertLess(float(radial_error.max()), .25)

    def test_stl_serialization_preserves_a_sub_float32_feature(self):
        self.assertTrue(hasattr(self.exporter, "_write_stl"), "Precision-safe STL writer has not been implemented")
        import trimesh
        tiny_tetrahedron = trimesh.Trimesh(vertices=[[100, 0, 0], [100.0000001, 0, 0], [100, 10, 0], [100, 0, 10]], faces=[[0, 2, 1], [0, 1, 3], [0, 3, 2], [1, 2, 3]], process=False)
        self.assertTrue(tiny_tetrahedron.is_watertight)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "precision.stl"
            exported, imported, info = self.exporter._write_stl(tiny_tetrahedron, path)
            self.assertTrue(imported.is_watertight)
            self.assertEqual(len(imported.vertices), 4)
            self.assertEqual(info["encoding"], "ascii_float64")

    def test_stl_writer_removes_only_faces_collapsed_by_standard_welding(self):
        import trimesh
        import numpy as np
        box = trimesh.creation.box()
        a, b = box.faces[0, :2]
        vertices = np.vstack([box.vertices, box.vertices[a] + (box.vertices[b] - box.vertices[a]) * 1e-10])
        faces = []
        for face in box.faces:
            if a in face and b in face:
                for i in range(3):
                    u, v, w = np.roll(face, -i)
                    if {u, v} == {a, b}:
                        faces.extend([[u, 8, w], [8, v, w]])
                        break
            else:
                faces.append(face)
        subdivided = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
        self.assertTrue(subdivided.is_watertight)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "near-edge.stl"
            exported, imported, info = self.exporter._write_stl(subdivided, path)
            self.assertTrue(imported.is_watertight)
            self.assertEqual(len(imported.faces), 12)
            self.assertEqual(info["collapsed_index_faces_removed"], 2)
            self.assertAlmostEqual(imported.volume, box.volume, places=12)


if __name__ == "__main__":
    unittest.main()
