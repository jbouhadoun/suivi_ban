"""
Tuiles vectorielles PBF (MVT) + métadonnées légères pour la carte Suivi BAN.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict
from typing import Any

from fastapi import APIRouter, Path as FPath, Query
from fastapi.responses import JSONResponse, Response
from mapbox_vector_tile import encode as mvt_encode

from backend.api.tile_utils import (
    bbox_intersects,
    feature_bbox,
    lonlat_to_tile_bounds,
    project_geometry_to_webmercator,
    project_and_simplify_geometry_tol,
    simplify_and_project_geometry,
    tile_bounds_webmercator,
)
from config import BAL_TILES_MIN_ZOOM
from db.mongo import (
    get_communes_geojson_in_bbox,
    get_communes_meta_by_departement,
    get_deploiement_bal_geojson_in_bbox,
    get_deploiement_bal_stats,
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

# Seuil au-delà duquel on bascule sur la requête Mongo par tuile :
# au-dessus, le bbox est petit donc Mongo est rapide ; en-dessous,
# on s'appuie sur l'index en mémoire (pré-projeté + simplifié).
_BAL_INDEX_MAX_ZOOM = 7
# Tolérance (en mètres Mercator) utilisée pour pré-simplifier les géométries
# de l'index bas zoom. ~1 pixel à z=4, donc invisible à l'œil sur z=4-5,
# légèrement perceptible à z=7 mais acceptable pour un fond choroplèthe BAL.
# Réduit fortement le nombre de points à encoder par tuile, tout en
# conservant davantage de détail visuel qu'à 5000 m.
_BAL_INDEX_SIMPLIFY_TOL_M = 3000.0
_bal_index_cache: dict[str, Any] = {}
_bal_index_lock = threading.Lock()


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


def _sanitize_and_project_feature_webmercator(f: dict) -> dict | None:
    """
    Sanitize les propriétés et reprojette la géométrie en Web Mercator.
    Utilisé pour toutes les tuiles MVT afin d'aligner l'encodage avec le
    fond cartographique (Web Mercator) et éviter les décalages visuels.
    """
    geom = f.get("geometry")
    if not geom:
        return None
    projected = project_geometry_to_webmercator(geom)
    if not projected or not projected.get("coordinates"):
        return None
    return {
        "type": "Feature",
        "geometry": projected,
        "properties": _sanitize_props(dict(f.get("properties") or {})),
    }


def _sanitize_and_project_feature(f: dict, z: int) -> dict | None:
    """
    Sanitize les propriétés et reprojette + simplifie la géométrie en
    Web Mercator pour encodage MVT cohérent avec les fonds carto.
    """
    geom = f.get("geometry")
    if not geom:
        return None
    projected = simplify_and_project_geometry(geom, z)
    if not projected or not projected.get("coordinates"):
        return None
    return {
        "type": "Feature",
        "geometry": projected,
        "properties": _sanitize_props(dict(f.get("properties") or {})),
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


def _bal_mercator_bbox(geometry: dict) -> tuple[float, float, float, float] | None:
    """BBox Mercator (min_x, min_y, max_x, max_y) à partir d'une géométrie projetée."""
    coords = geometry.get("coordinates")
    if not coords:
        return None
    min_x = min_y = float("inf")
    max_x = max_y = float("-inf")

    def walk(c: Any) -> None:
        nonlocal min_x, min_y, max_x, max_y
        if c and isinstance(c[0], (int, float)):
            if len(c) >= 2:
                if c[0] < min_x:
                    min_x = c[0]
                if c[0] > max_x:
                    max_x = c[0]
                if c[1] < min_y:
                    min_y = c[1]
                if c[1] > max_y:
                    max_y = c[1]
            return
        for sub in c:
            walk(sub)

    walk(coords)
    if min_x == float("inf"):
        return None
    return (min_x, min_y, max_x, max_y)


