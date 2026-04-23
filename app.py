import streamlit as st
import streamlit.components.v1 as components

# Configuration
st.set_page_config(
    page_title="Suivi BAN - IGN", 
    page_icon="🗺️", 
    layout="wide", 
    initial_sidebar_state="collapsed"
)

# CSS pour plein écran
st.markdown("""
<style>
    [data-testid="collapsedControl"] {display: none}
    .main .block-container {padding: 0 !important; max-width: 100% !important;}
    header {display: none !important;}
    footer {display: none !important;}
</style>
""", unsafe_allow_html=True)

# URL de l'API
# En K8s : "" (URL relative via Ingress)
# En local : "http://localhost:8000"
import os
import base64
API_URL = os.getenv("API_URL", "http://localhost:8000")

# Charger le logo BAN en base64
def load_logo_base64():
    logo_path = os.path.join(os.path.dirname(__file__), "data", "BAN.png")
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    return None

BAN_LOGO_BASE64 = load_logo_base64()

# Préparer le HTML du logo
logo_html = f'<img src="data:image/png;base64,{BAN_LOGO_BASE64}" alt="BAN" class="logo-ban" />' if BAN_LOGO_BASE64 else ''

# HTML complet de l'application
app_html = f"""
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Suivi BAN - IGN</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://unpkg.com/leaflet.vectorgrid@1.3.0/dist/Leaflet.VectorGrid.bundled.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Source+Sans+Pro:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        body {{ 
            font-family: 'Source Sans Pro', -apple-system, sans-serif;
            background: #f5f5f5;
            overflow: hidden;
        }}
        
        /* === LAYOUT === */
        .app {{ display: flex; height: 100vh; }}
        
        /* === SIDEBAR === */
        .sidebar {{
            width: 380px;
            background: white; 
            border-right: 1px solid #e0e0e0;
            display: flex;
            flex-direction: column;
            z-index: 1000;
        }}
        
        /* Header */
        .header {{
            background: linear-gradient(135deg, #000091 0%, #1212ff 100%);
            padding: 20px;
            color: white;
            display: flex;
            flex-direction: column;
        }}
        
        .header-top {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            width: 100%;
        }}
        
        .header-right {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .header h1 {{
            font-size: 16px;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 8px;
            white-space: nowrap;
        }}
        
        .header p {{
            font-size: 12px;
            opacity: 0.8;
            margin-top: 4px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .badge {{
            background: rgba(255,255,255,0.2);
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 10px;
            white-space: nowrap;
        }}
        
        .logo-ban {{
            height: 28px;
            width: auto;
            object-fit: contain;
            filter: brightness(0) invert(1);
            opacity: 0.9;
            flex-shrink: 0;
        }}
        
        .header-logos {{
            display: flex;
            align-items: center;
            gap: 8px;
            white-space: nowrap;
        }}
        
        .header-logos span {{
            white-space: nowrap;
        }}
        
        /* Info bar */
        .info-bar {{
            position: absolute;
            top: 10px;
            left: 60px;
            background: #E3F2FD;
            border: 1px solid #BBDEFB;
            border-radius: 8px;
            padding: 12px 18px;
            display: flex;
            align-items: flex-start;
            gap: 12px;
            font-size: 13px;
            color: #1565C0;
            z-index: 1000;
            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
            max-width: 95%;
            width: auto;
            white-space: nowrap;
        }}
        
        .info-bar-content > div {{
            white-space: normal;
        }}
        
        .info-bar-content {{
            display: flex;
            flex-direction: column;
            gap: 4px;
        }}
        
        .info-bar.hidden {{
            display: none;
        }}
        
        .info-bar-content {{
            flex: 1;
            line-height: 1.4;
        }}
        
        .info-bar-close {{
            background: none;
            border: none;
            color: #1565C0;
            cursor: pointer;
            font-size: 18px;
            padding: 0;
            width: 20px;
            height: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            opacity: 0.7;
            transition: opacity 0.2s;
            font-weight: bold;
        }}
        
        .info-bar-close:hover {{
            opacity: 1;
        }}
        
        /* Stats */
        .stats-bar {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 8px;
            padding: 16px;
            background: #fafafa;
            border-bottom: 1px solid #e0e0e0;
        }}
        
        .stat {{ text-align: center; }}
        .stat-value {{ font-size: 20px; font-weight: 700; color: #1a1a1a; }}
        .stat-label {{ font-size: 10px; color: #666; text-transform: uppercase; letter-spacing: 0.5px; }}
        
        /* Search */
        .search-box {{
            padding: 16px;
            border-bottom: 1px solid #e0e0e0;
        }}
        
        .search-input {{
            width: 100%;
            padding: 12px 16px 12px 44px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 14px;
            background: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='20' height='20' viewBox='0 0 24 24' fill='none' stroke='%23999' stroke-width='2'%3E%3Ccircle cx='11' cy='11' r='8'/%3E%3Cpath d='m21 21-4.35-4.35'/%3E%3C/svg%3E") no-repeat 14px center;
            transition: all 0.2s;
        }}
        
        .search-input:focus {{
            outline: none;
            border-color: #000091;
            box-shadow: 0 0 0 3px rgba(0,0,145,0.1);
        }}
        
        .search-results {{
            position: absolute;
            top: 100%;
            left: 0;
            right: 0;
            background: white;
            border: 1px solid #e0e0e0;
            border-radius: 10px;
            margin-top: 4px;
            max-height: 300px;
            overflow-y: auto;
            box-shadow: 0 10px 40px rgba(0,0,0,0.15);
            display: none;
            z-index: 100;
        }}
        
        .search-results.active {{ display: block; }}
        
        .search-result {{
            padding: 12px 16px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 12px;
            border-bottom: 1px solid #f0f0f0;
        }}
        
        .search-result:hover {{ background: #f5f5f5; }}
        .search-result:last-child {{ border-bottom: none; }}
        
        .result-dot {{
            width: 12px;
            height: 12px;
            border-radius: 50%;
            flex-shrink: 0;
        }}
        
        .result-info {{ flex: 1; }}
        .result-name {{ font-weight: 600; color: #1a1a1a; }}
        .result-meta {{ font-size: 12px; color: #666; }}
        
        /* Filters */
        .filters {{
            padding: 16px;
            border-bottom: 1px solid #e0e0e0;
        }}
        
        .filter-title {{
            font-size: 11px;
            font-weight: 600;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 10px;
        }}
        
        .select-wrap {{ position: relative; }}
        
        .select {{
            width: 100%;
            padding: 10px 14px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 14px;
            appearance: none;
            background: white url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='%23666'%3E%3Cpath d='M7 10l5 5 5-5z'/%3E%3C/svg%3E") no-repeat right 12px center;
            cursor: pointer;
        }}
        
        .select:focus {{ outline: none; border-color: #000091; }}
        
        /* Status chips */
        .status-chips {{
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-top: 10px;
        }}
        
        .chip {{
            display: flex;
            align-items: center;
            gap: 5px;
            padding: 5px 10px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 600;
            cursor: pointer;
            border: 2px solid transparent;
            transition: all 0.15s;
        }}
        
        .chip.active {{ border-color: currentColor; }}
        .chip.inactive {{ opacity: 0.35; }}
        
        .chip-dot {{ width: 10px; height: 10px; border-radius: 50%; }}
        
        .chip-vert {{ background: #e8f5e9; color: #2e7d32; }}
        .chip-vert .chip-dot {{ background: #2e7d32; }}
        
        .chip-orange {{ background: #fff3e0; color: #e65100; }}
        .chip-orange .chip-dot {{ background: #e65100; }}
        
        .chip-rouge {{ background: #ffebee; color: #c62828; }}
        .chip-rouge .chip-dot {{ background: #c62828; }}
        
        .chip-gris {{ background: #f5f5f5; color: #616161; }}
        .chip-gris .chip-dot {{ background: #616161; }}
        
        /* Breadcrumb */
        .breadcrumb {{
            padding: 12px 16px;
            background: #fafafa;
            border-bottom: 1px solid #e0e0e0;
            font-size: 13px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .bc-item {{ color: #000091; cursor: pointer; }}
        .bc-item:hover {{ text-decoration: underline; }}
        .bc-sep {{ color: #999; }}
        .bc-current {{ color: #1a1a1a; font-weight: 600; }}
        
        /* Info panel */
        .info-panel {{
            flex: 1;
            overflow-y: auto;
            padding: 16px;
        }}
        
        .card {{
            background: #fafafa;
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 12px;
        }}
        
        .card h3 {{
            font-size: 15px;
            font-weight: 600;
            color: #1a1a1a;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .info-row {{
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #e8e8e8;
            font-size: 13px;
        }}
        
        .info-row:last-child {{ border-bottom: none; }}
        .info-label {{ color: #666; }}
        .info-value {{ font-weight: 600; color: #1a1a1a; }}
        
        /* Status badge */
        .status-badge {{
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 3px 10px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 600;
        }}
        
        .badge-vert {{ background: #e8f5e9; color: #2e7d32; }}
        .badge-orange {{ background: #fff3e0; color: #e65100; }}
        .badge-rouge {{ background: #ffebee; color: #c62828; }}
        .badge-jaune {{ background: #fffde7; color: #f9a825; }}
        .badge-gris {{ background: #f5f5f5; color: #616161; }}
        
        /* Buttons */
        .btn {{
            padding: 10px 18px;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            border: none;
            transition: all 0.15s;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }}
        
        .btn-primary {{ background: #000091; color: white; }}
        .btn-primary:hover {{ background: #1212ff; }}
        
        .btn-secondary {{ background: #e0e0e0; color: #1a1a1a; }}
        .btn-secondary:hover {{ background: #d0d0d0; }}
        
        .btn-group {{ display: flex; gap: 8px; margin-top: 16px; }}
        
        /* Communes list */
        .communes-list {{ max-height: 300px; overflow-y: auto; }}
        
        .commune-item {{
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 10px 12px;
            border-radius: 8px;
            cursor: pointer;
            transition: background 0.15s;
        }}
        
        .commune-item:hover {{ background: #e8e8e8; }}
        
        .commune-dot {{ width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }}
        .commune-name {{ font-size: 13px; font-weight: 500; color: #1a1a1a; }}
        .commune-pop {{ font-size: 11px; color: #666; }}
        
        /* Empty state */
        .empty {{
            text-align: center;
            padding: 40px 20px;
            color: #999;
        }}
        
        .empty svg {{ margin-bottom: 16px; opacity: 0.4; }}
        
        /* Loading */
        .loading {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            padding: 20px;
            color: #666;
        }}
        
        .spinner {{
            width: 20px;
            height: 20px;
            border: 2px solid #e0e0e0;
            border-top-color: #000091;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }}
        
        @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
        
        /* Tooltip survol département (carte) */
        .leaflet-tooltip.dept-map-tooltip {{
            background: rgba(255,255,255,0.97) !important;
            color: #1a1a1a !important;
            border: 1px solid #c5c5c5 !important;
            border-radius: 8px !important;
            padding: 10px 12px !important;
            box-shadow: 0 4px 16px rgba(0,0,0,0.18) !important;
            font-family: 'Source Sans Pro', sans-serif !important;
            font-size: 13px !important;
            max-width: 220px !important;
        }}
        .leaflet-tooltip.dept-map-tooltip .leaflet-tooltip-content {{
            margin: 0 !important;
        }}
        
        .leaflet-tooltip.commune-map-tooltip {{
            background: rgba(255,255,255,0.97) !important;
            color: #1a1a1a !important;
            border: 1px solid #c5c5c5 !important;
            border-radius: 6px !important;
            padding: 6px 10px !important;
            box-shadow: 0 2px 10px rgba(0,0,0,0.15) !important;
            font-family: 'Source Sans Pro', sans-serif !important;
            font-size: 13px !important;
        }}
        
        /* === MAP === */
        #map {{ flex: 1; height: 100vh; position: relative; }}
        
        .map-container {{
            flex: 1;
            position: relative;
            height: 100vh;
        }}
        
        /* Map controls */
        .map-controls {{
            position: absolute;
            top: 20px;
            right: 20px;
            z-index: 1000;
            display: flex;
            flex-direction: column;
            gap: 2px;
        }}
        
        .map-btn {{
            width: 40px;
            height: 40px;
            background: white;
            border: none;
            font-size: 20px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 2px 6px rgba(0,0,0,0.15);
        }}
        
        .map-btn:first-child {{ border-radius: 8px 8px 0 0; }}
        .map-btn:last-child {{ border-radius: 0 0 8px 8px; }}
        .map-btn:hover {{ background: #f5f5f5; }}
        
        /* Legend */
        .legend {{
            position: absolute;
            bottom: 30px;
            left: 400px;
            background: white;
            padding: 12px 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            z-index: 1000;
            display: flex;
            gap: 20px;
            font-size: 12px;
        }}
        
        .legend-item {{ display: flex; align-items: center; gap: 6px; }}
        .legend-dot {{ width: 12px; height: 12px; border-radius: 50%; }}
        .legend-label {{ color: #666; }}
        
        /* Zoom indicator */
        .zoom-indicator {{
            position: absolute;
            bottom: 30px;
            right: 20px;
            background: white;
            padding: 8px 14px;
            border-radius: 8px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.1);
            z-index: 1000;
            font-size: 12px;
            color: #666;
        }}
        
        .zoom-indicator strong {{ color: #000091; font-size: 14px; }}
        
        /* Territory selector */
        .territory-selector {{
            position: absolute;
            top: 70px;
            right: 20px;
            z-index: 1000;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
            overflow: hidden;
        }}
        
        .territory-selector select {{
            border: none;
            padding: 10px 40px 10px 15px;
            font-size: 13px;
            font-weight: 600;
            color: #1a1a1a;
            background: white;
            cursor: pointer;
            appearance: none;
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%23666' d='M6 9L1 4h10z'/%3E%3C/svg%3E");
            background-repeat: no-repeat;
            background-position: right 12px center;
        }}
        
        .territory-selector select:hover {{
            background-color: #f5f5f5;
        }}
        
        .territory-selector select:focus {{
            outline: none;
            box-shadow: 0 0 0 2px rgba(0,0,145,0.2);
        }}
        
        /* Leaflet overrides */
        .leaflet-control-zoom {{ 
            border: none !important;
            box-shadow: 0 2px 8px rgba(0,0,0,0.15) !important;
            border-radius: 8px !important;
        }}
        .leaflet-popup-content-wrapper {{ border-radius: 10px; }}
        .leaflet-popup-content {{ margin: 14px; }}
        
        
        /* Scrollbar */
        ::-webkit-scrollbar {{ width: 6px; }}
        ::-webkit-scrollbar-track {{ background: #f5f5f5; }}
        ::-webkit-scrollbar-thumb {{ background: #ccc; border-radius: 3px; }}
    </style>
</head>
<body>
    <div class="app">
        <!-- Sidebar -->
        <div class="sidebar">
            <div class="header">
                <h1>
                    <span class="header-logos">
                        <span>Suivi du déploiement des identifiants uniques</span>
                    </span>
                </h1>
                <p>
                    <span>Base Adresse Nationale - Tableau de bord</span>
                    <span class="header-right">
                        {logo_html}
                        <span class="badge">IGN</span>
                    </span>
                </p>
            </div>
            
            <div class="stats-bar" id="statsBar">
                <div class="stat">
                    <div class="stat-value" id="statTotal">-</div>
                    <div class="stat-label">Communes</div>
                </div>
                <div class="stat">
                    <div class="stat-value" id="statVert" style="color:#2e7d32">-</div>
                    <div class="stat-label">% Vert</div>
                </div>
                <div class="stat">
                    <div class="stat-value" id="statNumeros">-</div>
                    <div class="stat-label">Numéros</div>
                </div>
                <div class="stat">
                    <div class="stat-value" id="statVoies">-</div>
                    <div class="stat-label">Voies</div>
        </div>
    </div>
    
            <div class="search-box" style="position: relative;">
                <input type="text" class="search-input" id="searchInput" placeholder="Nom ou code INSEE...">
                <div class="search-results" id="searchResults"></div>
            </div>
            
            <div class="filters">
                <div class="filter-title">Producteur</div>
                <div class="select-wrap">
                    <select class="select" id="producteurSelect">
                        <option value="">Tous les producteurs</option>
                    </select>
            </div>
                
                <div class="filter-title" style="margin-top: 16px;">Statuts</div>
                <div class="status-chips">
                    <div class="chip chip-vert active" data-status="vert" onclick="toggleStatus('vert')" title="ID fiabilisés">
                        <span class="chip-dot"></span> ID fiabilisés
            </div>
                    <div class="chip chip-orange active" data-status="orange" onclick="toggleStatus('orange')" title="ID initiés à contrôler">
                        <span class="chip-dot"></span> ID initiés à contrôler
            </div>
                    <div class="chip chip-rouge active" data-status="rouge" onclick="toggleStatus('rouge')" title="ID non initiés">
                        <span class="chip-dot"></span> ID non initiés
            </div>
                    <div class="chip chip-gris active" data-status="gris" onclick="toggleStatus('gris')" title="Sans donnée">
                        <span class="chip-dot"></span> Sans donnée
            </div>
        </div>
        
        
                <div class="btn-group">
            <button class="btn btn-secondary" onclick="resetFilters()">Réinitialiser</button>
        </div>
    </div>
    
            <div class="breadcrumb" id="breadcrumb">
                <span class="bc-current">🇫🇷 France</span>
            </div>
            
            <div class="info-panel" id="infoPanel">
                <div id="globalStats">
                    <div class="card" style="text-align:center; padding:20px;">
                        <div class="spinner"></div>
                        <p style="margin-top:10px; color:#666;">Chargement des statistiques...</p>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Map -->
        <div class="map-container">
            <div class="info-bar" id="infoBar">
                <div class="info-bar-content">
                    <div><strong>🔄 Actualisation quotidienne</strong> : Données mises à jour chaque jour à 2h du matin.</div>
                    <div><strong>💡 Évolution des statuts</strong> : Les communes passent progressivement de l'orange au vert après vérification de l'intégrité de leurs identifiants.</div>
                </div>
                <button class="info-bar-close" onclick="closeInfoBar()" title="Fermer">×</button>
            </div>
            <div id="map"></div>
        </div>
    </div>
    
    
    <!-- Legend -->
    <div class="legend">
        <div class="legend-item">
            <span class="legend-dot" style="background:#2e7d32"></span>
            <span class="legend-label">ID fiabilisés</span>
        </div>
        <div class="legend-item">
            <span class="legend-dot" style="background:#e65100"></span>
            <span class="legend-label">ID initiés à contrôler</span>
        </div>
        <div class="legend-item">
            <span class="legend-dot" style="background:#c62828"></span>
            <span class="legend-label">ID non initiés</span>
        </div>
        <div class="legend-item">
            <span class="legend-dot" style="background:#616161"></span>
            <span class="legend-label">Sans donnée</span>
        </div>
    </div>
    
    <!-- Zoom indicator -->
    <div class="zoom-indicator">
        Zoom: <strong id="zoomLevel">6</strong>
    </div>
    
    <!-- Territory selector -->
    <div class="territory-selector">
        <select id="territorySelector" onchange="navigateToTerritory(this.value)">
            <option value="">Naviguer vers...</option>
            <option value="france">France métropolitaine</option>
            <optgroup label="DOM-TOM">
                <option value="971">971 - Guadeloupe</option>
                <option value="972">972 - Martinique</option>
                <option value="973">973 - Guyane</option>
                <option value="974">974 - La Réunion</option>
                <option value="976">976 - Mayotte</option>
                <option value="975">975 - Saint-Pierre-et-Miquelon</option>
                <option value="977">977 - Saint-Barthélemy</option>
                <option value="978">978 - Saint-Martin</option>
                <option value="988">988 - Nouvelle-Calédonie</option>
                <option value="987">987 - Polynésie française</option>
                <option value="986">986 - Wallis-et-Futuna</option>
            </optgroup>
        </select>
    </div>
    
    <script>
        // === CONFIG ===
        const API = "{API_URL}";
        const COLORS = {{
            vert: '#2e7d32',
            orange: '#e65100', 
            rouge: '#c62828',
            jaune: '#f9a825',
            gris: '#616161'
        }};
        
        // === STATE ===
        let currentView = 'france';
        let selectedDept = null;
        let selectedProducteur = null;
        let activeStatuts = ['vert', 'orange', 'rouge', 'gris'];
        
        let departementsStats = {{}};
        let producteurs = [];
        let searchTimeout = null;
        let filteredBanStats = null; // Stats BAN filtrées (numéros, voies)
        window._deptSearchQuery = '';
        
        let departementsLayer = null;
        let communesLayer = null;
        let deptMapHoverTooltip = null;
        let communeMapHoverTooltip = null;
        
        // === MAP ===
        const map = L.map('map', {{ zoomControl: true }}).setView([46.603354, 1.888334], 6);
        
        // Déplacer le zoom par défaut en haut à gauche
        map.zoomControl.setPosition('topleft');
        
        // Fonds de carte IGN uniquement
        const baseLayers = {{
            'Plan IGN': L.tileLayer('https://data.geopf.fr/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2&STYLE=normal&FORMAT=image/png&TILEMATRIXSET=PM&TILEMATRIX={{z}}&TILEROW={{y}}&TILECOL={{x}}', {{
                attribution: '© IGN - Géoportail',
                maxZoom: 19
            }}),
            'Ortho IGN': L.tileLayer('https://data.geopf.fr/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=ORTHOIMAGERY.ORTHOPHOTOS&STYLE=normal&FORMAT=image/jpeg&TILEMATRIXSET=PM&TILEMATRIX={{z}}&TILEROW={{y}}&TILECOL={{x}}', {{
                attribution: '© IGN - Géoportail',
                maxZoom: 19
            }})
        }};
        
        // Fond par défaut : Plan IGN
        baseLayers['Plan IGN'].addTo(map);
        
        // Sélecteur de fond (en haut à droite)
        L.control.layers(baseLayers, {{}}, {{ position: 'topright', collapsed: true }}).addTo(map);
        
        map.on('zoomend', () => {{
            document.getElementById('zoomLevel').textContent = map.getZoom();
        }});
        
        // === NAVIGATION ===
        // Coordonnées des territoires français
        const TERRITOIRES = {{
            'france': {{ lat: 46.603354, lon: 1.888334, zoom: 6, nom: 'France métropolitaine' }},
            '971': {{ lat: 16.265, lon: -61.551, zoom: 9, nom: 'Guadeloupe' }},
            '972': {{ lat: 14.641, lon: -61.024, zoom: 10, nom: 'Martinique' }},
            '973': {{ lat: 3.933, lon: -53.125, zoom: 7, nom: 'Guyane' }},
            '974': {{ lat: -21.115, lon: 55.536, zoom: 10, nom: 'La Réunion' }},
            '976': {{ lat: -12.827, lon: 45.166, zoom: 10, nom: 'Mayotte' }},
            '975': {{ lat: 46.833, lon: -56.333, zoom: 7, nom: 'Saint-Pierre-et-Miquelon' }},
            '977': {{ lat: 17.900, lon: -62.833, zoom: 11, nom: 'Saint-Barthélemy' }},
            '978': {{ lat: 18.070, lon: -63.050, zoom: 11, nom: 'Saint-Martin' }},
            '988': {{ lat: -22.276, lon: 166.457, zoom: 7, nom: 'Nouvelle-Calédonie' }},
            '987': {{ lat: -17.679, lon: -149.406, zoom: 7, nom: 'Polynésie française' }},
            '986': {{ lat: -13.293, lon: -176.199, zoom: 7, nom: 'Wallis-et-Futuna' }}
        }};
        
        // Fonction de navigation vers un territoire
        function navigateToTerritory(code) {{
            // Réinitialiser le sélecteur
            const selector = document.getElementById('territorySelector');
            if (selector) {{
                selector.value = '';
            }}
            
            if (!code) return;
            
            if (code === 'france') {{
                backToFrance();
                return;
            }}
            
            const territoire = TERRITOIRES[code];
            if (!territoire) return;
            
            // Liste des codes DOM-TOM
            const domTomCodes = ['971', '972', '973', '974', '976', '975', '977', '978', '988', '987', '986'];
            
            // Pour les DOM-TOM, zoomer d'abord puis charger les communes
            if (domTomCodes.includes(code)) {{
                // Zoomer sur le territoire
                map.setView([territoire.lat, territoire.lon], territoire.zoom);
                // Puis charger les communes
                selectDepartement(code, territoire.nom || 'Département ' + code);
                return;
            }}
            
            // Métropole : stats déjà chargées
            if (code.length === 3 && departementsStats[code]) {{
                selectDepartement(code, departementsStats[code].nom || ('Département ' + code));
                return;
            }}
            
            // Sinon, juste zoomer
            map.setView([territoire.lat, territoire.lon], territoire.zoom);
        }}
        
        // === API CALLS ===
        async function fetchAPI(endpoint) {{
            try {{
                const res = await fetch(API + endpoint);
                if (!res.ok) throw new Error('API error');
                return await res.json();
            }} catch(e) {{
                console.error('API Error:', e);
                return null;
            }}
        }}
        
        // Stocker les stats globales
        let globalStatsData = null;
        
        // Afficher les stats globales de la France
        function showGlobalStats() {{
            if (!globalStatsData) return;
            
            const stats = globalStatsData;
            
            // Calculer les stats filtrées pour le panneau d'information (en bas)
            let filteredTotal = 0;
            let filteredStats = {{ vert: 0, orange: 0, rouge: 0, gris: 0 }};
            
            // Utiliser departementsStats pour calculer les totaux filtrés
            // Si un filtre producteur est actif, departementsStats contient déjà les stats filtrées
            Object.values(departementsStats).forEach(dept => {{
                activeStatuts.forEach(s => {{
                    filteredStats[s] += (dept[s] || 0);
                    filteredTotal += (dept[s] || 0);
                }});
            }});
            
            const isFiltered = activeStatuts.length < 4 || selectedProducteur;
            
            // La barre supérieure garde toujours les stats globales (non filtrées)
            // On ne modifie pas statTotal et statVert ici
            
            // Calculer les numéros et voies filtrés
            let filteredNumeros = stats.numeros || 0;
            let filteredVoies = stats.voies || 0;
            
            if (selectedProducteur && filteredBanStats) {{
                // Utiliser les stats filtrées du producteur
                filteredNumeros = filteredBanStats.numeros || 0;
                filteredVoies = filteredBanStats.voies || 0;
            }} else if (selectedProducteur) {{
                // Calculer à partir des départements filtrés
                filteredNumeros = 0;
                filteredVoies = 0;
                Object.values(departementsStats).forEach(dept => {{
                    filteredNumeros += (dept.numeros || 0);
                    filteredVoies += (dept.voies || 0);
                }});
            }}
            
            document.getElementById('infoPanel').innerHTML = `
                <div class="card" style="background: linear-gradient(135deg, #000091 0%, #1212ff 100%); color: white; padding: 20px;">
                    <h3 style="color:white; margin-bottom:15px;">🇫🇷 France entière</h3>
                    <div style="font-size:32px; font-weight:700;">${{isFiltered ? filteredTotal.toLocaleString() : stats.total.toLocaleString()}}</div>
                    <div style="font-size:13px; opacity:0.9;">communes ${{isFiltered ? '(filtrées)' : ''}}</div>
                </div>
                
                <div class="card">
                    <h3>📊 Répartition par statut</h3>
                    <div style="margin:15px 0;">
                        <div style="display:flex; height:20px; border-radius:10px; overflow:hidden;">
                            ${{activeStatuts.includes('vert') ? `<div style="width:${{(filteredStats.vert / filteredTotal * 100) || 0}}%; background:${{COLORS.vert}};"></div>` : ''}}
                            ${{activeStatuts.includes('orange') ? `<div style="width:${{(filteredStats.orange / filteredTotal * 100) || 0}}%; background:${{COLORS.orange}};"></div>` : ''}}
                            ${{activeStatuts.includes('rouge') ? `<div style="width:${{(filteredStats.rouge / filteredTotal * 100) || 0}}%; background:${{COLORS.rouge}};"></div>` : ''}}
                            ${{activeStatuts.includes('gris') ? `<div style="width:${{(filteredStats.gris / filteredTotal * 100) || 0}}%; background:${{COLORS.gris}};"></div>` : ''}}
                        </div>
                    </div>
                    
                    <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px;">
                        <div style="display:flex; align-items:center; gap:8px; padding:10px; background:#e8f5e9; border-radius:8px; opacity:${{activeStatuts.includes('vert') ? 1 : 0.4}};">
                            <span style="width:12px; height:12px; background:${{COLORS.vert}}; border-radius:50%;"></span>
                            <div>
                                <div style="font-weight:700; color:#2e7d32;">${{filteredStats.vert.toLocaleString()}}</div>
                                <div style="font-size:10px; color:#2e7d32;">ID fiabilisés</div>
                            </div>
                        </div>
                        <div style="display:flex; align-items:center; gap:8px; padding:10px; background:#fff3e0; border-radius:8px; opacity:${{activeStatuts.includes('orange') ? 1 : 0.4}};">
                            <span style="width:12px; height:12px; background:${{COLORS.orange}}; border-radius:50%;"></span>
                            <div>
                                <div style="font-weight:700; color:#e65100;">${{filteredStats.orange.toLocaleString()}}</div>
                                <div style="font-size:10px; color:#e65100;">ID initiés à contrôler</div>
                            </div>
                        </div>
                        <div style="display:flex; align-items:center; gap:8px; padding:10px; background:#ffebee; border-radius:8px; opacity:${{activeStatuts.includes('rouge') ? 1 : 0.4}};">
                            <span style="width:12px; height:12px; background:${{COLORS.rouge}}; border-radius:50%;"></span>
                            <div>
                                <div style="font-weight:700; color:#c62828;">${{filteredStats.rouge.toLocaleString()}}</div>
                                <div style="font-size:10px; color:#c62828;">ID non initiés</div>
                            </div>
                        </div>
                        <div style="display:flex; align-items:center; gap:8px; padding:10px; background:#f5f5f5; border-radius:8px; opacity:${{activeStatuts.includes('gris') ? 1 : 0.4}}; grid-column: span 2;">
                            <span style="width:12px; height:12px; background:${{COLORS.gris}}; border-radius:50%;"></span>
                            <div>
                                <div style="font-weight:700; color:#616161;">${{filteredStats.gris.toLocaleString()}}</div>
                                <div style="font-size:10px; color:#616161;">Sans donnée</div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <h3>📈 Données BAN</h3>
                    <div class="info-row">
                        <span class="info-label">Numéros d'adresses</span>
                        <span class="info-value">${{isFiltered ? filteredNumeros.toLocaleString() : (stats.numeros || 0).toLocaleString()}}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Voies</span>
                        <span class="info-value">${{isFiltered ? filteredVoies.toLocaleString() : (stats.voies || 0).toLocaleString()}}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Départements</span>
                        <span class="info-value">${{Object.keys(departementsStats).length}}</span>
                    </div>
                </div>
                
                <div style="text-align:center; padding:15px; color:#666; font-size:12px;">
                    👆 Cliquez sur un département pour voir le détail
                </div>
            `;
        }}
        
        // === INFO BAR ===
        function closeInfoBar() {{
            const infoBar = document.getElementById('infoBar');
            if (infoBar) {{
                infoBar.classList.add('hidden');
                // Ne pas sauvegarder la préférence - réafficher à chaque fois
            }}
        }}
        
        // === INIT ===
        async function init() {{
            // La barre d'info sera toujours affichée par défaut (pas de vérification localStorage)
            // Load stats
            const stats = await fetchAPI('/api/stats/global');
            if (stats) {{
                globalStatsData = stats;
                document.getElementById('statTotal').textContent = stats.total.toLocaleString();
                document.getElementById('statVert').textContent = stats.pct_vert + '%';
                document.getElementById('statNumeros').textContent = (stats.numeros || 0).toLocaleString();
                document.getElementById('statVoies').textContent = (stats.voies || 0).toLocaleString();
            }}
            
            // Load departements stats
            departementsStats = await fetchAPI('/api/stats/departements') || {{}};
            showDepartementsVector();
            showGlobalStats();
            
            // Load producteurs
            producteurs = await fetchAPI('/api/producteurs') || [];
            const select = document.getElementById('producteurSelect');
            producteurs.forEach(p => {{
                const opt = document.createElement('option');
                opt.value = p.nom;
                opt.textContent = `${{p.nom}} (${{p.nb_communes}} communes)`;
                select.appendChild(opt);
            }});
            
            // Event listeners
            document.getElementById('producteurSelect').addEventListener('change', onProducteurChange);
            document.getElementById('searchInput').addEventListener('input', onSearch);
        }}
        
        // === DEPARTEMENTS (tuiles vectorielles PBF) ===
        function vectorTileStyleDepartement(props) {{
            const code = String(props.code || '');
            const stats = departementsStats[code];
            if (!stats || stats.total === 0) {{
                return {{ fill: true, fillColor: '#e0e0e0', stroke: true, color: '#bdbdbd', weight: 1, fillOpacity: 0.4 }};
            }}
            const statuts = [
                {{ key: 'vert', value: stats.vert || 0, color: COLORS.vert }},
                {{ key: 'orange', value: stats.orange || 0, color: COLORS.orange }},
                {{ key: 'rouge', value: stats.rouge || 0, color: COLORS.rouge }},
                {{ key: 'gris', value: stats.gris || 0, color: COLORS.gris }}
            ].filter(s => activeStatuts.includes(s.key)).sort((a, b) => b.value - a.value);
            if (statuts.length === 0 || statuts.every(s => s.value === 0)) {{
                return {{ fill: true, fillColor: '#e0e0e0', stroke: true, color: '#bdbdbd', weight: 1, fillOpacity: 0.2 }};
            }}
            const activeTotal = statuts.reduce((sum, s) => sum + s.value, 0);
            if (activeTotal === 0) {{
                return {{ fill: true, fillColor: '#e0e0e0', stroke: true, color: '#bdbdbd', weight: 1, fillOpacity: 0.2 }};
            }}
            const dominant = statuts[0];
            const pctDominant = dominant.value / activeTotal;
            const opacity = 0.3 + (pctDominant * 0.55);
            return {{ fill: true, fillColor: dominant.color, stroke: true, color: '#fff', weight: 1, fillOpacity: opacity }};
        }}
        
        function buildDeptMapTooltipHtml(code, props) {{
            const stats = departementsStats[code];
            const nom = (stats && stats.nom) ? stats.nom : (props.nom || code);
            if (!stats || !stats.total) {{
                return `<div><b>${{nom}}</b><br><span style="color:#888;font-size:12px;font-style:italic;">Aucune donnée</span></div>`;
            }}
            const t = stats.total;
            const pcts = {{
                vert: Math.round((stats.vert || 0) / t * 100),
                orange: Math.round((stats.orange || 0) / t * 100),
                rouge: Math.round((stats.rouge || 0) / t * 100),
                gris: Math.round((stats.gris || 0) / t * 100)
            }};
            return `<div>
                <b>${{nom}}</b>
                <div style="display:flex;height:10px;width:160px;border-radius:5px;overflow:hidden;margin:8px 0;border:1px solid #ddd;">
                    <div style="width:${{pcts.vert}}%;background:${{COLORS.vert}};"></div>
                    <div style="width:${{pcts.orange}}%;background:${{COLORS.orange}};"></div>
                    <div style="width:${{pcts.rouge}}%;background:${{COLORS.rouge}};"></div>
                    <div style="width:${{pcts.gris}}%;background:${{COLORS.gris}};"></div>
                </div>
                <div style="font-size:11px;line-height:1.5;">
                    <span style="color:${{COLORS.vert}}">●</span> ${{pcts.vert}}%
                    <span style="color:${{COLORS.orange}}">●</span> ${{pcts.orange}}%
                    <span style="color:${{COLORS.rouge}}">●</span> ${{pcts.rouge}}%
                    <span style="color:${{COLORS.gris}}">●</span> ${{pcts.gris}}%
                </div>
            </div>`;
        }}
        
        function closeDeptMapHoverTooltip() {{
            if (deptMapHoverTooltip && map) {{
                map.removeLayer(deptMapHoverTooltip);
                deptMapHoverTooltip = null;
            }}
        }}
        
        function closeCommuneMapHoverTooltip() {{
            if (communeMapHoverTooltip && map) {{
                map.removeLayer(communeMapHoverTooltip);
                communeMapHoverTooltip = null;
            }}
        }}
        
        function buildCommuneMapTooltipHtml(props) {{
            const nom = (props.nom && String(props.nom)) || 'Commune';
            const code = (props.code && String(props.code)) || '';
            let sub = '';
            if (code) sub = '<br><span style="font-size:11px;color:#666;">' + code + '</span>';
            return '<div><b>' + nom + '</b>' + sub + '</div>';
        }}
        
        function showDepartementsVector() {{
            closeDeptMapHoverTooltip();
            closeCommuneMapHoverTooltip();
            if (communesLayer) {{
                map.removeLayer(communesLayer);
                communesLayer = null;
            }}
            if (departementsLayer) {{
                map.removeLayer(departementsLayer);
                departementsLayer = null;
            }}
            // Pas de rendererFactory: L.canvas.tile — avec canvas les clics interactive ne partent souvent pas (issue VectorGrid #117)
            departementsLayer = L.vectorGrid.protobuf(API + '/api/tiles/departements/{{z}}/{{x}}/{{y}}.pbf', {{
                vectorTileLayerStyles: {{ departements: vectorTileStyleDepartement }},
                maxNativeZoom: 14,
                interactive: true,
                getFeatureId: f => String(f.properties.code || '')
            }});
            departementsLayer.on('click', e => {{
                closeDeptMapHoverTooltip();
                const code = String(e.layer.properties.code || '');
                const stats = departementsStats[code];
                const nom = (stats && stats.nom) ? stats.nom : (e.layer.properties.nom || code);
                if (stats && stats.total > 0) selectDepartement(code, nom);
            }});
            departementsLayer.on('mouseover', e => {{
                const props = (e.layer && e.layer.properties) || {{}};
                const code = String(props.code || '');
                if (!code || !e.latlng) return;
                closeDeptMapHoverTooltip();
                const html = buildDeptMapTooltipHtml(code, props);
                deptMapHoverTooltip = L.tooltip({{ className: 'dept-map-tooltip', sticky: true, direction: 'top', opacity: 1 }})
                    .setLatLng(e.latlng)
                    .setContent(html)
                    .addTo(map);
            }});
            departementsLayer.on('mousemove', e => {{
                if (deptMapHoverTooltip && e.latlng) deptMapHoverTooltip.setLatLng(e.latlng);
            }});
            departementsLayer.on('mouseout', () => closeDeptMapHoverTooltip());
            departementsLayer.addTo(map);
        }}
        
        function vectorTileStyleCommune(props) {{
            const statut = (props.statut || 'gris').toString();
            const q = (window._deptSearchQuery || '').toLowerCase().trim();
            const matchStatut = activeStatuts.includes(statut);
            const matchProd = !selectedProducteur || (String(props.producteur || '') === selectedProducteur);
            const nom = (props.nom || '').toString().toLowerCase();
            const cod = (props.code || '').toString().toLowerCase();
            const matchSearch = !q || nom.includes(q) || cod.includes(q);
            if (matchStatut && matchProd && matchSearch) {{
                return {{ fill: true, fillColor: COLORS[statut] || COLORS.gris, stroke: true, color: '#fff', weight: 1, fillOpacity: 0.72, opacity: 1 }};
            }}
            return {{ fill: true, fillColor: '#888888', stroke: false, fillOpacity: 0.04, opacity: 0.12 }};
        }}
        
        function showCommunesVector(deptCode) {{
            closeDeptMapHoverTooltip();
            closeCommuneMapHoverTooltip();
            if (departementsLayer) {{
                map.removeLayer(departementsLayer);
                departementsLayer = null;
            }}
            if (communesLayer) {{
                map.removeLayer(communesLayer);
                communesLayer = null;
            }}
            const url = API + '/api/tiles/departement/' + deptCode + '/{{z}}/{{x}}/{{y}}.pbf';
            communesLayer = L.vectorGrid.protobuf(url, {{
                vectorTileLayerStyles: {{ communes: vectorTileStyleCommune }},
                maxNativeZoom: 14,
                interactive: true,
                getFeatureId: f => String(f.properties.code || '')
            }});
            communesLayer.on('click', e => {{
                closeCommuneMapHoverTooltip();
                const p = e.layer.properties || {{}};
                const lat = parseFloat(p.lat);
                const lon = parseFloat(p.lon);
                if (!isNaN(lat) && !isNaN(lon)) map.setView([lat, lon], 14);
                showCommuneInfo({{
                    ...p,
                    statut: p.statut || 'gris',
                    dept: selectedDept,
                    dept_nom: window._currentDeptNom || ''
                }});
            }});
            communesLayer.on('mouseover', e => {{
                const p = (e.layer && e.layer.properties) || {{}};
                if (!e.latlng) return;
                const statut = (p.statut || 'gris').toString();
                const q = (window._deptSearchQuery || '').toLowerCase().trim();
                const matchStatut = activeStatuts.includes(statut);
                const matchProd = !selectedProducteur || (String(p.producteur || '') === selectedProducteur);
                const nomL = (p.nom || '').toString().toLowerCase();
                const codL = (p.code || '').toString().toLowerCase();
                const matchSearch = !q || nomL.includes(q) || codL.includes(q);
                if (!(matchStatut && matchProd && matchSearch)) return;
                closeCommuneMapHoverTooltip();
                communeMapHoverTooltip = L.tooltip({{ className: 'commune-map-tooltip', sticky: true, direction: 'top', opacity: 1 }})
                    .setLatLng(e.latlng)
                    .setContent(buildCommuneMapTooltipHtml(p))
                    .addTo(map);
            }});
            communesLayer.on('mousemove', e => {{
                if (communeMapHoverTooltip && e.latlng) communeMapHoverTooltip.setLatLng(e.latlng);
            }});
            communesLayer.on('mouseout', () => closeCommuneMapHoverTooltip());
            communesLayer.addTo(map);
        }}
        
        function refreshCommunesVector() {{
            if (currentView === 'departement' && selectedDept) showCommunesVector(selectedDept);
        }}
        
        // Trouve la couleur dominante SANS filtre (tous statuts)
        function getOriginalDominant(stats) {{
            let max = 0, dominant = 'gris';
            ['vert', 'orange', 'rouge', 'gris'].forEach(s => {{
                if ((stats[s] || 0) > max) {{
                    max = stats[s];
                    dominant = s;
                    }}
                }});
            return dominant;
        }}
        
        // Couleur dominante parmi les statuts actifs (pour d'autres usages)
        function getDominantColor(stats) {{
            let max = 0, dominant = 'gris';
            activeStatuts.forEach(s => {{
                if ((stats[s] || 0) > max) {{
                    max = stats[s];
                    dominant = s;
                }}
            }});
            return COLORS[dominant];
        }}
        
        // === SELECT DEPARTEMENT ===
        async function selectDepartement(code, nom) {{
            selectedDept = code;
            currentView = 'departement';
            
            // Restaurer le sidebar original si nécessaire
            if (window._originalSidebarContent) {{
                document.querySelector('.sidebar').innerHTML = window._originalSidebarContent;
                window._originalSidebarContent = null;
                // Réattacher les events
                document.getElementById('producteurSelect').addEventListener('change', onProducteurChange);
                document.getElementById('searchInput').addEventListener('input', onSearch);
            }}
            
            // Restaurer les filtres visuellement dans la vue département
            setTimeout(() => {{
                // Restaurer le filtre producteur
                const prodSelect = document.getElementById('producteurSelect');
                if (prodSelect && selectedProducteur) {{
                    prodSelect.value = selectedProducteur;
                }}
                
                // Restaurer les chips de statut
                document.querySelectorAll('.chip').forEach(chip => {{
                    if (!chip) return;
                    const statut = chip.getAttribute('data-status');
                    if (statut && activeStatuts.includes(statut)) {{
                        chip.classList.add('active');
                        chip.classList.remove('inactive');
                    }} else if (statut) {{
                        chip.classList.remove('active');
                        chip.classList.add('inactive');
                    }}
                }});
            }}, 50);
            
            // Update breadcrumb (si existe)
            const breadcrumb = document.getElementById('breadcrumb');
            if (breadcrumb) {{
                breadcrumb.innerHTML = `
                    <span class="bc-item" onclick="backToFrance()">🇫🇷 France</span>
                    <span class="bc-sep">›</span>
                    <span class="bc-current">${{nom || 'Département'}} (${{code}})</span>
                `;
            }}
            
            // Show loading (si existe)
            const infoPanel = document.getElementById('infoPanel');
            if (infoPanel) {{
                infoPanel.innerHTML = `
                    <div class="loading"><div class="spinner"></div> Chargement des communes...</div>
                `;
            }}
            
            window._currentDeptNom = nom || (departementsStats[code] && departementsStats[code].nom) || ('Département ' + code);
            const bounds = await fetchAPI(`/api/departement/${{code}}/bounds`);
            if (bounds && bounds.southwest && bounds.northeast) {{
                map.fitBounds([bounds.southwest, bounds.northeast], {{ padding: [50, 50] }});
            }} else if (TERRITOIRES[code]) {{
                const t = TERRITOIRES[code];
                map.setView([t.lat, t.lon], t.zoom);
            }}
            const metaRes = await fetchAPI(`/api/departement/${{code}}/communes-meta`);
            if (infoPanel) infoPanel.innerHTML = '';
            if (!metaRes || !metaRes.communes) return;
            const allCommunes = metaRes.communes;
            window._currentDeptCommunes = allCommunes;
            window._currentDeptTotal = metaRes.total || allCommunes.length;
            showCommunesVector(code);
            showDeptInfo(code, window._currentDeptNom, allCommunes);
            setTimeout(() => {{
                let filtered = allCommunes.filter(c => activeStatuts.includes(c.statut || 'gris'));
                if (selectedProducteur) {{
                    filtered = filtered.filter(c => c.producteur === selectedProducteur);
                }}
                updateCommunesList(filtered);
                const countEl = document.getElementById('communesCount');
                if (countEl) {{
                    countEl.textContent = filtered.length !== allCommunes.length
                        ? `📋 Communes (${{filtered.length}}/${{allCommunes.length}})`
                        : `📋 Communes (${{allCommunes.length}})`;
                }}
                updateDeptFilters();
                refreshCommunesVector();
            }}, 100);
        }}
        
        // === INFO PANELS ===
        function showDeptInfo(code, nom, communesList) {{
            const communes = Array.isArray(communesList) ? communesList : [];
            const stats = {{ vert: 0, orange: 0, rouge: 0, jaune: 0, gris: 0 }};
            
            communes.forEach(c => {{
                const s = c.statut || 'gris';
                stats[s] = (stats[s] || 0) + 1;
            }});
            
            const total = communes.length;
            const allCommunesProps = communes;
            
            // Stocker TOUTES les communes (non filtrées) pour les filtres
            // Utiliser les communes déjà stockées dans selectDepartement si disponibles
            if (!window._currentDeptCommunes || window._currentDeptCommunes.length === 0) {{
                window._currentDeptCommunes = allCommunesProps;
                window._currentDeptTotal = total;
            }}
            
            // Filtrer les communes selon les statuts actifs pour l'affichage initial
            const filteredCommunes = allCommunesProps.filter(c => activeStatuts.includes(c.statut || 'gris'));
            
            const filteredCount = filteredCommunes.length;
            
            // Sort by population desc (sur les communes filtrées pour l'affichage)
            const sorted = filteredCommunes
                .sort((a, b) => (b.population || 0) - (a.population || 0));
            
            // Remplacer tout le panneau par un affichage pleine page
            const sidebar = document.querySelector('.sidebar');
            const originalContent = sidebar.innerHTML;
            
            let communesHtml = '';
            if (sorted.length === 0) {{
                communesHtml = `<p style="color:#999; text-align:center; padding:30px; font-size:13px;">Aucune commune avec les filtres actuels</p>`;
            }} else {{
                sorted.forEach(c => {{
                    communesHtml += `
                        <div class="commune-item" onclick="goToCommune('${{c.code}}')" style="padding:10px 12px; border-bottom: 1px solid #f0f0f0;">
                            <span class="commune-dot" style="background:${{COLORS[c.statut] || COLORS.gris}}"></span>
                            <div style="flex:1;">
                                <div class="commune-name">${{c.nom}}</div>
                                <div style="font-size:11px; color:#888;">${{c.code}}</div>
                </div>
                        </div>
                    `;
                }});
            }}
            
            sidebar.innerHTML = `
                <!-- Header département -->
                <div style="background: linear-gradient(135deg, #000091 0%, #1212ff 100%); padding:16px; color:white;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                        <h2 style="font-size:18px; font-weight:700; margin:0;">📍 ${{nom}}</h2>
                        <button onclick="restoreSidebar()" style="background:rgba(255,255,255,0.2); color:white; border:none; padding:8px 14px; border-radius:6px; font-weight:600; cursor:pointer; font-size:12px;">
                            ← France
                        </button>
                </div>
                    <div style="font-size:13px; opacity:0.9;">Département ${{code}} • ${{total}} communes</div>
                </div>
                
                <!-- Filtres de statuts -->
                <div id="deptFilters" style="display:flex; flex-wrap:wrap; padding:10px; gap:6px; background:#fafafa; border-bottom:1px solid #e0e0e0;">
                </div>
                
                <!-- Recherche dans le département -->
                <div style="padding:12px 16px; background:white; border-bottom:1px solid #e0e0e0;">
                    <input type="text" id="deptSearchInput" placeholder="🔍 Rechercher une commune..." 
                        style="width:100%; padding:10px 14px; border:2px solid #e0e0e0; border-radius:8px; font-size:13px;"
                        oninput="filterDeptCommunes(this.value, '${{code}}', '${{nom}}')"
                    />
                </div>
                
                <!-- Filtre producteur -->
                <div style="padding:8px 16px; background:#fafafa; border-bottom:1px solid #e0e0e0; display:flex; flex-direction:column; gap:8px;">
                    <select id="deptProducteurSelect" onchange="onDeptProducteurChange(this.value, '${{code}}', '${{nom}}')"
                        style="width:100%; padding:8px 12px; border:2px solid #e0e0e0; border-radius:8px; font-size:12px; background:white; overflow:hidden; text-overflow:ellipsis;">
                        <option value="">👤 Tous les producteurs</option>
                    </select>
                    <button onclick="resetDeptFilters('${{code}}', '${{nom}}')" 
                        style="width:100%; padding:8px 14px; border-radius:8px; font-size:12px; font-weight:600; cursor:pointer; border:none; background:#e0e0e0; color:#1a1a1a;">
                        Réinitialiser
                    </button>
                </div>
                
                <!-- Titre liste communes -->
                <div style="padding:10px 16px; background:white; border-bottom:1px solid #e0e0e0; display:flex; justify-content:space-between; align-items:center;">
                    <span id="communesCount" style="font-weight:600; color:#1a1a1a; font-size:13px;">
                        📋 Communes ${{filteredCount !== total ? '(' + filteredCount + '/' + total + ')' : '(' + total + ')'}}
                    </span>
                    <span style="font-size:11px; color:#666;">Cliquez pour zoomer</span>
                </div>
                
                <!-- Liste des communes (scroll) -->
                <div id="communesList" style="flex:1; overflow-y:auto; background:#fff;">
                    ${{communesHtml}}
                    </div>
                `;
            
            // Stocker les infos du département
            window._currentDeptCode = code;
            window._currentDeptNom = nom;
            window._currentDeptStats = stats;
            
            // Réinitialiser le filtre département (ne pas conserver le filtre France)
            window._currentDeptProducteur = null;
            
            // S'assurer qu'on a bien toutes les communes stockées (ne pas écraser si déjà rempli)
            if (!window._currentDeptCommunes || window._currentDeptCommunes.length === 0) {{
                window._currentDeptCommunes = allCommunesProps;
                window._currentDeptTotal = total;
            }}
            
            // Utiliser toutes les communes stockées
            const allCommunes = window._currentDeptCommunes;
            const totalCommunes = window._currentDeptTotal || total;
            
            // Appliquer seulement les filtres statuts (pas de filtre producteur au départ)
            let initialFiltered = allCommunes.filter(c => activeStatuts.includes(c.statut || 'gris'));
            
            // Mettre à jour la liste avec les communes filtrées
            updateCommunesList(initialFiltered);
            
            // Mettre à jour le compteur
            const countEl = document.getElementById('communesCount');
            if (countEl) {{
                countEl.textContent = initialFiltered.length !== totalCommunes 
                    ? `📋 Communes (${{initialFiltered.length}}/${{totalCommunes}})` 
                    : `📋 Communes (${{totalCommunes}})`;
            }}
            
            // Créer les filtres dynamiquement
            setTimeout(() => updateDeptFilters(), 50);
            
            // Remplir le select producteurs avec TOUS les producteurs du département (pas seulement ceux filtrés)
            setTimeout(() => {{
                // Utiliser toutes les communes stockées, pas seulement celles filtrées
                const allCommunesForProd = window._currentDeptCommunes || allCommunesProps;
                const producteursInDept = [...new Set(allCommunesForProd.filter(c => c.producteur).map(c => c.producteur))].sort();
                const select = document.getElementById('deptProducteurSelect');
                if (select) {{
                    // Vider le select avant de le remplir
                    select.innerHTML = '<option value="">👤 Tous les producteurs</option>';
                    
                    producteursInDept.forEach(p => {{
                        const opt = document.createElement('option');
                        opt.value = p;
                        opt.textContent = p;
                        select.appendChild(opt);
                    }});
                    
                    // Restaurer le filtre producteur si défini globalement
                    if (selectedProducteur) {{
                        select.value = selectedProducteur;
                    }}
                }}
            }}, 100);
            
            // Stocker le contenu original pour restauration
            window._originalSidebarContent = originalContent;
        }}
        
        function restoreSidebar() {{
            if (window._originalSidebarContent) {{
                document.querySelector('.sidebar').innerHTML = window._originalSidebarContent;
                // Réattacher les events
                document.getElementById('producteurSelect').addEventListener('change', onProducteurChange);
                document.getElementById('searchInput').addEventListener('input', onSearch);
            }}
            // Conserver le filtre producteur si défini dans la vue département
            // selectedProducteur est déjà conservé globalement
            backToFrance();
        }}

        function backToCommuneDepartement() {{
            const deptCode = window._currentCommuneDeptCode || selectedDept || window._currentDeptCode || '';
            if (!deptCode) return;
            const deptNom =
                window._currentCommuneDeptNom ||
                window._currentDeptNom ||
                ((departementsStats[deptCode] && departementsStats[deptCode].nom) ? departementsStats[deptCode].nom : ('Département ' + deptCode));
            selectDepartement(deptCode, deptNom);
        }}
        
        function showCommuneInfo(props) {{
            const statut = props.statut || 'gris';
            const statutLabels = {{
                vert: 'ID fiabilisés',
                orange: 'ID initiés à contrôler',
                rouge: 'ID non initiés',
                gris: 'Sans donnée'
            }};
            
            const sidebar = document.querySelector('.sidebar');
            const deptCode = (props.dept || selectedDept || window._currentDeptCode || '').toString();
            const deptNom =
                props.dept_nom ||
                window._currentDeptNom ||
                ((deptCode && departementsStats[deptCode] && departementsStats[deptCode].nom) ? departementsStats[deptCode].nom : (deptCode ? ('Département ' + deptCode) : 'Département'));
            window._currentCommuneDeptCode = deptCode;
            window._currentCommuneDeptNom = deptNom;
            
            sidebar.innerHTML = `
                <!-- Header commune -->
                <div style="background: linear-gradient(135deg, ${{COLORS[statut]}} 0%, ${{COLORS[statut]}}dd 100%); padding:16px; color:white;">
                    <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:8px;">
                        <div>
                            <h2 style="font-size:18px; font-weight:700; margin:0;">🏘️ ${{props.nom}}</h2>
                            <div style="font-size:13px; opacity:0.9; margin-top:4px;">${{props.code}} • ${{deptNom}}</div>
                        </div>
                    </div>
                    <div style="display:inline-block; background:rgba(255,255,255,0.25); padding:4px 10px; border-radius:12px; font-size:11px; font-weight:600;">
                        ${{statutLabels[statut]}}
                    </div>
                </div>
                
                <!-- Navigation -->
                <div style="display:flex; border-bottom:1px solid #e0e0e0;">
                    <button onclick="restoreSidebar()" style="flex:1; background:white; color:#1a1a1a; border:none; padding:12px; font-weight:600; cursor:pointer; font-size:12px; border-right:1px solid #e0e0e0;">
                        🇫🇷 France
                    </button>
                    <button onclick="backToCommuneDepartement()" style="flex:1; background:#000091; color:white; border:none; padding:12px; font-weight:600; cursor:pointer; font-size:12px;">
                        ← Département
                    </button>
                </div>
                
                <!-- Contenu scrollable -->
                <div style="flex:1; overflow-y:auto; padding:16px;">
                    <!-- Infos générales -->
                    <div class="card">
                        <h3 style="font-size:14px;">📍 Informations</h3>
                        <div class="info-row">
                            <span class="info-label">Type composition</span>
                            <span class="info-value">${{props.type_composition || 'N/A'}}</span>
                        </div>
                    </div>
                    
                    <!-- Données BAN -->
                    <div class="card">
                        <h3 style="font-size:14px;">📊 Données BAN</h3>
                        <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:10px;">
                            <div style="background:#f5f5f5; padding:12px; border-radius:8px; text-align:center;">
                                <div style="font-size:20px; font-weight:700; color:#1a1a1a;">${{props.nb_numeros ? props.nb_numeros.toLocaleString() : '0'}}</div>
                                <div style="font-size:11px; color:#666;">Numéros</div>
                            </div>
                            <div style="background:#f5f5f5; padding:12px; border-radius:8px; text-align:center;">
                                <div style="font-size:20px; font-weight:700; color:#1a1a1a;">${{props.nb_voies || 0}}</div>
                                <div style="font-size:11px; color:#666;">Voies</div>
                            </div>
                        </div>
                        ${{props.nb_voies_avec_banid ? `
                        <div class="info-row" style="margin-top:10px;">
                            <span class="info-label">Voies avec banId</span>
                            <span class="info-value">${{props.nb_voies_avec_banid}}</span>
                        </div>
                        ` : ''}}
                    </div>
                    
                    ${{props.producteur || props.date_revision ? `
                    <!-- Producteur -->
                    <div class="card">
                        <h3 style="font-size:14px;">👤 Producteur</h3>
                        ${{props.producteur ? `
                        <div class="info-row">
                            <span class="info-label">Nom</span>
                            <span class="info-value">${{props.producteur}}</span>
                        </div>
                        ` : ''}}
                        ${{props.date_revision ? `
                        <div class="info-row">
                            <span class="info-label">Date de publication</span>
                            <span class="info-value">${{typeof props.date_revision === 'string' ? props.date_revision.split('T')[0] : props.date_revision}}</span>
                        </div>
                        ` : ''}}
                    </div>
                    ` : ''}}
                </div>
            `;
        }}
        
        // === NAVIGATION ===
        function backToFrance() {{
            closeDeptMapHoverTooltip();
            closeCommuneMapHoverTooltip();
            currentView = 'france';
            selectedDept = null;
            
            map.setView([46.603354, 1.888334], 6);
            
            // Vérifier si on doit restaurer le sidebar
            if (window._originalSidebarContent) {{
                document.querySelector('.sidebar').innerHTML = window._originalSidebarContent;
                window._originalSidebarContent = null;
                // Réattacher les events
                document.getElementById('producteurSelect').addEventListener('change', onProducteurChange);
                document.getElementById('searchInput').addEventListener('input', onSearch);
            }}
            
            // Restaurer les filtres dans l'interface
            setTimeout(() => {{
                // Restaurer le filtre producteur
                const prodSelect = document.getElementById('producteurSelect');
                if (prodSelect && selectedProducteur) {{
                    prodSelect.value = selectedProducteur;
                }}
                
                // Restaurer les chips de statut
                document.querySelectorAll('.chip').forEach(chip => {{
                    if (!chip) return;
                    const statut = chip.getAttribute('data-status');
                    if (statut && activeStatuts.includes(statut)) {{
                        chip.classList.add('active');
                        chip.classList.remove('inactive');
                    }} else if (statut) {{
                        chip.classList.remove('active');
                        chip.classList.add('inactive');
                }}
            }});
            }}, 50);
            
            // Recharger les stats si filtre producteur actif
            if (selectedProducteur) {{
                fetchAPI(`/api/producteur/${{encodeURIComponent(selectedProducteur)}}/departements`).then(stats => {{
                    departementsStats = stats || {{}};
                    showDepartementsVector();
                    showGlobalStats(); // Mettra à jour la barre supérieure avec les stats filtrées
                }});
            }} else {{
                // Recharger les stats globales si pas de filtre producteur
                fetchAPI('/api/stats/departements').then(stats => {{
                    departementsStats = stats || {{}};
                    showDepartementsVector();
                    showGlobalStats();
                }});
            }}
            
            document.getElementById('breadcrumb').innerHTML = `<span class="bc-current">🇫🇷 France</span>`;
        }}
        
        async function goToCommune(code) {{
            const commune = await fetchAPI(`/api/commune/${{code}}`);
            if (commune && commune.lat && commune.lon) {{
                map.setView([commune.lat, commune.lon], 14);
                showCommuneInfo(commune);
            }}
        }}
        
        // === SEARCH ===
        async function onSearch(e) {{
            const query = e.target.value.trim();
            const resultsDiv = document.getElementById('searchResults');
            
            if (!resultsDiv) return;
            
            if (query.length < 2) {{
                resultsDiv.classList.remove('active');
                resultsDiv.innerHTML = '';
                return;
            }}
            
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(async () => {{
                try {{
                    const results = await fetchAPI(`/api/search?q=${{encodeURIComponent(query)}}`);
                    
                    if (!results || results.length === 0) {{
                        resultsDiv.innerHTML = '<div class="search-result"><span>Aucun résultat</span></div>';
                    }} else {{
                        resultsDiv.innerHTML = results.map(r => `
                            <div class="search-result" onclick="selectSearchResult('${{r.code}}', ${{r.lat || 0}}, ${{r.lon || 0}})">
                                <span class="result-dot" style="background:${{COLORS[r.statut] || COLORS.gris}}"></span>
                                <div class="result-info">
                                    <div class="result-name">${{r.nom}}</div>
                                    <div class="result-meta">${{r.dept || ''}} - ${{r.dept_nom || ''}}</div>
                                </div>
                            </div>
                        `).join('');
                    }}
                    
                    resultsDiv.classList.add('active');
                }} catch (error) {{
                    console.error('Erreur recherche:', error);
                    resultsDiv.innerHTML = '<div class="search-result"><span>Erreur lors de la recherche</span></div>';
                    resultsDiv.classList.add('active');
                }}
            }}, 300);
        }}
        
        async function selectSearchResult(code, lat, lon) {{
            const searchResults = document.getElementById('searchResults');
            if (searchResults) {{
                searchResults.classList.remove('active');
            }}
            const searchInput = document.getElementById('searchInput');
            if (searchInput) {{
                searchInput.value = '';
            }}
            
            if (lat && lon) {{
                map.setView([lat, lon], 12);
            }}
            
            const commune = await fetchAPI(`/api/commune/${{code}}`);
            if (commune) {{
                // Load dept communes too
                if (commune.dept) {{
                    selectedDept = commune.dept;
                    currentView = 'departement';
                    const metaRes = await fetchAPI(`/api/departement/${{commune.dept}}/communes-meta`);
                    if (metaRes && metaRes.communes) {{
                        window._currentDeptCommunes = metaRes.communes;
                        window._currentDeptTotal = metaRes.total || metaRes.communes.length;
                        window._currentDeptNom = commune.dept_nom || '';
                        window._currentDeptCode = commune.dept;
                        showCommunesVector(commune.dept);
                    }}
                    
                    const breadcrumb = document.getElementById('breadcrumb');
                    if (breadcrumb) {{
                        breadcrumb.innerHTML = `
                            <span class="bc-item" onclick="backToFrance()">🇫🇷 France</span>
                            <span class="bc-sep">›</span>
                            <span class="bc-item" onclick="selectDepartement('${{commune.dept}}', '${{commune.dept_nom}}')">${{commune.dept_nom}}</span>
                            <span class="bc-sep">›</span>
                            <span class="bc-current">${{commune.nom}}</span>
                        `;
                    }}
                }}
                
                showCommuneInfo(commune);
            }}
        }}
        
        // Hide search results when clicking outside
        document.addEventListener('click', e => {{
            if (!e.target.closest('.search-box')) {{
                const searchResults = document.getElementById('searchResults');
                if (searchResults) {{
                    searchResults.classList.remove('active');
                }}
            }}
        }});
        
        // === FILTERS ===
        async function onProducteurChange(e) {{
            selectedProducteur = e.target.value || null;
            
            if (currentView === 'departement' && selectedDept) {{
                // Dans la vue département, filtrer les communes par producteur
                if (selectedProducteur) {{
                    const allCommunes = window._currentDeptCommunes || [];
                    const filtered = allCommunes.filter(c => {{
                        // Filtrer par producteur ET par statuts actifs
                        return c.producteur === selectedProducteur && activeStatuts.includes(c.statut || 'gris');
                    }});
                    updateCommunesList(filtered);
                    
                    // Mettre à jour le compteur
                    const countEl = document.getElementById('communesCount');
                    if (countEl) {{
                        countEl.textContent = `📋 Communes (${{filtered.length}}/${{allCommunes.length}})`;
                    }}
                    
                    refreshCommunesVector();
                }} else {{
                    // Réinitialiser le filtre producteur dans la vue département
                    const allCommunes = window._currentDeptCommunes || [];
                    const filtered = allCommunes.filter(c => activeStatuts.includes(c.statut || 'gris'));
                    updateCommunesList(filtered);
                    
                    const countEl = document.getElementById('communesCount');
                    if (countEl) {{
                        countEl.textContent = filtered.length !== allCommunes.length 
                            ? `📋 Communes (${{filtered.length}}/${{allCommunes.length}})` 
                            : `📋 Communes (${{allCommunes.length}})`;
                    }}
                    
                    refreshCommunesVector();
                }}
                return;
            }}
            
            // Vue France
            if (selectedProducteur) {{
                // Get stats for this producteur
                const [deptStats, banStats] = await Promise.all([
                    fetchAPI(`/api/producteur/${{encodeURIComponent(selectedProducteur)}}/departements`),
                    fetchAPI(`/api/producteur/${{encodeURIComponent(selectedProducteur)}}/stats`)
                ]);
                if (deptStats) {{
                    departementsStats = deptStats;
                    filteredBanStats = banStats || null;
                    showDepartementsVector();
                    showGlobalStats(); // Mettre à jour les stats dans la barre supérieure
                    
                    const prod = producteurs.find(p => p.nom === selectedProducteur);
                    document.getElementById('infoPanel').innerHTML = `
                        <div class="card" style="background: linear-gradient(135deg, #e8eaf6, #f3e5f5); border: 1px solid #9fa8da;">
                            <h3 style="color: #1a237e;">👤 ${{selectedProducteur}}</h3>
                            <div class="info-row">
                                <span class="info-label">Communes</span>
                                <span class="info-value">${{prod ? prod.nb_communes : 0}}</span>
                        </div>
                            <div class="info-row">
                                <span class="info-label">Départements</span>
                                <span class="info-value">${{prod ? prod.nb_depts : 0}}</span>
                            </div>
                            <div class="info-row">
                                <span class="info-label"><span style="color:${{COLORS.vert}}">●</span> Vertes</span>
                                <span class="info-value">${{prod ? prod.vert : 0}}</span>
                            </div>
                            <div class="info-row">
                                <span class="info-label"><span style="color:${{COLORS.orange}}">●</span> Oranges</span>
                                <span class="info-value">${{prod ? prod.orange : 0}}</span>
                            </div>
                            <div class="info-row">
                                <span class="info-label"><span style="color:${{COLORS.rouge}}">●</span> Rouges</span>
                                <span class="info-value">${{prod ? prod.rouge : 0}}</span>
                            </div>
                        </div>
                        <p style="text-align:center;color:#666;font-size:12px;margin-top:12px;">
                            Cliquez sur un département coloré pour voir les communes
                        </p>
                    `;
                }}
            }} else {{
                filteredBanStats = null;
                departementsStats = await fetchAPI('/api/stats/departements') || {{}};
                showDepartementsVector();
                showGlobalStats(); // Mettre à jour les stats dans la barre supérieure
            }}
        }}
        
        function toggleStatus(statut) {{
            const chip = document.querySelector(`[data-status="${{statut}}"]`);
            if (!chip) return;
            
            if (activeStatuts.includes(statut)) {{
                activeStatuts = activeStatuts.filter(s => s !== statut);
                chip.classList.remove('active');
                chip.classList.add('inactive');
            }} else {{
                activeStatuts.push(statut);
                chip.classList.add('active');
                chip.classList.remove('inactive');
            }}
            
            // Refresh view
            if (currentView === 'france') {{
                showDepartementsVector();
                showGlobalStats();
            }} else if (currentView === 'departement') {{
                const allCommunes = window._currentDeptCommunes || [];
                const filtered = allCommunes.filter(c => {{
                    const statutOk = activeStatuts.includes(c.statut || 'gris');
                    const producteurOk = !selectedProducteur || c.producteur === selectedProducteur;
                    return statutOk && producteurOk;
                }});
                updateCommunesList(filtered);
                const countEl = document.getElementById('communesCount');
                if (countEl) {{
                    countEl.textContent = filtered.length !== allCommunes.length
                        ? `📋 Communes (${{filtered.length}}/${{allCommunes.length}})`
                        : `📋 Communes (${{allCommunes.length}})`;
                }}
                refreshCommunesVector();
            }}
        }}
        
        // Mettre à jour les filtres dans la vue département
        function updateDeptFilters() {{
            const container = document.getElementById('deptFilters');
            if (!container) return;
            
            const stats = window._currentDeptStats || {{}};
            const code = window._currentDeptCode || '';
            const nom = window._currentDeptNom || '';
            
            const filterData = [
                {{ key: 'vert', label: 'ID fiabilisés', bg: '#e8f5e9', color: '#2e7d32' }},
                {{ key: 'orange', label: 'ID initiés à contrôler', bg: '#fff3e0', color: '#e65100' }},
                {{ key: 'rouge', label: 'ID non initiés', bg: '#ffebee', color: '#c62828' }},
                {{ key: 'gris', label: 'Sans donnée', bg: '#f5f5f5', color: '#616161' }}
            ];
            
            container.innerHTML = filterData.map(f => {{
                const isActive = activeStatuts.includes(f.key);
                const count = stats[f.key] || 0;
                return `
                    <div onclick="toggleDeptStatus('${{f.key}}')" 
                         style="background:${{f.bg}}; padding:6px 10px; border-radius:16px; cursor:pointer; 
                                opacity:${{isActive ? 1 : 0.35}}; border:2px solid ${{isActive ? f.color : 'transparent'}};
                                display:flex; align-items:center; gap:4px; transition: all 0.2s;">
                        <span style="font-weight:700; color:${{f.color}}; font-size:13px;">${{count}}</span>
                        <span style="font-size:10px; color:${{f.color}};">${{f.label}}</span>
                    </div>
                `;
            }}).join('');
        }}
        
        // Toggle status depuis la vue département
        function toggleDeptStatus(statut) {{
            if (activeStatuts.includes(statut)) {{
                activeStatuts = activeStatuts.filter(s => s !== statut);
            }} else {{
                activeStatuts.push(statut);
            }}
            const code = window._currentDeptCode;
            if (!code) return;
            updateDeptFilters();
            const allCommunes = window._currentDeptCommunes || [];
            const total = window._currentDeptTotal || allCommunes.length;
            const filtered = allCommunes.filter(c => activeStatuts.includes(c.statut || 'gris'));
            updateCommunesList(filtered);
            const countEl = document.getElementById('communesCount');
            if (countEl) {{
                countEl.textContent = filtered.length !== total
                    ? `📋 Communes (${{filtered.length}}/${{total}})`
                    : `📋 Communes (${{total}})`;
            }}
            refreshCommunesVector();
        }}
        
        // Gérer le changement de producteur dans la vue département
        async function onDeptProducteurChange(producteur, deptCode, deptNom) {{
            // Mettre à jour le filtre producteur globalement pour qu'il soit conservé
            selectedProducteur = producteur || null;
            
            // Appliquer le filtre
            const searchInput = document.getElementById('deptSearchInput');
            const query = searchInput ? searchInput.value : '';
            filterDeptCommunes(query, deptCode, deptNom);
        }}
        
        // Réinitialiser les filtres dans la vue département
        async function resetDeptFilters(deptCode, deptNom) {{
            // Réinitialiser les filtres
            selectedProducteur = null;
            activeStatuts = ['vert', 'orange', 'rouge', 'gris'];
            
            // Réinitialiser l'interface
            const prodSelect = document.getElementById('deptProducteurSelect');
            if (prodSelect) {{
                prodSelect.value = '';
            }}
            
            const searchInput = document.getElementById('deptSearchInput');
            if (searchInput) {{
                searchInput.value = '';
            }}
            
            // Mettre à jour les filtres de statut visuellement
            updateDeptFilters();
            
            window._deptSearchQuery = '';
            const metaRes = await fetchAPI(`/api/departement/${{deptCode}}/communes-meta`);
            if (metaRes && metaRes.communes) {{
                window._currentDeptCommunes = metaRes.communes;
                window._currentDeptTotal = metaRes.total || metaRes.communes.length;
                updateCommunesList(metaRes.communes);
                refreshCommunesVector();
                const countEl = document.getElementById('communesCount');
                if (countEl) countEl.textContent = `📋 Communes (${{metaRes.communes.length}})`;
            }}
        }}
        
        // Filtre de recherche dans le département
        function filterDeptCommunes(query, deptCode, deptNom) {{
            const communes = window._currentDeptCommunes || [];
            const total = window._currentDeptTotal || communes.length;
            const q = query.toLowerCase().trim();
            window._deptSearchQuery = q;
            
            let filtered = communes;
            
            // Filtre statut
            filtered = filtered.filter(c => activeStatuts.includes(c.statut || 'gris'));
            
            // Filtre recherche
            if (q.length > 0) {{
                filtered = filtered.filter(c => 
                    c.nom.toLowerCase().includes(q) || 
                    c.code.toLowerCase().includes(q)
                );
            }}
            
            // Filtre producteur (utiliser selectedProducteur global)
            if (selectedProducteur) {{
                filtered = filtered.filter(c => c.producteur === selectedProducteur);
            }}
            
            updateCommunesList(filtered);
            refreshCommunesVector();
            
            // Mettre à jour le compteur
            const countEl = document.getElementById('communesCount');
            if (countEl) {{
                const filteredCount = filtered.length;
                countEl.textContent = filteredCount !== total 
                    ? `📋 Communes (${{filteredCount}}/${{total}})` 
                    : `📋 Communes (${{total}})`;
            }}
        }}
        
        // Cette fonction n'est plus utilisée, le filtrage se fait via filterDeptCommunes
        
        // Mettre à jour la liste des communes
        function updateCommunesList(communes) {{
            const container = document.getElementById('communesList');
            if (!container) return;
            
            if (communes.length === 0) {{
                container.innerHTML = `<p style="color:#999; text-align:center; padding:30px; font-size:13px;">Aucune commune trouvée</p>`;
                return;
            }}
            
            container.innerHTML = communes.map(c => {{
                const datePub = c.date_revision ? (typeof c.date_revision === 'string' ? c.date_revision.split('T')[0] : c.date_revision) : null;
                return `
                <div class="commune-item" onclick="goToCommune('${{c.code}}')" style="padding:10px 12px; border-bottom: 1px solid #f0f0f0;">
                    <span class="commune-dot" style="background:${{COLORS[c.statut] || COLORS.gris}}"></span>
                    <div style="flex:1;">
                        <div class="commune-name">${{c.nom}}</div>
                        <div style="font-size:11px; color:#888;">
                            ${{c.code}}${{c.producteur ? ' • ' + c.producteur : ''}}${{datePub ? ' • 📅 ' + datePub : ''}}
                        </div>
                    </div>
                </div>
            `;
            }}).join('');
        }}
        
        function resetFilters() {{
            selectedProducteur = null;
            activeStatuts = ['vert', 'orange', 'rouge', 'gris'];
            
            const prodSelect = document.getElementById('producteurSelect');
            if (prodSelect) {{
                prodSelect.value = '';
            }}
            document.querySelectorAll('.chip').forEach(c => {{
                if (c) {{
                    c.classList.add('active');
                    c.classList.remove('inactive');
                }}
            }});
            
            // Appliquer selon la vue actuelle
            if (currentView === 'france') {{
                // Reload stats pour la vue France
                fetchAPI('/api/stats/departements').then(stats => {{
                    departementsStats = stats || {{}};
                    showDepartementsVector();
                    showGlobalStats();
                }});
            }} else if (currentView === 'departement' && selectedDept) {{
                const nom = (departementsStats[selectedDept] && departementsStats[selectedDept].nom) || '';
                selectDepartement(selectedDept, nom);
            }}
        }}
        
        
        // === INIT ===
        init();
    </script>
</body>
</html>
"""

# Afficher
components.html(app_html, height=900, scrolling=False)
