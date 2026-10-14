"""The object library: rope-rigging equipment drawn as vector graphics.

Each object is a function ``build(palette) -> Drawing`` registered with
:func:`register`. Sizes are in millimetres and roughly match real gear, so
objects keep a consistent scale relative to each other when imported into
vRigger. To add a new object, write a builder and decorate it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from .geometry import (Drawing, Path, Point, Style, circle, rounded_polygon,
                       two_circle_outline)

OUTLINE_W = 0.9   # outline thickness (mm)


# ---------------------------------------------------------------------------
# Palettes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Palette:
    name: str
    outline: str
    metal: str          # bare aluminium / steel
    metal_dark: str     # sheaves, axles, gates
    accent: dict[str, str]

    def color(self, key: str) -> str:
        return self.accent.get(key, self.metal)


PALETTES = {
    "color": Palette(
        name="color", outline="#1f2328", metal="#c3c9d0", metal_dark="#7d858f",
        accent={"pulley": "#d6402b", "pulley_pm": "#f0a21c", "pulley_double": "#2f6fd1",
                "carabiner_d": "#2f6fd1", "carabiner_hms": "#e0a21b", "sleeve": "#3a3f46",
                "plate": "#e8742a", "eight": "#3aa0a0", "maillon": "#9aa2ab"},
    ),
    "mono": Palette(
        name="mono", outline="#000000", metal="#ffffff", metal_dark="#bdbdbd",
        accent={"sleeve": "#7a7a7a"},
    ),
}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LibraryObject:
    id: str
    name: str
    category: str
    description: str
    builder: Callable[[Palette], Drawing]

    def draw(self, palette: str | Palette = "color") -> Drawing:
        pal = PALETTES[palette] if isinstance(palette, str) else palette
        return self.builder(pal)


_REGISTRY: dict[str, LibraryObject] = {}
CATEGORIES = ("Pulleys", "Carabiners", "Hardware")


def register(id: str, name: str, category: str, description: str):
    if category not in CATEGORIES:
        raise ValueError(f"unknown category {category!r}")

    def deco(fn: Callable[[Palette], Drawing]):
        if id in _REGISTRY:
            raise ValueError(f"duplicate object id {id!r}")
        _REGISTRY[id] = LibraryObject(id, name, category, description, fn)
        return fn
    return deco


def all_objects() -> list[LibraryObject]:
    return list(_REGISTRY.values())


def get(id: str) -> LibraryObject:
    try:
        return _REGISTRY[id]
    except KeyError:
        raise KeyError(f"no object {id!r}; available: {', '.join(_REGISTRY)}") from None


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------

def _solid(pal: Palette, fill: str, evenodd: bool = False) -> Style:
    return Style(fill=fill, stroke=pal.outline, width=OUTLINE_W, evenodd=evenodd)


def _rod(d: Drawing, pal: Palette, path: Path, thickness: float, color: str,
         cap: str = "round") -> None:
    """A round bar (carabiner body, gate…) drawn as an outlined thick stroke."""
    d.add(path, Style(stroke=pal.outline, width=thickness + 2 * OUTLINE_W, cap=cap))
    d.add(path, Style(stroke=color, width=thickness, cap=cap))


def circle_hull(circles: list[tuple[Point, float]]) -> Path:
    """Convex outline around circles listed clockwise (on screen).

    Every circle must touch the hull. Used for pulley side plates and other
    rounded plates.
    """
    n = len(circles)
    alphas = []                       # outward normal angle of tangent i -> i+1
    for i in range(n):
        (c1, r1), (c2, r2) = circles[i], circles[(i + 1) % n]
        dx, dy = c2[0] - c1[0], c2[1] - c1[1]
        L = math.hypot(dx, dy)
        beta = math.degrees(math.atan2(dy, dx))
        alphas.append(beta - math.degrees(math.acos((r1 - r2) / L)))
    p = Path()
    for i in range(n):
        (c, r) = circles[(i + 1) % n]
        a_in, a_out = alphas[i], alphas[(i + 1) % n]
        while a_out < a_in:
            a_out += 360.0
        while a_out - a_in >= 360.0:
            a_out -= 360.0
        p.arc(c[0], c[1], r, a_in, a_out, connect=i > 0)
    return p.close()


def _with_holes(outline: Path, holes: list[tuple[Point, float]]) -> Path:
    p = Path().extend(outline)
    for c, r in holes:
        p.extend(circle(c[0], c[1], r))
    return p


def _lerp(a: Point, b: Point, t: float) -> Point:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def _bar(a: Point, b: Point, width: float, radius: float) -> Path:
    """Rounded rectangle whose centre line runs from a to b."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy)
    nx, ny = -dy / L * width / 2, dx / L * width / 2
    pts = [(a[0] + nx, a[1] + ny), (b[0] + nx, b[1] + ny),
           (b[0] - nx, b[1] - ny), (a[0] - nx, a[1] - ny)]
    return rounded_polygon(pts, radius)


