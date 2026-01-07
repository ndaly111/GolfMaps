"""Command line interface for yardage book generation."""

from __future__ import annotations

import argparse
from pathlib import Path

from yardagebook.book import build_book, load_config, merge_config, summarize_tees
from yardagebook.fetch import fetch_course, search_places
from yardagebook.load import load_course, filter_by_tag


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate golf yardage book PDFs.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate", help="Generate a yardage book PDF")
    generate.add_argument("--input", required=True, help="Input GeoJSON file")
    generate.add_argument("--course", required=True, help="Course name")
    generate.add_argument("--output", required=True, help="Output PDF path")
    generate.add_argument("--config", help="Config YAML path")
    generate.add_argument("--paper", choices=["pocket", "legal", "letter"], help="Paper size preset")
    generate.add_argument("--pocket-size", help="Override pocket size like 3.5x5")
    generate.add_argument("--two-up", dest="two_up", action="store_true", help="Enable two-up layout")
    generate.add_argument("--no-two-up", dest="two_up", action="store_false", help="Disable two-up layout")
    generate.add_argument("--duplex", dest="duplex", action="store_true", help="Enable duplex mode")
    generate.add_argument("--no-duplex", dest="duplex", action="store_false", help="Disable duplex mode")
    generate.set_defaults(two_up=None, duplex=None)
    generate.add_argument("--marker-step", type=float, help="Marker step in yards")
    generate.add_argument("--grid-step", type=float, help="Grid step in yards")
    generate.add_argument("--tee-radius", type=float, help="Tee search radius in meters")
    generate.add_argument("--fairway-tol", type=float, help="Fairway tolerance in meters")
    generate.add_argument("--tee-set", choices=["back", "middle", "front"], help="Select tee set")
    generate.add_argument("--tee-index", type=int, help="Select tee by index (1-based)")
    generate.add_argument("--tee-label", help="Select tee by label substring")
    generate.add_argument("--debug", action="store_true", help="Print matching debug info")

    fetch = subparsers.add_parser("fetch", help="Fetch course data from OpenStreetMap")
    fetch.add_argument("--place", help="Place name to geocode")
    fetch.add_argument("--lat", type=float, help="Latitude fallback")
    fetch.add_argument("--lon", type=float, help="Longitude fallback")
    fetch.add_argument("--radius", type=float, help="Search radius in meters")
    fetch.add_argument("--output", required=True, help="Output GeoJSON path")
    fetch.add_argument("--buffer-m", type=float, help="Buffer distance around place polygon")
    fetch.add_argument("--tags", help="Optional JSON/YAML dict of tags for OSMnx")

    tees = subparsers.add_parser("tees", help="List tee yardages for each hole")
    tees.add_argument("--input", required=True, help="Input GeoJSON file")
    tees.add_argument("--config", help="Config YAML path")
    tees.add_argument("--tee-set", choices=["back", "middle", "front"], help="Select tee set")
    tees.add_argument("--tee-index", type=int, help="Select tee by index (1-based)")
    tees.add_argument("--tee-label", help="Select tee by label substring")

    build = subparsers.add_parser("build", help="Fetch and generate a yardage book")
    build.add_argument("--place", help="Place name to geocode")
    build.add_argument("--course", required=True, help="Course name")
    build.add_argument("--output", required=True, help="Output PDF path")
    build.add_argument("--cache-path", help="Optional GeoJSON cache path")
    build.add_argument("--buffer-m", type=float, help="Buffer distance around place polygon")
    build.add_argument("--lat", type=float, help="Latitude fallback")
    build.add_argument("--lon", type=float, help="Longitude fallback")
    build.add_argument("--radius", type=float, help="Search radius in meters")
    build.add_argument("--tags", help="Optional JSON/YAML dict of tags for OSMnx")
    build.add_argument("--paper", choices=["pocket", "legal", "letter"], help="Paper size preset")
    build.add_argument("--pocket-size", help="Override pocket size like 3.5x5")
    build.add_argument("--two-up", dest="two_up", action="store_true", help="Enable two-up layout")
    build.add_argument("--no-two-up", dest="two_up", action="store_false", help="Disable two-up layout")
    build.add_argument("--duplex", dest="duplex", action="store_true", help="Enable duplex mode")
    build.add_argument("--no-duplex", dest="duplex", action="store_false", help="Disable duplex mode")
    build.set_defaults(two_up=None, duplex=None)
    build.add_argument("--tee-set", choices=["back", "middle", "front"], help="Select tee set")
    build.add_argument("--tee-index", type=int, help="Select tee by index (1-based)")
    build.add_argument("--tee-label", help="Select tee by label substring")
    build.add_argument("--debug", action="store_true", help="Print matching debug info")

    search = subparsers.add_parser("search", help="Search for places via OpenStreetMap")
    search.add_argument("--query", required=True, help="Place search query")
    search.add_argument("--limit", type=int, default=5, help="Max results to display")

    validate = subparsers.add_parser("validate", help="Validate input GeoJSON features")
    validate.add_argument("--input", required=True, help="Input GeoJSON file")
    return parser.parse_args()


def _parse_size(size_text: str) -> list[float]:
    parts = size_text.lower().replace("x", " ").split()
    if len(parts) != 2:
        raise ValueError("Size must be formatted like 3.5x5")
    return [float(parts[0]), float(parts[1])]


