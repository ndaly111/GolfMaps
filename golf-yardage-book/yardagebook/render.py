"""Rendering utilities for yardage book pages."""

from __future__ import annotations

import math

import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon, Rectangle
from shapely.geometry import LineString, MultiLineString, MultiPoint, MultiPolygon, Point, Polygon

from yardagebook import geom


def _page_size(config: dict) -> list[float]:
    paper = config["page"].get("paper", "pocket")
    if paper == "legal":
        return config["page"]["legal_size"]
    if paper == "letter":
        return config["page"]["letter_size"]
    return config["page"]["pocket_size"]


def _plot_polygon(ax, polygon: Polygon, **kwargs):
    exterior = list(polygon.exterior.coords)
    ax.add_patch(MplPolygon(exterior, closed=True, **kwargs))
    for interior in polygon.interiors:
        coords = list(interior.coords)
        ax.add_patch(MplPolygon(coords, closed=True, fill=False, edgecolor="white", linewidth=0.5))


def _plot_geometry(ax, geometry, **kwargs):
    if geometry is None:
        return
    if isinstance(geometry, Polygon):
        _plot_polygon(ax, geometry, **kwargs)
    elif isinstance(geometry, MultiPolygon):
        for poly in geometry.geoms:
            _plot_polygon(ax, poly, **kwargs)
    elif isinstance(geometry, LineString):
        xs, ys = geometry.xy
        ax.plot(xs, ys, **kwargs)
    elif isinstance(geometry, MultiLineString):
        for line in geometry.geoms:
            xs, ys = line.xy
            ax.plot(xs, ys, **kwargs)
    elif isinstance(geometry, Point):
        _scatter_points(ax, [geometry], **kwargs)
    elif isinstance(geometry, MultiPoint):
        _scatter_points(ax, list(geometry.geoms), **kwargs)


def _scatter_points(ax, points: list[Point], **kwargs):
    facecolor = kwargs.pop("facecolor", kwargs.pop("color", "#000000"))
    edgecolor = kwargs.pop("edgecolor", None)
    linewidth = kwargs.pop("linewidth", None)
    alpha = kwargs.pop("alpha", None)
    xs = [point.x for point in points]
    ys = [point.y for point in points]
    ax.scatter(
        xs,
        ys,
        c=facecolor,
        edgecolors=edgecolor,
        linewidths=linewidth,
        alpha=alpha,
        s=20,
    )


def _set_bounds(ax, geometry, margin_m: float):
    minx, miny, maxx, maxy = geometry.bounds
    ax.set_xlim(minx - margin_m, maxx + margin_m)
    ax.set_ylim(miny - margin_m, maxy + margin_m)


def _draw_grid(ax, bounds, step_m: float, color: str):
    minx, miny, maxx, maxy = bounds
    x = math.floor(minx / step_m) * step_m
    while x <= maxx:
        ax.plot([x, x], [miny, maxy], color=color, linewidth=0.4)
        x += step_m
    y = math.floor(miny / step_m) * step_m
    while y <= maxy:
        ax.plot([minx, maxx], [y, y], color=color, linewidth=0.4)
        y += step_m


def _draw_drive_distances(
    ax,
    tee_point: Point,
    green_point: Point,
    distances_yards: list[int],
    color: str,
    font_size: int = 7,
):
    """Draw straight-line carry distances from tee (how golfers actually measure)."""
    from shapely.geometry import Point

    # Calculate direction from tee to green
    dx = green_point.x - tee_point.x
    dy = green_point.y - tee_point.y
    total_dist = ((dx**2 + dy**2)**0.5)

    if total_dist < 1:
        return

    # Unit vector toward green
    ux = dx / total_dist
    uy = dy / total_dist

    # Mark each drive distance as straight-line carry from tee
    for yards in distances_yards:
        carry_m = yards / geom.YARDS_PER_METER
        # Point at straight-line distance from tee toward green
        marker_x = tee_point.x + (ux * carry_m)
        marker_y = tee_point.y + (uy * carry_m)

        ax.plot(marker_x, marker_y, marker="o", color=color, markersize=4, zorder=5)
        ax.text(
            marker_x + 3, marker_y + 3,
            f"{yards}",
            fontsize=font_size,
            color=color,
            weight="bold",
            zorder=5
        )


def _draw_notes_table(ax, origin, size, font_size: int):
    x0, y0 = origin
    width, height = size
    ax.add_patch(
        Rectangle(
            (x0, y0),
            width,
            height,
            fill=False,
            linewidth=0.7,
            transform=ax.transAxes,
        )
    )
    for i in range(1, 4):
        ax.plot(
            [x0, x0 + width],
            [y0 + i * height / 4, y0 + i * height / 4],
            color="black",
            linewidth=0.5,
            transform=ax.transAxes,
        )
    ax.text(
        x0 + 0.01,
        y0 + height + 0.01,
        "Notes",
        fontsize=font_size,
        weight="bold",
        transform=ax.transAxes,
    )


