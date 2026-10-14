"""Write a :class:`Drawing` as SVG or EPS (both fully vector, no dependencies)."""

from __future__ import annotations

import datetime as _dt
import os
from pathlib import Path as _FsPath

from .geometry import Drawing, Shape, Style

MM_TO_PT = 72.0 / 25.4
FORMATS = ("svg", "eps")


def _num(v: float) -> str:
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def _hex_to_rgb(color: str) -> tuple[float, float, float]:
    c = color.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    return tuple(int(c[i:i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]


def _xml_escape(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;"))


# ---------------------------------------------------------------------------
# SVG
# ---------------------------------------------------------------------------

def _svg_path_data(shape: Shape) -> str:
    parts = []
    for cmd in shape.commands:
        op = cmd[0]
        if op in ("M", "L"):
            parts.append(f"{op}{_num(cmd[1][0])} {_num(cmd[1][1])}")
        elif op == "C":
            parts.append("C" + " ".join(f"{_num(x)} {_num(y)}" for x, y in cmd[1:]))
        else:
            parts.append("Z")
    return "".join(parts)


def _svg_style(style: Style) -> str:
    attrs = [f'fill="{style.fill or "none"}"']
    if style.evenodd and style.fill:
        attrs.append('fill-rule="evenodd"')
    if style.stroke and style.width > 0:
        attrs.append(f'stroke="{style.stroke}"')
        attrs.append(f'stroke-width="{_num(style.width)}"')
        attrs.append(f'stroke-linecap="{style.cap}"')
        attrs.append(f'stroke-linejoin="{style.join}"')
    return " ".join(attrs)


def to_svg(drawing: Drawing, title: str = "", scale: float = 1.0) -> str:
    """Return SVG source. ``scale`` multiplies the physical size (mm)."""
    w, h = drawing.width, drawing.height
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" '
        f'width="{_num(w * scale)}mm" height="{_num(h * scale)}mm" '
        f'viewBox="0 0 {_num(w)} {_num(h)}">',
    ]
    if title:
        out.append(f"  <title>{_xml_escape(title)}</title>")
    for shape in drawing.shapes:
        out.append(f'  <path d="{_svg_path_data(shape)}" {_svg_style(shape.style)}/>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# EPS
# ---------------------------------------------------------------------------

_CAP = {"butt": 0, "round": 1, "square": 2}
_JOIN = {"miter": 0, "round": 1, "bevel": 2}


def _eps_path(shape: Shape) -> str:
    parts = ["newpath"]
    for cmd in shape.commands:
        op = cmd[0]
        if op == "M":
            parts.append(f"{_num(cmd[1][0])} {_num(cmd[1][1])} moveto")
        elif op == "L":
            parts.append(f"{_num(cmd[1][0])} {_num(cmd[1][1])} lineto")
        elif op == "C":
            parts.append(" ".join(f"{_num(x)} {_num(y)}" for x, y in cmd[1:]) + " curveto")
        else:
            parts.append("closepath")
    return "\n".join(parts)


def to_eps(drawing: Drawing, title: str = "", scale: float = 1.0) -> str:
    """Return EPS (PostScript level 2) source sized in points."""
    k = MM_TO_PT * scale
    w_pt, h_pt = drawing.width * k, drawing.height * k
    safe_title = title.replace("(", "").replace(")", "").replace("\\", "")
    out = [
        "%!PS-Adobe-3.0 EPSF-3.0",
        f"%%BoundingBox: 0 0 {int(round(w_pt))} {int(round(h_pt))}",
        f"%%HiResBoundingBox: 0 0 {w_pt:.3f} {h_pt:.3f}",
        f"%%Title: {safe_title}",
        "%%Creator: vRigger object library",
        f"%%CreationDate: {_dt.date.today().isoformat()}",
        "%%LanguageLevel: 2",
        "%%Pages: 1",
        "%%EndComments",
        "%%Page: 1 1",
        "gsave",
        # Model space is millimetres with y pointing down (as in SVG).
        f"0 {h_pt:.4f} translate {k:.6f} {-k:.6f} scale",
    ]
    for shape in drawing.shapes:
        st = shape.style
        path = _eps_path(shape)
        has_stroke = bool(st.stroke and st.width > 0)
        if st.fill:
            r, g, b = _hex_to_rgb(st.fill)
            out.append(path)
            if has_stroke:
                out.append("gsave")
            out.append(f"{r:.4f} {g:.4f} {b:.4f} setrgbcolor {'eofill' if st.evenodd else 'fill'}")
            if has_stroke:
                out.append("grestore")
        if has_stroke:
            if not st.fill:
                out.append(path)
            r, g, b = _hex_to_rgb(st.stroke)  # type: ignore[arg-type]
            out.append(f"{_num(st.width)} setlinewidth {_CAP[st.cap]} setlinecap "
                       f"{_JOIN[st.join]} setlinejoin {r:.4f} {g:.4f} {b:.4f} setrgbcolor stroke")
    out += ["grestore", "showpage", "%%EOF"]
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------

def render(drawing: Drawing, fmt: str, title: str = "", scale: float = 1.0) -> str:
    fmt = fmt.lower()
    if fmt == "svg":
        return to_svg(drawing, title, scale)
    if fmt == "eps":
        return to_eps(drawing, title, scale)
    raise ValueError(f"unknown format {fmt!r}; choose from {FORMATS}")


def save(drawing: Drawing, path: str | os.PathLike, title: str = "",
         scale: float = 1.0) -> _FsPath:
    """Write the drawing; the format comes from the file extension."""
    path = _FsPath(path)
    fmt = path.suffix.lstrip(".").lower()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(drawing, fmt, title, scale), encoding="utf-8")
    return path
