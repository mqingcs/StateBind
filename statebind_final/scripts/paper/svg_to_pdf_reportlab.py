#!/usr/bin/env python3
"""Convert the paper's deliberately simple SVG dialect to an embedded-font PDF.

The figure generator uses only rectangles, lines, circles, polygons, polylines,
text, and embedded raster images.  Rendering that subset directly keeps every
plot vector while avoiding the auxiliary Type-3 text objects emitted by the
platform SVG renderer.
"""

from __future__ import annotations

import base64
import io
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import reportlab
from reportlab.lib.colors import Color, HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas


MAC_FONT_DIR = Path("/System/Library/Fonts/Supplemental")
DEJAVU_FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")
REPORTLAB_FONT_DIR = Path(reportlab.__file__).resolve().parent / "fonts"
FONT_CANDIDATES = {
    "PaperRegular": (
        MAC_FONT_DIR / "Times New Roman.ttf",
        DEJAVU_FONT_DIR / "DejaVuSerif.ttf",
        REPORTLAB_FONT_DIR / "Vera.ttf",
    ),
    "PaperBold": (
        MAC_FONT_DIR / "Times New Roman Bold.ttf",
        DEJAVU_FONT_DIR / "DejaVuSerif-Bold.ttf",
        REPORTLAB_FONT_DIR / "VeraBd.ttf",
    ),
    "PaperItalic": (
        MAC_FONT_DIR / "Times New Roman Italic.ttf",
        DEJAVU_FONT_DIR / "DejaVuSerif-Italic.ttf",
        REPORTLAB_FONT_DIR / "VeraIt.ttf",
    ),
    "PaperBoldItalic": (
        MAC_FONT_DIR / "Times New Roman Bold Italic.ttf",
        DEJAVU_FONT_DIR / "DejaVuSerif-BoldItalic.ttf",
        REPORTLAB_FONT_DIR / "VeraBI.ttf",
    ),
}


def _register_fonts() -> None:
    for name, candidates in FONT_CANDIDATES.items():
        if name not in pdfmetrics.getRegisteredFontNames():
            path = next((candidate for candidate in candidates if candidate.exists()), None)
            if path is None:
                raise RuntimeError(f"no embeddable fallback font found for {name}")
            pdfmetrics.registerFont(TTFont(name, str(path)))


def _number(value: str | None, default: float = 0.0) -> float:
    if value is None:
        return default
    match = re.match(r"[-+0-9.eE]+", value)
    return float(match.group(0)) if match else default


def _color(value: str | None, default: Color | None = None) -> Color | None:
    if value is None:
        return default
    if value.lower() == "none":
        return None
    if value.startswith("#"):
        return HexColor(value)
    named = {"white": "#FFFFFF", "black": "#000000"}
    return HexColor(named.get(value.lower(), "#000000"))


def _paint(canvas: Canvas, element: ET.Element) -> tuple[bool, bool]:
    fill = _color(element.get("fill"), None)
    stroke = _color(element.get("stroke"), None)
    if fill is not None:
        canvas.setFillColor(fill)
    if stroke is not None:
        canvas.setStrokeColor(stroke)
        canvas.setLineWidth(_number(element.get("stroke-width"), 1.0))
    dash = element.get("stroke-dasharray")
    canvas.setDash([float(v) for v in dash.split()] if dash else [])
    return fill is not None, stroke is not None


def _font_name(element: ET.Element) -> str:
    bold = _number(element.get("font-weight"), 400) >= 600
    italic = element.get("font-style") == "italic"
    if bold and italic:
        return "PaperBoldItalic"
    if bold:
        return "PaperBold"
    if italic:
        return "PaperItalic"
    return "PaperRegular"


def convert_svg_to_pdf(svg_path: Path, pdf_path: Path) -> None:
    _register_fonts()
    root = ET.parse(svg_path).getroot()
    width = _number(root.get("width"))
    height = _number(root.get("height"))
    canvas = Canvas(
        str(pdf_path),
        pagesize=(width, height),
        pageCompression=1,
        initialFontName="PaperRegular",
        initialFontSize=12,
    )
    canvas.setTitle(svg_path.stem)

    for element in list(root):
        tag = element.tag.rsplit("}", 1)[-1]
        if tag == "rect":
            fill, stroke = _paint(canvas, element)
            x, y = _number(element.get("x")), _number(element.get("y"))
            w = width if element.get("width", "").endswith("%") else _number(element.get("width"))
            h = height if element.get("height", "").endswith("%") else _number(element.get("height"))
            radius = _number(element.get("rx"))
            if radius:
                canvas.roundRect(x, height - y - h, w, h, radius, int(stroke), int(fill))
            else:
                canvas.rect(x, height - y - h, w, h, int(stroke), int(fill))
        elif tag == "line":
            _, stroke = _paint(canvas, element)
            if stroke:
                canvas.line(
                    _number(element.get("x1")), height - _number(element.get("y1")),
                    _number(element.get("x2")), height - _number(element.get("y2")),
                )
        elif tag == "circle":
            fill, stroke = _paint(canvas, element)
            canvas.circle(
                _number(element.get("cx")), height - _number(element.get("cy")),
                _number(element.get("r")), int(stroke), int(fill),
            )
        elif tag in {"polygon", "polyline"}:
            fill, stroke = _paint(canvas, element)
            points = [tuple(map(float, pair.split(","))) for pair in element.get("points", "").split()]
            if not points:
                continue
            path = canvas.beginPath()
            path.moveTo(points[0][0], height - points[0][1])
            for x, y in points[1:]:
                path.lineTo(x, height - y)
            if tag == "polygon":
                path.close()
            canvas.drawPath(path, int(stroke), int(fill and tag == "polygon"))
        elif tag == "text":
            value = "".join(element.itertext())
            size = _number(element.get("font-size"), 12)
            font = _font_name(element)
            canvas.setFont(font, size)
            fill = _color(element.get("fill"), HexColor("#202124"))
            canvas.setFillColor(fill)
            x, y = _number(element.get("x")), height - _number(element.get("y"))
            anchor = element.get("text-anchor", "start")
            if anchor == "middle":
                canvas.drawCentredString(x, y, value)
            elif anchor == "end":
                canvas.drawRightString(x, y, value)
            else:
                canvas.drawString(x, y, value)
        elif tag == "image":
            href = element.get("{http://www.w3.org/1999/xlink}href", "")
            if not href.startswith("data:"):
                continue
            payload = href.split(",", 1)[1]
            reader = ImageReader(io.BytesIO(base64.b64decode(payload)))
            x, y = _number(element.get("x")), _number(element.get("y"))
            w, h = _number(element.get("width")), _number(element.get("height"))
            iw, ih = reader.getSize()
            slice_mode = "slice" in element.get("preserveAspectRatio", "")
            scale = max(w / iw, h / ih) if slice_mode else min(w / iw, h / ih)
            dw, dh = iw * scale, ih * scale
            dx = x + (w - dw) / 2
            dy = height - y - h + (h - dh) / 2
            if slice_mode:
                canvas.saveState()
                clip = canvas.beginPath()
                clip.rect(x, height - y - h, w, h)
                canvas.clipPath(clip, stroke=0, fill=0)
            canvas.drawImage(reader, dx, dy, dw, dh, preserveAspectRatio=True, mask="auto")
            if slice_mode:
                canvas.restoreState()

    canvas.showPage()
    canvas.save()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("svg", type=Path)
    parser.add_argument("pdf", type=Path)
    args = parser.parse_args()
    convert_svg_to_pdf(args.svg, args.pdf)