def _draw_tee_table(ax, hole, config: dict, max_entries: int = 5):
    x0, y0 = 0.02, 0.05
    width, height = 0.3, 0.2
    ax.add_patch(
        Rectangle(
            (x0, y0),
            width,
            height,
            fill=False,
            linewidth=0.7,
            transform=ax.transAxes,
        )
    )
    ax.text(
        x0 + 0.01,
        y0 + height + 0.01,
        "Tee Yardages",
        fontsize=config["page"]["body_size"],
        weight="bold",
        transform=ax.transAxes,
    )
    entries = hole.tees[:max_entries]
    line_height = height / max(len(entries) + (1 if len(hole.tees) > max_entries else 0), 1)
    for idx, tee_option in enumerate(entries):
        yardage = round(geom.to_yards(tee_option.yardage_m), config["tolerances"]["yardage_round"])
        marker = "*" if tee_option == hole.selected_tee else ""
        ax.text(
            x0 + 0.01,
            y0 + height - (idx + 1) * line_height + 0.01,
            f"{marker}{tee_option.label}: {yardage}",
            fontsize=config["page"]["body_size"],
            transform=ax.transAxes,
        )
    if len(hole.tees) > max_entries:
        ax.text(
            x0 + 0.01,
            y0 + 0.01,
            f"+{len(hole.tees) - max_entries} more",
            fontsize=config["page"]["body_size"],
            transform=ax.transAxes,
        )


def _header_text(hole, config: dict) -> str:
    yardage = round(geom.to_yards(hole.yardage_m), config["tolerances"]["yardage_round"])
    hole_label = hole.ref or hole.index
    par_text = f"Par {hole.par}" if hole.par is not None else "Par"
    return f"Hole {hole_label} — {par_text} — {yardage} yds"


def _prepare_geoms(hole) -> dict:
    return geom.orient_hole(
        {
            "line": hole.line,
            "green": hole.green,
            "fairway": hole.fairway,
            "bunkers": hole.bunkers,
            "waters": hole.waters,
            "tees": [tee.geometry for tee in hole.tees],
        },
        hole.tee_end,
        hole.green_end,
    )


def _render_fairway_view(ax, hole, geoms: dict, config: dict):
    ax.set_aspect("equal")
    ax.axis("off")
    # Base view bounds on playing corridor only (line + fairway + green + tees)
    # Don't include water/bunkers as they can be huge and zoom out too far
    bounds_parts = [geoms["line"], geoms["green"], geoms["fairway"]]
    bounds_parts += geoms["tees"]
    bounds_geom = geom.buffered_union([g for g in bounds_parts if g is not None])
    if bounds_geom is None:
        return
    _set_bounds(ax, bounds_geom, config["tolerances"]["fairway_margin_m"])
    _plot_geometry(ax, geoms["fairway"], facecolor=config["colors"]["fairway"], edgecolor="none")
    _plot_geometry(ax, geoms["green"], facecolor=config["colors"]["green"], edgecolor="none")
    selected_idx = hole.tees.index(hole.selected_tee)
    for idx, tee_geom in enumerate(geoms["tees"]):
        alpha = 0.9 if idx == selected_idx else 0.35
        edgecolor = config["colors"]["line"] if idx == selected_idx else "none"
        _plot_geometry(
            ax,
            tee_geom,
            facecolor=config["colors"]["tee"],
            edgecolor=edgecolor,
            linewidth=0.6,
            alpha=alpha,
        )
    for bunker in geoms["bunkers"]:
        _plot_geometry(ax, bunker, facecolor=config["colors"]["bunker"], edgecolor="none")
    for water in geoms["waters"]:
        _plot_geometry(ax, water, facecolor=config["colors"]["water"], edgecolor="none")
    _plot_geometry(ax, geoms["line"], color=config["colors"]["line"], linewidth=1.0)

    # Draw drive distance markers (straight-line carry from tee)
    line_coords = list(geoms["line"].coords)
    tee_point = Point(line_coords[0])
    green_point = Point(line_coords[-1])
    _draw_drive_distances(
        ax,
        tee_point,
        green_point,
        [200, 250, 275],  # Key drive distances for golfers
        config["colors"]["marker"],
        font_size=config["page"]["marker_font_size"],
    )
    ax.text(
        0.02,
        0.97,
        _header_text(hole, config),
        transform=ax.transAxes,
        fontsize=config["page"]["header_size"],
        va="top",
        ha="left",
    )
    _draw_tee_table(ax, hole, config)


def _render_green_view(ax, hole, geoms: dict, config: dict):
    ax.set_aspect("equal")
    ax.axis("off")
    if geoms["green"] is None:
        return
    _set_bounds(ax, geoms["green"], config["tolerances"]["green_margin_m"])
    _plot_geometry(
        ax,
        geoms["green"],
        facecolor=config["colors"]["green"],
        edgecolor=config["colors"]["line"],
        linewidth=0.8,
    )
    for bunker in geoms["bunkers"]:
        if bunker.distance(geoms["green"]) > config["tolerances"]["green_margin_m"]:
            continue
        _plot_geometry(ax, bunker, facecolor=config["colors"]["bunker"], edgecolor="none")
    bounds = geoms["green"].buffer(config["tolerances"]["green_margin_m"]).bounds
    _draw_grid(
        ax,
        bounds,
        config["tolerances"]["grid_step_yards"] / geom.YARDS_PER_METER,
        config["colors"]["grid"],
    )
    ax.text(
        0.02,
        0.97,
        _header_text(hole, config),
        transform=ax.transAxes,
        fontsize=config["page"]["header_size"],
        va="top",
        ha="left",
    )
    _draw_notes_table(ax, (0.65, 0.05), (0.3, 0.18), config["page"]["body_size"])


