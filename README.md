# Equestria · Atelier Collection

**[Download the complete nine-figure collection, STEP CAD, or STL meshes](https://github.com/NoahWLono/equestria-atelier-cad/releases/tag/v1.0.0)** · **[Read the complete experiment process](PROCESS.md)**

Created with Codex and collaborating LLM agents from a human brief. The source, STEP assemblies, previews, and structured reports are browsable here. The complete release archive contains all nine STEP, STL, and colored GLB files, the Blender studio, full-resolution renders, and rebuild source.

| Download | Size |
|---|---:|
| [Complete collection](https://github.com/NoahWLono/equestria-atelier-cad/releases/download/v1.0.0/Equestria-Atelier-Complete-9-Figure-Set.zip) | 321.1 MiB |
| [STEP CAD](https://github.com/NoahWLono/equestria-atelier-cad/releases/download/v1.0.0/Equestria-Atelier-STEP-CAD.zip) | 5.2 MiB |
| [STL print meshes](https://github.com/NoahWLono/equestria-atelier-cad/releases/download/v1.0.0/Equestria-Atelier-STL-Print-Meshes.zip) | 125.7 MiB |

The exported Blender scene, GLB scenes, and large STL meshes are distributed as release assets. Download and extract the complete archive to inspect or verify the delivered collection locally. The repository can regenerate these files with `./build.sh all`.

Nine original CAD sculptures: the Mane Six, Princess Celestia, Princess Luna, and Clockwork Relativity, the user's original character and Luna's son. Each figure has its own mane and tail, raised cutie marks on both flanks, layered eyes, and a named display plinth. The royal sisters have larger proportions, spread wings, and regalia.

![The nine-character collection](outputs/renders/collection_catalog.png)

| Character | Modeled form | File identifier |
|---|---|---|
| Twilight Sparkle | Alicorn | `twilight_sparkle` |
| Applejack | Earth pony | `applejack` |
| Rainbow Dash | Pegasus | `rainbow_dash` |
| Pinkie Pie | Earth pony | `pinkie_pie` |
| Fluttershy | Pegasus | `fluttershy` |
| Rarity | Unicorn | `rarity` |
| Princess Celestia | Alicorn | `princess_celestia` |
| Princess Luna | Alicorn | `princess_luna` |
| Clockwork Relativity | Unicorn | `clockwork_relativity` |

Clockwork uses the reference's teal coat (`#1497A5`), deep purple hair (`#342064`), green eyes, purple hoof accents, and a yellow-gold hourglass mark. His unicorn form and hourglass mark were confirmed by the user.

## Open the files

| File or directory | Purpose |
|---|---|
| [`outputs/step/`](outputs/step/) | Editable solid geometry, with named and colored design components |
| [`outputs/stl/`](outputs/stl/) | One boolean-unioned ASCII STL mesh per character for a slicer |
| [`outputs/color/`](outputs/color/) | Colored GLB scenes with separate named components |
| [Blender scene in the complete archive](https://github.com/NoahWLono/equestria-atelier-cad/releases/tag/v1.0.0) | Full cast in an editable Blender studio scene |
| [`outputs/renders/`](outputs/renders/) | Individual portraits, orthographic studies, the cast render, the 3 × 3 catalog, and Luna with her son |
| [`outputs/collection.json`](outputs/collection.json) | Editable geometry and color parameters for every component |
| [`outputs/reports/`](outputs/reports/) | Geometry checks, dimensions, triangle counts, and rendering evidence |

Use **STL** for the joined print mesh, **STEP** to work with the component solids, and **GLB** or the **Blender scene** to inspect the colors. STEP retains intentionally overlapping components. It is a sculpting assembly, with no mechanical joints or assembly clearances. Its summed component volume includes overlaps. STL is the union that removes those internal overlaps.

CAD and STL coordinates are in **millimeters**, with Z up. The STL files use ASCII text with decimal coordinates that preserve the union's float64 values. The union retains its topology without subsequent mesh simplification. STL does not encode a unit declaration, so select millimeters when importing it into a slicer. GLB uses **meters**, with Y up. The renderer handles this conversion when importing GLB into Blender.

Exact dimensions are recorded in each character's report under `stl.extents_mm`: X length, Y width, and Z height, including the plinth. See [printing and editing](docs/printing-and-editing.md) before scaling or preparing a print.

## Rebuild from source

The build runs locally. Opening the exported files requires no Python installation. Regeneration uses Python 3.11 and the pinned dependencies in [`requirements.txt`](requirements.txt).

From the package directory, with `uv` installed:

```bash
./build.sh install
./build.sh all
```

`install` downloads dependencies into `.venv311`, using local `.python` and `.cache` directories as needed. No installation happens when the launcher is opened without a command. `all` regenerates the nine models, renders them, and runs collection verification.

| Launcher command | Action |
|---|---|
| `./build.sh models` | Rebuild all nine STEP, STL, and GLB models |
| `./build.sh models rarity` | Rebuild one model |
| `./build.sh render` | Render every portrait, orthographic views, the cast, and Luna with Clockwork; compose the catalog |
| `./build.sh render rarity` | Render one full-resolution portrait |
| `./build.sh verify` | Check the delivered geometry and checksums |
| `./build.sh test` | Run the CAD primitive and emblem acceptance tests |

The source sequence is `source/design.py`, `source/export_cad.py`, `source/render_studio.py`, then `source/make_catalog.py`. The first script regenerates the collection JSON. The exporter builds OpenCascade solids, writes STEP and GLB, then unions the tessellated solids for STL. The renderer reads those GLB files to produce the images and Blender scene. The catalog script composes the rendered images into presentation plates.

To rebuild and preview one character after changing its design:

```bash
./build.sh models clockwork_relativity
.venv311/bin/python source/render_studio.py --only clockwork_relativity --quick
```

`--quick` renders a smaller image with fewer samples for inspection. Omit it for the full-resolution portrait. `--orthographic` adds front, side, and back views. `--all` also builds the cast scene and saves `outputs/collection.blend`; `--hero` rebuilds just that scene. `--pair` renders Luna with Clockwork. CPU rendering can take substantial time.

The local build environment uses these versions:

| Dependency | Version |
|---|---|
| Python | 3.11.16 |
| CadQuery | 2.8.0 |
| cadquery-ocp | 7.9.3.1.1 |
| trimesh | 5.1.0 |
| manifold3d | 3.5.3 |
| NumPy | 2.4.6 |
| SciPy | 1.17.1 |
| NetworkX | 3.6.1 |
| Blender Python module (`bpy`) | 4.4.0 |
| Pillow | 12.3.0 |

The build and programmatic imports were exercised on Linux. The exported formats can be opened by applications that support STEP, STL, GLB, or Blender files. Native CAD application behavior and rebuilding on macOS or Windows have not been tested. Font substitution and renderer versions can change labels or images.

## Verification and provenance

The exporter checks positive-volume, valid solids; closed component meshes; STEP import-back validity; and GLB component names. The STL gate requires a watertight mesh with consistent winding, positive volume, and exactly one connected shell, then checks the saved ASCII STL by importing it again. A failed check leaves a report with `status: "failed"` and stops that character's successful export. The per-character report is the evidence for a particular build. An optional `stl_repair` entry records regeneration from existing matching-design GLB meshes or a fresh tessellation of the original STEP solids, with source hashes and geometry checks recorded in the report.

Run the geometry acceptance tests with:

```bash
./build.sh test
```

Geometry verification does not establish print settings, material strength, or successful fabrication. These are decorative display figures; no physical test print is claimed.

All sculpture geometry was authored in Python for this collection. It uses analytic solids, lofted paths, and original polygon drawings, with no downloaded meshes or extracted game assets. The eight established characters are fan-art interpretations of *My Little Pony: Friendship Is Magic*. Clockwork Relativity is the user's original character, modeled from the supplied sprite. Studio images are rendered from the exported CAD geometry. The cutie-mark contact sheet is generated from the same relief profiles.

The bundled CAD label font is [`NotoSans-Bold.ttf`](assets/fonts/NotoSans-Bold.ttf), copyright 2022 The Noto Project Authors. Its matching [SIL Open Font License 1.1](assets/fonts/OFL.txt) is included. The font's embedded attribution and license were checked against the [upstream font project](https://github.com/notofonts/latin-greek-cyrillic/blob/main/OFL.txt).

Start editing in [`source/design.py`](source/design.py), use [`source/emblems.py`](source/emblems.py) for the flank symbols, and consult the [geometry contract](docs/geometry-contract.md) for supported primitives.