def _carabiner(d: Drawing, pal: Palette, corners: list[Point], radii: list[float],
               color: str, nose: float, hinge: float, thickness: float = 10.0,
               lock: bool = False) -> None:
    """Carabiner from a closed centre-line polygon.

    The gate lies on the edge from the last corner back to the first one;
    ``nose`` and ``hinge`` are fractions along that edge measured from the
    first and last corner respectively.
    """
    first, last = corners[0], corners[-1]
    nose_pt = _lerp(first, last, nose)
    hinge_pt = _lerp(last, first, hinge)
    body = rounded_polygon([nose_pt] + corners + [hinge_pt],
                           [0.0] + radii + [0.0], closed=False)
    _rod(d, pal, body, thickness, color)
    # Gate: slightly thinner bar from the hinge to just short of the nose.
    gate_end = _lerp(nose_pt, hinge_pt, 0.06)
    gate = Path().move(*hinge_pt).line(*gate_end)
    _rod(d, pal, gate, thickness * 0.7, pal.metal_dark)
    if lock:
        a = _lerp(gate_end, hinge_pt, 0.04)
        b = _lerp(gate_end, hinge_pt, 0.42)
        w = thickness * 1.25
        d.add(_bar(a, b, w, 2.2), _solid(pal, pal.color("sleeve")))
        # Knurl lines across the sleeve.
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy)
        nx, ny = -dy / L * (w / 2 - 1.4), dx / L * (w / 2 - 1.4)
        for k in range(1, 6):
            m = _lerp(a, b, k / 6)
            line = Path().move(m[0] + nx, m[1] + ny).line(m[0] - nx, m[1] - ny)
            d.add(line, Style(stroke=pal.outline, width=0.5, cap="butt"))


def _axle(d: Drawing, pal: Palette, c: Point, r: float = 6.0) -> None:
    d.add(circle(c[0], c[1], r), _solid(pal, pal.metal))
    d.add(circle(c[0], c[1], r * 0.42), _solid(pal, pal.metal_dark))


# ---------------------------------------------------------------------------
# Pulleys
# ---------------------------------------------------------------------------

@register("pulley_single", "Single pulley", "Pulleys",
          "Single-sheave rescue pulley with swing side plates, side view.")
def _pulley_single(pal: Palette) -> Drawing:
    d = Drawing(70, 104)
    sheave, top = (35.0, 68.0), (35.0, 20.0)
    d.add(circle(*sheave, 30.0), _solid(pal, pal.metal_dark))
    d.add(circle(*sheave, 25.0), Style(stroke=pal.outline, width=0.5))
    plate = circle_hull([(top, 13.0), (sheave, 27.0)])
    d.add(_with_holes(plate, [(top, 7.0)]), _solid(pal, pal.color("pulley"), evenodd=True))
    _axle(d, pal, sheave)
    return d


@register("pulley_prusik", "Prusik-minding pulley", "Pulleys",
          "Pulley with wide square shoulders that stop a Prusik hitch, side view.")
def _pulley_prusik(pal: Palette) -> Drawing:
    d = Drawing(74, 106)
    sheave = (37.0, 70.0)
    d.add(circle(*sheave, 30.0), _solid(pal, pal.metal_dark))
    plate = circle_hull([((10.0, 18.0), 5.0), ((64.0, 18.0), 5.0), (sheave, 28.0)])
    d.add(_with_holes(plate, [((37.0, 28.0), 7.5)]),
          _solid(pal, pal.color("pulley_pm"), evenodd=True))
    _axle(d, pal, sheave)
    return d


@register("pulley_double", "Double pulley (tandem)", "Pulleys",
          "Two sheaves in line in one frame, e.g. for tyroleans and 3:1 systems.")
def _pulley_double(pal: Palette) -> Drawing:
    d = Drawing(106, 86)
    s1, s2, top = (28.0, 56.0), (78.0, 56.0), (53.0, 18.0)
    for s in (s1, s2):
        d.add(circle(*s, 24.0), _solid(pal, pal.metal_dark))
    plate = circle_hull([(top, 13.0), (s2, 21.0), (s1, 21.0)])
    d.add(_with_holes(plate, [(top, 7.0)]), _solid(pal, pal.color("pulley_double"), evenodd=True))
    for s in (s1, s2):
        _axle(d, pal, s, 5.5)
    return d


