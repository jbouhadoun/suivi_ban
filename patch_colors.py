#!/usr/bin/env python3
"""
Patch pour corriger les couleurs des communes en tenant compte du typeComposition
"""

from database import get_connection

def patch_colors():
    """
    Recalcule les couleurs :
    - VERT : bal + withBanId=true
    - ORANGE : bal + withBanId=false + voies avec banId
    - ROUGE : bal + withBanId=false + aucun banId
    - JAUNE : assemblage (peu importe withBanId)
    - GRIS : aucune donnée
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    print("🔧 Correction des couleurs selon typeComposition...")
    
    # 1. JAUNE pour assemblage
    cursor.execute("""
        UPDATE communes
        SET statut_couleur = 'jaune'
        WHERE type_composition = 'assemblage'
    """)
    jaune = cursor.rowcount
    print(f"  🟡 {jaune} communes 'assemblage' → JAUNE")
    
    # 2. VERT pour bal + withBanId
    cursor.execute("""
        UPDATE communes
        SET statut_couleur = 'vert'
        WHERE type_composition = 'bal' 
        AND with_ban_id = 1
    """)
    vert = cursor.rowcount
    print(f"  🟢 {vert} communes BAL + withBanId → VERT")
    
    # 3. ORANGE pour bal + pas withBanId + voies avec banId
    cursor.execute("""
        UPDATE communes
        SET statut_couleur = 'orange'
        WHERE type_composition = 'bal'
        AND with_ban_id = 0
        AND nb_voies_avec_banid > 0
    """)
    orange = cursor.rowcount
    print(f"  🟠 {orange} communes BAL + voies banId → ORANGE")
    
    # 4. ROUGE pour bal + pas withBanId + aucun banId
    cursor.execute("""
        UPDATE communes
        SET statut_couleur = 'rouge'
        WHERE type_composition = 'bal'
        AND with_ban_id = 0
        AND nb_voies_avec_banid = 0
    """)
    rouge = cursor.rowcount
    print(f"  🔴 {rouge} communes BAL sans banId → ROUGE")
    
    # 5. GRIS pour le reste (pas de données)
    cursor.execute("""
        UPDATE communes
        SET statut_couleur = 'gris'
        WHERE type_composition IS NULL
        OR type_composition = ''
    """)
    gris = cursor.rowcount
    print(f"  ⚫ {gris} communes sans données → GRIS")
    
    conn.commit()
    
    # Stats finales
    print("\n📊 Répartition finale :")
    cursor.execute("""
        SELECT statut_couleur, COUNT(*) 
        FROM communes 
        GROUP BY statut_couleur
    """)
    for statut, count in cursor.fetchall():
        emoji = {'vert': '🟢', 'orange': '🟠', 'rouge': '🔴', 'jaune': '🟡', 'gris': '⚫'}.get(statut, '❓')
        print(f"  {emoji} {statut}: {count:,}")
    
    conn.close()
    print("\n✅ Couleurs corrigées !")

if __name__ == "__main__":
    patch_colors()








