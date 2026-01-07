"""FastAPI web UI for building yardage book PDFs."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from fastapi import BackgroundTasks, FastAPI, Form, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from yardagebook.book import build_book, load_config, merge_config
from yardagebook.fetch import fetch_course

app = FastAPI()
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

PAPER_OPTIONS = ["pocket", "legal", "letter"]


def _parse_optional_float(value: str | None) -> float | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    return float(text)


def _parse_optional_int(value: str | None) -> int | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    return int(text)


def _build_overrides(
    *,
    paper: str,
    tee_set: str,
    tee_label: str | None,
    tee_index: int | None,
) -> tuple[dict[str, Any], bool]:
    overrides: dict[str, Any] = {
        "page": {"paper": paper},
        "tolerances": {"tee_set": tee_set},
    }
    if tee_label:
        overrides["tolerances"]["tee_label"] = tee_label
    if tee_index is not None:
        overrides["tolerances"]["tee_index"] = tee_index
    two_up = False
    duplex = True
    if paper == "legal":
        two_up = True
        duplex = False
    elif paper == "pocket":
        two_up = False
        duplex = True
    overrides["tolerances"]["two_up"] = two_up
    overrides["tolerances"]["duplex"] = duplex
    return overrides, two_up


def _render_form(request: Request, errors: list[str] | None = None, values: dict[str, Any] | None = None):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "errors": errors or [],
            "values": values or {},
            "paper_options": PAPER_OPTIONS,
        },
    )


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return _render_form(request)


@app.post("/build")
async def build(
    request: Request,
    background_tasks: BackgroundTasks,
    place: str = Form(""),
    course: str = Form(""),
    paper: str = Form("pocket"),
    tee_set: str = Form("back"),
    tee_label: str = Form(""),
    tee_index: str = Form(""),
    buffer_m: str = Form(""),
    lat: str = Form(""),
    lon: str = Form(""),
    radius: str = Form(""),
):
    errors: list[str] = []
    paper = paper.strip() or "pocket"
    if paper not in PAPER_OPTIONS:
        errors.append("Select a valid paper size.")
    place_value = place.strip() or None
    course_value = course.strip() or "Yardage Book"
    values = {
        "place": place,
        "course": course,
        "paper": paper,
        "tee_set": tee_set,
        "tee_label": tee_label,
        "tee_index": tee_index,
        "buffer_m": buffer_m,
        "lat": lat,
        "lon": lon,
        "radius": radius,
    }

    try:
        tee_index_value = _parse_optional_int(tee_index)
    except ValueError:
        errors.append("Tee index must be an integer.")
        tee_index_value = None

    try:
        buffer_value = _parse_optional_float(buffer_m)
    except ValueError:
        errors.append("Buffer must be a number.")
        buffer_value = None

    try:
        lat_value = _parse_optional_float(lat)
        lon_value = _parse_optional_float(lon)
        radius_value = _parse_optional_float(radius)
    except ValueError:
        errors.append("Latitude, longitude, and radius must be numbers.")
        lat_value = lon_value = radius_value = None

    if not place_value and (lat_value is None or lon_value is None or radius_value is None):
        errors.append("Provide a place or a latitude/longitude/radius combination.")

    if errors:
        return _render_form(request, errors=errors, values=values)

    temp_dir = TemporaryDirectory()
    background_tasks.add_task(temp_dir.cleanup)
    geojson_path = Path(temp_dir.name) / "course.geojson"
    pdf_path = Path(temp_dir.name) / "book.pdf"

    try:
        fetch_course(
            place=place_value,
            lat=lat_value,
            lon=lon_value,
            radius_m=radius_value,
            output=str(geojson_path),
            buffer_m=buffer_value,
            tags_raw=None,
        )
        defaults = load_config(None)
        overrides, two_up = _build_overrides(
            paper=paper,
            tee_set=tee_set.strip() or defaults["tolerances"]["tee_set"],
            tee_label=tee_label.strip() or None,
            tee_index=tee_index_value,
        )
        config = merge_config(defaults, overrides)
        build_book(
            input_path=str(geojson_path),
            course=course_value,
            output_path=str(pdf_path),
            config=config,
            two_up=two_up,
            debug=False,
        )
    except Exception as exc:
        errors.append(str(exc))
        return _render_form(request, errors=errors, values=values)

    safe_course = course_value.strip().replace(" ", "_") or "yardage_book"
    filename = f"{safe_course}_{paper}.pdf"
    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=filename,
        background=background_tasks,
    )
