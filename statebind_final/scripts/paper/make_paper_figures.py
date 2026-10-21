#!/usr/bin/env python3
"""Generate the five camera-ready figures for the StateBind paper.

The figures deliberately use a restrained conference-paper visual language:
paper-matched serif type, black/gray structure, one semantic blue, direct
labels, and real image evidence only where it clarifies the scientific claim.
"""

from __future__ import annotations

import base64
import json
import math
import shutil
import subprocess
from html import escape
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
PAPER = ROOT / "statebind_final" / "paper"
FIGURES = PAPER / "figures"
EVIDENCE = PAPER / "paper_evidence.json"

FONT = "STIX Two Text"
INK = "#202124"
MUTED = "#62676D"
MID = "#969BA1"
GRID = "#D6D9DD"
LIGHT = "#F4F5F6"
BLUE = "#2F6793"
PALE_BLUE = "#E9F0F5"
WHITE = "#FFFFFF"


def load_json(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def text(x, y, value, size=22, weight=400, fill=INK, anchor="start", italic=False):
    style = "italic" if italic else "normal"
    return (
        f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" '
        f'font-style="{style}" font-weight="{weight}" fill="{fill}" '
        f'text-anchor="{anchor}">{escape(str(value))}</text>'
    )


def rect(x, y, w, h, fill=WHITE, stroke=GRID, sw=1.4, rx=0):
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'
    )


def line(x1, y1, x2, y2, stroke=INK, sw=1.5, dash=None, opacity=1.0):
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
        f'stroke="{stroke}" stroke-width="{sw}" opacity="{opacity}"{dash_attr}/>'
    )


def circle(cx, cy, r, fill=WHITE, stroke=INK, sw=1.7):
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'


def polygon(points, fill=WHITE, stroke=INK, sw=1.6):
    pts = " ".join(f"{x},{y}" for x, y in points)
    return f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'


def marker(shape, x, y, size=7, fill=WHITE, stroke=INK, sw=1.7):
    if shape == "circle":
        return circle(x, y, size, fill, stroke, sw)
    if shape == "square":
        return rect(x - size, y - size, 2 * size, 2 * size, fill, stroke, sw)
    if shape == "diamond":
        return polygon([(x, y - size), (x + size, y), (x, y + size), (x - size, y)], fill, stroke, sw)
    if shape == "triangle":
        return polygon([(x, y - size), (x + size, y + size), (x - size, y + size)], fill, stroke, sw)
    raise ValueError(shape)


def arrow(x1, y1, x2, y2, stroke=INK, sw=1.5):
    angle = math.atan2(y2 - y1, x2 - x1)
    head = 7
    p1 = (x2 + head * math.cos(angle + 2.62), y2 + head * math.sin(angle + 2.62))
    p2 = (x2 + head * math.cos(angle - 2.62), y2 + head * math.sin(angle - 2.62))
    return line(x1, y1, x2, y2, stroke, sw) + polygon([(x2, y2), p1, p2], stroke, stroke, 0)


def image_data(path: Path) -> str:
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def embedded_image(path: Path, x, y, w, h, mode="meet"):
    return (
        f'<image x="{x}" y="{y}" width="{w}" height="{h}" '
        f'preserveAspectRatio="xMidYMid {mode}" xlink:href="{image_data(path)}"/>'
    )


def slice_map(path: Path, x, y, w, h, nx, ny):
    """Map normalized 0--1000 source coordinates into a centered slice box."""
    with Image.open(path) as image:
        iw, ih = image.size
    scale = max(w / iw, h / ih)
    dw, dh = iw * scale, ih * scale
    dx, dy = x + (w - dw) / 2, y + (h - dh) / 2
    return dx + (nx / 1000) * iw * scale, dy + (ny / 1000) * ih * scale


def svg_root(width, height, body):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        f'<rect width="100%" height="100%" fill="white"/>{body}</svg>'
    )


def save_figure(name: str, width: int, height: int, body: str):
    FIGURES.mkdir(parents=True, exist_ok=True)
    svg_path = FIGURES / f"{name}.svg"
    pdf_path = FIGURES / f"{name}.pdf"
    png_path = FIGURES / f"{name}.png"
    svg_path.write_text(svg_root(width, height, body), encoding="utf-8")
    from svg_to_pdf_reportlab import convert_svg_to_pdf

    convert_svg_to_pdf(svg_path, pdf_path)
    if shutil.which("rsvg-convert"):
        subprocess.run(
            [
                "rsvg-convert", "-f", "png", "-w", str(width * 2), "-h", str(height * 2),
                "-o", str(png_path), str(svg_path),
            ],
            check=True,
        )