def render_two_up(draw_fn, config: dict):
    fig, axes = plt.subplots(1, 2, figsize=_page_size(config))
    for ax in axes:
        ax.axis("off")
        draw_fn(ax)
    fig.subplots_adjust(wspace=0.05)
    return fig


def render_cover(course: str, config: dict):
    def _draw(ax):
        ax.text(0.5, 0.6, course, fontsize=28, ha="center", va="center", transform=ax.transAxes)
        ax.text(0.5, 0.4, "Yardage Book", fontsize=16, ha="center", va="center", transform=ax.transAxes)

    if config["page"].get("paper") == "legal" and config["tolerances"].get("two_up"):
        return render_two_up(_draw, config)
    fig, ax = plt.subplots(figsize=_page_size(config))
    ax.axis("off")
    _draw(ax)
    return fig


def render_notes(config: dict):
    def _draw(ax):
        ax.text(0.5, 0.85, "Notes & Club Carry", fontsize=18, ha="center", transform=ax.transAxes)
        rows = ["Club", "Carry (yds)"]
        table_data = [["", ""] for _ in range(10)]
        ax.table(cellText=table_data, colLabels=rows, loc="center", cellLoc="center", colWidths=[0.3, 0.3])

    if config["page"].get("paper") == "legal" and config["tolerances"].get("two_up"):
        return render_two_up(_draw, config)
    fig, ax = plt.subplots(figsize=_page_size(config))
    ax.axis("off")
    _draw(ax)
    return fig


def render_legend(config: dict):
    def _draw(ax):
        ax.text(0.5, 0.85, "Legend", fontsize=18, ha="center", transform=ax.transAxes)
        items = [
            ("Fairway", config["colors"]["fairway"]),
            ("Green", config["colors"]["green"]),
            ("Tee", config["colors"]["tee"]),
            ("Bunker", config["colors"]["bunker"]),
            ("Water", config["colors"]["water"]),
        ]
        for idx, (label, color) in enumerate(items):
            ax.add_patch(Rectangle((0.2, 0.65 - idx * 0.08), 0.05, 0.04, color=color, transform=ax.transAxes))
            ax.text(0.27, 0.67 - idx * 0.08, label, fontsize=12, transform=ax.transAxes, va="center")
        ax.text(0.6, 0.65, "FAIRWAY VIEW LEGEND", fontsize=10, weight="bold", transform=ax.transAxes)
        ax.text(
            0.6,
            0.6,
            "- Yardage markers every step\n- Selected tee highlighted\n- Hazards shaded",
            fontsize=9,
            transform=ax.transAxes,
            va="top",
        )
        ax.text(0.6, 0.42, "GREEN VIEW LEGEND", fontsize=10, weight="bold", transform=ax.transAxes)
        ax.text(
            0.6,
            0.37,
            "- Grid shows yards\n- Notes area for pin\n- Nearby bunkers shown",
            fontsize=9,
            transform=ax.transAxes,
            va="top",
        )
        ax.text(
            0.5,
            0.08,
            "Map data © OpenStreetMap contributors (ODbL)",
            fontsize=8,
            ha="center",
            transform=ax.transAxes,
        )

    if config["page"].get("paper") == "legal" and config["tolerances"].get("two_up"):
        return render_two_up(_draw, config)
    fig, ax = plt.subplots(figsize=_page_size(config))
    ax.axis("off")
    _draw(ax)
    return fig


def render_hole_pages(hole, config: dict, two_up: bool) -> list:
    paper = config["page"].get("paper", "pocket")
    duplex = config["tolerances"].get("duplex", False)
    geoms = _prepare_geoms(hole)
    pages: list = []
    if paper == "pocket" and duplex:
        fig, ax = plt.subplots(1, 1, figsize=_page_size(config))
        _render_fairway_view(ax, hole, geoms, config)
        pages.append(fig)
        fig, ax = plt.subplots(1, 1, figsize=_page_size(config))
        _render_green_view(ax, hole, geoms, config)
        pages.append(fig)
        return pages

    rows = 2
    cols = 2 if two_up else 1
    fig, axes = plt.subplots(rows, cols, figsize=_page_size(config))
    axes_list = list(axes.ravel()) if hasattr(axes, "ravel") else [axes]
    for col in range(cols):
        green_ax = axes_list[col]
        fairway_ax = axes_list[col + cols]
        _render_green_view(green_ax, hole, geoms, config)
        _render_fairway_view(fairway_ax, hole, geoms, config)
    fig.subplots_adjust(hspace=0.08, wspace=0.08)
    pages.append(fig)
    return pages