def _get_bal_index() -> list:
    """
    Index en mémoire des features déploiement BAL :
    géométrie projetée + simplifiée (tolérance bas zoom), bbox Mercator,
    propriétés sanitizées. Construit à la demande, TTL 6 h.
    """
    entry = _bal_index_cache.get("idx")
    if entry and (_now() - entry["ts"]) < _CACHE_TTL:
        return entry["data"]
    with _bal_index_lock:
        entry = _bal_index_cache.get("idx")
        if entry and (_now() - entry["ts"]) < _CACHE_TTL:
            return entry["data"]
        from db.mongo import get_collection  # import local pour limiter le coût au boot

        coll = get_collection("deploiement_bal_features")
        cursor = coll.find({}, {"_id": 0, "properties": 1, "geometry": 1})
        index: list[tuple[dict, tuple[float, float, float, float]]] = []
        for doc in cursor:
            geom = doc.get("geometry")
            if not geom:
                continue
            projected = project_and_simplify_geometry_tol(
                geom, _BAL_INDEX_SIMPLIFY_TOL_M
            )
            if not projected or not projected.get("coordinates"):
                continue
            bb = _bal_mercator_bbox(projected)
            if not bb:
                continue
            feat = {
                "type": "Feature",
                "geometry": projected,
                "properties": _sanitize_props(dict(doc.get("properties") or {})),
            }
            index.append((feat, bb))
        _bal_index_cache["idx"] = {"data": index, "ts": _now()}
        logger.info("Index tuiles déploiement BAL construit (%s features)", len(index))
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
            headers={"Cache-Control": "public, max-age=3600"},
        )
    tile_bbox = lonlat_to_tile_bounds(z, x, y)
    index = _get_departements_index()
    matching_lonlat = [_sanitize_feature(f) for f, b in index if bbox_intersects(b, tile_bbox)]
    matching: list[dict] = []
    for f in matching_lonlat:
        sf = _sanitize_and_project_feature_webmercator(f)
        if sf is not None:
            matching.append(sf)
    merc_bbox = tile_bounds_webmercator(z, x, y)
    pbf = _encode_pbf("departements", matching, merc_bbox)
    _pbf_lru.put(cache_key, pbf)
    return Response(
        content=pbf,
        media_type="application/x-protobuf",
        headers={"Cache-Control": "public, max-age=3600"},
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
            headers={"Cache-Control": "public, max-age=3600"},
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
    matching: list[dict] = []
    for f in fc.get("features", []):
        if not isinstance(f, dict):
            continue
        sf = _sanitize_and_project_feature_webmercator(f)
        if sf is not None:
            matching.append(sf)
    t1 = time.perf_counter()
    merc_bbox = tile_bounds_webmercator(z, x, y)
    pbf = _encode_pbf("communes", matching, merc_bbox)
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
        headers={"Cache-Control": "public, max-age=3600"},
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


@router.get(
    "/api/deploiement-bal/stats",
    summary="FeatureCollection déploiement BAL (filtrée par codesCommune)",
)
def api_deploiement_bal_stats(
    codesCommune: str = Query(default=""),
):
    codes = [c.strip() for c in codesCommune.split(",") if c.strip()] if codesCommune else []
    # Alignement avec l'usage historique côté adresse.data.gouv.fr :
    # l'endpoint stats est destiné à des communes filtrées (EPCI/département),
    # pas à un dump France entière.
    if not codes:
        return JSONResponse(
            content={"type": "FeatureCollection", "features": []},
            headers={"Cache-Control": "public, max-age=3600"},
        )
    fc = get_deploiement_bal_stats(codes or None)
    return JSONResponse(
        content=fc,
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get(
    "/api/tiles/deploiement-bal/{z}/{x}/{y}.pbf",
    summary="Tuile MVT — déploiement BAL (communes)",
    response_class=Response,
)
@router.get(
    "/api/deploiement-stats/{z}/{x}/{y}.pbf",
    summary="Tuile MVT legacy — déploiement BAL (communes)",
    response_class=Response,
)
def tile_deploiement_bal(
    z: int = FPath(..., ge=0, le=14),
    x: int = FPath(..., ge=0),
    y: int = FPath(..., ge=0),
):
    if z < BAL_TILES_MIN_ZOOM:
        return Response(content=b"", media_type="application/x-protobuf")
    if z > 14:
        return Response(content=b"", media_type="application/x-protobuf")

    cache_key = ("depbal", z, x, y)
    hit = _pbf_lru.get(cache_key)
    if hit is not None:
        return Response(
            content=hit,
            media_type="application/x-protobuf",
            headers={"Cache-Control": "public, max-age=3600"},
        )

    # Quantize_bounds en Web Mercator pour éviter le décalage à bas zoom.
    merc_bbox = tile_bounds_webmercator(z, x, y)
    t0 = time.perf_counter()

    if z <= _BAL_INDEX_MAX_ZOOM:
        # Bas/moyen zoom : index en mémoire (features pré-projetées + simplifiées).
        # Évite la requête $geoIntersects qui ramène ~30k features sur la France entière.
        index = _get_bal_index()
        matching = [feat for feat, bb in index if bbox_intersects(bb, merc_bbox)]
        dt_query = 0.0
    else:
        # Zoom élevé : bbox petit, peu de features, requête Mongo + projection à la volée.
        tile_bbox = lonlat_to_tile_bounds(z, x, y)
        fc = get_deploiement_bal_geojson_in_bbox(*tile_bbox)
        dt_query = time.perf_counter() - t0
        matching = []
        for f in fc.get("features", []):
            if not isinstance(f, dict):
                continue
            sf = _sanitize_and_project_feature(f, z)
            if sf is not None:
                matching.append(sf)

    t1 = time.perf_counter()
    pbf = _encode_pbf("communes", matching, merc_bbox)
    dt_total = time.perf_counter() - t0
    if dt_total > 1.5:
        logger.warning(
            "Tuile BAL lente z=%s x=%s y=%s : query=%.2fs encodage=%.2fs features=%s pbf=%so",
            z,
            x,
            y,
            dt_query,
            time.perf_counter() - t1,
            len(matching),
            len(pbf),
        )
    _pbf_lru.put(cache_key, pbf)
    return Response(
        content=pbf,
        media_type="application/x-protobuf",
        headers={"Cache-Control": "public, max-age=3600"},
    )
