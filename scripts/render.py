"""Render the README pictures with measured dimensions. Needs the FreeCAD GUI.

Run build.FCMacro first, then this file in the same FreeCAD session (Macro menu or
the MCP execute_file tool). Writes docs/assembly.png, docs/exploded.png,
docs/parts.png and docs/ghost-fit.png. Every number is measured from the solids.
"""
import importlib.machinery
import importlib.util
from pathlib import Path

import FreeCAD as App
import FreeCADGui as Gui
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
# .FCMacro is not a known suffix, so name the source loader explicitly.
loader = importlib.machinery.SourceFileLoader("stool", str(ROOT / "build.FCMacro"))
spec = importlib.util.spec_from_loader("stool", loader)
P = importlib.util.module_from_spec(spec)  # Parameters only; build() is not run.
spec.loader.exec_module(P)

DOCS, TMP = ROOT / "docs", ROOT / "out"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
HEADER, RED = 110, (200, 30, 30)


def font(size):
    try:
        return ImageFont.truetype(FONT, size)
    except OSError:
        return ImageFont.load_default()


def shot(d, name, show):
    for o in d.Objects:
        if o.TypeId in ("PartDesign::Body", "Part::Feature"):
            o.Visibility = o.Name in show
    v = Gui.activeDocument().activeView()
    v.setAnimationEnabled(False)  # saveImage would catch a half-turned camera.
    v.setCameraType("Orthographic")
    v.viewAxonometric()
    v.fitAll()
    Gui.updateGui()
    w, h = v.getSize()  # Viewport size, so projected points line up with the image.
    path = TMP / (name + ".tmp.png")
    v.saveImage(str(path), w, h, "White")
    img = Image.open(path).convert("RGB")
    path.unlink()
    sheet = Image.new("RGB", (img.width, img.height + HEADER), "white")
    sheet.paste(img, (0, HEADER))
    return v, sheet


def px(view, p):
    x, y = view.getPointOnViewport(App.Vector(*p))
    return x, view.getSize()[1] - y + HEADER  # Coin origin is bottom-left.


def dim(draw, a, b, text, off):
    (ax, ay), (bx, by) = a, b
    n = ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5 or 1
    ox, oy = -(by - ay) / n * off, (bx - ax) / n * off
    a2, b2 = (ax + ox, ay + oy), (bx + ox, by + oy)
    draw.line([a, a2], fill=(150, 150, 150))
    draw.line([b, b2], fill=(150, 150, 150))
    draw.line([a2, b2], fill=RED, width=3)
    for x, y in (a2, b2):
        draw.ellipse([x - 4, y - 4, x + 4, y + 4], fill=RED)
    f = font(24)
    mx, my = (a2[0] + b2[0]) / 2 + ox * 0.6, (a2[1] + b2[1]) / 2 + oy * 0.6
    l, t, r, btm = draw.textbbox((0, 0), text, font=f)
    w, h = r - l, btm - t
    draw.rectangle([mx - w / 2 - 6, my - h / 2 - 6, mx + w / 2 + 6, my + h / 2 + 6], fill="white", outline=RED)
    draw.text((mx - w / 2, my - h / 2 - 2), text, fill=RED, font=f)


def title(draw, text, sub):
    draw.text((30, 20), text, fill=(20, 20, 20), font=font(36))
    draw.text((30, 66), sub, fill=(90, 90, 90), font=font(22))


def main():
    d = App.getDocument("StoolStand")
    assert d, "Run build.FCMacro first"
    shown = {o.Name: o.Visibility for o in d.Objects if hasattr(o, "Visibility")}
    DOCS.mkdir(exist_ok=True)
    bb = d.getObject("Assembly").Shape.optimalBoundingBox()
    W, H, h = bb.XLength, bb.ZLength, P.HALF
    try:
        v, img = shot(d, "assembly", {"Assembly"})
        g = ImageDraw.Draw(img)
        dim(g, px(v, (-h, h, H)), px(v, (h, h, H)), "%.0f mm" % W, -55)
        dim(g, px(v, (h, h, H)), px(v, (h, -h, H)), "%.0f mm" % bb.YLength, -55)
        dim(g, px(v, (h, -h, 0)), px(v, (h, -h, H)), "%.0f mm" % H, -60)
        title(g, "Purifier stool", "8 printed parts: 4 seat quarters + 4 legs  |  12 x M3 heat-set insert + M3x8")
        img.save(DOCS / "assembly.png")

        v, img = shot(d, "exploded", {"Exploded"})
        title(ImageDraw.Draw(img), "Exploded view",
              "Quarters slide down into each other's dovetails; legs drop into tapered recesses from below")
        img.save(DOCS / "exploded.png")

        v, img = shot(d, "ghost", {"Assembly", "GhostRoundPurifier", "GhostSquarePurifier"})
        g = ImageDraw.Draw(img)
        dim(g, px(v, (h - P.MARGIN, h, H)), px(v, (h, h, H)), "%.0f mm" % P.MARGIN, -45)
        title(g, "Ghost fit", "Round and square %.0f mm purifier bases on a %.0f mm seat: %.0f mm margin per side" % (
            P.LOAD_BASE, W, P.MARGIN))
        img.save(DOCS / "ghost-fit.png")

        # Printed parts side by side, in print orientation, from the released STLs.
        import Mesh
        seat = Mesh.Mesh(str(TMP / (P.SEAT_STL + ".stl")))
        leg = Mesh.Mesh(str(TMP / (P.LEG_STL + ".stl")))
        gap = 130.0  # The tall leg must clear the seat in the isometric projection.
        leg.translate(seat.BoundBox.XLength + gap, 0, 0)
        added = []
        for name, m in (("PrintSeat", seat), ("PrintLeg", leg)):
            o = d.addObject("Mesh::Feature", name)
            o.Mesh = m
            added.append(o.Name)
        try:
            v, img = shot(d, "parts", set(added))
            g = ImageDraw.Draw(img)
            sb, lb = seat.BoundBox, leg.BoundBox
            dim(g, px(v, (0, 0, 0)), px(v, (sb.XLength, 0, 0)), "%.0f mm" % sb.XLength, 45)
            dim(g, px(v, (0, 0, 0)), px(v, (0, sb.YLength, 0)), "%.0f mm" % sb.YLength, -45)
            dim(g, px(v, (lb.XMin, 0, 0)), px(v, (lb.XMax, 0, 0)), "%.0f mm" % lb.XLength, 45)
            dim(g, px(v, (lb.XMax, 0, 0)), px(v, (lb.XMax, 0, lb.ZLength)), "%.0f mm" % lb.ZLength, -60)
            title(g, "Printed parts, print orientation (4 of each)",
                  "Seat quarter %.0f x %.0f x %.0f, top face on bed  |  Leg %.0f x %.0f x %.0f, flange on bed" % (
                      sb.XLength, sb.YLength, sb.ZLength, lb.XLength, lb.YLength, lb.ZLength))
            img.save(DOCS / "parts.png")
        finally:
            for name in added:
                d.removeObject(name)
    finally:
        for name, vis in shown.items():
            if d.getObject(name):
                d.getObject(name).Visibility = vis
        d.recompute()
    print("PASS: docs/assembly.png, exploded.png, ghost-fit.png, parts.png")


main()
