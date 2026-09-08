"""Original raised flank motifs for the Equestria collection and its guest OC.

All drawings use X for forward and Z for up. They use printable polygons,
including the curved outlines, and a body-colored plaque joins every detail.
The origin is the center of the flank's nominal surface. The plaque starts
1.5 mm inward and ends 0.35 mm outward. Relief ends 0.85--1.00 mm outward.
Scale all dimensions uniformly, and place the plaque inside the rump surface.
"""

from __future__ import annotations

import math


BODY_COLORS = {
    "twilight_sparkle": "#B9A0DD",
    "applejack": "#F2B65C",
    "rainbow_dash": "#77C9ED",
    "pinkie_pie": "#F6A6CE",
    "fluttershy": "#F9EAA4",
    "rarity": "#F4F3FA",
    "princess_celestia": "#FFF7EE",
    "princess_luna": "#485EAE",
    "clockwork_relativity": "#1497A5",
}


def _ellipse(cx, cy, rx, ry, count=32, angle=0):
    ca, sa = math.cos(angle), math.sin(angle)
    return [
        (cx + rx*math.cos(t)*ca - ry*math.sin(t)*sa,
         cy + rx*math.cos(t)*sa + ry*math.sin(t)*ca)
        for t in (2*math.pi*i/count for i in range(count))
    ]


def _star(cx, cy, radius, inner, rays=6, angle=math.pi/2):
    return [
        (cx + (radius if i % 2 == 0 else inner)*math.cos(angle+i*math.pi/rays),
         cy + (radius if i % 2 == 0 else inner)*math.sin(angle+i*math.pi/rays))
        for i in range(2*rays)
    ]


def _offset(points, x, y, scale=1):
    return [(x+u*scale, y+v*scale) for u,v in points]


class _Drawing:
    def __init__(self, parts, origin, scale, side):
        self.parts, self.origin, self.scale, self.side = parts, origin, scale, side
        self.prefix = "cutie_mark_left" if side == -1 else "cutie_mark_right"

    def polygon(self, name, points, color, start=.22, end=.90):
        """Build a CCW profile whose outward normal matches the chosen flank."""
        pts = [[-self.side*u*self.scale, v*self.scale] for u,v in points]
        area = sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(pts, pts[1:]+pts[:1]))
        if area < 0:
            pts.reverse()
        self.parts.append({
            "name": f"{self.prefix}_{name}", "kind": "polygon", "color": color,
            "points": pts,
            "origin": [self.origin[0], self.origin[1]+self.side*start*self.scale, self.origin[2]],
            "u": [-self.side, 0, 0], "v": [0, 0, 1],
            "depth": (end-start)*self.scale,
        })

    def ellipse(self, name, cx, cy, rx, ry, color, angle=0, end=.90):
        self.polygon(name, _ellipse(cx, cy, rx, ry, angle=angle), color, end=end)

    def ribbon(self, name, points, width, color, end=.85):
        # Offset each vertex by the perpendicular of its central tangent.
        left, right = [], []
        for i, p in enumerate(points):
            a, b = points[max(0,i-1)], points[min(len(points)-1,i+1)]
            dx, dy = b[0]-a[0], b[1]-a[1]
            length = math.hypot(dx, dy)
            ox, oy = -dy*width/(2*length), dx*width/(2*length)
            left.append((p[0]+ox, p[1]+oy))
            right.append((p[0]-ox, p[1]-oy))
        self.polygon(name, left+right[::-1], color, end=end)


def _twilight(d):
    d.polygon("six_point_magic_star", _star(0, 0, 3.3, 1.25), "#E74BAA", end=.96)
    for i, (x,y) in enumerate(((0,4.35),(-3.6,2.35),(-3.8,-2.1),(3.6,2.35),(3.8,-2.1))):
        d.polygon(f"white_star_{i+1}", _star(x, y, .82, .32), "#FFFFFF")


