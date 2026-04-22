"""
Tuiles vectorielles PBF (MVT) + métadonnées légères pour la carte Suivi BAN.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from fastapi import APIRouter, Path as FPath
from fastapi.responses import JSONResponse, Response
from mapbox_vector_tile import encode as mvt_encode

from backend.api.tile_utils import bbox_intersects, feature_bbox, lonlat_to_tile_bounds
from db.mongo import (
    get_communes_geojson_in_bbox,
    get_communes_meta_by_departement,
    get_departement_bounds_leaflet,
    get_departements_geojson,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Carte PBF"])

_CACHE_TTL = 6 * 3600
_departements_index_cache: dict[str, Any] = {}
_departements_index_lock = threading.Lock()


def _now() -> float:
    return time.time()


def _sanitize_props(props: dict) -> dict:
    """Valeurs compatibles MVT (pas de None)."""
    out: dict[str, Any] = {}
    for k, v in props.items():
        if v is None:
            out[k] = ""
        elif isinstance(v, float) and (v != v):  # NaN
            out[k] = 0.0
        else:
            out[k] = v
    return out


def _sanitize_feature(f: dict) -> dict:
    p = f.get("properties") or {}
    return {
        "type": "Feature",
        "geometry": f.get("geometry"),
        "properties": _sanitize_props(dict(p)),
    }


def _get_departements_index() -> list:
    entry = _departements_index_cache.get("idx")
    if entry and (_now() - entry["ts"]) < _CACHE_TTL:
        return entry["data"]
    with _departements_index_lock:
        entry = _departements_index_cache.get("idx")
        if entry and (_now() - entry["ts"]) < _CACHE_TTL:
            return entry["data"]
        data = get_departements_geojson()
        index = [
            (_sanitize_feature(f), feature_bbox(f))
            for f in data.get("features", [])
            if isinstance(f, dict) and f.get("geometry")
        ]
        _departements_index_cache["idx"] = {"data": index, "ts": _now()}
        logger.info("Index tuiles départements construit (%s polygones)", len(index))
        return index


def _encode_pbf(
    layer_name: str,
    sanitized_features: list[dict],
    tile_bbox: tuple[float, float, float, float],
) -> bytes:
    if not sanitized_features:
        return b""
    return mvt_encode(
        {"name": layer_name, "features": sanitized_features},
        default_options={
            "quantize_bounds": tile_bbox,
            "extents": 4096,
            "check_winding_order": False,
        },
    )


@router.get(
    "/api/tiles/departements/{z}/{x}/{y}.pbf",
    summary="Tuile MVT — contours départements (France)",
    response_class=Response,
)
def tile_departements(
    z: int = FPath(..., ge=0, le=14),
    x: int = FPath(..., ge=0),
    y: int = FPath(..., ge=0),
):
    if z > 14:
        return Response(content=b"", media_type="application/x-protobuf")
    tile_bbox = lonlat_to_tile_bounds(z, x, y)
    index = _get_departements_index()
    matching = [_sanitize_feature(f) for f, b in index if bbox_intersects(b, tile_bbox)]
    pbf = _encode_pbf("departements", matching, tile_bbox)
    return Response(
        content=pbf,
        media_type="application/x-protobuf",
        headers={"Cache-Control": "public, max-age=300"},
    )


@router.get(
    "/api/tiles/departement/{code}/{z}/{x}/{y}.pbf",
    summary="Tuile MVT — communes d'un département",
    response_class=Response,
)
def tile_communes_departement(
    code: str = FPath(..., min_length=2, max_length=3),
    z: int = FPath(..., ge=0, le=14),
    x: int = FPath(..., ge=0),
    y: int = FPath(..., ge=0),
):
    if z > 14:
        return Response(content=b"", media_type="application/x-protobuf")
    tile_bbox = lonlat_to_tile_bounds(z, x, y)
    fc = get_communes_geojson_in_bbox(code, *tile_bbox)
    matching = [
        _sanitize_feature(f)
        for f in fc.get("features", [])
        if isinstance(f, dict) and f.get("geometry")
    ]
    pbf = _encode_pbf("communes", matching, tile_bbox)
    return Response(
        content=pbf,
        media_type="application/x-protobuf",
        headers={"Cache-Control": "public, max-age=300"},
    )


@router.get(
    "/api/departement/{code}/communes-meta",
    summary="Liste des communes (sans géométrie)",
)
def api_communes_meta(code: str):
    rows = get_communes_meta_by_departement(code)
    if not rows:
        return JSONResponse(status_code=404, content={"error": "Département introuvable ou vide"})
    return {"communes": rows, "total": len(rows)}


@router.get(
    "/api/departement/{code}/bounds",
    summary="Emprise Leaflet du département",
)
def api_departement_bounds(code: str):
    b = get_departement_bounds_leaflet(code)
    if not b:
        return JSONResponse(status_code=404, content={"error": "Département introuvable"})
    return b