def make_teaser():
    clean = ROOT / "round3/generated/statebind_test131_interfaces/images/r4_026__d4__clean.png"
    physical = ROOT / "round3/generated/statebind_test131_interfaces/images/r4_026__d4__swapped_order__physical.png"
    w, h = 1200, 400
    body = [
        text(20, 28, "(a) Numeric", 24, 700),
        text(414, 28, "(b) Physicalized", 24, 700),
        text(846, 28, "(c) Automatic evidence check", 23, 700),
        line(395, 10, 395, 337, GRID, 1.1),
        line(835, 10, 835, 337, GRID, 1.1),
        embedded_image(clean, 20, 44, 355, 230, mode="slice"),
        embedded_image(physical, 415, 44, 400, 230, mode="slice"),
        text(198, 302, "A  38.70 °C     B  38.25 °C", 22, 400, INK, "middle"),
        text(615, 302, "A  38.70 °C     B  38.25 °C", 22, 400, INK, "middle"),
        text(198, 333, "majority selects A", 21, 400, MUTED, "middle"),
        text(615, 333, "majority selects B", 21, 700, BLUE, "middle"),
    ]

    x0, y0 = 948, 88
    body += [
        text(1015, 60, "lattice source", 18, 400, MUTED, "middle"),
        text(x0 + 28.5, y0 - 8, "D", 19, 700, MUTED, "middle"),
        text(x0 + 104.5, y0 - 8, "G", 19, 700, MUTED, "middle"),
        text(x0 - 14, y0 + 26, "target D", 18, 400, MUTED, "end"),
        text(x0 - 14, y0 + 88, "target G", 18, 400, MUTED, "end"),
    ]
    for row in range(2):
        for col in range(2):
            x, y = x0 + col * 76, y0 + row * 62
            body += [rect(x, y, 57, 40, WHITE, GRID, 1.3), text(x + 28.5, y + 28, "B", 24, 700, BLUE, "middle")]
    body += [
        line(856, 226, 1174, 226, GRID, 1.1),
        text(1015, 258, "four validated combinations", 20, 400, INK, "middle"),
        text(1015, 289, "all select candidate B", 21, 700, BLUE, "middle"),
        arrow(1015, 302, 1015, 326, BLUE, 1.4),
        text(1015, 352, "accept B", 22, 700, BLUE, "middle"),
        line(20, 365, 815, 365, GRID, 1.1),
        text(418, 391, "Paired128 majority: 75.54 → 91.13%  (+15.30 pp, image-balanced)", 20, 400, INK, "middle"),
    ]
    save_figure("fig1_teaser", w, h, "".join(body))


