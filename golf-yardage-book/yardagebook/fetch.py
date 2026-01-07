"""Fetch course features from OpenStreetMap."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import geopandas as gpd
import osmnx as ox
import yaml

from yardagebook import geom

DEFAULT_TAGS = {
    "golf": True,
    "natural": "water",
    "landuse": "golf_course",
    "leisure": "golf_course",
}


def _parse_tags(raw: str | None) -> dict[str, Any]:
    if not raw:
        return DEFAULT_TAGS
    try:
        if raw.strip().startswith("{"):
            data = json.loads(raw)
        else:
            data = yaml.safe_load(raw)
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        raise ValueError("Failed to parse tags override; provide JSON or YAML dict.") from exc
    if not isinstance(data, dict):
        raise ValueError("Tags override must be a dict.")
    return data


def _buffer_polygon(polygon, buffer_m: float):
    gdf = gpd.GeoDataFrame(geometry=[polygon], crs="EPSG:4326")
    projected = geom.project_to_utm(gdf)
    buffered = projected.geometry.buffer(buffer_m).iloc[0]
    return gpd.GeoSeries([buffered], crs=projected.crs).to_crs("EPSG:4326").iloc[0]


def _place_geometry_to_polygon(geometry, buffer_m: float | None):
    if buffer_m is not None and buffer_m <= 0:
        raise ValueError("buffer_m must be positive when provided.")
    if geometry.geom_type in ("Polygon", "MultiPolygon"):
        if buffer_m:
            return _buffer_polygon(geometry, buffer_m)
        return geometry
    if buffer_m is None:
        buffer_m = 1200
    try:
        return _buffer_polygon(geometry, buffer_m)
    except Exception as exc:  # pragma: no cover - defensive guard
        raise ValueError("Failed to buffer place geometry into a polygon.") from exc


def _sanitize_gdf(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    cleaned = gdf.copy()
    for column in cleaned.columns:
        if column == "geometry":
            continue
        cleaned[column] = cleaned[column].apply(_sanitize_value)
    cleaned = cleaned.reset_index(drop=True)
    if cleaned.crs is None:
        cleaned = cleaned.set_crs("EPSG:4326")
    else:
        cleaned = cleaned.to_crs("EPSG:4326")
    return cleaned


def _sanitize_value(value):
    if isinstance(value, (list, dict)):
        return json.dumps(value)
    return value


def fetch_by_place(place: str, buffer_m: float | None, tags: dict[str, Any]) -> gpd.GeoDataFrame:
    place_gdf = ox.geocode_to_gdf(place, which_result=1)
    if place_gdf.empty:
        raise ValueError("Could not geocode place.")
    polygon = _place_geometry_to_polygon(place_gdf.geometry.iloc[0], buffer_m)
    return ox.features_from_polygon(polygon, tags)


def fetch_by_point(lat: float, lon: float, radius_m: float, tags: dict[str, Any]) -> gpd.GeoDataFrame:
    return ox.features_from_point((lat, lon), tags, dist=radius_m)


def save_geojson(gdf: gpd.GeoDataFrame, output_path: str) -> None:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    sanitized = _sanitize_gdf(gdf)
    sanitized.to_file(output, driver="GeoJSON")


def fetch_course(
    place: str | None,
    lat: float | None,
    lon: float | None,
    radius_m: float | None,
    output: str,
    buffer_m: float | None,
    tags_raw: str | None,
) -> None:
    tags = _parse_tags(tags_raw)
    if place:
        gdf = fetch_by_place(place, buffer_m, tags)
    else:
        if lat is None or lon is None or radius_m is None:
            raise ValueError("Provide --place or --lat/--lon/--radius.")
        gdf = fetch_by_point(lat, lon, radius_m, tags)
    if gdf.empty:
        raise ValueError("No features found for the requested area.")
    save_geojson(gdf, output)


def search_places(query: str, limit: int = 5) -> gpd.GeoDataFrame:
    results = ox.geocode_to_gdf(query)
    if len(results) > limit:
        return results.head(limit)
    return results