def _apply_overrides(config: dict, args: argparse.Namespace) -> dict:
    overrides = {"tolerances": {}}
    if getattr(args, "paper", None) is not None:
        overrides.setdefault("page", {})["paper"] = args.paper
        if args.paper == "legal" and getattr(args, "two_up", None) is None:
            overrides["tolerances"]["two_up"] = True
        if args.paper == "pocket" and getattr(args, "duplex", None) is None:
            overrides["tolerances"]["duplex"] = True
        if args.paper == "legal" and getattr(args, "duplex", None) is None:
            overrides["tolerances"]["duplex"] = False
    if getattr(args, "pocket_size", None):
        overrides.setdefault("page", {})["pocket_size"] = _parse_size(args.pocket_size)
    if getattr(args, "marker_step", None) is not None:
        overrides["tolerances"]["marker_step_yards"] = args.marker_step
    if getattr(args, "grid_step", None) is not None:
        overrides["tolerances"]["grid_step_yards"] = args.grid_step
    if getattr(args, "tee_radius", None) is not None:
        overrides["tolerances"]["tee_radius_m"] = args.tee_radius
    if getattr(args, "fairway_tol", None) is not None:
        overrides["tolerances"]["fairway_tol_m"] = args.fairway_tol
    if getattr(args, "two_up", None) is not None:
        overrides["tolerances"]["two_up"] = args.two_up
    if getattr(args, "duplex", None) is not None:
        overrides["tolerances"]["duplex"] = args.duplex
    if getattr(args, "tee_set", None) is not None:
        overrides["tolerances"]["tee_set"] = args.tee_set
    if getattr(args, "tee_index", None) is not None:
        overrides["tolerances"]["tee_index"] = args.tee_index
    if getattr(args, "tee_label", None) is not None:
        overrides["tolerances"]["tee_label"] = args.tee_label
    return merge_config(config, overrides)


def _fetch_error(exc: Exception) -> SystemExit:
    return SystemExit(
        "Fetch failed: "
        f"{exc}. Try providing --place or --lat/--lon/--radius, "
        "or export GeoJSON from QGIS."
    )


def main() -> None:
    args = _parse_args()
    if args.command == "generate":
        config_path = Path(args.config) if args.config else None
        base_config = load_config(str(config_path)) if config_path else load_config(None)
        config = _apply_overrides(base_config, args)
        two_up = config["tolerances"].get("two_up", True) if args.two_up is None else args.two_up
        build_book(
            input_path=args.input,
            course=args.course,
            output_path=args.output,
            config=config,
            two_up=two_up,
            debug=args.debug,
        )
    if args.command == "fetch":
        try:
            fetch_course(
                place=args.place,
                lat=args.lat,
                lon=args.lon,
                radius_m=args.radius,
                output=args.output,
                buffer_m=args.buffer_m,
                tags_raw=args.tags,
            )
        except ValueError as exc:
            raise _fetch_error(exc) from exc
    if args.command == "tees":
        config_path = Path(args.config) if args.config else None
        base_config = load_config(str(config_path)) if config_path else load_config(None)
        config = _apply_overrides(base_config, args)
        for line in summarize_tees(args.input, config):
            print(line)
    if args.command == "build":
        cache_path = Path(args.cache_path) if args.cache_path else None
        if cache_path is None:
            slug = args.course.lower().replace(" ", "_")
            cache_path = Path("data") / f"{slug}.geojson"
        if not args.place and (args.lat is None or args.lon is None or args.radius is None):
            raise SystemExit("Provide --place or --lat/--lon/--radius for build.")
        try:
            fetch_course(
                place=args.place,
                lat=args.lat,
                lon=args.lon,
                radius_m=args.radius,
                output=str(cache_path),
                buffer_m=args.buffer_m,
                tags_raw=args.tags,
            )
        except ValueError as exc:
            if args.place and args.lat is not None and args.lon is not None and args.radius is not None:
                try:
                    fetch_course(
                        place=None,
                        lat=args.lat,
                        lon=args.lon,
                        radius_m=args.radius,
                        output=str(cache_path),
                        buffer_m=args.buffer_m,
                        tags_raw=args.tags,
                    )
                except ValueError as fallback_exc:
                    raise _fetch_error(fallback_exc) from fallback_exc
            else:
                raise _fetch_error(exc) from exc
        base_config = load_config(None)
        config = _apply_overrides(base_config, args)
        two_up = config["tolerances"].get("two_up", True) if args.two_up is None else args.two_up
        build_book(
            input_path=str(cache_path),
            course=args.course,
            output_path=args.output,
            config=config,
            two_up=two_up,
            debug=args.debug,
        )
    if args.command == "search":
        results = search_places(args.query, limit=args.limit)
        if results.empty:
            print("No results found.")
            return
        for _, row in results.iterrows():
            name = row.get("display_name") or row.get("name") or "Unknown"
            lat = row.get("lat") or row.geometry.centroid.y
            lon = row.get("lon") or row.geometry.centroid.x
            print(f"{name} ({lat}, {lon})")
    if args.command == "validate":
        gdf = load_course(args.input)
        holes = filter_by_tag(gdf, golf="hole")
        greens = filter_by_tag(gdf, golf="green")
        tees = filter_by_tag(gdf, golf="tee")
        fairways = filter_by_tag(gdf, golf="fairway")
        bunkers = filter_by_tag(gdf, golf="bunker")
        waters = gdf[gdf["natural"] == "water"] if "natural" in gdf.columns else gdf.iloc[0:0]
        print(f"Holes: {len(holes)}")
        print(f"Greens: {len(greens)}")
        print(f"Tees: {len(tees)}")
        print(f"Fairways: {len(fairways)}")
        print(f"Bunkers: {len(bunkers)}")
        print(f"Water: {len(waters)}")
        if holes.empty:
            print("Warning: no golf=hole LineStrings found. Add centerlines in QGIS and re-export.")


if __name__ == "__main__":
    main()
