#!/usr/bin/env bash
set -euo pipefail

PLACE=${PLACE:-}
COURSE=${COURSE:-Yardage Book}
PAPER=${PAPER:-pocket}
TEE_SET=${TEE_SET:-back}
TEE_LABEL=${TEE_LABEL:-}
TEE_INDEX=${TEE_INDEX:-}
BUFFER_M=${BUFFER_M:-}
LAT=${LAT:-}
LON=${LON:-}
RADIUS=${RADIUS:-}
OUTPUT=${OUTPUT:-outputs/book.pdf}

args=(build --course "$COURSE" --paper "$PAPER" --tee-set "$TEE_SET" --output "$OUTPUT")

if [[ -n "$TEE_LABEL" ]]; then
  args+=(--tee-label "$TEE_LABEL")
fi

if [[ -n "$TEE_INDEX" ]]; then
  args+=(--tee-index "$TEE_INDEX")
fi

if [[ -n "$BUFFER_M" ]]; then
  args+=(--buffer-m "$BUFFER_M")
fi

if [[ -n "$PLACE" ]]; then
  args+=(--place "$PLACE")
else
  if [[ -z "$LAT" || -z "$LON" || -z "$RADIUS" ]]; then
    echo "Provide PLACE or LAT/LON/RADIUS." >&2
    exit 1
  fi
  args+=(--lat "$LAT" --lon "$LON" --radius "$RADIUS")
fi

python -m yardagebook "${args[@]}"
