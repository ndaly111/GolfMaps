"""PDF assembly for yardage books."""

from __future__ import annotations

from pathlib import Path
import importlib.resources as resources

import matplotlib

matplotlib.use("Agg")

import yaml
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.pyplot as plt

from yardagebook import geom, render
from yardagebook.load import load_course
from yardagebook.match import MatchConfig, match_holes


def load_config(path: str | None) -> dict:
    if path:
        with open(path, "r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}
    default_path = resources.files("yardagebook").joinpath("configs/default.yml")
    with default_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def merge_config(defaults: dict, overrides: dict) -> dict:
    merged = defaults.copy()
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_config(merged[key], value)
        else:
            merged[key] = value
    return merged


def build_book(
    input_path: str,
    course: str,
    output_path: str,
    config: dict,
    two_up: bool,
    debug: bool,
) -> None:
    raw = load_course(input_path)
    projected = geom.project_to_utm(raw)
    match_config = MatchConfig(
        tee_radius_m=config["tolerances"]["tee_radius_m"],
        fairway_tol_m=config["tolerances"]["fairway_tol_m"],
        fairway_proxy_halfwidth_m=config["tolerances"]["fairway_proxy_halfwidth_m"],
        hazard_tol_m=config["tolerances"]["hazard_tol_m"],
        green_proxy_radius_m=config["tolerances"]["green_proxy_radius_m"],
        tee_proxy_radius_m=config["tolerances"]["tee_proxy_radius_m"],
        tee_set=config["tolerances"]["tee_set"],
        tee_label=config["tolerances"]["tee_label"],
        tee_index=config["tolerances"]["tee_index"],
    )
    holes = match_holes(projected, match_config)
    if not holes:
        raise ValueError(
            "No golf=hole LineStrings found. Provide hole centerlines via OSM or "
            "digitize them in QGIS and export GeoJSON."
        )
    holes = _sorted_holes(holes)
    if debug:
        print(f"Holes found: {len(holes)}")
        for hole in holes:
            yardage = round(geom.to_yards(hole.yardage_m), config["tolerances"]["yardage_round"])
            hole_label = hole.ref or hole.index
            par = hole.par if hole.par is not None else "?"
            tee_labels = [
                f"{tee.label}: {round(geom.to_yards(tee.yardage_m), config['tolerances']['yardage_round'])}"
                for tee in hole.tees
            ]
            warnings = []
            if hole.green_proxy:
                warnings.append("green proxy")
            if hole.tee_proxy:
                warnings.append("tee proxy")
            if hole.fairway_proxy:
                warnings.append("fairway proxy")
            warn_text = f" ({', '.join(warnings)})" if warnings else ""
            print(
                f"Hole {hole_label} (Par {par}): {yardage} yds "
                f"[{hole.selected_tee.label}] {', '.join(tee_labels)}{warn_text}"
            )

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with PdfPages(output) as pdf:
        cover = render.render_cover(course, config)
        pdf.savefig(cover)
        plt.close(cover)
        notes = render.render_notes(config)
        pdf.savefig(notes)
        plt.close(notes)
        legend = render.render_legend(config)
        pdf.savefig(legend)
        plt.close(legend)
        for hole in holes:
            for fig in render.render_hole_pages(hole, config, two_up):
                pdf.savefig(fig)
                plt.close(fig)


def _sorted_holes(holes: list) -> list:
    ordered = []
    for idx, hole in enumerate(holes):
        ref_value = None
        if hole.ref is not None and str(hole.ref).isdigit():
            ref_value = int(hole.ref)
        ordered.append((ref_value, idx, hole))
    ordered.sort(key=lambda item: (item[0] is None, item[0] or 0, item[1]))
    sorted_holes = [item[2] for item in ordered]
    for idx, hole in enumerate(sorted_holes, start=1):
        hole.index = idx
    return sorted_holes


def summarize_tees(input_path: str, config: dict) -> list[str]:
    raw = load_course(input_path)
    projected = geom.project_to_utm(raw)
    match_config = MatchConfig(
        tee_radius_m=config["tolerances"]["tee_radius_m"],
        fairway_tol_m=config["tolerances"]["fairway_tol_m"],
        fairway_proxy_halfwidth_m=config["tolerances"]["fairway_proxy_halfwidth_m"],
        hazard_tol_m=config["tolerances"]["hazard_tol_m"],
        green_proxy_radius_m=config["tolerances"]["green_proxy_radius_m"],
        tee_proxy_radius_m=config["tolerances"]["tee_proxy_radius_m"],
        tee_set=config["tolerances"]["tee_set"],
        tee_label=config["tolerances"]["tee_label"],
        tee_index=config["tolerances"]["tee_index"],
    )
    holes = _sorted_holes(match_holes(projected, match_config))
    lines: list[str] = []
    for hole in holes:
        hole_label = hole.ref or hole.index
        selected = hole.selected_tee.label
        tee_text = ", ".join(
            f"{tee.label}: {round(geom.to_yards(tee.yardage_m), config['tolerances']['yardage_round'])}"
            for tee in hole.tees
        )
        lines.append(f"Hole {hole_label} [{selected}] {tee_text}")
    return lines
