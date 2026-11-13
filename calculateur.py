"""Simulation énergétique lunaire. Python 3, bibliothèque standard uniquement.

python3 calculateur.py            # génère un cycle complet (708 h)
python3 calculateur.py --direct   # ajoute une heure simulée toutes les 0,1 s

Dépose les fichiers JSON des groupes dans le dossier groupes_json/.
Les valeurs du dictionnaire 'machines' sont supposées en kW.
"""
import argparse
import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path

DOSSIER = Path(__file__).resolve().parent
DOSSIER_GROUPES = DOSSIER / 'groupes_json'
SORTIE = DOSSIER / 'donnees_energie.json'

# 4 janvier 2030 à 03:50 heure de Paris = 02:50 UTC
DATE_DEBUT = 1893725400
PAS_SECONDES = 3600
CYCLE_LUNAIRE_H = 29.5 * 24
CAPACITE_BATTERIE_KWH = 1000.0
BATTERIE_INITIALE_PCT = 0.0
PUISSANCE_SOLAIRE_MAX_KW = 100.0
HEURES_SIMULEES_PAR_SECONDE = 10.0

# En l'absence de fichier de production, modèle solaire provisoire.
PRODUCTION_SOLAIRE_FICTIVE = True
# Les entrées des autres groupes ont leurs propres dates ; si elles ne couvrent
# pas la simulation, on conserve leur dernière mesure comme puissance constante.


def charger_groupes():
    """Charge chaque fichier JSON une seule fois par actualisation."""
    DOSSIER_GROUPES.mkdir(exist_ok=True)
    groupes = []
    for chemin in sorted(DOSSIER_GROUPES.glob('*.json')):
        try:
            donnees = json.loads(chemin.read_text(encoding='utf-8'))
            if isinstance(donnees, dict):
                groupes.append((chemin.name, donnees))
            else:
                print(f'Attention : {chemin.name} doit contenir un objet JSON.')
        except (OSError, ValueError) as erreur:
            print(f'Attention : impossible de lire {chemin.name} : {erreur}')
    return groupes


def instantane(donnees, date):
    """Récupère l'entrée disponible à la date, ou la plus proche passée.

    Si toutes les entrées sont antérieures au début de la simulation,
    la dernière est conservée. Si elles sont futures, la première est retenue.
    """
    entrees = donnees.get('entrees')
    if isinstance(entrees, list) and entrees:
        valides = [e for e in entrees if isinstance(e, dict) and isinstance(e.get('date'), (int, float))]
        if valides:
            valides.sort(key=lambda e: e['date'])
            passees = [e for e in valides if e['date'] <= date]
            return (passees[-1] if passees else valides[0]).get('donnees', {})
    return donnees


def puissances_groupes(groupes, date):
    """Somme les puissances déclarées par chaque groupe (en kW).

    Format Exemple_chat1 : donnees.piece[].machines = [{nom: puissance_kW}, ...]
    Format complémentaire : production_kw et consommation_kw au niveau racine
    ou dans donnees. Les clés production_kwh / consommation_kwh sont aussi
    acceptées, comme énergie par intervalle de 1 h.
    """
    production = 0.0
    consommation = 0.0
    for nom, groupe in groupes:
        etat = instantane(groupe, date)
        if not isinstance(etat, dict):
            continue
        for piece in etat.get('piece', []):
            if not isinstance(piece, dict):
                continue
            for machine in piece.get('machines', []):
                if not isinstance(machine, dict):
                    continue
                for nom_machine, valeur in machine.items():
                    if isinstance(valeur, (int, float)) and not isinstance(valeur, bool) and math.isfinite(valeur):
                        consommation += valeur
                    else:
                        print(f'Valeur ignorée : {nom}/{nom_machine}')
        for cle in ('production_kw', 'production_kwh'):
            valeur = etat.get(cle, groupe.get(cle, 0))
            if isinstance(valeur, (int, float)) and not isinstance(valeur, bool):
                production += valeur
                break
        for cle in ('consommation_kw', 'consommation_kwh'):
            valeur = etat.get(cle, groupe.get(cle, 0))
            if isinstance(valeur, (int, float)) and not isinstance(valeur, bool):
                consommation += valeur
                break
    return production, consommation