def make_representation_ladder(evidence):
    w, h = 1120, 400
    body = []
    rows = [
        ("Doubao", evidence["representation"]["models"]["doubao"]),
        ("Gemini", evidence["representation"]["models"]["gemini"]),
        ("Qwen", evidence["representation"]["models"]["qwen"]),
        ("Majority", evidence["representation"]["majority"]),
    ]
    body += [
        text(18, 28, "Call accuracy (%)", 23, 700),
        text(790, 28, "Image-balanced Physicalized − Numeric (pp)", 23, 700, INK, "middle"),
        text(180, 60, "Numeric", 20, 400, MUTED, "middle"),
        text(300, 60, "Calibrated", 20, 400, MUTED, "middle"),
        text(420, 60, "Physicalized", 20, 700, BLUE, "middle"),
        line(18, 72, 478, 72, GRID, 1.1),
        line(515, 12, 515, 375, GRID, 1.1),
    ]
    fx0, fx1 = 585, 1065
    for value in (0, 5, 10, 15, 20):
        x = fx0 + value / 24 * (fx1 - fx0)
        body += [line(x, 72, x, 330, GRID, 1, dash="3 4"), text(x, 356, value, 18, 400, MUTED, "middle")]
    for index, ((label, row), y) in enumerate(zip(rows, (112, 176, 240, 304))):
        if index == 3:
            body.append(line(18, y - 33, 1065, y - 33, GRID, 1.1))
        body += [
            text(18, y + 7, label, 22, 700 if index == 3 else 400),
            text(180, y + 7, f'{100 * row["numeric_accuracy"]:.1f}', 22, 400, INK, "middle"),
            text(300, y + 7, f'{100 * row["calibrated_accuracy"]:.1f}', 22, 400, MUTED, "middle"),
            text(420, y + 7, f'{100 * row["physicalized_accuracy"]:.1f}', 22, 700, BLUE, "middle"),
        ]
        effect = 100 * row["image_balanced_effect"]
        low, high = (100 * v for v in row["image_bootstrap_95_interval"])
        x_low = fx0 + low / 24 * (fx1 - fx0)
        x_high = fx0 + high / 24 * (fx1 - fx0)
        x_eff = fx0 + effect / 24 * (fx1 - fx0)
        body += [
            line(x_low, y, x_high, y, BLUE, 2.1),
            line(x_low, y - 5, x_low, y + 5, BLUE, 1.7),
            line(x_high, y - 5, x_high, y + 5, BLUE, 1.7),
            marker("diamond" if index == 3 else "circle", x_eff, y, 6.2, BLUE, BLUE, 1.3),
            text(min(x_high + 10, 1070), y + 6, f"{effect:.1f}", 19, 700, BLUE),
        ]
    body.append(text(825, 383, "95% source-image bootstrap interval", 18, 400, MUTED, "middle"))
    save_figure("fig2_representation_ladder", w, h, "".join(body))


def make_mechanism():
    source = ROOT / "round3/generated/sol_high_real200_curator/full_resolution_images/mb_a93e660b90db82853604.png"
    w, h = 1200, 385
    body = [
        text(18, 27, "(a) Target found, lattice misplaced", 24, 700),
        text(450, 27, "(b) Within one tick", 24, 700),
        text(835, 27, "(c) Physicalized gain (pp)", 24, 700),
        line(420, 10, 420, 360, GRID, 1.1),
        line(805, 10, 805, 360, GRID, 1.1),
        embedded_image(source, 18, 47, 382, 245, mode="slice"),
    ]
    tx, ty = slice_map(source, 18, 47, 382, 245, 631, 500)
    body += [
        line(tx, ty - 30, tx, ty + 35, BLUE, 4.0),
        text(tx + 9, ty - 18, "target", 20, 700, BLUE),
    ]
    for nx in (590, 602, 614, 626, 638, 650, 662, 674, 686, 698):
        px, py = slice_map(source, 18, 47, 382, 245, nx, 500)
        body.append(line(px, py + 20, px, py + 31, MUTED, 1.6))
    body += [
        text(18, 322, "Doubao proposal on r4_026", 20, 400, INK),
        text(18, 350, "target error 0.01 tick", 20, 700, BLUE),
        text(218, 350, "lattice error 4.63 ticks", 20, 400, MUTED),
    ]

    ax0, ax1 = 545, 770
    for value in (0, 20, 40, 60, 80):
        x = ax0 + value / 80 * (ax1 - ax0)
        body += [line(x, 65, x, 305, GRID, 1, dash="3 4"), text(x, 331, value, 19, 400, MUTED, "middle")]
    for label, target_v, lattice_v, y in (("Doubao", 62.60, 24.39, 126), ("Gemini", 46.77, 41.94, 239)):
        xt = ax0 + target_v / 80 * (ax1 - ax0)
        xl = ax0 + lattice_v / 80 * (ax1 - ax0)
        body += [
            text(450, y + 6, label, 21, 400),
            line(min(xt, xl), y, max(xt, xl), y, MID, 1.7),
            marker("circle", xt, y, 6.2, WHITE, INK, 1.6),
            marker("square", xl, y, 5.7, BLUE, BLUE, 1.3),
            text(xt, y - 15, f"{target_v:.1f}", 18, 400, INK, "middle"),
            text(xl, y + 25, f"{lattice_v:.1f}", 18, 700, BLUE, "middle"),
        ]
    body += [
        marker("circle", 548, 369, 4.8, WHITE, INK, 1.4), text(560, 375, "target", 19, 400, MUTED),
        marker("square", 655, 369, 4.5, BLUE, BLUE, 1.2), text(667, 375, "lattice", 19, 400, MUTED),
    ]

    cx0, cx1 = 930, 1170
    for value in (0, 10, 20, 30):
        x = cx0 + value / 32 * (cx1 - cx0)
        body += [line(x, 65, x, 308, GRID, 1, dash="3 4"), text(x, 334, value, 19, 400, MUTED, "middle")]
    for label, single, span, y in (("Doubao", 6.37, 18.18, 105), ("Gemini", 14.78, 23.48, 190), ("Qwen", 13.44, 28.79, 275)):
        xs = cx0 + single / 32 * (cx1 - cx0)
        xp = cx0 + span / 32 * (cx1 - cx0)
        body += [
            text(835, y + 6, label, 21, 400),
            line(xs, y, xp, y, MID, 1.7),
            marker("circle", xs, y, 5.8, WHITE, INK, 1.6),
            marker("circle", xp, y, 6.2, BLUE, BLUE, 1.3),
            text(xs, y - 14, f"{single:.1f}", 18, 400, INK, "middle"),
            text(xp, y + 24, f"{span:.1f}", 18, 700, BLUE, "middle"),
        ]
    body += [
        marker("circle", 932, 369, 4.7, WHITE, INK, 1.4), text(944, 375, "single", 19, 400, MUTED),
        marker("circle", 1040, 369, 4.8, BLUE, BLUE, 1.2), text(1052, 375, "two endpoints", 19, 400, MUTED),
    ]
    save_figure("fig3_mechanism", w, h, "".join(body))


