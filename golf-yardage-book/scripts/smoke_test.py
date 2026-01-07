"""Offline smoke test for yardage book generation."""

from __future__ import annotations

import tempfile
from pathlib import Path

import geopandas as gpd
from shapely.geometry import LineString, Point, Polygon

from yardagebook.book import build_book, load_config, merge_config
from yardagebook.fetch import _place_geometry_to_polygon


def _make_geojson(path: Path) -> None:
    base_lon, base_lat = (-122.0, 37.0)
    hole_line = LineString([(base_lon, base_lat), (base_lon, base_lat + 0.0018)])
    green = Polygon(
        [
            (base_lon - 0.0001, base_lat + 0.0017),
            (base_lon + 0.0001, base_lat + 0.0017),
            (base_lon + 0.0001, base_lat + 0.0019),
            (base_lon - 0.0001, base_lat + 0.0019),
        ]
    )
    fairway = Polygon(
        [
            (base_lon - 0.0002, base_lat - 0.0001),
            (base_lon + 0.0002, base_lat - 0.0001),
            (base_lon + 0.0002, base_lat + 0.0020),
            (base_lon - 0.0002, base_lat + 0.0020),
        ]
    )
    tees = [
        (Point(base_lon, base_lat), {"golf": "tee", "name": "Blue"}),
        (Point(base_lon, base_lat - 0.0001), {"golf": "tee", "name": "White"}),
        (Point(base_lon, base_lat - 0.0002), {"golf": "tee", "name": "Red"}),
    ]

    records = [
        {"golf": "hole", "ref": "1", "par": 4, "geometry": hole_line},
        {"golf": "green", "geometry": green},
        {"golf": "fairway", "geometry": fairway},
    ]
    for tee_geom, props in tees:
        record = {"geometry": tee_geom}
        record.update(props)
        records.append(record)

    gdf = gpd.GeoDataFrame(records, crs="EPSG:4326")
    gdf.to_file(path, driver="GeoJSON")


def _run_build(input_path: Path, output_path: Path, overrides: dict) -> None:
    config = merge_config(load_config(None), overrides)
    build_book(
        input_path=str(input_path),
        course="Test Course",
        output_path=str(output_path),
        config=config,
        two_up=config["tolerances"]["two_up"],
        debug=False,
    )
    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError(f"Output PDF was not created: {output_path}")


def _run_fetch_geometry_checks() -> None:
    point = Point(-122.0, 37.0)
    polygon = Polygon(
        [
            (-122.001, 37.0),
            (-121.999, 37.0),
            (-121.999, 37.001),
            (-122.001, 37.001),
        ]
    )
    assert _place_geometry_to_polygon(point, None).geom_type in ("Polygon", "MultiPolygon")
    assert _place_geometry_to_polygon(point, 800).geom_type in ("Polygon", "MultiPolygon")
    assert _place_geometry_to_polygon(polygon, None).geom_type in ("Polygon", "MultiPolygon")


def main() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        input_path = tmp_path / "course.geojson"
        _make_geojson(input_path)
        _run_fetch_geometry_checks()

        pocket_output = tmp_path / "pocket.pdf"
        _run_build(
            input_path,
            pocket_output,
            {
                "page": {"paper": "pocket"},
                "tolerances": {"duplex": True, "two_up": False},
            },
        )

        legal_output = tmp_path / "legal.pdf"
        _run_build(
            input_path,
            legal_output,
            {
                "page": {"paper": "legal"},
                "tolerances": {"duplex": False, "two_up": True},
            },
        )


if __name__ == "__main__":
    main()
