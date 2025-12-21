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
API_URL = os.getenv("API_URL", "http://localhost:8000")

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
        }}
        
        .header h1 {{
            font-size: 20px;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        
        .header p {{ font-size: 12px; opacity: 0.8; margin-top: 4px; }}
        
        .badge {{
            background: rgba(255,255,255,0.2);
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 11px;
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
        
        /* === MAP === */
        #map {{ flex: 1; height: 100vh; }}
        
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
                <h1>🗺️ Suivi BAN <span class="badge">IGN</span></h1>
                <p>Base Adresse Nationale - Tableau de bord</p>
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
                    <div class="chip chip-vert active" data-status="vert" onclick="toggleStatus('vert')" title="BAL nouveau socle">
                        <span class="chip-dot"></span> Nouveau
            </div>
                    <div class="chip chip-orange active" data-status="orange" onclick="toggleStatus('orange')" title="BAL ancien socle avec identifiant">
                        <span class="chip-dot"></span> Ancien+ID
            </div>
                    <div class="chip chip-rouge active" data-status="rouge" onclick="toggleStatus('rouge')" title="BAL ancien socle sans identifiant">
                        <span class="chip-dot"></span> Ancien
            </div>
                    <div class="chip chip-gris active" data-status="gris" onclick="toggleStatus('gris')" title="Pas de données">
                        <span class="chip-dot"></span> Vide
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
        <div id="map"></div>
    </div>
    
    
    <!-- Legend -->
    <div class="legend">
        <div class="legend-item">
            <span class="legend-dot" style="background:#2e7d32"></span>
            <span class="legend-label">Nouveau socle</span>
        </div>
        <div class="legend-item">
            <span class="legend-dot" style="background:#e65100"></span>
            <span class="legend-label">Ancien + ID</span>
        </div>
        <div class="legend-item">
            <span class="legend-dot" style="background:#f9a825"></span>
            <span class="legend-label">Assemblage</span>
        </div>
        <div class="legend-item">
            <span class="legend-dot" style="background:#c62828"></span>
            <span class="legend-label">Ancien sans ID</span>
        </div>
        <div class="legend-item">
            <span class="legend-dot" style="background:#616161"></span>
            <span class="legend-label">Pas de données</span>
        </div>
    </div>
    
    <!-- Zoom indicator -->
    <div class="zoom-indicator">
        Zoom: <strong id="zoomLevel">6</strong>
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
        
        let departementsData = null;
        let departementsStats = {{}};
        let producteurs = [];
        let searchTimeout = null;
        
        let departementsLayer = null;
        let communesLayer = null;
        
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
            
            // Calculer les stats filtrées
            let filteredTotal = 0;
            let filteredStats = {{ vert: 0, orange: 0, rouge: 0, gris: 0 }};
            
            // Utiliser departementsStats pour calculer les totaux filtrés
            Object.values(departementsStats).forEach(dept => {{
                activeStatuts.forEach(s => {{
                    filteredStats[s] += (dept[s] || 0);
                    filteredTotal += (dept[s] || 0);
                }});
            }});
            
            const isFiltered = activeStatuts.length < 4;
            
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
                                <div style="font-size:10px; color:#2e7d32;">Nouveau socle</div>
                            </div>
                        </div>
                        <div style="display:flex; align-items:center; gap:8px; padding:10px; background:#fff3e0; border-radius:8px; opacity:${{activeStatuts.includes('orange') ? 1 : 0.4}};">
                            <span style="width:12px; height:12px; background:${{COLORS.orange}}; border-radius:50%;"></span>
                            <div>
                                <div style="font-weight:700; color:#e65100;">${{filteredStats.orange.toLocaleString()}}</div>
                                <div style="font-size:10px; color:#e65100;">Ancien + ID</div>
                            </div>
                        </div>
                        <div style="display:flex; align-items:center; gap:8px; padding:10px; background:#ffebee; border-radius:8px; opacity:${{activeStatuts.includes('rouge') ? 1 : 0.4}};">
                            <span style="width:12px; height:12px; background:${{COLORS.rouge}}; border-radius:50%;"></span>
                            <div>
                                <div style="font-weight:700; color:#c62828;">${{filteredStats.rouge.toLocaleString()}}</div>
                                <div style="font-size:10px; color:#c62828;">Ancien sans ID</div>
                            </div>
                        </div>
                        <div style="display:flex; align-items:center; gap:8px; padding:10px; background:#f5f5f5; border-radius:8px; opacity:${{activeStatuts.includes('gris') ? 1 : 0.4}}; grid-column: span 2;">
                            <span style="width:12px; height:12px; background:${{COLORS.gris}}; border-radius:50%;"></span>
                            <div>
                                <div style="font-weight:700; color:#616161;">${{filteredStats.gris.toLocaleString()}}</div>
                                <div style="font-size:10px; color:#616161;">Pas de données</div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <h3>📈 Données BAN</h3>
                    <div class="info-row">
                        <span class="info-label">Numéros d'adresses</span>
                        <span class="info-value">${{(stats.numeros || 0).toLocaleString()}}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Voies</span>
                        <span class="info-value">${{(stats.voies || 0).toLocaleString()}}</span>
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
        
        // === INIT ===
        async function init() {{
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
            
            // Load departements GeoJSON
            departementsData = await fetchAPI('/api/departements');
            if (departementsData) {{
                showDepartements();
                showGlobalStats();
            }}
            
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
        
        // === DEPARTEMENTS ===
        function showDepartements() {{
            if (communesLayer) {{
                map.removeLayer(communesLayer);
                communesLayer = null;
            }}
            
            if (departementsLayer) {{
                map.removeLayer(departementsLayer);
            }}
            
            departementsLayer = L.geoJSON(departementsData, {{
                style: styleDepartement,
                onEachFeature: (feature, layer) => {{
                    const code = feature.properties.code;
                    const stats = departementsStats[code];
                    const nom = stats?.nom || feature.properties.nom;
                    
                    layer.on('mouseover', e => {{
                        e.target.setStyle({{ weight: 3, color: '#000091', fillOpacity: 0.9 }});
                    }});
                    
                    layer.on('mouseout', e => departementsLayer.resetStyle(e.target));
                    
                    layer.on('click', () => {{
                        if (stats && stats.total > 0) {{
                            selectDepartement(code, nom);
                        }}
                    }});
                    
                    // Tooltip détaillé
                    if (stats && stats.total > 0) {{
                        const pcts = {{
                            vert: Math.round((stats.vert || 0) / stats.total * 100),
                            orange: Math.round((stats.orange || 0) / stats.total * 100),
                            rouge: Math.round((stats.rouge || 0) / stats.total * 100),
                            gris: Math.round((stats.gris || 0) / stats.total * 100)
                        }};
                        layer.bindTooltip(`
                            <b>${{nom}}</b><br>
                            <div style="display:flex; height:10px; width:140px; border-radius:5px; overflow:hidden; margin:6px 0; border:1px solid #ddd;">
                                <div style="width:${{pcts.vert}}%; background:${{COLORS.vert}};"></div>
                                <div style="width:${{pcts.orange}}%; background:${{COLORS.orange}};"></div>
                                <div style="width:${{pcts.rouge}}%; background:${{COLORS.rouge}};"></div>
                                <div style="width:${{pcts.gris}}%; background:${{COLORS.gris}};"></div>
                            </div>
                            <span style="color:#2e7d32">●</span> ${{pcts.vert}}%
                            <span style="color:#e65100">●</span> ${{pcts.orange}}%
                            <span style="color:#c62828">●</span> ${{pcts.rouge}}%
                            <span style="color:#616161">●</span> ${{pcts.gris}}%
                        `, {{ sticky: true }});
                    }} else {{
                        layer.bindTooltip(`<b>${{nom}}</b><br><i>Aucune donnée</i>`, {{ sticky: true }});
                    }}
                }}
            }}).addTo(map);
        }}
        
        function styleDepartement(feature) {{
            const code = feature.properties.code;
            const stats = departementsStats[code];
            
            if (!stats || stats.total === 0) {{
                return {{ fillColor: '#e0e0e0', color: '#bdbdbd', weight: 1, fillOpacity: 0.4 }};
            }}
            
            // Ne compter que les statuts actifs (filtrés)
            const statuts = [
                {{ key: 'vert', value: stats.vert || 0, color: COLORS.vert }},
                {{ key: 'orange', value: stats.orange || 0, color: COLORS.orange }},
                {{ key: 'rouge', value: stats.rouge || 0, color: COLORS.rouge }},
                {{ key: 'gris', value: stats.gris || 0, color: COLORS.gris }}
            ].filter(s => activeStatuts.includes(s.key))
             .sort((a, b) => b.value - a.value);
            
            // Si aucun statut actif dans ce département → grisé
            if (statuts.length === 0 || statuts.every(s => s.value === 0)) {{
                return {{ fillColor: '#e0e0e0', color: '#bdbdbd', weight: 1, fillOpacity: 0.2 }};
            }}
            
            // Calculer le total des statuts actifs
            const activeTotal = statuts.reduce((sum, s) => sum + s.value, 0);
            
            if (activeTotal === 0) {{
                return {{ fillColor: '#e0e0e0', color: '#bdbdbd', weight: 1, fillOpacity: 0.2 }};
            }}
            
            const dominant = statuts[0];
            const pctDominant = dominant.value / activeTotal;
            
            // Opacité basée sur le % dominant (min 0.3, max 0.85)
            const opacity = 0.3 + (pctDominant * 0.55);
            
            return {{
                fillColor: dominant.color,
                color: '#fff',
                weight: 1,
                fillOpacity: opacity
            }};
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
            
            // Zoom to dept
            const deptFeature = departementsData.features.find(f => f.properties.code === code);
            if (deptFeature) {{
                const layer = L.geoJSON(deptFeature);
                map.fitBounds(layer.getBounds(), {{ padding: [50, 50] }});
                // Récupérer le nom du département si pas fourni
                if (!nom) {{
                    nom = deptFeature.properties.nom || departementsStats[code]?.nom || '';
                }}
            }}
            
            // Load communes
            const communesData = await fetchAPI(`/api/departement/${{code}}/communes`);
            if (communesData) {{
                // Stocker TOUTES les communes AVANT d'appliquer les filtres
                const allCommunes = communesData.features.map(c => c.properties);
                window._currentDeptCommunes = allCommunes;
                window._currentDeptTotal = communesData.features.length;
                
                showCommunes(communesData);
                showDeptInfo(code, nom || 'Département ' + code, communesData);
                
                // Appliquer seulement les filtres statuts (pas de filtre producteur global)
                setTimeout(() => {{
                    const filtered = allCommunes.filter(c => activeStatuts.includes(c.statut || 'gris'));
                    updateCommunesList(filtered);
                    const countEl = document.getElementById('communesCount');
                    if (countEl) {{
                        countEl.textContent = filtered.length !== allCommunes.length 
                            ? `📋 Communes (${{filtered.length}}/${{allCommunes.length}})` 
                            : `📋 Communes (${{allCommunes.length}})`;
                    }}
                    
                    // Appliquer filtres statuts
                    updateDeptFilters();
                }}, 100);
            }}
        }}
        
        // === SHOW COMMUNES ===
        function showCommunes(data) {{
            if (departementsLayer) {{
                map.removeLayer(departementsLayer);
            }}
            
            if (communesLayer) {{
                map.removeLayer(communesLayer);
            }}
            
            // Afficher TOUTES les communes du département (filtrées seulement par statut)
            // Le filtrage par producteur se fera par style (opacité) dans filterByProducteur
            communesLayer = L.geoJSON(data, {{
                filter: feature => activeStatuts.includes(feature.properties.statut || 'gris'),
                style: feature => {{
                    const props = feature.properties;
                    const statut = props.statut || 'gris';
                    
                    // Style simple : toutes les communes visibles normalement
                    return {{
                        fillColor: COLORS[statut] || COLORS.gris,
                        color: '#fff',
                        weight: 1,
                        fillOpacity: 0.7,
                        opacity: 1
                    }};
                }},
                onEachFeature: (feature, layer) => {{
                    const p = feature.properties;
                    
                    // Style simple : toujours visible normalement
                    const statut = p.statut || 'gris';
                    const initialStyle = {{
                        fillColor: COLORS[statut] || COLORS.gris,
                        color: '#fff',
                        weight: 1,
                        fillOpacity: 0.7,
                        opacity: 1
                    }};
                    
                    layer.on('mouseover', e => {{
                        // Survol : accentuer seulement le contour en bleu, garder la couleur de fond
                        const opts = e.target.options;
                        e.target.setStyle({{
                            fillColor: opts.fillColor || initialStyle.fillColor,
                            color: '#000091',
                            weight: 3,
                            fillOpacity: opts.fillOpacity !== undefined ? opts.fillOpacity : initialStyle.fillOpacity,
                            opacity: 1
                        }});
                    }});
                    
                    layer.on('mouseout', e => {{
                        // Restaurer le style depuis les options (mis à jour par filterDeptCommunes)
                        const opts = e.target.options;
                        e.target.setStyle({{
                            fillColor: opts.fillColor || initialStyle.fillColor,
                            color: '#fff',
                            weight: 1,
                            fillOpacity: opts.fillOpacity !== undefined ? opts.fillOpacity : initialStyle.fillOpacity,
                            opacity: opts.opacity !== undefined ? opts.opacity : initialStyle.opacity
                        }});
                    }});
                    
                    layer.on('click', () => {{
                        // Zoom sur la commune
                        if (p.lat && p.lon) {{
                            map.setView([p.lat, p.lon], 14);
                        }} else {{
                            // Sinon, zoomer sur les bounds de la commune
                            const bounds = layer.getBounds();
                            if (bounds && bounds.isValid()) {{
                                map.fitBounds(bounds, {{ padding: [50, 50] }});
                            }}
                        }}
                        showCommuneInfo(p);
                    }});
                    
                    layer.bindTooltip(`<b>${{p.nom}}</b>`, {{ sticky: true }});
                }}
            }}).addTo(map);
        }}
        
        // === INFO PANELS ===
        function showDeptInfo(code, nom, communesData) {{
            const communes = communesData.features || [];
            const stats = {{ vert: 0, orange: 0, rouge: 0, jaune: 0, gris: 0 }};
            
            communes.forEach(c => {{
                const s = c.properties.statut || 'gris';
                stats[s] = (stats[s] || 0) + 1;
            }});
            
            const total = communes.length;
            
            // Convertir toutes les communes en propriétés (SANS filtrer)
            const allCommunesProps = communes.map(c => c.properties);
            
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
                <div style="padding:8px 16px; background:#fafafa; border-bottom:1px solid #e0e0e0;">
                    <select id="deptProducteurSelect" onchange="filterDeptCommunes(document.getElementById('deptSearchInput').value, '${{code}}', '${{nom}}')"
                        style="width:100%; padding:8px 12px; border:2px solid #e0e0e0; border-radius:8px; font-size:12px; background:white;">
                        <option value="">👤 Tous les producteurs</option>
                    </select>
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
                    
                    // Pas de filtre producteur au départ (l'utilisateur choisira)
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
            backToFrance();
        }}
        
        function showCommuneInfo(props) {{
            const statut = props.statut || 'gris';
            const statutLabels = {{
                vert: 'BAL nouveau socle',
                orange: 'BAL ancien socle (avec ID)',
                rouge: 'BAL ancien socle (sans ID)',
                gris: 'Pas de données'
            }};
            
            const sidebar = document.querySelector('.sidebar');
            
            sidebar.innerHTML = `
                <!-- Header commune -->
                <div style="background: linear-gradient(135deg, ${{COLORS[statut]}} 0%, ${{COLORS[statut]}}dd 100%); padding:16px; color:white;">
                    <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:8px;">
                        <div>
                            <h2 style="font-size:18px; font-weight:700; margin:0;">🏘️ ${{props.nom}}</h2>
                            <div style="font-size:13px; opacity:0.9; margin-top:4px;">${{props.code}} • ${{props.dept_nom || 'Département ' + (props.dept || '')}}</div>
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
                    <button onclick="selectDepartement('${{selectedDept || props.dept}}', '${{props.dept_nom || ''}}')" style="flex:1; background:#000091; color:white; border:none; padding:12px; font-weight:600; cursor:pointer; font-size:12px;">
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
                    showDepartements();
                    showGlobalStats();
                }});
            }} else {{
                showDepartements();
                showGlobalStats();
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
                    const communesData = await fetchAPI(`/api/departement/${{commune.dept}}/communes`);
                    if (communesData) {{
                        showCommunes(communesData);
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
            
            if (selectedProducteur) {{
                // Get stats for this producteur
                const stats = await fetchAPI(`/api/producteur/${{encodeURIComponent(selectedProducteur)}}/departements`);
                if (stats) {{
                    departementsStats = stats;
                    showDepartements();
                    
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
                departementsStats = await fetchAPI('/api/stats/departements') || {{}};
                showDepartements();
                backToFrance();
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
                showDepartements();
                showGlobalStats();
            }} else if (communesLayer) {{
                // Re-filter communes
                selectDepartement(selectedDept, '');
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
                {{ key: 'vert', label: 'Nouveau', bg: '#e8f5e9', color: '#2e7d32' }},
                {{ key: 'orange', label: 'Ancien+ID', bg: '#fff3e0', color: '#e65100' }},
                {{ key: 'rouge', label: 'Ancien', bg: '#ffebee', color: '#c62828' }},
                {{ key: 'gris', label: 'Vide', bg: '#f5f5f5', color: '#616161' }}
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
        async function toggleDeptStatus(statut) {{
            // Toggle le statut
            if (activeStatuts.includes(statut)) {{
                activeStatuts = activeStatuts.filter(s => s !== statut);
            }} else {{
                activeStatuts.push(statut);
            }}
            
            const code = window._currentDeptCode;
            const nom = window._currentDeptNom;
            
            if (!code) return;
            
            // Mettre à jour visuellement les filtres
            updateDeptFilters();
            
            // Recharger les communes du département
            const communesData = await fetchAPI(`/api/departement/${{code}}/communes`);
            if (communesData) {{
                showCommunes(communesData);
                
                const total = communesData.features.length;
                
                // Mettre à jour la liste des communes (toutes, filtrage appliqué dans les fonctions)
                const allCommunes = communesData.features.map(c => c.properties);
                // NE PAS écraser si déjà rempli, garder toutes les communes
                if (!window._currentDeptCommunes || window._currentDeptCommunes.length < allCommunes.length) {{
                    window._currentDeptCommunes = allCommunes;
                    window._currentDeptTotal = communesData.features.length;
                }}
                
                // Appliquer les filtres initiaux
                const filtered = allCommunes.filter(c => activeStatuts.includes(c.statut || 'gris'));
                updateCommunesList(filtered);
                
                // Mettre à jour le compteur
                const countEl = document.getElementById('communesCount');
                if (countEl) {{
                    const filteredCount = filtered.length;
                    countEl.textContent = filteredCount !== total 
                        ? `📋 Communes (${{filteredCount}}/${{total}})` 
                        : `📋 Communes (${{total}})`;
                        }}
                    }}
                }}
                
        // Filtre de recherche dans le département
        function filterDeptCommunes(query, deptCode, deptNom) {{
            const communes = window._currentDeptCommunes || [];
            const total = window._currentDeptTotal || communes.length;
            const q = query.toLowerCase().trim();
            
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
            
            // Filtre producteur
            const prodSelect = document.getElementById('deptProducteurSelect');
            const prodValue = prodSelect ? prodSelect.value : '';
            if (prodValue) {{
                filtered = filtered.filter(c => c.producteur === prodValue);
            }}
            
            updateCommunesList(filtered);
            
            // Mettre à jour la carte : afficher seulement les communes qui matchent les filtres
            if (communesLayer) {{
                communesLayer.eachLayer(layer => {{
                    const props = layer.feature.properties;
                    const matchStatut = activeStatuts.includes(props.statut || 'gris');
                    const matchSearch = !q || props.nom.toLowerCase().includes(q) || props.code.toLowerCase().includes(q);
                    const matchProd = !prodValue || props.producteur === prodValue;
                    
                    if (matchStatut && matchSearch && matchProd) {{
                        // Commune qui matche : visible normalement
                        const statut = props.statut || 'gris';
                        const style = {{
                            fillColor: COLORS[statut] || COLORS.gris,
                            color: '#fff',
                            weight: 1,
                            fillOpacity: 0.7,
                            opacity: 1
                        }};
                        // Mettre à jour les options pour la restauration au mouseout
                        Object.assign(layer.options, style);
                        layer.setStyle(style);
                    }} else {{
                        // Commune qui ne matche pas : presque invisible
                        const style = {{ fillOpacity: 0.05, opacity: 0.1 }};
                        Object.assign(layer.options, style);
                        layer.setStyle(style);
                    }}
                }});
            }}
            
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
            
            // Reload stats
            fetchAPI('/api/stats/departements').then(stats => {{
                departementsStats = stats || {{}};
                backToFrance();
            }});
        }}
        
        
        // === INIT ===
        init();
    </script>
</body>
</html>
"""

# Afficher
components.html(app_html, height=900, scrolling=False)