def _applejack(d):
    apple = [(-.03,1.0),(-.58,1.2),(-1.04,.96),(-1.3,.43),(-1.24,-.24),
             (-.94,-.92),(-.5,-1.23),(0,-1.1),(.48,-1.24),(.96,-.92),
             (1.24,-.22),(1.28,.43),(.99,.98),(.5,1.2)]
    for i, (x,y) in enumerate(((-2,1.65),(2,1.65),(0,-2.0))):
        d.ribbon(f"apple_{i+1}_stem", [(x,y+.75),(x+.1,y+1.6)], .37, "#855234")
        d.polygon(f"apple_{i+1}_fruit", _offset(apple,x,y), "#E74743", end=.96)
        d.ellipse(f"apple_{i+1}_leaf", x+.52,y+1.47,.68,.29,"#59A85A",angle=.32,end=.97)


def _rainbow(d):
    # Three interlocking bent ribbons read as one red-yellow-blue lightning bolt.
    bolt = [(-2.9,1.65),(-1.6,-.55),(-2.55,-.55),(-.6,-4.35),
            (-.25,-1.76),(.50,-1.76),(-.8,1.65)]
    for i, (shift,color) in enumerate(((0,"#E5484E"),(1.45,"#FFE363"),(2.9,"#389ADE"))):
        d.polygon(f"lightning_{i+1}", _offset(bolt, shift-1.0,0), color)
    cloud = [(-3.9,1.35),(-4.1,1.85),(-3.99,2.55),(-3.52,2.99),(-2.85,3.0),
             (-2.55,3.68),(-1.84,4.02),(-1.02,3.97),(-.5,3.45),(.18,3.72),
             (.94,3.61),(1.42,3.08),(2.18,3.2),(2.84,2.92),(3.05,2.2),
             (2.83,1.58),(2.18,1.22),(-3.2,1.15)]
    d.polygon("storm_cloud", cloud, "#FFFFFF", end=1.0)


def _pinkie(d):
    for i, (x,y,color) in enumerate(((-2.8,1.7,"#65CDF0"),(0,2.7,"#FFDD58"),(2.8,1.7,"#65CDF0"))):
        d.ribbon(f"balloon_{i+1}_string", [(x,y-1.2),(x-.35,y-2.1),(x+.2,y-2.9),
                                            (x-.2,y-3.65),(x+.1,y-4.65)], .32,"#86A9D0")
        d.polygon(f"balloon_{i+1}_knot", [(x-.33,y-1.67),(x+.33,y-1.67),(x,y-1.16)],color)
        d.ellipse(f"balloon_{i+1}",x,y,1.05,1.50,color,end=.97)


def _fluttershy(d):
    for i,(x,y,angle) in enumerate(((-2.1,2.1,-.2),(2.2,1.4,.35),(0,-2.2,-.3))):
        ca,sa = math.cos(angle),math.sin(angle)
        def transform(points):
            return [(x+u*ca-v*sa,y+u*sa+v*ca) for u,v in points]
        wing = [(.12,.6),(.73,1.39),(1.31,1.24),(1.53,.68),(1.32,.07),
                (.94,-.18),(1.2,-.47),(1.18,-1.0),(.69,-1.14),(.18,-.63)]
        for wing_side in (-1,1):
            d.polygon(f"butterfly_{i+1}_wing_{wing_side}", transform([(u*wing_side,v) for u,v in wing]),"#F3A2C4")
        d.polygon(f"butterfly_{i+1}_body",transform(_ellipse(0,0,.26,1.0)),"#4FBBB0",end=.98)
        for antenna_side in (-1,1):
            d.polygon(f"butterfly_{i+1}_antenna_{antenna_side}",transform([
                (.03*antenna_side,.71),(.24*antenna_side,.77),
                (.48*antenna_side,1.36),(.24*antenna_side,1.43)]),"#4FBBB0",end=.97)


def _rarity(d):
    outline = [(0,1.55),(-1.29,.55),(-.94,-.63),(0,-1.8),(.94,-.63),(1.29,.55)]
    for i,(x,y) in enumerate(((-2.1,1.6),(2.1,1.6),(0,-2.05))):
        d.polygon(f"diamond_{i+1}",_offset(outline,x,y),"#59C4E5")
        facets = [([(0,1.55),(-1.29,.55),(0,.37)],"#ACF0F4"),
                  ([(0,1.55),(0,.37),(1.29,.55)],"#7DD8EF"),
                  ([(-1.29,.55),(0,.37),(0,-1.8),(-.94,-.63)],"#3B9FD2"),
                  ([(0,.37),(1.29,.55),(.94,-.63),(0,-1.8)],"#6BD4ED")]
        for j,(points,color) in enumerate(facets):
            d.polygon(f"diamond_{i+1}_facet_{j+1}",_offset(points,x,y),color,end=.96)