def proposal_panel(body, source, x, y, w, h, label, target_x, ticks, colour=BLUE):
    body += [text(x, y - 10, label, 25, 700), embedded_image(source, x, y, w, h, mode="slice")]
    tx, ty = slice_map(source, x, y, w, h, target_x, 500)
    body.append(line(tx, ty - 25, tx, ty + 28, colour, 3.4))
    for nx in ticks:
        px, py = slice_map(source, x, y, w, h, nx, 500)
        body.append(line(px, py + 15, px, py + 25, MUTED, 1.4))


def state_cell(body, x, y, w, h, target_source, lattice_source):
    body += [
        rect(x, y, w, h, WHITE, GRID, 1.3),
        text(x + 12, y + 24, f"target {target_source}  /  lattice {lattice_source}", 21, 400, MUTED),
    ]
    x0, x1, ay = x + 22, x + w - 22, y + 55
    body.append(line(x0, ay, x1, ay, INK, 1.4))
    spacing = 18 if lattice_source == "D" else 15
    phase = 2 if lattice_source == "D" else 6
    for tx in range(int(x0 + phase), int(x1), spacing):
        body.append(line(tx, ay - 8, tx, ay + 8, MUTED, 1.1))
    target = x0 + (0.52 if target_source == "D" else 0.55) * (x1 - x0)
    body += [line(target, ay - 20, target, ay + 19, BLUE, 3.0), text(x + w - 16, y + h - 12, "B", 24, 700, BLUE, "end")]


def make_architecture():
    source = ROOT / "round3/generated/sol_high_real200_curator/full_resolution_images/mb_a93e660b90db82853604.png"
    w, h = 1200, 525
    body = [
        text(20, 30, "Independent proposals", 27, 700),
        text(738, 30, "Evidence checks", 27, 700),
        line(700, 10, 700, 242, GRID, 1.1),
    ]
    proposal_panel(body, source, 20, 62, 310, 160, "Doubao: target D, lattice D", 631, (590, 602, 614, 626, 638, 650, 662, 674, 686, 698))
    proposal_panel(body, source, 365, 62, 310, 160, "Gemini: target G, lattice G", 631, (608, 615, 622, 629, 636, 643))
    body += [
        text(738, 73, "Qwen component verifier", 25, 700, BLUE),
        circle(747, 107, 4.3, BLUE, BLUE, 1.0), text(762, 114, "target boundary evidence", 22, 400),
        circle(747, 141, 4.3, BLUE, BLUE, 1.0), text(762, 148, "local tick and anchor evidence", 22, 400),
        circle(747, 175, 4.3, BLUE, BLUE, 1.0), text(762, 182, "branch, unit, and operator", 22, 400),
        line(738, 193, 1168, 193, GRID, 1.1),
        text(953, 224, "evidence only; candidate identity hidden", 21, 400, MUTED, "middle"),
        line(20, 257, 1175, 257, GRID, 1.1),
        text(20, 292, "Recombine verified components", 27, 700),
    ]
    for idx, (ts, ls) in enumerate((("D", "D"), ("D", "G"), ("G", "D"), ("G", "G"))):
        state_cell(body, 20 + idx * 288, 315, 265, 112, ts, ls)
    body += [
        line(20, 450, 1175, 450, GRID, 1.1),
        text(365, 488, "4/4 agree", 25, 700, BLUE, "middle"),
        arrow(443, 480, 535, 480, BLUE, 1.7),
        text(630, 488, "accept B", 25, 700, BLUE, "middle"),
        text(820, 488, "otherwise", 22, 400, MUTED, "middle"),
        arrow(890, 480, 985, 480, MUTED, 1.5),
        text(1090, 488, "Numeric", 23, 400, INK, "middle"),
    ]
    save_figure("fig4_factorial_architecture", w, h, "".join(body))


