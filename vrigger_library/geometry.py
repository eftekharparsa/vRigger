"""Format-neutral vector drawing primitives.

Every library object is described once as a :class:`Drawing` made of
:class:`Shape` items. A shape is a path built only from move/line/cubic/close
commands, so the same description can be written to SVG, EPS or a Tk canvas
without any loss. Circular arcs are converted to cubic Béziers on creation.

Coordinates use the SVG convention: x to the right, y downwards, in
millimetres. The EPS writer flips the y axis itself.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

Point = tuple[float, float]

# Path commands: ("M", p) ("L", p) ("C", c1, c2, p) ("Z",)
Command = tuple


@dataclass
class Style:
    fill: str | None = None            # "#rrggbb" or None
    stroke: str | None = None          # "#rrggbb" or None
    width: float = 0.0                 # stroke width in mm
    evenodd: bool = False              # inner sub-paths become holes
    cap: str = "round"                 # butt | round | square
    join: str = "round"                # miter | round | bevel


@dataclass
class Shape:
    commands: list[Command]
    style: Style


@dataclass
class Drawing:
    width: float
    height: float
    shapes: list[Shape] = field(default_factory=list)

    def add(self, path: "Path", style: Style) -> None:
        self.shapes.append(Shape(list(path.commands), style))


class Path:
    """Small builder for move/line/cubic/close paths."""

    def __init__(self) -> None:
        self.commands: list[Command] = []
        self._current: Point | None = None

    # -- basic commands -------------------------------------------------
    def move(self, x: float, y: float) -> "Path":
        self.commands.append(("M", (x, y)))
        self._current = (x, y)
        return self

    def line(self, x: float, y: float) -> "Path":
        self.commands.append(("L", (x, y)))
        self._current = (x, y)
        return self

    def curve(self, c1: Point, c2: Point, p: Point) -> "Path":
        self.commands.append(("C", c1, c2, p))
        self._current = p
        return self

    def close(self) -> "Path":
        self.commands.append(("Z",))
        return self

    def extend(self, other: "Path") -> "Path":
        self.commands.extend(other.commands)
        self._current = other._current
        return self

    # -- arcs ---------------------------------------------------------------
    def arc(self, cx: float, cy: float, r: float, a0: float, a1: float,
            connect: bool = True) -> "Path":
        """Circular arc around (cx, cy) from angle a0 to a1 (degrees).

        Angles are measured clockwise on screen (SVG convention), so 0 is
        to the right and 90 is straight down. The arc runs in the direction
        of increasing angle when a1 > a0 and decreasing otherwise. With
        ``connect`` the arc start is joined to the current point by a line
        (or starts a new sub-path if there is none).
        """
        start = _polar(cx, cy, r, a0)
        if self._current is None or not connect:
            self.move(*start)
        elif _dist(self._current, start) > 1e-9:
            self.line(*start)
        sweep = a1 - a0
        segments = max(1, math.ceil(abs(sweep) / 90.0 - 1e-9))
        step = sweep / segments
        for i in range(segments):
            b0 = math.radians(a0 + i * step)
            b1 = math.radians(a0 + (i + 1) * step)
            k = 4.0 / 3.0 * math.tan((b1 - b0) / 4.0) * r
            p0 = (cx + r * math.cos(b0), cy + r * math.sin(b0))
            p3 = (cx + r * math.cos(b1), cy + r * math.sin(b1))
            c1 = (p0[0] - k * math.sin(b0), p0[1] + k * math.cos(b0))
            c2 = (p3[0] + k * math.sin(b1), p3[1] - k * math.cos(b1))
            self.curve(c1, c2, p3)
        return self


# ---------------------------------------------------------------------------
# Shape helpers
# ---------------------------------------------------------------------------

def _polar(cx: float, cy: float, r: float, deg: float) -> Point:
    a = math.radians(deg)
    return (cx + r * math.cos(a), cy + r * math.sin(a))


def _dist(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def circle(cx: float, cy: float, r: float, reverse: bool = False) -> Path:
    p = Path()
    if reverse:
        p.arc(cx, cy, r, 360, 0, connect=False)
    else:
        p.arc(cx, cy, r, 0, 360, connect=False)
    return p.close()


def rounded_polygon(points: list[Point], radii: float | list[float],
                    closed: bool = True) -> Path:
    """Polygon whose corners are rounded with the given radius per vertex.

    Works for any winding direction. With ``closed=False`` the first and last
    points stay sharp and the result is an open poly-line with rounded bends
    (used for rod-like parts such as carabiner bodies).
    """
    n = len(points)
    if isinstance(radii, (int, float)):
        radii = [float(radii)] * n
    path = Path()

    def corner(i: int) -> tuple[Point, Point, tuple[float, float, float, float, float]] | None:
        prev, cur, nxt = points[i - 1], points[i], points[(i + 1) % n]
        r = radii[i]
        v1 = (prev[0] - cur[0], prev[1] - cur[1])
        v2 = (nxt[0] - cur[0], nxt[1] - cur[1])
        l1, l2 = math.hypot(*v1), math.hypot(*v2)
        u1 = (v1[0] / l1, v1[1] / l1)
        u2 = (v2[0] / l2, v2[1] / l2)
        cos_t = max(-1.0, min(1.0, u1[0] * u2[0] + u1[1] * u2[1]))
        theta = math.acos(cos_t)                     # interior angle
        if r <= 0 or theta < 1e-6 or abs(theta - math.pi) < 1e-6:
            return None
        t = r / math.tan(theta / 2.0)                # tangent length
        lim1 = l1 if (not closed and i == 1) else l1 / 2.0
        lim2 = l2 if (not closed and i == n - 2) else l2 / 2.0
        t = min(t, lim1, lim2)
        r = t * math.tan(theta / 2.0)
        p1 = (cur[0] + u1[0] * t, cur[1] + u1[1] * t)
        p2 = (cur[0] + u2[0] * t, cur[1] + u2[1] * t)
        bis = (u1[0] + u2[0], u1[1] + u2[1])
        lb = math.hypot(*bis)
        d = r / math.sin(theta / 2.0)
        c = (cur[0] + bis[0] / lb * d, cur[1] + bis[1] / lb * d)
        a0 = math.degrees(math.atan2(p1[1] - c[1], p1[0] - c[0]))
        a1 = math.degrees(math.atan2(p2[1] - c[1], p2[0] - c[0]))
        sweep = (a1 - a0 + 540.0) % 360.0 - 180.0    # shortest way round
        return p1, p2, (c[0], c[1], r, a0, a0 + sweep)

    if closed:
        first = corner(0)
        start = first[1] if first else points[0]
        path.move(*start)
        order = list(range(1, n)) + [0]
    else:
        path.move(*points[0])
        order = list(range(1, n - 1))
    for i in order:
        c = corner(i)
        if c is None:
            path.line(*points[i])
        else:
            path.arc(*c[2])
    if not closed:
        path.line(*points[-1])
    else:
        path.close()
    return path


def two_circle_outline(c1: Point, r1: float, c2: Point, r2: float) -> Path:
    """Outline of the union of two overlapping circles (e.g. a figure-8)."""
    dx, dy = c2[0] - c1[0], c2[1] - c1[1]
    d = math.hypot(dx, dy)
    if not abs(r1 - r2) < d < r1 + r2:
        raise ValueError("circles must overlap without one containing the other")
    base = math.degrees(math.atan2(dy, dx))
    # Half-angle at each centre to the intersection points (law of cosines).
    h1 = math.degrees(math.acos((r1 * r1 + d * d - r2 * r2) / (2 * r1 * d)))
    h2 = math.degrees(math.acos((r2 * r2 + d * d - r1 * r1) / (2 * r2 * d)))
    p = Path()
    # Big arc on circle 1 (away from circle 2), then big arc on circle 2.
    p.arc(c1[0], c1[1], r1, base + h1, base + 360 - h1, connect=False)
    p.arc(c2[0], c2[1], r2, base + 180 + h2, base + 180 + 360 - h2)
    return p.close()


def flatten(commands: list[Command], tolerance: float = 0.25) -> list[tuple[list[Point], bool]]:
    """Convert path commands into poly-lines: [(points, closed), ...]."""
    out: list[tuple[list[Point], bool]] = []
    pts: list[Point] = []
    for cmd in commands:
        op = cmd[0]
        if op == "M":
            if len(pts) > 1:
                out.append((pts, False))
            pts = [cmd[1]]
        elif op == "L":
            pts.append(cmd[1])
        elif op == "C":
            p0 = pts[-1]
            c1, c2, p3 = cmd[1], cmd[2], cmd[3]
            length = _dist(p0, c1) + _dist(c1, c2) + _dist(c2, p3)
            steps = max(2, min(64, int(length / tolerance)))
            for i in range(1, steps + 1):
                t = i / steps
                mt = 1 - t
                pts.append((
                    mt ** 3 * p0[0] + 3 * mt * mt * t * c1[0] + 3 * mt * t * t * c2[0] + t ** 3 * p3[0],
                    mt ** 3 * p0[1] + 3 * mt * mt * t * c1[1] + 3 * mt * t * t * c2[1] + t ** 3 * p3[1],
                ))
        elif op == "Z":
            if len(pts) > 1:
                out.append((pts, True))
            pts = []
    if len(pts) > 1:
        out.append((pts, False))
    return out


def bounds(drawing: Drawing) -> tuple[float, float, float, float]:
    """Bounding box (x0, y0, x1, y1) including half the stroke widths."""
    x0 = y0 = math.inf
    x1 = y1 = -math.inf
    for shape in drawing.shapes:
        pad = shape.style.width / 2 if shape.style.stroke else 0.0
        for pts, _ in flatten(shape.commands, 0.5):
            for x, y in pts:
                x0, y0 = min(x0, x - pad), min(y0, y - pad)
                x1, y1 = max(x1, x + pad), max(y1, y + pad)
    return x0, y0, x1, y1
