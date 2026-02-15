"""Spatial matching for hole features."""

from __future__ import annotations

from dataclasses import dataclass

import geopandas as gpd
from shapely.geometry import LineString, Point
from shapely.ops import unary_union

from yardagebook import geom
from yardagebook.load import filter_by_tag


@dataclass
class TeeOption:
    label: str
    geometry: object
    yardage_m: float
    project_m: float


@dataclass
class HoleMatch:
    index: int
    ref: str | None
    par: int | None
    line: LineString
    green: object | None
    tee: object | None
    fairway: object | None
    tees: list[TeeOption]
    selected_tee: TeeOption
    bunkers: list
    waters: list
    tee_end: Point
    green_end: Point
    hole_length_m: float
    yardage_m: float
    green_proxy: bool = False
    tee_proxy: bool = False
    fairway_proxy: bool = False


@dataclass
class MatchConfig:
    tee_radius_m: float
    fairway_tol_m: float
    fairway_proxy_halfwidth_m: float
    hazard_tol_m: float
    green_proxy_radius_m: float
    tee_proxy_radius_m: float
    tee_set: str
    tee_label: str | None
    tee_index: int | None


def _nearest_geometry(gdf: gpd.GeoDataFrame, target) -> object | None:
    if gdf.empty:
        return None
    distances = gdf.distance(target)
    idx = distances.idxmin()
    return gdf.loc[idx, "geometry"]


def _value_or_none(row, key: str) -> str | None:
    import pandas as pd
    if key not in row or row[key] in (None, ""):
        return None
    value = row[key]
    # Handle pandas NaN values
    if pd.isna(value):
        return None
    str_value = str(value)
    # Catch string "nan" from float conversion
    if str_value.lower() in ("nan", "none", "null"):
        return None
    return str_value


def _resolve_par(row) -> int | None:
    if "par" not in row or row["par"] in (None, ""):
        return None
    try:
        return int(row["par"])
    except (TypeError, ValueError):
        return None


def _label_from_row(row, fallback: str) -> str:
    for key in ("colour", "color", "name", "ref"):
        value = _value_or_none(row, key)
        if value:
            return value
    return fallback


def _select_tee(tees: list[TeeOption], config: MatchConfig) -> TeeOption:
    if not tees:
        raise ValueError("No tee options available")
    if config.tee_label:
        label_lower = config.tee_label.lower()
        for option in tees:
            if label_lower in option.label.lower():
                return option
    if config.tee_index is not None:
        # Convert 1-based index to 0-based and clamp to valid range
        idx = max(0, min(config.tee_index - 1, len(tees) - 1))
        return tees[idx]
    if config.tee_set == "front":
        return tees[-1]
    if config.tee_set == "middle":
        return tees[len(tees) // 2]
    return tees[0]


def _ensure_line_direction(line: LineString, tee_end: Point) -> LineString:
    start = Point(line.coords[0])
    end = Point(line.coords[-1])
    if start.distance(tee_end) <= end.distance(tee_end):
        return line
    return LineString(list(line.coords)[::-1])


def match_holes(features: gpd.GeoDataFrame, config: MatchConfig) -> list[HoleMatch]:
    holes = filter_by_tag(features, golf="hole")
    greens = filter_by_tag(features, golf="green")
    tees = filter_by_tag(features, golf="tee")
    fairways = filter_by_tag(features, golf="fairway")
    bunkers = filter_by_tag(features, golf="bunker")
    waters = features
    if "natural" in features.columns:
        waters = features[features["natural"] == "water"]
    else:
        waters = features.iloc[0:0]

    matches: list[HoleMatch] = []
    for _, row in holes.iterrows():
        line = row.geometry
        if not isinstance(line, LineString):
            continue
        tee_end, green_end = geom.line_endpoints(line)
        green = _nearest_geometry(greens, line)
        green_proxy = False
        if green is None:
            green = green_end.buffer(config.green_proxy_radius_m)
            green_proxy = True
            green_centroid = green.centroid
        else:
            green_centroid = green.centroid
            if green_centroid.distance(tee_end) < green_centroid.distance(green_end):
                tee_end, green_end = green_end, tee_end
        line = _ensure_line_direction(line, tee_end)
        tee_candidates = tees[tees.distance(tee_end) <= config.tee_radius_m]
        tee_proxy = False
        tee_options: list[TeeOption] = []
        if tee_candidates.empty:
            tee = tee_end.buffer(config.tee_proxy_radius_m)
            tee_proxy = True
            tee_options.append(
                TeeOption(
                    label="Tee (proxy)",
                    geometry=tee,
                    yardage_m=line.length,
                    project_m=0.0,
                )
            )
        else:
            for idx, tee_row in tee_candidates.iterrows():
                tee_geom = tee_row.geometry
                tee_pt = tee_geom.centroid
                proj_m = line.project(tee_pt)
                yardage_m = max(line.length - proj_m, 0.0)
                label = _label_from_row(tee_row, f"Tee {len(tee_options) + 1}")
                tee_options.append(
                    TeeOption(
                        label=label,
                        geometry=tee_geom,
                        yardage_m=yardage_m,
                        project_m=proj_m,
                    )
                )
            tee_options.sort(key=lambda option: option.yardage_m, reverse=True)
            tee = tee_options[0].geometry
        selected_tee = _select_tee(tee_options, config)
        tee = selected_tee.geometry
        fairway_candidates = fairways[fairways.distance(line) <= config.fairway_tol_m]
        fairway_proxy = False
        if fairway_candidates.empty:
            fairway = line.buffer(config.fairway_proxy_halfwidth_m, cap_style=2)
            fairway_proxy = True
        else:
            fairway = unary_union(fairway_candidates.geometry)
        bunkers_near = bunkers[bunkers.distance(line) <= config.hazard_tol_m].geometry.tolist()
        waters_near = waters[waters.distance(line) <= config.hazard_tol_m].geometry.tolist()
        hole_length_m = line.length
        yardage_m = selected_tee.yardage_m
        matches.append(
            HoleMatch(
                index=len(matches) + 1,
                ref=_value_or_none(row, "ref"),
                par=_resolve_par(row),
                line=line,
                green=green,
                tee=tee,
                fairway=fairway,
                tees=tee_options,
                selected_tee=selected_tee,
                bunkers=bunkers_near,
                waters=waters_near,
                tee_end=tee_end,
                green_end=green_end,
                hole_length_m=hole_length_m,
                yardage_m=yardage_m,
                green_proxy=green_proxy,
                tee_proxy=tee_proxy,
                fairway_proxy=fairway_proxy,
            )
        )
    return matches
