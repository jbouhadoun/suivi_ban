"""Utilitaires pour tuiles XYZ Web Mercator et bbox GeoJSON."""

from __future__ import annotations

import math
from typing import Any

# Web Mercator (EPSG:3857) — rayon équatorial en mètres.
_R = 6378137.0
_HALF_C = math.pi * _R  # demi-circonférence ~ 20 037 508.34 m
_LAT_LIMIT = 85.05112878


def lonlat_to_webmercator(lon: float, lat: float) -> tuple[float, float]:
    """Projette (lon, lat) WGS84 vers (x, y) Web Mercator (EPSG:3857) en mètres."""
    lat_clamped = max(-_LAT_LIMIT, min(_LAT_LIMIT, lat))
    x = math.radians(lon) * _R
    y = math.log(math.tan(math.pi / 4.0 + math.radians(lat_clamped) / 2.0)) * _R
    return x, y


def tile_bounds_webmercator(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    """BBox (min_x, min_y, max_x, max_y) en Web Mercator pour la tuile (z, x, y)."""
    n = 2.0**z
    size = (2.0 * _HALF_C) / n
    min_x = -_HALF_C + x * size
    max_x = -_HALF_C + (x + 1) * size
    max_y = _HALF_C - y * size
    min_y = _HALF_C - (y + 1) * size
    return (min_x, min_y, max_x, max_y)


def _project_coords(coords: Any) -> Any:
    if coords and isinstance(coords[0], (int, float)):
        if len(coords) >= 2:
            return list(lonlat_to_webmercator(float(coords[0]), float(coords[1])))
        return coords
    return [_project_coords(c) for c in coords]


def project_geometry_to_webmercator(geometry: dict) -> dict:
    """
    Reprojette une géométrie GeoJSON WGS84 vers Web Mercator pour encodage MVT.
    Indispensable à bas zoom : un `quantize_bounds` linéaire en lon/lat
    introduit un décalage avec les fonds Web Mercator.
    """
    if not isinstance(geometry, dict):
        return geometry
    gtype = geometry.get("type")
    coords = geometry.get("coordinates")
    if coords is None or gtype not in {
        "Point",
        "MultiPoint",
        "LineString",
        "MultiLineString",
        "Polygon",
        "MultiPolygon",
    }:
        return geometry
    try:
        return {"type": gtype, "coordinates": _project_coords(coords)}
    except Exception:
        return geometry


def tolerance_meters_for_zoom(z: int) -> float:
    """
    Tolérance de simplification en mètres Mercator pour un zoom donné.
    Vise ~0,5 pixel logique au zoom courant (aucun effet visible côté carte
    mais drastiquement moins de points à encoder).
    """
    if z >= 10:
        return 0.0
    # 156543 ≈ 2 * π * R / 256 (taille d'un pixel Mercator au zoom 0).
    return 156543.034 / (2.0**z) * 0.5


def _decimate_ring(ring: list, tol_sq: float) -> list:
    """Décime un ring/ligne en supprimant les points distants < sqrt(tol_sq)."""
    if tol_sq <= 0 or len(ring) <= 4:
        return ring
    out = [ring[0]]
    last_x, last_y = ring[0][0], ring[0][1]
    for p in ring[1:-1]:
        dx = p[0] - last_x
        dy = p[1] - last_y
        if dx * dx + dy * dy >= tol_sq:
            out.append(p)
            last_x, last_y = p[0], p[1]
    out.append(ring[-1])
    return out if len(out) >= 4 else ring


def _simplify_coords(coords: Any, gtype: str, tol_sq: float) -> Any:
    if gtype in ("Point", "MultiPoint"):
        return coords
    if gtype == "LineString":
        return _decimate_ring(coords, tol_sq)
    if gtype == "MultiLineString":
        return [_decimate_ring(line, tol_sq) for line in coords]
    if gtype == "Polygon":
        return [_decimate_ring(ring, tol_sq) for ring in coords]
    if gtype == "MultiPolygon":
        return [
            [_decimate_ring(ring, tol_sq) for ring in poly] for poly in coords
        ]
    return coords


def simplify_and_project_geometry(geometry: dict, z: int) -> dict:
    """
    Projette en Web Mercator puis simplifie la géométrie en fonction du zoom.
    La simplification se fait dans l'espace projeté (en mètres) pour rester
    cohérente avec le rendu carto et éviter tout décalage visuel.
    """
    return project_and_simplify_geometry_tol(
        geometry, tolerance_meters_for_zoom(z)
    )


def project_and_simplify_geometry_tol(geometry: dict, tolerance_m: float) -> dict:
    """
    Variante avec tolérance explicite (mètres Mercator). Utile pour pré-construire
    un index en mémoire avec une simplification fixe indépendante du zoom rendu.
    """
    if not isinstance(geometry, dict):
        return geometry
    gtype = geometry.get("type")
    coords = geometry.get("coordinates")
    if coords is None or gtype not in {
        "Point",
        "MultiPoint",
        "LineString",
        "MultiLineString",
        "Polygon",
        "MultiPolygon",
    }:
        return geometry
    try:
        projected = _project_coords(coords)
        if tolerance_m > 0.0:
            projected = _simplify_coords(projected, gtype, tolerance_m * tolerance_m)
        return {"type": gtype, "coordinates": projected}
    except Exception:
        return geometry


def lonlat_to_tile_bounds(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    """BBox (min_lon, min_lat, max_lon, max_lat) pour la tuile (z, x, y)."""
    n = 2.0**z
    lon_min = x / n * 360.0 - 180.0
    lon_max = (x + 1) / n * 360.0 - 180.0
    lat_rad_min = math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n)))
    lat_rad_max = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
    lat_min = math.degrees(lat_rad_min)
    lat_max = math.degrees(lat_rad_max)
    return (lon_min, lat_min, lon_max, lat_max)


