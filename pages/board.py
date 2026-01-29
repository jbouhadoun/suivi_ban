"""
Board alertes BAN - accessible uniquement via l'URL /board.
La sidebar est repliée par défaut ; aucun lien vers cette page n'est affiché
sur l'accueil, donc seuls les utilisateurs qui ont le lien y accèdent.
"""
import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# Configuration : sidebar repliée pour ne pas exposer le lien
st.set_page_config(
    page_title="Board alertes - BAN",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Optionnel : masquer le bouton qui ouvre la sidebar sur cette page
st.markdown("""
<style>
    [data-testid="collapsedControl"] { display: none; }
    .main .block-container { padding: 1rem 2rem; max-width: 100%; }
</style>
""", unsafe_allow_html=True)

BASE_URL = "https://plateforme.adresse.data.gouv.fr/api/alerts"
ERRORS_URL = f"{BASE_URL}/errors-summary?limit=500"
WARNINGS_URL = f"{BASE_URL}/warnings-summary?limit=1000"

CACHE_TTL_SECONDS = 30 * 60  # 30 minutes


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def _fetch_json_cached(url: str):
    """Appel API (résultat mis en cache 30 min). Ne pas appeler en cas d’erreur."""
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()


def fetch_json(url: str):
    """Appel API avec cache 30 min ; les échecs ne sont pas mis en cache."""
    try:
        return _fetch_json_cached(url)
    except Exception as e:
        st.error(f"Erreur lors de l'appel à l'API : {e}")
        return None


def parse_message_type(msg: str, is_error: bool = True) -> str:
    """Identifie le type de message (même logique que le script jq wiki)."""
    if not msg or not isinstance(msg, str):
        return "—"
    prefix = "🔴" if is_error else "🟠"
    if "⚠️ **Conflit mainTopoID avec lieu-dit**" in msg:
        return f"{prefix} Lieu-dit déclaré à la fois en voie et en lieu-dit"
    if "⚠️ **Lieu-dit avec addressID**" in msg:
        return f"{prefix} Lieu-dit déclaré avec un identifiant adresse"
    lower = msg.strip().lower()
    if "job" in lower and "échoué" in lower:
        if "updatedate is a required field" in lower:
            return f"{prefix} Date mise à jour manquante"
        return f"{prefix} Erreur interne - contacter le support"
    if "droits manquants" in lower:
        return f"{prefix} Droits manquants"
    if "opération non autorisée" in lower:
        return f"{prefix} Opération non autorisée - Identifiants déjà utilisés"
    if "seuil de suppression" in lower or "exceeded" in lower:
        return f"{prefix} Seuil de suppression dépassé"
    if "addressid manquant" in lower:
        return f"{prefix} addressID manquant - Consulter rapport de validation"
    if "districtid manquant" in lower:
        return f"{prefix} districtID manquant - Consulter rapport de validation"
    if "maintopoid manquant" in lower:
        return f"{prefix} mainTopoID manquant - Consulter rapport de validation"
    if "ids manquants" in lower:
        return f"{prefix} IDs manquants - Consulter rapport de validation"
    if "enregistrement de la bal sans les identifiants" in lower:
        return f"{prefix} Enregistrement sans identifiants - Consulter rapport"
    if any(x in lower for x in ["api ban", "api dump", "timeout"]):
        return f"{prefix} Erreur interne - contactez le support"
    # Sinon première ligne du message, tronquée
    first_line = msg.strip().split("\n")[0][:80]
    if len(msg.strip().split("\n")[0]) > 80:
        first_line += "..."
    return f"{prefix} {first_line}"


def normalize_alerts(data, is_error: bool = True) -> list[dict]:
    """Normalise la liste d'alertes (format API variable). is_error=True pour erreurs, False pour warnings."""
    if data is None:
        return []
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict) and "response" in data:
        # API plateforme adresse : { "response": { "communes": [...] } }
        resp = data.get("response") or {}
        if isinstance(resp, dict):
            items = resp.get("communes") or resp.get("data") or []
        else:
            items = []
        if not isinstance(items, list):
            items = []
    elif isinstance(data, dict) and "data" in data:
        items = data.get("data", [])
    elif isinstance(data, dict) and "results" in data:
        items = data.get("results", [])
    else:
        items = [data] if data else []
    out = []
    for row in items:
        if not isinstance(row, dict):
            continue
        commune = (
            row.get("districtName")
            or row.get("commune")
            or row.get("nom_commune")
            or row.get("city")
            or "—"
        )
        cog = row.get("cog") or row.get("code_insee") or row.get("code") or "—"
        date_val = row.get("date") or row.get("createdAt") or row.get("created_at") or row.get("timestamp")
        if date_val and isinstance(date_val, str) and "T" in date_val:
            date_val = date_val.split("T")[0]
        msg = row.get("message") or row.get("message_type") or row.get("description") or ""
        msg_str = msg if isinstance(msg, str) else str(msg)
        out.append({
            "Commune": commune,
            "COG": str(cog),
            "Date": date_val or "—",
            "Type": parse_message_type(msg_str, is_error=is_error),
            "Détail": msg_str,
        })
    return out


