"""
Tuiles vectorielles PBF (MVT) + métadonnées légères pour la carte Suivi BAN.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict
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

# Cache PBF en RAM par pod (évite Mongo + encodage MVT sur les mêmes URLs).
_PBF_LRU_MAX_BYTES = 200 * 1024 * 1024


class _PbfLru:
    __slots__ = ("_max", "_od", "_size", "_lock")

    def __init__(self, max_bytes: int) -> None:
        self._max = max_bytes
        self._od: "OrderedDict[tuple, bytes]" = OrderedDict()
        self._size = 0
        self._lock = threading.Lock()

    def get(self, key: tuple) -> bytes | None:
        with self._lock:
            if key not in self._od:
                return None
            val = self._od.pop(key)
            self._od[key] = val
            return val

    def put(self, key: tuple, data: bytes) -> None:
        n = len(data)
        if n > self._max:
            return
        with self._lock:
            if key in self._od:
                self._size -= len(self._od.pop(key))
            self._od[key] = data
            self._size += n
            while self._size > self._max and self._od:
                _, v = self._od.popitem(last=False)
                self._size -= len(v)


_pbf_lru = _PbfLru(_PBF_LRU_MAX_BYTES)

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
    cache_key = ("dep", z, x, y)
    hit = _pbf_lru.get(cache_key)
    if hit is not None:
        return Response(
            content=hit,
            media_type="application/x-protobuf",
            headers={"Cache-Control": "public, max-age=300"},
        )
    tile_bbox = lonlat_to_tile_bounds(z, x, y)
    index = _get_departements_index()
    matching = [_sanitize_feature(f) for f, b in index if bbox_intersects(b, tile_bbox)]
    pbf = _encode_pbf("departements", matching, tile_bbox)
    _pbf_lru.put(cache_key, pbf)
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
    cache_key = ("com", code, z, x, y)
    hit = _pbf_lru.get(cache_key)
    if hit is not None:
        return Response(
            content=hit,
            media_type="application/x-protobuf",
            headers={"Cache-Control": "public, max-age=300"},
        )
    tile_bbox = lonlat_to_tile_bounds(z, x, y)
    t0 = time.perf_counter()
    fc = get_communes_geojson_in_bbox(code, *tile_bbox)
    dt = time.perf_counter() - t0
    if dt > 1.0:
        logger.warning(
            "Tuile communes lente dept=%s z=%s x=%s y=%s : Mongo/geo %.2fs (%s features)",
            code,
            z,
            x,
            y,
            dt,
            len(fc.get("features") or []),
        )
    matching = [
        _sanitize_feature(f)
        for f in fc.get("features", [])
        if isinstance(f, dict) and f.get("geometry")
    ]
    t1 = time.perf_counter()
    pbf = _encode_pbf("communes", matching, tile_bbox)
    enc = time.perf_counter() - t1
    if dt + enc > 1.5:
        logger.warning(
            "Tuile communes lente dept=%s z=%s x=%s y=%s : encodage MVT %.2fs, pbf=%s o",
            code,
            z,
            x,
            y,
            enc,
            len(pbf),
        )
    _pbf_lru.put(cache_key, pbf)
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
