#!/usr/bin/env python3
"""Compose the actual Blender renders into a labeled, print-resolution collection plate."""
from __future__ import annotations

import json
import hashlib
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
RENDERS = OUT / "renders"
NAVY = (15, 25, 42)
INK = (236, 235, 227)
GOLD = (199, 168, 111)
MUTED = (148, 164, 186)


def font(size, serif=False):
    paths = [
        Path("/usr/share/fonts/noto/NotoSerifDisplay-Regular.ttf") if serif else Path("/usr/share/fonts/Adwaita/AdwaitaSans-Regular.ttf"),
        Path("/usr/share/fonts/noto/NotoSerif-Regular.ttf") if serif else Path("/usr/share/fonts/noto/NotoSans-Regular.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf") if serif else Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for path in paths:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default(size=size)


def text_center(draw, x, y, text, face, color=INK):
    draw.text((x, y), text, font=face, fill=color, anchor="mt")


def tracked(draw, center, y, text, face, spacing, fill):
    widths = [draw.textlength(c, font=face) for c in text]
    cursor = center - (sum(widths) + spacing*(len(text)-1))/2
    for char, width in zip(text, widths):
        draw.text((cursor, y), char, font=face, fill=fill)
        cursor += width + spacing


def paste_figure(canvas, path, box, crop=True):
    figure = Image.open(path).convert("RGBA")
    if crop:
        opaque = figure.getchannel("A").point(lambda value: 255 if value > 230 else 0)
        extent = opaque.getbbox()
        if extent:
            padding = round((extent[3]-extent[1])*.065)
            extent = (max(0, extent[0]-padding), max(0, extent[1]-padding), min(figure.width, extent[2]+padding), min(figure.height, extent[3]+padding*2))
            figure = figure.crop(extent)
    scale = min((box[2]-box[0])/figure.width, (box[3]-box[1])/figure.height)
    figure = figure.resize((round(figure.width*scale), round(figure.height*scale)), Image.Resampling.LANCZOS)
    x = box[0] + (box[2]-box[0]-figure.width)//2
    y = box[3] - figure.height
    canvas.alpha_composite(figure, (x, y))


def technical_height(character):
    report = OUT / "reports" / f"{character['id']}.json"
    if report.exists():
        data = json.loads(report.read_text())
        for key in ("extents_mm", "extents"):
            extents = data.get(key)
            if isinstance(extents, list) and len(extents) == 3:
                return f"{extents[2]:.0f} MM"
        mesh = data.get("stl", data.get("mesh", {}))
        if isinstance(mesh, dict):
            extents = mesh.get("extents_mm") or mesh.get("extents")
            if isinstance(extents, list) and len(extents) == 3:
                return f"{extents[2]:.0f} MM"
    return "SCULPTED CAD EDITION"


def trim_vertical_studio_space(image):
    opaque = image.getchannel("A").point(lambda value: 255 if value > 230 else 0)
    extent = opaque.getbbox()
    if extent:
        pad = round((extent[3]-extent[1])*.07)
        return image.crop((0, max(0, extent[1]-pad), image.width, min(image.height, extent[3]+pad*2)))
    return image


def catalog(characters):
    columns = 3 if len(characters) > 8 else 4
    rows = math.ceil(len(characters)/columns)
    width = 3000 if columns == 3 else 3600
    margin, header, footer = 130, 450, 170
    cell_width = (width-2*margin)//columns
    cell_height = 1000 if columns == 3 else 1040
    height = header + rows*cell_height + footer
    canvas = Image.new("RGBA", (width, height), NAVY+(255,))
    draw = ImageDraw.Draw(canvas)
    tracked(draw, width/2, 88, "THE ATELIER COLLECTION", font(27), 8, GOLD)
    tracked(draw, width/2, 142, "EQUESTRIA", font(116, serif=True), 13, INK)
    text_center(draw, width/2, 302, f"{len(characters):02d} CHARACTERS  /  ORIGINAL SOLID MODELING  /  FULL COLOR EDITIONS", font(28), MUTED)
    draw.line((margin, 385, width-margin, 385), fill=(63, 74, 91), width=2)
    for index, character in enumerate(characters):
        col, row = index % columns, index // columns
        x, y = margin+col*cell_width, header+row*cell_height
        if col:
            draw.line((x, y+55, x, y+cell_height-65), fill=(36, 48, 66), width=1)
        center = x+cell_width/2
        tracked(draw, center, y+8, f"Nº {index+1:02d}", font(21), 4, GOLD)
        path = RENDERS / f"{character['id']}.png"
        if not path.exists():
            raise FileNotFoundError(f"Missing studio render: {path}")
        paste_figure(canvas, path, (x+10, y+58, x+cell_width-10, y+cell_height-170))
        draw = ImageDraw.Draw(canvas)
        name = character["name"].replace("Princess ", "")
        size = 46 if len(name) < 22 else 40
        text_center(draw, center, y+cell_height-155, name, font(size, serif=True))
        tagline = character.get("tagline", "").upper()
        if character["id"] == "clockwork_relativity":
            tagline = "LUNA'S SON"
        if len(tagline) > 44:
            tagline = tagline[:43].rsplit(" ", 1)[0]
        text_center(draw, center, y+cell_height-98, tagline, font(26), GOLD)
        text_center(draw, center, y+cell_height-60, technical_height(character), font(24), MUTED)
    line_y = height-footer+20
    draw.line((margin, line_y, width-margin, line_y), fill=(63, 74, 91), width=2)
    draw.text((margin, line_y+45), "STEP  /  STL  /  GLB", font=font(23), fill=GOLD)
    draw.text((width-margin, line_y+45), "RENDERED DIRECTLY FROM THE CAD EXPORTS", font=font(21), fill=MUTED, anchor="rt")
    result = RENDERS / "collection_catalog.png"
    canvas.convert("RGB").save(result, dpi=(300, 300))
    thumb = canvas.convert("RGB")
    thumb.thumbnail((1800, 2400), Image.Resampling.LANCZOS)
    thumb.save(RENDERS / "collection_catalog.jpg", quality=93, subsampling=0)
    print(result)


def hero_plate():
    raw_path = RENDERS / "full_cast.png"
    if not raw_path.exists():
        return
    image = trim_vertical_studio_space(Image.open(raw_path).convert("RGBA"))
    width = image.width
    header = int(width*0.16)
    footer = int(width*0.08)
    canvas = Image.new("RGBA", (width, image.height+header+footer), NAVY+(255,))
    canvas.alpha_composite(image, (0, header))
    draw = ImageDraw.Draw(canvas)
    tracked(draw, width/2, int(width*.023), "THE ATELIER COLLECTION", font(int(width*.010)), int(width*.0022), GOLD)
    tracked(draw, width/2, int(width*.046), "EQUESTRIA", font(int(width*.044), serif=True), int(width*.004), INK)
    text_center(draw, width/2, int(width*.112), "THE MANE SIX, CELESTIA, LUNA & CLOCKWORK RELATIVITY", font(int(width*.0085)), MUTED)
    text_center(draw, width/2, header+image.height+int(width*.014), "A COLLECTION OF ORIGINAL CAD SCULPTURES  •  RENDERED FROM THE EXPORTED SOLIDS", font(int(width*.007)), GOLD)
    canvas.convert("RGB").save(RENDERS / "collection_hero.png", dpi=(300, 300))


def pair_plate():
    raw_path = RENDERS / "luna_and_clockwork.png"
    if not raw_path.exists():
        return
    image = trim_vertical_studio_space(Image.open(raw_path).convert("RGBA"))
    width = image.width
    header, footer = int(width*.16), int(width*.09)
    canvas = Image.new("RGBA", (width, image.height+header+footer), NAVY+(255,))
    canvas.alpha_composite(image, (0, header))
    draw = ImageDraw.Draw(canvas)
    tracked(draw, width/2, int(width*.024), "THE ATELIER COLLECTION", font(int(width*.010)), int(width*.002), GOLD)
    text_center(draw, width/2, int(width*.063), "Luna & Clockwork Relativity", font(int(width*.034), serif=True), INK)
    tracked(draw, width/2, int(width*.116), "MOTHER & SON", font(int(width*.011)), int(width*.003), MUTED)
    text_center(draw, width/2, header+image.height+int(width*.018), "ORIGINAL CAD SCULPTURES  /  FULL COLOR EDITIONS", font(int(width*.009)), GOLD)
    canvas.convert("RGB").save(RENDERS / "luna_and_clockwork_plate.png", dpi=(300, 300))


def orthographic_plates(characters):
    for character in characters:
        paths = [RENDERS/"orthographic"/f"{character['id']}_{view}.png" for view in ("front", "side", "back")]
        if not all(path.exists() for path in paths):
            continue
        width, height = 3000, 1700
        canvas = Image.new("RGBA", (width, height), (241, 240, 235, 255))
        draw = ImageDraw.Draw(canvas)
        draw.text((100, 65), character["name"], font=font(60, serif=True), fill=NAVY)
        draw.text((2900, 95), "ORTHOGRAPHIC STUDY", font=font(26), fill=(92, 100, 111), anchor="rt")
        draw.line((100, 180, 2900, 180), fill=(190, 191, 185), width=2)
        for index, (path, label) in enumerate(zip(paths, ("FRONT · +X", "LEFT FLANK · −Y", "BACK · −X"))):
            paste_figure(canvas, path, (index*1000+40, 220, (index+1)*1000-40, 1500), crop=False)
            draw = ImageDraw.Draw(canvas)
            text_center(draw, index*1000+500, 1560, label, font(27), NAVY)
        canvas.convert("RGB").save(RENDERS / "orthographic" / f"{character['id']}_sheet.png", dpi=(300, 300))


def main():
    data = json.loads((OUT/"collection.json").read_text())
    catalog(data["characters"])
    hero_plate()
    pair_plate()
    orthographic_plates(data["characters"])
    def record(path):
        return {"file": str(path.relative_to(OUT)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    inputs = [RENDERS/f"{c['id']}.png" for c in data["characters"]]
    inputs += [RENDERS/name for name in ("full_cast.png", "luna_and_clockwork.png") if (RENDERS/name).exists()]
    inputs += [RENDERS/"orthographic"/f"{c['id']}_{view}.png" for c in data["characters"] for view in ("front", "side", "back") if (RENDERS/"orthographic"/f"{c['id']}_{view}.png").exists()]
    outputs = [RENDERS/name for name in ("collection_catalog.png", "collection_catalog.jpg", "collection_hero.png", "luna_and_clockwork_plate.png") if (RENDERS/name).exists()]
    outputs += [RENDERS/"orthographic"/f"{c['id']}_sheet.png" for c in data["characters"] if (RENDERS/"orthographic"/f"{c['id']}_sheet.png").exists()]
    report = {
        "collection": record(OUT/"collection.json"),
        "sources": [record(path) for path in inputs],
        "outputs": [record(path) for path in outputs],
    }
    report_path = OUT/"reports"/"catalog.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2)+"\n")


if __name__ == "__main__":
    main()
