"""Geometry-contract checks for the two-sided raised cutie marks."""

import importlib.util
import math
import unittest


CHARACTERS = (
    "twilight_sparkle", "applejack", "rainbow_dash", "pinkie_pie",
    "fluttershy", "rarity", "princess_celestia", "princess_luna", "clockwork_relativity",
)


class EmblemTests(unittest.TestCase):
    def load_module(self):
        self.assertIsNotNone(importlib.util.find_spec("emblems"), "emblems module must exist")
        import emblems
        return emblems

    def test_both_flanks_extrude_outward_with_closed_positive_area_profiles(self):
        """Catches inverted back-flank relief and degenerate polygon outlines."""
        module = self.load_module()
        for character in CHARACTERS:
            for side in (-1, 1):
                parts = []
                module.add_emblem(parts, character, [0, 10 * side, 30], side=side)
                self.assertGreater(len(parts), 2)
                self.assertEqual(len({p["name"] for p in parts}), len(parts))
                for part in parts:
                    self.assertEqual(part["kind"], "polygon")
                    u, v = part["u"], part["v"]
                    normal = [u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0]]
                    self.assertEqual(normal, [0, side, 0])
                    pts = part["points"]
                    area = sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(pts, pts[1:]+pts[:1])) / 2
                    self.assertGreater(area, 0.01, part["name"])
                    self.assertGreater(part["depth"], 0)
                    self.assertTrue(all(math.isfinite(c) for p in pts for c in p))

    def test_backing_overlaps_every_raised_piece_in_depth(self):
        """Catches floating motif details detached from their joining plaque."""
        module = self.load_module()
        for character in CHARACTERS:
            parts = []
            module.add_emblem(parts, character, [0, -10, 30])
            backing = parts[0]
            backing_outer = -backing["origin"][1] + backing["depth"]
            for part in parts[1:]:
                self.assertLess(-part["origin"][1], backing_outer, part["name"])
                self.assertGreater(-part["origin"][1]+part["depth"], backing_outer, part["name"])

    def test_bad_identifier_and_side_do_not_modify_parts(self):
        module = self.load_module()
        for kwargs in ({"character_id": "missing"}, {"character_id": "rarity", "side": 0}):
            parts = []
            with self.assertRaises(ValueError):
                module.add_emblem(parts, origin=[0, 0, 0], **kwargs)
            self.assertEqual(parts, [])


if __name__ == "__main__":
    unittest.main()