def make_reliability_atlas(evidence):
    attr = evidence["factorial"]["attribution"]
    route = attr["exact_factorial_route"]["readers"]
    distances = attr["validation_and_margin"]["heldout"]["validated_full_agreement_by_distance"]
    w, h = 1200, 400
    body = [
        text(18, 30, "(a) Exact-route accuracy", 29, 700),
        text(650, 30, "(b) Precision by state separation", 29, 700),
        line(620, 10, 620, 378, GRID, 1.1),
    ]

    reader_rows = [
        ("Doubao", route["doubao"]),
        ("Gemini", route["gemini"]),
        ("Qwen", route["qwen_batch_no_thinking"]),
        ("Majority", route["three_model_numeric_majority"]),
        ("Factorial", route["factorial_statebind"]),
    ]
    bx0, bx1 = 250, 590
    for value in (70, 80, 90, 100):
        x = bx0 + (value - 70) / 30 * (bx1 - bx0)
        body += [
            line(x, 62, x, 326, GRID, 1, dash="3 4"),
            text(x, 350, value, 21, 400, MUTED, "middle"),
        ]
    for index, (label, row) in enumerate(reader_rows):
        y = 84 + index * 55
        value = 100 * row["accuracy"]
        x = bx0 + (value - 70) / 30 * (bx1 - bx0)
        colour = BLUE if label == "Factorial" else MUTED
        body += [
            text(18, y + 7, label, 23, 700 if label == "Factorial" else 400),
            line(bx0, y, x, y, colour, 2.3),
            marker("circle", x, y, 7.2, colour, colour, 1.2),
            text(x, y - 16, f'{row["correct"]}/72', 22, 700 if label == "Factorial" else 400, colour, "middle"),
        ]
    body.append(text(420, 390, "accuracy on the exact 72-cell route (%)", 21, 400, MUTED, "middle"))

    cx0, cx1, cy0, cy1 = 715, 1160, 72, 310
    for value in (60, 80, 100):
        y = cy1 - (value - 60) / 40 * (cy1 - cy0)
        body += [
            line(cx0, y, cx1, y, GRID, 1, dash="3 4"),
            text(cx0 - 12, y + 7, value, 21, 400, MUTED, "end"),
        ]
    points = []
    for index, distance in enumerate(("1", "2", "4")):
        precision = 100 * distances[distance]["candidate_precision"]
        x = cx0 + index / 2 * (cx1 - cx0)
        y = cy1 - (precision - 60) / 40 * (cy1 - cy0)
        points.append((x, y))
        body += [
            marker("circle", x, y, 7.2, BLUE, BLUE, 1.2),
            text(x, y - 17, f"{precision:.1f}", 23, 700, BLUE, "middle"),
            text(x, 348, f"{distance} tick", 22, 400, MUTED, "middle"),
        ]
    body += [
        f'<polyline points="{" ".join(f"{x},{y}" for x, y in points)}" fill="none" stroke="{BLUE}" stroke-width="2"/>',
        text(938, 390, "precision among validated 4/4 agreements", 21, 400, MUTED, "middle"),
    ]
    save_figure("fig5_reliability_atlas", w, h, "".join(body))


def main():
    evidence = load_json(EVIDENCE)
    make_teaser()
    make_representation_ladder(evidence)
    make_mechanism()
    make_architecture()
    make_reliability_atlas(evidence)
    print(f"Generated five figures under {FIGURES}")


if __name__ == "__main__":
    main()
