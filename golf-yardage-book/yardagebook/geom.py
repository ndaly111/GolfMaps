"""Geometry utilities for yardage book rendering."""

from __future__ import annotations

import math

import geopandas as gpd
from pyproj import CRS
from shapely.affinity import rotate
from shapely.geometry import LineString, Point
from shapely.ops import unary_union

YARDS_PER_METER = 1.09361


def utm_crs_from_lonlat(lon: float, lat: float) -> CRS:
    zone = int((lon + 180) / 6) + 1
    is_northern = lat >= 0
    return CRS.from_dict(
        {
            "proj": "utm",
            "zone": zone,
            "south": not is_northern,
        }
    )


def project_to_utm(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Project GeoDataFrame to an appropriate UTM CRS."""
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    centroid = gdf.to_crs("EPSG:4326").unary_union.centroid
    utm_crs = utm_crs_from_lonlat(centroid.x, centroid.y)
    return gdf.to_crs(utm_crs)


def to_yards(meters: float) -> float:
    return meters * YARDS_PER_METER


def line_endpoints(line: LineString) -> tuple[Point, Point]:
    coords = list(line.coords)
    return Point(coords[0]), Point(coords[-1])


def bearing_radians(start: Point, end: Point) -> float:
    dx = end.x - start.x
    dy = end.y - start.y
    return math.atan2(dx, dy)


def rotate_geometry(geometry, angle_radians: float, origin: Point):
    return rotate(geometry, math.degrees(angle_radians), origin=origin)


def orient_hole(geoms: dict, tee_end: Point, green_end: Point) -> dict:
    """Rotate geometries so tee->green aligns with +Y axis."""
    origin = geoms.get("origin", None)
    if origin is None:
        origin = unary_union([tee_end, green_end]).centroid
    angle = -bearing_radians(tee_end, green_end)
    rotated = {}
    for key, value in geoms.items():
        if key == "origin":
            rotated[key] = origin
            continue
        if value is None:
            rotated[key] = None
            continue
        if isinstance(value, list):
            rotated[key] = [rotate_geometry(v, angle, origin) for v in value]
        else:
            rotated[key] = rotate_geometry(value, angle, origin)
    rotated["origin"] = origin
    return rotated


def buffered_union(geoms):
    if not geoms:
        return None
    return unary_union(geoms)


def interpolate_points(line: LineString, step_m: float) -> list[Point]:
    points = []
    distance = step_m
    while distance < line.length:
        points.append(line.interpolate(distance))
        distance += step_m
    return points