st.title("📊 Board suivi des alertes BAN")

err_data = fetch_json(ERRORS_URL)
warn_data = fetch_json(WARNINGS_URL)

errors_list = normalize_alerts(err_data, is_error=True)
warnings_list = normalize_alerts(warn_data, is_error=False)

tab_erreurs, tab_warnings = st.tabs(["🔴 Erreurs", "🟠 Warnings"])

with tab_erreurs:
    st.subheader("Erreurs")
    if not errors_list:
        st.info("Aucune erreur récente ou API indisponible.")
    else:
        df_err = pd.DataFrame(errors_list)
        filter_err = st.text_input("Filtrer (commune, COG, type, détail)", key="filter_err")
        if filter_err:
            q = filter_err.lower()
            df_err = df_err[
                df_err["Commune"].astype(str).str.lower().str.contains(q, na=False)
                | df_err["COG"].astype(str).str.contains(q, na=False)
                | df_err["Type"].astype(str).str.lower().str.contains(q, na=False)
                | df_err["Détail"].astype(str).str.lower().str.contains(q, na=False)
            ]
        st.dataframe(
            df_err,
            use_container_width=True,
            height=400,
            column_config={"Détail": st.column_config.TextColumn("Détail", width="large")},
        )
        st.metric("Nombre d'erreurs", len(df_err))

BAL_SANS_IDS = "⚠️ **Enregistrement de la BAL sans les identifiants**"

with tab_warnings:
    st.subheader("Warnings")
    if not warnings_list:
        st.info("Aucun warning récent ou API indisponible.")
    else:
        warnings_bloquants = [w for w in warnings_list if BAL_SANS_IDS in (w.get("Détail") or "")]
        warnings_nouveau_socle = [w for w in warnings_list if BAL_SANS_IDS not in (w.get("Détail") or "")]

        sub_bloq, sub_nouveau = st.tabs([
            f"🚫 Bloquants — ancien socle ({len(warnings_bloquants)})",
            f"🟠 Nouveau socle ({len(warnings_nouveau_socle)})",
        ])

        with sub_bloq:
            st.caption("Enregistrement de la BAL sans les identifiants (dans l'ancien socle) parceque elle est jamais enregistrée avec les identifiants.")
            if not warnings_bloquants:
                st.info("Aucun warning bloquant.")
            else:
                df_bloquants = pd.DataFrame(warnings_bloquants)
                filter_bloq = st.text_input("Filtrer (commune, COG, type, détail)", key="filter_warn_bloq")
                if filter_bloq:
                    q = filter_bloq.lower()
                    df_bloquants = df_bloquants[
                        df_bloquants["Commune"].astype(str).str.lower().str.contains(q, na=False)
                        | df_bloquants["COG"].astype(str).str.contains(q, na=False)
                        | df_bloquants["Type"].astype(str).str.lower().str.contains(q, na=False)
                        | df_bloquants["Détail"].astype(str).str.lower().str.contains(q, na=False)
                    ]
                st.dataframe(
                    df_bloquants,
                    use_container_width=True,
                    height=400,
                    column_config={"Détail": st.column_config.TextColumn("Détail", width="large")},
                )
                st.metric("Nombre de warnings bloquants", len(df_bloquants))

        with sub_nouveau:
            if not warnings_nouveau_socle:
                st.info("Aucun autre warning.")
            else:
                df_nouveau = pd.DataFrame(warnings_nouveau_socle)
                filter_nouveau = st.text_input("Filtrer (commune, COG, type, détail)", key="filter_warn_nouveau")
                if filter_nouveau:
                    q = filter_nouveau.lower()
                    df_nouveau = df_nouveau[
                        df_nouveau["Commune"].astype(str).str.lower().str.contains(q, na=False)
                        | df_nouveau["COG"].astype(str).str.contains(q, na=False)
                        | df_nouveau["Type"].astype(str).str.lower().str.contains(q, na=False)
                        | df_nouveau["Détail"].astype(str).str.lower().str.contains(q, na=False)
                    ]
                st.dataframe(
                    df_nouveau,
                    use_container_width=True,
                    height=400,
                    column_config={"Détail": st.column_config.TextColumn("Détail", width="large")},
                )
                st.metric("Nombre d’autres warnings", len(df_nouveau))

st.divider()
st.markdown('[← Retour au suivi BAN (carte)](/)')
