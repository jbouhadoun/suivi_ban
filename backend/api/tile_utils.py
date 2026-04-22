"""Utilitaires pour tuiles XYZ Web Mercator et bbox GeoJSON."""

from __future__ import annotations

import math
from typing import Any


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
