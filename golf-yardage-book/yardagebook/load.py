"""Load and normalize GeoJSON course data."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
from shapely.geometry import LineString, MultiLineString
from shapely.ops import linemerge


def _normalize_line(geometry):
    if isinstance(geometry, LineString):
        return geometry
    if isinstance(geometry, MultiLineString):
        merged = linemerge(geometry)
        if isinstance(merged, LineString):
            return merged
    return geometry


def load_course(path: str | Path) -> gpd.GeoDataFrame:
    """Load a GeoJSON file into a GeoDataFrame."""
    gdf = gpd.read_file(path)
    if gdf.empty:
        raise ValueError("GeoJSON contained no features")
    gdf = gdf.copy()
    gdf["geometry"] = gdf["geometry"].apply(_normalize_line)
    return gdf


def filter_by_tag(gdf: gpd.GeoDataFrame, **tags) -> gpd.GeoDataFrame:
    """Filter features by tag values if present."""
    filtered = gdf
    for key, value in tags.items():
        if key not in filtered.columns:
            return filtered.iloc[0:0]
        filtered = filtered[filtered[key] == value]
    return filtered