def solaire_kw(t_h):
    phase = 2 * math.pi * (t_h % CYCLE_LUNAIRE_H) / CYCLE_LUNAIRE_H
    return PUISSANCE_SOLAIRE_MAX_KW * max(0.0, math.sin(phase))


def energie_solaire_kwh(debut_h, fin_h):
    """Intégration trapèzes sur une heure, en kWh."""
    n = 120
    dt = (fin_h - debut_h) / n
    total = (solaire_kw(debut_h) + solaire_kw(fin_h)) / 2
    total += sum(solaire_kw(debut_h + i * dt) for i in range(1, n))
    return total * dt


def simuler_heure(heure, batterie_kwh, groupes):
    date = DATE_DEBUT + heure * PAS_SECONDES
    production_kw, consommation_kw = puissances_groupes(groupes, date)
    production_kwh = production_kw
    if PRODUCTION_SOLAIRE_FICTIVE:
        production_kwh += energie_solaire_kwh(heure, heure + 1)
    consommation_kwh = consommation_kw
    bilan = production_kwh - consommation_kwh
    batterie_kwh = min(CAPACITE_BATTERIE_KWH, max(0.0, batterie_kwh + bilan))
    mesure = {
        'date': date,  # Timestamp Unix de cette mesure (+3600 s par heure)
        'T-heure': heure,
        'production_kwh': round(production_kwh, 3),
        'consommation_kwh': round(consommation_kwh, 3),
        'batterie_%': round(100 * batterie_kwh / CAPACITE_BATTERIE_KWH, 3),
    }
    return mesure, batterie_kwh


def enregistrer(mesures):
    contenu = {'date_initiale': DATE_DEBUT, 'données': mesures}
    temporaire = SORTIE.with_suffix('.json.tmp')
    temporaire.write_text(json.dumps(contenu, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    os.replace(temporaire, SORTIE)


def main():
    parser = argparse.ArgumentParser(description='Simulateur énergétique lunaire')
    parser.add_argument('--direct', action='store_true', help='Simulation progressive')
    args = parser.parse_args()
    if CAPACITE_BATTERIE_KWH <= 0:
        raise ValueError('La capacité de batterie doit être positive.')
    if not 0 <= BATTERIE_INITIALE_PCT <= 100:
        raise ValueError('La charge initiale doit être comprise entre 0 et 100 %.')
    mesures = []
    batterie = CAPACITE_BATTERIE_KWH * BATTERIE_INITIALE_PCT / 100
    groupes = charger_groupes()
    print('Fichiers chargés :', ', '.join(n for n, _ in groupes) or 'aucun')
    print('Début UTC :', datetime.fromtimestamp(DATE_DEBUT, timezone.utc).isoformat())
    print('Sortie :', SORTIE)
    if args.direct:
        debut_reel = time.monotonic()
        heure = 0
        try:
            while True:
                heure_cible = int((time.monotonic() - debut_reel) * HEURES_SIMULEES_PAR_SECONDE)
                if heure <= heure_cible:
                    groupes = charger_groupes()
                    while heure <= heure_cible:
                        mesure, batterie = simuler_heure(heure, batterie, groupes)
                        mesures.append(mesure)
                        heure += 1
                    enregistrer(mesures)
                time.sleep(0.05)
        except KeyboardInterrupt:
            print('\nSimulation arrêtée.')
    else:
        for heure in range(math.ceil(CYCLE_LUNAIRE_H)):
            mesure, batterie = simuler_heure(heure, batterie, groupes)
            mesures.append(mesure)
        enregistrer(mesures)
        print(f'{len(mesures)} heures simulées.')


if __name__ == '__main__':
    main()
