"""
Collecteur snapshot Déploiement BAL.

Construit une FeatureCollection compatible avec l'API historique /api/deploiement-stats
et stocke le résultat dans la collection MongoDB `deploiement_bal_features`.
"""

from __future__ import annotations

import logging
from datetime import datetime

import requests

from config import API_BAN_LOOKUP, API_BAL_DEPOT, API_BAL_STATS_BASE, API_TIMEOUT
from db.mongo import get_collection, replace_deploiement_bal_features

logger = logging.getLogger(__name__)

# API BAN search (communes-summary)
API_BAN_BASE = API_BAN_LOOKUP.rsplit("/lookup", 1)[0]
API_COMMUNES_SUMMARY = f"{API_BAN_BASE}/api/communes-summary"

# API BAL (stats bals)
# Endpoint API prioritaire + fallback legacy.
API_BAL_STATS_CANDIDATES = [
    f"{API_BAL_STATS_BASE.rstrip('/')}/stats/bals",
    "https://api-bal.adresse.data.gouv.fr/v2/stats/bals",
    "https://plateforme-bal.adresse.data.gouv.fr/stats/bals",
]


def _space_thousands(number: int | float | None) -> str:
    try:
        return f"{int(number or 0):,}".replace(",", " ")
    except Exception:
        return "0"


def _percentage(value: int | float | None, total: int | float | None):
    total_v = float(total or 0)
    value_v = float(value or 0)
    if total_v <= 0:
        return 0
    pct = (value_v * 100.0) / total_v
    rounded = int(pct * 10) / 10
    if rounded == 0:
        return 0
    # Aligner le format JS historique: "100" et non "100,0"
    if float(rounded).is_integer():
        return str(int(rounded))
    return str(rounded).replace(".", ",")


def _compute_status_bals(bals: list[dict] | None = None) -> str:
    statuses = {b.get("status") for b in (bals or []) if isinstance(b, dict)}
    if "published" in statuses:
        return "published"
    if "replaced" in statuses:
        return "replaced"
    if "draft" in statuses:
        return "draft"
    return "unknown"


def _fetch_json(url: str, method: str = "GET", payload: dict | None = None):
    if method == "POST":
        r = requests.post(url, json=payload or {}, timeout=API_TIMEOUT)
    else:
        r = requests.get(url, timeout=API_TIMEOUT)
    r.raise_for_status()
    content_type = (r.headers.get("Content-Type") or "").lower()
    if "application/json" not in content_type:
        raise ValueError(f"Réponse non JSON depuis {url} (content-type={content_type})")
    try:
        return r.json()
    except Exception as e:
        body_preview = (r.text or "")[:200].replace("\n", " ")
        raise ValueError(f"JSON invalide depuis {url}: {e}; body='{body_preview}'") from e


def _fetch_bals_stats() -> list[dict]:
    """
    Récupère les stats BAL depuis l'endpoint disponible.
    Certains endpoints publics renvoient HTML (landing) au lieu de JSON.
    """
    last_err = None
    for url in API_BAL_STATS_CANDIDATES:
        try:
            # Alignement API historique: POST + fields en query string
            full_url = f"{url}?fields=id&fields=commune&fields=status"
            data = _fetch_json(full_url, method="POST", payload=None)
            if isinstance(data, list):
                return data
            logger.warning("[deploiement_bal] Réponse inattendue depuis %s (type=%s)", url, type(data))
        except Exception as e:
            logger.warning("[deploiement_bal] Endpoint BAL indisponible %s: %s", url, e)
            last_err = e
    if last_err:
        raise RuntimeError(f"Aucun endpoint stats/bals JSON disponible: {last_err}") from last_err
    return []


def _build_indexes(current_revisions: list[dict], communes_summary: list[dict], bals: list[dict]):
    rev_idx = {
        str(r.get("codeCommune")): r
        for r in current_revisions
        if r.get("codeCommune")
    }
    summary_idx = {
        str(s.get("codeCommune")): s
        for s in communes_summary
        if s.get("codeCommune")
    }
    bals_idx: dict[str, list[dict]] = {}
    for b in bals:
        code = b.get("commune")
        if not code:
            continue
        bals_idx.setdefault(str(code), []).append(b)
    return rev_idx, summary_idx, bals_idx


