# Printing and editing the collection

Each character includes a display plinth and connected sculptural features. The STL export is intended for slicing as one joined object. The STEP and GLB exports preserve separate named design components for editing and color presentation.

## Prepare a print

1. Open `outputs/stl/<character_id>.stl` in your slicer and interpret its coordinates as millimeters.
2. Check its height against `stl.extents_mm[2]` in `outputs/reports/<character_id>.json`. That measurement includes the plinth. A 1,000-fold size difference indicates a meter/millimeter import mismatch.
3. Inspect the layer preview at the chosen scale, especially the eyelashes, horn spiral, feather tips, cutie marks, and lettering. Fine relief ribbons are approximately 0.3 mm wide before the character's overall scale is applied.
4. Choose orientation and supports for your process. The flat plinth offers a starting orientation, but the muzzle, mane, tail, wings, and regalia include overhangs. Support-free printing has not been established.
5. Review the slices for isolated starts and missing thin details before producing the full figure.

Layer height, nozzle size, resin exposure, wall count, and support placement depend on your printer and material. No printer-specific settings or physical test prints are supplied. Enlarging a figure can preserve small features; reducing its size can erase lettering or weaken fine details.

The models contain solid geometry. They have no designed hollow interior, drainage holes, removable supports, or keyed assembly joints. Any hollowing, splitting, or fitting tolerances should be added in the application you use for manufacturing preparation.

The STL contains geometry only. Color is available in STEP components, GLB materials, and the Blender scene. For a painted print, use the portrait and cutie-mark sheet as color references. For a printer with multiple materials, prepare color regions in your slicer or CAD software and inspect the resulting toolpaths. Overlapping STEP components are not pre-separated material volumes.

## Understand the formats

| Format | Coordinates | Structure |
|---|---|---|
| Python and JSON | Millimeters; X toward the nose, Y across the flanks, Z up | Parameterized primitives and color values |
| STEP | Millimeters; Z up | Named component solids with intentional overlaps |
| STL | Millimeter-valued coordinates; Z up | Unsimplified boolean union, written as ASCII text with float64 coordinate precision |
| GLB | Meters; Y up | Named meshes and materials for color viewing |
| Blender scene | Meters internally; millimeter display units | Imported GLB geometry, studio lights, cameras, and presentation objects |

The STEP export preserves the authored solids. Its component boundaries and overlaps help with selecting and changing details. It does not contain a native feature-history tree for a particular CAD application. The Python source and JSON are the editable construction definition.

The exporter tessellates OpenCascade solids with an absolute linear deflection setting of **0.10 mm** and an angular setting of **0.12 radians**. STL and GLB derive from these tessellations. The STL preserves the raw manifold3d union without subsequent mesh simplification. It is written as ASCII text using decimal representations that retain each union coordinate's float64 value. The saved STL is imported again and must retain watertightness, consistent winding, and exactly one connected shell. The tessellation settings and coordinate precision do not establish manufacturing tolerances or printer accuracy.

When a character report contains `stl_repair`, that STL was regenerated from existing GLB component meshes or a fresh tessellation of the original STEP solids for the same design. The GLB path converts float32 positions back into millimeters and compares each component's bounds against the original tessellation report within **0.001 mm**. The STEP path validates the imported solid count and bounds, then tessellates the solids in float64 at the documented absolute tolerances. The report identifies the source and records the relevant file hashes. Both paths retain the raw union and require the saved ASCII STL to pass import-back checks. ASCII serialization preserves the resulting union coordinates; it does not restore precision that was already absent from a GLB source.

Component volumes in the STEP report count overlaps more than once. Use `stl.volume_mm3` for the joined mesh volume. Even that volume does not include supports or account for a slicer's hollowing and infill choices.

The STL writer checks how a standard loader welds repeated vertices. If that welding collapses a triangle to repeated vertex indices, the writer can remove that collapsed face after confirming unchanged bounds and volume. Clockwork's delivered STL uses this normalization for two faces; the operation is recorded in its report.


## Change a character

Edit the relevant entry in `CAST` in `source/design.py`. The entries control each character's colors and species features:

| Field | Effect |
|---|---|
| `body`, `mane`, `stripe`, `iris` | Hex RGB colors |
| `wings`, `horn` | Adds the corresponding anatomy |
| `hat` | Enables Applejack's hat and freckles |
| `royal` | Enables royal wings, regalia, and associated proportions |
| `leg_extra`, `neck_extra` | Changes the body proportions in millimeters |
| `scale` | Uniformly scales the entire figure, including the plinth and lettering |
| `oc` | Enables Clockwork's mane, hoof accents, and other reference-specific details |