def _celestia(d):
    d.polygon("solar_rays",_star(0,0,5.0,3.32,rays=12),"#EDB939")
    d.ellipse("sun_orange_corona",0,0,2.96,2.96,"#F39B3F",end=.96)
    d.ellipse("sun_golden_disk",0,0,2.37,2.37,"#FFD55B",end=1.0)


def _luna(d):
    d.polygon("night_patch",_ellipse(0,0,5.15,4.95,40),"#18294F",end=.84)
    # Crescent is one simple profile bounded by two intersecting circle arcs.
    radius, inner, distance = 3.65, 3.25, 1.36
    x = (radius*radius-inner*inner+distance*distance)/(2*distance)
    z = math.sqrt(radius*radius-x*x)
    a = math.atan2(z,x)
    b = math.atan2(z,x-distance)
    outside = [(radius*math.cos(t),radius*math.sin(t))
               for t in (a+(2*math.pi-2*a)*i/36 for i in range(37))]
    inside = [(distance+inner*math.cos(t),inner*math.sin(t))
              for t in (2*math.pi-b-(2*math.pi-2*b)*i/36 for i in range(1,36))]
    d.polygon("crescent_moon",outside+inside,"#E6F1FF",end=1.0)
    d.polygon("night_star",_star(2.9,2.35,.55,.2,rays=4),"#BBD8FF",end=.97)


def _clockwork(d):
    # The supplied pixel-art reference shows a compact yellow hourglass.
    silhouette = [(-2.3,3.7),(2.3,3.7),(2.3,2.85),(.54,.36),(.54,-.36),
                  (2.3,-2.85),(2.3,-3.7),(-2.3,-3.7),(-2.3,-2.85),
                  (-.54,-.36),(-.54,.36),(-2.3,2.85)]
    d.polygon("hourglass_golden_frame",silhouette,"#E7C82D")
    for name,z in (("upper",3.25),("lower",-3.7)):
        d.polygon(f"hourglass_{name}_rail",[(-2.52,z),(2.52,z),(2.52,z+.47),(-2.52,z+.47)],"#FFE263",end=1.0)
    d.polygon("hourglass_upper_glass",[(-1.71,2.84),(1.71,2.84),(0,.39)],"#FFEE95",end=.96)
    d.polygon("hourglass_lower_sand",[(-1.7,-2.87),(1.7,-2.87),(0,-.8)],"#FFE263",end=.98)
    d.polygon("hourglass_falling_sand",[(-.19,-1.32),(.19,-1.32),(.19,.63),(-.19,.63)],"#FFE263",end=.98)


_DRAWERS = {
    "twilight_sparkle": _twilight, "applejack": _applejack,
    "rainbow_dash": _rainbow, "pinkie_pie": _pinkie,
    "fluttershy": _fluttershy, "rarity": _rarity,
    "princess_celestia": _celestia, "princess_luna": _luna,
    "clockwork_relativity": _clockwork,
}


def add_emblem(parts, character_id, origin, scale=1.0, side=-1):
    """Append a joining plaque and each named, colored raised motif component.

    ``side`` must be -1 or +1. The drawing preserves world X/Z orientation on
    both flanks, while extrusion points away from the body. Override the first
    appended component's color if a body palette differs from BODY_COLORS.
    """
    if character_id not in _DRAWERS:
        raise ValueError(f"Unknown character: {character_id}")
    if side not in (-1,1):
        raise ValueError("side must be -1 or +1")
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError("scale must be finite and positive")
    if len(origin) != 3 or not all(math.isfinite(c) for c in origin):
        raise ValueError("origin must contain three finite coordinates")
    d = _Drawing(parts,origin,scale,side)
    d.polygon("joining_plaque",_ellipse(0,0,5.65,5.65,48),BODY_COLORS[character_id],start=-1.5,end=.35)
    _DRAWERS[character_id](d)
