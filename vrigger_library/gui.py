"""Graphical chooser: pick objects, formats and a destination, then export."""

from __future__ import annotations

import os
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import CATEGORIES, FORMATS, PALETTES, all_objects, export_objects
from .geometry import Drawing, flatten

PREVIEW_BG = "#f4f5f7"


def draw_on_canvas(canvas: tk.Canvas, drawing: Drawing, box: tuple[int, int, int, int],
                   bg: str = PREVIEW_BG) -> None:
    """Draw a Drawing scaled to fit inside box=(x, y, w, h) on a Tk canvas.

    Tk has no even-odd fill, so inner sub-paths of a holed shape are painted
    in the background colour.
    """
    bx, by, bw, bh = box
    k = min(bw / drawing.width, bh / drawing.height)
    ox = bx + (bw - drawing.width * k) / 2
    oy = by + (bh - drawing.height * k) / 2

    def tr(pts):
        return [c for x, y in pts for c in (ox + x * k, oy + y * k)]

    for shape in drawing.shapes:
        st = shape.style
        polys = flatten(shape.commands, tolerance=0.4)
        width = max(1.0, st.width * k) if st.stroke else 0
        for i, (pts, closed) in enumerate(polys):
            coords = tr(pts)
            if st.fill and closed:
                fill = bg if (st.evenodd and i > 0) else st.fill
                canvas.create_polygon(coords, fill=fill, outline=st.stroke or "",
                                      width=width, joinstyle=tk.ROUND)
            elif st.stroke:
                if closed:
                    coords += coords[:2]
                canvas.create_line(coords, fill=st.stroke, width=width,
                                   capstyle={"round": tk.ROUND, "butt": tk.BUTT,
                                             "square": tk.PROJECTING}[st.cap],
                                   joinstyle=tk.ROUND)