Twilight Sparkle is modeled as an alicorn. Rainbow Dash and Fluttershy are pegasi; Rarity is a unicorn; Applejack and Pinkie Pie are earth ponies. Celestia and Luna are alicorns. Clockwork is a unicorn with a gold hourglass mark, as confirmed by the user.

Most geometry is authored in `build()`, with separate functions for eyes, wings, manes, tails, horns, and regalia. Keep adjacent features overlapping when moving or reshaping them. The exporter rejects detached pieces in the final STL and records their bounds and nearby component names in the report.

For cutie marks, edit `source/emblems.py`. `add_emblem(parts, character_id, origin, scale, side)` adds a body-colored joining plaque followed by named relief components. `side=-1` and `side=1` make the relief point outward on the two flanks. At unit scale, the plaque is 11.3 mm across and extends from 1.5 mm inside the nominal flank surface to 0.35 mm outside it. Relief overlaps the plaque and reaches at most 1.0 mm outside the surface. The figure builder applies the character's body color to the plaque.

The detailed primitive fields are listed in [geometry-contract.md](geometry-contract.md). New profiles must be closed and free of self-intersections. Tubes need positive radii and a usable path. A visually close feature can still be detached in 3D, so export and check the union after moving small details.

## Rebuild after an edit

From the package root, after `./build.sh install` has created the local environment:

```bash
./build.sh models rarity
.venv311/bin/python source/render_studio.py --only rarity --quick
```

Inspect the new report and preview, then render the full portrait without `--quick`. To refresh every image and the Blender scene:

```bash
./build.sh render
```

Run `./build.sh models` before this command if you changed more than the one selected character. The renderer reads the files under `outputs/color/`; it does not rebuild CAD geometry. `--resume`, when passed directly to `source/render_studio.py`, can skip individual portraits whose GLB hashes, output hashes, and requested resolution still match. For changes to lighting, camera logic, or rendering code, rebuild without `--resume`.

The renderer creates the cast scene from scratch. If you customize `outputs/collection.blend` by hand, save your version under a separate filename before running `--all` or `--hero` again.

The launcher uses the bundled `assets/fonts/NotoSans-Bold.ttf` for the raised labels. When running `source/export_cad.py` directly, you can choose another TrueType or OpenType file through `CAD_FONT_PATH`. A new font changes the label geometry and can affect its spacing or connection to the plinth, so re-export and check the result after substitution. Keep the bundled font's `OFL.txt` with it when moving the package.

## Edit JSON directly

`outputs/collection.json` includes all component parameters, names, and colors. Running `source/design.py` overwrites it. For independent JSON edits, make a separate copy and export to a separate directory:

```bash
cp outputs/collection.json my-collection.json
.venv311/bin/python source/export_cad.py --input my-collection.json --output outputs-custom --only clockwork_relativity
```

Edit `my-collection.json` before running the second command. The standard rendering script reads the default `outputs/` paths; it does not automatically render this custom output directory.

## Read the verification evidence

Run `./build.sh verify` to check the delivered collection, and `./build.sh test` to run the exporter and emblem acceptance tests after source changes.

In `outputs/reports/<character_id>.json`, look for `status: "passed"`. The report includes:

- `components`: names, solid validity, bounds, volumes, and component mesh checks.
- `cad`: the overlapping assembly's solid count and bounds.
- `step_import`: checks from importing the written STEP file back into OpenCascade.
- `glb`: imported component count, name preservation, units, and bounds.
- `stl`: the union's watertightness, winding, volume, dimensions, and connected shell count.
- `stl_import`: checks from importing the written STL again.
- `stl_repair`, when present: the GLB or STEP regeneration source, source hashes, and geometry comparison evidence.

A successful STL build requires one connected shell. This establishes mesh connectivity. Material strength and the durability of narrow connections during support removal need separate assessment. The reports describe the generated files; they do not certify a physical print.

`outputs/reports/renders/` records renderer versions, image hashes, resolution, and source asset hashes for individual renders. The color catalog is composed from those images. If geometry or colors change, regenerate the GLB and the affected renders to keep the images consistent with the CAD files.
