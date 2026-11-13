"""Cycle complet : python3 calculateur.py
Mode progressif : python3 calculateur.py --direct (Ctrl+C pour arrêter).
Écrit donnees_energie.json à côté de ce fichier. Aucun module à installer.
Chaque lancement recommence la simulation à t=0 et remplace le JSON.
"""
import json
import math
import os
import sys
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

# ---------- PARAMÈTRES DE LA SIMULATION ----------
delta_t_H = 1          # Pas des points ; mettre 0.5 pour 2 points par heure.
H_par_s = 10           # Heures simulées par seconde réelle.
cycle_lunaire_H = 29.5 * 24
puissance_max_kW = 100
puissance_consommee_kW = 40  # Hypothèse fictive : consommation constante.
historique_H = 2 * cycle_lunaire_H  # Durée conservée dans le JSON.
fichier_json = Path(__file__).resolve().with_name('donnees_energie.json')


def puissance_solaire(t_heures):
    """Puissance en kW : modèle fictif de jour/nuit lunaire."""
    phase = 2 * math.pi * (t_heures % cycle_lunaire_H) / cycle_lunaire_H
    return puissance_max_kW * max(0, math.sin(phase))


def puissance_consommation(t_heures):
    """Remplace ici la constante par le calcul des besoins de ta base."""
    return puissance_consommee_kW


def energie_sur_intervalle(debut_H, fin_H, puissance):
    """Intégrale de P(t) dt : kW × h = kWh (méthode des trapèzes)."""
    subdivisions = max(1, math.ceil((fin_H - debut_H) * 120))
    dt = (fin_H - debut_H) / subdivisions
    somme = (puissance(debut_H) + puissance(fin_H)) / 2
    somme += sum(puissance(debut_H + i * dt) for i in range(1, subdivisions))
    return somme * dt


def calculer_mesure(t_H):
    # Chaque valeur couvre UNE HEURE, quel que soit delta_t_H.
    # À t=0, l'heure précédente est calculée avec le modèle pour t<0.
    # Colonnes : temps_H, energie_produite_kWh, energie_consommee_kWh.
    return [
        t_H,
        energie_sur_intervalle(t_H - 1, t_H, puissance_solaire),
        energie_sur_intervalle(t_H - 1, t_H, puissance_consommation),
    ]



def ecrire_json(mesures, mode="direct"):
    donnees = {
        'version': 2,
        'mode': mode,
        'colonnes': ['temps_H', 'energie_produite_kWh', 'energie_consommee_kWh'],
        'mise_a_jour_UTC': datetime.now(timezone.utc).isoformat(),
        'delta_t_H': delta_t_H,
        'H_par_s': H_par_s,
        'duree_integration_H': 1,
        'historique_H': historique_H,
        'temps_simule_H': mesures[-1][0],
        'mesures': list(mesures),
    }
    # Remplacement atomique : le lecteur ne voit jamais un JSON à moitié écrit.
    temporaire = fichier_json.with_suffix('.json.tmp')
    try:
        temporaire.write_text(json.dumps(donnees, separators=(',', ':'), ensure_ascii=False, allow_nan=False), encoding='utf-8')
        os.replace(temporaire, fichier_json)
    finally:
        temporaire.unlink(missing_ok=True)


def lancer_direct():
    if delta_t_H <= 0 or H_par_s <= 0 or historique_H <= 0:
        raise ValueError('delta_t_H, H_par_s et historique_H doivent être positifs.')
    mesures = deque()
    debut = time.monotonic()
    prochain_indice = 0
    print(f'Simulation démarrée : pas {delta_t_H:g} h, vitesse {H_par_s:g} h/s.')
    print(f'JSON : {fichier_json}\nCtrl+C pour arrêter. Un seul calculateur à la fois.')
    try:
        while True:
            dernier_indice = math.floor((time.monotonic() - debut) * H_par_s / delta_t_H)
            if prochain_indice <= dernier_indice:
                while prochain_indice <= dernier_indice:
                    t_H = prochain_indice * delta_t_H
                    mesures.append(calculer_mesure(t_H))
                    prochain_indice += 1
                while mesures[0][0] < t_H - historique_H:
                    mesures.popleft()
                ecrire_json(mesures)
            time.sleep(min(0.05, delta_t_H / H_par_s))
    except KeyboardInterrupt:
        print('\nCalculateur arrêté. Le dernier JSON reste consultable.')


def lancer():
    """Génère toutes les mesures du cycle, puis termine."""
    if not math.isfinite(delta_t_H) or delta_t_H <= 0:
        raise ValueError('delta_t_H doit être positif et fini.')
    mesures = [calculer_mesure(i * delta_t_H)
               for i in range(math.floor(cycle_lunaire_H / delta_t_H) + 1)]
    if mesures[-1][0] < cycle_lunaire_H:
        mesures.append(calculer_mesure(cycle_lunaire_H))
    ecrire_json(mesures, mode='cycle_complet')
    print(f'Cycle complet : {cycle_lunaire_H:g} h, {len(mesures)} mesures.')
    print(f'Fichier : {fichier_json}')


if __name__ == '__main__':
    if '--direct' in sys.argv:
        lancer_direct()
    else:
        lancer()