def run_deploiement_bal_collect() -> bool:
    started_at = datetime.utcnow()
    logger.info("[deploiement_bal] Collecte démarrée")
    try:
        logger.info("[deploiement_bal] STEP 1/5 fetch current-revisions")
        current_revisions = _fetch_json(f"{API_BAL_DEPOT}/current-revisions")
        logger.info(
            "[deploiement_bal] current_revisions=%s",
            len(current_revisions) if isinstance(current_revisions, list) else "invalid",
        )
        logger.info("[deploiement_bal] STEP 2/5 fetch communes-summary")
        communes_summary = _fetch_json(API_COMMUNES_SUMMARY)
        logger.info(
            "[deploiement_bal] communes_summary=%s",
            len(communes_summary) if isinstance(communes_summary, list) else "invalid",
        )
        logger.info("[deploiement_bal] STEP 3/5 fetch stats/bals")
        bals = _fetch_bals_stats()
        logger.info(
            "[deploiement_bal] bals=%s",
            len(bals) if isinstance(bals, list) else "invalid",
        )

        if not isinstance(current_revisions, list):
            current_revisions = []
        if not isinstance(communes_summary, list):
            communes_summary = []
        if not isinstance(bals, list):
            bals = []

        rev_idx, summary_idx, bals_idx = _build_indexes(current_revisions, communes_summary, bals)

        # Univers de communes: union(current-revisions, communes-summary)
        codes = set(rev_idx.keys()) | set(summary_idx.keys())
        logger.info(
            "[deploiement_bal] STEP 4/5 index done: rev_idx=%s summary_idx=%s bals_idx=%s codes=%s",
            len(rev_idx),
            len(summary_idx),
            len(bals_idx),
            len(codes),
        )
        communes = get_collection("communes")

        features: list[dict] = []
        total_codes = len(codes)
        processed = 0
        missing_summary = 0
        missing_commune = 0
        missing_geometry = 0
        for code in codes:
            processed += 1
            summary = summary_idx.get(code)
            if not summary:
                missing_summary += 1
                continue
            commune_doc = communes.find_one(
                {"code_insee": code},
                {"nom": 1, "geometry": 1, "geometry_raw": 1},
            )
            if not commune_doc:
                missing_commune += 1
                continue

            geometry = commune_doc.get("geometry") or commune_doc.get("geometry_raw")
            if not geometry:
                missing_geometry += 1
                continue

            has_bal = summary.get("typeComposition") == "bal"
            revisions = rev_idx.get(code) or {}
            status_bals = _compute_status_bals(bals_idx.get(code))

            properties = {
                "nom": commune_doc.get("nom") or summary.get("nomCommune") or "",
                "code": code,
                "nbNumeros": _space_thousands(summary.get("nbNumeros")),
                "hasBAL": bool(has_bal),
                "certificationPercentage": _percentage(
                    summary.get("nbNumerosCertifies"),
                    summary.get("nbNumeros"),
                ),
                "statusBals": status_bals,
            }

            if has_bal and revisions:
                client = revisions.get("client") or {}
                # Parité avec l'API historique observée:
                # idClient est souvent vide même avec nomClient renseigné.
                properties["idClient"] = client.get("legacyId") or ""
                properties["nomClient"] = client.get("nom") or ""

            features.append(
                {
                    "type": "Feature",
                    "code_insee": code,
                    "properties": properties,
                    "geometry": geometry,
                    "collected_at": started_at,
                }
            )
            if processed % 1000 == 0:
                logger.info(
                    "[deploiement_bal] progress %s/%s features=%s missing_summary=%s missing_commune=%s missing_geometry=%s",
                    processed,
                    total_codes,
                    len(features),
                    missing_summary,
                    missing_commune,
                    missing_geometry,
                )

        logger.info(
            "[deploiement_bal] STEP 5/5 write snapshot: features=%s source={current_revisions=%s communes_summary=%s bals=%s}",
            len(features),
            len(current_revisions),
            len(communes_summary),
            len(bals),
        )
        inserted = replace_deploiement_bal_features(
            features,
            source_stats={
                "current_revisions": len(current_revisions),
                "communes_summary": len(communes_summary),
                "bals": len(bals),
                "features": len(features),
            },
        )
        logger.info(
            "[deploiement_bal] Collecte terminée: inserted=%s built=%s missing_summary=%s missing_commune=%s missing_geometry=%s",
            inserted,
            len(features),
            missing_summary,
            missing_commune,
            missing_geometry,
        )
        return True
    except Exception as e:
        logger.exception("[deploiement_bal] Erreur collecte: %s", e)
        return False


if __name__ == "__main__":
    ok = run_deploiement_bal_collect()
    raise SystemExit(0 if ok else 1)