# ---------------------------------------------------------------------------
# Carabiners
# ---------------------------------------------------------------------------

@register("carabiner_oval", "Oval carabiner", "Carabiners",
          "Symmetric oval carabiner with a straight non-locking gate.")
def _carabiner_oval(pal: Palette) -> Drawing:
    d = Drawing(64, 120)
    corners = [(54.0, 10.0), (10.0, 10.0), (10.0, 110.0), (54.0, 110.0)]
    _carabiner(d, pal, corners, [22.0] * 4, pal.metal, nose=0.30, hinge=0.27)
    return d


@register("carabiner_d", "D carabiner (screwgate)", "Carabiners",
          "Asymmetric D-shaped carabiner with a screw-locking sleeve.")
def _carabiner_d(pal: Palette) -> Drawing:
    d = Drawing(70, 120)
    corners = [(58.0, 10.0), (11.0, 10.0), (11.0, 110.0), (46.0, 110.0)]
    _carabiner(d, pal, corners, [22.0, 14.0, 12.0, 14.0], pal.color("carabiner_d"),
               nose=0.30, hinge=0.20, lock=True)
    return d


@register("carabiner_hms", "HMS carabiner (pear)", "Carabiners",
          "Pear-shaped locking carabiner for Munter hitches and belaying.")
def _carabiner_hms(pal: Palette) -> Drawing:
    d = Drawing(80, 122)
    corners = [(70.0, 10.0), (10.0, 10.0), (26.0, 112.0), (48.0, 112.0)]
    _carabiner(d, pal, corners, [28.0, 28.0, 11.0, 11.0], pal.color("carabiner_hms"),
               nose=0.32, hinge=0.20, lock=True)
    return d


# ---------------------------------------------------------------------------
# Hardware
# ---------------------------------------------------------------------------

@register("rigging_plate", "Rigging plate", "Hardware",
          "Anchor/rigging plate with one master hole and three distribution holes.")
def _rigging_plate(pal: Palette) -> Drawing:
    d = Drawing(104, 80)
    top, br, bl = (52.0, 19.0), (88.0, 60.0), (16.0, 60.0)
    plate = circle_hull([(top, 15.0), (br, 12.0), (bl, 12.0)])
    holes = [(top, 8.0), ((20.0, 59.0), 6.5), ((52.0, 62.0), 6.5), ((84.0, 59.0), 6.5),
             ((36.0, 40.0), 4.5), ((68.0, 40.0), 4.5)]
    d.add(_with_holes(plate, holes), _solid(pal, pal.color("plate"), evenodd=True))
    return d


@register("descender_eight", "Figure-8 descender", "Hardware",
          "Classic figure-8 descender / belay device.")
def _descender_eight(pal: Palette) -> Drawing:
    d = Drawing(64, 100)
    small, big = (32.0, 21.0), (32.0, 64.0)
    outline = two_circle_outline(small, 16.0, big, 30.0)
    d.add(_with_holes(outline, [(small, 7.5), (big, 19.0)]),
          _solid(pal, pal.color("eight"), evenodd=True))
    return d


@register("maillon", "Quick link (maillon)", "Hardware",
          "Screw-closing steel quick link (maillon rapide).")
def _maillon(pal: Palette) -> Drawing:
    d = Drawing(46, 96)
    t = 8.0
    corners = [(37.0, 9.0), (9.0, 9.0), (9.0, 87.0), (37.0, 87.0)]
    body = rounded_polygon([_lerp(corners[0], corners[3], 0.42)] + corners
                           + [_lerp(corners[3], corners[0], 0.38)],
                           [0.0, 13.0, 13.0, 13.0, 13.0, 0.0], closed=False)
    _rod(d, pal, body, t, pal.color("maillon"), cap="butt")
    # Threaded sleeve closing the gap on the right-hand side.
    a, b = _lerp(corners[0], corners[3], 0.30), _lerp(corners[0], corners[3], 0.66)
    d.add(_bar(a, b, t * 1.4, 2.0), _solid(pal, pal.color("sleeve")))
    for k in range(1, 5):
        m = _lerp(a, b, k / 5)
        d.add(Path().move(m[0] - t * 0.5, m[1]).line(m[0] + t * 0.5, m[1]),
              Style(stroke=pal.outline, width=0.5, cap="butt"))
    return d