class App(ttk.Frame):
    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master, padding=10)
        self.master = master
        master.title("vRigger Object Library")
        master.minsize(760, 520)
        self.grid(sticky="nsew")
        master.columnconfigure(0, weight=1)
        master.rowconfigure(0, weight=1)

        self.objects = all_objects()
        self.selected = {o.id: tk.BooleanVar(value=False) for o in self.objects}
        self.formats = {f: tk.BooleanVar(value=(f == "svg")) for f in FORMATS}
        self.palette = tk.StringVar(value="color")
        self.scale = tk.DoubleVar(value=1.0)
        self.keep = tk.BooleanVar(value=False)
        self.dest = tk.StringVar(value=str(Path.home() / "vRigger objects"))
        self.status = tk.StringVar(value="Tick the objects you want, then press Export.")
        self.current = self.objects[0].id

        self._build()
        self._refresh()

    # -- layout -------------------------------------------------------------
    def _build(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # Object list, grouped by category.
        left = ttk.LabelFrame(self, text="Objects", padding=8)
        left.grid(row=0, column=0, sticky="nsw", padx=(0, 10))
        row = 0
        for cat in CATEGORIES:
            items = [o for o in self.objects if o.category == cat]
            if not items:
                continue
            ttk.Label(left, text=cat, font=("TkDefaultFont", 10, "bold")).grid(
                row=row, column=0, sticky="w", pady=(6 if row else 0, 2))
            row += 1
            for o in items:
                cb = ttk.Checkbutton(left, text=o.name, variable=self.selected[o.id],
                                     command=lambda i=o.id: self._show(i))
                cb.grid(row=row, column=0, sticky="w", padx=(12, 0))
                cb.bind("<Enter>", lambda _e, i=o.id: self._show(i))
                row += 1
        btns = ttk.Frame(left)
        btns.grid(row=row, column=0, sticky="w", pady=(10, 0))
        ttk.Button(btns, text="Select all", command=lambda: self._set_all(True)).pack(side="left")
        ttk.Button(btns, text="Clear", command=lambda: self._set_all(False)).pack(side="left", padx=4)

        # Preview of the highlighted object plus thumbnails of the selection.
        right = ttk.LabelFrame(self, text="Preview", padding=8)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(right, bg=PREVIEW_BG, highlightthickness=0, height=300)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", lambda _e: self._refresh())
        self.caption = ttk.Label(right, wraplength=420, justify="left")
        self.caption.grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.strip = tk.Canvas(right, bg=PREVIEW_BG, highlightthickness=0, height=70)
        self.strip.grid(row=2, column=0, sticky="ew", pady=(6, 0))

        # Export options.
        opts = ttk.LabelFrame(self, text="Export", padding=8)
        opts.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        opts.columnconfigure(1, weight=1)

        ttk.Label(opts, text="Format:").grid(row=0, column=0, sticky="w")
        fr = ttk.Frame(opts)
        fr.grid(row=0, column=1, sticky="w")
        for f in FORMATS:
            ttk.Checkbutton(fr, text=f.upper(), variable=self.formats[f]).pack(side="left", padx=(0, 10))
        ttk.Label(fr, text="   Style:").pack(side="left")
        for p in PALETTES:
            ttk.Radiobutton(fr, text=p.capitalize(), value=p, variable=self.palette,
                            command=self._refresh).pack(side="left", padx=(4, 6))
        ttk.Label(fr, text="   Scale:").pack(side="left")
        ttk.Spinbox(fr, from_=0.1, to=20, increment=0.1, width=6,
                    textvariable=self.scale).pack(side="left", padx=4)
        ttk.Label(fr, text="× real size").pack(side="left")

        ttk.Label(opts, text="Save to:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(opts, textvariable=self.dest).grid(row=1, column=1, sticky="ew", pady=(8, 0))
        ttk.Button(opts, text="Browse…", command=self._browse).grid(row=1, column=2, padx=(6, 0), pady=(8, 0))

        bottom = ttk.Frame(opts)
        bottom.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        bottom.columnconfigure(1, weight=1)
        ttk.Checkbutton(bottom, text="Don't overwrite existing files",
                        variable=self.keep).grid(row=0, column=0, sticky="w")
        ttk.Label(bottom, textvariable=self.status, foreground="#555").grid(
            row=0, column=1, sticky="w", padx=10)
        ttk.Button(bottom, text="Export", command=self._export).grid(row=0, column=2, sticky="e")

    # -- actions --------------------------------------------------------------
    def _show(self, obj_id: str) -> None:
        self.current = obj_id
        self._refresh()

    def _set_all(self, value: bool) -> None:
        for v in self.selected.values():
            v.set(value)
        self._refresh()

    def _refresh(self) -> None:
        obj = next(o for o in self.objects if o.id == self.current)
        drawing = obj.draw(self.palette.get())
        c = self.canvas
        c.delete("all")
        w, h = max(c.winfo_width(), 50), max(c.winfo_height(), 50)
        draw_on_canvas(c, drawing, (16, 16, w - 32, h - 32))
        self.caption.config(text=f"{obj.name}  ({drawing.width:g} × {drawing.height:g} mm)\n"
                                 f"{obj.description}")
        # Thumbnails of everything currently ticked.
        s = self.strip
        s.delete("all")
        chosen = [o for o in self.objects if self.selected[o.id].get()]
        if not chosen:
            s.create_text(8, 35, anchor="w", fill="#888", text="No objects selected yet.")
        for i, o in enumerate(chosen):
            draw_on_canvas(s, o.draw(self.palette.get()), (8 + i * 64, 6, 56, 58))
        self.status.set(f"{len(chosen)} object(s) selected.")

    def _browse(self) -> None:
        start = self.dest.get() if os.path.isdir(self.dest.get()) else str(Path.home())
        folder = filedialog.askdirectory(initialdir=start, title="Choose destination folder")
        if folder:
            self.dest.set(folder)

    def _export(self) -> None:
        ids = [o.id for o in self.objects if self.selected[o.id].get()]
        formats = [f for f in FORMATS if self.formats[f].get()]
        if not ids:
            messagebox.showwarning("Nothing selected", "Tick at least one object.")
            return
        if not formats:
            messagebox.showwarning("No format", "Choose SVG, EPS or both.")
            return
        try:
            scale = float(self.scale.get())
            paths = export_objects(ids, self.dest.get(), formats, self.palette.get(),
                                   scale, overwrite=not self.keep.get())
        except (ValueError, tk.TclError, OSError) as exc:
            messagebox.showerror("Export failed", str(exc))
            return
        self.status.set(f"Saved {len(paths)} file(s) to {Path(paths[0]).parent}")
        messagebox.showinfo("Export complete",
                            f"Saved {len(paths)} file(s) to:\n{Path(paths[0]).parent}")


def main() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