def _ring_bbox(ring: list) -> tuple[float, float, float, float] | None:
    if not ring:
        return None
    lons = [p[0] for p in ring if len(p) >= 2]
    lats = [p[1] for p in ring if len(p) >= 2]
    if not lons:
        return None
    return (min(lons), min(lats), max(lons), max(lats))


def _coords_bbox(coords: Any, depth: int = 0) -> tuple[float, float, float, float] | None:
    if depth > 8 or coords is None:
        return None
    if coords and isinstance(coords[0], (int, float)):
        if len(coords) >= 2:
            lon, lat = float(coords[0]), float(coords[1])
            return (lon, lat, lon, lat)
        return None
    b: tuple[float, float, float, float] | None = None
    for part in coords:
        sub = _coords_bbox(part, depth + 1)
        if sub is None:
            continue
        if b is None:
            b = sub
        else:
            b = (min(b[0], sub[0]), min(b[1], sub[1]), max(b[2], sub[2]), max(b[3], sub[3]))
    return b


def feature_bbox(feature: dict) -> tuple[float, float, float, float]:
    """BBox d'une feature GeoJSON (Polygon / MultiPolygon / autres)."""
    geom = feature.get("geometry") or {}
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if gtype == "Polygon" and coords:
        b = _ring_bbox(coords[0])
        if b:
            return b
    if gtype == "MultiPolygon" and coords:
        mb: tuple[float, float, float, float] | None = None
        for poly in coords:
            if poly and poly[0]:
                rb = _ring_bbox(poly[0])
                if rb:
                    if mb is None:
                        mb = rb
                    else:
                        mb = (min(mb[0], rb[0]), min(mb[1], rb[1]), max(mb[2], rb[2]), max(mb[3], rb[3]))
        if mb:
            return mb
    cb = _coords_bbox(coords)
    if cb:
        return cb
    return (0.0, 0.0, 0.0, 0.0)


def bbox_intersects(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> bool:
    """Deux bbox (min_lon, min_lat, max_lon, max_lat) s'intersectent."""
    return not (a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3])


def geometry_bounds_leaflet(geometry: dict | None) -> dict | None:
    """
    Retourne southwest / northeast en [lat, lon] pour L.map.fitBounds,
    ou None si pas de géométrie exploitable.
    """
    if not geometry:
        return None
    f = {"type": "Feature", "geometry": geometry, "properties": {}}
    min_lon, min_lat, max_lon, max_lat = feature_bbox(f)
    if max_lon <= min_lon and max_lat <= min_lat:
        return None
    return {
        "southwest": [min_lat, min_lon],
        "northeast": [max_lat, max_lon],
    }
