# Golf Yardage Book

Generate printable golf yardage book PDFs from GeoJSON exports (OSM/QGIS). The Pine Ridge book is a layout reference: cover, notes page, legend, then per-hole pages with fairway/green views and tee yardages.

## System requirements

- Python 3.10+ recommended.
- If `pip install` fails for GeoPandas/Shapely/PROJ, use the conda or mamba workflow below (GDAL/PROJ are bundled).
- OSM coverage varies. Some courses do not include `golf=hole` centerlines; those must be digitized in QGIS.

## Install

```bash
cd golf-yardage-book
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

Optional conda workflow:

```bash
conda create -n yardagebook python=3.10 geopandas shapely pyproj matplotlib pyyaml osmnx
conda activate yardagebook
```

Optional mamba workflow:

```bash
mamba create -n yardagebook python=3.10 geopandas shapely pyproj matplotlib pyyaml osmnx
mamba activate yardagebook
```

Or use the provided `environment.yml` with micromamba/conda for reproducible installs.

## Usage

```bash
yardagebook build \
  --place "Forest Park Golf Course, Baltimore, MD" \
  --course "Forest Park" \
  --tee-set back \
  --paper pocket \
  --output outputs/forest_park_pocket.pdf
```

Pocket books default to duplex mode (fairway page + green page). Use `--paper legal --two-up` for two-up sheets, and `--debug` to print hole matching details.
Select tees with `--tee-set back|middle|front`, or override with `--tee-label`/`--tee-index`.

Quickstart (build + PDF artifact in one command):

```bash
yardagebook build --place "Forest Park Golf Course, Baltimore, MD" --course "Forest Park" --paper pocket --tee-set back --output outputs/forest_park_pocket.pdf
```

Inspect tee labels first:

```bash
yardagebook fetch --place "Forest Park Golf Course, Baltimore, MD" --output data/forest_park.geojson
yardagebook tees --input data/forest_park.geojson
yardagebook generate --input data/forest_park.geojson --course "Forest Park" --paper pocket --tee-label "Blue" --output outputs/forest_park_blue.pdf
yardagebook generate --input data/forest_park.geojson --course "Forest Park" --paper pocket --tee-index 1 --output outputs/forest_park_first.pdf
```

Pine Ridge-style legal print sheet:

```bash
yardagebook generate --input data/forest_park.geojson --course "Forest Park" --paper legal --two-up --no-duplex --output outputs/forest_park_legal.pdf
```

Place lookup helpers:

```bash
yardagebook search --query "Forest Park Golf Course, Baltimore, MD"
yardagebook validate --input data/forest_park.geojson
```

When a place lookup returns a point, the fetch step buffers it by a default ~1200m radius (or your `--buffer-m`).

Printing guidance:

- Pocket mode outputs 3.5\" x 5\" pages for pocket stock.
- Legal two-up duplicates content in two columns for print-and-cut layouts.

## OSM data limitations

OpenStreetMap coverage varies. Many courses do not include `golf=hole` LineString centerlines; those courses require digitized centerlines from QGIS before running `yardagebook generate`.

## Data requirements

GeoJSON should contain OSM-style tags in feature properties:

- `golf=hole` LineStrings for each hole centerline.
- Optional polygons: `golf=fairway`, `golf=green`, `golf=tee`, `golf=bunker`.
- Optional water: `natural=water`.

Matching is spatial: the tool does not require a `ref` field. It picks the nearest green to each hole line, determines tee/green ends, then finds tees/fairways/hazards within configurable tolerances.
If `golf=hole` centerlines are missing from OSM, you must digitize hole lines in QGIS and export GeoJSON.

## Configuration

`yardagebook/configs/default.yml` controls styling, margins, and tolerances (tee radius, fairway tolerance, marker/grid steps). Override values via CLI flags:

```bash
python -m yardagebook generate \
  --input data/course.geojson \
  --course "Forest Park" \
  --output outputs/forest_park.pdf \
  --marker-step 50 \
  --grid-step 5 \
  --tee-radius 120 \
  --fairway-tol 60
```

## Troubleshooting

- **Missing fairways/greens/tees:** The tool creates proxy shapes when features are missing and reports them in `--debug` output.
- **Incorrect yardages or orientation:** Ensure the hole centerlines are clean LineStrings and that the GeoJSON CRS is WGS84 (EPSG:4326).
- **Sparse hazard rendering:** Increase `hazard_tol_m` in `yardagebook/configs/default.yml` to capture more bunkers/water.

## Smoke test

```bash
python scripts/smoke_test.py
```
